from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the API key from the environment variables
api_key = os.getenv("API_KEY")

if not api_key:
    raise ValueError("API_KEY not found in the .env file.")

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Endpoint to get property data by ZPIDs
@app.route('/get-properties', methods=['POST'])
def get_properties():
    zpid_list = request.json.get('zpids', [])
    
    if not zpid_list:
        return jsonify({"error": "No ZPIDs provided"}), 400

    # Define the API URL with your access token
    api_url = "https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates"

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
                for result in bundle:
                    zestimate = float(result.get('zestimate', 0))
                    rental_zestimate = float(result.get('rentalZestimate', 0))
                    cap_rate = (rental_zestimate * 12 * 0.60 / zestimate * 100) if zestimate != 0 else 0
                    result['capRate'] = f"{cap_rate:.2f}%"
                all_results.extend(bundle)
        else:
            return jsonify({"error": f"Request failed with status code {response.status_code}"}), response.status_code

    if all_results:
        return jsonify(all_results), 200
    else:
        return jsonify({"error": "No results found"}), 404

# Endpoint to get nearby properties based on ZPID
@app.route('/get-nearby-properties', methods=['GET'])
def get_nearby_properties():
    zpid = request.args.get('zpid')
    if not zpid:
        return jsonify({'error': 'ZPID is required'}), 400

    # Define the API URL with your access token
    zpid_api_url = "https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates"
    params = {
        "access_token": api_key,
        "zpid": zpid
    }

    try:
        # Get the property data for the given ZPID
        property_response = requests.get(zpid_api_url, params=params)
        property_response.raise_for_status()
        property_data = property_response.json()

        if 'bundle' in property_data and len(property_data['bundle']) > 0:
            latitude = property_data['bundle'][0].get('Latitude')
            longitude = property_data['bundle'][0].get('Longitude')

            if latitude and longitude:
                nearby_api_url = "https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates"
                params = {
                    "access_token": api_key,
                    "near": f"{longitude},{latitude}",
                    "limit": 200
                }

                response = requests.get(nearby_api_url, params=params)
                response.raise_for_status()
                data = response.json()

                if 'bundle' in data:
                    properties = []
                    for result in data['bundle']:
                        address = result.get('address', '')
                        zestimate = result.get('zestimate', 0)
                        rental_zestimate = result.get('rentalZestimate', 0)

                        zestimate = float(zestimate) if zestimate is not None else 0
                        rental_zestimate = float(rental_zestimate) if rental_zestimate is not None else 0

                        cap_rate = (rental_zestimate * 12 * 0.60) / zestimate * 100 if zestimate != 0 else 0

                        properties.append({
                            'address': address,
                            'zestimate': zestimate,
                            'rentalZestimate': rental_zestimate,
                            'capRate': f"{cap_rate:.2f}%"
                        })

                    properties.sort(key=lambda x: float(x['capRate'].rstrip('%')), reverse=True)
                    return jsonify(properties)
                else:
                    return jsonify({'error': 'No nearby properties found'}), 404
            else:
                return jsonify({'error': 'Latitude and longitude not found for the given ZPID'}), 400
        else:
            return jsonify({'error': 'No property found for the given ZPID'}), 404

    except requests.RequestException as e:
        return jsonify({'error': str(e)}), 500

# Updated endpoint to get parcel data by ZPIDs
@app.route('/get-parcel-data', methods=['POST'])
def get_parcel_data():
    zpid_list = request.json.get('zpids', [])
    
    if not zpid_list:
        return jsonify({"error": "No ZPIDs provided"}), 400

    base_url = "https://api.bridgedataoutput.com/api/v2/pub/parcels"
    all_records = []

    for zpid in zpid_list:
        url = f"{base_url}?zpid={zpid}&access_token={api_key}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            if 'bundle' in data and len(data['bundle']) > 0:
                # Include all fields from the API response
                all_records.append(data['bundle'][0])
        except requests.exceptions.RequestException as e:
            print(f"Failed to retrieve data for ZPID {zpid}: {e}")

    if all_records:
        return jsonify(all_records), 200
    else:
        return jsonify({"error": "No parcel data found"}), 404
if __name__ == '__main__':
    app.run(port=5001)
