from django.shortcuts import render, redirect
from .services import AmadeusHotelService
from datetime import datetime, timedelta, time
from django.contrib.auth.decorators import login_required
from loginApp.models import UserProfile, UserActivity
from .models import CartItem, FlightCartItem
from django.contrib import messages
from django.contrib.auth.models import User
from adminApp.models import Hotel as AdminHotel  # Import the admin Hotel model
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
import json
from decimal import Decimal
import logging

# Configure logger
logger = logging.getLogger(__name__)

# Add these new views for hotel search and details

def hotels(request):
    hotel_service = AmadeusHotelService()
    
    # Get search parameters from request
    city_name = request.GET.get('city', '')
    
    # Default dates (today and tomorrow)
    today = datetime.today()
    tomorrow = today + timedelta(days=1)
    
    check_in = request.GET.get('check_in', today.strftime('%Y-%m-%d'))
    check_out = request.GET.get('check_out', tomorrow.strftime('%Y-%m-%d'))
    adults = int(request.GET.get('adults', 1))
    
    # Initialize context
    context = {
        'city': city_name,
        'check_in': check_in,
        'check_out': check_out,
        'adults': adults,
        'hotels_data': None,
        'error': None
    }
    
    # Log user activity if they performed a search and are logged in
    if city_name and request.user.is_authenticated:
        # Create activity record
        activity_title = f"Hotel search in {city_name}"
        activity_description = f"Searched for hotels in {city_name} from {check_in} to {check_out} for {adults} adults"
        
        UserActivity.objects.create(
            user=request.user,
            activity_type='search_hotel',
            title=activity_title,
            description=activity_description
        )
    
    # Get custom hotels from the admin database
    custom_hotels = []
    if city_name:
        admin_hotels = AdminHotel.objects.filter(
            Q(city_name__icontains=city_name) | 
            Q(location__icontains=city_name)
        ).filter(status='active')
        
        # Convert admin hotels to the same format as API results
        for hotel in admin_hotels:
            custom_hotel = {
                'hotel': {
                    'hotelId': f"ADMIN-{hotel.hotel_id}",
                    'name': hotel.name,
                    'rating': hotel.rating,
                    'cityCode': '',
                    'image_url': hotel.image_url,
                    'address': {
                        'lines': [hotel.address_line],
                        'cityName': hotel.city_name,
                        'countryCode': hotel.country_code,
                        'postalCode': hotel.postal_code
                    }
                },
                'offers': [
                    {
                        'id': f"ADMIN-OFFER-{hotel.id}",
                        'checkInDate': check_in,
                        'checkOutDate': check_out,
                        'roomQuantity': 1,
                        'price': {
                            'total': str(hotel.price_per_night),
                            'currency': 'USD'
                        },
                        'room': {
                            'typeEstimated': {
                                'category': 'STANDARD',
                                'beds': 1,
                                'bedType': 'DOUBLE'
                            }
                        }
                    }
                ],
                'self': f"/hotels/{hotel.hotel_id}"
            }
            custom_hotels.append(custom_hotel)
    
    # Only search if a city is provided
    if city_name:
        # Get city code from city name
        city_code = hotel_service.search_city_code(city_name)
        print(f"City code for {city_name}: {city_code}")  # Debug print
        
        api_hotels = []
        if city_code:
            # Validate dates
            try:
                # Convert to datetime objects
                check_in_date = datetime.strptime(check_in, "%Y-%m-%d")
                check_out_date = datetime.strptime(check_out, "%Y-%m-%d")
                
                # Check if check_out is after check_in
                if check_out_date <= check_in_date:
                    context['error'] = "Check-out date must be after check-in date."
                    return render(request, 'hotels.html', context)
                
                # Ensure dates are not too far in the future (Amadeus has limits)
                max_future_date = today + timedelta(days=365)  # Most APIs limit to 1 year
                if check_in_date > max_future_date or check_out_date > max_future_date:
                    context['error'] = "Dates cannot be more than one year in the future."
                    return render(request, 'hotels.html', context)
                
                # Search for hotels
                hotels_data = hotel_service.search_hotels(
                    city_code=city_code,
                    check_in_date=check_in,
                    check_out_date=check_out,
                    adults=adults
                )
                
                print(f"Hotels API response success: {hotels_data['success']}")  # Debug print
                if not hotels_data['success'] and 'error' in hotels_data:
                    error_details = hotels_data['error']
                    print(f"Detailed API error: {error_details}")  # Debug print
                    
                    # Try to extract meaningful error message if possible
                    try:
                        if isinstance(error_details, dict) and 'errors' in error_details:
                            error_message = error_details['errors'][0]['detail']
                            context['error'] = f"API error: {error_message}"
                        elif isinstance(error_details, str):
                            context['error'] = f"API error: {error_details}"
                        else:
                            context['error'] = "Failed to fetch hotel data. Please try again."
                    except (KeyError, IndexError, TypeError):
                        context['error'] = "Failed to fetch hotel data. Please try again."
                elif hotels_data['success']:
                    if hotels_data['data']:
                        api_hotels = hotels_data['data']
                
            except ValueError as e:
                print(f"Date format error: {str(e)}")
                context['error'] = "Invalid date format. Please use YYYY-MM-DD format."
            except Exception as e:
                print(f"Unexpected error in hotel search: {str(e)}")
                context['error'] = "An unexpected error occurred. Please try again."
        
        # Combine API hotels and custom hotels
        combined_hotels = custom_hotels + api_hotels
        
        if combined_hotels:
            context['hotels_data'] = combined_hotels
        elif not context['error']:
            context['error'] = f"No hotels found in {city_name} for the selected dates."
    
    return render(request, 'hotels.html', context)

