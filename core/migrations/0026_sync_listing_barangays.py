from django.db import migrations


def _pretty(name):
    """The display spelling for a free-text barangay value.

    Listings store their barangay as plain text, so one admin may type
    "poblacion" while the table says "Poblacion". Only the first letter is
    touched: "Say-oan" and "Sta. Cruz" must keep their internal casing.
    """
    name = (name or '').strip()
    if name and (name.islower() or name.isupper()):
        return name[:1].upper() + name[1:].lower()
    return name


def sync_barangays(apps, schema_editor):
    """Add a barangay row for every barangay an existing listing uses.

    Migration 0024 deleted every barangay except the six near campus. Listing
    rows kept their barangay string (it is a CharField, not a FK), so houses in
    the removed barangays stayed visible on Browse Listings while the filter no
    longer offered their barangay: eight of twelve cards could not be filtered,
    and Admin -> Edit Barangays showed no row for them at all.

    A listing's barangay is real data, so it has to exist in the table the
    admin manages. This restores those rows (nothing is deleted) and fixes
    rows typed entirely in lower/upper case.
    """
    Barangay = apps.get_model('core', 'Barangay')
    BoardingHouse = apps.get_model('core', 'BoardingHouse')

    for barangay in list(Barangay.objects.all()):
        pretty = _pretty(barangay.name)
        if not pretty or pretty == barangay.name:
            continue
        clash = Barangay.objects.filter(name__iexact=pretty).exclude(pk=barangay.pk)
        if clash.exists():
            continue
        barangay.name = pretty
        barangay.save(update_fields=['name'])

    existing = {(b.name or '').strip().casefold() for b in Barangay.objects.all()}
    values = (
        BoardingHouse.objects.exclude(barangay='')
        .values_list('barangay', flat=True)
        .distinct()
    )
    for value in values:
        name = _pretty(value)
        key = name.casefold()
        if not name or key in existing:
            continue
        Barangay.objects.create(name=name)
        existing.add(key)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_alter_landlordrating_booking'),
    ]

    operations = [
        # Reversing would delete rows an admin may since have used, so the
        # reverse is intentionally a no-op: the table is additive here.
        migrations.RunPython(sync_barangays, migrations.RunPython.noop),
    ]
