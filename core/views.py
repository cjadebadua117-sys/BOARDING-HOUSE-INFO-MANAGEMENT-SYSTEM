import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.db import DatabaseError, transaction
from django.db.models import Avg, Count, Min, Prefetch, Q
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
    MAX_MESSAGE_CHARS,
)


def visible_listings():
    """Boarding houses students are allowed to see: approved and active."""
    return BoardingHouse.objects.filter(
        status=BoardingHouse.Status.APPROVED,
        is_active=True,
    )


def decorate_house_cards(houses):
    """Attach min_price / available_rooms_count used by listing card templates."""
    houses = houses.distinct().annotate(
        min_price=Min('rooms__monthly_rate'),
    )

    # Prefetch rooms with their confirmed-booking counts so computing
    # availability needs a fixed number of queries instead of one per room.
    rooms_prefetch = Prefetch(
        'rooms',
        queryset=Room.objects.filter(is_active=True, is_available=True).annotate(
            confirmed_bookings=Count('bookings', filter=Q(bookings__status=Booking.Status.CONFIRMED))
        ),
    )
    houses = houses.prefetch_related(rooms_prefetch)

    decorated = []
    for house in houses:
        house.available_rooms_count = sum(
            1 for room in house.rooms.all()
            if room.capacity > room.confirmed_bookings
        )
        decorated.append(house)
    return decorated


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


def handler404(request, exception=None):
    return render(request, 'core/404.html', status=404)


def handler500(request):
    return render(request, 'core/500.html', status=500)


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

    listings = []
    try:
        listings = decorate_house_cards(visible_listings().order_by('-id'))[:6]
    except DatabaseError:
        # DB tables might not exist yet (migrations not applied).
        listings = []
    return render(request, 'core/landing.html', {'listings': listings})


def listing_list(request):
    try:
        houses = visible_listings().order_by('-id')
        # Force a simple DB access now so we can catch missing tables before template rendering.
        houses.exists()
    except DatabaseError:
        # DB tables might not exist yet (migrations not applied). Return empty queryset and skip DB lookups.
        houses = BoardingHouse.objects.none()
    
    barangays = []
    try:
        barangays = list(BoardingHouse.objects.values_list('barangay', flat=True).distinct())
    except Exception:
        barangays = []
    try:
        official = list(Barangay.objects.values_list('name', 'distance_from_campus'))
        if official:
            barangays = list(dict.fromkeys([o[0] for o in official] + barangays))
        official_distances = dict(official)
    except Exception:
        official_distances = {}

    form = ListingFilterForm(request.GET)
    form.fields['barangay'].choices = [('', 'Any')] + [
        (b, f'{b} ({official_distances[b]})' if official_distances.get(b) else b)
        for b in barangays
    ]
    # Style filter widgets with Bootstrap field classes
    form.fields['barangay'].widget.attrs['class'] = 'form-select'
    form.fields['sort'].widget.attrs['class'] = 'form-select'
    form.fields['price_min'].widget.attrs['class'] = 'form-control'
    form.fields['price_max'].widget.attrs['class'] = 'form-control'
    form.fields['amenities'].widget.attrs['class'] = 'form-control'

    if form.is_valid():
        price_min = form.cleaned_data.get('price_min')
        price_max = form.cleaned_data.get('price_max')
        room_type = form.cleaned_data.get('room_type')
        amenities_text = form.cleaned_data.get('amenities')
        barangay = form.cleaned_data.get('barangay')
        sort = form.cleaned_data.get('sort')

        if price_min:
            houses = houses.filter(rooms__monthly_rate__gte=price_min)
        if price_max:
            houses = houses.filter(rooms__monthly_rate__lte=price_max)
        if room_type:
            houses = houses.filter(rooms__room_type__icontains=room_type)
        if amenities_text:
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
        if barangay:
            houses = houses.filter(barangay=barangay)
        
        if sort == 'lowest_price':
            houses = houses.order_by('rooms__monthly_rate')
        elif sort == 'newest':
            houses = houses.order_by('-id')

    decorated_houses = decorate_house_cards(houses)

    # AJAX instant-filter: return only the grid fragment when requested via fetch.
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'core/includes/listing_grid_fragment.html', {
            'houses': decorated_houses,
        })

    # Keep full houses visible; the card template renders a "Full" badge
    return render(request, 'core/boardings_list.html', {
        'houses': decorated_houses,
        'boarding_houses': decorated_houses,
        'form': form
    })