def hotel_detail(request, hotel_id):
    # Check if this is a custom hotel (has ADMIN prefix)
    if str(hotel_id).startswith('ADMIN-'):
        admin_hotel_id = hotel_id.replace('ADMIN-', '')
        try:
            # Get custom hotel from database
            hotel = AdminHotel.objects.get(hotel_id=admin_hotel_id)
            
            # Log activity if user is authenticated
            if request.user.is_authenticated:
                from loginApp.models import UserActivity
                UserActivity.objects.create(
                    user=request.user,
                    activity_type='view_hotel',
                    title=f"Viewed hotel: {hotel.name}",
                    description=f"Viewed details for {hotel.name} in {hotel.city_name}, {hotel.country_code}"
                )
            
            # Get dates from request or use defaults
            today = datetime.today()
            tomorrow = today + timedelta(days=1)
            day_after = today + timedelta(days=2)
            
            check_in = request.GET.get('check_in', tomorrow.strftime('%Y-%m-%d'))
            check_out = request.GET.get('check_out', day_after.strftime('%Y-%m-%d'))
            adults = int(request.GET.get('adults', 1))
            
            # Calculate number of nights
            check_in_date = datetime.strptime(check_in, "%Y-%m-%d")
            check_out_date = datetime.strptime(check_out, "%Y-%m-%d")
            nights = (check_out_date - check_in_date).days
            
            # Create a hotel data structure similar to the API format
            hotel_data = {
                'hotel': {
                    'hotelId': f"ADMIN-{hotel.hotel_id}",
                    'name': hotel.name,
                    'rating': hotel.rating,
                    'description': {
                        'text': hotel.description
                    },
                    'address': {
                        'lines': [hotel.address_line],
                        'cityName': hotel.city_name,
                        'countryCode': hotel.country_code,
                        'postalCode': hotel.postal_code
                    },
                    'media': [
                        {'uri': hotel.image_url}
                    ]
                },
                'available': hotel.status == 'active' and hotel.available_rooms > 0,
                'offers': [
                    {
                        'id': f"ADMIN-OFFER-{hotel.id}",
                        'checkInDate': check_in,
                        'checkOutDate': check_out,
                        'roomQuantity': 1,
                        'guests': {
                            'adults': adults
                        },
                        'price': {
                            'total': str(hotel.price_per_night * nights),
                            'currency': 'USD'
                        },
                        'room': {
                            'typeEstimated': {
                                'category': 'STANDARD',
                                'beds': 1,
                                'bedType': 'DOUBLE'
                            },
                            'description': {
                                'text': 'Standard room with all amenities'
                            }
                        }
                    }
                ]
            }
            
            context = {
                'check_in': check_in,
                'check_out': check_out,
                'adults': adults,
                'hotel_data': hotel_data,
                'error': None,
                'hotel_id': hotel_id,
                'is_custom_hotel': True
            }
            
            return render(request, 'hotel_detail.html', context)
            
        except AdminHotel.DoesNotExist:
            context = {
                'error': "Custom hotel not found.",
                'hotel_id': hotel_id
            }
            return render(request, 'hotel_detail.html', context)
    
    # If not a custom hotel, proceed with API hotel detail
    hotel_service = AmadeusHotelService()
    
    # Get dates from request or use defaults
    today = datetime.today()
    tomorrow = today + timedelta(days=1)
    day_after = today + timedelta(days=2)
    
    check_in = request.GET.get('check_in', tomorrow.strftime('%Y-%m-%d'))
    check_out = request.GET.get('check_out', day_after.strftime('%Y-%m-%d'))
    adults = int(request.GET.get('adults', 1))
    
    print(f"Getting details for hotel: {hotel_id} for dates {check_in} to {check_out}")
    
    # Get hotel offers
    hotel_data = hotel_service.get_hotel_offers(
        hotel_id=hotel_id,
        check_in_date=check_in,
        check_out_date=check_out,
        adults=adults
    )
    
    context = {
        'check_in': check_in,
        'check_out': check_out,
        'adults': adults,
        'hotel_data': None,
        'error': None,
        'hotel_id': hotel_id,
        'is_custom_hotel': False
    }
    
    if hotel_data['success']:
        # Check if the data has content
        if hotel_data['data'] and 'hotel' in hotel_data['data']:
            context['hotel_data'] = hotel_data['data']
            
            # Log activity if user is authenticated and hotel data is available
            if request.user.is_authenticated:
                hotel_name = hotel_data['data']['hotel']['name']
                # Safely access the 'address' key with a default empty dict
                hotel_address = hotel_data['data']['hotel'].get('address', {})
                hotel_city = hotel_address.get('cityName', 'Unknown city')
                
                from loginApp.models import UserActivity
                UserActivity.objects.create(
                    user=request.user,
                    activity_type='view_hotel',
                    title=f"Viewed hotel: {hotel_name}",
                    description=f"Viewed details for {hotel_name} in {hotel_city}"
                )
        else:
            context['error'] = "No offers available for this hotel on the selected dates."
    else:
        error_message = hotel_data.get('error', "Failed to fetch hotel details. Please try again.")
        context['error'] = error_message
        
        # Log detailed error for debugging
        if 'detailed_error' in hotel_data:
            print(f"Detailed error for hotel {hotel_id}: {hotel_data['detailed_error']}")
    
    return render(request, 'hotel_detail.html', context)

