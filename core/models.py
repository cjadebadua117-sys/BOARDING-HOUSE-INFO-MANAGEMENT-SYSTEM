from decimal import Decimal
import secrets

from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import DatabaseError, models
from django.db.models.signals import post_save, post_delete
from django.utils.translation import gettext_lazy as _

MAX_IMAGE_MB = 5


def validate_image_size(image):
    """Keep user uploads sane: Pillow parses the file, but nothing capped its size."""
    if image and getattr(image, 'size', 0) > MAX_IMAGE_MB * 1024 * 1024:
        raise ValidationError(f'Image must be {MAX_IMAGE_MB} MB or smaller.')


def _upload_image_to(folder, instance, filename):
    """IGNORES the user's filename entirely (it could hide path tricks or
    leak private info) and stores the file as <folder>/<random hex>.<ext>.
    Collision-proof, path-traversal-proof, and migration-serializable via
    functools.partial."""
    import os
    import uuid
    ext = os.path.splitext(filename)[1].lower()[:8]
    if ext not in {'.jpg', '.jpeg', '.png', '.webp', '.gif'}:
        ext = '.jpg'
    return f'{folder}/{uuid.uuid4().hex}{ext}'


def _generated_image_path(folder):
    from functools import partial
    return partial(_upload_image_to, folder)


def validate_image_file(image):
    """Server-side content check (JS checks are advisory only): the file must
    actually decode as a real JPEG/PNG/WebP/GIF via Pillow, not just carry an
    image extension — blocks polyglot / renamed-non-image uploads."""
    if not image:
        return
    try:
        from PIL import Image
        image.seek(0)
        with Image.open(image) as img:
            fmt = img.format
        image.seek(0)
    except Exception:
        raise ValidationError('Upload a valid JPEG, PNG, WebP, or GIF image.')
    if fmt not in {'JPEG', 'PNG', 'WEBP', 'GIF'}:
        raise ValidationError('Upload a valid JPEG, PNG, WebP, or GIF image.')


MAX_MESSAGE_CHARS = 2000

# Barangays near DMMMSU NLUC used as the source of truth for the landlord
# barangay dropdown and as a fallback if the Barangay table is not yet populated.
# The full official list (47 barangays) is managed by admins via Edit Barangays.
BACNOTAN_BARANGAYS = [
    'Arosip', 'Cabaroan', 'Casiaman', 'Salincob', 'Sapilang', 'Say-oan',
]

# Distance of each fixed barangay from DMMMSU NLUC campus.
BARANGAY_DISTANCES = {
    'Arosip': '2.5 km',
    'Cabaroan': '5.6 km',
    'Casiaman': '1.5 km',
    'Salincob': '3.2 km',
    'Sapilang': 'Walking distance',
    'Say-oan': '4.5 km',
}


def canonical_barangay_name(name):
    """Return the spelling the admin's barangay table uses for `name`.

    A boarding house stores its barangay as plain text, so "Poblacion" and
    the admin's "poblacion" are the same barangay to a student (the filters
    match case-insensitively) but two different strings to code that compares
    them exactly — which is how the admin table reported 0 active listings for
    a barangay the student page could fill with houses. New writes go through
    here so a listing keeps the admin's spelling instead of creating its own
    variant.
    """
    if not name:
        return name
    wanted = name.strip().casefold()
    try:
        for candidate in Barangay.objects.values_list('name', flat=True):
            if candidate.strip().casefold() == wanted:
                return candidate
    except DatabaseError:
        # Table not ready (e.g. during first migrate) — keep what was given.
        pass
    return name



