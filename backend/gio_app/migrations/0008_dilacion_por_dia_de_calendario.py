"""Recalcula la dilación guardada con días de calendario, como la cuenta SISA.

Antes se contaban periodos completos de 24 horas, así que cerca de un tercio de los folios quedaba
con un día menos que en SISA. Los folios abiertos se refrescan solos al consultar el tablero, pero
los liquidados conservan el valor guardado al cerrarse.
"""
from django.db import migrations
from django.utils import timezone


def recalcular(apps, schema_editor):
    Incidente = apps.get_model('gio_app', 'Incidente')
    ahora = timezone.now()
    cambiados = []
    for folio in Incidente.objects.only('pk', 'fecha_apertura', 'fecha_cierre', 'dilacion_dias'):
        if not folio.fecha_apertura:
            continue
        fin = folio.fecha_cierre or ahora
        dias = max(0, (timezone.localdate(fin) - timezone.localdate(folio.fecha_apertura)).days)
        if dias != folio.dilacion_dias:
            folio.dilacion_dias = dias
            cambiados.append(folio)
    Incidente.objects.bulk_update(cambiados, ['dilacion_dias'], batch_size=500)


class Migration(migrations.Migration):

    dependencies = [
        ('gio_app', '0007_chat_fotos'),
    ]

    operations = [
        migrations.RunPython(recalcular, migrations.RunPython.noop),
    ]
