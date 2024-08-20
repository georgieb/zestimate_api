import folium
import os
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the API key from the environment variables
api_key = os.getenv("API_KEY")

if not api_key:
    raise ValueError("API_KEY not found in the .env file.")

# Check if API key is present
if api_key is None:
    raise ValueError("API_KEY is not set in the .env file.")

# Define the API URL
api_url = "https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates"


# List of ZPIDs
zpid_list = [
         "44158191", "43994986", "44106066", "62936198", "44106160", "43996214", "44154066", "43807923",
         "44105747", "43995191", "44107037", "62937284", "44151347", "44118156", "44160521", "44062156",
         "62936150", "62936164", "62937229", "44113047", "44113615", "43970389", "44063932", "43994966",
         "62937274", "43996838", "43996656", "44109256", "62933595", "44109202", "62937053", "62937149",
         "62936274", "62937287", "43995934", "44117834", "44122119", "44117891", "62937147", "62935928",
         "43972756", "44114467", "62936338", "44118194", "44113703", "44152032", "62936373", "62936341",
         "62936265", "44112792", "62937177", "44112873", "44117674", "44101389", "43993403", "44112911",
         "44151332", "44117786", "43993290", "44063896"
]

# Initialize a list to store marker locations
marker_locations = []

# Split the ZPID list into batches of 8
batch_size = 8
for i in range(0, len(zpid_list), batch_size):
    batch = zpid_list[i:i + batch_size]
    params = {
        "access_token": api_key,
        "zpid.in": ",".join(batch)
    }
    response = requests.get(api_url, params=params)
    if response.status_code == 200:
        data = response.json()
        print("API Response:", data)
        if 'bundle' in data:
            bundle = data['bundle']
            for result in bundle:
                print("Result:", result)
                # Extract coordinates (assuming latitude and longitude keys)
                lat = result.get('Latitude')
                lon = result.get('Longitude')
                if lat is not None and lon is not None:
                    marker_locations.append([lat, lon])
# Add this after the API request
print("API Response:", response)

# Calculate the map center and zoom level
if marker_locations:
    # Calculate the center of the markers
    center_lat = sum(lat for lat, lon in marker_locations) / len(marker_locations)
    center_lon = sum(lon for _, lon in marker_locations) / len(marker_locations)

    # Create the map with the calculated center and appropriate zoom level
    map = folium.Map(location=[center_lat, center_lon], zoom_start=10)

    # Add markers to the map
    for location in marker_locations:
        folium.Marker(location=location).add_to(map)

    # Save the map as an HTML file
    map.save('map.html')
    print("Map saved as map.html")
else:
    print("No coordinates found. No map created.")