class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.Role.ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = 'student', _('Student')
        LANDLORD = 'landlord', _('Landlord')
        ADMIN = 'admin', _('Admin')

    class Program(models.TextChoices):
        CE = 'CE', _('College of Education')
        CA = 'CA', _('College of Agriculture')
        CAS = 'CAS', _('College of Arts and Sciences')
        CVM = 'CVM', _('College of Veterinary Medicine')
        CAFF = 'CAFF', _('College of Agroforestry & Forestry')
        IABM = 'IABM', _('Institute of Agribusiness Management')
        CIS = 'CIS', _('College of Information Systems')
        IES = 'IES', _('Institute of Environmental Studies')
        IABE = 'IABE', _('Institute of Agricultural & Biosystems Engineering')
        K12 = 'K12', _('K-12 / Senior High School')

    email = models.EmailField(_('email address'), unique=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)
    full_name = models.CharField(max_length=255, blank=True)
    student_id = models.CharField(max_length=20, blank=True, null=True, unique=True)
    landlord_id = models.CharField(max_length=11, blank=True, null=True, unique=True)
    program = models.CharField(max_length=10, blank=True, choices=Program.choices)
    program_custom = models.CharField(
        max_length=100, blank=True,
        help_text=_('Free text for the grade level when Program is "K-12".')
    )
    phone_number = models.CharField(max_length=30, blank=True, null=True)
    last_seen_inquiries = models.DateTimeField(
        blank=True,
        null=True,
        help_text=_('When the landlord last opened their inquiry list; newer inquiries show a NEW chip.')
    )
    profile_picture = models.ImageField(
        upload_to=_generated_image_path('profile_pictures'),
        blank=True,
        null=True,
        validators=[validate_image_size, validate_image_file],
    )
    bio = models.TextField(max_length=300, blank=True, null=True)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    objects = UserManager()

    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'

    def __str__(self):
        return self.email or self.username

    @property
    def display_name(self):
        return self.full_name or self.get_full_name().strip() or self.username

    @staticmethod
    def generate_unique_landlord_id():
        """Return an unused landlord ID in the format xxx-xxxx-xx (digits only)."""
        while True:
            candidate = (
                f"{secrets.randbelow(900) + 100:03d}-"
                f"{secrets.randbelow(10000):04d}-"
                f"{secrets.randbelow(100):02d}"
            )
            if not User.objects.filter(landlord_id=candidate).exists():
                return candidate

    def save(self, *args, **kwargs):
        if self.role == self.Role.LANDLORD and not self.landlord_id:
            self.landlord_id = self.generate_unique_landlord_id()
        super().save(*args, **kwargs)


class BoardingHouse(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        APPROVED = 'approved', _('Approved')
        REJECTED = 'rejected', _('Rejected')

    class GenderAllowed(models.TextChoices):
        MALE = 'male', _('Male Only')
        FEMALE = 'female', _('Female Only')
        BOTH = 'both', _('Both (Male & Female)')

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='boarding_houses')
    name = models.CharField(max_length=255, verbose_name='Name of the boarding house')
    address = models.CharField(max_length=255, verbose_name='Location')
    barangay = models.CharField(max_length=255)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Price (₱ per month)',
    )
    gender_allowed = models.CharField(
        max_length=10,
        choices=GenderAllowed.choices,
        default=GenderAllowed.BOTH,
        verbose_name='Gender allowed',
    )
    description = models.TextField(blank=True, max_length=5000, help_text='Optional. Up to 500 words.')
    image = models.ImageField(
        upload_to=_generated_image_path('boarding_images'),
        blank=True,
        null=True,
        verbose_name='Photo',
        validators=[validate_image_size, validate_image_file],
    )
    is_active = models.BooleanField(default=True)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    @property
    def barangay_display(self):
        # Cached map lookup instead of one query per house per render (N+1
        # when listing pages render dozens of cards). Invalidated whenever a
        # Barangay row changes. The key is case-folded because a listing may
        # hold "Poblacion" while the admin table holds "poblacion"; the exact
        # lookup used to drop the distance label that every other house gets.
        key = (self.barangay or '').strip().casefold()
        return barangay_display_map().get(key, self.barangay)

    @property
    def image_ok(self):
        return bool(self.image and self.image.storage.exists(self.image.name))

    def get_photo_list(self):
        """Every displayable photo for this house, house photo first.

        One query for all room photos. The old version walked `rooms` and each
        room's `photos`, which cost one query per room on a page that is
        otherwise fully prefetched.
        """
        photos = []
        if self.image and self.image.storage.exists(self.image.name):
            photos.append(self.image.url)
        room_photos = (
            RoomPhoto.objects.filter(room__boarding_house=self)
            .order_by('room_id', 'id')
        )
        for photo in room_photos:
            if photo.image.storage.exists(photo.image.name):
                photos.append(photo.image.url)
        return photos

    def __str__(self):
        return self.name


