from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from .services import AmadeusFlightService
from datetime import datetime, timedelta
import json
import re
from django.db.models import Q
from adminApp.models import Flight as AdminFlight
from django.urls import reverse 
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
import requests

def flights(request):
    flight_service = AmadeusFlightService()
    
    # Get search parameters from request
    origin = request.GET.get('origin', '')
    destination = request.GET.get('destination', '')
    
    # Default dates (tomorrow and a week later)
    tomorrow = datetime.today() + timedelta(days=1)
    next_week = tomorrow + timedelta(days=7)
    
    departure_date = request.GET.get('departure_date', tomorrow.strftime('%Y-%m-%d'))
    return_date = request.GET.get('return_date', next_week.strftime('%Y-%m-%d'))
    trip_type = request.GET.get('trip_type', 'round')  # 'round' or 'one-way'
    adults = int(request.GET.get('adults', 1))
    
    # For one-way trips, set return_date to None
    if trip_type == 'one-way':
        return_date = None
    
    # Initialize context
    context = {
        'origin': origin,
        'destination': destination,
        'departure_date': departure_date,
        'return_date': return_date,
        'trip_type': trip_type,
        'adults': adults,
        'flights_data': None,
        'error': None
    }
    
    # Log user activity if they performed a search and are logged in
    if origin and destination and request.user.is_authenticated:
        # Import at function level to avoid circular imports
        from loginApp.models import UserActivity
        
        # Create activity record
        activity_title = f"Flight search from {origin} to {destination}"
        activity_description = f"Searched for {trip_type} flights from {origin} to {destination} departing on {departure_date}"
        if return_date:
            activity_description += f" and returning on {return_date}"
        activity_description += f" for {adults} adults"
        
        UserActivity.objects.create(
            user=request.user,
            activity_type='search_flight',
            title=activity_title,
            description=activity_description
        )
    
    # Only search if origin and destination are provided
    if origin and destination:
        # Check if origin and destination are IATA codes (3 uppercase letters)
        origin_iata = origin
        destination_iata = destination
        
        # If not IATA code pattern, try to convert city name to IATA code
        if not re.match(r'^[A-Z]{3}$', origin):
            # Try to find the IATA code for the origin city
            origin_result = flight_service.search_airport_city_code(origin)
            if origin_result['success'] and origin_result['data']:
                # Use the first result's IATA code
                origin_iata = origin_result['data'][0]['iataCode']
                context['origin_converted'] = origin_iata
                context['origin_original'] = origin
            else:
                context['error'] = f"Could not find airport code for '{origin}'. Please use a valid IATA code (e.g., LHR for London)."
                return render(request, 'flights/flights.html', context)
        
        if not re.match(r'^[A-Z]{3}$', destination):
            # Try to find the IATA code for the destination city
            destination_result = flight_service.search_airport_city_code(destination)
            if destination_result['success'] and destination_result['data']:
                # Use the first result's IATA code
                destination_iata = destination_result['data'][0]['iataCode']
                context['destination_converted'] = destination_iata
                context['destination_original'] = destination
            else:
                context['error'] = f"Could not find airport code for '{destination}'. Please use a valid IATA code (e.g., JFK for New York)."
                return render(request, 'flights/flights.html', context)
        
        # Validate dates
        try:
            # Convert to datetime objects for validation
            departure_date_obj = datetime.strptime(departure_date, "%Y-%m-%d")
            
            # Validate return date if trip is round trip
            if return_date:
                return_date_obj = datetime.strptime(return_date, "%Y-%m-%d")
                
                # Check if return date is after departure date
                if return_date_obj <= departure_date_obj:
                    context['error'] = "Return date must be after departure date."
                    return render(request, 'flights/flights.html', context)
            
            # Ensure dates aren't in the past
            today = datetime.today()
            if departure_date_obj < today:
                context['error'] = "Departure date cannot be in the past."
                return render(request, 'flights/flights.html', context)
            
            # Search for flights using the IATA codes (either original or converted)
            flights_data = flight_service.search_flights(
                origin=origin_iata,
                destination=destination_iata,
                departure_date=departure_date,
                return_date=return_date,
                adults=adults
            )
            
            # Fetch admin flights
            admin_flights = []
            try:
                # Query admin flights based on origin and destination IATA
                admin_flight_objects = AdminFlight.objects.filter(
                    Q(origin_iata=origin_iata) & 
                    Q(destination_iata=destination_iata) &
                    Q(status='scheduled')
                )
                
                for flight in admin_flight_objects:
                    # Format admin flight to match API response structure
                    admin_flight = {
                        'id': f"ADMIN-{flight.flight_id}",
                        'source': 'admin',
                        'itineraries': [
                            {
                                'duration': (flight.arrival_time - flight.departure_time).total_seconds() // 60,
                                'segments': [
                                    {
                                        'departure': {
                                            'iataCode': flight.origin_iata,
                                            'at': flight.departure_time.strftime('%Y-%m-%dT%H:%M:%S'),
                                        },
                                        'arrival': {
                                            'iataCode': flight.destination_iata,
                                            'at': flight.arrival_time.strftime('%Y-%m-%dT%H:%M:%S'),
                                        },
                                        'carrierCode': flight.carrier_code,
                                        'number': flight.flight_number,
                                        'aircraft': {
                                            'code': 'A320'  # Default aircraft code
                                        },
                                        'operating': {
                                            'carrierCode': flight.carrier_code
                                        },
                                        'duration': (flight.arrival_time - flight.departure_time).total_seconds() // 60,
                                    }
                                ]
                            }
                        ],
                        'price': {
                            'currency': flight.currency,
                            'total': str(flight.total_price),
                            'base': str(flight.base_price),
                            'taxes': str(flight.taxes),
                            'grandTotal': str(flight.total_price)
                        },
                        'validatingAirlineCodes': [flight.carrier_code],
                        'travelerPricings': [
                            {
                                'travelerId': '1',
                                'fareOption': 'STANDARD',
                                'travelerType': 'ADULT',
                                'price': {
                                    'currency': flight.currency,
                                    'total': str(flight.total_price),
                                    'base': str(flight.base_price),
                                    'taxes': str(flight.taxes)
                                }
                            }
                        ]
                    }
                    admin_flights.append(admin_flight)
                
                print(f"Found {len(admin_flights)} admin flights")
            except Exception as e:
                print(f"Error fetching admin flights: {str(e)}")
            
            # Combine API and admin flights
            combined_flights = []
            if flights_data['success']:
                combined_flights = flights_data['data']
            combined_flights.extend(admin_flights)
            
            if combined_flights:
                context['flights_data'] = combined_flights
                # Store flight data in session for retrieval on detail page
                try:
                    # For debugging, print the structure of the first flight result
                    if len(combined_flights) > 0:
                        print(f"Sample flight ID: {combined_flights[0].get('id')}")
                        print(f"Number of flights to store: {len(combined_flights)}")
                    
                    # Serialize the flight data to JSON
                    serialized_data = json.dumps(combined_flights)
                    
                    # Store in session
                    request.session['flight_search_results'] = serialized_data
                    request.session.modified = True
                    
                    # Verify data was stored correctly
                    if 'flight_search_results' in request.session:
                        stored_data_length = len(request.session['flight_search_results'])
                        print(f"Successfully stored {stored_data_length} bytes in session")
                    else:
                        print("WARNING: Failed to store data in session")
                        
                except Exception as e:
                    print(f"Error storing flight data in session: {str(e)}")
                    import traceback
                    traceback.print_exc()
                
                if 'dictionaries' in flights_data:
                    context['dictionaries'] = flights_data['dictionaries']
            else:
                context['error'] = "No flights found for your search criteria."
                
        except ValueError as e:
            context['error'] = "Invalid date format. Please use YYYY-MM-DD format."
        except Exception as e:
            context['error'] = f"An error occurred: {str(e)}"
    
    return render(request, 'flights/flights.html', context)

