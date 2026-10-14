from django.db import migrations

# The only barangays the system offers by default: the six near DMMMSU NLUC.
# Admins can add more through Admin -> Edit Barangays, but nothing else is
# seeded, so the landlord dropdown never offers an off-list parish.
ALLOWED_BARANGAYS = {
    'Arosip': '2.5 km',
    'Cabaroan': '5.6 km',
    'Casiaman': '1.5 km',
    'Salincob': '3.2 km',
    'Sapilang': 'Walking distance',
    'Say-oan': '4.5 km',
}


def restrict_to_allowed(apps, schema_editor):
    Barangay = apps.get_model('core', 'Barangay')
    # Guarantee the six exist (a previous state may have removed some), then
    # drop anything else. House rows keep their barangay string (CharField, not
    # a FK), so trimming only removes dropdown choices, never a listing.
    for name, distance in ALLOWED_BARANGAYS.items():
        Barangay.objects.get_or_create(
            name=name,
            defaults={'distance_from_campus': distance},
        )
    Barangay.objects.exclude(name__in=ALLOWED_BARANGAYS.keys()).delete()


def noop(apps, schema_editor):
    # Re-adding the removed rows is not desired; the seeder can recreate any of
    # the six, and admins manage the rest.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_inquiry_last_viewed_by_student'),
    ]

    operations = [
        migrations.RunPython(restrict_to_allowed, noop),
    ]
