from amadeus import Client, ResponseError
import os
from datetime import datetime, timedelta
import json

class AmadeusFlightService:
    def __init__(self):
        # Using the same Amadeus API credentials
        self.amadeus = Client(
            client_id='ADoADdFzddxkNZz9JhITZUJ0UCp5uZvu',
            client_secret='En3Inj6haN7MyLgt',
            hostname='test'  # Use test environment for development
        )
        print("Initializing Amadeus client for flight service with test environment")
    
    def search_flights(self, origin, destination, departure_date, return_date=None, adults=1):
        """
        Search for flights between origin and destination
        
        Args:
            origin (str): IATA airport or city code
            destination (str): IATA airport or city code
            departure_date (str): Departure date in YYYY-MM-DD format
            return_date (str, optional): Return date in YYYY-MM-DD format for round trips
            adults (int): Number of adult passengers
            
        Returns:
            dict: Flight search results or error message
        """
        try:
            print(f"Searching flights: {origin} to {destination}, departure: {departure_date}, return: {return_date}, adults: {adults}")
            
            # Base request parameters
            search_params = {
                'originLocationCode': origin,
                'destinationLocationCode': destination,
                'departureDate': departure_date,
                'adults': adults,
                'max': 20,  # Max results to return
                'currencyCode': 'USD'
            }
            
            # Add return date if provided (round trip)
            if return_date:
                search_params['returnDate'] = return_date
            
            # Call the Flight Offers Search API
            flight_offers = self.amadeus.shopping.flight_offers_search.get(**search_params)
            
            print(f"Found {len(flight_offers.data)} flight offers")
            
            if flight_offers.data:
                # Process flight results to enhance them
                enhanced_results = []
                for offer in flight_offers.data:
                    # Add the offer to our enhanced results
                    enhanced_results.append(offer)
                
                # The Response object doesn't have .get() method, use a different approach
                dictionaries = {}
                try:
                    # Try to access dictionaries if it exists in the response
                    if hasattr(flight_offers, 'dictionaries'):
                        dictionaries = flight_offers.dictionaries
                except:
                    # If we can't access it, just return an empty dict
                    dictionaries = {}
                
                return {
                    'success': True,
                    'data': enhanced_results,
                    'dictionaries': dictionaries
                }
            else:
                return {
                    'success': False,
                    'error': f"No flights found from {origin} to {destination} on the selected dates."
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
    
    def get_flight_offer_price(self, offer):
        """
        Get the flight offer price, which includes additional pricing details
        
        Args:
            offer (dict): The flight offer data
            
        Returns:
            dict: Flight offer price or error message
        """
        try:
            print(f"Getting detailed pricing for flight offer")
            
            # Convert the offer to proper format for the API
            if isinstance(offer, str):
                # If it's a string, assume it's already JSON
                offer_data = offer
            else:
                # Otherwise convert the dict to JSON string
                offer_data = json.dumps(offer)
            
            # Call the Flight Offers Price API
            price_response = self.amadeus.shopping.flight_offers.pricing.post(
                flightOffers=[offer]
            )
            
            if price_response.data:
                return {
                    'success': True,
                    'data': price_response.data
                }
            else:
                return {
                    'success': False,
                    'error': "No pricing information available for this flight."
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
    
    def search_airport_city_code(self, query):
        """
        Search for IATA city or airport code based on user query
        
        Args:
            query (str): City or airport name query
            
        Returns:
            dict: List of matching locations with codes
        """
        try:
            print(f"Searching for IATA code for: {query}")
            
            # Call the Airport & City Search API
            locations = self.amadeus.reference_data.locations.get(
                keyword=query,
                subType=["AIRPORT", "CITY"]
            )
            
            print(f"Found {len(locations.data)} matching locations")
            
            if locations.data:
                # Format the results
                formatted_locations = []
                for location in locations.data:
                    # Extract the important details
                    formatted_location = {
                        'name': location.get('name', ''),
                        'iataCode': location.get('iataCode', ''),
                        'subType': location.get('subType', ''),
                        'address': {}
                    }
                    
                    # Extract address details if available
                    if 'address' in location:
                        address = location['address']
                        formatted_location['address'] = {
                            'cityName': address.get('cityName', ''),
                            'countryName': address.get('countryName', ''),
                        }
                    
                    formatted_locations.append(formatted_location)
                
                return {
                    'success': True,
                    'data': formatted_locations
                }
            else:
                return {
                    'success': False,
                    'error': f"No locations found matching '{query}'."
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