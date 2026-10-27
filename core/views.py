import json
import time
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.db import DatabaseError, transaction
from django.db.models import Avg, Count, Exists, F, IntegerField, Min, OuterRef, Prefetch, Q, Subquery
from django.db.models.functions import Coalesce, Lower
from django.shortcuts import get_object_or_404, redirect, render
from django.http import Http404
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import (
    BoardingHouseForm,
    StudentRegistrationForm,
    StudentProfileEditForm,
    LandlordCreateForm,
    LandlordEditForm,
    InquiryForm,
    ListingFilterForm,
    RoomForm,
    BarangayForm,
    SystemSettingsForm,
)
from .forms import (
    StudentProfileUpdateForm,
    LandlordProfilePictureForm,
    LandlordProfileUpdateForm,
    BHIMSPasswordChangeForm,
    UserReportForm,
    LandlordRatingForm,
)
from .models import (
    BoardingHouse,
    User,
    Room,
    Inquiry,
    InquiryMessage,
    Amenity,
    Booking,
    Barangay,
    RoomPhoto,
    SiteSetting,
    UserReport,
    LandlordRating,
    site_setting,
    student_access_enabled,
    annotate_room_bookings,
    BACNOTAN_BARANGAYS,
    BARANGAY_DISTANCES,
    LANDING_CACHE_KEY,
    LISTING_CACHE_KEY,
    MAX_MESSAGE_CHARS,
)


LISTINGS_PER_PAGE = 12


def rooms_with_space():
    """Rooms a student could actually book right now.

    Switched on, not marked unavailable, and not yet at capacity. Capacity is
    compared against CONFIRMED bookings only — the same definition the room
    page and the admin dashboard already use — so "full" means one thing in
    this system instead of three.
    """
    return (
        Room.objects
        .filter(is_active=True, is_available=True)
        .annotate(
            taken=Count('bookings', filter=Q(bookings__status=Booking.Status.CONFIRMED)),
        )
        .filter(taken__lt=F('capacity'))
    )


def visible_listings():
    """Boarding houses students are allowed to see.

    Approved and active, and with something left to rent. A listing whose rooms
    are all taken, or all switched off, is hidden from every visitor exactly as
    if it had been taken down — a listed-but-unbookable house is the worst of
    both worlds, because a student can find it and then discover there is
    nothing to book.

    The rooms decide, not the listing: freeing a bed, raising a room's
    capacity, or switching a room back on brings the house back on its own,
    with no second place to remember to update.
    """
    return BoardingHouse.objects.filter(
        Exists(rooms_with_space().filter(boarding_house=OuterRef('pk'))),
        status=BoardingHouse.Status.APPROVED,
        is_active=True,
    )


def barangay_filter_choices():
    """The barangay options the student-facing filters may offer, as
    (value, label) pairs.

    Admin -> Edit Barangays is the single source of truth. The browse and
    search views used to build the list from each house's own `barangay`
    string as well, so a listing left over from before a barangay was removed
    quietly added an option the admin never created. Only the barangays the
    admin maintains belong in the list; if the table has not been populated
    yet, fall back to the built-in six so a fresh install still has a usable
    filter.

    The table must still name every barangay a live listing sits in — that is
    the data migration's job (0026), not the filter's: a house whose barangay
    has no row can be seen on the board but never selected from the filter.
    """
    try:
        rows = list(Barangay.objects.values_list('name', 'distance_from_campus'))
    except DatabaseError:
        rows = []
    if not rows:
        rows = [(name, BARANGAY_DISTANCES.get(name, '')) for name in BACNOTAN_BARANGAYS]
    return [
        (name, f'{name} ({distance})' if distance else name)
        for name, distance in rows
    ]


def barangay_active_listing_counts():
    """How many listings students can actually see, per barangay.

    Keyed by the case-folded name, because a listing stores its barangay as
    plain text: the row for Auring's Transient Home says "Poblacion" while the
    admin may have typed "poblacion". The admin table compared the two exactly
    and reported 0 active listings for a barangay the student filter could
    fill with that house. A house with no bookable room is not counted either
    — the student pages hide it, so counting it here would disagree with them
    in the other direction.
    """
    rows = (
        visible_listings()
        .values(key=Lower('barangay'))
        .annotate(count=Count('id'))
    )
    return {row['key']: row['count'] for row in rows}


def barangay_rows_with_counts():
    """(Barangay, student-visible listing count) for the admin table."""
    counts = barangay_active_listing_counts()
    return [
        (barangay, counts.get((barangay.name or '').strip().lower(), 0))
        for barangay in Barangay.objects.all()
    ]


def invalidate_listing_caches():
    """Drop the cached copies of the two public listing pages.

    Those pages are cached for a few seconds to survive traffic spikes; any
    write that changes what students may see has to clear them, otherwise a
    freshly approved listing stays invisible for up to a minute.
    """
    try:
        from django.core.cache import cache
        cache.delete(LANDING_CACHE_KEY)
        cache.delete(LISTING_CACHE_KEY)
    except Exception:
        # A cache problem must never fail the write that triggered it.
        pass


# ---------------------------------------------------------------------------
# Listing filters
#
# Every filter is written as an EXISTS subquery against rooms instead of a
# JOIN. A JOIN multiplies a boarding house by its matching rooms: one house
# with three rooms matching a filter rendered as three identical cards, and
# 'lowest price' ordering produced one row per room at that price. EXISTS
# answers "does this house have such a room?" and can never duplicate a row.
# ---------------------------------------------------------------------------
def _amenity_ids_from_names(names):
    """Resolve amenity names — or numeric ids from an old link — to Amenity ids.

    Names match case-insensitively, so the browse page's free-text box and the
    search page's checkbox list (which each used to speak a different language
    than the view, or than each other) now mean the same thing.
    """
    wanted = [str(n).strip() for n in names if str(n).strip()]
    if not wanted:
        return []
    try:
        match = Q(name__iexact=wanted[0])
        for name in wanted[1:]:
            match |= Q(name__iexact=name)
        numeric = [int(n) for n in wanted if n.isdigit()]
        if numeric:
            match |= Q(id__in=numeric)
        return list(Amenity.objects.filter(match).values_list('id', flat=True))
    except DatabaseError:
        return []


def _amenity_ids_from(cleaned):
    names = [s.strip() for s in (cleaned.get('amenities') or '').split(',') if s.strip()]
    return _amenity_ids_from_names(names)


def _matching_room_filter(cleaned, amenity_ids):
    """Q() describing the rooms the student's filter is talking about.

    Only rooms the student could actually book are considered, so the price
    and the open-room count on the card always describe the same rooms the
    filter matched.
    """
    q = Q(is_active=True, is_available=True)
    if cleaned.get('price_min'):
        q &= Q(monthly_rate__gte=cleaned['price_min'])
    if cleaned.get('price_max'):
        q &= Q(monthly_rate__lte=cleaned['price_max'])
    if cleaned.get('room_type'):
        q &= Q(room_type__icontains=cleaned['room_type'])
    if amenity_ids:
        q &= Q(amenities__in=amenity_ids)
    return q


def _apply_listing_filters(houses, cleaned, amenity_ids):
    """Filter and order houses without ever duplicating one.

    Returns (queryset, room_filter, matched_rooms) so the caller can decorate
    cards from exactly the rooms the filter matched.
    """
    room_filter = _matching_room_filter(cleaned, amenity_ids)
    room_level_filter_applied = bool(
        amenity_ids
        or cleaned.get('price_min')
        or cleaned.get('price_max')
        or cleaned.get('room_type')
    )
    if room_level_filter_applied:
        houses = houses.filter(
            Exists(
                Room.objects.filter(
                    boarding_house=OuterRef('pk'),
                ).filter(room_filter)
            )
        )
    if cleaned.get('barangay'):
        # Case-insensitive: the admin's spelling and the listing's spelling are
        # allowed to differ ("poblacion" vs "Poblacion"), and both fixed
        # filter sources must return the same houses.
        houses = houses.filter(barangay__iexact=cleaned['barangay'].strip())

    if cleaned.get('q'):
        term = cleaned['q']
        # The room-type clause is a subquery rather than a join, so a house that
        # matches through three of its rooms is still produced exactly once.
        houses = houses.filter(
            Q(name__icontains=term)
            | Q(address__icontains=term)
            | Q(barangay__icontains=term)
            | Q(description__icontains=term)
            | Q(pk__in=Room.objects.filter(room_type__icontains=term).values('boarding_house'))
        )

    if cleaned.get('min_rooms'):
        # Counts rooms a student could book right now, using the same
        # bookable-room definition as the cards and the browse page.
        #
        # The grouping is done on a plain Room queryset on purpose: reusing
        # rooms_with_space() here would group by its per-room `taken`
        # annotation as well, so a house whose rooms were in different states
        # (one booked out, one free) produced TWO rows and MariaDB answered
        # /search/?min_rooms=2 with "Subquery returns more than 1 row".
        open_room_ids = rooms_with_space().values('pk')
        open_rooms = (
            Room.objects
            .filter(boarding_house=OuterRef('pk'), pk__in=open_room_ids)
            .values('boarding_house')
            .annotate(total=Count('*'))
            .values('total')
        )
        houses = houses.annotate(
            open_room_total=Coalesce(
                Subquery(open_rooms, output_field=IntegerField()), 0,
            ),
        ).filter(open_room_total__gte=cleaned['min_rooms'])

    if cleaned.get('sort') == 'lowest_price':
        # A correlated subquery (not a join + aggregate) keeps one row per
        # house, so the ordering itself cannot fan a house into several cards.
        lowest = (
            Room.objects.filter(boarding_house=OuterRef('pk'))
            .filter(room_filter)
            .order_by('monthly_rate')
            .values('monthly_rate')[:1]
        )
        houses = houses.annotate(
            lowest_matching=Subquery(lowest),
        ).order_by(F('lowest_matching').asc(nulls_last=True), '-id')
    else:
        houses = houses.order_by('-id')
    return houses, room_filter


def decorate_house_cards(houses, room_filter=None, room_photos_first=False):
    """Attach min_price / available_rooms_count used by listing card templates.

    Both numbers are derived from ONE prefetched room set, scoped to the same
    rooms the student's filter matched. Before this, min_price was an
    aggregate over every room in the house (including rooms the landlord had
    switched off, so a card could advertise a price nobody could book) and
    available_rooms_count came from an unfiltered prefetch (so the badge
    ignored the filter outright).

    `room_photos_first` puts the room itself on the card instead of the
    façade. That is what the landing row shows: a student scanning listings
    wants to see the bed and the floor, which is the thing being rented. It
    costs one extra query for the whole page — not one per card — and the
    façade remains the fallback wherever a room has no photo yet.
    """
    room_photo_by_house = {}
    if room_photos_first:
        for photo in (RoomPhoto.objects
                      .filter(room__boarding_house__in=houses)
                      .select_related('room')
                      .order_by('room_id', 'id')):
            house_id = photo.room.boarding_house_id
            if house_id in room_photo_by_house:
                continue
            if photo.image and photo.image.storage.exists(photo.image.name):
                room_photo_by_house[house_id] = photo.image.url

    rooms = annotate_room_bookings(
        Room.objects.filter(is_active=True, is_available=True)
    )
    if room_filter is not None:
        rooms = rooms.filter(room_filter).distinct()
    # Amenities ride along with the prefetched rooms: the card prints the first
    # bookable room's amenities, and without this the template ran one query per
    # house, so browse cost grew with the catalogue (the N+1 the query-budget
    # test measures). One extra query per page, flat in the number of houses.
    rooms = rooms.prefetch_related('amenities')

    houses = list(
        houses.prefetch_related(
            Prefetch('rooms', queryset=rooms, to_attr='bookable_rooms')
        )
    )

    # The landlord's rating, so a student can weigh who they are renting from
    # before opening the listing. One grouped query for the whole page, keyed by
    # owner id (not one per card), and the same numbers the landlord's profile
    # shows: the average out of five, the count, and that average as a percent.
    owners = {house.owner_id for house in houses}
    ratings_by_owner = {}
    if owners:
        for row in (
            LandlordRating.objects.filter(landlord_id__in=owners)
            .values('landlord_id')
            .annotate(avg=Avg('rating'), n=Count('id'))
        ):
            ratings_by_owner[row['landlord_id']] = (row['avg'], row['n'])

    for house in houses:
        avg, rating_count = ratings_by_owner.get(house.owner_id, (None, 0))
        house.landlord_rating_avg = avg
        house.landlord_rating_count = rating_count
        house.landlord_rating_percent = round(avg / 5 * 100) if avg is not None else None
        if room_photos_first:
            house.card_photo_url = (
                room_photo_by_house.get(house.id)
                or (house.image.url if house.image_ok else '')
            )
        bookable = getattr(house, 'bookable_rooms', [])
        open_rooms = [r for r in bookable if r.capacity > r.confirmed_bookings]
        prices = [r.monthly_rate for r in open_rooms] or [r.monthly_rate for r in bookable]
        house.available_rooms_count = len(open_rooms)
        house.min_price = min(prices) if prices else None
        # Room type shown on the card. Deriving it here (instead of letting the
        # template do house.rooms.all|first) removes one query per card AND
        # means the card describes the rooms the filter actually matched.
        label_rooms = open_rooms or bookable
        house.card_room_type = label_rooms[0].room_type if label_rooms else ''
    return houses


