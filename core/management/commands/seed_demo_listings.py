"""Seed demo boarding houses, landlords, students, bookings and ratings.

Usage:
    python manage.py seed_demo_listings
    python manage.py seed_demo_listings --reset
    python manage.py seed_demo_listings --houses 6
    python manage.py seed_demo_listings --image C:/path/to/your-photo.jpg

Creates (or updates), all owned by the demo landlords:

  * three landlord accounts with different numbers of ratings, so the landing
    page's "most rated landlord" ordering has something real to rank;
  * twelve approved boarding houses, each in a barangay that exists in the
    Barangay table — the command refuses to invent one;
  * rooms per house, with the room photos supplied for the demo seated on
    them, which is what the landing row shows;
  * students, a confirmed booking each, and the ratings that come from them.

Everything is matched by name, so running it twice updates rather than
duplicates, and `--reset` removes only what this command created. A house you
added by hand, and its owner, are never touched.

Ratings are the reason the three landlords exist: a rating row needs a
confirmed booking and one rating per student per landlord, so the ranking the
landing page uses is built from the same records the app itself would write.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import (
    Amenity, Barangay, BoardingHouse, Booking, LandlordRating, Room, RoomPhoto, User,
)

DEFAULT_PASSWORD = 'DemoLandlord2026!'
STUDENT_PASSWORD = 'DemoStudent2026!'

# username, full name, phone, how many ratings this landlord has received.
#
# The counts differ on purpose: the landing row is ordered by ratings, and with
# everyone on zero that ordering cannot be seen, tested, or demonstrated.
LANDLORDS = (
    ('demo_landlord', 'Elena Villaflor', '0917 000 0001', 8),
    ('demo_landlord_2', 'Rodolfo Reyes', '0917 000 0002', 5),
    ('demo_landlord_3', 'Marites Bautista', '0917 000 0003', 2),
)

# Two exterior photos the project already ships, cropped into a set so the
# browse and detail pages do not all show the same building.
IMAGE_SOURCES = (
    'core/static/core/images/dmmmsu-campus-hd.jpg',
    'media/boarding_images/610c9981b86a42fcacd261e68b75c5d9.webp',
)

# Real room photos supplied for the demo, used for the room galleries and for
# the landing row. Kept as files in media/room_photos/.
ROOM_SOURCE_GLOB = 'media/room_photos/room-source-*.png'

AMENITIES = (
    'Wi-Fi', 'Water Included', 'Electricity Included', 'Own CR',
    'Shared Kitchen', 'Study Area', 'CCTV', 'Parking', 'Laundry Area',
    'Air Conditioning',
)

# The six barangays the system offers by default, with a plain-language
# distance note. Every seeded house must name one of these: see
# _check_barangays(). Admins extend the list through Edit Barangays; the demo
# seed deliberately stays inside the default set so it never adds choices of
# its own.
BARANGAYS = (
    ('Salincob', '10 min walk to NLUC'),
    ('Cabaroan', '5 min walk to NLUC'),
    ('Say-oan', '8 min walk to NLUC'),
    ('Sapilang', '12 min walk to NLUC'),
    ('Casiaman', '1 jeepney ride'),
    ('Arosip', '1 tricycle ride'),
)

# name, barangay, street address, headline rent, gender, owner index, rooms,
# description.
#
# `rooms` is (room_type, monthly_rate, capacity, available). A house whose
# rooms are all unavailable is a full house: the card shows its "Full" badge
# instead of a price, a state worth having in demo data.
HOUSES = (
    (
        'Villa Elena Boarding House', 'Salincob', 'Purok 3, Salincob',
        1200, BoardingHouse.GenderAllowed.BOTH, 0,
        (('Single Room', 1200, 1, True), ('Double Sharing', 900, 2, True),
         ('Bedspace (4 pax)', 650, 4, True)),
        'Three rooms behind the Salincob covered court, a ten-minute walk from the '
        'NLUC gate. Water and electricity are included in the rent, and the shared '
        'kitchen opens onto a covered drying area.',
    ),
    (
        "Auring's Transient Home", 'Cabaroan', 'Rizal Street, Cabaroan',
        1500, BoardingHouse.GenderAllowed.FEMALE, 1,
        (('Aircon Room', 1800, 2, True), ('Non-aircon Room', 1200, 2, True),
         ('Single Room', 1500, 1, True)),
        "A quiet house for female students along Rizal Street, five minutes on foot "
        'from campus. Rooms are air-conditioned on request, and the gate is locked '
        'at 10 PM with CCTV on the entrance.',
    ),
    (
        'Reyes Boarding Inn', 'Say-oan', 'Say-oan East, near the chapel',
        1000, BoardingHouse.GenderAllowed.BOTH, 1,
        (('Double Sharing', 1000, 2, True), ('Bedspace (4 pax)', 700, 4, True)),
        'Family-run boarding inn a short walk from the NLUC main gate. Rent covers '
        'water and Wi-Fi; each room has its own comfort room and a study table.',
    ),
    (
        'Casa Bacnotan Dormitory', 'Cabaroan', 'Cabaroan junction, Bacnotan',
        1800, BoardingHouse.GenderAllowed.BOTH, 0,
        (('Studio Type', 1800, 2, True), ('Aircon Room', 2200, 2, True),
         ('Single Room', 1500, 1, True), ('Double Sharing', 1100, 2, True)),
        'Newly built dormitory at the Cabaroan junction, one tricycle ride from NLUC. '
        'Every room is air-conditioned, with a study area per floor and gated '
        'parking for motorcycles.',
    ),
    (
        "Del Pilar Ladies' Dorm", 'Sapilang', 'Del Pilar Street, Sapilang',
        1350, BoardingHouse.GenderAllowed.FEMALE, 2,
        (('Non-aircon Room', 1350, 3, True), ('Bedspace (4 pax)', 800, 4, True)),
        "Ladies' dormitory twelve minutes from the campus, with a curfew at 9 PM and "
        'a resident house parent. Cooking is allowed in the common kitchen.',
    ),
    (
        "Mabini Men's Lodging", 'Casiaman', 'Mabini Extension, Casiaman',
        950, BoardingHouse.GenderAllowed.MALE, 2,
        (('Bedspace (4 pax)', 700, 4, True), ('Double Sharing', 950, 2, True)),
        'Plain, cheap lodging for male students, one jeepney ride from NLUC. Good '
        'for boardmates who mostly need a bed, a desk and a place to wash clothes.',
    ),
    (
        'Sunrise Boarding House', 'Arosip', 'Arosip proper',
        1100, BoardingHouse.GenderAllowed.BOTH, 0,
        (('Double Sharing', 1100, 2, True), ('Single Room', 1400, 1, True),
         ('Bedspace (4 pax)', 750, 4, True)),
        'East-facing rooms that catch the morning light, a tricycle ride from '
        'campus. Shared kitchen and laundry area, with water included.',
    ),
    (
        'J&J Room Rentals', 'Cabaroan', 'Cabaroan Road, Bacnotan',
        1250, BoardingHouse.GenderAllowed.BOTH, 1,
        (('Aircon Room', 1600, 2, True), ('Non-aircon Room', 1250, 2, True)),
        'Two well-kept rooms on Cabaroan Road, about fifteen minutes on foot from '
        'the NLUC gate. Electricity is metered separately; Wi-Fi is included.',
    ),
    (
        'Buenavista Bedspace', 'Arosip', 'Arosip, above the sari-sari store',
        850, BoardingHouse.GenderAllowed.BOTH, 2,
        (('Bedspace (4 pax)', 850, 4, True), ('Double Sharing', 1000, 2, True)),
        'The cheapest option in the list, one jeepney ride from campus. Bunk beds '
        'with individual lockers, shared comfort room and free drinking water.',
    ),
    (
        'Ilocandia Student Home', 'Sapilang', 'Sapilang, Bacnotan',
        1600, BoardingHouse.GenderAllowed.BOTH, 0,
        (('Aircon Room', 2000, 2, True), ('Studio Type', 1600, 2, True),
         ('Single Room', 1300, 1, True)),
        'A student home ten minutes from the NLUC gate, with a study area, CCTV on '
        'the corridors and a no-visitors-after-8-PM house rule.',
    ),
    (
        'Tres Marias Dormitory', 'Casiaman', 'Casiaman, near the elementary school',
        1400, BoardingHouse.GenderAllowed.FEMALE, 1,
        (('Non-aircon Room', 1400, 3, True), ('Single Room', 1700, 1, True)),
        'Three-room dormitory for female boarders, a tricycle ride from campus. '
        'Includes water, electricity and a shared kitchen; laundry is ₱150 a load.',
    ),
    (
        'Riverside Boarding House', 'Salincob', 'Salincob riverside',
        900, BoardingHouse.GenderAllowed.BOTH, 0,
        (('Non-aircon Room', 900, 2, False), ('Bedspace (4 pax)', 650, 4, False)),
        'Six beds on a quiet Salincob lane, a tricycle ride from NLUC. Currently full for '
        'this semester, so it is not taking new boarders.',
    ),
)

# Short, ordinary student comments. Written to sound like people, not like
# placeholders, because that is what a rating field looks like in use.
RATING_COMMENTS = (
    'Tahimik ang lugar, okay for review.',
    'Malinis ang CR at may tubig lagi.',
    'Mabait ang may-ari, mabilis sumagot sa chat.',
    'Medyo mainit sa hapon pero okay naman.',
    'Walking distance lang sa gate, safe maglakad.',
    'Malakas ang Wi-Fi, maganda para sa thesis.',
    'Maayos ang kwarto, kaso mahigpit sa curfew.',
    'Sulit sa presyo, babalik ako next sem.',
)


class Command(BaseCommand):
    help = 'Create demo landlords, houses, rooms, students, bookings and ratings.'

    def add_arguments(self, parser):
        parser.add_argument('--houses', type=int, default=len(HOUSES),
                            help=f'How many houses to seed (max {len(HOUSES)}).')
        parser.add_argument('--image', default=None,
                            help='Exterior photo to use for every seeded house.')
        parser.add_argument('--password', default=DEFAULT_PASSWORD,
                            help='Password for the demo landlord accounts.')
        parser.add_argument('--reset', action='store_true',
                            help='Delete everything this command created.')
        parser.add_argument('--force', action='store_true',
                            help='Regenerate the exterior photo files.')

    # ------------------------------------------------------------------ #

    def handle(self, *args, **options):
        if options['reset']:
            return self._reset()

        specs = HOUSES[:max(1, min(options['houses'], len(HOUSES)))]
        self._check_barangays()

        custom = Path(options['image']) if options['image'] else None
        if custom is not None and not custom.is_file():
            raise CommandError(f'No such image: {custom}')

        room_sources = sorted(Path(settings.BASE_DIR).glob(ROOM_SOURCE_GLOB))
        if not room_sources:
            self.stderr.write(self.style.WARNING(
                'No room photos found; the landing row will fall back to façades.'
            ))

        with transaction.atomic():
            landlords = self._landlords(options['password'])
            self._barangays()
            amenities = self._amenities()
            exteriors = self._exteriors(specs, custom, options['force'])
            room_files = self._convert_room_photos(room_sources, options['force'])
            houses = self._houses(landlords, specs, exteriors, amenities)
            self._room_photos(houses, room_files)
            students = self._students()
            self._bookings_and_ratings(landlords, houses, students)

        from core.views import invalidate_listing_caches
        invalidate_listing_caches()

        from core.views import featured_listings
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Seeded {BoardingHouse.objects.filter(name__in=[s[0] for s in specs]).count()} '
            f'boarding houses across {len(landlords)} landlords.'
        ))
        self.stdout.write('')
        self.stdout.write('Landing row order (most-rated landlord first):')
        for position, house in enumerate(featured_listings()[:12], start=1):
            ratings = house.owner.landlord_ratings_received.count()
            self.stdout.write(
                f'  {position:2d}. {house.name} - {house.owner.full_name} '
                f'({ratings} ratings, {house.barangay})'
            )
        self.stdout.write('')
        self.stdout.write('Sign-ins:')
        for username, full_name, _phone, _count in LANDLORDS:
            self.stdout.write(f'  landlord  {username} / {options["password"]}   ({full_name})')
        self.stdout.write(f'  students  demo_student01..{len(students):02d} / {STUDENT_PASSWORD}')

    # ------------------------------------------------------------------ #

    def _check_barangays(self):
        """Every seeded house must sit in a barangay the system already lists.

        A free-text barangay is how a listing ends up unfilterable and
        unsearchable: the filters match on this exact string.
        """
        listed = set(Barangay.objects.values_list('name', flat=True)) | {b[0] for b in BARANGAYS}
        unknown = sorted({spec[1] for spec in HOUSES} - listed)
        if unknown:
            raise CommandError(
                'These barangays are not in the Barangay table: '
                + ', '.join(unknown)
                + '\nAdd them (or fix the spelling) before seeding.'
            )

    def _reset(self):
        names = [h[0] for h in HOUSES]
        houses = BoardingHouse.objects.filter(name__in=names)
        rooms = Room.objects.filter(boarding_house__in=houses)
        RoomPhoto.objects.filter(room__in=rooms).delete()
        Booking.objects.filter(room__in=rooms).delete()
        LandlordRating.objects.filter(landlord__username__startswith='demo_landlord').delete()
        rooms.delete()
        for house in houses:
            if house.image:
                house.image.delete(save=False)
        removed = houses.count()
        houses.delete()

        usernames = [l[0] for l in LANDLORDS] + [f'demo_student{i:02d}' for i in range(1, 31)]
        User.objects.filter(username__in=usernames).delete()
        from core.views import invalidate_listing_caches
        invalidate_listing_caches()
        self.stdout.write(self.style.SUCCESS(
            f'Removed {removed} seeded houses, their rooms, bookings, ratings '
            f'and the {len(usernames)} demo accounts.'
        ))

    def _landlords(self, password: str) -> list[User]:
        rows = []
        for username, full_name, phone, _ratings in LANDLORDS:
            user = User.objects.filter(username=username).first()
            if user is None:
                user = User(
                    username=username,
                    email=f'{username}@example.com',
                    role=User.Role.LANDLORD,
                )
            user.full_name = full_name
            user.phone_number = phone
            user.bio = 'Demo account owning seeded boarding houses.'
            user.is_active = True
            user.set_password(password)
            user.save()
            rows.append(user)
        return rows

    def _barangays(self):
        for name, distance in BARANGAYS:
            barangay, created = Barangay.objects.get_or_create(
                name=name, defaults={'distance_from_campus': distance}
            )
            if not barangay.distance_from_campus:
                barangay.distance_from_campus = distance
                barangay.save(update_fields=['distance_from_campus'])

    def _amenities(self) -> list[Amenity]:
        rows = []
        for name in AMENITIES:
            amenity, _ = Amenity.objects.get_or_create(name=name)
            rows.append(amenity)
        return rows

    def _variance(self, source: Path, index: int, out_dir: Path, out_name: str):
        """Write one 4:3 crop of `source`. A fixed pseudo-grid, so re-running
        the command reproduces the same picture instead of churning files."""
        try:
            from PIL import Image
        except ImportError:  # pragma: no cover - Pillow is in requirements
            return
        with Image.open(source) as img:
            img = img.convert('RGB')
            width, height = img.size
            box_w = int(width * 0.46)
            box_h = int(box_w * 0.75)
            if box_h > height:
                box_h = height
                box_w = int(box_h / 0.75)
            left = int((index * 37 % 100) / 100 * max(0, width - box_w))
            top = int((index * 53 % 100) / 100 * max(0, height - box_h))
            crop = img.crop((left, top, left + box_w, top + box_h)).resize((1200, 900), Image.LANCZOS)
            out_dir.mkdir(parents=True, exist_ok=True)
            crop.save(out_dir / out_name, 'JPEG', quality=80, optimize=True)

    def _exteriors(self, specs, custom, force) -> dict[str, str]:
        sources = [Path(settings.BASE_DIR) / p for p in IMAGE_SOURCES]
        out_dir = Path(settings.MEDIA_ROOT) / 'boarding_images'
        photos = {}
        for index, spec in enumerate(specs):
            name = f'seed-house-{index + 1:02d}.jpg'
            target = out_dir / name
            if custom is not None:
                if force or not target.exists():
                    self._variance(custom, 0, out_dir, name)
            elif all(p.is_file() for p in sources):
                if force or not target.exists():
                    self._variance(sources[index % len(sources)], index, out_dir, name)
            if target.exists():
                photos[spec[0]] = f'boarding_images/{name}'
        return photos

    def _convert_room_photos(self, sources, force) -> list[str]:
        """Normalise the supplied room photos to web-sized JPEGs.

        They arrive as screenshots in mixed sizes and orientations (one is
        194px wide, another is landscape). Storing them as-is means a multi-
        megabyte PNG per card and a row of wildly uneven images; the crop to a
        card-shaped frame happens in CSS, so the file only has to be sane.
        """
        out_dir = Path(settings.MEDIA_ROOT) / 'room_photos'
        names = []
        for index, source in enumerate(sources, start=1):
            out_name = f'room-{index:02d}.jpg'
            target = out_dir / out_name
            if force or not target.exists():
                try:
                    from PIL import Image
                except ImportError:  # pragma: no cover
                    break
                with Image.open(source) as img:
                    img = img.convert('RGB')
                    if img.width > 1100:
                        height = round(img.height * 1100 / img.width)
                        img = img.resize((1100, height), Image.LANCZOS)
                    out_dir.mkdir(parents=True, exist_ok=True)
                    img.save(target, 'JPEG', quality=82, optimize=True)
            if target.exists():
                names.append(f'room_photos/{out_name}')
        return names

    def _houses(self, landlords, specs, exteriors, amenities):
        rows = []
        for spec in specs:
            (name, barangay, address, price, gender, owner_index, rooms, description) = spec
            landlord = landlords[owner_index]
            house = BoardingHouse.objects.filter(name=name).first()
            if house is None:
                house = BoardingHouse(name=name, owner=landlord)
            house.owner = landlord
            house.address = address
            house.barangay = barangay
            house.price = price
            house.gender_allowed = gender
            house.description = description
            house.is_active = True
            house.status = BoardingHouse.Status.APPROVED
            if exteriors.get(name) and not house.image:
                house.image = exteriors[name]
            house.save()
            rows.append(house)

            for order, (room_type, rate, capacity, available) in enumerate(rooms):
                room = Room.objects.filter(
                    boarding_house=house, room_type=room_type
                ).first()
                if room is None:
                    room = Room(boarding_house=house, room_type=room_type)
                room.monthly_rate = rate
                room.capacity = capacity
                room.is_available = available
                room.is_active = True
                room.save()
                picks = [amenities[0], amenities[1]] + [
                    amenities[(order * 3 + 4 + i) % len(amenities)] for i in range(3)
                ]
                room.amenities.set({a for a in picks})
        return rows

    def _room_photos(self, houses, room_files):
        """Seat the supplied room photos on the seeded rooms.

        Houses are walked in the order the landing row will show them, so the
        ten cards on that row get ten different rooms. (Walking them in
        creation order instead gave the same bunk bed to three cards, because
        the row is ranked by landlord, not by house id.)

        Each room takes two photos from the pool so a room gallery is not the
        same picture twice. Only photos from the pool are replaced on a re-run;
        anything a landlord uploaded by hand is left alone.
        """
        if not room_files:
            return
        from core.views import featured_listings
        row_order = {house.id: position for position, house in enumerate(featured_listings())}
        ordered = sorted(houses, key=lambda h: (row_order.get(h.id, len(row_order)), h.id))
        pool = len(room_files)
        pool_names = set(room_files)

        for house_position, house in enumerate(ordered):
            for room_index, room in enumerate(house.rooms.order_by('id')):
                offset = house_position + room_index * 3
                wanted = [room_files[(offset + step) % pool] for step in (0, 5)]
                for photo in room.photos.all():
                    if str(photo.image) in pool_names:
                        photo.delete()
                for photo_name in wanted:
                    RoomPhoto.objects.create(room=room, image=photo_name)

    def _students(self) -> list[User]:
        """One student per rating, because a rating is one-per-student."""
        needed = sum(count for _u, _n, _p, count in LANDLORDS)
        students = []
        for index in range(1, needed + 1):
            username = f'demo_student{index:02d}'
            user = User.objects.filter(username=username).first()
            if user is None:
                user = User(
                    username=username,
                    email=f'{username}@example.com',
                    role=User.Role.STUDENT,
                )
            user.full_name = f'Demo Student {index:02d}'
            user.is_active = True
            user.set_password(STUDENT_PASSWORD)
            user.save()
            students.append(user)
        return students

    def _bookings_and_ratings(self, landlords, houses, students):
        """Give each landlord the ratings its spec asks for, through a real
        confirmed booking — the only way the app itself can produce a rating."""
        by_owner = {landlord.id: [] for landlord in landlords}
        for house in houses:
            by_owner.setdefault(house.owner_id, []).append(house)

        cursor = 0
        for landlord, (_u, _n, _p, wanted) in zip(landlords, LANDLORDS):
            owned = by_owner.get(landlord.id, [])
            rooms = [room for house in owned for room in house.rooms.order_by('id')]
            if not rooms:
                continue
            for index in range(wanted):
                student = students[cursor]
                cursor += 1
                room = rooms[index % len(rooms)]
                booking = Booking.objects.filter(student=student, room=room).first()
                if booking is None:
                    booking = Booking(student=student, room=room)
                booking.status = Booking.Status.CONFIRMED
                booking.confirmed_at = timezone.now()
                booking.move_in_date = date.today()
                booking.save()

                rating = LandlordRating.objects.filter(student=student, landlord=landlord).first()
                if rating is None:
                    rating = LandlordRating(student=student, landlord=landlord, booking=booking)
                rating.booking = booking
                # Mostly good, with the occasional honest 3, so an average is
                # an average and not a wall of fives.
                rating.rating = 5 if index % 4 else 3 + (index % 2)
                rating.comment = RATING_COMMENTS[index % len(RATING_COMMENTS)]
                rating.save()
