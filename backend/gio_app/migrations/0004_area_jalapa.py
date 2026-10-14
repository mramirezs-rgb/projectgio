from django.db import migrations


def xalapa_a_jalapa(apps, schema_editor):
    # Folios capturados a mano con XALAPA como área: el área correcta es JALAPA.
    Incidente = apps.get_model('gio_app', 'Incidente')
    Incidente.objects.filter(area_operativa='XALAPA').update(area_operativa='JALAPA')


class Migration(migrations.Migration):

    dependencies = [
        ('gio_app', '0003_alter_bitacoraincidente_accion_turnoevaluador'),
    ]

    operations = [
        migrations.RunPython(xalapa_a_jalapa, migrations.RunPython.noop),
    ]