def offer_detail(request, offer_id):
    # Check if this is a custom hotel offer
    if str(offer_id).startswith('ADMIN-OFFER-'):
        # Extract hotel ID from the offer ID
        hotel_id = offer_id.replace('ADMIN-OFFER-', '')
        try:
            # Get custom hotel from database
            hotel = AdminHotel.objects.get(id=hotel_id)
            
            # Get dates from request or use defaults
            today = datetime.today()
            tomorrow = today + timedelta(days=1)
            day_after = today + timedelta(days=2)
            
            check_in = request.GET.get('check_in', tomorrow.strftime('%Y-%m-%d'))
            check_out = request.GET.get('check_out', day_after.strftime('%Y-%m-%d'))
            adults = int(request.GET.get('adults', 1))
            
            # Calculate number of nights
            check_in_date = datetime.strptime(check_in, "%Y-%m-%d")
            check_out_date = datetime.strptime(check_out, "%Y-%m-%d")
            nights = (check_out_date - check_in_date).days
            
            # Create offer data structure similar to the API format
            offer_data = {
                'offer': {
                    'id': offer_id,
                    'checkInDate': check_in,
                    'checkOutDate': check_out,
                    'roomQuantity': 1,
                    'guests': {
                        'adults': adults
                    },
                    'price': {
                        'total': str(hotel.price_per_night * nights),
                        'currency': 'USD'
                    },
                    'room': {
                        'typeEstimated': {
                            'category': 'STANDARD',
                            'beds': 1,
                            'bedType': 'DOUBLE'
                        },
                        'description': {
                            'text': 'Standard room with all amenities'
                        }
                    }
                },
                'hotel': {
                    'hotelId': f"ADMIN-{hotel.hotel_id}",
                    'name': hotel.name,
                    'rating': hotel.rating,
                    'description': {
                        'text': hotel.description
                    },
                    'address': {
                        'lines': [hotel.address_line],
                        'cityName': hotel.city_name,
                        'countryCode': hotel.country_code,
                        'postalCode': hotel.postal_code
                    },
                    'media': [
                        {'uri': hotel.image_url}
                    ]
                }
            }
            
            context = {
                'offer_data': offer_data,
                'error': None,
                'is_custom_offer': True
            }
            
            return render(request, 'offer_detail.html', context)
            
        except AdminHotel.DoesNotExist:
            context = {
                'error': "Custom hotel offer not found.",
                'offer_id': offer_id
            }
            return render(request, 'offer_detail.html', context)
    
    # If not a custom offer, proceed with API offer detail
    hotel_service = AmadeusHotelService()
    
    # Get offer details
    offer_data = hotel_service.get_hotel_offer_details(offer_id)
    
    context = {
        'offer_data': None,
        'error': None,
        'is_custom_offer': False
    }
    
    if offer_data['success']:
        context['offer_data'] = offer_data['data']
    else:
        context['error'] = "Failed to fetch offer details. Please try again."
    
    return render(request, 'offer_detail.html', context)


