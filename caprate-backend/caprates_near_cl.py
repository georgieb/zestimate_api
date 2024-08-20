import os
import requests
import argparse
from dotenv import load_dotenv
from prettytable import PrettyTable

# Load environment variables from .env file
load_dotenv()

# Get the API key from the environment variables
api_key = os.getenv("API_KEY")

if not api_key:
    raise ValueError("API_KEY not found in the .env file.")

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Get cap rates for properties near a given ZPID.")
parser.add_argument("zpid", type=str, help="The Zillow Property ID (ZPID)")
args = parser.parse_args()
zpid = args.zpid

# Define the API URL for retrieving property details by ZPID
zpid_api_url = f"https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates"

# Request parameters including the ZPID
params = {
    "access_token": api_key,
    "zpid": zpid
}

# Make the API request to get property details
property_response = requests.get(zpid_api_url, params=params)

if property_response.status_code == 200:
    property_data = property_response.json()

    # Debug: Print the full response to inspect the structure
    print("API Response:", property_data)

    if 'bundle' in property_data and len(property_data['bundle']) > 0:
        # Extract latitude and longitude
        latitude = property_data['bundle'][0].get('Latitude')
        longitude = property_data['bundle'][0].get('Longitude')

        if latitude is not None and longitude is not None:
            # Define the API URL for retrieving nearby properties
            nearby_api_url = "https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates"

            # Initialize an empty list to store nearby property data
            nearby_property_data = []

            # Set parameters for the API request to get nearby properties
            params = {
                "access_token": api_key,
                "near": f"{longitude},{latitude}",  # Latitude and longitude
                "limit": 200
            }

            # Make the API request for nearby properties
            response = requests.get(nearby_api_url, params=params)

            if response.status_code == 200:
                data = response.json()
                if 'bundle' in data:
                    for result in data['bundle']:
                        address = result.get('address', '')
                        zestimate = result.get('zestimate', 0)
                        rental_zestimate = result.get('rentalZestimate', 0)

                        # Check if required fields are present
                        if address and zestimate is not None and rental_zestimate is not None:
                            # Calculate cap rate (assuming 'rentalZestimate' is monthly rent)
                            cap_rate = (rental_zestimate * 12*.60) / zestimate * 100 if zestimate != 0 else 0

                            # Add a tuple to the list
                            nearby_property_data.append((address, zestimate, rental_zestimate, f"{cap_rate:.2f}%"))

                    # Sort the property data by Cap Rate in descending order
                    nearby_property_data.sort(key=lambda x: float(x[3].rstrip('%')), reverse=True)

                    # Check if there is nearby property data
                    if nearby_property_data:
                        # Define headers for the table
                        table_headers = ['Address', 'Zestimate', 'Rental Zestimate', 'Cap Rate']

                        # Create a PrettyTable instance with the specified headers
                        nearby_property_table = PrettyTable(table_headers)

                        # Iterate through the property data and add rows to the table
                        for data_tuple in nearby_property_data:
                            nearby_property_table.add_row(data_tuple)

                        # Print the table
                        print(nearby_property_table)
                    else:
                        print("No nearby properties found.")
                else:
                    print("No nearby properties found.")
            else:
                print(f"Request for nearby properties failed with status code {response.status_code}")
                print(response.text)  # Print the response text for more information
        else:
            print("Latitude and longitude not found for the given ZPID.")
    else:
        print("No property found for the given ZPID.")
else:
    print(f"Request failed with status code {property_response.status_code}")
    print(property_response.text)  # Print the response text for more information
