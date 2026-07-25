import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.db import DatabaseError
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.core.exceptions import ValidationError
from django.http import JsonResponse

from .forms import (
    BoardingHouseForm,
    StudentRegistrationForm,
    StudentProfileEditForm,
    LandlordCreateForm,
    LandlordEditForm,
    InquiryMessageForm,
    ListingFilterForm
)
from .forms import (
    StudentProfileUpdateForm,
    LandlordProfilePictureForm,
    BHIMSPasswordChangeForm,
)
from .models import BoardingHouse, User, Room, Inquiry, InquiryMessage, Amenity


def admin_required(user):
    return user.is_authenticated and user.role == User.Role.ADMIN


def landlord_required(user):
    return user.is_authenticated and user.role == User.Role.LANDLORD


def student_required(user):
    return user.is_authenticated and user.role == User.Role.STUDENT


# Public views
def home(request):
    listings = BoardingHouse.objects.all().order_by('-id')[:6]
    return render(request, 'core/landing.html', {'listings': listings})


def listing_list(request):
    try:
        houses = BoardingHouse.objects.all().order_by('-id')
        # Force a simple DB access now so we can catch missing tables before template rendering.
        houses.exists()
    except DatabaseError:
        # DB tables might not exist yet (migrations not applied). Return empty queryset and skip DB lookups.
        houses = BoardingHouse.objects.none()
    
    # Get distinct room types and barangays for filter dropdowns when fields exist
    def has_field(model, name):
        return any(f.name == name for f in model._meta.get_fields())

    room_types = []
    barangays = []
    try:
        if has_field(Room, 'room_type'):
            room_types = Room.objects.values_list('room_type', flat=True).distinct()
    except Exception:
        room_types = []
    try:
        if has_field(BoardingHouse, 'barangay'):
            barangays = list(BoardingHouse.objects.values_list('barangay', flat=True).distinct())
        else:
            # Default barangays when model/DB doesn't provide them
            barangays = ['CABAROAN', 'SAYOAN', 'CASIAMAN', 'SAPILANG']
    except Exception:
        barangays = ['CABAROAN', 'SAYOAN', 'CASIAMAN', 'SAPILANG']

    form = ListingFilterForm(request.GET)
    form.fields['room_type'].choices = [('', 'Any')] + [(rt, rt) for rt in room_types]
    form.fields['barangay'].choices = [('', 'Any')] + [(b, b) for b in barangays]

    if form.is_valid():
        price_min = form.cleaned_data.get('price_min')
        price_max = form.cleaned_data.get('price_max')
        room_type = form.cleaned_data.get('room_type')
        amenities_text = form.cleaned_data.get('amenities')
        barangay = form.cleaned_data.get('barangay')
        sort = form.cleaned_data.get('sort')

        if price_min:
            houses = houses.filter(rooms__price__gte=price_min)
        if price_max:
            houses = houses.filter(rooms__price__lte=price_max)
        if room_type and has_field(Room, 'room_type'):
            houses = houses.filter(rooms__room_type=room_type)
        if amenities_text and has_field(Room, 'amenities'):
            amenity_names = [s.strip() for s in amenities_text.split(',') if s.strip()]
            try:
                amenity_ids = list(
                    Amenity.objects.filter(
                        name__in=amenity_names
                    ).values_list('id', flat=True)
                )
            except DatabaseError:
                amenity_ids = []
            if amenity_ids:
                houses = houses.filter(rooms__amenities__in=amenity_ids)
            else:
                houses = houses.none()
        if barangay and has_field(BoardingHouse, 'barangay'):
            houses = houses.filter(barangay=barangay)
        
        if sort == 'lowest_price':
            houses = houses.order_by('rooms__price')
        elif sort == 'newest':
            houses = houses.order_by('-id')

    return render(request, 'core/boardings_list.html', {
        'houses': houses.distinct(),
        'boarding_houses': houses.distinct(),
        'form': form
    })


def boarding_detail(request, pk):
    house = get_object_or_404(BoardingHouse, pk=pk)
    rooms = house.rooms.all()
    return render(request, 'core/boarding_detail.html', {'house': house, 'rooms': rooms})


# Authentication views
def student_register(request):
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = User.Role.STUDENT
            user.save()
            login(request, user)
            messages.success(request, 'Student account created successfully!')
            return redirect('listing_list')
    else:
        form = StudentRegistrationForm()
    return render(request, 'core/student_register.html', {'form': form})


def landlord_register(request):
    if request.method == 'POST':
        form = LandlordCreateForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = User.Role.LANDLORD
            user.save()
            login(request, user)
            messages.success(request, 'Landlord account created successfully! Awaiting verification.')
            return redirect('landlord_dashboard')
    else:
        form = LandlordCreateForm()
    return render(request, 'core/landlord_create.html', {'form': form})


