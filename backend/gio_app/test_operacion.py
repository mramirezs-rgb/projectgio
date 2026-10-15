import io
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
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