# Add this function to match what's referenced in urls.py
def homeFunction(request):
    return render(request, 'home.html')  # Make sure 'home.html' exists in your templates folder

# Add the missing aboutFunction that's referenced in urls.py
def aboutFunction(request):
    return render(request, 'about.html')  # Make sure 'about.html' exists in your templates folder

# Add the missing blogFunction that's referenced in urls.py
def blogFunction(request):
    return render(request, 'blog.html')  # Make sure 'blog.html' exists in your templates folder

# Add the missing contactFunction that's referenced in urls.py
def contactFunction(request):
    return render(request, 'contact.html')  # Make sure 'contact.html' exists in your templates folder

# Add other potentially needed functions
def roomsFunction(request):
    return render(request, 'rooms.html')  # Make sure 'rooms.html' exists in your templates folder

def servicesFunction(request):
    return render(request, 'services.html')  # Make sure 'services.html' exists in your templates folder

def elementsFunction(request):
    return render(request, 'elements.html')  # Make sure 'elements.html' exists in your templates folder

def loginFunction(request):
    return render(request, 'login.html')  # Make sure 'login.html' exists in your templates folder

def registerFunction(request):
    return render(request, 'register.html')  # Make sure 'register.html' exists in your templates folder

# Keep your other view functions as they are

@login_required
def profile_view(request):
    user = request.user  # Get the currently logged-in user
    try:
        profile = UserProfile.objects.get(user=user)  # Get the user profile
    except UserProfile.DoesNotExist:
        profile = None  # If profile does not exist, set to None
    
    # Get the user's recent bookings (limit to 5 most recent)
    from flights.models import FlightBooking
    recent_bookings = FlightBooking.objects.filter(user=user).order_by('-booking_date')[:5]
    
    # Get the user's recent activities (limit to 10 most recent)
    from loginApp.models import UserActivity
    recent_activities = UserActivity.objects.filter(user=user).order_by('-timestamp')[:10]

    return render(request, 'profile.html', {
        'user': user, 
        'profile': profile,
        'recent_bookings': recent_bookings,
        'recent_activities': recent_activities
    })

@login_required
def edit_profile(request):
    user = request.user
    try:
        profile = UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        profile = None
    
    if request.method == 'POST':
        # Handle form submission
        email = request.POST.get('email', '')
        new_username = request.POST.get('username', '').strip()
        
        # Check if username is being changed
        if new_username and new_username != user.username:
            # Check if username already exists
            if User.objects.filter(username=new_username).exists():
                messages.error(request, f'Username "{new_username}" is already taken. Please choose another one.')
                return render(request, 'edit_profile.html', {'user': user, 'profile': profile})
            else:
                # Store the old username for the message
                old_username = user.username
                # Update username
                user.username = new_username
                # Add a specific message for username change
                messages.success(request, f'Your username has been changed from "{old_username}" to "{new_username}". Please use your new username to log in next time.')
        
        # Update user email
        user.email = email
        user.save()
        
        # If user is a manager, update hotel name if provided
        if profile and profile.is_manager():
            hotel_name = request.POST.get('hotel_name', '')
            if hotel_name:
                profile.hotel_name = hotel_name
                profile.save()
        
        # Add a general success message if no username change message was added
        if not any(message.tags == 'success' for message in messages.get_messages(request)):
            messages.success(request, 'Profile updated successfully!')
        return redirect('profile')
    
    # For GET request, just render the edit form
    return render(request, 'edit_profile.html', {'user': user, 'profile': profile})