def flight_detail(request, offer_id):
    """View flight details for a specific offer"""
    
    # Check if it's an admin flight
    if str(offer_id).startswith('ADMIN-'):
        try:
            flight_id = offer_id.replace('ADMIN-', '')
            flight = AdminFlight.objects.get(flight_id=flight_id)
            
            # Log user activity if authenticated
            if request.user.is_authenticated:
                from loginApp.models import UserActivity
                UserActivity.objects.create(
                    user=request.user,
                    activity_type='view_flight',
                    title=f"Viewed flight: {flight.origin_iata} to {flight.destination_iata}",
                    description=f"Viewed flight details for {flight.carrier_code}{flight.flight_number} from {flight.origin_iata} to {flight.destination_iata}"
                )
                
            # Construct flight data in a format similar to Amadeus API
            flight_data = {
                'id': offer_id,
                'source': 'admin',
                'itineraries': [
                    {
                        'duration': (flight.arrival_time - flight.departure_time).total_seconds() // 60,
                        'segments': [
                            {
                                'departure': {
                                    'iataCode': flight.origin_iata,
                                    'at': flight.departure_time.strftime('%Y-%m-%dT%H:%M:%S'),
                                },
                                'arrival': {
                                    'iataCode': flight.destination_iata,
                                    'at': flight.arrival_time.strftime('%Y-%m-%dT%H:%M:%S'),
                                },
                                'carrierCode': flight.carrier_code,
                                'number': flight.flight_number,
                                'aircraft': {
                                    'code': 'A320'  # Default aircraft code
                                },
                                'operating': {
                                    'carrierCode': flight.carrier_code
                                },
                                'duration': (flight.arrival_time - flight.departure_time).total_seconds() // 60,
                            }
                        ]
                    }
                ],
                'price': {
                    'currency': flight.currency,
                    'total': str(flight.total_price),
                    'base': str(flight.base_price),
                    'taxes': str(flight.taxes),
                    'grandTotal': str(flight.total_price)
                },
                'validatingAirlineCodes': [flight.carrier_code],
                'travelerPricings': [
                    {
                        'travelerId': '1',
                        'fareOption': 'STANDARD',
                        'travelerType': 'ADULT',
                        'price': {
                            'currency': flight.currency,
                            'total': str(flight.total_price),
                            'base': str(flight.base_price),
                            'taxes': str(flight.taxes)
                        }
                    }
                ]
            }
            
            # Generate a unique color based on the flight ID for styling
            unique_number = sum(ord(c) for c in offer_id) % 1000
            bg_color = f"#{unique_number:06x}"[:7]
            
            # Default values in case we can't get actual data
            origin_city = "Origin City"
            dest_city = "Destination City"
            outbound_segments = []
            return_segments = []
            base_price = 0
            taxes = 0
            total_price = 0
            currency = "USD"
            airline_codes = []
            
            # Parse actual flight data if available
            if flight_data:
                try:
                    # Get price information
                    if 'price' in flight_data:
                        price_data = flight_data['price']
                        base_price = float(price_data.get('base', '0'))
                        taxes = float(price_data.get('taxes', '0'))
                        total_price = float(price_data.get('total', '0'))
                        currency = price_data.get('currency', 'USD')
                    
                    # Parse outbound journey (first itinerary)
                    if 'itineraries' in flight_data and len(flight_data['itineraries']) > 0:
                        outbound = flight_data['itineraries'][0]
                        if 'segments' in outbound:
                            outbound_segments = outbound['segments']
                            
                            # Get origin/destination from first and last segment
                            if len(outbound_segments) > 0:
                                first_segment = outbound_segments[0]
                                last_segment = outbound_segments[-1]
                                
                                origin_city = first_segment.get('departure', {}).get('iataCode', 'Origin')
                                dest_city = last_segment.get('arrival', {}).get('iataCode', 'Destination')
                                
                                # Collect airline codes
                                for seg in outbound_segments:
                                    if 'carrierCode' in seg and seg['carrierCode'] not in airline_codes:
                                        airline_codes.append(seg['carrierCode'])
                
                    # Parse return journey (second itinerary if exists)
                    if 'itineraries' in flight_data and len(flight_data['itineraries']) > 1:
                        return_journey = flight_data['itineraries'][1]
                        if 'segments' in return_journey:
                            return_segments = return_journey['segments']
                            
                            # Collect airline codes
                            for seg in return_segments:
                                if 'carrierCode' in seg and seg['carrierCode'] not in airline_codes:
                                    airline_codes.append(seg['carrierCode'])
                
                except Exception as e:
                    print(f"Error parsing flight data: {str(e)}")
            
            # Create outbound segments HTML
            outbound_segments_html = ""
            if outbound_segments:
                for i, segment in enumerate(outbound_segments):
                    dep_iata = segment.get('departure', {}).get('iataCode', '')
                    arr_iata = segment.get('arrival', {}).get('iataCode', '')
                    dep_time = segment.get('departure', {}).get('at', '')
                    arr_time = segment.get('arrival', {}).get('at', '')
                    carrier = segment.get('carrierCode', '')
                    flight_number = segment.get('number', '')
                    
                    # Format times
                    formatted_dep_time = "Time N/A"
                    formatted_arr_time = "Time N/A"
                    if dep_time:
                        try:
                            dt = datetime.fromisoformat(dep_time.replace('Z', '+00:00'))
                            formatted_dep_time = dt.strftime("%I:%M %p")
                        except:
                            pass
                            
                    if arr_time:
                        try:
                            dt = datetime.fromisoformat(arr_time.replace('Z', '+00:00'))
                            formatted_arr_time = dt.strftime("%I:%M %p")
                        except:
                            pass
                    
                    # Create segment HTML
                    outbound_segments_html += f"""
                    <div class="d-flex justify-content-between align-items-center mb-3 p-3 bg-light rounded">
                        <div>
                            <div class="city-name">{dep_iata}</div>
                            <p>{formatted_dep_time}</p>
                        </div>
                        <div class="flight-arrow">
                            <p class="mb-0 small">Flight {carrier}{flight_number}</p>
                            <p>✈️ ────────</p>
                        </div>
                        <div>
                            <div class="city-name">{arr_iata}</div>
                            <p>{formatted_arr_time}</p>
                        </div>
                    </div>
                    """
                    
                    # Add connection indicator if there are more segments
                    if i < len(outbound_segments) - 1:
                        outbound_segments_html += f"""
                        <div class="text-center mb-3">
                            <span class="badge bg-warning text-dark p-2">Connection at {arr_iata}</span>
                        </div>
                        """
            else:
                # Fallback if no segments are available
                outbound_segments_html = f"""
                <div class="d-flex justify-content-between align-items-center mb-3 p-3 bg-light rounded">
                    <div>
                        <div class="city-name">{origin_city}</div>
                        <p>8:00 AM</p>
                    </div>
                    <div class="flight-arrow">
                        <i class="fa fa-plane"></i> ✈️ ────────
                    </div>
                    <div>
                        <div class="city-name">{dest_city}</div>
                        <p>11:20 AM</p>
                    </div>
                </div>
                """
            
            # Create return segments HTML
            return_segments_html = ""
            if return_segments:
                for i, segment in enumerate(return_segments):
                    dep_iata = segment.get('departure', {}).get('iataCode', '')
                    arr_iata = segment.get('arrival', {}).get('iataCode', '')
                    dep_time = segment.get('departure', {}).get('at', '')
                    arr_time = segment.get('arrival', {}).get('at', '')
                    carrier = segment.get('carrierCode', '')
                    flight_number = segment.get('number', '')
                    
                    # Format times
                    formatted_dep_time = "Time N/A"
                    formatted_arr_time = "Time N/A"
                    if dep_time:
                        try:
                            dt = datetime.fromisoformat(dep_time.replace('Z', '+00:00'))
                            formatted_dep_time = dt.strftime("%I:%M %p")
                        except:
                            pass
                            
                    if arr_time:
                        try:
                            dt = datetime.fromisoformat(arr_time.replace('Z', '+00:00'))
                            formatted_arr_time = dt.strftime("%I:%M %p")
                        except:
                            pass
                    
                    # Create segment HTML
                    return_segments_html += f"""
                    <div class="d-flex justify-content-between align-items-center mb-3 p-3 bg-light rounded">
                        <div>
                            <div class="city-name">{dep_iata}</div>
                            <p>{formatted_dep_time}</p>
                        </div>
                        <div class="flight-arrow">
                            <p class="mb-0 small">Flight {carrier}{flight_number}</p>
                            <p>✈️ ────────</p>
                        </div>
                        <div>
                            <div class="city-name">{arr_iata}</div>
                            <p>{formatted_arr_time}</p>
                        </div>
                    </div>
                    """
                    
                    # Add connection indicator if there are more segments
                    if i < len(return_segments) - 1:
                        return_segments_html += f"""
                        <div class="text-center mb-3">
                            <span class="badge bg-warning text-dark p-2">Connection at {arr_iata}</span>
                        </div>
                        """
            else:
                # Only show return journey if there are return segments
                return_segments_html = "" if not flight_data or len(flight_data.get('itineraries', [])) <= 1 else f"""
                <h4>Return Journey</h4>
                <div class="d-flex justify-content-between align-items-center p-3 bg-light rounded">
                    <div>
                        <div class="city-name">{dest_city}</div>
                        <p>1:00 PM</p>
                    </div>
                    <div class="flight-arrow">
                        <i class="fa fa-plane"></i> ✈️ ────────
                    </div>
                    <div>
                        <div class="city-name">{origin_city}</div>
                        <p>5:30 PM</p>
                    </div>
                </div>
                """
            
            # Return journey title - only show if there are return segments
            return_journey_title = "<h4>Return Journey</h4>" if return_segments else ""
            
            # Create a completely unique HTML response for each flight ID using actual data
            html_content = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Flight Details - Bookify</title>
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
                <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">
                <style>
                    /* Palatin Theme Styles */
                    body {{ 
                        font-family: 'Helvetica', Arial, sans-serif;
                        color: #333; 
                        background-color: #f5f5f5;
                    }}
                    
                    /* Breadcrumb Area */
                    .breadcumb-area {{
                        position: relative;
                        height: 280px;
                        background-color: #0e2737;  
                        z-index: 1;
                    }}
                    
                    .breadcumb-area::after {{
                        content: '';
                        position: absolute;
                        top: 0;
                        left: 0;
                        width: 100%;
                        height: 100%;
                        background-color: rgba(14, 39, 55, 0.7);
                        z-index: -1;
                    }}
                    
                    .bradcumbContent {{
                        text-align: center;
                        padding: 50px;
                    }}
                    
                    .bradcumbContent h2 {{
                        font-size: 42px;
                        color: white;
                        font-weight: 700;
                    }}
                    
                    /* Content Areas */
                    .section-padding-100 {{
                        padding: 100px 0;
                    }}
                    
                    .line {{
                        width: 100px;
                        height: 2px;
                        background-color: #ce8954;
                        margin: 15px 0 30px;
                    }}
                    
                    .single-room-area {{
                        background-color: white;
                        box-shadow: 0 2px 15px rgba(0, 0, 0, 0.1);
                        margin-bottom: 30px;
                    }}
                    
                    .room-content {{
                        padding: 30px;
                    }}
                    
                    .room-content h2 {{
                        font-size: 30px;
                        color: #0e2737;
                        margin-bottom: 5px;
                    }}
                    
                    /* Flight Timeline */
                    .flight-timeline {{
                        margin: 30px 0;
                    }}
                    
                    .flight-timeline .progress {{
                        height: 2px;
                        background-color: #ddd;
                    }}
                    
                    .flight-timeline .progress-bar {{
                        background-color: #0e2737;
                    }}
                    
                    .layover {{
                        position: relative;
                        padding: 10px 0;
                    }}
                    
                    .layover:before {{
                        content: "";
                        position: absolute;
                        width: 10px;
                        height: 10px;
                        background-color: #0e2737;
                        border-radius: 50%;
                        left: 50%;
                        top: 0;
                        transform: translateX(-50%);
                    }}
                    
                    /* Info Boxes */
                    .flight-info {{
                        background-color: #f9f9f9;
                        padding: 20px;
                        border-radius: 5px;
                    }}
                    
                    .flight-info h4 {{
                        margin-bottom: 15px;
                        color: #0e2737;
                    }}
                    
                    .flight-info i {{
                        color: #0e2737;
                        margin-right: 10px;
                        width: 16px;
                    }}
                    
                    /* Price Summary */
                    .hotel-reservation--area {{
                        margin-bottom: 50px;
                    }}
                    
                    .price-summary {{
                        background-color: #f9f9f9;
                        padding: 25px;
                        border-radius: 5px;
                    }}
                    
                    /* Buttons */
                    .palatin-btn {{
                        display: inline-block;
                        min-width: 160px;
                        height: 50px;
                        color: #ffffff;
                        border: none;
                        border-radius: 0;
                        padding: 0 30px;
                        font-size: 16px;
                        line-height: 50px;
                        background-color: #0e2737;
                        font-weight: 600;
                        text-decoration: none;
                        text-align: center;
                    }}
                    
                    .palatin-btn:hover {{
                        background-color: #ce8954;
                        color: #ffffff;
                    }}
                    
                    .btn-2 {{
                        background-color: transparent !important;
                        color: #0e2737 !important;
                        border: 1px solid #0e2737 !important;
                    }}
                    
                    .btn-2:hover {{
                        background-color: #0e2737 !important;
                        color: #fff !important;
                    }}
                    
                    /* Footer */
                    .footer-area {{
                        background-color: #0e2737;
                        color: white;
                        padding: 30px 0;
                        text-align: center;
                    }}
                    
                    .city-name {{ 
                        font-weight: bold; 
                        font-size: 1.2rem; 
                    }}
                    
                    .flight-segment {{
                        padding: 15px;
                        border-radius: 5px;
                        background-color: #f9f9f9;
                        margin-bottom: 15px;
                    }}
                </style>
            </head>
            <body>
                <!-- ##### Breadcumb Area Start ##### -->
                <section class="breadcumb-area bg-img d-flex align-items-center justify-content-center">
                    <div class="bradcumbContent">
                        <h2>Flight Details</h2>
                    </div>
                </section>
                <!-- ##### Breadcumb Area End ##### -->
                
                <!-- ##### Flight Details Area Start ##### -->
                <section class="section-padding-100">
                    <div class="container">
                        <div class="row">
                            <div class="col-12 col-lg-8">
                                <div class="single-room-area wow fadeInUp">
                                    <div class="room-content">
                                        <h2>Flight Itinerary</h2>
                                        <div class="line"></div>
                                        
                                        <!-- Outbound Flight -->
                                        <div class="flight-section mb-5">
                                            <h4 class="mb-4">Outbound Journey from {origin_city} to {dest_city}</h4>
                                            {outbound_segments_html}
                                        </div>
                                        
                                        <!-- Return Flight if applicable -->
                                        {return_journey_title}
                                        {return_segments_html}
                                        
                                        <!-- Flight Information -->
                                        <div class="flight-info mt-4">
                                            <div class="row mb-4">
                                                <div class="col-md-6">
                                                    <h4>Airline Information</h4>
                                                    <p><i class="fas fa-plane"></i> Airlines: {', '.join(airline_codes)}</p>
                                                    <p><i class="fas fa-tag"></i> Flight ID: {offer_id}</p>
                                                    <p><i class="fas fa-suitcase"></i> Baggage: 1 personal item + 1 carry-on</p>
                                                </div>
                                                <div class="col-md-6">
                                                    <h4>Flight Details</h4>
                                                    <p><i class="fas fa-clock"></i> Check-in: 2 hours before departure</p>
                                                    <p><i class="fas fa-ticket-alt"></i> Class: Economy</p>
                                                    <p><i class="fas fa-utensils"></i> Meal: Complimentary</p>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="col-12 col-lg-4">
                                <!-- Price Summary Card -->
                                <div class="hotel-reservation--area">
                                    <div class="mb-4">
                                        <h2>Price Summary</h2>
                                        <div class="line"></div>
                                    </div>
                                    
                                    <div class="price-summary">
                                        <div class="d-flex justify-content-between mb-2">
                                            <span>Base Fare:</span>
                                            <strong>${base_price:.2f}</strong>
                                        </div>
                                        <div class="d-flex justify-content-between mb-2">
                                            <span>Taxes & Fees:</span>
                                            <strong>${taxes:.2f}</strong>
                                        </div>
                                        <hr>
                                        <div class="d-flex justify-content-between mb-2">
                                            <span>Total Price:</span>
                                            <strong style="color: #0e2737;">${total_price:.2f}</strong>
                                        </div>
                                        <div class="d-flex justify-content-between mb-4">
                                            <span>Per Passenger:</span>
                                            <strong>${total_price:.2f}</strong>
                                        </div>
                                        
                                        <div class="text-center mb-4">
                                            <a href="{'/book-flight/' + offer_id + '/' if request.user.is_authenticated else '/login/'}" class="btn btn-primary btn-lg">Book Now</a>
                                            
                                            <!-- Add to Cart Button -->
                                            <a href="{'/cart/add-flight/?offer_id=' + offer_id + '&origin=' + origin_city + '&destination=' + dest_city + '&departure_date=' + (outbound_segments[0]['departure']['at'] if outbound_segments else '') + '&return_date=' + (return_segments[0]['departure']['at'] if return_segments else '') + '&airline=' + (airline_codes[0] if airline_codes else '') + '&flight_number=' + (outbound_segments[0]['number'] if outbound_segments else '') + '&price=' + str(total_price) + '&passengers=1&flight_class=ECONOMY&is_round_trip=' + str(len(return_segments) > 0) if request.user.is_authenticated else '/login/'}" class="btn btn-success btn-lg">Add to Cart</a>
                                        </div>
                                        
                                        <div class="price-details p-4 mb-4 border rounded bg-light">
                                            <h4>Price Details</h4>
                                            <div class="row">
                                                <div class="col-6"><p>Base Price:</p></div>
                                                <div class="col-6 text-end"><p>${base_price:.2f}</p></div>
                                            </div>
                                            <div class="row">
                                                <div class="col-6"><p>Taxes + Fees:</p></div>
                                                <div class="col-6 text-end"><p>${taxes:.2f}</p></div>
                                            </div>
                                            <div class="row border-top pt-2 fw-bold">
                                                <div class="col-6"><p>Total:</p></div>
                                                <div class="col-6 text-end"><p>${total_price:.2f} {currency}</p></div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                
                                <!-- Additional Info Card -->
                                <div class="mt-4">
                                    <h2>Important Information</h2>
                                    <div class="line"></div>
                                    
                                    <div class="flight-info mt-4">
                                        <h4>Fare Rules</h4>
                                        <ul>
                                            <li>Cancellation charges may apply</li>
                                            <li>Date changes subject to availability</li>
                                            <li>Non-refundable fare</li>
                                        </ul>
                                        
                                        <h4 class="mt-4">Baggage Policy</h4>
                                        <p>Checked baggage fees may apply. Please check with the airline for the most current baggage policy.</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </section>
                <!-- ##### Flight Details Area End ##### -->
                
                <!-- ##### Footer Area Start ##### -->
                <footer class="footer-area">
                    <div class="container">
                        <p>© 2023 The Palatin Travel | Flight ID: {offer_id}</p>
                    </div>
                </footer>
                <!-- ##### Footer Area End ##### -->
            </body>
            </html>
            """
            
            # Create direct HTML response
            response = HttpResponse(html_content)
            
            # Add aggressive anti-caching headers
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0, private'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
            
            return response
        except Exception as e:
            print(f"Error processing admin flight: {str(e)}")
            return render(request, 'flights/flights.html', {'error': "An error occurred while processing the flight details."})
    else:
        actual_flight_data = None

    # First try to get actual flight data from session
    
    try:
        flight_search_results_json = request.session.get('flight_search_results', '[]')
        flight_search_results = json.loads(flight_search_results_json)
        
        # Find the specific flight by ID
        for flight in flight_search_results:
            if str(flight.get('id')) == str(offer_id):
                actual_flight_data = flight
                print(f"Found matching flight in session: {offer_id}")
                break
    except Exception as e:
        print(f"Error retrieving flight data from session: {str(e)}")
    
    # Generate a unique color based on the flight ID for styling
    unique_number = sum(ord(c) for c in offer_id) % 1000
    bg_color = f"#{unique_number:06x}"[:7]
    
    # Default values in case we can't get actual data
    origin_city = "Origin City"
    dest_city = "Destination City"
    outbound_segments = []
    return_segments = []
    base_price = 0
    taxes = 0
    total_price = 0
    currency = "USD"
    airline_codes = []
    
    # Parse actual flight data if available
    if actual_flight_data:
        try:
            # Get price information
            if 'price' in actual_flight_data:
                price_data = actual_flight_data['price']
                base_price = float(price_data.get('base', '0'))
                taxes = float(price_data.get('taxes', '0'))
                total_price = float(price_data.get('total', '0'))
                currency = price_data.get('currency', 'USD')
            
            # Parse outbound journey (first itinerary)
            if 'itineraries' in actual_flight_data and len(actual_flight_data['itineraries']) > 0:
                outbound = actual_flight_data['itineraries'][0]
                if 'segments' in outbound:
                    outbound_segments = outbound['segments']
                    
                    # Get origin/destination from first and last segment
                    if len(outbound_segments) > 0:
                        first_segment = outbound_segments[0]
                        last_segment = outbound_segments[-1]
                        
                        origin_city = first_segment.get('departure', {}).get('iataCode', 'Origin')
                        dest_city = last_segment.get('arrival', {}).get('iataCode', 'Destination')
                        
                        # Collect airline codes
                        for seg in outbound_segments:
                            if 'carrierCode' in seg and seg['carrierCode'] not in airline_codes:
                                airline_codes.append(seg['carrierCode'])
            
            # Parse return journey (second itinerary if exists)
            if 'itineraries' in actual_flight_data and len(actual_flight_data['itineraries']) > 1:
                return_journey = actual_flight_data['itineraries'][1]
                if 'segments' in return_journey:
                    return_segments = return_journey['segments']
                    
                    # Collect airline codes
                    for seg in return_segments:
                        if 'carrierCode' in seg and seg['carrierCode'] not in airline_codes:
                            airline_codes.append(seg['carrierCode'])
        
        except Exception as e:
            print(f"Error parsing flight data: {str(e)}")
    
    # Create outbound segments HTML
    outbound_segments_html = ""
    if outbound_segments:
        for i, segment in enumerate(outbound_segments):
            dep_iata = segment.get('departure', {}).get('iataCode', '')
            arr_iata = segment.get('arrival', {}).get('iataCode', '')
            dep_time = segment.get('departure', {}).get('at', '')
            arr_time = segment.get('arrival', {}).get('at', '')
            carrier = segment.get('carrierCode', '')
            flight_number = segment.get('number', '')
            
            # Format times
            formatted_dep_time = "Time N/A"
            formatted_arr_time = "Time N/A"
            if dep_time:
                try:
                    dt = datetime.fromisoformat(dep_time.replace('Z', '+00:00'))
                    formatted_dep_time = dt.strftime("%I:%M %p")
                except:
                    pass
                    
            if arr_time:
                try:
                    dt = datetime.fromisoformat(arr_time.replace('Z', '+00:00'))
                    formatted_arr_time = dt.strftime("%I:%M %p")
                except:
                    pass
            
            # Create segment HTML
            outbound_segments_html += f"""
            <div class="d-flex justify-content-between align-items-center mb-3 p-3 bg-light rounded">
                <div>
                    <div class="city-name">{dep_iata}</div>
                    <p>{formatted_dep_time}</p>
                </div>
                <div class="flight-arrow">
                    <p class="mb-0 small">Flight {carrier}{flight_number}</p>
                    <p>✈️ ────────</p>
                </div>
                <div>
                    <div class="city-name">{arr_iata}</div>
                    <p>{formatted_arr_time}</p>
                </div>
            </div>
            """
            
            # Add connection indicator if there are more segments
            if i < len(outbound_segments) - 1:
                outbound_segments_html += f"""
                <div class="text-center mb-3">
                    <span class="badge bg-warning text-dark p-2">Connection at {arr_iata}</span>
                </div>
                """
    else:
        # Fallback if no segments are available
        outbound_segments_html = f"""
        <div class="d-flex justify-content-between align-items-center mb-3 p-3 bg-light rounded">
            <div>
                <div class="city-name">{origin_city}</div>
                <p>8:00 AM</p>
            </div>
            <div class="flight-arrow">
                <i class="fa fa-plane"></i> ✈️ ────────
            </div>
            <div>
                <div class="city-name">{dest_city}</div>
                <p>11:20 AM</p>
            </div>
        </div>
        """
    
    # Create return segments HTML
    return_segments_html = ""
    if return_segments:
        for i, segment in enumerate(return_segments):
            dep_iata = segment.get('departure', {}).get('iataCode', '')
            arr_iata = segment.get('arrival', {}).get('iataCode', '')
            dep_time = segment.get('departure', {}).get('at', '')
            arr_time = segment.get('arrival', {}).get('at', '')
            carrier = segment.get('carrierCode', '')
            flight_number = segment.get('number', '')
            
            # Format times
            formatted_dep_time = "Time N/A"
            formatted_arr_time = "Time N/A"
            if dep_time:
                try:
                    dt = datetime.fromisoformat(dep_time.replace('Z', '+00:00'))
                    formatted_dep_time = dt.strftime("%I:%M %p")
                except:
                    pass
                    
            if arr_time:
                try:
                    dt = datetime.fromisoformat(arr_time.replace('Z', '+00:00'))
                    formatted_arr_time = dt.strftime("%I:%M %p")
                except:
                    pass
            
            # Create segment HTML
            return_segments_html += f"""
            <div class="d-flex justify-content-between align-items-center mb-3 p-3 bg-light rounded">
                <div>
                    <div class="city-name">{dep_iata}</div>
                    <p>{formatted_dep_time}</p>
                </div>
                <div class="flight-arrow">
                    <p class="mb-0 small">Flight {carrier}{flight_number}</p>
                    <p>✈️ ────────</p>
                </div>
                <div>
                    <div class="city-name">{arr_iata}</div>
                    <p>{formatted_arr_time}</p>
                </div>
            </div>
            """
            
            # Add connection indicator if there are more segments
            if i < len(return_segments) - 1:
                return_segments_html += f"""
                <div class="text-center mb-3">
                    <span class="badge bg-warning text-dark p-2">Connection at {arr_iata}</span>
                </div>
                """
    else:
        # Only show return journey if there are return segments
        return_segments_html = "" if not actual_flight_data or len(actual_flight_data.get('itineraries', [])) <= 1 else f"""
        <h4>Return Journey</h4>
        <div class="d-flex justify-content-between align-items-center p-3 bg-light rounded">
            <div>
                <div class="city-name">{dest_city}</div>
                <p>1:00 PM</p>
            </div>
            <div class="flight-arrow">
                <i class="fa fa-plane"></i> ✈️ ────────
            </div>
            <div>
                <div class="city-name">{origin_city}</div>
                <p>5:30 PM</p>
            </div>
        </div>
        """
    
    # Return journey title - only show if there are return segments
    return_journey_title = "<h4>Return Journey</h4>" if return_segments else ""
    
    # Create a completely unique HTML response for each flight ID using actual data
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Flight Details - Bookify</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">
        <style>
            /* Palatin Theme Styles */
            body {{ 
                font-family: 'Helvetica', Arial, sans-serif;
                color: #333; 
                background-color: #f5f5f5;
            }}
            
            /* Breadcrumb Area */
            .breadcumb-area {{
                position: relative;
                height: 280px;
                background-color: #0e2737;  
                z-index: 1;
            }}
            
            .breadcumb-area::after {{
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(14, 39, 55, 0.7);
                z-index: -1;
            }}
            
            .bradcumbContent {{
                text-align: center;
                padding: 50px;
            }}
            
            .bradcumbContent h2 {{
                font-size: 42px;
                color: white;
                font-weight: 700;
            }}
            
            /* Content Areas */
            .section-padding-100 {{
                padding: 100px 0;
            }}
            
            .line {{
                width: 100px;
                height: 2px;
                background-color: #ce8954;
                margin: 15px 0 30px;
            }}
            
            .single-room-area {{
                background-color: white;
                box-shadow: 0 2px 15px rgba(0, 0, 0, 0.1);
                margin-bottom: 30px;
            }}
            
            .room-content {{
                padding: 30px;
            }}
            
            .room-content h2 {{
                font-size: 30px;
                color: #0e2737;
                margin-bottom: 5px;
            }}
            
            /* Flight Timeline */
            .flight-timeline {{
                margin: 30px 0;
            }}
            
            .flight-timeline .progress {{
                height: 2px;
                background-color: #ddd;
            }}
            
            .flight-timeline .progress-bar {{
                background-color: #0e2737;
            }}
            
            .layover {{
                position: relative;
                padding: 10px 0;
            }}
            
            .layover:before {{
                content: "";
                position: absolute;
                width: 10px;
                height: 10px;
                background-color: #0e2737;
                border-radius: 50%;
                left: 50%;
                top: 0;
                transform: translateX(-50%);
            }}
            
            /* Info Boxes */
            .flight-info {{
                background-color: #f9f9f9;
                padding: 20px;
                border-radius: 5px;
            }}
            
            .flight-info h4 {{
                margin-bottom: 15px;
                color: #0e2737;
            }}
            
            .flight-info i {{
                color: #0e2737;
                margin-right: 10px;
                width: 16px;
            }}
            
            /* Price Summary */
            .hotel-reservation--area {{
                margin-bottom: 50px;
            }}
            
            .price-summary {{
                background-color: #f9f9f9;
                padding: 25px;
                border-radius: 5px;
            }}
            
            /* Buttons */
            .palatin-btn {{
                display: inline-block;
                min-width: 160px;
                height: 50px;
                color: #ffffff;
                border: none;
                border-radius: 0;
                padding: 0 30px;
                font-size: 16px;
                line-height: 50px;
                background-color: #0e2737;
                font-weight: 600;
                text-decoration: none;
                text-align: center;
            }}
            
            .palatin-btn:hover {{
                background-color: #ce8954;
                color: #ffffff;
            }}
            
            .btn-2 {{
                background-color: transparent !important;
                color: #0e2737 !important;
                border: 1px solid #0e2737 !important;
            }}
            
            .btn-2:hover {{
                background-color: #0e2737 !important;
                color: #fff !important;
            }}
            
            /* Footer */
            .footer-area {{
                background-color: #0e2737;
                color: white;
                padding: 30px 0;
                text-align: center;
            }}
            
            .city-name {{ 
                font-weight: bold; 
                font-size: 1.2rem; 
            }}
            
            .flight-segment {{
                padding: 15px;
                border-radius: 5px;
                background-color: #f9f9f9;
                margin-bottom: 15px;
            }}
        </style>
    </head>
    <body>
        <!-- ##### Breadcumb Area Start ##### -->
        <section class="breadcumb-area bg-img d-flex align-items-center justify-content-center">
            <div class="bradcumbContent">
                <h2>Flight Details</h2>
            </div>
        </section>
        <!-- ##### Breadcumb Area End ##### -->
        
        <!-- ##### Flight Details Area Start ##### -->
        <section class="section-padding-100">
            <div class="container">
                <div class="row">
                    <div class="col-12 col-lg-8">
                        <div class="single-room-area wow fadeInUp">
                            <div class="room-content">
                                <h2>Flight Itinerary</h2>
                                <div class="line"></div>
                                
                                <!-- Outbound Flight -->
                                <div class="flight-section mb-5">
                                    <h4 class="mb-4">Outbound Journey from {origin_city} to {dest_city}</h4>
                                    {outbound_segments_html}
                                </div>
                                
                                <!-- Return Flight if applicable -->
                                {return_journey_title}
                                {return_segments_html}
                                
                                <!-- Flight Information -->
                                <div class="flight-info mt-4">
                                    <div class="row mb-4">
                                        <div class="col-md-6">
                                            <h4>Airline Information</h4>
                                            <p><i class="fas fa-plane"></i> Airlines: {', '.join(airline_codes)}</p>
                                            <p><i class="fas fa-tag"></i> Flight ID: {offer_id}</p>
                                            <p><i class="fas fa-suitcase"></i> Baggage: 1 personal item + 1 carry-on</p>
                                        </div>
                                        <div class="col-md-6">
                                            <h4>Flight Details</h4>
                                            <p><i class="fas fa-clock"></i> Check-in: 2 hours before departure</p>
                                            <p><i class="fas fa-ticket-alt"></i> Class: Economy</p>
                                            <p><i class="fas fa-utensils"></i> Meal: Complimentary</p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-12 col-lg-4">
                        <!-- Price Summary Card -->
                        <div class="hotel-reservation--area">
                            <div class="mb-4">
                                <h2>Price Summary</h2>
                                <div class="line"></div>
                            </div>
                            
                            <div class="price-summary">
                                <div class="d-flex justify-content-between mb-2">
                                    <span>Base Fare:</span>
                                    <strong>${base_price:.2f}</strong>
                                </div>
                                <div class="d-flex justify-content-between mb-2">
                                    <span>Taxes & Fees:</span>
                                    <strong>${taxes:.2f}</strong>
                                </div>
                                <hr>
                                <div class="d-flex justify-content-between mb-2">
                                    <span>Total Price:</span>
                                    <strong style="color: #0e2737;">${total_price:.2f}</strong>
                                </div>
                                <div class="d-flex justify-content-between mb-4">
                                    <span>Per Passenger:</span>
                                    <strong>${total_price:.2f}</strong>
                                </div>
                                
                                <div class="text-center mb-4">
                                    <a href="{'/book-flight/' + offer_id + '/' if request.user.is_authenticated else '/login/'}" class="btn btn-primary btn-lg">Book Now</a>
                                    
                                    <!-- Add to Cart Button -->
                                    <a href="{'/cart/add-flight/?offer_id=' + offer_id + '&origin=' + origin_city + '&destination=' + dest_city + '&departure_date=' + (outbound_segments[0]['departure']['at'] if outbound_segments else '') + '&return_date=' + (return_segments[0]['departure']['at'] if return_segments else '') + '&airline=' + (airline_codes[0] if airline_codes else '') + '&flight_number=' + (outbound_segments[0]['number'] if outbound_segments else '') + '&price=' + str(total_price) + '&passengers=1&flight_class=ECONOMY&is_round_trip=' + str(len(return_segments) > 0) if request.user.is_authenticated else '/login/'}" class="btn btn-success btn-lg">Add to Cart</a>
                                </div>
                                
                                <div class="price-details p-4 mb-4 border rounded bg-light">
                                    <h4>Price Details</h4>
                                    <div class="row">
                                        <div class="col-6"><p>Base Price:</p></div>
                                        <div class="col-6 text-end"><p>${base_price:.2f}</p></div>
                                    </div>
                                    <div class="row">
                                        <div class="col-6"><p>Taxes + Fees:</p></div>
                                        <div class="col-6 text-end"><p>${taxes:.2f}</p></div>
                                    </div>
                                    <div class="row border-top pt-2 fw-bold">
                                        <div class="col-6"><p>Total:</p></div>
                                        <div class="col-6 text-end"><p>${total_price:.2f} {currency}</p></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Additional Info Card -->
                        <div class="mt-4">
                            <h2>Important Information</h2>
                            <div class="line"></div>
                            
                            <div class="flight-info mt-4">
                                <h4>Fare Rules</h4>
                                <ul>
                                    <li>Cancellation charges may apply</li>
                                    <li>Date changes subject to availability</li>
                                    <li>Non-refundable fare</li>
                                </ul>
                                
                                <h4 class="mt-4">Baggage Policy</h4>
                                <p>Checked baggage fees may apply. Please check with the airline for the most current baggage policy.</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>
        <!-- ##### Flight Details Area End ##### -->
        
        <!-- ##### Footer Area Start ##### -->
        <footer class="footer-area">
            <div class="container">
                <p>© 2023 The Palatin Travel | Flight ID: {offer_id}</p>
            </div>
        </footer>
        <!-- ##### Footer Area End ##### -->
    </body>
    </html>
    """
    
    # Create direct HTML response
    response = HttpResponse(html_content)
    
    # Add aggressive anti-caching headers
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0, private'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    
    return response

@login_required
def book_flight(request, offer_id):
    """View for booking a selected flight offer"""
    # This would be implemented to create a booking with the Amadeus API
    # For now, we'll just render a booking form template
    
    context = {
        'offer_id': offer_id,
        'error': None
    }
    
    if request.method == 'POST':
        # This would process the booking form
        # For now, just redirect to a confirmation page
        return redirect('booking_confirmed')
    
    return render(request, 'flights/book_flight.html', context)

@login_required
def booking_confirmed(request):
    """Confirmation page after successful booking"""
    return render(request, 'flights/booking_confirmed.html')

@login_required
def my_bookings(request):
    """View for displaying a user's flight bookings"""
    # Get the user's bookings from the database
    bookings = request.user.flight_bookings.all().order_by('-booking_date')
    
    context = {
        'bookings': bookings
    }
    
    return render(request, 'flights/my_bookings.html', context)

def search_airport(request):
    """AJAX endpoint for searching airports by name"""
    query = request.GET.get('q', '')
    
    if not query or len(query) < 2:
        return JsonResponse({'success': False, 'error': 'Query too short'})
    
    flight_service = AmadeusFlightService()
    results = flight_service.search_airport_city_code(query)
    
    return JsonResponse(results)
