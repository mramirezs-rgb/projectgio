from collections import Counter
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import BitacoraIncidente, Incidente, TurnoEvaluador


def programar_turnos(evaluadores, desde, hasta, horarios):
    """Aplica un horario semanal a varios técnicos de planta interna en un rango de fechas.

    `horarios` trae 7 entradas, de lunes a domingo. Cada una es:
      - None: ese día no se modifica;
      - {'descanso': True}: se elimina el turno de ese día;
      - {'hora_inicio': ..., 'hora_fin': ...}: se crea o reemplaza el turno.
    """
    resultado = {'guardados': 0, 'eliminados': 0}
    with transaction.atomic():
        fecha = desde
        while fecha <= hasta:
            horario = horarios[fecha.weekday()]
            if horario is not None:
                if horario.get('descanso'):
                    eliminados, _ = TurnoEvaluador.objects.filter(
                        fecha=fecha, evaluador__in=evaluadores).delete()
                    resultado['eliminados'] += eliminados
                else:
                    for evaluador in evaluadores:
                        TurnoEvaluador.objects.update_or_create(
                            fecha=fecha, evaluador=evaluador,
                            defaults={'hora_inicio': horario['hora_inicio'],
                                      'hora_fin': horario['hora_fin']},
                        )
                        resultado['guardados'] += 1
            fecha += timedelta(days=1)
    return resultado


def evaluadores_de_turno(fecha):
    """Evaluadores (planta interna) con turno en la fecha indicada y cuenta activa."""
    turnos = (TurnoEvaluador.objects.filter(fecha=fecha, evaluador__is_active=True)
              .select_related('evaluador')
              .order_by('evaluador__expediente'))
    return [turno.evaluador for turno in turnos]


def repartir_folios_del_dia(fecha, responsable, limite=0):
    """Asigna evaluador a los folios abiertos que aún no lo tienen.

    Se consideran los folios no liquidados con fecha de apertura hasta la fecha del turno.
    Cada folio va al evaluador de turno con menos folios abiertos, de modo que la carga
    quede equitativa. Un evaluador solo recibe folios de su zona (área operativa) o de
    cualquier zona si no tiene área asignada.

    Con `limite` > 0 solo se reparten esa cantidad de folios, los más antiguos primero.
    """
    evaluadores = evaluadores_de_turno(fecha)
    resultado = {
        'fecha': fecha,
        'evaluadores_de_turno': len(evaluadores),
        'asignados': 0,
        'sin_zona': 0,
        'por_evaluador': {},
    }
    if not evaluadores:
        return resultado

    pendientes = (Incidente.objects.filter(evaluador__isnull=True,
                                           fecha_apertura__date__lte=fecha)
                  .exclude(estatus=Incidente.Estatus.LIQUIDADO)
                  .order_by('fecha_apertura', 'id'))
    if limite and limite > 0:
        pendientes = pendientes[:limite]

    carga = Counter()
    for evaluador in evaluadores:
        carga[evaluador.pk] = (Incidente.objects.filter(evaluador=evaluador)
                               .exclude(estatus=Incidente.Estatus.LIQUIDADO).count())

    with transaction.atomic():
        for incidente in pendientes:
            candidatos = [
                evaluador for evaluador in evaluadores
                if not evaluador.area_operativa
                or evaluador.area_operativa == incidente.area_operativa
            ]
            if not candidatos:
                resultado['sin_zona'] += 1
                continue

            elegido = min(candidatos, key=lambda ev: (carga[ev.pk], ev.expediente))
            anterior = incidente.evaluador
            incidente.evaluador = elegido
            incidente.save()
            carga[elegido.pk] += 1

            BitacoraIncidente.registrar(
                incidente, responsable, BitacoraIncidente.Accion.ASIGNACION,
                campo='evaluador',
                anterior=anterior.expediente if anterior else '',
                nuevo=elegido.expediente,
                detalle=f'Reparto de turno {fecha:%Y-%m-%d} ({timezone.now():%H:%M})',
            )
            resultado['asignados'] += 1
            resultado['por_evaluador'][elegido.expediente] = (
                resultado['por_evaluador'].get(elegido.expediente, 0) + 1)

    return resultado
