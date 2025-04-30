from amadeus import Client, ResponseError
import os
from datetime import datetime, timedelta
import sys
import importlib.util
import os.path

# Try different import approaches
try:
    from .image_service import get_hotel_image  # Try relative import
except ImportError:
    try:
        from app1.image_service import get_hotel_image  # Try absolute import
    except ImportError:
        # Manual import if the module is not found
        image_service_path = os.path.join(os.path.dirname(__file__), 'image_service.py')
        if os.path.exists(image_service_path):
            print(f"Manually importing from {image_service_path}")
            spec = importlib.util.spec_from_file_location("image_service", image_service_path)
            image_service = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(image_service)
            get_hotel_image = image_service.get_hotel_image
        else:
            print("WARNING: Could not import image_service module, hotel images will not be available")
            def get_hotel_image(hotel_name, city_name, country_code=""):
                return None

class AmadeusHotelService:
    def __init__(self):
        # Using the provided Amadeus API credentials with test environment
        self.amadeus = Client(
            client_id='ADoADdFzddxkNZz9JhITZUJ0UCp5uZvu',
            client_secret='En3Inj6haN7MyLgt',
            hostname='test'  # Use test environment for development
        )
        print("Initializing Amadeus client with test environment")
    
    # Let's look at the search_hotels method in AmadeusHotelService
    def search_hotels(self, city_code, check_in_date, check_out_date, adults):
        """
        Search for hotels in a city
        
        Args:
            city_code (str): IATA city code
            check_in_date (str): Check-in date in YYYY-MM-DD format
            check_out_date (str): Check-out date in YYYY-MM-DD format
            adults (int): Number of adults
            
        Returns:
            dict: Hotel search results or error message
        """
        try:
            print(f"Searching hotels with: city={city_code}, check_in={check_in_date}, check_out={check_out_date}, adults={adults}")
            
            # The API now requires different parameters
            # First get a list of hotel IDs in the city
            location_response = self.amadeus.reference_data.locations.hotels.by_city.get(
                cityCode=city_code
            )
            
            if not location_response.data:
                print(f"No hotels found in city: {city_code}")
                return {
                    'success': False,
                    'error': f"No hotels found in {city_code}"
                }
            
            # Log total hotels found
            print(f"Total hotels found in {city_code}: {len(location_response.data)}")
                
            # Extract hotel IDs (increased from 20 to 100)
            hotel_ids = [hotel['hotelId'] for hotel in location_response.data[:100]]
            print(f"Using {len(hotel_ids)} hotels in {city_code} for offer search")
            
            # Now search for offers with these hotel IDs
            # Process in smaller batches to avoid API limits (25 hotels per request)
            all_offers = []
            batch_size = 25
            
            for i in range(0, len(hotel_ids), batch_size):
                batch = hotel_ids[i:i+batch_size]
                print(f"Searching offers for batch {i//batch_size + 1} with {len(batch)} hotels")
                
                try:
                    # Enhanced API call with more details
                    hotel_offers = self.amadeus.shopping.hotel_offers_search.get(
                        hotelIds=','.join(batch),
                        checkInDate=check_in_date,
                        checkOutDate=check_out_date,
                        adults=adults,
                        currency='USD',
                        roomQuantity=1,
                        priceRange='50-5000',
                        includeClosed=False,
                        bestRateOnly=False,  # Get multiple room types
                        sort='PRICE',
                        view='FULL',  # Get complete details
                        includeHotelAmenities=True  # Get amenities and services
                    )
                    
                    if hotel_offers.data:
                        all_offers.extend(hotel_offers.data)
                        print(f"Found {len(hotel_offers.data)} offers in batch {i//batch_size + 1}")
                except Exception as batch_error:
                    print(f"Error in batch {i//batch_size + 1}: {str(batch_error)}")
                    # Continue with next batch even if this one fails
                    continue
            
            print(f"Successfully retrieved {len(all_offers)} total hotel offers")
            
            if not all_offers:
                return {
                    'success': False,
                    'error': f"No available hotel offers found for {city_code} on these dates"
                }
                
            # Enhance hotel data with images from Unsplash
            for hotel_data in all_offers:
                try:
                    if 'hotel' in hotel_data:
                        hotel = hotel_data['hotel']
                        hotel_name = hotel.get('name', '')
                        
                        # Try to extract city from address
                        city_name = city_code
                        country_code = ''
                        
                        if 'address' in hotel:
                            address = hotel['address']
                            if 'cityName' in address:
                                city_name = address['cityName']
                            if 'countryCode' in address:
                                country_code = address['countryCode']
                        
                        if hotel_name:
                            print(f"Fetching image for hotel: {hotel_name} in {city_name}")
                            # Get image for this hotel
                            image_url = get_hotel_image(hotel_name, city_name, country_code)
                            if image_url:
                                print(f"✓ Found image for {hotel_name}: {image_url}")
                                # Add the image URL to the hotel data
                                hotel_data['hotel']['image_url'] = image_url
                            else:
                                print(f"✗ No image found for {hotel_name}")
                        else:
                            print("Hotel name is missing")
                    else:
                        print("Hotel data is missing the 'hotel' field")
                except Exception as e:
                    print(f"Error processing hotel image: {str(e)}")
                    continue
            
            return {
                'success': True,
                'data': all_offers
            }
            
        except ResponseError as error:
            print(f"Amadeus API error: {error.response.body}")
            return {
                'success': False,
                'error': error.response.body
            }
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_hotel_offers(self, hotel_id, check_in_date, check_out_date, adults=1):
        """
        Get offers for a specific hotel
        
        Args:
            hotel_id (str): Amadeus hotel ID
            check_in_date (str): Check-in date in YYYY-MM-DD format
            check_out_date (str): Check-out date in YYYY-MM-DD format
            adults (int): Number of adults
            
        Returns:
            dict: Hotel offers or error message
        """
        try:
            print(f"Getting hotel offers for hotel ID: {hotel_id}")
            print(f"Parameters: check_in={check_in_date}, check_out={check_out_date}, adults={adults}")
            
            # For test environment, limit dates to within the next 6 months
            today = datetime.today()
            max_future_date = today + timedelta(days=180)  # 6 months
            
            check_in_obj = datetime.strptime(check_in_date, "%Y-%m-%d")
            check_out_obj = datetime.strptime(check_out_date, "%Y-%m-%d")
            
            # If dates are too far in the future, adjust them to be within the next week
            if check_in_obj > max_future_date or check_out_obj > max_future_date:
                print(f"Warning: Dates are too far in the future, adjusting to next available dates")
                new_check_in = today + timedelta(days=1)  # tomorrow
                new_check_out = today + timedelta(days=3)  # 2 days after tomorrow
                check_in_date = new_check_in.strftime("%Y-%m-%d")
                check_out_date = new_check_out.strftime("%Y-%m-%d")
                print(f"Adjusted dates: check_in={check_in_date}, check_out={check_out_date}")
            
            # Use hotel_offers_search instead of hotel_offers_by_hotel
            hotel_offers = self.amadeus.shopping.hotel_offers_search.get(
                hotelIds=hotel_id,  # Use hotelIds (plural) with a single hotel ID
                checkInDate=check_in_date,
                checkOutDate=check_out_date,
                adults=adults,
                currency='USD',
                roomQuantity=1,
                view='FULL',  # Get complete details
                includeHotelAmenities=True  # Get amenities and services
            )
            
            print(f"Successfully retrieved hotel offers for {hotel_id}")
            
            # The response structure is different - we need to extract the first hotel
            if hotel_offers.data and len(hotel_offers.data) > 0:
                return {
                    'success': True,
                    'data': hotel_offers.data[0]  # Return the first hotel's data
                }
            else:
                return {
                    'success': False,
                    'error': f"No offers available for hotel {hotel_id} on the selected dates."
                }
            
        except ResponseError as error:
            error_body = error.response.body
            print(f"Amadeus API error in get_hotel_offers: {error_body}")
            
            # Try to extract a more specific error message
            error_message = "Failed to fetch hotel details."
            try:
                if isinstance(error_body, dict) and 'errors' in error_body:
                    for err in error_body['errors']:
                        if 'detail' in err:
                            error_message = f"API error: {err['detail']}"
                            break
            except:
                pass
                
            return {
                'success': False,
                'error': error_message,
                'detailed_error': error_body
            }
        except Exception as e:
            print(f"Unexpected error in get_hotel_offers: {str(e)}")
            return {
                'success': False,
                'error': f"Error: {str(e)}"
            }
    
    def get_hotel_offer_details(self, offer_id):
        """
        Get detailed information about a specific hotel offer
        
        Args:
            offer_id (str): Amadeus offer ID
            
        Returns:
            dict: Hotel offer details or error message
        """
        try:
            print(f"Getting hotel offer details for offer ID: {offer_id}")
            # Get details for the specific offer - corrected method call
            offer_details = self.amadeus.shopping.hotel_offer(offer_id).get()
            
            return {
                'success': True,
                'data': offer_details.data
            }
            
        except ResponseError as error:
            print(f"Amadeus API error in get_hotel_offer_details: {error.response.body}")
            return {
                'success': False,
                'error': error.response.body
            }
        except Exception as e:
            print(f"Unexpected error in get_hotel_offer_details: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def search_city_code(self, city_name):
        """
        Search for IATA city code by city name
        
        Args:
            city_name (str): Name of the city
            
        Returns:
            str: IATA city code or None if not found
        """
        try:
            # Handle direct city code input (3-letter codes like LON, NYC)
            if len(city_name) == 3:
                return city_name.upper()  # Always uppercase city codes
                
            # Search for locations matching the city name
            print(f"Searching for city code for: {city_name}")
            response = self.amadeus.reference_data.locations.get(
                keyword=city_name,
                subType='CITY'
            )
            
            # Return the first city code found
            if response.data:
                code = response.data[0]['iataCode']
                print(f"Found city code: {code}")
                return code
            print(f"No city code found for: {city_name}")
            return None
            
        except ResponseError as error:
            print(f"Error in city code search: {error.response.body}")
            return None
        except Exception as e:
            print(f"Unexpected error in city code search: {str(e)}")
            return None