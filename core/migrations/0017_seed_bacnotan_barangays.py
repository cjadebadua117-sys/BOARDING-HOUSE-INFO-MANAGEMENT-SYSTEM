from django.db import migrations

# Seed the six Bacnotan barangays near DMMMSU NLUC so the Barangay table is
# populated out of the box and the hardcoded fallback lists in models/forms
# are only ever needed on a fresh, un-migrated database.
BARANGAYS = [
    ('Arosip', '2.5 km'),
    ('Cabaroan', '5.6 km'),
    ('Casiaman', '1.5 km'),
    ('Salincob', '3.2 km'),
    ('Sapilang', 'Walking distance'),
    ('Say-oan', '4.5 km'),
]


def seed_barangays(apps, schema_editor):
    Barangay = apps.get_model('core', 'Barangay')
    for name, distance in BARANGAYS:
        Barangay.objects.get_or_create(
            name=name,
            defaults={'distance_from_campus': distance},
        )


def unseed_barangays(apps, schema_editor):
    # Leave user-created/edited rows alone; only remove untouched seeds.
    Barangay = apps.get_model('core', 'Barangay')
    for name, distance in BARANGAYS:
        Barangay.objects.filter(name=name, distance_from_campus=distance).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_alter_user_program_custom'),
    ]

    operations = [
        migrations.RunPython(seed_barangays, unseed_barangays),
    ]
