from django.db import migrations

DEFAULT_SETTINGS = {
    'site_name': 'BHIMS',
    'tagline': 'Your Home Away From Home, Near NLUC',
    'support_email': '',
    'student_registration_enabled': '1',
}


def mark_existing_houses_approved(apps, schema_editor):
    BoardingHouse = apps.get_model('core', 'BoardingHouse')
    # Listings created before the approval workflow are treated as approved so
    # they remain visible to students.
    BoardingHouse.objects.filter(status='pending').update(status='approved')


def seed_settings(apps, schema_editor):
    SiteSetting = apps.get_model('core', 'SiteSetting')
    for key, value in DEFAULT_SETTINGS.items():
        SiteSetting.objects.get_or_create(key=key, defaults={'value': value})


def unseed_settings(apps, schema_editor):
    SiteSetting = apps.get_model('core', 'SiteSetting')
    SiteSetting.objects.filter(key__in=DEFAULT_SETTINGS.keys()).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_sitesetting_boardinghouse_status'),
    ]

    operations = [
        migrations.RunPython(mark_existing_houses_approved, migrations.RunPython.noop),
        migrations.RunPython(seed_settings, unseed_settings),
    ]
