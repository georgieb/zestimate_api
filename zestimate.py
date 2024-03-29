import os
import requests
from dotenv import load_dotenv
import csv

# Load environment variables from .env file
load_dotenv()

# Get the API key from the environment variables
api_key = os.getenv("API_KEY")

if not api_key:
    raise ValueError("API_KEY not found in the .env file.")

# Define the API URL with your access token
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

# Initialize an empty list to store all results
all_results = []

# Split the ZPID list into batches of 8
batch_size = 8
for i in range(0, len(zpid_list), batch_size):
    batch = zpid_list[i:i+batch_size]
    params = {
        "access_token": api_key,
        "zpid.in": ",".join(batch)
    }
    response = requests.get(api_url, params=params)
    if response.status_code == 200:
        data = response.json()
        if 'bundle' in data:
            bundle = data['bundle']
            all_results.extend(bundle)
    else:
        print(f"Request failed with status code {response.status_code}")

# Check if there are results
if all_results:
    # Create a CSV file for writing
    with open('zestimate_data.csv', 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        
        # Write a header row with the field names
        writer.writerow(all_results[0].keys())

        # Iterate through the results and write to the CSV
        for result in all_results:
            writer.writerow(result.values())
        print(f"Data saved to zestimate_data.csv")
else:
    print("No results found.")