def boarding_detail(request, pk):
    house = get_object_or_404(BoardingHouse, pk=pk)

    # Approved + active houses are visible to everyone. A house that is still
    # pending/rejected/inactive stays viewable to the landlord who owns it and
    # to any student who already has a confirmed booking for it (so the
    # "View Property" button in My Bookings always works).
    is_public = house.status == BoardingHouse.Status.APPROVED and house.is_active
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

    rooms = [room for room in house.rooms.prefetch_related('photos', 'amenities').all() if room.has_space()]
    return render(request, 'core/boarding_detail.html', {'house': house, 'rooms': rooms})


_ROLE_DASHBOARDS = {
    User.Role.STUDENT: 'student_dashboard',
    User.Role.LANDLORD: 'landlord_dashboard',
    User.Role.ADMIN: 'admin_dashboard',
}


def _dashboard_for(user):
    """Where an already-authenticated user belongs."""
    return _ROLE_DASHBOARDS.get(getattr(user, 'role', None), 'listing_list')


def _redirect_if_authenticated(request):
    """Login pages must never render for users who are already signed in."""
    if request.user.is_authenticated:
        return redirect(_safe_redirect_target(request.GET.get('next') or '') or _dashboard_for(request.user))
    return None


# Authentication views
def student_register(request):
    from django.contrib.auth.forms import AuthenticationForm
    next_url = request.POST.get('next') or request.GET.get('next') or ''
    if site_setting('student_registration_enabled', '1') != '1':
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
    })


