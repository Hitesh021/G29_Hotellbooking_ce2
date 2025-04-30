import requests

def test_unsplash_api():
    """Test function to verify Unsplash API is working"""
    access_key = "SNtY2c5K46dhFWrFVlQxZoLFStpTGkfV851LEZtHx7c"
    
    url = "https://api.unsplash.com/search/photos"
    params = {
        "query": "hotel London",
        "per_page": 1,
        "client_id": access_key
    }
    
    print("Making API request to Unsplash...")
    response = requests.get(url, params=params)
    
    print(f"Response status code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Total results found: {data.get('total', 0)}")
        
        if data.get("results") and len(data["results"]) > 0:
            image_url = data["results"][0]["urls"]["regular"]
            print(f"Found image: {image_url}")
            print("API TEST SUCCESSFUL!")
            return True
        else:
            print("No images found in results.")
    else:
        print(f"API Error: {response.text}")
    
    return False

if __name__ == "__main__":
    print("Running Unsplash API test...")
    test_unsplash_api() 