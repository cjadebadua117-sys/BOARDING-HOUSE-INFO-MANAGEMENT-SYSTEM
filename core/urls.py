from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('listings/', views.listing_list, name='listing_list'),
    path('listings/<int:pk>/', views.boarding_detail, name='boarding_detail'),
    path('students/register/', views.student_register, name='student_register'),
    path('students/login/', views.student_login, name='student_login'),
    path('students/profile/', views.student_profile, name='student_profile'),
    path('students/inquiries/', views.student_inquiry_list, name='student_inquiry_list'),
    path('landlords/inquiries/', views.landlord_inquiry_list, name='landlord_inquiry_list'),
    path('landlords/register/', views.landlord_register, name='landlord_register'),
    path('landlords/login/', views.landlord_login, name='landlord_login'),
    path('landlords/dashboard/', views.landlord_dashboard, name='landlord_dashboard'),
    path('landlords/boarding-houses/', views.landlord_boarding_house_list, name='landlord_boarding_house_list'),
    path('landlords/boarding-houses/add/', views.boarding_house_create, name='boarding_house_create'),
    path('landlords/boarding-houses/<int:pk>/', views.landlord_boarding_house_detail, name='landlord_boarding_house_detail'),
    path('landlords/boarding-houses/<int:pk>/edit/', views.boarding_house_edit, name='boarding_house_edit'),
    path('admin/login/', views.admin_login, name='admin_login'),
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/analytics/', views.admin_analytics, name='admin_analytics'),
    path('admin/landlords/', views.admin_landlord_list, name='admin_landlord_list'),
    path('admin/landlords/<int:pk>/', views.admin_landlord_detail, name='admin_landlord_detail'),
    path('admin/landlords/<int:pk>/edit/', views.admin_edit_landlord, name='admin_edit_landlord'),
    path('admin/landlords/<int:pk>/toggle/', views.toggle_landlord_active, name='toggle_landlord_active'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/update/', views.update_profile, name='update_profile'),
    path('profile/upload-picture/', views.upload_profile_picture, name='upload_profile_picture'),
    path('profile/change-password/', views.change_password, name='change_password'),
]