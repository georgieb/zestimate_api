from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import os
import requests
from dotenv import load_dotenv
import json
from datetime import datetime
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Load environment variables
API_KEY = os.getenv("API_KEY")

# Configure retry strategy
retry_strategy = Retry(
    total=5,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
http = requests.Session()
http.mount("https://", adapter)
http.mount("http://", adapter)

def safe_float(value, default=0.0):
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def get_parcel_data_batch(zpids):
    """Get parcel data for multiple ZPIDs"""
    url = "https://api.bridgedataoutput.com/api/v2/pub/parcels"
    chunk_size = 5
    all_parcel_data = {}
    
    for i in range(0, len(zpids), chunk_size):
        chunk = zpids[i:i + chunk_size]
        params = {
            "access_token": API_KEY,
            "zpid.in": ",".join(chunk)
        }
        
        try:
            response = http.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if 'bundle' in data and data['bundle']:
                for parcel in data['bundle']:
                    zpid = str(parcel.get('zpid'))
                    all_parcel_data[zpid] = {
                        'bedrooms': safe_float(parcel.get('BedroomsCount')),
                        'bathrooms': safe_float(parcel.get('BathroomsTotalCount')),
                        'lotSize': safe_float(parcel.get('LotSizeSquareFeet')),
                        'yearBuilt': parcel.get('YearBuilt'),
                        'livingArea': safe_float(parcel.get('BuildingAreaSqFt')),
                        'propertyType': parcel.get('PropertyTypeName')
                    }
        except Exception as e:
            logger.error(f"Error fetching parcel data: {str(e)}")
            continue
        
    return all_parcel_data

# Routes
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    if path == "":
        return render_template('index.html')
    elif path == "portfolio":
        return render_template('portfolio.html')
    elif path.startswith('static/'):
        return send_from_directory('.', path)
    return render_template('index.html')

@app.route('/api/properties', methods=['POST'])
def get_properties():
    try:
        zpid_list = request.json.get('zpids', [])
        
        if not zpid_list:
            return jsonify({"error": "No ZPIDs provided"}), 400

        api_url = "https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates"
        all_results = []
        
        batch_size = 5
        for i in range(0, len(zpid_list), batch_size):
            batch = zpid_list[i:i+batch_size]
            params = {
                "access_token": API_KEY,
                "zpid.in": ",".join(batch)
            }
            
            response = http.get(api_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if 'bundle' in data:
                for result in data['bundle']:
                    zestimate = safe_float(result.get('zestimate'))
                    rental_zestimate = safe_float(result.get('rentalZestimate'))
                    cap_rate = (rental_zestimate * 12 * 0.60 / zestimate * 100) if zestimate != 0 else 0
                    result['capRate'] = cap_rate
                    all_results.append(result)

        if all_results:
            parcel_data = get_parcel_data_batch([str(r.get('zpid')) for r in all_results])
            
            processed_results = []
            for result in all_results:
                zpid = str(result.get('zpid'))
                if zpid in parcel_data:
                    result.update(parcel_data[zpid])
                processed_results.append(result)

            total_value = sum(safe_float(p.get('zestimate')) for p in processed_results)
            total_rental = sum(safe_float(p.get('rentalZestimate')) for p in processed_results)
            total_sqft = sum(safe_float(p.get('livingArea', 0)) for p in processed_results)
            
            portfolio_metrics = {
                'properties': processed_results,
                'summary': {
                    'total_value': total_value,
                    'total_rental': total_rental,
                    'avg_cap_rate': sum(p['capRate'] for p in processed_results) / len(processed_results),
                    'property_count': len(processed_results),
                    'total_sqft': total_sqft,
                    'avg_price_per_sqft': total_value / total_sqft if total_sqft > 0 else 0
                }
            }
            
            return jsonify(portfolio_metrics), 200
        
        return jsonify({"error": "No results found"}), 404
    except Exception as e:
        logger.error(f"Error in get_properties: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/nearby-properties/<zpid>', methods=['GET'])
def nearby_properties(zpid):
    try:
        api_url = "https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates"
        params = {
            "access_token": API_KEY,
            "zpid": zpid
        }
        
        response = http.get(api_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if 'bundle' in data and len(data['bundle']) > 0:
            property_data = data['bundle'][0]
            latitude = property_data.get('Latitude')
            longitude = property_data.get('Longitude')
            
            if latitude and longitude:
                params = {
                    "access_token": API_KEY,
                    "near": f"{longitude},{latitude}",
                    "limit": 100
                }
                
                response = http.get(api_url, params=params)
                response.raise_for_status()
                data = response.json()
                
                if 'bundle' in data:
                    return jsonify(data['bundle']), 200
                
        return jsonify({"error": "Property coordinates not found"}), 404
        
    except Exception as e:
        logger.error(f"Error in nearby_properties: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Error handler
@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {str(e)}")
    return jsonify({"error": "Internal server error"}), 500

# Required for Vercel
app = app.wsgi_app