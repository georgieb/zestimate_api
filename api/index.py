# api/index.py
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import os
import requests
from dotenv import load_dotenv
import json
from datetime import datetime
import logging
import sys
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Enhanced logging setup
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout  # Ensure logs go to stdout for Vercel
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Load environment variables
load_dotenv()
API_KEY = os.environ.get("API_KEY")

# Verify API key is present
if not API_KEY:
    logger.error("API_KEY environment variable is not set!")
    raise ValueError("API_KEY environment variable is required")

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
            logger.debug(f"Fetching parcel data for chunk: {chunk}")
            response = http.get(url, params=params)
            
            # Log API response for debugging
            logger.debug(f"API Response Status: {response.status_code}")
            logger.debug(f"API Response Headers: {response.headers}")
            
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
                    logger.debug(f"Processed parcel data for ZPID {zpid}")
        except Exception as e:
            logger.error(f"Error fetching parcel data: {str(e)}")
            # Include the full error traceback in logs
            logger.exception("Full traceback:")
            continue
        
    return all_parcel_data

@app.route('/api/properties', methods=['POST'])
def get_properties():
    try:
        logger.debug("Received request to /api/properties")
        logger.debug(f"Request headers: {dict(request.headers)}")
        logger.debug(f"Request body: {request.json}")
        
        zpid_list = request.json.get('zpids', [])
        
        if not zpid_list:
            return jsonify({"error": "No ZPIDs provided"}), 400

        api_url = "https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates"
        all_results = []
        
        for i in range(0, len(zpid_list), 5):
            batch = zpid_list[i:i+5]
            params = {
                "access_token": API_KEY,
                "zpid.in": ",".join(batch)
            }
            
            logger.debug(f"Fetching Zestimate data for batch: {batch}")
            response = http.get(api_url, params=params)
            
            # Log API response
            logger.debug(f"Zestimate API Response Status: {response.status_code}")
            logger.debug(f"Zestimate API Response Headers: {response.headers}")
            
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

            metrics = {
                'properties': processed_results,
                'summary': {
                    'total_value': sum(safe_float(p.get('zestimate')) for p in processed_results),
                    'total_rental': sum(safe_float(p.get('rentalZestimate')) for p in processed_results),
                    'avg_cap_rate': sum(p['capRate'] for p in processed_results) / len(processed_results),
                    'property_count': len(processed_results),
                    'total_sqft': sum(safe_float(p.get('livingArea', 0)) for p in processed_results)
                }
            }
            
            if metrics['summary']['total_sqft'] > 0:
                metrics['summary']['avg_price_per_sqft'] = metrics['summary']['total_value'] / metrics['summary']['total_sqft']
            else:
                metrics['summary']['avg_price_per_sqft'] = 0
            
            logger.debug("Successfully processed all properties")
            return jsonify(metrics), 200
        
        logger.warning("No results found for the provided ZPIDs")
        return jsonify({"error": "No results found"}), 404
        
    except Exception as e:
        logger.error(f"Error in get_properties: {str(e)}")
        logger.exception("Full traceback:")
        return jsonify({
            "error": "Internal server error",
            "details": str(e),
            "api_key_present": bool(API_KEY)
        }), 500

# Add this test route to verify API key
@app.route('/api/test', methods=['GET'])
def test_api():
    return jsonify({
        "status": "ok",
        "api_key_present": bool(API_KEY),
        "api_key_length": len(API_KEY) if API_KEY else 0
    })

# Error handler
@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {str(e)}")
    logger.exception("Full traceback:")
    return jsonify({
        "error": "Internal server error",
        "details": str(e),
        "type": type(e).__name__
    }), 500

# Required for Vercel
app = app.wsgi_app