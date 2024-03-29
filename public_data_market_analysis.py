import requests
import os
from dotenv import load_dotenv
import csv

# Load environment variables from .env file
load_dotenv()

# Define the base URL of the API
base_url = "https://api.bridgedataoutput.com/api/v2/pub/parcels"

# Retrieve the API key from environment variables
api_key = os.getenv("API_KEY")

# Define the postal code for White Salmon area
postal_code = "98672"

# Define function to retrieve parcels in the specified postal code
def get_parcels_in_area(postal_code):
    url = f"{base_url}?access_token={api_key}&address.zip={postal_code}"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for HTTP errors
        parcels = response.json()
        return parcels
    except requests.exceptions.RequestException as e:
        print(f"Failed to retrieve parcels: {e}")
        return None

# Function to perform market analysis based on assessments
def perform_market_analysis(parcels):
    if parcels and 'bundle' in parcels:
        # Extract actual parcel data
        actual_parcels = parcels['bundle']
        
        # Define a list to store market analysis data
        market_analysis_data = []

        # Iterate over each parcel
        for parcel in actual_parcels:
            # Extract relevant fields for analysis
            address = parcel.get('address', {})
            land_use_description = parcel.get('landUseDescription', '')
            market_value = parcel.get('marketTotalValue', '')

            # Append extracted data to market analysis list
            market_analysis_data.append({
                'Address': address.get('full', ''),
                'Land Use Description': land_use_description,
                'Market Value': market_value
            })

        return market_analysis_data
    else:
        print("No parcel data found in the response.")
        return None

# Function to save market analysis data to a CSV file
def save_to_csv(data, filename):
    if data:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = data[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in data:
                writer.writerow(row)
        print(f"Market analysis data has been saved to {filename}")
    else:
        print("No data to save.")

# Retrieve parcels in the specified postal code
parcels = get_parcels_in_area(postal_code)

# Perform market analysis based on parcels
market_analysis_data = perform_market_analysis(parcels)

# Save market analysis data to a CSV file
if market_analysis_data:
    save_to_csv(market_analysis_data, 'market_analysis_white_salmon.csv')

