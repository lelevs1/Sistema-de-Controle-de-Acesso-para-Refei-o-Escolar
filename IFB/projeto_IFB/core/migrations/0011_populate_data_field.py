from django.db import migrations

def preencher_data(apps, schema_editor):
    Almoco = apps.get_model('core', 'Almoco')
    # Para cada almoço existente, define a data como a data do campo data_hora
    for almoco in Almoco.objects.all():
        almoco.data = almoco.data_hora.date()
        almoco.save()

class Migration(migrations.Migration):
    dependencies = [
        ('core', '0010_almoco_data_alter_almoco_unique_together'),
    ]

    operations = [
        migrations.RunPython(preencher_data),
    ]
    from django.db import migrations

def preencher_data(apps, schema_editor):
    Almoco = apps.get_model('core', 'Almoco')
    # Para cada almoço existente, define a data como a data do campo data_hora
    for almoco in Almoco.objects.all():
        almoco.data = almoco.data_hora.date()
        almoco.save()

class Migration(migrations.Migration):
    dependencies = [
        ('core', '0010_almoco_data_alter_almoco_unique_together'),
    ]

    operations = [
        migrations.RunPython(preencher_data),
    ]