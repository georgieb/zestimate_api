import os
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the API key from the environment variables
api_key = os.getenv("API_KEY")

if not api_key:
    raise ValueError("API_KEY not found in the .env file.")

# Define the API URL with your access token
api_url = "https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates"

# Define a new list of ZIP codes
new_zip_codes = ["33054", "33056", "33147", "33167", "33168", "33055", "33162", "33169", "33127", "33142", "33142", "33181"]

# Initialize a list to store property data as tuples
property_data = []

# Iterate through each location (zip code)
for zip_code in new_zip_codes:
    # Initialize variables to store total cap rate and count of properties for the current ZIP code
    total_cap_rate = 0
    property_count = 0

    # Set parameters for the API request
    params = {
        "access_token": api_key,
        "near": f"{zip_code}",  # Use zip code as the location
        "limit": 200
    }

    # Make the API request
    response = requests.get(api_url, params=params)

    if response.status_code == 200:
        data = response.json()
        if 'bundle' in data:
            for result in data['bundle']:
                zestimate = result.get('zestimate', 0)
                rental_zestimate = result.get('rentalZestimate', 0)

                # Check if 'zestimate' is within the specified range (350000 to 625000)
                if 350000 <= zestimate <= 625000 and rental_zestimate is not None:
                    # Calculate cap rate (assuming 'rentalZestimate' is monthly rent)
                    cap_rate = (rental_zestimate * 12) / zestimate * 100 if zestimate != 0 else 0

                    # Accumulate cap rate and increment property count for the current ZIP code
                    total_cap_rate += cap_rate
                    property_count += 1

    # Calculate average cap rate for the current ZIP code
    average_cap_rate = total_cap_rate / property_count if property_count != 0 else 0

    # Append a tuple to the list for the current ZIP code
    property_data.append((zip_code, average_cap_rate))

# Sort the property data by Average Cap Rate in descending order
property_data.sort(key=lambda x: x[1], reverse=True)  # Sort by Average Cap Rate in descending order (index 1)

# Print the sorted results
print("Sorted Results:")
for data_tuple in property_data:
    print(f"ZIP Code: {data_tuple[0]}, Average Cap Rate: {data_tuple[1]:.2f}%")

