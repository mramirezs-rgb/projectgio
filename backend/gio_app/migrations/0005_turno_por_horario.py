import datetime

from django.db import migrations, models

# Equivalencia para los turnos guardados con el esquema anterior (por nombre).
HORARIOS = {
    'MATUTINO': (datetime.time(6, 0), datetime.time(14, 0)),
    'VESPERTINO': (datetime.time(14, 0), datetime.time(22, 0)),
    'NOCTURNO': (datetime.time(22, 0), datetime.time(6, 0)),
}


def turno_a_horario(apps, schema_editor):
    TurnoEvaluador = apps.get_model('gio_app', 'TurnoEvaluador')
    for turno in TurnoEvaluador.objects.all():
        turno.hora_inicio, turno.hora_fin = HORARIOS.get(turno.turno, HORARIOS['MATUTINO'])
        turno.save(update_fields=['hora_inicio', 'hora_fin'])


class Migration(migrations.Migration):

    dependencies = [
        ('gio_app', '0004_area_jalapa'),
    ]

    operations = [
        migrations.AddField(
            model_name='turnoevaluador',
            name='hora_inicio',
            field=models.TimeField(null=True),
        ),
        migrations.AddField(
            model_name='turnoevaluador',
            name='hora_fin',
            field=models.TimeField(null=True),
        ),
        migrations.RunPython(turno_a_horario, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='turnoevaluador',
            name='hora_inicio',
            field=models.TimeField(),
        ),
        migrations.AlterField(
            model_name='turnoevaluador',
            name='hora_fin',
            field=models.TimeField(),
        ),
        migrations.RemoveField(
            model_name='turnoevaluador',
            name='turno',
        ),
        migrations.AlterModelOptions(
            name='turnoevaluador',
            options={
                'ordering': ['fecha', 'hora_inicio', 'evaluador__expediente'],
                'verbose_name': 'turno',
                'verbose_name_plural': 'turnos',
            },
        ),
        migrations.AddConstraint(
            model_name='turnoevaluador',
            constraint=models.CheckConstraint(
                condition=models.Q(('hora_inicio', models.F('hora_fin')), _negated=True),
                name='turno_con_duracion',
            ),
        ),
    ]
