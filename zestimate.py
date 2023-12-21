import requests
import csv

# Get the API key from the environment variables
api_key = "API KEY HERE"

# Define the API URL with your access token
api_url = "https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates"


# List of ZPIDs
zpid_list = [
    "43996214", "44106066", "44154066", "43994986", "44158191", "44106162", "44151304", "62936198",
    "62937284", "44151347", "44160521", "43807923", "43995191", "44105747", "44118156", "44107037",
    "44062156", "44063932", "44113615", "43970389", "62936164", "62937229", "44113047", "62936150",
    "62937274", "62933595", "43996838", "62937053", "44109202", "43994966", "43996656", "44109256",
    "44117834", "43995934", "62937147", "44117891", "62936274", "62937149", "44112804", "44122119",
    "44113703", "44152032", "62935928", "62937192", "44114467", "43972756", "62936338", "44118194",
    "62936373", "44101389", "62937177", "62936265", "44112873", "44117674", "62936341", "44112792",
    "43993403", "43993290", "44117786", "44112911", "44151332", "2068443583", "44063896", "43977694",
    "44149668", "2056138890", "2081387401", "44119719", "44151131", "44151108"

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
