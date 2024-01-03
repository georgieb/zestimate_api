import os
from dotenv import load_dotenv
import subprocess
import pandas as pd


# Load environment variables from .env file
load_dotenv()

# Get the API key from the environment variables
api_key = os.getenv("API_KEY")

if not api_key:
    raise ValueError("API_KEY not found in the .env file.")

# Run the caprates_near.py script using subprocess
subprocess.run(["python", "caprates_near.py"])

# Import the property_data from caprates_near.py
from caprates_near import property_data

# Check if there is property data
if property_data:
    # Create a DataFrame from the property data
    table_headers = ['Address', 'Zestimate', 'Rental Zestimate', 'Cap Rate']
    df = pd.DataFrame(property_data, columns=table_headers)

    # Save the DataFrame to an Excel file
    excel_file_path = "property_data.xlsx"
    df.to_excel(excel_file_path, index=False)

    print(f"Property data saved to {excel_file_path}")
else:
    print("No properties found.")
