"""Remove the rows the exploration harness created in the demo database.

`explore_flows.py` writes real records -- that is the point of it -- so a run
leaves boarding houses, inquiries, messages and bookings behind. This deletes
exactly what the harness creates and nothing else, so the demo data is back to
what it was before the audit.

Safe to re-run: every predicate matches on the harness's own marker strings.

    ./venv/Scripts/python.exe tools/explore_cleanup.py --dry-run
    ./venv/Scripts/python.exe tools/explore_cleanup.py
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")

import django  # noqa: E402

django.setup()

from core.models import (  # noqa: E402
    BoardingHouse,
    Booking,
    Inquiry,
    InquiryMessage,
    LandlordRating,
    Room,
    UserReport,
)

HOUSE_MARKER = "Review Test House"
MESSAGE_MARKER = "Automated review message"
REPLY_MARKER = "Landlord reply "
REPORT_MARKER = "Automated review report"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    houses = BoardingHouse.objects.filter(name__startswith=HOUSE_MARKER)
    rooms = Room.objects.filter(boarding_house__in=houses)
    photos = sum(r.photos.count() for r in rooms)

    inquiries = Inquiry.objects.filter(message_text__startswith=MESSAGE_MARKER)
    threads = Inquiry.objects.filter(
        pk__in=inquiries.values_list("pk", flat=True)
    ) | Inquiry.objects.filter(
        messages__message_text__startswith=REPLY_MARKER
    )
    messages = InquiryMessage.objects.filter(
        message_text__startswith=REPLY_MARKER
    ) | InquiryMessage.objects.filter(inquiry__in=inquiries)

    # The accept step books the room the inquiry was about. Matching on the room
    # ALONE would delete the seeded demo bookings that happen to sit on the
    # same rooms -- the seed data books every student into a real room, and the
    # harness asks about those same rooms. Scope by time as well: the earliest
    # harness inquiry is the moment the audit began, and nothing the seeder
    # wrote can be newer than that.
    if inquiries.exists():
        cutoff = inquiries.earliest("created_at").created_at
        touched_rooms = Room.objects.filter(
            pk__in=inquiries.values_list("room_id", flat=True)
        )
        bookings = Booking.objects.filter(room__in=touched_rooms,
                                          requested_at__gte=cutoff)
    else:
        cutoff = None
        bookings = Booking.objects.none()
    ratings = LandlordRating.objects.filter(booking__in=bookings)
    reports = UserReport.objects.filter(details__startswith=REPORT_MARKER)

    plan = [
        ("boarding houses", houses.count()),
        ("rooms", rooms.count()),
        ("room photos", photos),
        ("inquiries", threads.distinct().count()),
        ("inquiry messages", messages.distinct().count()),
        ("bookings", bookings.count()),
        ("ratings", ratings.count()),
        ("user reports", reports.count()),
    ]
    print(f"harness window starts {cutoff}")
    print("would remove:" if args.dry_run else "removing:")
    for label, n in plan:
        print(f"  {label:20s} {n}")

    if args.dry_run:
        return 0

    ratings.delete()
    bookings.delete()
    messages.distinct().delete()
    threads.distinct().delete()
    for room in rooms:
        for photo in room.photos.all():
            if photo.image:
                photo.image.delete(save=False)
    rooms.delete()
    houses.delete()
    reports.delete()
    print("\ndone. Remaining demo totals:")
    print(f"  boarding houses {BoardingHouse.objects.count()}"
          f" | rooms {Room.objects.count()}"
          f" | inquiries {Inquiry.objects.count()}"
          f" | bookings {Booking.objects.count()}"
          f" | reports {UserReport.objects.count()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())