@login_required
def cart_view(request):
    user = request.user
    from .models import CartItem, FlightCartItem
    
    # Get both hotel and flight cart items
    hotel_items = CartItem.objects.filter(user=user)
    flight_items = FlightCartItem.objects.filter(user=user)
    
    # Calculate totals
    hotel_total = sum(item.price for item in hotel_items)
    flight_total = sum(item.price for item in flight_items)
    grand_total = hotel_total + flight_total
    
    # Count items
    hotel_count = hotel_items.count()
    flight_count = flight_items.count()
    total_count = hotel_count + flight_count
    
    # Determine which tab should be active
    active_tab = request.GET.get('tab', 'all')
    if active_tab not in ['all', 'hotels', 'flights']:
        active_tab = 'all'
    
    context = {
        'hotel_items': hotel_items,
        'flight_items': flight_items,
        'hotel_total': hotel_total,
        'flight_total': flight_total,
        'grand_total': grand_total,
        'hotel_count': hotel_count,
        'flight_count': flight_count,
        'total_count': total_count,
        'active_tab': active_tab,
    }
    return render(request, 'cart.html', context)

@login_required
def add_to_cart(request):
    if request.method == 'GET':
        # Get parameters from the URL
        offer_id = request.GET.get('offer_id')
        hotel_name = request.GET.get('hotel_name')
        check_in_str = request.GET.get('check_in')
        check_out_str = request.GET.get('check_out')
        adults = request.GET.get('adults', 1)
        price_str = request.GET.get('price')
        room_description = request.GET.get('room_description', '')
        hotel_id = request.GET.get('hotel_id', '')  # Get hotel_id from the URL
        
        # Validate required parameters
        if not all([offer_id, hotel_name, check_in_str, check_out_str, price_str]):
            messages.error(request, "Missing required information for adding to cart.")
            return redirect('hotels')
        
        try:
            # Convert string values to appropriate types
            check_in = datetime.strptime(check_in_str, '%Y-%m-%d').date()
            check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date()
            price = float(price_str)
            adults = int(adults)
            
            # Check if this offer is already in the user's cart
            existing_item = CartItem.objects.filter(
                user=request.user,
                offer_id=offer_id
            ).first()
            
            if existing_item:
                messages.info(request, f"This room at {hotel_name} is already in your cart.")
            else:
                # Create and save the cart item
                cart_item = CartItem(
                    user=request.user,
                    hotel_name=hotel_name,
                    hotel_id=hotel_id,  # Store the hotel_id
                    offer_id=offer_id,
                    check_in=check_in,
                    check_out=check_out,
                    price=price,
                    adults=adults,
                    room_description=room_description
                )
                cart_item.save()
                
                # Log the activity
                if request.user.is_authenticated:
                    from loginApp.models import UserActivity
                    UserActivity.objects.create(
                        user=request.user,
                        activity_type='add_to_cart',
                        title=f"Added hotel to cart: {hotel_name}",
                        description=f"Added {hotel_name} to cart for {check_in} to {check_out} ({adults} adults)"
                    )
                
                messages.success(request, f"Added {hotel_name} to your cart!")
            
            # Redirect to the cart page
            return redirect('cart')
            
        except ValueError as e:
            messages.error(request, f"Invalid data format: {str(e)}")
            return redirect('hotels')
        except Exception as e:
            messages.error(request, f"Error adding to cart: {str(e)}")
            return redirect('hotels')
    
    # If not a GET request, redirect to hotels page
    return redirect('hotels')

