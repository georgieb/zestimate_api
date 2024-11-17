]# api/index.py
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

# Logging setup
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__
            )
CORS(app)

# Load environment variables
load_dotenv()
API_KEY = os.environ.get("API_KEY")

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
    """Safely convert value to float"""
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
                        'propertyType': parcel.get('PropertyTypeName'),
                        'constructionType': parcel.get('ConstructionType'),
                        'foundation': parcel.get('Foundation'),
                        'parkingSpaces': safe_float(parcel.get('ParkingSpaces')),
                        'stories': safe_float(parcel.get('StoriesCount')),
                        'taxAssessedValue': safe_float(parcel.get('TaxAssessedValue')),
                        'taxYear': parcel.get('TaxYear'),
                        'propertyTax': safe_float(parcel.get('TaxAmount')),
                    }
                    logger.debug(f"Processed parcel data for ZPID {zpid}")
            
            if response.status_code == 429:
                logger.warning("Rate limit hit, waiting 2 seconds...")
                time.sleep(2)
                
        except Exception as e:
            logger.error(f"Error fetching parcel data: {str(e)}")
            logger.exception("Full traceback:")
            continue
        
    return all_parcel_data

@app.route('/')
def home():
    """Serve the main page"""
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Error serving index: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/portfolio')
def portfolio():
    """Serve the portfolio page"""
    try:
        return render_template('portfolio.html')
    except Exception as e:
        logger.error(f"Error serving portfolio: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files"""
    try:
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return send_from_directory(os.path.join(root_dir, 'static'), filename)
    except Exception as e:
        logger.error(f"Error serving static file: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/properties', methods=['POST'])
def get_properties():
    """Get property data endpoint"""
    try:
        logger.debug("Received properties request")
        logger.debug(f"Request JSON: {request.json}")
        
        zpid_list = request.json.get('zpids', [])
        if not zpid_list:
            return jsonify({"error": "No ZPIDs provided"}), 400

        api_url = "https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates"
        all_results = []
        
        # Get Zestimate data in batches
        batch_size = 5
        for i in range(0, len(zpid_list), batch_size):
            batch = zpid_list[i:i+batch_size]
            params = {
                "access_token": API_KEY,
                "zpid.in": ",".join(batch)
            }
            
            try:
                logger.debug(f"Fetching Zestimate data for batch: {batch}")
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
                        
                if response.status_code == 429:
                    logger.warning("Rate limit hit, waiting 2 seconds...")
                    time.sleep(2)
                    
            except requests.RequestException as e:
                logger.error(f"Error fetching Zestimate data: {str(e)}")
                continue

        if all_results:
            # Get parcel data
            parcel_data = get_parcel_data_batch([str(r.get('zpid')) for r in all_results])
            
            # Process results and merge data
            processed_results = []
            for result in all_results:
                zpid = str(result.get('zpid'))
                if zpid in parcel_data:
                    result.update(parcel_data[zpid])
                processed_results.append(result)

            # Calculate portfolio metrics
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
                    'avg_price_per_sqft': total_value / total_sqft if total_sqft > 0 else 0,
                    'total_bedrooms': sum(safe_float(p.get('bedrooms', 0)) for p in processed_results),
                    'total_bathrooms': sum(safe_float(p.get('bathrooms', 0)) for p in processed_results)
                }
            }
            
            return jsonify(portfolio_metrics), 200
        
        return jsonify({"error": "No results found"}), 404

    except Exception as e:
        logger.error(f"Error in get_properties: {str(e)}")
        logger.exception("Full traceback:")
        return jsonify({
            "error": "Internal server error",
            "details": str(e),
            "type": type(e).__name__
        }), 500

@app.route('/api/nearby-properties/<zpid>')
def nearby_properties(zpid):
    """Get nearby properties endpoint"""
    try:
        logger.debug(f"Fetching nearby properties for ZPID: {zpid}")
        api_url = "https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates"
        
        # First get the property's coordinates
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
                # Get nearby properties
                params = {
                    "access_token": API_KEY,
                    "near": f"{longitude},{latitude}",
                    "limit": 100
                }
                
                response = http.get(api_url, params=params)
                response.raise_for_status()
                nearby_data = response.json()
                
                if 'bundle' in nearby_data:
                    properties = []
                    for prop in nearby_data['bundle']:
                        # Calculate metrics for each property
                        zestimate = safe_float(prop.get('zestimate'))
                        rental_zestimate = safe_float(prop.get('rentalZestimate'))
                        cap_rate = (rental_zestimate * 12 * 0.60 / zestimate * 100) if zestimate != 0 else 0
                        prop['capRate'] = cap_rate
                        
                        # Get parcel data
                        if prop.get('zpid'):
                            parcel_data = get_parcel_data_batch([str(prop['zpid'])])
                            if str(prop['zpid']) in parcel_data:
                                prop.update(parcel_data[str(prop['zpid'])])
                        
                        properties.append(prop)
                    
                    return jsonify(properties), 200
                
        return jsonify({"error": "Property coordinates not found"}), 404
        
    except Exception as e:
        logger.error(f"Error in nearby_properties: {str(e)}")
        logger.exception("Full traceback:")
        return jsonify({
            "error": "Internal server error",
            "details": str(e),
            "type": type(e).__name__
        }), 500

@app.route('/api/test')
def test_api():
    """Test endpoint for API verification"""
    return jsonify({
        "status": "ok",
        "api_key_present": bool(API_KEY),
        "api_key_length": len(API_KEY) if API_KEY else 0,
        "routes": [str(rule) for rule in app.url_map.iter_rules()]
    })

# Catch-all route for undefined routes
@app.route('/<path:path>')
def catch_all(path):
    """Handle undefined routes"""
    logger.warning(f"Undefined route accessed: {path}")
    return jsonify({
        "error": "Not found",
        "message": f"The path /{path} does not exist",
        "available_routes": [str(rule) for rule in app.url_map.iter_rules()]
    }), 404

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    logger.warning(f"404 error: {error}")
    return jsonify({
        "error": "Not found",
        "message": "The requested resource was not found",
        "available_routes": [str(rule) for rule in app.url_map.iter_rules()]
    }), 404

@app.errorhandler(Exception)
def handle_exception(error):
    logger.error(f"Unhandled exception: {str(error)}")
    logger.exception("Full traceback:")
    return jsonify({
        "error": "Internal server error",
        "details": str(error),
        "type": type(error).__name__
    }), 500

# For Vercel
app = app.wsgi_app