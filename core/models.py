from decimal import Decimal
import secrets

from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.signals import post_save, post_delete
from django.utils.translation import gettext_lazy as _

MAX_IMAGE_MB = 5


def validate_image_size(image):
    """Keep user uploads sane: Pillow parses the file, but nothing capped its size."""
    if image and getattr(image, 'size', 0) > MAX_IMAGE_MB * 1024 * 1024:
        raise ValidationError(f'Image must be {MAX_IMAGE_MB} MB or smaller.')


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
        upload_to='profile_pictures/',
        blank=True,
        null=True,
        validators=[validate_image_size],
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
    description = models.TextField(blank=True, help_text='Optional. Up to 500 words.')
    image = models.ImageField(
        upload_to='boarding_images/',
        blank=True,
        null=True,
        verbose_name='Photo',
        validators=[validate_image_size],
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
        # Barangay row changes.
        return barangay_display_map().get(self.barangay, self.barangay)

    @property
    def image_ok(self):
        return bool(self.image and self.image.storage.exists(self.image.name))

    def get_photo_list(self):
        photos = []
        if self.image and self.image.storage.exists(self.image.name):
            photos.append(self.image.url)
        for room in self.rooms.all():
            for photo in room.photos.all():
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
    def photo_ok(self):
        photo = self.photos.first()
        return bool(photo and photo.image.storage.exists(photo.image.name))

    @property
    def occupied_count(self):
        return Booking.objects.filter(
            room=self,
            status=Booking.Status.CONFIRMED,
        ).count()

    @property
    def is_full(self):
        return self.occupied_count >= self.capacity

    def has_space(self):
        return self.is_active and self.is_available and not self.is_full


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
                b.name: b.display_name for b in Barangay.objects.all()
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
    image = models.ImageField(upload_to='room_photos/', validators=[validate_image_size])

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
    message_text = models.TextField()
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
    message_text = models.TextField()
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


class SiteSetting(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Site setting'
        verbose_name_plural = 'Site settings'

    def __str__(self):
        return f'{self.key}: {self.value}'


def site_setting(key, default=''):
    """Read a SiteSetting value, falling back to a default if unset."""
    try:
        obj = SiteSetting.objects.get(key=key)
        return obj.value if obj.value != '' else default
    except SiteSetting.DoesNotExist:
        return default


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