def admin_required(user):
    return user.is_authenticated and user.role == User.Role.ADMIN


def landlord_required(user):
    return user.is_authenticated and user.role == User.Role.LANDLORD


def student_required(user):
    return user.is_authenticated and user.role == User.Role.STUDENT


def _safe_redirect_target(raw):
    """Allow only same-origin relative paths (blocks open redirects via ?next=)."""
    if raw and url_has_allowed_host_and_scheme(raw, allowed_hosts=None):
        return raw
    return ''


# Brute-force lockout thresholds: 15 consecutive failures inside a 15 minute
# window lock that (IP, account) pair for 30 minutes.
LOGIN_FAIL_LIMIT = 15
LOGIN_WINDOW = 900
LOGIN_LOCK = 1800


def _client_ip(request):
    """Best-effort client IP for throttling. With no reverse proxy in front
    (this project's setup), REMOTE_ADDR is the real client."""
    return request.META.get('REMOTE_ADDR', 'unknown') or 'unknown'


def _cache_get(key):
    """Read from the cache, but never let a cache problem break a page.

    The cache is an optimisation. A backend that raises (a full disk, a
    file-lock conflict on Windows, a dead Redis node) must degrade to
    "cache miss" and let the page render normally - not turn a busy page into
    an HTTP 500 for everyone at once.
    """
    from django.core.cache import cache
    try:
        return cache.get(key)
    except Exception:
        return None


def _cache_set(key, value, timeout):
    """Write to the cache, ignoring backend failures (see _cache_get)."""
    from django.core.cache import cache
    try:
        cache.set(key, value, timeout)
    except Exception:
        pass


def _hit(key, timeout):
    """Increase a counter and return the new value, atomically.

    The old read-modify-write (get -> +1 -> set) loses updates when several
    requests hit the same key at once: two threads both read 9, both write 10,
    and one of the attempts is never counted. That silently weakens every
    limit built on it. `add` + `incr` is done under the cache backend's own
    lock, so no attempt is lost.
    """
    from django.core.cache import cache
    try:
        cache.add(key, 0, timeout)   # no-op when the key already exists
        try:
            return cache.incr(key)
        except ValueError:
            # Key expired between add() and incr().
            cache.set(key, 1, timeout)
            return 1
    except Exception:
        # Cache unavailable: fail open (the request proceeds) rather than
        # fail closed (nobody can log in).
        return 0


def _throttle_login(request):
    """Sliding-window rate limit for login POSTs: max 10 attempts per IP per
    minute (and 40 per hour). Blocks brute-force waves and absorbs traffic
    spikes on the login page without slowing legitimate users.
    Returns True when the request should be REJECTED."""
    ip = _client_ip(request)
    now = int(time.time())
    minute_hits = _hit(f'login-throttle-m:{ip}:{now // 60}', 65)
    hour_hits = _hit(f'login-throttle-h:{ip}:{now // 3600}', 3610)
    return minute_hits > 10 or hour_hits > 40


def _throttle_key(request):
    """Who owns this request's write budget?

    Signed-in users get their own budget. Keying on the IP alone meant every
    student behind the campus NAT/proxy shared one allowance, so a normal
    classroom could start answering 429 to innocent people while a single
    scripted abuser on a second IP got a fresh allowance.
    """
    user = getattr(request, 'user', None)
    if user is not None and getattr(user, 'is_authenticated', False):
        return f'u:{user.pk}'
    return f'ip:{_client_ip(request)}'


def _throttle_generic(request, scope='post', per_minute=120):
    """Cap on write requests (any POST) and JSON endpoints, per caller.
    Generous enough that no real user can hit it while filling forms; tight
    enough that scripted floods get shed before they reach the database.
    Returns True to REJECT."""
    now = int(time.time())
    key = f'g-throttle:{scope}:{_throttle_key(request)}:{now // 60}'
    hits = _hit(key, 65)
    return hits > per_minute


def _with_latest_message(inquiries):
    """Annotate each inquiry with its newest message time.

    The unread ('NEW') badge used to pull one query per inquiry; this is a
    single correlated subquery for the whole list.
    """
    from .models import InquiryMessage
    latest = (
        InquiryMessage.objects.filter(inquiry=OuterRef('pk'))
        .order_by('-sent_at')
        .values('sent_at')[:1]
    )
    return inquiries.annotate(latest_message_at=Subquery(latest))


def _inquiry_has_new_message(inquiry, viewed_field='last_viewed_by_landlord'):
    """True when the viewer has activity they have not opened yet.

    The newest reply counts; a thread with no replies yet falls back to the
    inquiry's own created_at, because the opening message is still a message
    the other side has not read.
    """
    latest_at = getattr(inquiry, 'latest_message_at', None) or inquiry.created_at
    viewed = getattr(inquiry, viewed_field, None)
    return viewed is None or latest_at > viewed


def _lockout_state(request):
    """Account lockout bookkeeping (instructor item: brute-force hardening).
    Tracks failed logins per (IP, username); 15 consecutive failures in 15
    minutes lock that combination for 30 minutes. Returns
    (is_locked, fail_count, locked_until_or_None)."""
    ip = _client_ip(request)
    username = (request.POST.get('username') or '').strip().lower()
    if not username:
        return False, 0, None
    base = f'login-fails:{ip}:{username}'
    fails = _cache_get(base) or 0
    first = _cache_get(f'{base}:first')
    locked = fails >= LOGIN_FAIL_LIMIT
    locked_until = (first + LOGIN_WINDOW + LOGIN_LOCK) if (locked and first) else None
    return locked, fails, locked_until


def _record_login_failure(request):
    """Count one failed sign-in attempt for this (IP, account).

    The counter is incremented atomically and the window start is written once
    with cache.add, so a burst of parallel attempts is counted exactly.
    """
    from django.core.cache import cache
    ip = _client_ip(request)
    username = (request.POST.get('username') or '').strip().lower()
    if not username:
        return
    base = f'login-fails:{ip}:{username}'
    ttl = LOGIN_WINDOW + LOGIN_LOCK
    try:
        cache.add(f'{base}:first', int(time.time()), ttl)
    except Exception:
        pass
    _hit(base, ttl)


def _clear_login_failures(request):
    from django.core.cache import cache
    ip = _client_ip(request)
    username = (request.POST.get('username') or '').strip().lower()
    if not username:
        return
    base = f'login-fails:{ip}:{username}'
    try:
        cache.delete_many([base, f'{base}:first'])
    except Exception:
        pass


def handler404(request, exception=None):
    return render(request, 'core/404.html', status=404)


def handler500(request):
    return render(request, 'core/500.html', status=500)


# How many cards the landing page's sliding row holds. The row is a
# shop window, not the catalogue — /listings/ is where the whole inventory
# lives — so this is a fixed, chosen number rather than "all of them".
LANDING_FEATURED_LIMIT = 10

# How many landlords the window is drawn from, ranked by how many ratings
# they have received.
LANDING_FEATURED_LANDLORDS = 10


def featured_listings():
    """Visible houses of the most-rated landlords, most-rated landlord first.

    The row is a social-proof slot, so it is ordered by the community's
    ratings rather than by who signed up last: the landlord with the most
    ratings leads, and the row is filled from the next landlords down.

    Ties — and a fresh install where nobody has been rated yet — fall back to
    average score and then to the newest house, so the row degrades to
    "newest first" instead of going empty.
    """
    from django.db.models import Avg, Count, F, IntegerField, Value, When, Case

    ranked = list(
        User.objects
        .filter(role=User.Role.LANDLORD)
        .annotate(
            rating_count=Count('landlord_ratings_received', distinct=True),
            rating_avg=Avg('landlord_ratings_received__rating'),
        )
        # nulls_last keeps landlords nobody has rated yet at the bottom on
        # every database (NULLs sort first in a DESC order on Postgres).
        .order_by(
            F('rating_count').desc(),
            F('rating_avg').desc(nulls_last=True),
            F('id').desc(),
        )[:LANDING_FEATURED_LANDLORDS]
    )
    if not ranked:
        return visible_listings().none()

    # One CASE rank, so the database does the ordering: the most-rated
    # landlord's houses come first, and within a landlord the newest house.
    rank = Case(
        *[When(owner_id=user.id, then=Value(position))
          for position, user in enumerate(ranked)],
        default=Value(len(ranked)),
        output_field=IntegerField(),
    )
    return visible_listings().filter(owner_id__in=[u.id for u in ranked]).order_by(rank, '-id')


# Public views
def home(request):
    # Logged-in users must never see the landing/marketing page; send them
    # straight to their role dashboard. Only logged-out visitors get the landing.
    if request.user.is_authenticated:
        role = getattr(request.user, 'role', None)
        if role == User.Role.STUDENT:
            return redirect('student_dashboard')
        if role == User.Role.LANDLORD:
            return redirect('landlord_dashboard')
        if role == User.Role.ADMIN:
            return redirect('admin_dashboard')
        return redirect('listing_list')

    # The landing page is identical for every anonymous visitor — cache the
    # rendered HTML for 60s so hundreds of simultaneous visitors share one
    # render instead of each hitting the DB for the newest listings.
    html = _cache_get(LANDING_CACHE_KEY)
    if html is None:
        listings = []
        try:
            listings = decorate_house_cards(
                featured_listings(), room_photos_first=True
            )[:LANDING_FEATURED_LIMIT]
        except DatabaseError:
            # DB tables might not exist yet (migrations not applied).
            listings = []
        html = render(request, 'core/landing.html', {'listings': listings}).content.decode('utf-8')
        _cache_set(LANDING_CACHE_KEY, html, 60)
    from django.http import HttpResponse
    return HttpResponse(html)


