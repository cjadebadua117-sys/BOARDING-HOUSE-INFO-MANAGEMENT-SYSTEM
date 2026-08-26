from django import forms as django_forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Booking, BoardingHouse, Inquiry, InquiryMessage, Room, Amenity, Barangay, RoomPhoto, User, SiteSetting


@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'value')
    search_fields = ('key', 'value')
    ordering = ('key',)


@admin.register(Barangay)
class BarangayAdmin(admin.ModelAdmin):
    list_display = ('name', 'distance_from_campus')
    search_fields = ('name',)
    ordering = ('name',)


class BoardingHouseAdminForm(django_forms.ModelForm):
    class Meta:
        model = BoardingHouse
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [(b.name, b.display_name) for b in Barangay.objects.all()]
        current = self.instance.barangay if self.instance and self.instance.pk else ''
        if current and current not in [c[0] for c in choices]:
            choices.append((current, current))
        self.fields['barangay'].widget = django_forms.Select(choices=choices)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('email', 'full_name', 'student_id', 'program', 'phone_number', 'profile_picture', 'bio')}),
        ('Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'role'),
        }),
    )
    list_display = ('username', 'email', 'full_name', 'role', 'is_active', 'is_staff')
    search_fields = ('username', 'email', 'full_name')
    ordering = ('username',)
    list_filter = ('role', 'is_active', 'is_staff')


@admin.register(BoardingHouse)
class BoardingHouseAdmin(admin.ModelAdmin):
    form = BoardingHouseAdminForm
    list_display = ('name', 'owner', 'barangay', 'address', 'is_active')
    search_fields = ('name', 'address', 'barangay', 'owner__email')
    list_filter = ('is_active', 'barangay')


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('room_type', 'boarding_house', 'monthly_rate', 'capacity', 'is_available', 'is_active')
    search_fields = ('room_type', 'boarding_house__name')
    list_filter = ('is_available', 'is_active', 'boarding_house')


@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(RoomPhoto)
class RoomPhotoAdmin(admin.ModelAdmin):
    list_display = ('room', 'image')
    search_fields = ('room__room_type',)


@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ('student', 'room', 'status', 'created_at')
    search_fields = ('student__email', 'room__room_type', 'message_text')
    list_filter = ('status', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(InquiryMessage)
class InquiryMessageAdmin(admin.ModelAdmin):
    list_display = ('inquiry', 'sender', 'sent_at')
    search_fields = ('inquiry__message_text', 'sender__email')
    readonly_fields = ('sent_at',)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('student', 'room', 'status', 'requested_at', 'confirmed_at')
    search_fields = ('student__email', 'room__room_type')
    list_filter = ('status', 'requested_at', 'confirmed_at')
    readonly_fields = ('requested_at',)
