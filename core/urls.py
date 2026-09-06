from django.urls import path
from django.views.generic.base import RedirectView

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('listings/', views.listing_list, name='listing_list'),
    path('listings/<int:pk>/', views.boarding_detail, name='boarding_detail'),
    # Redirect to fix common typo: /landlord/login/ -> /landlords/login/

    path('landlord/login/', RedirectView.as_view(url='/landlords/login/'), name='landlord_login_redirect'),
    path('students/register/', views.student_register, name='student_register'),
    path('students/login/', views.student_login, name='student_login'),
    path('students/inquiries/', views.student_inquiry_list, name='student_inquiry_list'),
    path('students/inquiries/<int:pk>/', views.inquiry_thread, name='student_inquiry_thread'),
    path('students/bookings/', views.student_bookings, name='student_bookings'),
    path('students/dashboard/', views.student_dashboard, name='student_dashboard'),
    path('landlords/inquiries/', views.landlord_inquiry_list, name='landlord_inquiry_list'),
    path('landlords/inquiries/<int:pk>/', views.inquiry_thread, name='landlord_inquiry_thread'),
    path('landlords/inquiries/<int:pk>/accept/', views.accept_student, name='accept_student'),
    path('landlords/inquiries/<int:pk>/reject/', views.reject_student, name='reject_student'),
    path('landlords/bookings/', views.landlord_bookings, name='landlord_bookings'),
    path('inquiries/<int:pk>/messages/', views.inquiry_messages_json, name='inquiry_messages_json'),
    path('inquiries/send/<int:pk>/', views.send_inquiry, name='send_inquiry'),
    # Landlord accounts are admin-created; kept as a friendly redirect.
    path('landlords/register/', views.landlord_register, name='landlord_register'),
    path('landlords/login/', views.landlord_login, name='landlord_login'),
    path('landlords/dashboard/', views.landlord_dashboard, name='landlord_dashboard'),
    path('landlords/boarding-houses/', views.landlord_boarding_house_list, name='landlord_boarding_house_list'),
    path('landlords/boarding-houses/add/', views.boarding_house_create, name='boarding_house_create'),
    path('landlords/boarding-houses/<int:pk>/', views.landlord_boarding_house_detail, name='landlord_boarding_house_detail'),
    path('landlords/boarding-houses/<int:pk>/edit/', views.boarding_house_edit, name='boarding_house_edit'),
    path('landlords/boarding-houses/<int:pk>/rooms/add/', views.room_create, name='room_create'),
    path('landlords/rooms/<int:pk>/edit/', views.room_edit, name='room_edit'),
    path('landlords/rooms/<int:pk>/toggle-availability/', views.toggle_room_availability, name='toggle_room_availability'),
    path('admin/login/', views.admin_login, name='admin_login'),
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/analytics/', views.admin_analytics, name='admin_analytics'),
    path('admin/landlords/', views.admin_landlord_list, name='admin_landlord_list'),
    path('admin/landlords/<int:pk>/', views.admin_landlord_detail, name='admin_landlord_detail'),
    path('admin/landlords/<int:pk>/edit/', views.admin_edit_landlord, name='admin_edit_landlord'),
    path('admin/landlords/<int:pk>/toggle/', views.toggle_landlord_active, name='toggle_landlord_active'),
    path('admin/landlords/<int:pk>/delete/', views.admin_delete_landlord, name='admin_delete_landlord'),
    path('admin/students/', views.admin_student_list, name='admin_student_list'),
    path('admin/students/<int:pk>/delete/', views.admin_delete_student, name='admin_delete_student'),
    path('admin/landlords/add/', views.admin_create_landlord, name='admin_create_landlord'),
    path('admin/listings/pending/', views.admin_pending_listings, name='admin_pending_listings'),
    path('admin/listings/<int:pk>/approve/', views.admin_approve_listing, name='admin_approve_listing'),
    path('admin/listings/<int:pk>/reject/', views.admin_reject_listing, name='admin_reject_listing'),
    path('admin/barangays/', views.admin_barangay_list, name='admin_barangay_list'),
    path('admin/barangays/<int:pk>/edit/', views.admin_barangay_edit, name='admin_barangay_edit'),
    path('admin/barangays/<int:pk>/delete/', views.admin_barangay_delete, name='admin_barangay_delete'),
    path('admin/settings/', views.admin_settings, name='admin_settings'),
    path('admin/reports/', views.admin_reports, name='admin_reports'),
    path('admin/reports/<int:pk>/', views.admin_report_detail, name='admin_report_detail'),
    path('admin/reports/<int:pk>/update/', views.admin_report_update, name='admin_report_update'),
    path('logout/', views.logout_view, name='logout'),
    path('accounts/login/', views.accounts_login, name='login'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/update/', views.update_profile, name='update_profile'),
    path('profile/upload-picture/', views.upload_profile_picture, name='upload_profile_picture'),
    path('profile/change-password/', views.change_password, name='change_password'),
    path('users/<int:pk>/', views.user_profile, name='user_profile'),
    path('users/<int:pk>/report/', views.report_user, name='report_user'),

    # Profile
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/avatar/', views.update_avatar, name='update_avatar'),

    # Search with AJAX
    path('search/', views.search_results, name='search_results'),

    # Chat
    path('chat/', views.chat_list, name='chat_list'),
    path('chat/<int:pk>/', views.chat_detail, name='chat_detail'),
    path('chat/<int:pk>/send/', views.send_message, name='send_message'),

    # Listing detail alias
    path('listing/<int:pk>/', views.listing_detail, name='listing_detail'),
]