def listing_list(request):
    # Stampede shield: the DEFAULT browse page (no filters, logged-out) is
    # identical for every visitor and is the single hottest page during a
    # campus-wide surge. Cache its HTML for 30s so 500 simultaneous visitors
    # share one query+render instead of 500. Any filter/search, or a
    # logged-in user, bypasses the cache and computes fresh results.
    if not request.user.is_authenticated and not any(
        v for k, v in request.GET.items()
    ):
        cached = _cache_get(LISTING_CACHE_KEY)
        if cached is not None:
            from django.http import HttpResponse
            return HttpResponse(cached)

    try:
        houses = visible_listings().order_by('-id')
        # Force a simple DB access now so we can catch missing tables before template rendering.
        houses.exists()
    except DatabaseError:
        # DB tables might not exist yet (migrations not applied). Return empty queryset and skip DB lookups.
        houses = BoardingHouse.objects.none()
    
    form = ListingFilterForm(request.GET)
    # Exactly the barangays an admin maintains: a house's free-text barangay
    # must never add a choice of its own to the student's filter.
    form.fields['barangay'].choices = [('', 'Any')] + barangay_filter_choices()
    # Style filter widgets with Bootstrap field classes
    form.fields['barangay'].widget.attrs['class'] = 'form-select'
    form.fields['sort'].widget.attrs['class'] = 'form-select'
    form.fields['price_min'].widget.attrs['class'] = 'form-control'
    form.fields['price_max'].widget.attrs['class'] = 'form-control'
    form.fields['amenities'].widget.attrs['class'] = 'form-control'

    room_filter = None
    if form.is_valid():
        cleaned = form.cleaned_data
        amenity_ids = _amenity_ids_from(cleaned)
        # A filter naming amenities nobody has must match nothing, not everything.
        if cleaned.get('amenities') and not amenity_ids:
            houses = houses.none()
        else:
            houses, room_filter = _apply_listing_filters(houses, cleaned, amenity_ids)

    # One page at a time. The browse page is the hottest public route; without
    # a page size it rendered (and counted) every house in the database on
    # every single request, which is what collapses a worker under a surge.
    paginator = Paginator(houses, LISTINGS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page'))
    page_houses = decorate_house_cards(page_obj.object_list, room_filter=room_filter)
    query_params = request.GET.copy()
    query_params.pop('page', None)
    query_string = '&' + query_params.urlencode() if query_params else ''

    context = {
        'houses': page_houses,
        'boarding_houses': page_houses,
        'page_obj': page_obj,
        'query_string': query_string,
        'form': form,
    }

    # AJAX instant-filter: return only the grid fragment when requested via fetch.
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'core/includes/listing_grid_fragment.html', context)

    # Keep full houses visible; the card template renders a "Full" badge.
    # Logged-in users get the sidebar app shell; visitors get the public navbar.
    template = 'core/boardings_list_app.html' if request.user.is_authenticated else 'core/boardings_list.html'
    response = render(request, template, context)
    if not request.user.is_authenticated and not any(request.GET.values()):
        _cache_set(LISTING_CACHE_KEY, response.content.decode('utf-8'), 30)
    return response


def boarding_detail(request, pk):
    house = get_object_or_404(BoardingHouse, pk=pk)

    # Public means approved, active AND with a room to rent. A listed house
    # whose rooms are all taken (or all switched off) is not shown to anyone,
    # so a shared link to it stops working instead of advertising a bed nobody
    # can book. The landlord who owns it, and any student who already holds a
    # confirmed booking, stay allowed — so managing it and the "View Property"
    # button in My Bookings both keep working.
    is_public = visible_listings().filter(pk=house.pk).exists()
    if not is_public:
        allowed = False
        if request.user.is_authenticated:
            if request.user == house.owner:
                allowed = True
            elif request.user.role == User.Role.STUDENT and Booking.objects.filter(
                student=request.user,
                room__boarding_house=house,
                status=Booking.Status.CONFIRMED,
            ).exists():
                allowed = True
        if not allowed:
            messages.info(request, 'This boarding house is not currently available to students.')
            return redirect('listing_list')

    # One COUNT for the whole page instead of one per room (this list used to
    # run 54 queries for a 12-room house).
    rooms = [
        room for room in annotate_room_bookings(
            house.rooms.filter(is_active=True, is_available=True)
            .prefetch_related('photos', 'amenities')
            .order_by('monthly_rate', 'id')
        ) if room.has_space()
    ]
    # Landlord reputation, so the student can weigh who they are renting from
    # right on the listing page. One aggregate query for the page.
    owner_rating = LandlordRating.objects.filter(landlord=house.owner).aggregate(
        avg=Avg('rating'), n=Count('id'),
    )

    # Logged-in users keep their sidebar shell; visitors get the public navbar.
    template = 'core/boarding_detail_app.html' if request.user.is_authenticated else 'core/boarding_detail.html'
    return render(request, template, {
        'house': house,
        'rooms': rooms,
        'owner_rating_avg': owner_rating['avg'],
        'owner_rating_count': owner_rating['n'],
    })


_ROLE_DASHBOARDS = {
    User.Role.STUDENT: 'student_dashboard',
    User.Role.LANDLORD: 'landlord_dashboard',
    User.Role.ADMIN: 'admin_dashboard',
}


def _dashboard_for(user):
    """Where an already-authenticated user belongs."""
    return _ROLE_DASHBOARDS.get(getattr(user, 'role', None), 'listing_list')


def _redirect_if_authenticated(request):
    """Login pages must never render for users who are already signed in.

    An already-signed-in visitor goes to their OWN dashboard and never to
    `?next=`. Django's `user_passes_test` bounces a signed-in user who lacks
    the role a page requires to `LOGIN_URL?next=<the page they were just
    denied>`, so honouring that parameter here bounced them straight back --
    an unbounded redirect loop that ended in the browser's
    ERR_TOO_MANY_REDIRECTS page instead of any page at all. Someone who is
    already signed in has nothing left to sign in to, so the only useful thing
    a login page can do for them is step aside.
    """
    if request.user.is_authenticated:
        return redirect(_dashboard_for(request.user))
    return None


# Authentication views
def student_register(request):
    from django.contrib.auth.forms import AuthenticationForm
    next_url = request.POST.get('next') or request.GET.get('next') or ''
    if not student_access_enabled():
        messages.error(request, 'Student registration is currently disabled. Please contact the BHIMS admin.')
        return redirect('home')
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST, auto_id='reg_%s')
        if form.is_valid():
            user = form.save(commit=False)
            user.role = User.Role.STUDENT
            user.save()
            login(request, user)
            return redirect(_safe_redirect_target(next_url) or 'student_dashboard')
    else:
        form = StudentRegistrationForm(auto_id='reg_%s')
    # Shares the animated Sign in / Sign up page with the login views;
    # it opens straight on the registration pane.
    return render(request, 'core/auth/login_student.html', {
        'form': AuthenticationForm(auto_id='login_%s'),
        'reg_form': form,
        'next': next_url,
        # The registration route always opens on the sign-up pane.
        'initial_mode': 'signup',
        'student_registration_enabled': True,
    })


def accounts_login(request):
    early = _redirect_if_authenticated(request)
    if early:
        return early
    from django.contrib.auth.forms import AuthenticationForm
    next_url = _safe_redirect_target(request.POST.get('next') or request.GET.get('next'))
    form = AuthenticationForm(request, data=request.POST or None)
    registration_enabled = student_access_enabled()
    if request.method == 'POST':
        locked, _fails, _until = _lockout_state(request)
        if locked:
            messages.error(request, 'Too many failed attempts. This account is temporarily locked — try again in about 30 minutes.')
            return render(request, 'core/auth/login_student.html', {
                'form': form,
                'reg_form': StudentRegistrationForm(auto_id='reg_%s'),
                'next': next_url,
                'initial_mode': 'signin',
            })
        if _throttle_login(request):
            messages.error(request, 'Too many attempts. Please wait a minute and try again.')
            return render(request, 'core/auth/login_student.html', {
                'form': form,
                'reg_form': StudentRegistrationForm(auto_id='reg_%s'),
                'next': next_url,
                'initial_mode': 'signin',
            })
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me')
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_active:
            if user.role == User.Role.STUDENT and not registration_enabled:
                # The admin has closed the student side. A correct student
                # password must not open a session; this is not a failed
                # credential, so it is not counted against the lockout.
                messages.error(
                    request,
                    'Student sign-in is currently disabled. Please contact the BHIMS admin.',
                )
            else:
                login(request, user)
                _clear_login_failures(request)
                if remember_me:
                    request.session.set_expiry(1209600)  # 2 weeks
                else:
                    request.session.set_expiry(0)  # expire when the browser closes
                role_dashboards = {
                    User.Role.STUDENT: 'student_dashboard',
                    User.Role.LANDLORD: 'landlord_dashboard',
                    User.Role.ADMIN: 'admin_dashboard',
                }
                return redirect(next_url or role_dashboards.get(user.role, 'profile'))
        else:
            _record_login_failure(request)
            messages.error(request, 'Invalid credentials or account disabled.')
    # A failed sign-up reopens the registration half, and so does a
    # ?mode=signup link — the deck keeps that parameter in the address bar, so
    # reloading one has to land on the same half instead of flashing the
    # sign-in form first. A failed sign-in stays put.
    # With registration switched off there is no sign-up sheet to show, so a
    # stale ?mode=signup link (or a failed sign-up POST) must land on sign-in
    # instead — otherwise the page's title says "Create your account" while
    # neither form is visible.
    initial_mode = 'signup' if registration_enabled and (
        request.POST.get('password1') is not None or request.GET.get('mode') == 'signup'
    ) else 'signin'
    return render(request, 'core/auth/login_student.html', {
        'form': form,
        'reg_form': StudentRegistrationForm(auto_id='reg_%s'),
        'next': next_url,
        'initial_mode': initial_mode,
        'student_registration_enabled': registration_enabled,
    })


def landlord_register(request):
    # Landlord accounts are created by the admin only; this route exists so
    # old bookmarks do not 404.
    messages.info(request, 'All landlords who want an account must go to DMMMSU for account registration.')
    return redirect('landlord_login')


def student_login(request):
    early = _redirect_if_authenticated(request)
    if early:
        return early
    from django.contrib.auth.forms import AuthenticationForm
    next_url = _safe_redirect_target(request.POST.get('next') or request.GET.get('next'))
    form = AuthenticationForm(request, data=request.POST or None)
    registration_enabled = student_access_enabled()
    if request.method == 'POST' and not registration_enabled:
        messages.error(
            request,
            'Student sign-in is currently disabled. Please contact the BHIMS admin.',
        )
    elif request.method == 'POST':
        locked, _fails, _until = _lockout_state(request)
        if locked:
            messages.error(request, 'Too many failed attempts. This account is temporarily locked — try again in about 30 minutes.')
            return render(request, 'core/auth/login_student.html', {
                'form': form,
                'reg_form': StudentRegistrationForm(auto_id='reg_%s'),
                'next': next_url,
                'initial_mode': 'signin',
            })
        if _throttle_login(request):
            messages.error(request, 'Too many attempts. Please wait a minute and try again.')
            return render(request, 'core/auth/login_student.html', {
                'form': form,
                'reg_form': StudentRegistrationForm(auto_id='reg_%s'),
                'next': next_url,
                'initial_mode': 'signin',
            })
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me')
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_active and user.role == User.Role.STUDENT:
            login(request, user)
            _clear_login_failures(request)
            if remember_me:
                request.session.set_expiry(1209600)  # 2 weeks
            else:
                request.session.set_expiry(0)  # expire when the browser closes
            return redirect(next_url or 'student_dashboard')
        else:
            _record_login_failure(request)
            messages.error(request, 'Invalid credentials or account disabled.')
    # A failed sign-up reopens the registration half, and so does a
    # ?mode=signup link — see accounts_login above.
    # With registration switched off there is no sign-up sheet to show, so a
    # stale ?mode=signup link (or a failed sign-up POST) must land on sign-in
    # instead — otherwise the page's title says "Create your account" while
    # neither form is visible.
    initial_mode = 'signup' if registration_enabled and (
        request.POST.get('password1') is not None or request.GET.get('mode') == 'signup'
    ) else 'signin'
    return render(request, 'core/auth/login_student.html', {
        'form': form,
        'reg_form': StudentRegistrationForm(auto_id='reg_%s'),
        'next': next_url,
        'initial_mode': initial_mode,
        'student_registration_enabled': registration_enabled,
    })


def landlord_login(request):
    early = _redirect_if_authenticated(request)
    if early:
        return early
    from django.contrib.auth.forms import AuthenticationForm
    next_url = _safe_redirect_target(request.POST.get('next') or request.GET.get('next'))
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST':
        locked, _fails, _until = _lockout_state(request)
        if locked:
            messages.error(request, 'Too many failed attempts. This account is temporarily locked — try again in about 30 minutes.')
            return render(request, 'core/auth/login_landlord.html', {'form': form, 'next': next_url})
        if _throttle_login(request):
            messages.error(request, 'Too many attempts. Please wait a minute and try again.')
            return render(request, 'core/auth/login_landlord.html', {'form': form, 'next': next_url})
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me')
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_active and user.role == User.Role.LANDLORD:
            login(request, user)
            _clear_login_failures(request)
            if remember_me:
                request.session.set_expiry(1209600)  # 2 weeks
            else:
                request.session.set_expiry(0)  # expire when the browser closes
            return redirect(next_url or 'landlord_dashboard')
        else:
            _record_login_failure(request)
            messages.error(request, 'Invalid credentials or not an active landlord account.')
    return render(request, 'core/auth/login_landlord.html', {'form': form, 'next': next_url})