def student_login(request):
    from django.contrib.auth.forms import AuthenticationForm
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me')
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_active and user.role == User.Role.STUDENT:
            login(request, user)
            if remember_me:
                request.session.set_expiry(1209600)
            return redirect('student_profile')
        else:
            messages.error(request, 'Invalid credentials or account disabled.')
    return render(request, 'core/student_login.html', {'form': form})


def landlord_login(request):
    from django.contrib.auth.forms import AuthenticationForm
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me')
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_active and user.role == User.Role.LANDLORD:
            login(request, user)
            if remember_me:
                request.session.set_expiry(1209600)
            return redirect('landlord_dashboard')
        else:
            messages.error(request, 'Invalid credentials or not an active landlord account.')
    return render(request, 'core/landlord_login.html', {'form': form})


def admin_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me')
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_active and user.role == User.Role.ADMIN:
            login(request, user)
            if remember_me:
                request.session.set_expiry(1209600)
            return redirect('admin_dashboard')
        else:
            messages.error(request, 'Invalid credentials or not an admin account.')
    else:
        from django.contrib.auth.forms import AuthenticationForm
        form = AuthenticationForm()
    return render(request, 'core/admin_login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('home')


# Student views
@login_required
@user_passes_test(student_required)
def student_profile(request):
    if request.method == 'POST':
        form = StudentProfileEditForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('student_profile')
    else:
        form = StudentProfileEditForm(instance=request.user)
    return render(request, 'core/student_profile.html', {'form': form})


@login_required
def profile_view(request):
    user = request.user
    context = {
        'is_landlord': user.role == 'landlord',
        'is_student': user.role == 'student',
    }
    if user.role == 'landlord':
        # related_name on BoardingHouse is 'boarding_houses'
        context['boarding_house_count'] = user.boarding_houses.filter(is_active=True).count()
    return render(request, 'core/profile.html', context)


@login_required
def update_profile(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)

    user = request.user
    if user.role != 'student':
        return JsonResponse({
            'success': False,
            'message': 'Only students can edit profile details. Landlords must contact Admin to update account info.'
        }, status=403)

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({'success': False, 'message': 'Invalid data received.'}, status=400)

    form = StudentProfileUpdateForm(payload, instance=user)
    if form.is_valid():
        form.save()
        return JsonResponse({
            'success': True,
            'message': 'Profile updated successfully.',
            'profile': {
                'first_name': user.first_name,
                'last_name': user.last_name,
                'program': user.get_program_display() if user.program else '',
                'phone_number': user.phone_number,
                'bio': user.bio,
            }
        })
    else:
        return JsonResponse({'success': False, 'message': 'Please correct the errors.', 'errors': form.errors}, status=400)


@login_required
def upload_profile_picture(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)

    form = LandlordProfilePictureForm(request.POST, request.FILES, instance=request.user)
    if form.is_valid():
        form.save()
        return JsonResponse({
            'success': True,
            'message': 'Profile picture updated.',
            'image_url': request.user.profile_picture.url if request.user.profile_picture else '',
        })
    return JsonResponse({'success': False, 'message': 'Could not process image.'}, status=400)


@login_required
def change_password(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({'success': False, 'message': 'Invalid data received.'}, status=400)

    form = BHIMSPasswordChangeForm(user=request.user, data=payload)
    if form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        return JsonResponse({'success': True, 'message': 'Password changed successfully.'})
    else:
        return JsonResponse({'success': False, 'message': 'Please correct the errors.', 'errors': form.errors}, status=400)


@login_required
@user_passes_test(student_required)
def student_inquiry_list(request):
    inquiries = Inquiry.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'core/student_inquiry_list.html', {'inquiries': inquiries})


# Landlord views
@login_required
@user_passes_test(landlord_required)
def landlord_dashboard(request):
    houses = BoardingHouse.objects.filter(owner=request.user)
    inquiries = Inquiry.objects.filter(room__boarding_house__owner=request.user).order_by('-created_at')
    return render(request, 'core/landlord_dashboard.html', {
        'houses': houses,
        'inquiries': inquiries,
        'landlord': request.user
    })


@login_required
@user_passes_test(landlord_required)
def landlord_boarding_house_list(request):
    houses = BoardingHouse.objects.filter(owner=request.user).order_by('-id')
    return render(request, 'core/landlord_boarding_house_list.html', {
        'houses': houses,
        'landlord': request.user
    })


@login_required
@user_passes_test(landlord_required)
def boarding_house_create(request):
    if request.method == 'POST':
        form = BoardingHouseForm(request.POST)
        if form.is_valid():
            house = form.save(commit=False)
            house.owner = request.user
            try:
                house.save()
                messages.success(request, 'Boarding house created!')
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
        form = BoardingHouseForm(request.POST, instance=house)
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
def landlord_boarding_house_detail(request, pk):
    house = get_object_or_404(BoardingHouse, pk=pk, owner=request.user)
    rooms = house.rooms.all()
    inquiries = Inquiry.objects.filter(room__boarding_house=house).order_by('-created_at')
    return render(request, 'core/landlord_boarding_house_detail.html', {
        'house': house,
        'rooms': rooms,
        'inquiries': inquiries
    })


@login_required
@user_passes_test(landlord_required)
def landlord_inquiry_list(request):
    inquiries = Inquiry.objects.filter(room__boarding_house__owner=request.user).order_by('-created_at')
    return render(request, 'core/landlord_inquiry_list.html', {'inquiries': inquiries})


# Admin views
@login_required
@user_passes_test(admin_required)
def admin_dashboard(request):
    total_students = User.objects.filter(role=User.Role.STUDENT, is_active=True).count()
    total_landlords = User.objects.filter(role=User.Role.LANDLORD, is_active=True).count()
    total_boarding_houses = BoardingHouse.objects.count()
    total_inquiries = Inquiry.objects.count()
    
    return render(request, 'core/admin_dashboard.html', {
        'total_students': total_students,
        'total_landlords': total_landlords,
        'total_boarding_houses': total_boarding_houses,
        'total_inquiries': total_inquiries
    })


@login_required
@user_passes_test(admin_required)
def admin_analytics(request):
    from django.db.models.functions import TruncMonth
    from datetime import datetime, timedelta

    # Basic analytics data
    total_students = User.objects.filter(role=User.Role.STUDENT, is_active=True).count()
    total_landlords = User.objects.filter(role=User.Role.LANDLORD, is_active=True).count()
    total_boarding_houses = BoardingHouse.objects.count()
    total_inquiries = Inquiry.objects.count()

    # Monthly registrations (last 6 months)
    six_months_ago = datetime.now() - timedelta(days=180)
    monthly_students = User.objects.filter(
        role=User.Role.STUDENT,
        date_joined__gte=six_months_ago
    ).annotate(
        month=TruncMonth('date_joined')
    ).values('month').annotate(
        count=Count('id')
    ).order_by('month')

    monthly_landlords = User.objects.filter(
        role=User.Role.LANDLORD,
        date_joined__gte=six_months_ago
    ).annotate(
        month=TruncMonth('date_joined')
    ).values('month').annotate(
        count=Count('id')
    ).order_by('month')

    context = {
        'total_students': total_students,
        'total_landlords': total_landlords,
        'total_boarding_houses': total_boarding_houses,
        'total_inquiries': total_inquiries,
        'monthly_students': list(monthly_students),
        'monthly_landlords': list(monthly_landlords),
    }

    return render(request, 'core/admin_analytics.html', context)


@login_required
@user_passes_test(admin_required)
def admin_landlord_list(request):
    landlords = User.objects.filter(role=User.Role.LANDLORD).order_by('-date_joined')
    return render(request, 'core/admin_landlord_list.html', {'landlords': landlords})


@login_required
@user_passes_test(admin_required)
def admin_landlord_detail(request, pk):
    landlord = get_object_or_404(User, pk=pk, role=User.Role.LANDLORD)
    houses = BoardingHouse.objects.filter(owner=landlord)
    return render(request, 'core/admin_landlord_detail.html', {'landlord': landlord, 'houses': houses})


@login_required
@user_passes_test(admin_required)
def admin_edit_landlord(request, pk):
    landlord = get_object_or_404(User, pk=pk, role=User.Role.LANDLORD)
    if request.method == 'POST':
        form = LandlordEditForm(request.POST, instance=landlord)
        if form.is_valid():
            form.save()
            messages.success(request, 'Landlord updated successfully!')
            return redirect('admin_landlord_detail', pk=landlord.pk)
    else:
        form = LandlordEditForm(instance=landlord)
    return render(request, 'core/landlord_edit.html', {'form': form, 'landlord': landlord})


@login_required
@user_passes_test(admin_required)
def toggle_landlord_active(request, pk):
    landlord = get_object_or_404(User, pk=pk, role=User.Role.LANDLORD)
    landlord.is_active = not landlord.is_active
    landlord.save()
    status = 'activated' if landlord.is_active else 'deactivated'
    messages.success(request, f'Landlord account {status} successfully!')
    return redirect('admin_landlord_list')