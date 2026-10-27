import csv
import io
import os
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook
from rest_framework import status

from .models import BitacoraIncidente, Incidente, TurnoEvaluador
from .tests import BaseGIOTestCase, UsuarioGIO, imagen_en_memoria


def liquidado(folio, tecnico, evaluador, cierre=None, area='PUEBLA'):
    ahora = timezone.now()
    return Incidente.objects.create(
        folio=folio, area_operativa=area, empresa='LIQUIDADA SA', tecnico=tecnico,
        evaluador=evaluador, estatus=Incidente.Estatus.LIQUIDADO,
        fecha_apertura=ahora - timedelta(hours=3),
        fecha_cierre=cierre or ahora,
        diagnostico_final='Reparación previa registrada.',
    )


class BloqueoLiquidacionTests(BaseGIOTestCase):
    def setUp(self):
        super().setUp()
        self.cerrado = liquidado('LIQ-0001', self.tecnico, self.evaluador)
        self.url_detalle = reverse('incidente-detail', args=[self.cerrado.pk])

    def test_planta_interna_no_puede_editar_un_folio_liquidado(self):
        self.autenticar(self.evaluador)
        respuesta = self.client.patch(self.url_detalle, {'diagnostico_final': 'Cambio'}, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)

    def test_supervisor_no_puede_editar_un_folio_liquidado(self):
        self.autenticar(self.sub)
        respuesta = self.client.patch(self.url_detalle, {'obs_usuario': 'Nota'}, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)

    def test_tecnico_no_puede_reabrir_ni_editar_un_folio_liquidado(self):
        self.autenticar(self.tecnico)
        respuesta = self.client.patch(self.url_detalle, {'estatus': 'EN_PROCESO'}, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)
        self.cerrado.refresh_from_db()
        self.assertEqual(self.cerrado.estatus, Incidente.Estatus.LIQUIDADO)

    def test_no_se_vuelve_a_liquidar_un_folio_liquidado(self):
        self.autenticar(self.tecnico)
        url = reverse('incidente-liquidar', args=[self.cerrado.pk])
        respuesta = self.client.post(url, {'diagnostico_final': 'Otra vez'}, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)

    def test_no_se_carga_evidencia_en_un_folio_liquidado(self):
        self.autenticar(self.tecnico)
        url = reverse('incidente-evidencias', args=[self.cerrado.pk])
        respuesta = self.client.post(url, {'imagen': imagen_en_memoria()}, format='multipart')
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)

    def test_gerencia_puede_editar_un_folio_liquidado(self):
        self.autenticar(self.admin)
        respuesta = self.client.patch(self.url_detalle, {'obs_usuario': 'Corrección'}, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)

    def test_el_folio_liquidado_se_marca_como_bloqueado_segun_quien_consulta(self):
        self.autenticar(self.tecnico)
        self.assertTrue(self.client.get(self.url_detalle).data['bloqueado'])
        self.autenticar(self.admin)
        self.assertFalse(self.client.get(self.url_detalle).data['bloqueado'])

    def test_asignacion_masiva_omite_folios_liquidados_para_supervision(self):
        self.autenticar(self.sub)
        respuesta = self.client.post(reverse('incidente-asignar-masivo'), {
            'folios': [self.cerrado.folio],
            'tecnico': self.otro_tecnico.pk,
        }, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(respuesta.data['actualizados'], 0)
        self.assertEqual(respuesta.data['bloqueados'], [self.cerrado.folio])
        self.cerrado.refresh_from_db()
        self.assertEqual(self.cerrado.tecnico, self.tecnico)


class CancelarLiquidacionTests(BaseGIOTestCase):
    def setUp(self):
        super().setUp()
        self.cerrado = liquidado('LIQ-0002', self.tecnico, self.evaluador)
        self.url = reverse('incidente-cancelar-liquidacion', args=[self.cerrado.pk])

    def test_tecnico_asignado_cancela_dentro_de_la_hora_del_mismo_dia(self):
        self.autenticar(self.tecnico)
        respuesta = self.client.post(self.url)
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(respuesta.data['estatus'], Incidente.Estatus.PENDIENTE)
        self.assertIsNone(respuesta.data['fecha_cierre'])
        self.assertTrue(BitacoraIncidente.objects.filter(
            incidente=self.cerrado,
            accion=BitacoraIncidente.Accion.CANCELACION_LIQUIDACION).exists())

    def test_tecnico_no_cancela_despues_de_una_hora(self):
        Incidente.objects.filter(pk=self.cerrado.pk).update(
            fecha_cierre=timezone.now() - timedelta(hours=2))
        self.autenticar(self.tecnico)
        self.assertEqual(self.client.post(self.url).status_code, status.HTTP_403_FORBIDDEN)

    def test_tecnico_no_cancela_una_liquidacion_de_otro_dia(self):
        Incidente.objects.filter(pk=self.cerrado.pk).update(
            fecha_cierre=timezone.now() - timedelta(days=1))
        self.autenticar(self.tecnico)
        self.assertEqual(self.client.post(self.url).status_code, status.HTTP_403_FORBIDDEN)

    def test_planta_interna_no_cancela_liquidaciones(self):
        self.autenticar(self.evaluador)
        self.assertEqual(self.client.post(self.url).status_code, status.HTTP_403_FORBIDDEN)

    def test_gerencia_cancela_en_cualquier_momento(self):
        Incidente.objects.filter(pk=self.cerrado.pk).update(
            fecha_cierre=timezone.now() - timedelta(days=5))
        self.autenticar(self.admin)
        self.assertEqual(self.client.post(self.url).status_code, status.HTTP_200_OK)

    def test_ventana_de_cancelacion_en_el_modelo(self):
        zona = timezone.get_current_timezone()
        cierre = timezone.make_aware(datetime(2026, 10, 14, 10, 0), zona)
        tecnico = self.tecnico
        folio = Incidente(folio='VENT-1', tecnico=tecnico, estatus=Incidente.Estatus.LIQUIDADO,
                          fecha_cierre=cierre)
        self.assertTrue(folio.puede_cancelar_liquidacion(tecnico, cierre + timedelta(minutes=30)))
        self.assertFalse(folio.puede_cancelar_liquidacion(tecnico, cierre + timedelta(minutes=61)))
        self.assertFalse(folio.puede_cancelar_liquidacion(
            tecnico, timezone.make_aware(datetime(2026, 10, 15, 0, 5), zona)))


class TurnosYRepartoTests(BaseGIOTestCase):
    def setUp(self):
        super().setUp()
        self.hoy = timezone.localdate()
        self.manana = self.hoy + timedelta(days=1)
        self.url_turnos = reverse('turnos')
        self.url_reparto = reverse('turnos-repartir')
        self.nuevos = [
            Incidente.objects.create(
                folio=f'NEW-{n}', area_operativa='PUEBLA', empresa='NUEVA',
                estatus=Incidente.Estatus.PENDIENTE,
                fecha_apertura=timezone.now() - timedelta(days=1, minutes=n))
            for n in range(4)
        ]

    HORARIO = {'hora_inicio': '06:00', 'hora_fin': '14:00'}

    def programar(self, evaluadores, desde, hasta, horarios):
        self.autenticar(self.admin)
        return self.client.post(self.url_turnos, {
            'evaluadores': [e.pk for e in evaluadores],
            'desde': desde.isoformat(),
            'hasta': hasta.isoformat(),
            'horarios': horarios,
        }, format='json')

    def turnar(self, fecha, *evaluadores):
        return self.programar(evaluadores, fecha, fecha, [self.HORARIO] * 7)

    def lunes(self):
        return self.hoy - timedelta(days=self.hoy.weekday())

    def test_semana_de_6_a_14_con_sabado_de_15_a_23(self):
        lunes = self.lunes()
        horarios = [self.HORARIO] * 5 + [{'hora_inicio': '15:00', 'hora_fin': '23:00'}, None]
        respuesta = self.programar([self.evaluador, self.otro_evaluador], lunes,
                                   lunes + timedelta(days=6), horarios)
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(respuesta.data['guardados'], 12)

        consulta = self.client.get(self.url_turnos, {
            'desde': lunes.isoformat(), 'hasta': (lunes + timedelta(days=6)).isoformat()}).data
        self.assertEqual(len(consulta), 12)
        sabado = (lunes + timedelta(days=5)).isoformat()
        self.assertEqual({(t['hora_inicio'], t['hora_fin']) for t in consulta if t['fecha'] == sabado},
                         {('15:00', '23:00')})
        domingo = (lunes + timedelta(days=6)).isoformat()
        self.assertFalse([t for t in consulta if t['fecha'] == domingo])

    def test_descanso_elimina_el_dia_y_sin_cambios_lo_conserva(self):
        lunes = self.lunes()
        self.programar([self.evaluador], lunes, lunes + timedelta(days=6), [self.HORARIO] * 7)
        self.programar([self.evaluador], lunes, lunes + timedelta(days=6),
                       [{'descanso': True}] + [None] * 6)
        self.assertFalse(TurnoEvaluador.objects.filter(fecha=lunes).exists())
        self.assertTrue(TurnoEvaluador.objects.filter(fecha=lunes + timedelta(days=1)).exists())

    def test_reprogramar_reemplaza_el_horario_del_dia(self):
        self.turnar(self.hoy, self.evaluador)
        self.programar([self.evaluador], self.hoy, self.hoy,
                       [{'hora_inicio': '15:00', 'hora_fin': '23:00'}] * 7)
        turno = TurnoEvaluador.objects.get(fecha=self.hoy, evaluador=self.evaluador)
        self.assertEqual(turno.hora_inicio.strftime('%H:%M'), '15:00')

    def test_turno_nocturno_cruza_medianoche(self):
        self.programar([self.evaluador], self.hoy, self.hoy,
                       [{'hora_inicio': '23:00', 'hora_fin': '07:00'}] * 7)
        consulta = self.client.get(self.url_turnos, {'fecha': self.hoy.isoformat()}).data
        self.assertTrue(consulta[0]['cruza_medianoche'])

    def test_validaciones_de_la_programacion(self):
        casos = [
            ([self.evaluador], self.hoy, self.hoy, [{'hora_inicio': '06:00', 'hora_fin': '06:00'}] * 7),
            ([self.evaluador], self.hoy, self.hoy - timedelta(days=1), [self.HORARIO] * 7),
            ([self.evaluador], self.hoy, self.hoy + timedelta(days=70), [self.HORARIO] * 7),
            ([self.evaluador], self.hoy, self.hoy, [None] * 7),
            ([self.tecnico], self.hoy, self.hoy, [self.HORARIO] * 7),
        ]
        for evaluadores, desde, hasta, horarios in casos:
            respuesta = self.programar(evaluadores, desde, hasta, horarios)
            self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST, respuesta.data)
        self.assertFalse(TurnoEvaluador.objects.exists())

    def test_planta_externa_no_gestiona_turnos(self):
        self.autenticar(self.tecnico)
        self.assertEqual(self.client.get(self.url_turnos).status_code, status.HTTP_403_FORBIDDEN)

    def test_reparto_equitativo_entre_los_de_turno(self):
        # Cada evaluador ya tiene un folio abierto; el reparto debe emparejar la carga.
        self.turnar(self.hoy, self.evaluador, self.otro_evaluador)
        self.autenticar(self.admin)
        respuesta = self.client.post(self.url_reparto, {'fecha': self.hoy.isoformat()}, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(respuesta.data['asignados'], 4)
        self.assertEqual(respuesta.data['por_evaluador'], {'OQU-8821': 2, 'OQU-9000': 2})

    def test_reparto_con_limite_toma_los_mas_antiguos(self):
        self.turnar(self.hoy, self.evaluador, self.otro_evaluador)
        self.autenticar(self.admin)
        respuesta = self.client.post(self.url_reparto,
                                     {'fecha': self.hoy.isoformat(), 'limite': 1}, format='json')
        self.assertEqual(respuesta.data['asignados'], 1)
        primero = Incidente.objects.get(folio='NEW-3')  # el de apertura más antigua
        self.assertIsNotNone(primero.evaluador)

    def test_reparto_respeta_la_zona_del_evaluador(self):
        self.otro_evaluador.area_operativa = 'VERACRUZ'
        self.otro_evaluador.save()
        self.turnar(self.hoy, self.evaluador, self.otro_evaluador)
        self.autenticar(self.admin)
        respuesta = self.client.post(self.url_reparto, {'fecha': self.hoy.isoformat()}, format='json')
        self.assertEqual(respuesta.data['por_evaluador'], {'OQU-8821': 4})

    def test_reparto_no_toma_folios_abiertos_despues_de_la_fecha_del_turno(self):
        self.nuevos[0].fecha_apertura = timezone.now() + timedelta(days=2)
        self.nuevos[0].save()
        self.turnar(self.hoy, self.evaluador)
        self.autenticar(self.admin)
        self.client.post(self.url_reparto, {'fecha': self.hoy.isoformat()}, format='json')
        self.nuevos[0].refresh_from_db()
        self.assertIsNone(self.nuevos[0].evaluador)

    def test_reparto_sin_turnos_no_asigna_nada(self):
        self.autenticar(self.admin)
        respuesta = self.client.post(self.url_reparto,
                                     {'fecha': self.manana.isoformat()}, format='json')
        self.assertEqual(respuesta.data['evaluadores_de_turno'], 0)
        self.assertEqual(respuesta.data['asignados'], 0)


class FiltrosPorZonaTests(BaseGIOTestCase):
    def setUp(self):
        super().setUp()
        self.ajeno.central = 'CENTRAL VERACRUZ'
        self.ajeno.save()
        self.tecnico.area_operativa = 'PUEBLA'
        self.tecnico.save()
        self.otro_tecnico.area_operativa = 'VERACRUZ'
        self.otro_tecnico.save()

    def test_centrales_se_filtran_por_area(self):
        self.autenticar(self.admin)
        datos = self.client.get(reverse('centrales-list'), {'area': 'PUEBLA'}).data
        self.assertEqual([(c['nombre'], c['area']) for c in datos], [('LOS PINOS', 'PUEBLA')])

    def test_tecnicos_se_filtran_por_zona(self):
        self.autenticar(self.admin)
        datos = self.client.get(reverse('tecnicos-list'), {'area': 'VERACRUZ'}).data
        self.assertEqual({t['expediente'] for t in datos}, {'TEC-9999'})

    def test_evaluadores_se_filtran_por_zona(self):
        self.autenticar(self.admin)
        datos = self.client.get(reverse('evaluadores-list'), {'area': 'PUEBLA'}).data
        self.assertEqual(len(datos), 2)  # sin zona asignada cuentan para cualquier área


class DesempenoDeCampoTests(BaseGIOTestCase):
    def test_supervision_ve_la_carga_de_tecnicos_y_evaluadores(self):
        self.autenticar(self.sub)
        datos = self.client.get(reverse('incidente-desempeno')).data
        externa = {f['expediente']: f for f in datos['tecnicos_planta_externa']}
        interna = {f['expediente']: f for f in datos['tecnicos_planta_interna']}
        self.assertEqual(externa['TEC-4410']['abiertos'], 1)
        self.assertEqual(externa['TEC-9999']['abiertos'], 1)
        self.assertEqual(interna['OQU-8821']['abiertos'], 1)
        self.assertEqual(interna['OQU-9000']['abiertos'], 1)

    def test_planta_externa_no_ve_el_desempeno(self):
        self.autenticar(self.tecnico)
        self.assertEqual(self.client.get(reverse('incidente-desempeno')).status_code,
                         status.HTTP_403_FORBIDDEN)

    def test_tecnico_liquidado_hoy_se_cuenta(self):
        liquidado('LIQ-HOY', self.tecnico, None)
        self.autenticar(self.admin)
        fila = next(f for f in self.client.get(reverse('incidente-desempeno')).data[
            'tecnicos_planta_externa'] if f['expediente'] == 'TEC-4410')
        self.assertEqual(fila['liquidados'], 1)
        self.assertEqual(fila['liquidados_hoy'], 1)
        self.assertIsNotNone(fila['mttr_horas_promedio'])


ENCABEZADO_SISA = 'FOLIO,EMPRESA,ÁREA,CENTRAL,TÉCNICO ASIGNADO,TELÉFONO TECNICO\n'


def correr(comando, contenido, *argumentos):
    """Ejecuta un comando de importación sobre un CSV con el formato del reporte SISA."""
    salida = io.StringIO()
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = Path(carpeta) / 'reporte.csv'
        ruta.write_text(ENCABEZADO_SISA + contenido, encoding='utf-8')
        call_command(comando, '--archivo', str(ruta), *argumentos, stdout=salida)
    return salida.getvalue()


class ImportacionTelefonoTecnicoTests(BaseGIOTestCase):
    def test_ingesta_guarda_el_telefono_del_reporte_en_el_tecnico(self):
        correr('ingesta_sisa', '98765432,UNINET,JALAPA,XALAPA,LUIS SERRANO,2221112233\n',
               '--sin-mover')
        self.tecnico.refresh_from_db()
        self.assertEqual(self.tecnico.telefono, '2221112233')
        folio = Incidente.objects.get(folio='98765432')
        self.assertEqual(folio.tecnico, self.tecnico)
        self.assertEqual((folio.area_operativa, folio.central), ('JALAPA', 'XALAPA'))

    def test_ingesta_vincula_por_telefono_cuando_el_nombre_no_coincide(self):
        self.tecnico.telefono = '222 111 2233'
        self.tecnico.save()
        correr('ingesta_sisa', '98765433,UNINET,PUEBLA,LOS PINOS,L. SERRANO M.,2221112233\n',
               '--sin-mover')
        folio = Incidente.objects.get(folio='98765433')
        self.assertEqual(folio.tecnico, self.tecnico)
        self.assertEqual(folio.estatus, Incidente.Estatus.ASIGNADO)

    def test_ingesta_no_sobrescribe_un_telefono_existente(self):
        self.tecnico.telefono = '2229998877'
        self.tecnico.save()
        correr('ingesta_sisa', '98765434,UNINET,PUEBLA,LOS PINOS,LUIS SERRANO,2221112233\n',
               '--sin-mover')
        self.tecnico.refresh_from_db()
        self.assertEqual(self.tecnico.telefono, '2229998877')

    def test_dry_run_no_guarda_el_telefono(self):
        correr('ingesta_sisa', '98765435,UNINET,PUEBLA,LOS PINOS,LUIS SERRANO,2221112233\n',
               '--dry-run')
        self.tecnico.refresh_from_db()
        self.assertEqual(self.tecnico.telefono, '')

    def test_importar_tecnicos_da_de_alta_con_telefono_y_completa_existentes(self):
        correr('importar_tecnicos',
               '1,UNINET,PUEBLA,LOS PINOS,JUAN CARLOS HERNANDEZ MUNOZ,2222299341\n'
               '2,UNINET,PUEBLA,LOS PINOS,LUIS SERRANO,2221112233\n',
               '--confirmar')
        nuevo = UsuarioGIO.objects.get(first_name='JUAN CARLOS')
        self.assertEqual(nuevo.telefono, '2222299341')
        self.assertEqual(nuevo.rol, UsuarioGIO.Rol.TECNICO)
        self.tecnico.refresh_from_db()
        self.assertEqual(self.tecnico.telefono, '2221112233')

    def test_importar_tecnicos_sin_confirmar_no_cambia_nada(self):
        salida = correr('importar_tecnicos', '2,UNINET,PUEBLA,LOS PINOS,LUIS SERRANO,2221112233\n')
        self.assertIn('sin teléfono', salida)
        self.tecnico.refresh_from_db()
        self.assertEqual(self.tecnico.telefono, '')


ENCABEZADO_OQU = 'FOLIO,EMPRESA,ÁREA,TÉCNICO ASIGNADO,OQU\n'


def correr_oqu(comando, contenido, *argumentos):
    salida = io.StringIO()
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = Path(carpeta) / 'reporte.csv'
        ruta.write_text(ENCABEZADO_OQU + contenido, encoding='utf-8')
        call_command(comando, '--archivo', str(ruta), *argumentos, stdout=salida)
    return salida.getvalue()


class OquPlantaInternaTests(BaseGIOTestCase):
    def test_folio_nuevo_toma_al_tecnico_de_planta_interna_de_oqu(self):
        correr_oqu('ingesta_sisa', '55500001,UNINET,PUEBLA,LUIS SERRANO,CARLA EVALUADORA\n',
                   '--sin-mover')
        folio = Incidente.objects.get(folio='55500001')
        self.assertEqual(folio.evaluador, self.evaluador)
        self.assertEqual(folio.oqu, 'CARLA EVALUADORA')

    def test_folio_existente_sin_planta_interna_la_completa(self):
        self.ajeno.evaluador = None
        self.ajeno.save()
        correr_oqu('ingesta_sisa', f'{self.ajeno.folio},UNINET,VERACRUZ,,CARLA EVALUADORA\n',
                   '--sin-mover')
        self.ajeno.refresh_from_db()
        self.assertEqual(self.ajeno.evaluador, self.evaluador)

    def test_folio_existente_conserva_su_tecnico_de_planta_interna(self):
        correr_oqu('ingesta_sisa', f'{self.ajeno.folio},UNINET,VERACRUZ,,CARLA EVALUADORA\n',
                   '--sin-mover')
        self.ajeno.refresh_from_db()
        self.assertEqual(self.ajeno.evaluador, self.otro_evaluador)

    def test_oqu_desconocido_se_reporta_y_no_se_asigna(self):
        salida = correr_oqu('ingesta_sisa', '55500002,UNINET,PUEBLA,,JUDITH DIAZ LOZANO\n',
                            '--sin-mover')
        self.assertIn('JUDITH DIAZ LOZANO', salida)
        self.assertIsNone(Incidente.objects.get(folio='55500002').evaluador)

    def test_importar_tecnicos_da_de_alta_al_oqu_como_planta_interna(self):
        correr_oqu('importar_tecnicos', '1,UNINET,PUEBLA,,JUDITH DIAZ LOZANO\n', '--confirmar')
        nuevo = UsuarioGIO.objects.get(first_name='JUDITH')
        self.assertEqual(nuevo.rol, UsuarioGIO.Rol.PI_EVALUADOR)
        self.assertTrue(nuevo.expediente.startswith('OQU-'))

    def test_importar_tecnicos_omite_las_cuentas_de_operadora(self):
        salida = correr_oqu('importar_tecnicos',
                            '1,UNINET,PUEBLA,,CASPUE OPERADORA INTERNET\n'
                            '2,UNINET,PUEBLA,,MERIDA OPERADORA TRANS\n'
                            '3,UNINET,PUEBLA,,JUDITH DIAZ LOZANO\n', '--confirmar')
        self.assertIn('2 nombre(s) omitido(s)', salida)
        self.assertTrue(UsuarioGIO.objects.filter(first_name='JUDITH').exists())
        self.assertFalse(UsuarioGIO.objects.filter(last_name__icontains='OPERADORA').exists())

    def test_importar_tecnicos_excluye_los_nombres_indicados(self):
        correr_oqu('importar_tecnicos', '1,UNINET,PUEBLA,,BUZON GENERAL SOPORTE\n',
                   '--confirmar', '--excluir', 'buzon')
        self.assertFalse(UsuarioGIO.objects.filter(first_name__icontains='BUZON').exists())

    def test_importar_tecnicos_toma_las_dos_ultimas_palabras_como_apellidos(self):
        correr_oqu('importar_tecnicos',
                   '1,UNINET,PUEBLA,,MARIA MARTINA SILVIA JARAMILLO CORTEZ\n', '--confirmar')
        nuevo = UsuarioGIO.objects.get(last_name='JARAMILLO CORTEZ')
        self.assertEqual(nuevo.first_name, 'MARIA MARTINA SILVIA')

    def test_ingesta_no_reporta_cuentas_de_operadora_en_oqu(self):
        salida = correr_oqu('ingesta_sisa', '55500003,UNINET,PUEBLA,,CASPUE OPERADORA INTERNET\n',
                            '--sin-mover')
        self.assertNotIn('OPERADORA', salida)
        self.assertIsNone(Incidente.objects.get(folio='55500003').evaluador)


class ExportacionReporteTests(BaseGIOTestCase):
    url = reverse('incidente-exportar')

    def setUp(self):
        super().setUp()
        for numero in range(30):
            Incidente.objects.create(folio=f'EXP-{numero:04d}', area_operativa='PUEBLA',
                                     empresa=f'EMPRESA {numero}')

    def filas_csv(self, respuesta):
        texto = respuesta.content.decode('utf-8-sig')
        return list(csv.reader(io.StringIO(texto)))

    def hoja_xlsx(self, respuesta):
        return load_workbook(io.BytesIO(respuesta.content)).active

    def test_exporta_todos_los_folios_filtrados_sin_paginar(self):
        self.autenticar(self.sub)
        respuesta = self.client.get(self.url, {'formato': 'csv', 'area_operativa': 'PUEBLA',
                                               'page_size': 20})
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        filas = self.filas_csv(respuesta)
        folios = {fila[0] for fila in filas[1:]}
        self.assertEqual(len(folios), 31)
        self.assertIn(self.propio.folio, folios)
        self.assertNotIn(self.ajeno.folio, folios)
        self.assertEqual(respuesta['X-Total-Folios'], '31')

    def test_excel_por_omision_con_encabezado_fechas_y_numeros(self):
        liquidado('LIQ-EXP', self.tecnico, self.evaluador)
        self.autenticar(self.admin)
        respuesta = self.client.get(self.url, {'search': 'LIQ-EXP'})
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertIn('spreadsheetml', respuesta['Content-Type'])
        self.assertIn('.xlsx', respuesta['Content-Disposition'])

        hoja = self.hoja_xlsx(respuesta)
        encabezados = [celda.value for celda in hoja[1]]
        fila = dict(zip(encabezados, [celda.value for celda in hoja[2]]))
        self.assertEqual(fila['Folio'], 'LIQ-EXP')
        self.assertEqual(fila['Técnico de planta externa'], 'Luis Serrano')
        self.assertIsInstance(fila['Apertura'], datetime)
        self.assertAlmostEqual(fila['MTTR (horas)'], 3, places=1)
        self.assertEqual(hoja.freeze_panes, 'A2')
        self.assertTrue(hoja.auto_filter.ref)

    def test_csv_neutraliza_textos_que_serian_formulas(self):
        Incidente.objects.create(folio='EXP-FORMULA', area_operativa='PUEBLA',
                                 empresa='=HYPERLINK("http://x","clic")')
        self.autenticar(self.admin)
        respuesta = self.client.get(self.url, {'formato': 'csv', 'search': 'EXP-FORMULA'})
        filas = self.filas_csv(respuesta)
        empresa = filas[1][filas[0].index('Empresa')]
        self.assertEqual(empresa, '\'=HYPERLINK("http://x","clic")')

    def test_excel_guarda_como_texto_lo_que_parece_formula(self):
        Incidente.objects.create(folio='EXP-FORMULA', area_operativa='PUEBLA', empresa='=1+1')
        self.autenticar(self.admin)
        respuesta = self.client.get(self.url, {'search': 'EXP-FORMULA'})
        hoja = self.hoja_xlsx(respuesta)
        columna = [celda.value for celda in hoja[1]].index('Empresa')
        celda = hoja[2][columna]
        self.assertEqual(celda.data_type, 's')
        self.assertEqual(celda.value, '=1+1')

    def test_solo_supervision_y_gerencia_pueden_exportar(self):
        for usuario in (self.tecnico, self.evaluador):
            self.autenticar(usuario)
            respuesta = self.client.get(self.url)
            self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)

    def test_formato_invalido(self):
        self.autenticar(self.admin)
        respuesta = self.client.get(self.url, {'formato': 'pdf'})
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_limite_de_filas(self):
        self.autenticar(self.admin)
        with patch('gio_app.views.MAX_FILAS', 5):
            respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('máximo por reporte', str(respuesta.data['detail']))


