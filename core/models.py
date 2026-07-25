from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


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
        OTHER = 'OTHER', _('Other')

    email = models.EmailField(_('email address'), unique=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)
    full_name = models.CharField(max_length=255, blank=True)
    student_id = models.CharField(max_length=20, blank=True, null=True, unique=True)
    program = models.CharField(max_length=10, blank=True, choices=Program.choices)
    phone_number = models.CharField(max_length=30, blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    bio = models.TextField(max_length=300, blank=True, null=True)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    objects = UserManager()

    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'

    def __str__(self):
        return self.email or self.username


class BoardingHouse(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='boarding_houses')
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    barangay = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Room(models.Model):
    boarding_house = models.ForeignKey(BoardingHouse, on_delete=models.CASCADE, related_name='rooms')
    room_type = models.CharField(max_length=100)
    monthly_rate = models.DecimalField(max_digits=10, decimal_places=2)
    capacity = models.PositiveIntegerField(default=1)
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


class Amenity(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class RoomPhoto(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField(upload_to='room_photos/')

    def __str__(self):
        return f'Photo for {self.room}'


class Inquiry(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        OPEN = 'open', _('Open')
        CLOSED = 'closed', _('Closed')

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='inquiries')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='inquiries')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    subject = models.CharField(max_length=255, blank=True)
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