@login_required
def remove_from_cart(request, item_id):
    try:
        cart_item = CartItem.objects.get(id=item_id, user=request.user)
        hotel_name = cart_item.hotel_name
        cart_item.delete()
        messages.success(request, f"Removed {hotel_name} from your cart.")
    except CartItem.DoesNotExist:
        messages.error(request, "Item not found in your cart.")
    
    return redirect('cart')

@login_required
def add_flight_to_cart(request):
    if request.method == 'GET':
        # Get parameters from the URL
        offer_id = request.GET.get('offer_id')
        origin = request.GET.get('origin')
        destination = request.GET.get('destination')
        departure_date_str = request.GET.get('departure_date')
        return_date_str = request.GET.get('return_date')
        airline = request.GET.get('airline')
        flight_number = request.GET.get('flight_number')
        price_str = request.GET.get('price')
        passengers = request.GET.get('passengers', 1)
        flight_class = request.GET.get('flight_class', 'ECONOMY')
        is_round_trip = request.GET.get('is_round_trip', 'true').lower() == 'true'
        
        # Validate required parameters
        if not all([offer_id, origin, destination, departure_date_str, price_str]):
            messages.error(request, "Missing required information for adding flight to cart.")
            return redirect('flights:flights')
        
        try:
            # Convert string values to appropriate types
            departure_date = datetime.strptime(departure_date_str, '%Y-%m-%dT%H:%M:%S')
            return_date = datetime.strptime(return_date_str, '%Y-%m-%dT%H:%M:%S') if return_date_str else None
            price = float(price_str)
            passengers = int(passengers)
            
            # Check if this flight is already in the user's cart
            existing_item = FlightCartItem.objects.filter(
                user=request.user,
                offer_id=offer_id
            ).first()
            
            if existing_item:
                messages.info(request, f"This flight from {origin} to {destination} is already in your cart.")
            else:
                # Create and save the cart item
                cart_item = FlightCartItem(
                    user=request.user,
                    offer_id=offer_id,
                    origin=origin,
                    destination=destination,
                    departure_date=departure_date,
                    return_date=return_date,
                    airline=airline,
                    flight_number=flight_number,
                    price=price,
                    passengers=passengers,
                    flight_class=flight_class,
                    is_round_trip=is_round_trip
                )
                cart_item.save()
                
                # Log the activity
                if request.user.is_authenticated:
                    from loginApp.models import UserActivity
                    UserActivity.objects.create(
                        user=request.user,
                        activity_type='add_to_cart',
                        title=f"Added flight to cart: {origin} to {destination}",
                        description=f"Added flight from {origin} to {destination} to cart ({passengers} passengers)"
                    )
                
                messages.success(request, f"Added flight from {origin} to {destination} to your cart!")
            
            # Redirect to the cart page
            return redirect('cart')
            
        except ValueError as e:
            messages.error(request, f"Invalid data format: {str(e)}")
            return redirect('flights:flights')
        except Exception as e:
            messages.error(request, f"Error adding flight to cart: {str(e)}")
            return redirect('flights:flights')
    
    # If not a GET request, redirect to flights page
    return redirect('flights:flights')

@login_required
def remove_flight_from_cart(request, item_id):
    try:
        from .models import FlightCartItem
        cart_item = FlightCartItem.objects.get(id=item_id, user=request.user)
        origin = cart_item.origin
        destination = cart_item.destination
        cart_item.delete()
        messages.success(request, f"Removed flight from {origin} to {destination} from your cart.")
    except FlightCartItem.DoesNotExist:
        messages.error(request, "Flight not found in your cart.")
    
    return redirect('cart')

