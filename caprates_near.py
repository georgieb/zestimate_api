import os
import requests
from dotenv import load_dotenv
from prettytable import PrettyTable

# Load environment variables from .env file
load_dotenv()

# Get the API key from the environment variables
api_key = os.getenv("API_KEY")

if not api_key:
    raise ValueError("API_KEY not found in the .env file.")

# Define the API URL with your access token
api_url = "https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates"

# Define the coordinates for the location (longitude, latitude)
location = (34.28840206601289, -77.8300671579137)

# Initialize an empty list to store property data
property_data = []

# Set parameters for the API request
params = {
    "access_token": api_key,
    "near": f"{location[1]},{location[0]}",  
    "limit": 30
}

# Make the API request
response = requests.get(api_url, params=params)

if response.status_code == 200:
    data = response.json()
    if 'bundle' in data:
        for i, result in enumerate(data['bundle']):
            address = result.get('address', '')
            zestimate = result.get('zestimate', 0)
            rental_zestimate = result.get('rentalZestimate', 0)

            # Check if required fields are present
            if address and zestimate is not None and rental_zestimate is not None:
                # Calculate cap rate (assuming 'rentalZestimate' is monthly rent)
                cap_rate = (rental_zestimate * 12) / zestimate * 100 if zestimate != 0 else 0

                # Add a tuple to the list
                property_data.append((address, zestimate, rental_zestimate, f"{cap_rate:.2f}%"))

               # Sort the property data by Cap Rate in descending order
                property_data.sort(key=lambda x: float(x[3].rstrip('%')), reverse=True)  # Sort by Cap Rate in descending order (index 3)


    else:
        print("No properties found.")
else:
    print(f"Request failed with status code {response.status_code}")
    print(response.text)  # Print the response text for more information

# Check if there is property data
if property_data:
    # Define headers for the table
    table_headers = ['Address', 'Zestimate', 'Rental Zestimate', 'Cap Rate']

    # Create a PrettyTable instance with the specified headers
    property_table = PrettyTable(table_headers)

    # Iterate through the property data and add rows to the table
    for data_tuple in property_data:
        property_table.add_row(data_tuple)

    # Print the table
    print(property_table)
else:
    print("No properties found.")
