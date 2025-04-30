"""
Test script to verify hotel search and image fetching functionality
"""

# Import Django settings (required to use Django models and modules)
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project1.settings')
django.setup()

# Import the AmadeusHotelService
from app1.services import AmadeusHotelService

def test_hotel_search_with_images():
    """Test hotel search with image fetching"""
    # Create the service
    hotel_service = AmadeusHotelService()
    
    # Search parameters
    city_code = "LON"  # London
    
    # Use current dates (today + 1 day, today + 3 days)
    from datetime import datetime, timedelta
    today = datetime.today()
    check_in_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    check_out_date = (today + timedelta(days=3)).strftime("%Y-%m-%d")
    
    adults = 2
    
    print(f"Searching for hotels in {city_code} from {check_in_date} to {check_out_date} for {adults} adults")
    
    # Search for hotels
    results = hotel_service.search_hotels(
        city_code=city_code,
        check_in_date=check_in_date,
        check_out_date=check_out_date,
        adults=adults
    )
    
    if not results['success']:
        print(f"Search failed: {results.get('error', 'Unknown error')}")
        return False
    
    print(f"Search successful, found {len(results['data'])} hotels")
    
    # Check if images were retrieved
    hotels_with_images = 0
    for i, hotel_data in enumerate(results['data'][:5]):  # Check first 5 hotels only
        hotel_name = hotel_data['hotel']['name']
        has_image = 'image_url' in hotel_data['hotel']
        image_url = hotel_data['hotel'].get('image_url', 'None')
        
        print(f"Hotel #{i+1}: {hotel_name}")
        print(f"  Has image: {has_image}")
        print(f"  Image URL: {image_url}")
        
        if has_image:
            hotels_with_images += 1
    
    print(f"\nSummary: {hotels_with_images} out of 5 hotels have images")
    
    return hotels_with_images > 0

if __name__ == "__main__":
    print("Testing hotel search with image fetching...")
    test_hotel_search_with_images() 