@login_required
def start_checkout(request):
    user = request.user
    hotel_items = CartItem.objects.filter(user=user)
    flight_items = FlightCartItem.objects.filter(user=user)

    if not hotel_items.exists() and not flight_items.exists():
        messages.error(request, "Your cart is empty. Add items before checking out.")
        return redirect('cart')

    # Calculate grand total
    hotel_total = sum(item.price for item in hotel_items)
    flight_total = sum(item.price for item in flight_items)
    grand_total = hotel_total + flight_total

    first_flight = flight_items.first()
    first_hotel = hotel_items.first()
    booking_details_data = {} # To store extra info

    # --- Determine primary details and add extra info ---
    if first_flight:
        # Primarily a flight booking (might include hotels too)
        booking_origin = first_flight.origin
        booking_destination = first_flight.destination
        booking_departure_date = first_flight.departure_date
        booking_return_date = first_flight.return_date
        booking_passenger_count = first_flight.passengers
        booking_is_round_trip = first_flight.is_round_trip
        booking_flight_offer_id = f"cart_checkout_{user.id}_{datetime.now().timestamp()}"
        
        # Add additional flight details as strings to prevent serialization issues
        booking_details_data['type'] = 'Flight'
        booking_details_data['airline'] = first_flight.airline if first_flight.airline else 'Unknown'
        booking_details_data['flight_number'] = first_flight.flight_number if first_flight.flight_number else 'N/A'
        booking_details_data['departure_date_str'] = first_flight.departure_date.strftime('%Y-%m-%d %H:%M:%S')
        if booking_return_date:
            booking_details_data['return_date_str'] = booking_return_date.strftime('%Y-%m-%d %H:%M:%S')
        
        if first_hotel:
             booking_details_data['includes_hotel'] = True
             booking_details_data['hotel_name'] = first_hotel.hotel_name
             # Store dates as strings
             if first_hotel.check_in: 
                 booking_details_data['hotel_check_in'] = first_hotel.check_in.strftime('%Y-%m-%d')
             if first_hotel.check_out:
                 booking_details_data['hotel_check_out'] = first_hotel.check_out.strftime('%Y-%m-%d')
    elif first_hotel:
        # Only hotels in cart
        booking_origin = first_hotel.hotel_name # Use hotel name for origin
        booking_destination = first_hotel.check_in.strftime('%Y-%m-%d') # Use check-in for destination
        booking_departure_date = datetime.combine(first_hotel.check_in, time.min) if first_hotel.check_in else datetime.now() # Use check-in time
        booking_return_date = datetime.combine(first_hotel.check_out, time.min) if first_hotel.check_out else None # Use check-out time
        booking_passenger_count = first_hotel.adults
        booking_is_round_trip = False # Treat as one-way conceptually
        booking_flight_offer_id = f"cart_checkout_hotels_{user.id}_{datetime.now().timestamp()}"
        booking_details_data['type'] = 'Hotel'
        booking_details_data['hotel_name'] = first_hotel.hotel_name
        # Store dates as strings
        if first_hotel.check_in:
            booking_details_data['hotel_check_in'] = first_hotel.check_in.strftime('%Y-%m-%d')
        if first_hotel.check_out:
            booking_details_data['hotel_check_out'] = first_hotel.check_out.strftime('%Y-%m-%d')
        messages.warning(request, "Checkout includes only hotels.")
    else:
        # This case shouldn't happen due to the empty cart check, but as a fallback:
        messages.error(request, "Cannot proceed to checkout. Error determining items.")
        return redirect('cart')

    try:
        from flights.models import FlightBooking
        
        # Clean up booking details data to ensure it's JSON serializable
        for key in list(booking_details_data.keys()):
            if booking_details_data[key] is None:
                booking_details_data[key] = ""
                
        # Make sure origin and destination don't contain problematic characters
        booking_origin = booking_origin[:90] if booking_origin else "Unknown"
        booking_destination = booking_destination[:90] if booking_destination else "Unknown"
        
        # Create the booking with properly formatted data
        new_booking = FlightBooking.objects.create(
            user=user,
            flight_offer_id=booking_flight_offer_id,
            origin=booking_origin,
            destination=booking_destination,
            departure_date=booking_departure_date,
            return_date=booking_return_date,
            passenger_count=booking_passenger_count,
            total_price=Decimal(str(grand_total)),  # Ensure proper Decimal conversion
            currency='USD',
            payment_status='PENDING',
            is_round_trip=booking_is_round_trip,
            booking_details=booking_details_data # Store the extra details
        )

        # Store the ID of the newly created booking in the session
        request.session['booking_id'] = new_booking.id
        logger.info(f"Stored booking_id {new_booking.id} in session before redirecting.")

        # Redirect to the payment processing page
        return redirect('payments:process')

    except Exception as e:
        messages.error(request, f"Could not proceed to checkout. Error: {e}")
        logger.error(f"Error creating booking record during checkout: {e}", exc_info=True)
        return redirect('cart')