class Room(models.Model):
    boarding_house = models.ForeignKey(BoardingHouse, on_delete=models.CASCADE, related_name='rooms')
    room_type = models.CharField(max_length=255, blank=True)
    monthly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    capacity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    is_available = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    amenities = models.ManyToManyField('Amenity', blank=True, related_name='rooms')

    def __str__(self):
        return f'{self.boarding_house.name} - {self.room_type}'

    @property
    def price(self):
        return self.monthly_rate

    @property
    def name(self):
        return self.room_type

    @property
    def primary_photo(self):
        """First photo of this room whose file actually exists on disk.

        Iterates `self.photos.all()` on purpose: `.first()` and `.last()`
        deliberately bypass Django's prefetch cache and fire a fresh query per
        room, so using them inside a room loop cost one query per room even
        when `photos` had been prefetched.
        """
        for photo in self.photos.all():
            if photo.image and photo.image.storage.exists(photo.image.name):
                return photo
        return None

    @property
    def photo_ok(self):
        return self.primary_photo is not None

    @property
    def occupied_count(self):
        """Confirmed bookings for this room.

        If the queryset was built with annotate_room_bookings() the count is
        already attached, so rendering a page of rooms costs ONE query
        instead of one COUNT per room (this used to be the single biggest
        source of query fan-out: a 12-room listing page ran 54 queries).
        """
        annotated = self.__dict__.get('confirmed_bookings')
        if annotated is not None:
            return annotated
        return Booking.objects.filter(
            room=self,
            status=Booking.Status.CONFIRMED,
        ).count()

    @property
    def is_full(self):
        return self.occupied_count >= self.capacity

    def has_space(self):
        return self.is_active and self.is_available and not self.is_full


def annotate_room_bookings(queryset):
    """Attach `confirmed_bookings` to every room in one extra query.

    Every caller that loops over rooms must use this, otherwise each room
    triggers its own COUNT (and each card on the browse page its own query).
    """
    from django.db.models import Count, Q as _Q
    return queryset.annotate(
        confirmed_bookings=Count(
            'bookings', filter=_Q(bookings__status=Booking.Status.CONFIRMED),
        ),
    )


class Amenity(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Barangay(models.Model):
    name = models.CharField(max_length=100, unique=True)
    distance_from_campus = models.CharField(
        max_length=50,
        blank=True,
        default='',
        verbose_name='Distance from DMMMSU NLUC campus',
    )

    class Meta:
        ordering = ['name']

    @property
    def display_name(self):
        if self.distance_from_campus:
            return f'{self.name} ({self.distance_from_campus})'
        return self.name

    def __str__(self):
        return self.display_name


# ---- Barangay display cache (avoids per-house queries on listing pages) ----
_barangay_display_cache = None


def barangay_display_map():
    global _barangay_display_cache
    if _barangay_display_cache is None:
        try:
            # display_name is a Python property, so it must be evaluated
            # per-object (values_list would raise FieldError).
            _barangay_display_cache = {
                b.name.strip().casefold(): b.display_name
                for b in Barangay.objects.all()
            }
        except Exception:
            # Table not ready (e.g. during first migrate) — fall back to raw names.
            return {}
    return _barangay_display_cache


def _reset_barangay_cache(*args, **kwargs):
    global _barangay_display_cache
    _barangay_display_cache = None


post_save.connect(_reset_barangay_cache, sender=Barangay)
post_delete.connect(_reset_barangay_cache, sender=Barangay)


class RoomPhoto(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField(
        upload_to=_generated_image_path('room_photos'),
        validators=[validate_image_size, validate_image_file],
    )

    def __str__(self):
        return f'Photo for {self.room}'


class Inquiry(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        OPEN = 'open', _('Open')
        CLOSED = 'closed', _('Closed')
        REJECTED = 'rejected', _('Rejected')

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='inquiries')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='inquiries')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    subject = models.CharField(max_length=255, blank=True)
    last_viewed_by_landlord = models.DateTimeField(
        blank=True, null=True,
        help_text=_('When the landlord last opened this inquiry thread.')
    )
    last_viewed_by_student = models.DateTimeField(
        blank=True, null=True,
        help_text=_('When the student last opened this inquiry thread.')
    )
    message_text = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.subject or f'Inquiry #{self.pk}'

    @property
    def user(self):
        return self.student

    @property
    def message(self):
        return self.message_text

    @property
    def last_activity(self):
        """Time of the latest thread activity: last reply, or when created."""
        last = self.messages.last()
        return last.sent_at if last else self.created_at


class InquiryMessage(models.Model):
    inquiry = models.ForeignKey(Inquiry, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    message_text = models.TextField(max_length=2000)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sent_at']

    def __str__(self):
        return f'Message from {self.sender} on {self.sent_at}'

    @property
    def message(self):
        return self.message_text


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        CONFIRMED = 'confirmed', _('Confirmed')
        DECLINED = 'declined', _('Declined')
        CANCELLED = 'cancelled', _('Cancelled')

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookings')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='bookings')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    requested_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(blank=True, null=True)
    move_in_date = models.DateField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-requested_at']

    def __str__(self):
        return f'Booking #{self.pk or "new"} for {self.student}'


class LandlordRating(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='landlord_ratings_given',
    )
    landlord = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='landlord_ratings_received',
    )
    # Optional: a decision to decline leaves the student with no booking, but
    # they may still rate the landlord once the inquiry has been settled either
    # way (accepted -> a confirmed booking, declined -> no booking).
    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name='landlord_rating',
        blank=True,
        null=True,
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField(blank=True, max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'landlord'],
                name='unique_student_landlord_rating',
            ),
        ]

    def __str__(self):
        return f'{self.student} rated {self.landlord} ({self.rating}/5)'