def admin_login(request):
    early = _redirect_if_authenticated(request)
    if early:
        return early
    from django.contrib.auth.forms import AuthenticationForm
    from django.conf import settings as django_settings
    from myproject.middleware import totp_is_valid
    next_url = _safe_redirect_target(request.POST.get('next') or request.GET.get('next'))
    totp_required = bool(getattr(django_settings, 'ADMIN_TOTP_SECRET', ''))
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST':
        # Optional 2FA: when DJANGO_ADMIN_TOTP_SECRET is configured, admin
        # sign-in additionally requires a valid 6-digit TOTP code.
        if totp_required and not totp_is_valid(
            django_settings.ADMIN_TOTP_SECRET, request.POST.get('totp_code', '')
        ):
            messages.error(request, 'Invalid or expired verification code.')
            return render(request, 'core/auth/login_admin.html', {
                'form': AuthenticationForm(), 'next': next_url, 'totp_required': True,
            })
        locked, _fails, _until = _lockout_state(request)
        if locked:
            messages.error(request, 'Too many failed attempts. This account is temporarily locked — try again in about 30 minutes.')
            return render(request, 'core/auth/login_admin.html', {'form': form, 'next': next_url, 'totp_required': totp_required})
        if _throttle_login(request):
            messages.error(request, 'Too many attempts. Please wait a minute and try again.')
            return render(request, 'core/auth/login_admin.html', {'form': form, 'next': next_url, 'totp_required': totp_required})
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me')
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_active and user.role == User.Role.ADMIN:
            login(request, user)
            _clear_login_failures(request)
            if remember_me:
                request.session.set_expiry(1209600)  # 2 weeks
            else:
                request.session.set_expiry(0)  # expire when the browser closes
            return redirect(next_url or 'admin_dashboard')
        else:
            _record_login_failure(request)
            messages.error(request, 'Invalid credentials or not an admin account.')
    return render(request, 'core/auth/login_admin.html', {'form': form, 'next': next_url, 'totp_required': totp_required})


@require_POST
def logout_view(request):
    logout(request)
    return redirect('home')


# Student views
@login_required
def profile_view(request):
    if request.user.role == User.Role.ADMIN:
        messages.info(request, 'Admin accounts do not have a profile page.')
        return redirect('admin_dashboard')
    user = request.user
    context = {
        'is_landlord': user.role == 'landlord',
        'is_student': user.role == 'student',
        'program_choices': User.Program.choices,
    }
    if user.role == 'landlord':
        # related_name on BoardingHouse is 'boarding_houses'
        context['boarding_house_count'] = user.boarding_houses.filter(is_active=True).count()
    return render(request, 'core/profile.html', context)


def _serialize_profile(user):
    """Profile fields the client needs to refresh the card after a save."""
    return {
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'full_name': user.full_name,
        'email': user.email,
        'student_id': user.student_id or '',
        'program': user.get_program_display() if user.program else '',
        'program_custom': user.program_custom or '',
        'phone_number': user.phone_number or '',
        'bio': user.bio or '',
        'profile_picture': user.profile_picture.url if user.profile_picture else '',
    }


