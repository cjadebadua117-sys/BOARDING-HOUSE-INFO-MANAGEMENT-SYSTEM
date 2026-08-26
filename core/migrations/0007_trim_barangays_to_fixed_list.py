from django.db import migrations

BARANGAY_DISTANCES = {
    'Arosip': '2.5 km',
    'Cabaroan': '5.6 km',
    'Casiaman': '1.5 km',
    'Salincob': '3.2 km',
    'Sapilang': 'Walking distance',
    'Say-oan': '4.5 km',
}


def apply_distances_and_trim(apps, schema_editor):
    Barangay = apps.get_model('core', 'Barangay')
    for name, distance in BARANGAY_DISTANCES.items():
        Barangay.objects.filter(name=name).update(distance_from_campus=distance)
    # The system only uses these fixed barangays; remove everything else.
    Barangay.objects.exclude(name__in=BARANGAY_DISTANCES.keys()).delete()


def reverse(apps, schema_editor):
    Barangay = apps.get_model('core', 'Barangay')
    Barangay.objects.filter(name__in=BARANGAY_DISTANCES.keys()).update(distance_from_campus='')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_barangay_distance_from_campus'),
    ]

    operations = [
        migrations.RunPython(apply_distances_and_trim, reverse),
    ]