class AdminActionLog(models.Model):
    """Audit trail for staff actions (approve/reject/delete/toggle).
    Written on every admin mutation so disputes and report handling can be
    traced back to who did what, and when."""
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='admin_actions',
    )
    action = models.CharField(max_length=64)
    target_model = models.CharField(max_length=64)
    target_id = models.CharField(max_length=64, blank=True)
    target_repr = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.actor} {self.action} {self.target_model}#{self.target_id}'


def log_admin_action(actor, action, target):
    """Fire-and-forget audit helper (never let logging break the request)."""
    try:
        AdminActionLog.objects.create(
            actor=actor,
            action=action,
            target_model=type(target).__name__,
            target_id=str(getattr(target, 'pk', '') or ''),
            target_repr=str(target)[:255],
        )
    except Exception:
        pass


class SiteSetting(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Site setting'
        verbose_name_plural = 'Site settings'

    def __str__(self):
        return f'{self.key}: {self.value}'


# Cache keys for the two public listing pages (they are cached for a few
# seconds each to absorb traffic spikes).
LANDING_CACHE_KEY = 'landing-page-v1'
LISTING_CACHE_KEY = 'listing-list-anon-v1'


def site_setting(key, default=''):
    """Read a SiteSetting value, falling back to a default if unset."""
    try:
        obj = SiteSetting.objects.get(key=key)
        return obj.value if obj.value != '' else default
    except SiteSetting.DoesNotExist:
        return default


def student_access_enabled():
    """Whether students may use the portal at all.

    The switch is labelled "Allow student registration" and its key is
    `student_registration_enabled`, but an admin who turns it off means the
    student side is closed: new accounts cannot be created AND existing
    students cannot sign in. Reading it through one helper keeps the signup
    route, both login views, the templates and the session guard agreeing.
    A database that is not ready yet falls back to the historical default
    (open) rather than breaking every request.
    """
    try:
        return site_setting('student_registration_enabled', '1') == '1'
    except Exception:
        return True


class UserReport(models.Model):
    class Reason(models.TextChoices):
        HARASSMENT = 'harassment', _('Harassment or Abuse')
        SCAM = 'scam', _('Scam or Fraud')
        FAKE_LISTING = 'fake_listing', _('Fake Listing')
        INAPPROPRIATE = 'inappropriate', _('Inappropriate Behavior')
        OTHER = 'other', _('Other')

    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        RESOLVED = 'resolved', _('Resolved')
        DISMISSED = 'dismissed', _('Dismissed')

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reports_filed',
    )
    reported_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reports_received',
    )
    reason = models.CharField(max_length=20, choices=Reason.choices)
    details = models.TextField(blank=True, max_length=1000)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Report #{self.pk}: {self.reporter} -> {self.reported_user} ({self.reason})'

# ---------------------------------------------------------------------------
# Listing cache invalidation
#
# The landing page and the anonymous browse page are cached for a few seconds
# to survive traffic spikes. Without invalidation, a listing the admin just
# approved (or a room a landlord just booked out) stays invisible/stale until
# the timer runs out -- a wrong-output bug that only appears under load, when
# the cache is actually warm.
#
# Wired as signals rather than sprinkled through views so that no future
# mutation path can forget to clear them.
# ---------------------------------------------------------------------------
def _invalidate_listing_caches(*args, **kwargs):
    from django.core.cache import cache
    try:
        cache.delete(LANDING_CACHE_KEY)
        cache.delete(LISTING_CACHE_KEY)
    except Exception:
        # A cache backend problem must never break a write.
        pass


for _sender in (BoardingHouse, Room, Booking):
    post_save.connect(_invalidate_listing_caches, sender=_sender)
    post_delete.connect(_invalidate_listing_caches, sender=_sender)