def accounts_login(request):
    early = _redirect_if_authenticated(request)
    if early:
        return early
    from django.contrib.auth.forms import AuthenticationForm
    next_url = _safe_redirect_target(request.POST.get('next') or request.GET.get('next'))
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me')
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_active:
            login(request, user)
            if remember_me:
                request.session.set_expiry(1209600)
            role_dashboards = {
                User.Role.STUDENT: 'student_dashboard',
                User.Role.LANDLORD: 'landlord_dashboard',
                User.Role.ADMIN: 'admin_dashboard',
            }
            return redirect(next_url or role_dashboards.get(user.role, 'profile'))
        messages.error(request, 'Invalid credentials or account disabled.')
    # Failed sign-ups reopen the registration pane; failed logins stay put.
    initial_mode = 'signup' if (
        request.method == 'POST' and request.POST.get('password1') is not None
    ) else 'signin'
    return render(request, 'core/auth/login_student.html', {
        'form': form,
        'reg_form': StudentRegistrationForm(auto_id='reg_%s'),
        'next': next_url,
        'initial_mode': initial_mode,
        'login_heading': 'Sign in to BHIMS',
        'login_subtitle': 'Use your student, landlord or admin account to continue.',
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
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me')
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_active and user.role == User.Role.STUDENT:
            login(request, user)
            if remember_me:
                request.session.set_expiry(1209600)
            return redirect(next_url or 'student_dashboard')
        else:
            messages.error(request, 'Invalid credentials or account disabled.')
    initial_mode = 'signup' if (
        request.method == 'POST' and request.POST.get('password1') is not None
    ) else 'signin'
    return render(request, 'core/auth/login_student.html', {
        'form': form,
        'reg_form': StudentRegistrationForm(auto_id='reg_%s'),
        'next': next_url,
        'initial_mode': initial_mode,
    })


def landlord_login(request):
    early = _redirect_if_authenticated(request)
    if early:
        return early
    from django.contrib.auth.forms import AuthenticationForm
    next_url = _safe_redirect_target(request.POST.get('next') or request.GET.get('next'))
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
            return redirect(next_url or 'landlord_dashboard')
        else:
            messages.error(request, 'Invalid credentials or not an active landlord account.')
    return render(request, 'core/auth/login_landlord.html', {'form': form, 'next': next_url})


def admin_login(request):
    early = _redirect_if_authenticated(request)
    if early:
        return early
    from django.contrib.auth.forms import AuthenticationForm
    next_url = _safe_redirect_target(request.POST.get('next') or request.GET.get('next'))
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me')
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_active and user.role == User.Role.ADMIN:
            login(request, user)
            if remember_me:
                request.session.set_expiry(1209600)
            return redirect(next_url or 'admin_dashboard')
        else:
            messages.error(request, 'Invalid credentials or not an admin account.')
    return render(request, 'core/auth/login_admin.html', {'form': form, 'next': next_url})


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


@login_required
def update_profile(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)

    user = request.user
    if user.role not in ('student', 'landlord'):
        return JsonResponse({
            'success': False,
            'message': 'Admin accounts do not have a profile page.'
        }, status=403)

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({'success': False, 'message': 'Invalid data received.'}, status=400)

    if user.role == 'student':
        form = StudentProfileUpdateForm(payload, instance=user)
    else:
        form = LandlordProfileUpdateForm(payload, instance=user)
    if form.is_valid():
        form.save()
        return JsonResponse({
            'success': True,
            'message': 'Profile updated successfully.',
            'profile': {
                'first_name': user.first_name,
                'last_name': user.last_name,
                'full_name': user.full_name,
                'program': user.get_program_display() if user.program else '',
                'program_custom': user.program_custom or '',
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
def user_profile(request, pk):
    person = get_object_or_404(User, pk=pk)
    if person.role == User.Role.ADMIN:
        raise Http404('Profile not found.')

    viewer = request.user
    if person.role == 'landlord':
        houses = person.boarding_houses.filter(
            is_active=True, status=BoardingHouse.Status.APPROVED
        ).order_by('-id')
        ratings = person.landlord_ratings_received.select_related('student')
        eligible_booking = None
        can_rate = False
        has_rated = False
        if viewer.role == User.Role.STUDENT:
            has_rated = LandlordRating.objects.filter(
                student=viewer,
                landlord=person,
            ).exists()
            eligible_booking = Booking.objects.filter(
                student=viewer,
                status=Booking.Status.CONFIRMED,
                room__boarding_house__owner=person,
            ).select_related('room__boarding_house').first() if not has_rated else None
            can_rate = eligible_booking is not None
        return render(request, 'core/user_profile.html', {
            'person': person,
            'viewed_is_landlord': True,
            'houses': houses,
            'ratings': ratings,
            'average_rating': ratings.aggregate(Avg('rating'))['rating__avg'],
            'rating_count': ratings.count(),
            'can_rate': can_rate,
            'has_rated': has_rated,
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
        'viewed_is_landlord': False,
        'phone_visible': phone_visible,
    })


@login_required
@user_passes_test(student_required)
@require_POST
def rate_landlord(request, pk):
    landlord = get_object_or_404(User, pk=pk, role=User.Role.LANDLORD)
    if LandlordRating.objects.filter(student=request.user, landlord=landlord).exists():
        messages.info(request, 'You have already rated this landlord.')
        return redirect('user_profile', pk=landlord.pk)

    booking = Booking.objects.filter(
        student=request.user,
        status=Booking.Status.CONFIRMED,
        room__boarding_house__owner=landlord,
    ).select_related('room__boarding_house').first()
    if not booking:
        messages.error(request, 'You can rate a landlord only after a confirmed booking.')
        return redirect('user_profile', pk=landlord.pk)

    form = LandlordRatingForm(request.POST)
    if form.is_valid():
        rating = form.save(commit=False)
        rating.student = request.user
        rating.landlord = landlord
        rating.booking = booking
        rating.save()
        messages.success(request, 'Your rating has been submitted.')
    return redirect('user_profile', pk=landlord.pk)


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
    inquiries = Inquiry.objects.filter(student=request.user).select_related(
        'room', 'room__boarding_house'
    ).order_by('-created_at')
    return render(request, 'core/student_inquiry_list.html', {'inquiries': inquiries})


@login_required
@user_passes_test(student_required)
def student_bookings(request):
    bookings = Booking.objects.filter(student=request.user).order_by('-requested_at')
    return render(request, 'core/student_bookings.html', {'bookings': bookings})

@login_required
def inquiry_thread(request, pk):
    inquiry = get_object_or_404(Inquiry, pk=pk)
    # Check if user is authorized to view this inquiry
    if request.user != inquiry.student and request.user != inquiry.room.boarding_house.owner:
        messages.error(request, 'You are not authorized to view this inquiry.')
        return redirect('home')
    
    # Mark as viewed by landlord when they open the thread
    if request.user == inquiry.room.boarding_house.owner:
        inquiry.last_viewed_by_landlord = timezone.now()
        inquiry.save(update_fields=['last_viewed_by_landlord'])
    
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
            # Mark inquiry as open once a reply is sent (no longer "new")
            if inquiry.status == Inquiry.Status.PENDING:
                inquiry.status = Inquiry.Status.OPEN
                inquiry.save(update_fields=['status'])
            messages.success(request, 'Message sent successfully!')
            return redirect(request.path)
    
    accepted_booking = Booking.objects.filter(
        student=inquiry.student,
        room=inquiry.room,
        status=Booking.Status.CONFIRMED,
    ).first()

    return render(request, 'core/inquiry_thread.html', {
        'inquiry': inquiry,
        'accepted_booking': accepted_booking,
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
        room = Room.objects.select_for_update().get(pk=inquiry.room_id)

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
    # If the previous inquiry was rejected, let the student start fresh.
    existing = Inquiry.objects.filter(student=request.user, room=room).order_by('-created_at').first()
    if existing and existing.status == Inquiry.Status.REJECTED:
        existing.delete()
        existing = None

    if request.method == 'POST':
        message_text = (request.POST.get('message_text') or '').strip()
        if not message_text:
            messages.error(request, 'Please write a message before sending your inquiry.')
            bound = InquiryForm(request.POST)
            bound.is_valid()
            return render(request, 'core/send_inquiry.html', {'room': room, 'form': bound})
        if len(message_text) > MAX_MESSAGE_CHARS:
            messages.error(request, f'Messages are limited to {MAX_MESSAGE_CHARS} characters.')
            return render(request, 'core/send_inquiry.html', {'room': room, 'form': InquiryForm()})
        if existing:
            messages.info(request, 'You already have a conversation about this room.')
            return redirect('student_inquiry_thread', pk=existing.pk)
        inquiry = Inquiry.objects.create(
            student=request.user,
            room=room,
            subject=(request.POST.get('subject') or '').strip(),
            message_text=message_text,
        )
        messages.success(request, 'Your inquiry has been sent to the landlord!')
        return redirect('student_inquiry_thread', pk=inquiry.pk)

    # GET: never create anything — show the confirmation form instead.
    if existing:
        return redirect('student_inquiry_thread', pk=existing.pk)
    return render(request, 'core/send_inquiry.html', {
        'room': room,
        'form': InquiryForm(initial={'message_text': 'Hello! I would like to inquire about this room.'}),
    })


# Landlord views
@login_required
@user_passes_test(landlord_required)
def landlord_dashboard(request):
    houses = BoardingHouse.objects.filter(owner=request.user)
    inquiries = Inquiry.objects.filter(room__boarding_house__owner=request.user).order_by('-created_at')
    total_available_rooms = Room.objects.filter(boarding_house__owner=request.user, is_available=True).count()
    
    # Determine which inquiries have new messages
    new_inquiry_ids = set()
    for inq in inquiries[:5]:  # Only check the top 5 shown on dashboard
        if inq.status in [Inquiry.Status.CLOSED, Inquiry.Status.REJECTED]:
            continue
        latest_msg = inq.messages.order_by('-sent_at').first()
        if latest_msg and (inq.last_viewed_by_landlord is None or latest_msg.sent_at > inq.last_viewed_by_landlord):
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
    houses = BoardingHouse.objects.filter(owner=request.user).order_by('-id')
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
    return render(request, 'core/room_form.html', {'form': form, 'house': house})

@login_required
@user_passes_test(landlord_required)
def room_edit(request, pk):
    room = get_object_or_404(Room, pk=pk, boarding_house__owner=request.user)
    if request.method == 'POST':
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
    return render(request, 'core/room_form.html', {'form': form, 'room': room, 'house': room.boarding_house})

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
    rooms = house.rooms.all()
    inquiries = Inquiry.objects.filter(room__boarding_house=house).order_by('-created_at')
    return render(request, 'core/landlord_boarding_house_detail.html', {
        'house': house,
        'rooms': rooms,
        'inquiries': inquiries,
        'available_count': sum(1 for room in rooms if room.has_space()),
        'occupied_count': sum(room.occupied_count for room in rooms),
    })


@login_required
@user_passes_test(landlord_required)
def landlord_inquiry_list(request):
    inquiries = Inquiry.objects.filter(
        room__boarding_house__owner=request.user
    ).order_by('-created_at')
    
    # Determine which inquiries have new messages since landlord last viewed
    new_inquiry_ids = set()
    for inq in inquiries:
        if inq.status in [Inquiry.Status.CLOSED, Inquiry.Status.REJECTED]:
            continue
        latest_msg = inq.messages.order_by('-sent_at').first()
        if latest_msg and (inq.last_viewed_by_landlord is None or latest_msg.sent_at > inq.last_viewed_by_landlord):
            new_inquiry_ids.add(inq.pk)
    
    return render(request, 'core/landlord_inquiry_list.html', {
        'inquiries': inquiries,
        'new_inquiry_ids': new_inquiry_ids,
    })


@login_required
@user_passes_test(landlord_required)
def landlord_bookings(request):
    bookings = Booking.objects.filter(room__boarding_house__owner=request.user).order_by('-requested_at')
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
    paginator = Paginator(landlords, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'core/admin_landlord_list.html', {'landlords': page_obj, 'page_obj': page_obj})


@login_required
@user_passes_test(admin_required)
def admin_landlord_detail(request, pk):
    landlord = get_object_or_404(User, pk=pk, role=User.Role.LANDLORD)
    houses = BoardingHouse.objects.filter(owner=landlord)
    return render(request, 'core/admin_landlord_detail.html', {'landlord': landlord, 'houses': houses})


@login_required
@user_passes_test(admin_required)
def admin_edit_landlord(request, pk):
    # Use canonical User model (only active schema)
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
@require_POST
def toggle_landlord_active(request, pk):
    landlord = get_object_or_404(User, pk=pk, role=User.Role.LANDLORD)
    landlord.is_active = not landlord.is_active
    landlord.save()
    status = 'activated' if landlord.is_active else 'deactivated'
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
    paginator = Paginator(students, 10)
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
    student.delete()
    messages.success(request, f'Student "{name}" deleted successfully!')
    return redirect('admin_student_list')


@login_required
@user_passes_test(admin_required)
def admin_pending_listings(request):
    pending = (
        BoardingHouse.objects.filter(status=BoardingHouse.Status.PENDING)
        .select_related('owner')
        .order_by('-id')
    )
    paginator = Paginator(pending, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'core/admin_pending_listings.html', {'page_obj': page_obj})


@login_required
@user_passes_test(admin_required)
@require_POST
def admin_approve_listing(request, pk):
    house = get_object_or_404(BoardingHouse, pk=pk, status=BoardingHouse.Status.PENDING)
    house.status = BoardingHouse.Status.APPROVED
    house.is_active = True
    house.save()
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
    messages.success(request, f'"{house.name}" rejected.')
    return redirect('admin_pending_listings')


@login_required
@user_passes_test(admin_required)
def admin_barangay_list(request):
    barangays = Barangay.objects.all()
    barangay_counts = {
        row['barangay']: row['count']
        for row in BoardingHouse.objects.filter(status=BoardingHouse.Status.APPROVED)
        .values('barangay')
        .annotate(count=Count('barangay'))
    }
    barangay_data = [(b, barangay_counts.get(b.name, 0)) for b in barangays]
    form = BarangayForm()
    add_error = False
    if request.method == 'POST':
        form = BarangayForm(request.POST)
        if form.is_valid():
            form.save()
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
            messages.success(request, 'Barangay updated successfully!')
            return redirect('admin_barangay_list')
        barangays = Barangay.objects.all()
        barangay_counts = {
            row['barangay']: row['count']
            for row in BoardingHouse.objects.filter(status=BoardingHouse.Status.APPROVED)
            .values('barangay')
            .annotate(count=Count('barangay'))
        }
        return render(request, 'core/admin_barangays.html', {
            'barangay_data': [(b, barangay_counts.get(b.name, 0)) for b in barangays],
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
    barangay.delete()
    messages.success(request, f'Barangay "{barangay.name}" removed.')
    return redirect('admin_barangay_list')


@login_required
@user_passes_test(admin_required)
def admin_settings(request):
    if request.method == 'POST':
        form = SystemSettingsForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Settings saved successfully!')
            return redirect('admin_settings')
    else:
        form = SystemSettingsForm(initial={
            'site_name': site_setting('site_name', 'BHIMS'),
            'tagline': site_setting('tagline', 'Your Home Away From Home, Near NLUC'),
            'support_email': site_setting('support_email', ''),
            'student_registration_enabled': site_setting('student_registration_enabled', '1') == '1',
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
    for booking in request.user.bookings.order_by('-created_at')[:5]:
        activities.append({
            'icon': 'calendar-check',
            'description': f'Booked <strong>{booking.room.boarding_house.name}</strong> (Room: {booking.room.name})',
            'created_at': booking.created_at,
        })
    for inquiry in request.user.inquiries.order_by('-created_at')[:5]:
        activities.append({
            'icon': 'envelope',
            'description': f'Inquired about <strong>{inquiry.room.boarding_house.name}</strong>',
            'created_at': inquiry.created_at,
        })
    activities.sort(key=lambda x: x['created_at'], reverse=True)

    return render(request, 'core/profile.html', {
        'activities': activities,
    })


@login_required
def edit_profile(request):
    """Edit user profile."""
    if request.method == 'POST':
        form = StudentProfileUpdateForm(request.POST, instance=request.user) if request.user.role == 'student' else LandlordProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
    else:
        form = StudentProfileUpdateForm(instance=request.user) if request.user.role == 'student' else LandlordProfileUpdateForm(instance=request.user)
    return render(request, 'core/edit_profile.html', {'form': form})


@login_required
def update_avatar(request):
    """Update user avatar."""
    if request.method == 'POST':
        form = LandlordProfilePictureForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Avatar updated!')
    return redirect('profile')


def search_results(request):
    """Search listings with filters - supports AJAX for instant filtering."""
    # Base queryset
    qs = BoardingHouse.objects.filter(status=BoardingHouse.Status.APPROVED, is_active=True)

    barangays = []
    try:
        barangays = list(qs.values_list('barangay', flat=True).distinct())
    except Exception:
        pass
    try:
        official = list(Barangay.objects.values_list('name', 'distance_from_campus'))
        if official:
            barangays = list(dict.fromkeys([o[0] for o in official] + barangays))
    except Exception:
        pass
    all_amenities = Amenity.objects.all()

    form = ListingFilterForm(request.GET)
    form.fields['barangay'].choices = [('', 'All')] + [(b, b) for b in barangays]
    for field in ['price_min', 'price_max', 'room_type', 'amenities', 'sort', 'barangay']:
        form.fields[field].widget.attrs['class'] = 'form-control' if field != 'sort' else 'form-select'

    if form.is_valid():
        price_min = form.cleaned_data.get('price_min')
        price_max = form.cleaned_data.get('price_max')
        room_type = form.cleaned_data.get('room_type')
        amenities_text = form.cleaned_data.get('amenities')
        barangay = form.cleaned_data.get('barangay')
        sort = form.cleaned_data.get('sort')

        if price_min:
            qs = qs.filter(rooms__monthly_rate__gte=price_min)
        if price_max:
            qs = qs.filter(rooms__monthly_rate__lte=price_max)
        if room_type:
            qs = qs.filter(rooms__room_type__icontains=room_type)
        if amenities_text:
            amenity_names = [s.strip() for s in amenities_text.split(',') if s.strip()]
            try:
                amenity_ids = list(Amenity.objects.filter(name__in=amenity_names).values_list('id', flat=True))
            except DatabaseError:
                amenity_ids = []
            if amenity_ids:
                qs = qs.filter(rooms__amenities__in=amenity_ids)
            else:
                qs = qs.none()
        if barangay:
            qs = qs.filter(barangay=barangay)
        if sort == 'lowest_price':
            qs = qs.order_by('rooms__monthly_rate')
        elif sort == 'newest':
            qs = qs.order_by('-id')

    # Decorate AFTER filtering
    houses = decorate_house_cards(qs)

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(houses, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Build query string for pagination links
    query_params = request.GET.copy()
    query_params.pop('page', None)
    query_string = '&' + query_params.urlencode() if query_params else ''

    # AJAX fragment response
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'core/includes/search_grid_fragment.html', {
            'listings': page_obj.object_list,
        })

    return render(request, 'core/search_results.html', {
        'listings': page_obj,
        'barangays': barangays,
        'all_amenities': all_amenities,
        'form': form,
        'query_string': query_string,
    })


@login_required
def chat_list(request):
    """List user's conversations."""
    # Get conversations where user is participant
    # This assumes an Inquiry/Message model structure
    conversations = []
    return render(request, 'core/chat.html', {
        'conversations': conversations,
        'active_conversation': None,
    })


@login_required
def chat_detail(request, pk):
    """View a conversation and its messages."""
    # Placeholder - requires Inquiry/Message model
    return render(request, 'core/chat.html', {
        'conversations': [],
        'active_conversation': None,
        'messages': [],
    })


@login_required
@require_POST
def send_message(request, pk):
    """Send a message in a conversation."""
    return redirect('chat_detail', pk=pk)


def listing_detail(request, pk):
    """Public listing detail page (alias for boarding_detail)."""
    return boarding_detail(request, pk)