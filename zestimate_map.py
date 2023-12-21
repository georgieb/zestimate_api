import requests
import folium

# Get the API key from the environment variables
api_key = "API KEY HERE"

# Check if API key is present
if api_key is None:
    raise ValueError("API_KEY is not set in the .env file.")

# Define the API URL
api_url = "https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates"


# List of ZPIDs
zpid_list = [
    "43996214", "44106066", "44154066", "43994986", "44158191", "44106162", "62936198", "62937284",
    "44151347", "44160521", "43807923", "43995191", "44105747", "44118156", "44107037", "44062156",
    "44063932", "44113615", "43970389", "62936164", "62937229", "44113047", "62936150", "62937274",
    "62933595", "43996838", "62937053", "44109202", "43994966", "43996656", "44109256", "44117834",
    "43995934", "62937147", "44117891", "62936274", "62937149", "44112804", "44122119", "44113703",
    "44152032", "62935928", "44114467", "43972756", "62936338", "44118194", "62936373", "44101389",
    "62937177", "62936265", "44112873", "44117674", "62936341", "44112792", "43993403", "43993290",
    "44117786", "44112911", "44151332", "44063896"
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
