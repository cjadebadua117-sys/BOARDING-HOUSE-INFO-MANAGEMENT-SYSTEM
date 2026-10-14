from django.db import migrations, models


BACNOTAN_BARANGAYS = [
    'Agtipal', 'Arosip', 'Bacqui', 'Bacsil', 'Bagutot', 'Ballogo', 'Baroro',
    'Bitalag', 'Bulala', 'Burayoc', 'Bussaoit', 'Cabaroan', 'Cabarsican',
    'Cabugao', 'Calautit', 'Carcarmay', 'Casiaman', 'Galongen', 'Guinabang',
    'Legleg', 'Lisqueb', 'Mabanengbeng I', 'Mabanengbeng II', 'Maragayap',
    'Nagatiran', 'Nagsaraboan', 'Nagsimbaanan', 'Nangalisan', 'Narra',
    'Ortega', 'Oya-oy', 'Paagan', 'Pandan', 'Pangpang', 'Poblacion',
    'Quirino', 'Raois', 'Salincob', 'San Martin', 'Sapilang', 'Say-oan',
    'Sipulo', 'Sta. Cruz', 'Sta. Rita', 'Tammocalao', 'Ubbog', 'Zaragosa',
]


def seed_barangays(apps, schema_editor):
    Barangay = apps.get_model('core', 'Barangay')
    for name in BACNOTAN_BARANGAYS:
        Barangay.objects.get_or_create(name=name)


def unseed_barangays(apps, schema_editor):
    Barangay = apps.get_model('core', 'Barangay')
    Barangay.objects.filter(name__in=BACNOTAN_BARANGAYS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_alter_boardinghouse_barangay_alter_room_room_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='Barangay',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.RunPython(seed_barangays, unseed_barangays),
    ]
