from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


# 1. tbl_accounts (corresponds to User model)
class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        username = extra_fields.get('username') or email
        extra_fields['username'] = username
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
            raise ValueError('Superuser must have is_staff=True.')

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    # tbl_accounts
    class Role(models.TextChoices):
        STUDENT = 'Student', _('Student')
        LANDLORD = 'Landlord', _('Landlord')
        ADMIN = 'Admin', _('Admin')

    class Status(models.TextChoices):
        ACTIVE = 'Active', _('Active')
        INACTIVE = 'Inactive', _('Inactive')

    # AccountID (PK, INT, AI) - Django automatically creates id field
    # Username (VARCHAR, UNIQUE) - AbstractUser provides username
    # Password (VARCHAR, hashed) - AbstractUser provides password
    # Email (VARCHAR, UNIQUE) - AbstractUser provides email
    role = models.CharField(_('role'), max_length=12, choices=Role.choices, default=Role.STUDENT, db_index=True)
    status = models.CharField(_('status'), max_length=10, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    DateCreated = models.DateTimeField(auto_now_add=True)  # DateCreated (DATETIME)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    objects = UserManager()

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = self.email
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'tbl_accounts'  # Exact table name as requested
        indexes = [
            models.Index(fields=['role', 'status']),
            models.Index(fields=['email']),
        ]

    def __str__(self):
        return self.username


# 2. tbl_students
class Student(models.Model):
    # StudentID (PK, INT, AI)
    StudentID = models.AutoField(primary_key=True)
    # AccountID (FK → tbl_accounts)
    AccountID = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='student_profile',
        limit_choices_to={'role': User.Role.STUDENT},
        db_index=True
    )
    # FullName (VARCHAR)
    FullName = models.CharField(max_length=255)
    # Course - matches your request
    Course = models.CharField(max_length=100)
    # YearLevel (INT)
    YearLevel = models.PositiveSmallIntegerField()
    # ContactNumber (VARCHAR)
    ContactNumber = models.CharField(max_length=30)
    # Address (VARCHAR)
    Address = models.TextField()
    # IsDeleted (BOOLEAN, default 0)
    IsDeleted = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = 'tbl_students'

    def __str__(self):
        return f"{self.FullName} - {self.Course}"


# 3. tbl_landlords
class Landlord(models.Model):
    # LandlordID (PK, INT, AI)
    LandlordID = models.AutoField(primary_key=True)
    # AccountID (FK → tbl_accounts)
    AccountID = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='landlord_profile',
        limit_choices_to={'role': User.Role.LANDLORD},
        db_index=True
    )
    # FullName (VARCHAR)
    FullName = models.CharField(max_length=255)
    # ContactNumber (VARCHAR)
    ContactNumber = models.CharField(max_length=30)
    # Address (VARCHAR)
    Address = models.TextField()
    # VerifiedStatus (ENUM: 'Verified','Pending','Rejected')
    class VerifiedStatus(models.TextChoices):
        VERIFIED = 'Verified', _('Verified')
        PENDING = 'Pending', _('Pending')
        REJECTED = 'Rejected', _('Rejected')
    VerifiedStatus = models.CharField(max_length=10, choices=VerifiedStatus.choices, default=VerifiedStatus.PENDING, db_index=True)
    # IsDeleted (BOOLEAN, default 0)
    IsDeleted = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = 'tbl_landlords'

    def __str__(self):
        return self.FullName


# 4. tbl_boardinghouses
class BoardingHouse(models.Model):
    # BoardingHouseID (PK, INT, AI)
    BoardingHouseID = models.AutoField(primary_key=True)
    # LandlordID (FK → tbl_landlords)
    LandlordID = models.ForeignKey(
        'Landlord',
        on_delete=models.PROTECT,
        related_name='boarding_houses',
        db_index=True
    )
    # HouseName (VARCHAR)
    HouseName = models.CharField(max_length=180, db_index=True)
    # Barangay (must be: sapilang, casiaman, salincob, cabaroan)
    class BarangayChoices(models.TextChoices):
        SAPILANG = 'sapilang', _('Sapilang')
        CASIAMAN = 'casiaman', _('Casiaman')
        SALINCOB = 'salincob', _('Salincob')
        CABAROAN = 'cabaroan', _('Cabaroan')
    Barangay = models.CharField(max_length=20, choices=BarangayChoices.choices, db_index=True)
    # Address (VARCHAR)
    Address = models.CharField(max_length=255)
    # MonthlyRate (DECIMAL(8,2))
    MonthlyRate = models.DecimalField(max_digits=8, decimal_places=2)
    # Capacity (INT)
    Capacity = models.PositiveIntegerField()
    # AvailableSlots (INT)
    AvailableSlots = models.PositiveIntegerField()
    # Amenities (TEXT)
    Amenities = models.TextField(blank=True)
    # Curfew (VARCHAR)
    Curfew = models.CharField(max_length=50, blank=True)
    # Status (ENUM: 'Available','Full','Unavailable')
    class Status(models.TextChoices):
        AVAILABLE = 'Available', _('Available')
        FULL = 'Full', _('Full')
        UNAVAILABLE = 'Unavailable', _('Unavailable')
    Status = models.CharField(max_length=15, choices=Status.choices, default=Status.UNAVAILABLE, db_index=True)
    # IsDeleted (BOOLEAN, default 0)
    IsDeleted = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = 'tbl_boardinghouses'
        ordering = ['-BoardingHouseID']

    def __str__(self):
        return self.HouseName