@login_required
def update_profile(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)
    if _throttle_generic(request, scope='profile'):
        return JsonResponse({'success': False, 'message': 'Too many requests. Slow down.'}, status=429)

    user = request.user
    if user.role not in ('student', 'landlord'):
        return JsonResponse({
            'success': False,
            'message': 'Admin accounts do not have a profile page.'
        }, status=403)

    try:
        payload = json.loads(request.body or b'{}')
    except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
        return JsonResponse({'success': False, 'message': 'Invalid data received.'}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({'success': False, 'message': 'Invalid data received.'}, status=400)

    from .models import log_admin_action

    # The "Clear bio" / "Clear Profile Picture" buttons send a single flag, not
    # the whole form. Handle them before validation, which would otherwise
    # reject the payload for missing name/phone fields.
    if payload.get('clear_bio'):
        user.bio = ''
        user.save(update_fields=['bio'])
        log_admin_action(request.user, 'profile_updated', request.user)
        return JsonResponse({
            'success': True,
            'message': 'Bio cleared.',
            'profile': _serialize_profile(user),
        })

    if payload.get('clear_profile_picture'):
        if user.profile_picture:
            user.profile_picture.delete(save=False)
            user.profile_picture = ''
            user.save(update_fields=['profile_picture'])
        log_admin_action(request.user, 'profile_updated', request.user)
        return JsonResponse({
            'success': True,
            'message': 'Profile picture cleared.',
            'profile': _serialize_profile(user),
        })

    if user.role == 'student':
        form = StudentProfileUpdateForm(payload, instance=user)
    else:
        form = LandlordProfileUpdateForm(payload, instance=user)
    if form.is_valid():
        form.save()
        log_admin_action(request.user, 'profile_updated', request.user)
        return JsonResponse({
            'success': True,
            'message': 'Profile updated successfully.',
            'profile': _serialize_profile(user),
        })
    else:
        return JsonResponse({'success': False, 'message': 'Please correct the errors.', 'errors': form.errors}, status=400)


@login_required
def upload_profile_picture(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)
    if _throttle_generic(request, scope='avatar'):
        return JsonResponse({'success': False, 'message': 'Too many requests. Slow down.'}, status=429)

    form = LandlordProfilePictureForm(request.POST, request.FILES, instance=request.user)
    if form.is_valid():
        form.save()
        from .models import log_admin_action
        log_admin_action(request.user, 'avatar_updated', request.user)
        return JsonResponse({
            'success': True,
            'message': 'Profile picture updated.',
            'image_url': request.user.profile_picture.url if request.user.profile_picture else '',
        })
    return JsonResponse({'success': False, 'message': 'Could not process image.'}, status=400)


@login_required
def change_password(request):
    """Change-password page: GET renders the form, POST validates and saves.
    Write requests are rate-limited (password brute-force through this form
    is pointless — it requires the current password — but the endpoint still
    gets flood protection like every other POST)."""
    if request.method == 'POST':
        if _throttle_generic(request, scope='password'):
            messages.error(request, 'Too many requests. Please wait a minute.')
            return redirect('change_password')
        form = BHIMSPasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            from .models import log_admin_action
            log_admin_action(request.user, 'password_changed', request.user)
            # Keep the user logged in after their password changed
            update_session_auth_hash(request, user)
            messages.success(request, 'Password changed successfully!')
            return redirect('change_password')
    else:
        form = BHIMSPasswordChangeForm(user=request.user)
    return render(request, 'core/change_password.html', {'form': form})


@login_required
def user_profile(request, pk):
    person = get_object_or_404(User, pk=pk)
    if person.role == User.Role.ADMIN:
        raise Http404('Profile not found.')

    viewer = request.user
    # Object-level access control (fixes IDOR): students and landlords may
    # open landlord profiles (public business card) and their OWN profile
    # only — never another student's private data (phone, bookings).
    is_self = viewer.pk == person.pk
    is_public_card = person.role == User.Role.LANDLORD
    is_admin = viewer.role == User.Role.ADMIN
    # A landlord must be able to open the student they are negotiating with:
    # the inquiry thread links that student's name and avatar, and denying it
    # 404s the link in the middle of the flow the system is built around. The
    # scope stays narrow — only a student with an inquiry or booking under
    # THIS landlord — so student-to-student privacy is unchanged.
    is_counterpart = (
        viewer.role == User.Role.LANDLORD
        and person.role == User.Role.STUDENT
        and (
            Inquiry.objects.filter(student=person, room__boarding_house__owner=viewer).exists()
            or Booking.objects.filter(student=person, room__boarding_house__owner=viewer).exists()
        )
    )
    if not (is_self or is_public_card or is_admin or is_counterpart):
        raise Http404('Profile not found.')
    if person.role == 'landlord':
        # A landlord's public card lists what a student could actually book.
        # Rating now happens from the student's My Inquiries page once the
        # conversation is settled, so this page only shows the results.
        houses = visible_listings().filter(owner=person).order_by('-id')
        ratings = person.landlord_ratings_received.select_related('student')
        return render(request, 'core/user_profile.html', {
            'person': person,
            'viewed_is_landlord': True,
            'houses': houses,
            'ratings': ratings,
            'average_rating': ratings.aggregate(Avg('rating'))['rating__avg'],
            'rating_count': ratings.count(),
        })

    phone_visible = False
    if viewer.role == 'landlord':
        phone_visible = Booking.objects.filter(
            student=person,
            status=Booking.Status.CONFIRMED,
            room__boarding_house__owner=viewer,
        ).exists()

    return render(request, 'core/user_profile.html', {
        'person': person,
        'viewed_is_landlord': person.role == User.Role.LANDLORD,
        'phone_visible': phone_visible,
    })


def _rating_redirect(request, landlord):
    """Return to wherever the rating form was shown.

    The form lives on the student's My Inquiries page (and the conversation
    thread it opens), so that is the default; a `next` field lets a form shown
    anywhere else send the student back to it.
    """
    from django.utils.http import url_has_allowed_host_and_scheme
    nxt = request.POST.get('next') or ''
    if nxt and url_has_allowed_host_and_scheme(
        nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
    ):
        return redirect(nxt)
    return redirect('student_inquiry_list')


@login_required
@user_passes_test(student_required)
@require_POST
def rate_landlord(request, pk):
    landlord = get_object_or_404(User, pk=pk, role=User.Role.LANDLORD)
    if LandlordRating.objects.filter(student=request.user, landlord=landlord).exists():
        messages.info(request, 'You have already rated this landlord.')
        return _rating_redirect(request, landlord)

    # Race guard: the DB unique constraint on (student, landlord) is the last
    # line of defense; wrapping the pick-booking + save in one transaction
    # with an IntegrityError fallback turns what used to be a 500 page under
    # double-submits into a friendly 'already rated' message.
    from django.db import IntegrityError, transaction
    # A rating is earned by a settled conversation: the landlord accepted the
    # student (a confirmed booking) or declined them (a rejected inquiry).
    # Deterministic pick, oldest confirmed first: without an explicit order the
    # database was free to attach the rating to either property, so a
    # landlord-facing per-property rating could point at the wrong house.
    booking = Booking.objects.filter(
        student=request.user,
        status=Booking.Status.CONFIRMED,
        room__boarding_house__owner=landlord,
    ).order_by('confirmed_at', 'id').select_related('room__boarding_house').first()
    declined = Inquiry.objects.filter(
        student=request.user,
        status=Inquiry.Status.REJECTED,
        room__boarding_house__owner=landlord,
    ).exists()
    if not booking and not declined:
        messages.error(
            request,
            'You can rate a landlord only after they accept or decline your inquiry.',
        )
        return _rating_redirect(request, landlord)

    form = LandlordRatingForm(request.POST)
    if form.is_valid():
        try:
            with transaction.atomic():
                rating = form.save(commit=False)
                rating.student = request.user
                rating.landlord = landlord
                # No booking when the landlord declined - the rating still
                # records the student's experience with that landlord.
                rating.booking = booking
                rating.save()
            messages.success(request, 'Your rating has been submitted.')
        except IntegrityError:
            messages.info(request, 'You have already rated this landlord.')
    return _rating_redirect(request, landlord)


@login_required
@user_passes_test(lambda u: u.is_authenticated and u.role in (User.Role.STUDENT, User.Role.LANDLORD))
def report_user(request, pk):
    person = get_object_or_404(User, pk=pk)
    if person.role == User.Role.ADMIN:
        raise Http404('Profile not found.')
    if person.pk == request.user.pk:
        messages.error(request, 'You cannot report your own account.')
        return redirect('user_profile', pk=pk)

    if request.method == 'POST':
        if UserReport.objects.filter(
            reporter=request.user,
            reported_user=person,
            status=UserReport.Status.PENDING,
        ).exists():
            messages.info(request, 'You already have a pending report for this user.')
            return redirect('user_profile', pk=pk)
        form = UserReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.reporter = request.user
            report.reported_user = person
            report.save()
            messages.success(request, 'Your report has been submitted and will be reviewed by the administrator.')
            return redirect('user_profile', pk=pk)
    else:
        form = UserReportForm()

    return render(request, 'core/report_user.html', {
        'form': form,
        'person': person,
    })


@login_required
@user_passes_test(student_required)
def student_dashboard(request):
    inquiries = (
        Inquiry.objects.filter(student=request.user)
        .select_related('room', 'room__boarding_house')
        .order_by('-created_at')[:8]
    )
    active_inquiries = Inquiry.objects.filter(
        student=request.user,
        status__in=[Inquiry.Status.PENDING, Inquiry.Status.OPEN]
    ).count()
    confirmed_bookings = Booking.objects.filter(
        student=request.user,
        status=Booking.Status.CONFIRMED,
    ).count()
    return render(request, 'core/student_dashboard.html', {
        'inquiries': inquiries,
        'student': request.user,
        'active_inquiries': active_inquiries,
        'confirmed_bookings': confirmed_bookings,
        'total_inquiries': Inquiry.objects.filter(student=request.user).count(),
    })


@login_required
@user_passes_test(student_required)
def student_inquiry_list(request):
    inquiries = (
        Inquiry.objects.filter(student=request.user)
        .select_related('room', 'room__boarding_house__owner')
        .order_by('-created_at')
    )

    # Unread conversations (a landlord reply since the student last opened
    # the thread) each get a NEW chip, mirroring the landlord's own list.
    inquiries = _with_latest_message(inquiries)
    new_inquiry_ids = {
        inq.pk for inq in inquiries
        if _inquiry_has_new_message(inq, 'last_viewed_by_student')
    }
    inquiries = list(inquiries)

    # Rating lives here now, on the settled conversations. Two bulk lookups
    # keep it off the per-row query count: which landlords the student has
    # already rated, and which rooms they hold a confirmed booking in. A
    # settled conversation is one the landlord accepted (a confirmed booking
    # in that room) or declined (the inquiry itself is rejected).
    landlord_ids = {inq.room.boarding_house.owner_id for inq in inquiries}
    rated_landlord_ids = set(
        LandlordRating.objects.filter(
            student=request.user, landlord_id__in=landlord_ids,
        ).values_list('landlord_id', flat=True)
    )
    accepted_room_ids = set(
        Booking.objects.filter(
            student=request.user,
            status=Booking.Status.CONFIRMED,
            room_id__in=[inq.room_id for inq in inquiries],
        ).values_list('room_id', flat=True)
    )
    for inq in inquiries:
        landlord_id = inq.room.boarding_house.owner_id
        inq.landlord_id = landlord_id
        inq.has_rated_landlord = landlord_id in rated_landlord_ids
        settled = (
            inq.status == Inquiry.Status.REJECTED or inq.room_id in accepted_room_ids
        )
        inq.can_rate_landlord = settled and not inq.has_rated_landlord

    return render(request, 'core/student_inquiry_list.html', {
        'inquiries': inquiries,
        'new_inquiry_ids': new_inquiry_ids,
    })


@login_required
@user_passes_test(student_required)
def student_bookings(request):
    # select_related kills the N+1: the template walks booking -> room ->
    # house -> owner for every row; without the join that's 4 extra queries
    # per booking (measured 10 queries for 3 bookings before this fix).
    bookings = Booking.objects.filter(student=request.user).select_related(
        'room__boarding_house__owner', 'room'
    ).order_by('-requested_at')
    return render(request, 'core/student_bookings.html', {'bookings': bookings})

@login_required
def inquiry_thread(request, pk):
    inquiry = get_object_or_404(Inquiry, pk=pk)
    # Check if user is authorized to view this inquiry
    if request.user != inquiry.student and request.user != inquiry.room.boarding_house.owner:
        messages.error(request, 'You are not authorized to view this inquiry.')
        return redirect('home')
    
    # Mark as viewed by whichever side opened the thread, so the unread
    # ('NEW') badge clears once the conversation is actually read.
    if request.user == inquiry.room.boarding_house.owner:
        inquiry.last_viewed_by_landlord = timezone.now()
        inquiry.save(update_fields=['last_viewed_by_landlord'])
    elif request.user == inquiry.student:
        inquiry.last_viewed_by_student = timezone.now()
        inquiry.save(update_fields=['last_viewed_by_student'])
    
    if request.method == 'POST':
        message_text = (request.POST.get('message_text') or '').strip()
        if message_text:
            if len(message_text) > MAX_MESSAGE_CHARS:
                messages.error(request, f'Messages are limited to {MAX_MESSAGE_CHARS} characters.')
                return redirect(request.path)
            InquiryMessage.objects.create(
                inquiry=inquiry,
                sender=request.user,
                message_text=message_text
            )
            # Status follows activity: any message reopens the thread, whatever
            # it was before — new, closed after acceptance, or declined. Only
            # PENDING used to move, so a CLOSED thread accepted messages while
            # still claiming to be closed.
            if inquiry.status != Inquiry.Status.OPEN:
                inquiry.status = Inquiry.Status.OPEN
                inquiry.save(update_fields=['status'])
            messages.success(request, 'Message sent successfully!')
            return redirect(request.path)
    
    accepted_booking = Booking.objects.filter(
        student=inquiry.student,
        room=inquiry.room,
        status=Booking.Status.CONFIRMED,
    ).first()

    # The student rates the landlord from here once the conversation is
    # settled - the landlord accepted (a confirmed booking exists) or declined
    # (the inquiry is rejected). Same rule rate_landlord enforces.
    rating_landlord = None
    if request.user == inquiry.student:
        landlord = inquiry.room.boarding_house.owner
        has_rated = LandlordRating.objects.filter(
            student=request.user, landlord=landlord,
        ).exists()
        settled = (
            accepted_booking is not None
            or inquiry.status == Inquiry.Status.REJECTED
        )
        if settled:
            rating_landlord = {
                'landlord': landlord,
                'has_rated': has_rated,
                'can_rate': not has_rated,
            }

    return render(request, 'core/inquiry_thread.html', {
        'inquiry': inquiry,
        'accepted_booking': accepted_booking,
        'rating_landlord': rating_landlord,
        'last_message_id': inquiry.messages.last().id if inquiry.messages.exists() else 0,
    })


@login_required
def accept_student(request, pk):
    inquiry = get_object_or_404(Inquiry, pk=pk)

    if request.user != inquiry.room.boarding_house.owner:
        messages.error(request, 'You are not authorized to accept this student.')
        return redirect('home')

    if request.method != 'POST':
        return redirect('landlord_inquiry_thread', pk=inquiry.pk)

    # Lock the room row so two simultaneous accepts cannot overbook the last slot
    with transaction.atomic():
        room = Room.objects.select_for_update().select_related(
            'boarding_house'
        ).get(pk=inquiry.room_id)

        # A rejected or switched-off listing is invisible to students, so a
        # booking inside it is a booking nobody can act on. Refuse before the
        # row is written instead of leaving orphaned reservations behind.
        if (room.boarding_house.status != BoardingHouse.Status.APPROVED
                or not room.boarding_house.is_active):
            messages.error(
                request,
                'This listing is no longer available to students, so the '
                'student cannot be accepted.',
            )
            return redirect('landlord_inquiry_thread', pk=inquiry.pk)

        accepted_booking = Booking.objects.filter(
            student=inquiry.student,
            room=room,
            status=Booking.Status.CONFIRMED,
        ).first()
        if accepted_booking:
            messages.info(request, 'This student has already been accepted for this room.')
            return redirect('landlord_inquiry_thread', pk=inquiry.pk)

        if room.is_full or not room.is_active or not room.is_available:
            messages.error(request, 'This room has no space left, so the student cannot be accepted.')
            return redirect('landlord_inquiry_thread', pk=inquiry.pk)

        booking = Booking.objects.create(
            student=inquiry.student,
            room=room,
            status=Booking.Status.CONFIRMED,
            confirmed_at=timezone.now(),
            notes=f'Accepted via inquiry #{inquiry.pk}.',
        )

        inquiry.status = Inquiry.Status.CLOSED
        inquiry.save(update_fields=['status'])

        # Written inside the same transaction as the booking: a confirmed
        # booking must never exist without the message that tells the student
        # about it (a crash between the two used to leave exactly that).
        InquiryMessage.objects.create(
            inquiry=inquiry,
            sender=request.user,
            message_text=(
                f'System: Great news! Your booking for this room has been accepted. '
                f'It is now reserved for you.'
            ),
        )

    messages.success(request, f'{inquiry.student.full_name or inquiry.student.username} has been accepted!')
    return redirect('landlord_inquiry_thread', pk=inquiry.pk)


@login_required
@user_passes_test(landlord_required)
def reject_student(request, pk):
    inquiry = get_object_or_404(Inquiry, pk=pk)

    if request.user != inquiry.room.boarding_house.owner:
        messages.error(request, 'You are not authorized to reject this inquiry.')
        return redirect('home')

    if request.method != 'POST':
        return redirect('landlord_inquiry_thread', pk=inquiry.pk)

    if Booking.objects.filter(student=inquiry.student, room=inquiry.room, status=Booking.Status.CONFIRMED).exists():
        messages.info(request, 'This student has already been accepted — use the Bookings page to manage their stay.')
        return redirect('landlord_inquiry_thread', pk=inquiry.pk)

    inquiry.status = Inquiry.Status.REJECTED
    inquiry.save(update_fields=['status'])

    messages.info(request, f'Inquiry from {inquiry.student.full_name or inquiry.student.username} has been declined.')
    return redirect('landlord_inquiry_thread', pk=inquiry.pk)


@login_required
def inquiry_messages_json(request, pk):
    inquiry = get_object_or_404(Inquiry, pk=pk)
    if request.user != inquiry.student and request.user != inquiry.room.boarding_house.owner:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    try:
        since = int(request.GET.get('since', 0))
    except (TypeError, ValueError):
        since = 0

    messages = [
        {
            'id': m.id,
            'text': m.message_text,
            'sender': m.sender.full_name or m.sender.username,
            'is_self': m.sender_id == request.user.id,
            'time': timezone.localtime(m.sent_at).strftime('%b %d, %Y %I:%M %p'),
            'photo': m.sender.profile_picture.url if m.sender.profile_picture else None,
        }
        for m in inquiry.messages.filter(id__gt=since)
    ]
    return JsonResponse({'messages': messages})

@login_required
@user_passes_test(student_required)
def send_inquiry(request, pk=None):
    room_id = request.POST.get('room_id') or pk
    room = get_object_or_404(Room, pk=room_id)

    # Only allow inquiries to rooms in approved, active boarding houses
    house = room.boarding_house
    if house.status != BoardingHouse.Status.APPROVED or not house.is_active:
        messages.error(request, 'This room is not currently available for inquiries.')
        return redirect('listing_list')

    # Reuse an existing conversation for this student + room, or start a new one.
    # A declined conversation is kept until the student explicitly confirms a
    # replacement on a POST — see below.
    existing = Inquiry.objects.filter(student=request.user, room=room).order_by('-created_at').first()
    previously_declined = bool(existing and existing.status == Inquiry.Status.REJECTED)

    def form_page(form):
        return render(request, 'core/send_inquiry.html', {
            'room': room,
            'form': form,
            'previously_declined': previously_declined,
        })

    if request.method == 'POST':
        message_text = (request.POST.get('message_text') or '').strip()
        if not message_text:
            messages.error(request, 'Please write a message before sending your inquiry.')
            bound = InquiryForm(request.POST)
            bound.is_valid()
            return form_page(bound)
        if len(message_text) > MAX_MESSAGE_CHARS:
            messages.error(request, f'Messages are limited to {MAX_MESSAGE_CHARS} characters.')
            return form_page(InquiryForm())
        if previously_declined:
            # Replacing a declined thread is destructive, so it happens only on
            # an explicit POST carrying the confirmation field the form renders.
            # A GET — an old link, a prefetch, a crawler — can no longer wipe
            # the student's inquiry and its whole message history.
            if not request.POST.get('reapply'):
                messages.error(request, 'Please confirm that you want to replace your declined inquiry.')
                return form_page(InquiryForm(request.POST))
            with transaction.atomic():
                existing.delete()
                existing = None
        if existing:
            messages.info(request, 'You already have a conversation about this room.')
            return redirect('student_inquiry_thread', pk=existing.pk)
        inquiry = Inquiry.objects.create(
            student=request.user,
            room=room,
            subject=(request.POST.get('subject') or '').strip()[:255],  # clamp: model max_length
            message_text=message_text,
        )
        messages.success(request, 'Your inquiry has been sent to the landlord!')
        return redirect('student_inquiry_thread', pk=inquiry.pk)

    # GET: never create and never delete — show the form. When the last inquiry
    # for this room was declined the page says so and explains that sending
    # replaces it.
    if existing and not previously_declined:
        return redirect('student_inquiry_thread', pk=existing.pk)
    return form_page(InquiryForm(initial={'message_text': 'Hello! I would like to inquire about this room.'}))


# Landlord views
@login_required
@user_passes_test(landlord_required)
def landlord_dashboard(request):
    houses = BoardingHouse.objects.filter(owner=request.user).annotate(
        total_rooms=Count('rooms'),
    )
    inquiries = Inquiry.objects.filter(room__boarding_house__owner=request.user).order_by('-created_at')
    total_available_rooms = Room.objects.filter(boarding_house__owner=request.user, is_available=True).count()
    
    # Determine which inquiries have new messages (one subquery, not one
    # query per inquiry)
    new_inquiry_ids = set()
    for inq in _with_latest_message(inquiries[:5]):  # top 5 shown on dashboard
        if inq.status in [Inquiry.Status.CLOSED, Inquiry.Status.REJECTED]:
            continue
        if _inquiry_has_new_message(inq):
            new_inquiry_ids.add(inq.pk)
    
    return render(request, 'core/landlord_dashboard.html', {
        'houses': houses,
        'inquiries': inquiries,
        'landlord': request.user,
        'total_available_rooms': total_available_rooms,
        'new_inquiry_ids': new_inquiry_ids,
    })


@login_required
@user_passes_test(landlord_required)
def landlord_boarding_house_list(request):
    # total_rooms is annotated: the template asked for house.rooms.count per
    # card, which is one extra COUNT query per listing.
    houses = BoardingHouse.objects.filter(owner=request.user).annotate(
        total_rooms=Count('rooms'),
    ).order_by('-id')
    return render(request, 'core/landlord_boarding_house_list.html', {
        'houses': houses,
        'landlord': request.user
    })


@login_required
@user_passes_test(landlord_required)
def boarding_house_create(request):
    if request.method == 'POST':
        form = BoardingHouseForm(request.POST, request.FILES)
        if form.is_valid():
            house = form.save(commit=False)
            house.owner = request.user
            house.status = BoardingHouse.Status.PENDING
            house.is_active = False
            try:
                house.save()
                messages.success(
                    request,
                    'Boarding house submitted! It will appear to students once approved by the admin.',
                )
                return redirect('landlord_boarding_house_detail', pk=house.pk)
            except ValidationError as e:
                messages.error(request, str(e))
    else:
        form = BoardingHouseForm()
    return render(request, 'core/boarding_house_form.html', {'form': form})


@login_required
@user_passes_test(landlord_required)
def boarding_house_edit(request, pk):
    house = get_object_or_404(BoardingHouse, pk=pk, owner=request.user)
    if request.method == 'POST':
        form = BoardingHouseForm(request.POST, request.FILES, instance=house)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Boarding house updated.')
                return redirect('landlord_boarding_house_detail', pk=house.pk)
            except ValidationError as e:
                messages.error(request, str(e))
    else:
        form = BoardingHouseForm(instance=house)
    return render(request, 'core/boarding_house_form.html', {'form': form, 'house': house})


@login_required
@user_passes_test(landlord_required)
def room_create(request, pk):
    house = get_object_or_404(BoardingHouse, pk=pk, owner=request.user)
    if request.method == 'POST':
        # Room photos are the largest thing a landlord can push at us, so this
        # endpoint is rate-limited like the other upload paths.
        if _throttle_generic(request, scope='room-photo', per_minute=20):
            messages.error(request, 'Too many uploads. Please wait a minute and try again.')
            return redirect('landlord_boarding_house_detail', pk=house.pk)
        form = RoomForm(request.POST, request.FILES)
        if form.is_valid():
            room = form.save(commit=False)
            room.boarding_house = house
            room.save()
            photo = form.cleaned_data.get('photo')
            if photo:
                RoomPhoto.objects.create(room=room, image=photo)
            messages.success(request, 'Room created successfully!')
            return redirect('landlord_boarding_house_detail', pk=house.pk)
    else:
        form = RoomForm()
    return render(request, 'core/room_form.html', {'form': form, 'house': house, 'title': 'Add New Room'})

@login_required
@user_passes_test(landlord_required)
def room_edit(request, pk):
    room = get_object_or_404(Room, pk=pk, boarding_house__owner=request.user)
    if request.method == 'POST':
        # Same rationale as room_create: this path writes a user file.
        if _throttle_generic(request, scope='room-photo', per_minute=20):
            messages.error(request, 'Too many uploads. Please wait a minute and try again.')
            return redirect('landlord_boarding_house_detail', pk=room.boarding_house.pk)
        form = RoomForm(request.POST, request.FILES, instance=room)
        if form.is_valid():
            form.save()
            photo = form.cleaned_data.get('photo')
            if photo:
                for existing in room.photos.all():
                    existing.image.delete(save=False)
                room.photos.all().delete()
                RoomPhoto.objects.create(room=room, image=photo)
            messages.success(request, 'Room updated successfully!')
            return redirect('landlord_boarding_house_detail', pk=room.boarding_house.pk)
    else:
        form = RoomForm(instance=room)
    return render(request, 'core/room_form.html', {'form': form, 'room': room, 'house': room.boarding_house, 'title': 'Edit Room'})

@login_required
@user_passes_test(landlord_required)
@require_POST
def toggle_room_availability(request, pk):
    room = get_object_or_404(Room, pk=pk, boarding_house__owner=request.user)
    room.is_available = not room.is_available
    room.save(update_fields=['is_available'])
    status = "available" if room.is_available else "unavailable"
    messages.success(request, f'Room marked as {status}.')
    return redirect('landlord_boarding_house_detail', pk=room.boarding_house.pk)


@login_required
@user_passes_test(lambda u: u.role in (User.Role.LANDLORD, User.Role.ADMIN))
def landlord_boarding_house_detail(request, pk):
    # Admins may view any property page read-only; landlords only their own.
    if request.user.role == User.Role.ADMIN:
        house = get_object_or_404(BoardingHouse, pk=pk)
    else:
        house = get_object_or_404(BoardingHouse, pk=pk, owner=request.user)
    # Annotated so the page runs a fixed number of queries no matter how many
    # rooms the property has (this page used to run 104 queries for 12 rooms).
    rooms = list(
        annotate_room_bookings(house.rooms.all())
        .prefetch_related('photos', 'amenities')
        .order_by('monthly_rate', 'id')
    )
    inquiries = (
        Inquiry.objects.filter(room__boarding_house=house)
        .select_related('student', 'room')
        .prefetch_related('messages')
        .order_by('-created_at')
    )
    return render(request, 'core/landlord_boarding_house_detail.html', {
        'house': house,
        'rooms': rooms,
        'inquiries': inquiries,
        'available_count': sum(1 for room in rooms if room.has_space()),
        'occupied_count': sum(room.occupied_count for room in rooms),
    })


@login_required
@user_passes_test(landlord_required)
@require_POST
def resubmit_listing(request, pk):
    """Send a rejected listing back to the admin queue.

    The admin reject confirmation has always told landlords they can resubmit,
    but there was no route to do it: a rejected house stayed invisible to
    students forever. Resubmitting only clears the rejection — it never
    approves the house itself, so the admin still decides.
    """
    house = get_object_or_404(BoardingHouse, pk=pk, owner=request.user)
    if house.status == BoardingHouse.Status.REJECTED:
        house.status = BoardingHouse.Status.PENDING
        house.is_active = False
        house.save(update_fields=['status', 'is_active'])
        messages.success(
            request,
            f'"{house.name}" was resubmitted and is now waiting for admin approval.',
        )
    elif house.status == BoardingHouse.Status.PENDING:
        messages.info(request, 'This listing is already waiting for admin approval.')
    else:
        messages.info(request, 'This listing is already approved and visible to students.')
    return redirect('landlord_boarding_house_detail', pk=house.pk)


@login_required
@user_passes_test(landlord_required)
def landlord_inquiry_list(request):
    inquiries = Inquiry.objects.filter(
        room__boarding_house__owner=request.user
    ).order_by('-created_at')
    
    # Determine which inquiries have new messages since landlord last viewed
    new_inquiry_ids = set()
    for inq in _with_latest_message(inquiries):
        if inq.status in [Inquiry.Status.CLOSED, Inquiry.Status.REJECTED]:
            continue
        if _inquiry_has_new_message(inq):
            new_inquiry_ids.add(inq.pk)
    
    return render(request, 'core/landlord_inquiry_list.html', {
        'inquiries': inquiries,
        'new_inquiry_ids': new_inquiry_ids,
    })


@login_required
@user_passes_test(landlord_required)
def landlord_bookings(request):
    bookings = Booking.objects.filter(
        room__boarding_house__owner=request.user
    ).select_related('student', 'room__boarding_house').order_by('-requested_at')
    return render(request, 'core/landlord_bookings.html', {'bookings': bookings})


# Admin views
@login_required
@user_passes_test(admin_required)
def admin_dashboard(request):
    from django.db.models import Count
    total_students = User.objects.filter(role=User.Role.STUDENT, is_active=True).count()
    total_landlords = User.objects.filter(role=User.Role.LANDLORD, is_active=True).count()
    total_boarding_houses = BoardingHouse.objects.count()
    total_inquiries = Inquiry.objects.count()
    total_available_rooms = Room.objects.filter(is_available=True).count()
    total_rooms = Room.objects.count()
    pending_listings = BoardingHouse.objects.filter(status=BoardingHouse.Status.PENDING).count()
    program_stats = (
        User.objects.filter(role=User.Role.STUDENT)
        .values('program')
        .annotate(count=Count('program'))
        .order_by('-count')
    )
    top_listings = (
        Inquiry.objects.values('room__boarding_house__name')
        .annotate(inquiry_count=Count('id'))
        .order_by('-inquiry_count')[:5]
    )
    landlords = User.objects.filter(role=User.Role.LANDLORD).order_by('-date_joined')[:5]

    return render(request, 'core/admin_dashboard.html', {
        'total_students': total_students,
        'total_landlords': total_landlords,
        'total_boarding_houses': total_boarding_houses,
        'total_inquiries': total_inquiries,
        'total_available_rooms': total_available_rooms,
        'total_rooms': total_rooms,
        'program_stats': program_stats,
        'top_listings': top_listings,
        'landlords': landlords,
        'pending_listings': pending_listings,
    })


@login_required
@user_passes_test(admin_required)
def admin_analytics(request):
    from django.db.models import Count
    from django.db.models.functions import TruncMonth
    from datetime import datetime

    # Basic analytics data
    total_students = User.objects.filter(role=User.Role.STUDENT, is_active=True).count()
    total_landlords = User.objects.filter(role=User.Role.LANDLORD, is_active=True).count()
    total_boarding_houses = BoardingHouse.objects.count()
    total_inquiries = Inquiry.objects.count()
    total_bookings = Booking.objects.count()

    # Monthly registrations (last 6 months) — real calendar months,
    # timezone-aware so comparisons against date_joined are correct.
    today = timezone.localdate()
    last_six_months = []
    year_i, month_i = today.year, today.month
    for _ in range(6):
        last_six_months.append((year_i, month_i))
        month_i -= 1
        if month_i == 0:
            month_i, year_i = 12, year_i - 1
    last_six_months.reverse()

    months = []
    student_counts = []
    landlord_counts = []

    for year_i, month_i in last_six_months:
        month_start = timezone.make_aware(datetime(year_i, month_i, 1))
        if month_i == 12:
            next_month_start = timezone.make_aware(datetime(year_i + 1, 1, 1))
        else:
            next_month_start = timezone.make_aware(datetime(year_i, month_i + 1, 1))
        months.append(month_start.strftime('%b'))

        # Count students for this month
        student_count = User.objects.filter(
            role=User.Role.STUDENT,
            date_joined__gte=month_start,
            date_joined__lt=next_month_start
        ).count()
        student_counts.append(student_count)

        # Count landlords for this month
        landlord_count = User.objects.filter(
            role=User.Role.LANDLORD,
            date_joined__gte=month_start,
            date_joined__lt=next_month_start
        ).count()
        landlord_counts.append(landlord_count)
    
    # Boarding house status distribution (real occupancy data):
    #   Available  = approved+active with at least one bookable room
    #   Full       = approved+active where every room is at capacity
    #   Unavailable= everything else (inactive/rejected/pending or no rooms)
    rooms_prefetch = Prefetch(
        'rooms',
        queryset=Room.objects.filter(is_active=True).annotate(
            confirmed_bookings=Count('bookings', filter=Q(bookings__status=Booking.Status.CONFIRMED))
        ),
    )
    active_houses = (
        BoardingHouse.objects.filter(
            status=BoardingHouse.Status.APPROVED,
            is_active=True,
        )
        .prefetch_related(rooms_prefetch)
    )
    available_bh = 0
    full_bh = 0
    for house in active_houses:
        open_rooms = [
            room for room in house.rooms.all()
            if room.is_available and room.capacity > room.confirmed_bookings
        ]
        if open_rooms:
            available_bh += 1
        elif house.rooms.all():
            full_bh += 1
    unavailable_bh = total_boarding_houses - available_bh - full_bh

    # Recent activity: a merged feed of inquiries, confirmed bookings and new
    # accounts instead of only the latest inquiries.
    activities = []
    for inquiry in Inquiry.objects.select_related('student', 'room__boarding_house').order_by('-created_at')[:6]:
        activities.append({
            'description': f'New inquiry from {inquiry.student.full_name or inquiry.student.email}',
            'details': inquiry.subject or inquiry.room.boarding_house.name,
            'timestamp': inquiry.created_at,
        })
    for booking in Booking.objects.select_related('student', 'room__boarding_house').filter(
        status=Booking.Status.CONFIRMED,
    ).order_by('-confirmed_at')[:4]:
        activities.append({
            'description': f'{booking.student.full_name or booking.student.email} was accepted into {booking.room.room_type}',
            'details': booking.room.boarding_house.name,
            'timestamp': booking.confirmed_at or booking.requested_at,
        })
    for user in User.objects.order_by('-date_joined')[:4]:
        activities.append({
            'description': f'New {user.role} account registered',
            'details': user.display_name or user.email,
            'timestamp': user.date_joined,
        })
    recent_activities = sorted(
        activities, key=lambda activity: activity['timestamp'], reverse=True,
    )[:8]

    context = {
        'total_students': total_students,
        'total_landlords': total_landlords,
        'total_boarding_houses': total_boarding_houses,
        'total_inquiries': total_inquiries,
        'total_bookings': total_bookings,
        'chart_labels': months,
        'student_data': student_counts,
        'landlord_data': landlord_counts,
        'status_data': [available_bh, full_bh, max(0, unavailable_bh)],
        'recent_activities': recent_activities,
    }

    return render(request, 'core/admin_analytics.html', context)


@login_required
@user_passes_test(admin_required)
def admin_create_landlord(request):
    from django.core.mail import send_mail
    from django.conf import settings

    if request.method == 'POST':
        form = LandlordCreateForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = User.Role.LANDLORD
            # Password chosen by the admin (set by UserCreationForm.save)
            password = form.cleaned_data['password1']
            user.save()
            from .models import log_admin_action
            log_admin_action(request.user, 'landlord_created', user)

            # Best-effort email notification (console backend locally).
            # Never email the plaintext password; the admin hands it over
            # via the confirmation screen instead.
            try:
                send_mail(
                    'Your BHIMS Account Credentials',
                    (
                        f'Your BHIMS landlord account has been created.\n\n'
                        f'Login email: {user.email}\n'
                        f'Landlord ID: {user.landlord_id}\n\n'
                        'The site administrator will provide your password through a '
                        'secure channel. Please change your password after first login.'
                    ),
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=True,
                )
            except Exception:
                pass

            return render(request, 'core/landlord_confirmation.html', {
                'landlord_name': user.full_name,
                'landlord_email': user.email,
                'landlord_password': password,
                'landlord_id': user.landlord_id,
                'credentials': [
                    ('Full Name', user.full_name),
                    ('Landlord ID', user.landlord_id),
                    ('Login Email', user.email),
                    ('Temporary Password', password),
                ],
            })
    else:
        form = LandlordCreateForm()

    return render(request, 'core/landlord_create.html', {'form': form})


@login_required
@user_passes_test(admin_required)
def admin_reports(request):
    status = request.GET.get('status', '')
    reports = UserReport.objects.select_related('reporter', 'reported_user').all()
    if status in ('pending', 'resolved', 'dismissed'):
        reports = reports.filter(status=status)
    pending_count = UserReport.objects.filter(status=UserReport.Status.PENDING).count()
    return render(request, 'core/admin_reports.html', {
        'reports': reports,
        'status': status,
        'pending_count': pending_count,
    })


@login_required
@user_passes_test(admin_required)
def admin_report_detail(request, pk):
    report = get_object_or_404(
        UserReport.objects.select_related('reporter', 'reported_user'), pk=pk
    )
    return render(request, 'core/admin_report_detail.html', {'report': report})


@login_required
@user_passes_test(admin_required)
@require_POST
def admin_report_update(request, pk):
    report = get_object_or_404(UserReport, pk=pk)
    action = request.POST.get('action')
    if action in ('resolve', 'dismiss'):
        report.status = (
            UserReport.Status.RESOLVED if action == 'resolve' else UserReport.Status.DISMISSED
        )
        report.resolved_at = timezone.now()
        report.save(update_fields=['status', 'resolved_at'])
        from .models import log_admin_action
        log_admin_action(request.user, f'report_{report.status}', report)
        messages.success(request, f'Report #{report.pk} marked as {report.status}.')
    return redirect('admin_reports')


@login_required
@user_passes_test(admin_required)
def admin_landlord_list(request):
    landlords = User.objects.filter(role=User.Role.LANDLORD).order_by('-date_joined')
    search = request.GET.get('search', '').strip()
    if search:
        landlords = landlords.filter(
            Q(full_name__icontains=search)
            | Q(username__icontains=search)
            | Q(email__icontains=search)
            | Q(phone_number__icontains=search)
        )
    paginator = Paginator(landlords.annotate(
        avg_rating=Avg('landlord_ratings_received__rating'),
        rating_total=Count('landlord_ratings_received'),
    ).order_by('-date_joined'), 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'core/admin_landlord_list.html', {'landlords': page_obj, 'page_obj': page_obj})


@login_required
@user_passes_test(admin_required)
def admin_landlord_detail(request, pk):
    landlord = get_object_or_404(User, pk=pk, role=User.Role.LANDLORD)
    houses = BoardingHouse.objects.filter(owner=landlord)
    ratings = landlord.landlord_ratings_received.select_related('student', 'booking__room__boarding_house')
    return render(request, 'core/admin_landlord_detail.html', {
        'landlord': landlord,
        'houses': houses,
        'ratings': ratings,
        'average_rating': ratings.aggregate(Avg('rating'))['rating__avg'],
        'rating_count': ratings.count(),
    })


@login_required
@user_passes_test(admin_required)
def admin_edit_landlord(request, pk):
    # Use canonical User model (only active schema)
    landlord = get_object_or_404(User, pk=pk, role=User.Role.LANDLORD)
    if request.method == 'POST':
        form = LandlordEditForm(request.POST, instance=landlord)
        if form.is_valid():
            form.save()
            from .models import log_admin_action
            log_admin_action(request.user, 'landlord_edited', landlord)
            messages.success(request, 'Landlord updated successfully!')
            return redirect('admin_landlord_detail', pk=landlord.pk)
    else:
        form = LandlordEditForm(instance=landlord)
    return render(request, 'core/landlord_edit.html', {'form': form, 'landlord': landlord})


@login_required
@user_passes_test(admin_required)
@require_POST
def toggle_landlord_active(request, pk):
    landlord = get_object_or_404(User, pk=pk, role=User.Role.LANDLORD)
    landlord.is_active = not landlord.is_active
    landlord.save()
    status = 'activated' if landlord.is_active else 'deactivated'
    from .models import log_admin_action
    log_admin_action(request.user, f'landlord_{status}', landlord)
    messages.success(request, f'Landlord account {status} successfully!')
    return redirect('admin_landlord_list')


@login_required
@user_passes_test(admin_required)
@require_POST
def admin_delete_landlord(request, pk):
    landlord = get_object_or_404(User, pk=pk, role=User.Role.LANDLORD)
    if landlord.pk == request.user.pk:
        messages.error(request, 'You cannot delete your own account.')
        return redirect('admin_landlord_list')
    name = landlord.full_name or landlord.username
    from .models import log_admin_action
    log_admin_action(request.user, 'landlord_deleted', landlord)
    landlord.delete()
    messages.success(request, f'Landlord "{name}" deleted successfully!')
    return redirect('admin_landlord_list')


@login_required
@user_passes_test(admin_required)
def admin_student_list(request):
    students = User.objects.filter(role=User.Role.STUDENT).order_by('-date_joined')
    search = request.GET.get('search', '').strip()
    if search:
        students = students.filter(
            Q(full_name__icontains=search)
            | Q(username__icontains=search)
            | Q(email__icontains=search)
            | Q(student_id__icontains=search)
        )
    paginator = Paginator(students.annotate(
        avg_rating=Avg('landlord_ratings_given__rating'),
        rating_total=Count('landlord_ratings_given'),
    ).order_by('-date_joined'), 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'core/admin_student_list.html', {'students': page_obj, 'page_obj': page_obj})


@login_required
@user_passes_test(admin_required)
@require_POST
def admin_delete_student(request, pk):
    student = get_object_or_404(User, pk=pk, role=User.Role.STUDENT)
    if student.pk == request.user.pk:
        messages.error(request, 'You cannot delete your own account.')
        return redirect('admin_student_list')
    name = student.full_name or student.username
    from .models import log_admin_action
    log_admin_action(request.user, 'student_deleted', student)
    student.delete()
    messages.success(request, f'Student "{name}" deleted successfully!')
    return redirect('admin_student_list')


@login_required
@user_passes_test(admin_required)
def admin_pending_listings(request):
    pending = (
        BoardingHouse.objects.filter(status=BoardingHouse.Status.PENDING)
        .select_related('owner')
        .annotate(total_rooms=Count('rooms'))
        .order_by('-id')
    )
    paginator = Paginator(pending, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    # Rejected listings stay reviewable: a landlord may fix the details and
    # resubmit, and the admin needs a way to approve one after the fact.
    rejected = (
        BoardingHouse.objects.filter(status=BoardingHouse.Status.REJECTED)
        .select_related('owner')
        .annotate(total_rooms=Count('rooms'))
        .order_by('-id')[:20]
    )
    return render(request, 'core/admin_pending_listings.html', {
        'page_obj': page_obj,
        'rejected': rejected,
    })


@login_required
@user_passes_test(admin_required)
@require_POST
def admin_approve_listing(request, pk):
    # Pending is the normal case; a rejected listing can be approved too
    # (after the landlord fixes and resubmits, or at the admin's discretion).
    house = get_object_or_404(
        BoardingHouse, pk=pk,
        status__in=[BoardingHouse.Status.PENDING, BoardingHouse.Status.REJECTED],
    )
    house.status = BoardingHouse.Status.APPROVED
    house.is_active = True
    house.save()
    from .models import log_admin_action
    log_admin_action(request.user, 'listing_approved', house)
    messages.success(request, f'"{house.name}" approved and is now visible to students.')
    return redirect('admin_pending_listings')


@login_required
@user_passes_test(admin_required)
@require_POST
def admin_reject_listing(request, pk):
    house = get_object_or_404(BoardingHouse, pk=pk, status=BoardingHouse.Status.PENDING)
    house.status = BoardingHouse.Status.REJECTED
    house.is_active = False
    house.save()
    from .models import log_admin_action
    log_admin_action(request.user, 'listing_rejected', house)
    messages.success(request, f'"{house.name}" rejected.')
    return redirect('admin_pending_listings')


@login_required
@user_passes_test(admin_required)
def admin_barangay_list(request):
    barangay_data = barangay_rows_with_counts()
    form = BarangayForm()
    add_error = False
    if request.method == 'POST':
        form = BarangayForm(request.POST)
        if form.is_valid():
            form.save()
            # The browse page is cached for logged-out visitors; without this
            # a new barangay stays missing from their filter until the cache
            # expires.
            invalidate_listing_caches()
            messages.success(request, 'Barangay added successfully!')
            return redirect('admin_barangay_list')
        # Invalid submit: fall through so the template reopens the Add
        # modal and shows the field errors instead of failing silently.
        add_error = True
    return render(request, 'core/admin_barangays.html', {
        'barangay_data': barangay_data,
        'form': form,
        'add_error': add_error,
        # Always present so the modal's inputs keep their prefixed ids
        # (no duplicate id= against the Add form).
        'edit_form': BarangayForm(auto_id='edit_%s'),
    })


@login_required
@user_passes_test(admin_required)
def admin_barangay_edit(request, pk):
    barangay = get_object_or_404(Barangay, pk=pk)
    if request.method == 'POST':
        form = BarangayForm(request.POST, instance=barangay)
        if form.is_valid():
            form.save()
            # A renamed barangay or a new distance label must reach the cached
            # browse filter at once, not on the next cache miss.
            invalidate_listing_caches()
            messages.success(request, 'Barangay updated successfully!')
            return redirect('admin_barangay_list')
        return render(request, 'core/admin_barangays.html', {
            'barangay_data': barangay_rows_with_counts(),
            'form': BarangayForm(),
            # Prefixed ids keep the hidden Add form's inputs from colliding
            # with the Edit form's (duplicate id= is invalid + breaks labels).
            'edit_form': BarangayForm(request.POST, instance=barangay, auto_id='edit_%s'),
            'editing_id': barangay.pk,
        })
    return redirect('admin_barangay_list')


@login_required
@user_passes_test(admin_required)
@require_POST
def admin_barangay_delete(request, pk):
    barangay = get_object_or_404(Barangay, pk=pk)
    name = barangay.name
    barangay.delete()
    invalidate_listing_caches()
    from .models import log_admin_action
    log_admin_action(request.user, 'barangay_deleted', barangay)
    messages.success(request, f'Barangay "{name}" removed.')
    return redirect('admin_barangay_list')


@login_required
@user_passes_test(admin_required)
def admin_settings(request):
    if request.method == 'POST':
        form = SystemSettingsForm(request.POST)
        if form.is_valid():
            form.save()
            from .models import log_admin_action
            log_admin_action(request.user, 'settings_updated', None)
            messages.success(request, 'Settings saved successfully!')
            return redirect('admin_settings')
    else:
        form = SystemSettingsForm(initial={
            'site_name': site_setting('site_name', 'BHIMS'),
            'tagline': site_setting('tagline', 'Your Home Away From Home, Near NLUC'),
            'support_email': site_setting('support_email', ''),
            'student_registration_enabled': student_access_enabled(),
        })
    return render(request, 'core/admin_settings.html', {'form': form})


# =========================================================================
# Profile, Search, Chat, Listing Detail
# =========================================================================

@login_required
def profile(request):
    """User profile with tabs for activity, bookings, inquiries, properties."""
    activities = []
    # Build activity feed from recent actions
    for booking in request.user.bookings.order_by('-requested_at')[:5]:
        activities.append({
            'icon': 'calendar-check',
            'description': f'Booked <strong>{booking.room.boarding_house.name}</strong> (Room: {booking.room.name})',
            'created_at': booking.requested_at,
        })
    for inquiry in request.user.inquiries.order_by('-created_at')[:5]:
        activities.append({
            'icon': 'envelope',
            'description': f'Inquired about <strong>{inquiry.room.boarding_house.name}</strong>',
            'created_at': inquiry.created_at,
        })
    activities.sort(key=lambda x: x['created_at'], reverse=True)

    # Profile edit form
    if request.user.role == 'student':
        form = StudentProfileUpdateForm(instance=request.user)
    else:
        form = LandlordProfileUpdateForm(instance=request.user)

    return render(request, 'core/profile.html', {
        'activities': activities,
        'profile': request.user,
        'profile_user': request.user,
        'is_instructor': request.user.role == 'landlord',
        'is_own_profile': True,
        'form': form,
    })


@login_required
def edit_profile(request):
    """Edit user profile."""
    if request.method == 'POST':
        if _throttle_generic(request, scope='edit-profile'):
            messages.error(request, 'Too many requests. Please wait a minute.')
            return redirect('profile')
        form = StudentProfileUpdateForm(request.POST, instance=request.user) if request.user.role == 'student' else LandlordProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            from .models import log_admin_action
            log_admin_action(request.user, 'profile_updated', request.user)
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
    else:
        form = StudentProfileUpdateForm(instance=request.user) if request.user.role == 'student' else LandlordProfileUpdateForm(instance=request.user)
    return render(request, 'core/edit_profile.html', {'form': form})


@login_required
def update_avatar(request):
    """Update user avatar — returns JSON for AJAX requests."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)
    if _throttle_generic(request, scope='avatar'):
        return JsonResponse({'success': False, 'message': 'Too many requests. Slow down.'}, status=429)

    form = LandlordProfilePictureForm(request.POST, request.FILES, instance=request.user)
    if form.is_valid():
        form.save()
        from .models import log_admin_action
        log_admin_action(request.user, 'avatar_updated', request.user)
        return JsonResponse({
            'success': True,
            'message': 'Profile picture updated.',
            'image_url': request.user.profile_picture.url if request.user.profile_picture else '',
        })
    return JsonResponse({'success': False, 'message': 'Could not process image.'}, status=400)


def search_results(request):
    """Search listings with filters - supports AJAX for instant filtering."""
    # Base queryset. Explicitly ordered BEFORE pagination: an unordered
    # queryset lets the database return a different order per page, so a
    # visitor paging through results could meet one listing twice and miss
    # another entirely. The filter form re-orders when it applies a sort; the
    # unfiltered fallback needs a stable order of its own.
    qs = visible_listings().order_by('-id')

    # The same admin-maintained list as the browse page: no barangay appears
    # in this filter unless an admin added it under Edit Barangays.
    barangay_options = barangay_filter_choices()
    barangays = [name for name, _label in barangay_options]
    all_amenities = Amenity.objects.all()

    form = ListingFilterForm(request.GET)
    form.fields['barangay'].choices = [('', 'All')] + barangay_options
    for field in ['price_min', 'price_max', 'room_type', 'amenities', 'sort', 'barangay']:
        form.fields[field].widget.attrs['class'] = 'form-control' if field != 'sort' else 'form-select'

    room_filter = None
    # The search page's amenity list is a set of checkboxes, so it arrives as
    # repeated parameters — getlist, not a single value — and carries names
    # rather than ids.
    selected_amenities = [a for a in request.GET.getlist('amenities') if a.strip()]
    if form.is_valid():
        cleaned = form.cleaned_data
        typed_amenities = [s.strip() for s in (cleaned.get('amenities') or '').split(',') if s.strip()]
        amenity_ids = _amenity_ids_from_names(selected_amenities + typed_amenities)
        # A filter naming amenities nobody has must match nothing, not everything.
        if (selected_amenities or typed_amenities) and not amenity_ids:
            qs = qs.none()
        else:
            qs, room_filter = _apply_listing_filters(qs, cleaned, amenity_ids)

    # Page the queryset FIRST, then decorate only the rows that will be shown:
    # a 30-house catalogue costs the same as a 12-house one.
    paginator = Paginator(qs, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    # Decorate the page's own objects: search_results.html iterates `listings`
    # (the Page), so the price/availability numbers must live on those rows.
    page_obj.object_list = decorate_house_cards(
        page_obj.object_list, room_filter=room_filter,
    )
    houses = page_obj.object_list

    # Build query string for pagination links
    query_params = request.GET.copy()
    query_params.pop('page', None)
    query_string = '&' + query_params.urlencode() if query_params else ''

    # AJAX fragment response
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'core/includes/search_grid_fragment.html', {
            'listings': houses,
        })

    return render(request, 'core/search_results.html', {
        'listings': page_obj,
        'houses': houses,
        'barangays': barangays,
        'all_amenities': all_amenities,
        'selected_amenities': selected_amenities,
        'form': form,
        'query_string': query_string,
    })


@login_required
def chat_list(request):
    """Removed: real-time messaging lives inside inquiry threads."""
    return redirect('home')


def health_check(request):
    """Liveness endpoint: answers 200 without touching the database, so
    monitors can confirm the process is up without giving attackers a DB
    reconnaissance tool. The deep DB check (?deep=1) is staff-only."""
    from django.http import JsonResponse
    import django.db
    if request.GET.get('deep'):
        if not request.user.is_staff:
            return JsonResponse({'detail': 'Not found.'}, status=404)
        try:
            with django.db.connection.cursor() as cur:
                cur.execute('SELECT 1')
            db_ok = True
        except Exception:
            db_ok = False
        status = 200 if db_ok else 503
        return JsonResponse({'status': 'ok' if db_ok else 'db-unreachable', 'db': db_ok}, status=status)
    return JsonResponse({'status': 'ok'})


@login_required
@user_passes_test(admin_required)
def admin_ratings(request):
    """Admin overview of every landlord rating students have submitted."""
    ratings = LandlordRating.objects.select_related(
        'student', 'landlord', 'booking__room__boarding_house'
    )

    stars = (request.GET.get('stars') or '').strip()
    if stars in {'1', '2', '3', '4', '5'}:
        ratings = ratings.filter(rating=int(stars))

    search = (request.GET.get('search') or '').strip()
    if search:
        ratings = ratings.filter(
            Q(student__full_name__icontains=search)
            | Q(student__username__icontains=search)
            | Q(landlord__full_name__icontains=search)
            | Q(landlord__username__icontains=search)
            | Q(booking__room__boarding_house__name__icontains=search)
            | Q(comment__icontains=search)
        )

    stats_base = LandlordRating.objects.all()
    average_rating = stats_base.aggregate(Avg('rating'))['rating__avg']
    rating_count = stats_base.count()
    distribution = {s: stats_base.filter(rating=s).count() for s in range(5, 0, -1)}
    comment_count = stats_base.exclude(comment='').count()

    paginator = Paginator(ratings.order_by('-created_at'), 12)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'core/admin_ratings.html', {
        'ratings': page_obj,
        'page_obj': page_obj,
        'average_rating': average_rating,
        'rating_count': rating_count,
        'distribution': distribution,
        'comment_count': comment_count,
        'low_count': distribution[2] + distribution[1],
        'stars': stars,
        'search': search,
    })


@login_required
@user_passes_test(landlord_required)
def landlord_my_ratings(request):
    """Ratings students have given the signed-in landlord."""
    ratings = request.user.landlord_ratings_received.select_related(
        'student', 'booking__room__boarding_house'
    )

    # Summary stats cover ALL of this landlord's ratings, regardless of filter.
    average_rating = ratings.aggregate(Avg('rating'))['rating__avg']
    rating_count = ratings.count()
    distribution = {s: ratings.filter(rating=s).count() for s in range(5, 0, -1)}
    comment_count = ratings.exclude(comment='').count()

    stars = (request.GET.get('stars') or '').strip()
    if stars in {'1', '2', '3', '4', '5'}:
        ratings = ratings.filter(rating=int(stars))

    paginator = Paginator(ratings.order_by('-created_at'), 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'core/landlord_my_ratings.html', {
        'ratings': page_obj,
        'page_obj': page_obj,
        'average_rating': average_rating,
        'rating_count': rating_count,
        'distribution': distribution,
        'stars': stars,
    })


def listing_detail(request, pk):
    """Public listing detail page (alias for boarding_detail)."""
    return boarding_detail(request, pk)