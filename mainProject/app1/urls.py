from django.urls import path
from . import views

urlpatterns = [
    # Change home_view to homeFunction to match what's in views.py
    path('', views.homeFunction, name='home'),
    
    # Keep your hotel-related URLs
    path('hotels/', views.hotels, name='hotels'),
    path('hotels/<str:hotel_id>/', views.hotel_detail, name='hotel_detail'),
    path('offers/<str:offer_id>/', views.offer_detail, name='offer_detail'),
    
    # Add paths for other view functions
    path('about/', views.aboutFunction, name='about'),
    path('blog/', views.blogFunction, name='blog'),
    path('contact/', views.contactFunction, name='contact'),
    path('rooms/', views.roomsFunction, name='rooms'),
    path('services/', views.servicesFunction, name='services'),
    path('elements/', views.elementsFunction, name='elements'),
    
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('cart/', views.cart_view, name='cart'),
    
    # Cart management URLs
    path('cart/add/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    
    # Flight cart management URLs
    path('cart/add-flight/', views.add_flight_to_cart, name='add_flight_to_cart'),
    path('cart/remove-flight/<int:item_id>/', views.remove_flight_from_cart, name='remove_flight_from_cart'),
    
    # Checkout URL
    path('checkout/start/', views.start_checkout, name='start_checkout'),
]
