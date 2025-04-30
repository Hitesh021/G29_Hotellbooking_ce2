from django.urls import path
from . import views

app_name = 'flights'  # This defines the namespace

urlpatterns = [
    path('', views.flights, name='flights'),
    path('search/', views.flights, name='flight_search'),
    path('detail/<str:offer_id>/', views.flight_detail, name='flight_detail'),
    path('book/<str:offer_id>/', views.book_flight, name='book_flight'),
    path('booking/confirmed/', views.booking_confirmed, name='booking_confirmed'),
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    path('search-airport/', views.search_airport, name='search_airport'),
] 