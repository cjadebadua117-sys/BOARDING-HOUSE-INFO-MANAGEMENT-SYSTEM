from django.db import migrations, models


def clear_other(apps, schema_editor):
    User = apps.get_model('core', 'User')
    # "Other" is no longer a choice; blank the program but keep any typed text.
    User.objects.filter(program='OTHER').update(program='')


def restore_other(apps, schema_editor):
    User = apps.get_model('core', 'User')
    User.objects.filter(program='', program_custom='').update(program='OTHER')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_user_program_custom_alter_user_program'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='program',
            field=models.CharField(blank=True, choices=[
                ('CE', 'College of Education'),
                ('CA', 'College of Agriculture'),
                ('CAS', 'College of Arts and Sciences'),
                ('CVM', 'College of Veterinary Medicine'),
                ('CAFF', 'College of Agroforestry & Forestry'),
                ('IABM', 'Institute of Agribusiness Management'),
                ('CIS', 'College of Information Systems'),
                ('IES', 'Institute of Environmental Studies'),
                ('IABE', 'Institute of Agricultural & Biosystems Engineering'),
                ('K12', 'K-12 / Senior High School'),
            ], max_length=10),
        ),
        migrations.RunPython(clear_other, restore_other),
    ]
