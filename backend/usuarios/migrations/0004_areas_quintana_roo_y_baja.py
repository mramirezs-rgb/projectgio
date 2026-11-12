from django.db import migrations, models


def bajas_al_area_de_bajas(apps, schema_editor):
    # Los usuarios que ya estaban dados de baja salen de su zona para no mezclarse con los activos.
    UsuarioGIO = apps.get_model('usuarios', 'UsuarioGIO')
    UsuarioGIO.objects.filter(is_active=False).update(area_operativa='BAJA')


class Migration(migrations.Migration):

    dependencies = [
        ("usuarios", "0003_area_jalapa"),
    ]

    operations = [
        migrations.AlterField(
            model_name="usuariogio",
            name="area_operativa",
            field=models.CharField(
                blank=True,
                choices=[
                    ("PUEBLA", "Puebla"),
                    ("PACHUCA", "Pachuca"),
                    ("VERACRUZ", "Veracruz"),
                    ("POZA RICA", "Poza Rica"),
                    ("JALAPA", "Jalapa"),
                    ("TLAXCALA", "Tlaxcala"),
                    ("CORDOBA", "Córdoba"),
                    ("COATZACOALCOS", "Coatzacoalcos"),
                    ("QUINTANA ROO", "Quintana Roo"),
                    ("BAJA", "Baja"),
                ],
                default="",
                max_length=50,
            ),
        ),
        migrations.RunPython(bajas_al_area_de_bajas, migrations.RunPython.noop),
    ]