class ChatFolioTests(BaseGIOTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse('incidente-mensajes', args=[self.propio.pk])
        self.url_pendientes = reverse('incidente-pendientes-de-chat')

    def escribir(self, usuario, texto, url=None):
        self.autenticar(usuario)
        return self.client.post(url or self.url, {'texto': texto}, format='json')

    def pendientes(self, usuario):
        self.autenticar(usuario)
        return self.client.get(self.url_pendientes).data

    def test_planta_externa_e_interna_conversan_en_el_folio(self):
        respuesta = self.escribir(self.tecnico, '  Llegué al sitio, el par está mojado.  ')
        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED)
        self.assertEqual(respuesta.data['texto'], 'Llegué al sitio, el par está mojado.')
        self.assertEqual(respuesta.data['autor_rol'], UsuarioGIO.Rol.TECNICO)
        self.escribir(self.evaluador, 'Enterado, veo el puerto caído en gestión.')

        respuesta = self.client.get(self.url)
        self.assertEqual([m['autor'] for m in respuesta.data],
                         [self.tecnico.pk, self.evaluador.pk])
        self.assertEqual(respuesta.data[1]['autor_nombre'], self.evaluador.nombre_completo)

    def test_quien_no_ve_el_folio_no_ve_ni_escribe_en_su_chat(self):
        self.escribir(self.tecnico, 'Mensaje interno del folio')
        for usuario in (self.otro_tecnico, self.otro_evaluador):
            self.autenticar(usuario)
            self.assertEqual(self.client.get(self.url).status_code, status.HTTP_404_NOT_FOUND)
            self.assertEqual(self.escribir(usuario, 'Hola').status_code,
                             status.HTTP_404_NOT_FOUND)

    def test_mensaje_vacio_o_demasiado_largo_se_rechaza(self):
        self.assertEqual(self.escribir(self.tecnico, '   ').status_code,
                         status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.escribir(self.tecnico, 'x' * 2001).status_code,
                         status.HTTP_400_BAD_REQUEST)
        self.assertFalse(self.propio.mensajes.exists())

    def test_consulta_incremental_trae_solo_los_mensajes_nuevos(self):
        primero = self.escribir(self.tecnico, 'Uno').data['id']
        self.escribir(self.evaluador, 'Dos')
        self.autenticar(self.tecnico)
        respuesta = self.client.get(self.url, {'despues': primero})
        self.assertEqual([m['texto'] for m in respuesta.data], ['Dos'])
        self.assertEqual(self.client.get(self.url, {'despues': 'x'}).status_code,
                         status.HTTP_400_BAD_REQUEST)

    def test_avisa_de_mensajes_sin_leer_hasta_que_se_abre_el_chat(self):
        self.escribir(self.tecnico, 'Necesito que liberen el puerto')
        self.escribir(self.tecnico, 'Sigo en sitio')

        avisos = self.pendientes(self.evaluador)
        self.assertEqual(avisos['total'], 2)
        self.assertEqual(avisos['por_folio'], {str(self.propio.pk): 2})
        self.assertEqual(avisos['recientes'][0]['folio'], self.propio.folio)
        self.assertEqual(avisos['recientes'][0]['ultimo']['texto'], 'Sigo en sitio')
        self.assertEqual(self.pendientes(self.tecnico)['total'], 0)

        self.autenticar(self.evaluador)
        self.client.get(self.url)
        self.assertEqual(self.pendientes(self.evaluador)['total'], 0)

        self.escribir(self.tecnico, 'Ya quedó')
        self.assertEqual(self.pendientes(self.evaluador)['total'], 1)

    def test_supervision_solo_recibe_avisos_de_los_chats_en_que_participa(self):
        self.escribir(self.tecnico, 'Reporte de avance')
        self.assertEqual(self.pendientes(self.sub)['total'], 0)

        self.escribir(self.sub, 'Den prioridad a este folio')
        self.escribir(self.tecnico, 'Enterado')
        self.assertEqual(self.pendientes(self.sub)['total'], 1)
        self.assertEqual(self.pendientes(self.admin)['total'], 0)

    def test_se_puede_conversar_en_un_folio_liquidado(self):
        cerrado = liquidado('LIQ-CHAT', self.tecnico, self.evaluador)
        url = reverse('incidente-mensajes', args=[cerrado.pk])
        self.assertEqual(self.escribir(self.evaluador, 'Revisa el cierre', url).status_code,
                         status.HTTP_201_CREATED)
        cerrado.refresh_from_db()
        self.assertEqual(cerrado.estatus, Incidente.Estatus.LIQUIDADO)