# 7. tbl_boardinghouse_images (comes after tbl_boardinghouses)
class BoardingHouseImage(models.Model):
    # ImageID (PK, INT, AI)
    ImageID = models.AutoField(primary_key=True)
    # BoardingHouseID (FK → tbl_boardinghouses)
    BoardingHouseID = models.ForeignKey(
        'BoardingHouse',
        on_delete=models.CASCADE,
        related_name='images',
        db_index=True
    )
    # ImagePath (VARCHAR) — file path/filename stored on server
    ImagePath = models.CharField(max_length=255)
    # IsPrimary (BOOLEAN, default 0) — marks the "cover photo"
    IsPrimary = models.BooleanField(default=False, db_index=True)
    # DateUploaded (DATETIME)
    DateUploaded = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tbl_boardinghouse_images'

    def __str__(self):
        return f"Image {self.ImageID} for {self.BoardingHouseID.HouseName}"


# 5. tbl_bookings
class Booking(models.Model):
    # BookingID (PK, INT, AI)
    BookingID = models.AutoField(primary_key=True)
    # StudentID (FK → tbl_students)
    StudentID = models.ForeignKey(
        'Student',
        on_delete=models.PROTECT,
        related_name='bookings',
        db_index=True
    )
    # BoardingHouseID (FK → tbl_boardinghouses)
    BoardingHouseID = models.ForeignKey(
        'BoardingHouse',
        on_delete=models.PROTECT,
        related_name='bookings',
        db_index=True
    )
    # DateStart (DATE)
    DateStart = models.DateField()
    # DateEnd (DATE)
    DateEnd = models.DateField()
    # Status (ENUM: 'Pending','Approved','Rejected','Ended')
    class Status(models.TextChoices):
        PENDING = 'Pending', _('Pending')
        APPROVED = 'Approved', _('Approved')
        REJECTED = 'Rejected', _('Rejected')
        ENDED = 'Ended', _('Ended')
    Status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING, db_index=True)
    # IsDeleted (BOOLEAN, default 0)
    IsDeleted = models.BooleanField(default=False, db_index=True)
    # DateCreated (DATETIME)
    DateCreated = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tbl_bookings'
        ordering = ['-DateCreated']

    def __str__(self):
        return f"Booking {self.BookingID} - {self.StudentID.FullName}"


# 6. tbl_adminlogs
class AdminLog(models.Model):
    # LogID (PK, INT, AI)
    LogID = models.AutoField(primary_key=True)
    # AccountID (FK → tbl_accounts, the admin who acted)
    AccountID = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='admin_logs',
        limit_choices_to={'role': User.Role.ADMIN},
        db_index=True
    )
    # ActionType (ENUM: 'VerifyLandlord','RejectLandlord','ApproveListing','RejectListing','Other')
    class ActionType(models.TextChoices):
        VERIFY_LANDLORD = 'VerifyLandlord', _('Verify Landlord')
        REJECT_LANDLORD = 'RejectLandlord', _('Reject Landlord')
        APPROVE_LISTING = 'ApproveListing', _('Approve Listing')
        REJECT_LISTING = 'RejectListing', _('Reject Listing')
        OTHER = 'Other', _('Other')
    ActionType = models.CharField(max_length=20, choices=ActionType.choices.choices, db_index=True)
    # TargetTable (VARCHAR)
    TargetTable = models.CharField(max_length=50)
    # TargetID (INT)
    TargetID = models.IntegerField()
    # Remarks (TEXT)
    Remarks = models.TextField(blank=True)
    # DateLogged (DATETIME)
    DateLogged = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tbl_adminlogs'
        ordering = ['-DateLogged']

    def __str__(self):
        return f"{self.ActionType} - {self.TargetTable}#{self.TargetID}"