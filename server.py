from flask import Flask, render_template, request, jsonify

import requests
import os
from dotenv import load_dotenv


# Load environment variables from .env file if running locally
if os.getenv('FLASK_ENV') != 'production':
    load_dotenv()


app = Flask(__name__)

API_KEY = os.getenv("API_KEY")


@app.route('/')
def home():
    return render_template('index.html',)



@app.route('/get-nearby-properties/<zpid>', methods=['GET'])
def get_nearby_properties(zpid):
    # Define the API URL with your access token
    zpid_api_url = "https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates"
    params = {
        "access_token": API_KEY,
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
                    "access_token": API_KEY,
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


@app.route('/api/caprates', methods=['GET'])
def get_caprates():
    zpid = request.args.get('zpid')
    if not zpid:
        return jsonify({'error': 'ZPID is required'}), 400

    zpid_api_url = "https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates"
    params = {"access_token": API_KEY, "zpid": zpid}
    
    try:
        property_response = requests.get(zpid_api_url, params=params)
        property_response.raise_for_status()

        property_data = property_response.json()

        if 'bundle' in property_data and len(property_data['bundle']) > 0:
            latitude = property_data['bundle'][0].get('Latitude')
            longitude = property_data['bundle'][0].get('Longitude')

            if latitude and longitude:
                nearby_api_url = "https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates"
                params = {"access_token": API_KEY, "near": f"{longitude},{latitude}", "limit": 200}

                response = requests.get(nearby_api_url, params=params)
                response.raise_for_status()

                data = response.json()
                if 'bundle' in data:
                    properties = []
                    for result in data['bundle']:
                        address = result.get('address', '')
                        zestimate = result.get('zestimate', 0)
                        rental_zestimate = result.get('rentalZestimate', 0)

                        # Provide default values if fields are None
                        zestimate = float(zestimate) if zestimate is not None else 0
                        rental_zestimate = float(rental_zestimate) if rental_zestimate is not None else 0

                        # Calculate cap rate
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


if __name__ == '__main__':
    app.run(debug=True, port=5001)