class ChatFotosTests(BaseGIOTestCase):
    def setUp(self):
        super().setUp()
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        ajuste = override_settings(MEDIA_ROOT=carpeta.name, EVIDENCIA_MAX_BYTES=512 * 1024)
        ajuste.enable()
        self.addCleanup(ajuste.disable)
        self.url = reverse('incidente-mensajes', args=[self.propio.pk])

    def enviar(self, usuario, **datos):
        self.autenticar(usuario)
        return self.client.post(self.url, datos, format='multipart')

    def test_planta_interna_y_externa_envian_fotos_con_o_sin_texto(self):
        respuesta = self.enviar(self.tecnico, imagen=imagen_en_memoria(), texto='Así está el par')
        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED)
        self.assertEqual(respuesta.data['texto'], 'Así está el par')
        self.assertTrue(respuesta.data['imagen_url'].startswith('http://testserver/media/chat/'))
        self.assertNotIn('imagen', respuesta.data)

        respuesta = self.enviar(self.evaluador, imagen=imagen_en_memoria('gestion.png'))
        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED)
        self.assertEqual(respuesta.data['texto'], '')

        mensajes = self.client.get(self.url).data
        self.assertTrue(all(m['imagen_url'] for m in mensajes))
        self.assertFalse(self.propio.evidencias.exists())
        self.assertGreater(self.propio.mensajes.first().tamano_bytes, 0)

    def test_mensaje_sin_texto_ni_foto_se_rechaza(self):
        respuesta = self.enviar(self.tecnico, texto='  ')
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('texto', respuesta.data)

    def test_archivo_que_no_es_imagen_se_rechaza(self):
        archivo = SimpleUploadedFile('nota.jpg', b'no es una imagen', content_type='image/jpeg')
        respuesta = self.enviar(self.tecnico, imagen=archivo)
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('imagen', respuesta.data)

    @override_settings(EVIDENCIA_MAX_BYTES=1024)
    def test_foto_demasiado_pesada_se_rechaza(self):
        grande = imagen_en_memoria(tamano=(900, 900), calidad=98)
        respuesta = self.enviar(self.tecnico, imagen=grande)
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('límite', str(respuesta.data['imagen']))
        self.assertFalse(self.propio.mensajes.exists())

    def test_el_aviso_indica_que_llego_una_foto(self):
        self.enviar(self.tecnico, imagen=imagen_en_memoria())
        self.autenticar(self.evaluador)
        avisos = self.client.get(reverse('incidente-pendientes-de-chat')).data
        self.assertEqual(avisos['recientes'][0]['ultimo']['texto'], 'Envió una foto')


