import requests
import time

def get_hotel_image(hotel_name, city_name, country_code=""):
    """Get a hotel image from Unsplash API"""
    try:
        start_time = time.time()
        
        # Unsplash access key
        access_key = "SNtY2c5K46dhFWrFVlQxZoLFStpTGkfV851LEZtHx7c"
        
        # Clean the hotel name (remove chain names like "Best Western" for better results)
        hotel_query = hotel_name
        for chain in ["Hotel", "Inn", "Suites", "Resort", "Best Western", "Hilton", "Marriott"]:
            hotel_query = hotel_query.replace(chain, "").strip()
            
        if not hotel_query:
            hotel_query = hotel_name
        
        # Create search query
        query = f"{hotel_query} hotel {city_name}"
        print(f"Searching Unsplash for: {query}")
        
        # Call Unsplash API
        url = "https://api.unsplash.com/search/photos"
        params = {
            "query": query,
            "per_page": 1,
            "client_id": access_key
        }
        
        print(f"Making Unsplash API request to: {url}")
        print(f"Request params: {params}")
        
        # Add timeout to prevent hanging
        response = requests.get(url, params=params, timeout=10)
        request_time = time.time() - start_time
        
        print(f"Unsplash API response status: {response.status_code} (took {request_time:.2f}s)")
        
        # Check rate limit
        if response.status_code == 429:  # Too Many Requests
            print("Unsplash rate limit reached")
            return None
        
        if response.status_code != 200:
            print(f"Unsplash API error: {response.status_code} - {response.text}")
            return None
            
        data = response.json()
        total_results = data.get('total', 0)
        print(f"Unsplash found {total_results} results for query: {query}")
        
        # Return image URL if found
        if data.get("results") and len(data["results"]) > 0:
            image_url = data["results"][0]["urls"]["regular"]
            print(f"Found image for {hotel_name}: {image_url}")
            return image_url
        
        # Try with just the city if specific hotel not found
        print(f"No specific hotel image found, trying generic: hotel {city_name}")
        params["query"] = f"hotel {city_name}"
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code != 200:
            print(f"Unsplash API error on generic search: {response.status_code} - {response.text}")
            return None
            
        data = response.json()
        total_results = data.get('total', 0)
        print(f"Unsplash found {total_results} results for generic query: hotel {city_name}")
        
        if data.get("results") and len(data["results"]) > 0:
            image_url = data["results"][0]["urls"]["regular"]
            print(f"Found generic hotel image for {city_name}: {image_url}")
            return image_url
            
    except requests.exceptions.Timeout:
        print(f"Unsplash API request timed out after 10 seconds")
        return None
    except requests.exceptions.ConnectionError:
        print(f"Connection error when accessing Unsplash API")
        return None
    except Exception as e:
        print(f"Error getting Unsplash image: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # Return None if no image found or error occurred
    print(f"No image found for {hotel_name} in {city_name}")
    return None 