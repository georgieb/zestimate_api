import os
import requests
from dotenv import load_dotenv
from prettytable import PrettyTable

# Load environment variables from .env file
load_dotenv()

# Get the Zillow API key from the environment variables
api_key = os.getenv("API_KEY")

if not api_key:
    raise ValueError("Zillow API_KEY not found in the .env file.")

# Define the Zillow API URL with your access token
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

# Initialize an empty list to store property data
property_data = []

# Split the ZPIDs into batches of 8
batch_size = 8
for i in range(0, len(zpid_list), batch_size):
    batch = zpid_list[i:i + batch_size]

    # Fetch property data for each ZPID in the batch
    for zpid in batch:
        params = {
            "access_token": api_key,
            "zpid": zpid
        }

        response = requests.get(api_url, params=params)

        if response.status_code == 200:
            data = response.json()
            if 'bundle' in data:
                result = data['bundle'][0]  # Assuming one result per ZPID
                address = result.get('address', '')
                zestimate = result.get('zestimate', 0)
                rental_zestimate = result.get('rentalZestimate', 0)

                # Check if required fields are present
                if address and zestimate is not None and rental_zestimate is not None:
                    # Calculate cap rate (assuming 'rentalZestimate' is monthly rent)
                    cap_rate = (rental_zestimate * 12) / zestimate * 100 if zestimate != 0 else 0

                    # Add a tuple to the list
                    property_data.append((address, zestimate, rental_zestimate, f"{cap_rate:.2f}%"))
            else:
                print(f"No properties found for ZPID: {zpid}")
        else:
            print(f"Request failed with status code {response.status_code} for ZPID: {zpid}")
            print(response.text)  # Print the response text for more information

# Sort the property_data list by cap rate in descending order
property_data.sort(key=lambda x: float(x[3][:-1]), reverse=True)

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
    print("No properties found for the specified ZPIDs.")