class LiquidacionPorGerenciaTests(BaseGIOTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse('incidente-detail', args=[self.propio.pk])

    def editar(self, usuario, datos, url=None):
        self.autenticar(usuario)
        return self.client.patch(url or self.url, datos, format='json')

    def test_gerencia_liquida_desde_cualquier_estatus(self):
        respuesta = self.editar(self.admin, {
            'estatus': Incidente.Estatus.LIQUIDADO, 'diagnostico_final': 'Cerrado en SISA',
        })
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(respuesta.data['estatus'], Incidente.Estatus.LIQUIDADO)
        self.assertIsNotNone(respuesta.data['fecha_cierre'])

        sin_tecnico = reverse('incidente-detail', args=[self.ajeno.pk])
        self.ajeno.tecnico = None
        self.ajeno.save()
        respuesta = self.editar(self.admin, {
            'estatus': Incidente.Estatus.LIQUIDADO, 'desc_liq': 'Servicio restablecido',
        }, sin_tecnico)
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(respuesta.data['estatus'], Incidente.Estatus.LIQUIDADO)

    def test_gerencia_necesita_diagnostico_o_descripcion_para_liquidar(self):
        respuesta = self.editar(self.admin, {'estatus': Incidente.Estatus.LIQUIDADO})
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('diagnostico_final', respuesta.data)

    def test_al_escribir_la_descripcion_de_liquidacion_gerencia_liquida(self):
        respuesta = self.editar(self.admin, {
            'estatus': Incidente.Estatus.ASIGNADO, 'desc_liq': 'Se cambió la acometida',
        })
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(respuesta.data['estatus'], Incidente.Estatus.LIQUIDADO)
        registro = BitacoraIncidente.objects.get(
            incidente=self.propio, accion=BitacoraIncidente.Accion.LIQUIDACION)
        self.assertEqual(registro.valor_anterior, Incidente.Estatus.ASIGNADO)
        self.assertIn('descripción de liquidación', registro.detalle)
        self.assertEqual(registro.usuario, self.admin)

    def test_si_gerencia_elige_otro_estatus_se_respeta(self):
        respuesta = self.editar(self.admin, {
            'estatus': Incidente.Estatus.EN_PROCESO, 'desc_liq': 'Pendiente de confirmar',
        })
        self.assertEqual(respuesta.data['estatus'], Incidente.Estatus.EN_PROCESO)

    def test_una_descripcion_que_ya_estaba_no_liquida(self):
        # La ingesta SISA puede traer la descripción; editar otro campo no debe liquidar.
        self.propio.desc_liq = 'Texto de SISA'
        self.propio.save()
        respuesta = self.editar(self.admin, {
            'desc_liq': 'Texto de SISA', 'obs_usuario': 'Revisado por Gerencia',
        })
        self.assertEqual(respuesta.data['estatus'], Incidente.Estatus.ASIGNADO)

    def test_las_demas_areas_conservan_las_reglas(self):
        for usuario in (self.sub, self.evaluador):
            respuesta = self.editar(usuario, {'desc_liq': f'Descripción de {usuario.expediente}'})
            self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
            self.assertEqual(respuesta.data['estatus'], Incidente.Estatus.ASIGNADO)
        respuesta = self.editar(self.sub, {
            'estatus': Incidente.Estatus.LIQUIDADO, 'diagnostico_final': 'Cerrado',
        })
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_solo_gerencia_ve_liquidado_entre_los_estatus_posibles(self):
        self.autenticar(self.admin)
        self.assertIn(Incidente.Estatus.LIQUIDADO, self.client.get(self.url).data['transiciones_validas'])
        self.autenticar(self.sub)
        self.assertNotIn(Incidente.Estatus.LIQUIDADO,
                         self.client.get(self.url).data['transiciones_validas'])

    def test_boton_liquidar_de_gerencia_acepta_solo_la_descripcion(self):
        self.autenticar(self.admin)
        respuesta = self.client.post(reverse('incidente-liquidar', args=[self.propio.pk]),
                                     {'desc_liq': 'Restablecido'}, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(respuesta.data['estatus'], Incidente.Estatus.LIQUIDADO)
        self.assertEqual(respuesta.data['desc_liq'], 'Restablecido')


class CarpetaCompartidaSisaTests(BaseGIOTestCase):
    """La carpeta de intercambio puede ser una carpeta compartida en red con otra computadora."""

    def setUp(self):
        super().setUp()
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        self.raiz = Path(carpeta.name)
        self.entrada = self.raiz / 'sisa_imports'
        self.salida = self.raiz / 'sisa_exports'
        self.entrada.mkdir()
        ajuste = override_settings(
            PRIVATE_DATA_DIR=self.raiz, SISA_IMPORTS_DIR=self.entrada,
            SISA_IMPORTS_PROCESADOS_DIR=self.entrada / 'procesados', SISA_EXPORTS_DIR=self.salida)
        ajuste.enable()
        self.addCleanup(ajuste.disable)

    def depositar(self, nombre, contenido, hace_segundos=600):
        ruta = self.entrada / nombre
        ruta.write_text(ENCABEZADO_SISA + contenido, encoding='utf-8')
        marca = timezone.now().timestamp() - hace_segundos
        os.utime(ruta, (marca, marca))
        return ruta

    def ingestar(self, *argumentos):
        salida = io.StringIO()
        call_command('ingesta_sisa', *argumentos, stdout=salida, stderr=io.StringIO())
        return salida.getvalue()

    def test_ingesta_la_carpeta_y_archiva_lo_leido(self):
        self.depositar('reporte.csv', '70000001,UNINET,PUEBLA,LOS PINOS,,\n')
        self.ingestar()
        self.assertTrue(Incidente.objects.filter(folio='70000001').exists())
        self.assertFalse((self.entrada / 'reporte.csv').exists())
        self.assertEqual(len(list((self.entrada / 'procesados').glob('reporte_*.csv'))), 1)

    def test_espera_a_que_termine_de_copiarse_el_archivo(self):
        ruta = self.depositar('reporte.csv', '70000002,UNINET,PUEBLA,LOS PINOS,,\n',
                              hace_segundos=5)
        salida = self.ingestar()
        self.assertIn('se sigue copiando', salida)
        self.assertFalse(Incidente.objects.filter(folio='70000002').exists())
        self.assertTrue(ruta.exists())
        self.ingestar('--espera', '0')
        self.assertTrue(Incidente.objects.filter(folio='70000002').exists())

    def test_lee_el_xls_que_en_realidad_es_una_tabla_html(self):
        ruta = self.entrada / 'reporte.xls'
        ruta.write_text('<html><body><table><tr><th>FOLIO</th><th>EMPRESA</th><th>ÁREA</th>'
                        '<th>TÉCNICO ASIGNADO</th></tr><tr><td>70000005</td><td>UNINET</td>'
                        '<td>PUEBLA</td><td>LUIS SERRANO</td></tr></table></body></html>',
                        encoding='utf-8')
        self.ingestar('--espera', '0')
        folio = Incidente.objects.get(folio='70000005')
        self.assertEqual(folio.tecnico, self.tecnico)

    def test_carpeta_de_red_inaccesible_da_un_error_claro(self):
        with override_settings(SISA_IMPORTS_DIR=self.entrada / 'reporte.csv' / 'no-existe'):
            self.depositar('reporte.csv', '70000006,UNINET,PUEBLA,LOS PINOS,,\n')
            with self.assertRaisesMessage(CommandError, 'No se puede abrir la carpeta'):
                self.ingestar()

    def test_ignora_los_archivos_temporales_de_excel(self):
        (self.entrada / '~$reporte.xlsx').write_bytes(b'bloqueo de Excel')
        salida = self.ingestar()
        self.assertIn('Sin archivos pendientes', salida)
        self.assertTrue((self.entrada / '~$reporte.xlsx').exists())

    def test_si_no_puede_archivar_sigue_con_los_demas_archivos(self):
        self.depositar('a.csv', '70000003,UNINET,PUEBLA,LOS PINOS,,\n')
        self.depositar('b.csv', '70000004,UNINET,PUEBLA,LOS PINOS,,\n')
        movimiento_real = shutil.move

        def mover(origen, destino):
            if origen.endswith('a.csv'):
                raise PermissionError('El archivo está abierto en otra computadora')
            return movimiento_real(origen, destino)

        with patch('gio_app.management.commands.ingesta_sisa.shutil.move', side_effect=mover):
            salida = self.ingestar()
        self.assertIn('no se pudo archivar', salida)
        self.assertEqual(Incidente.objects.filter(folio__in=['70000003', '70000004']).count(), 2)
        self.assertFalse((self.entrada / 'b.csv').exists())

    def test_retorno_no_se_sobrescribe_si_se_genera_dos_veces_en_el_mismo_minuto(self):
        liquidado('LIQ-A', self.tecnico, self.evaluador)
        call_command('exportar_sisa', stdout=io.StringIO())
        liquidado('LIQ-B', self.tecnico, self.evaluador)
        call_command('exportar_sisa', stdout=io.StringIO())
        archivos = sorted(self.salida.glob('RETORNO_SISA_*.csv'))
        self.assertEqual(len(archivos), 2)
        folios = set()
        for archivo in archivos:
            with archivo.open(encoding='utf-8-sig') as contenido:
                folios.update(fila['FOLIO'] for fila in csv.DictReader(contenido))
        self.assertEqual(folios, {'LIQ-A', 'LIQ-B'})
        self.assertEqual(list(self.salida.glob('*.tmp')), [])

    def test_retorno_fallido_no_marca_los_folios_como_exportados(self):
        folio = liquidado('LIQ-C', self.tecnico, self.evaluador)
        with patch('gio_app.management.commands.exportar_sisa.os.replace',
                   side_effect=PermissionError('Carpeta de red sin permiso de escritura')):
            with self.assertRaisesMessage(CommandError, 'siguen pendientes'):
                call_command('exportar_sisa', stdout=io.StringIO())
        folio.refresh_from_db()
        self.assertFalse(folio.exportado_sisa)
        self.assertEqual(list(self.salida.glob('*')), [])


class RefrescoSisaTests(BaseGIOTestCase):
    """Lo que GIO registra no se pierde cuando el reporte SISA vuelve a traer el folio."""

    def test_sin_columna_de_enlace_no_borra_el_estado_registrado(self):
        self.propio.estado_enlace = Incidente.EstadoEnlace.UP
        self.propio.save()
        correr('ingesta_sisa', f'{self.propio.folio},SERVICIOS MULTIPLES,PUEBLA,LOS PINOS,,\n',
               '--sin-mover')
        self.propio.refresh_from_db()
        self.assertEqual(self.propio.estado_enlace, Incidente.EstadoEnlace.UP)
        self.assertFalse(self.propio.bitacora.filter(accion=BitacoraIncidente.Accion.INGESTA)
                         .exists())

    def test_folio_nuevo_sin_columna_de_enlace_queda_desconocido(self):
        correr('ingesta_sisa', '70000010,UNINET,PUEBLA,LOS PINOS,,\n', '--sin-mover')
        self.assertEqual(Incidente.objects.get(folio='70000010').estado_enlace,
                         Incidente.EstadoEnlace.DESCONOCIDO)

    def test_no_reemplaza_la_liquidacion_hecha_en_gio(self):
        folio = liquidado('70000011', self.tecnico, self.evaluador)
        folio.cve_liq, folio.desc_liq = 'R01', 'Cambio de módem'
        folio.estado_enlace = Incidente.EstadoEnlace.UP
        folio.save()
        salida = io.StringIO()
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / 'reporte.csv'
            ruta.write_text('FOLIO,EMPRESA,CVE LIQ,DESC LIQ,ESTATUS I/O\n'
                            '70000011,NUEVA RAZON SOCIAL,X99,Pendiente de visita,DOWN\n',
                            encoding='utf-8')
            call_command('ingesta_sisa', '--archivo', str(ruta), stdout=salida)
        folio.refresh_from_db()
        self.assertEqual((folio.cve_liq, folio.desc_liq), ('R01', 'Cambio de módem'))
        self.assertEqual(folio.estado_enlace, Incidente.EstadoEnlace.UP)
        self.assertEqual(folio.empresa, 'NUEVA RAZON SOCIAL')


class ValidacionesRevisionTests(BaseGIOTestCase):
    def test_liquidar_rechaza_valores_fuera_de_catalogo(self):
        self.propio.estatus = Incidente.Estatus.EN_PROCESO
        self.propio.save()
        self.autenticar(self.tecnico)
        url = reverse('incidente-liquidar', args=[self.propio.pk])
        for datos in ({'estado_enlace': 'ARRIBA'}, {'codigo_fallo': 'XYZ'}, {'cve_liq': 'C' * 51}):
            respuesta = self.client.post(url, {'diagnostico_final': 'Se cambió el módem.', **datos},
                                         format='json')
            self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST, datos)
        self.propio.refresh_from_db()
        self.assertEqual(self.propio.estatus, Incidente.Estatus.EN_PROCESO)

    def test_planta_interna_guarda_direccion_y_telefono(self):
        self.autenticar(self.evaluador)
        respuesta = self.client.patch(reverse('incidente-detail', args=[self.propio.pk]), {
            'dir_pta_a': 'Av. Reforma 100', 'telefono_tecnico': '2221234567',
        }, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.propio.refresh_from_db()
        self.assertEqual((self.propio.dir_pta_a, self.propio.telefono_tecnico),
                         ('Av. Reforma 100', '2221234567'))

    def test_quitar_el_tecnico_en_lote_regresa_el_folio_a_pendiente(self):
        self.autenticar(self.sub)
        respuesta = self.client.post(reverse('incidente-asignar-masivo'), {
            'folios': [self.propio.folio], 'tecnico': None,
        }, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.propio.refresh_from_db()
        self.assertIsNone(self.propio.tecnico)
        self.assertEqual(self.propio.estatus, Incidente.Estatus.PENDIENTE)

    def test_rango_de_fechas_incluye_el_dia_final(self):
        hoy = timezone.localdate().isoformat()
        Incidente.objects.create(folio='HOY-0001', area_operativa='PUEBLA')
        self.autenticar(self.admin)
        respuesta = self.client.get(reverse('incidente-metricas'),
                                    {'abierto_desde': hoy, 'abierto_hasta': hoy})
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(respuesta.data['total'], 1)
