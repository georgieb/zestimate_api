import sys
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

def get_zip_codes_for_city(city_name):
    # Initialize Nominatim geocoder
    geolocator = Nominatim(user_agent="city_search")

    try:
        # Get location details for the city
        location = geolocator.geocode(city_name, addressdetails=True)

        if location and 'postcode' in location.raw['address']:
            zip_code = location.raw['address']['postcode']
            return [zip_code]
        else:
            return []
    except (GeocoderTimedOut, GeocoderUnavailable):
        print("Error: Unable to connect to the geocoding service. Please try again later.")
        sys.exit(1)

if __name__ == "__main__":
    # Check if a city is provided as a command line argument
    if len(sys.argv) < 2:
        print("Please provide the city name as a command line argument.")
        sys.exit(1)

    # Join command line arguments to handle multi-word city names
    city_name = ' '.join(sys.argv[1:])

    # Get ZIP codes for the specified city
    zip_codes = get_zip_codes_for_city(city_name)

    if zip_codes:
        print(f"ZIP codes in {city_name}: {', '.join(map(str, zip_codes))}")
    else:
        print(f"No ZIP codes found for {city_name}.")




