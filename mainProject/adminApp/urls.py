from django.urls import path
from . import views

app_name = 'adminApp'

urlpatterns = [
    # ------------------------
    # Dashboards (Role-Based)
    # ------------------------
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/manager/', views.manager_dashboard, name='manager_dashboard'),
    path('dashboard/customer/', views.customer_dashboard, name='customer_dashboard'),

    # ------------------------
    # Admin Subpages
    # ------------------------
    path('dashboard/admin/reservations/', views.reservations_view, name='reservations'),
    path('create/', views.create_reservation, name='create_reservation'),
    path('reservations/<int:booking_id>/', views.reservation_detail, name='reservation_detail'),
    path('dashboard/admin/users/', views.user_list_view, name='users'),
    path('dashboard/admin/users/<int:user_id>/', views.user_detail_view, name='user_detail'),
    path('dashboard/admin/HNF/', views.HNF_view, name='HNF'),
    
    # ------------------------
    # Hotel CRUD Operations
    # ------------------------
    path('dashboard/admin/hotels/', views.hotel_list, name='hotel_list'),
    path('dashboard/admin/hotels/create/', views.hotel_create, name='hotel_create'),
    path('dashboard/admin/hotels/<int:hotel_id>/edit/', views.hotel_edit, name='hotel_edit'),
    path('dashboard/admin/hotels/<int:hotel_id>/delete/', views.hotel_delete, name='hotel_delete'),
    
    # ------------------------
    # Flight CRUD Operations
    # ------------------------
    path('dashboard/admin/flights/', views.flight_list, name='flight_list'),
    path('dashboard/admin/flights/create/', views.flight_create, name='flight_create'),
    path('dashboard/admin/flights/<int:flight_id>/edit/', views.flight_edit, name='flight_edit'),
    path('dashboard/admin/flights/<int:flight_id>/delete/', views.flight_delete, name='flight_delete'),

    # ------------------------
    # Future Features
    # ------------------------
    # path('dashboard/admin/hotels/', views.hotels_view, name='hotels'),
    # path('dashboard/admin/requests/', views.requests_view, name='requests'),
]

