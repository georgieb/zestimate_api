import os
import requests
from dotenv import load_dotenv
import sys

# Load environment variables from .env file
load_dotenv()

# Get the API key from the environment variables
api_key = os.getenv("API_KEY")

if not api_key:
    raise ValueError("API_KEY not found in the .env file.")

# Define the API URL with your access token
api_url = "https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates"

# Check if ZIP codes are provided as command line arguments
if len(sys.argv) < 2:
    raise ValueError("Please provide ZIP codes as command line arguments.")

# Get ZIP codes from command line arguments
new_zip_codes = sys.argv[1].split(',')

# Initialize a list to store property data as tuples
property_data = []

# Iterate through each location (zip code)
for zip_code in new_zip_codes:
    # Initialize variables to store total cap rate and count of properties for the current ZIP code
    total_cap_rate = 0
    property_count = 0

    # Make the initial request to get the total count of properties
    params_initial = {
        "access_token": api_key,
        "near": f"{zip_code}",
        "limit": 1  # Only need one result to get the total count
    }

    response_initial = requests.get(api_url, params=params_initial)
    if response_initial.status_code == 200:
        data_initial = response_initial.json()
        total_properties = data_initial.get('total', 0)

        # Make multiple requests with different offsets to handle pagination
        for offset in range(0, total_properties, 200):
            # Set parameters for the API request
            params = {
                "access_token": api_key,
                "near": f"{zip_code}",
                "limit": 200,
                "offset": offset
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
