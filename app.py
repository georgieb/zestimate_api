from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import os
import requests
from dotenv import load_dotenv
import json
from datetime import datetime
import logging
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry  # Fixed import

# Setup logging and load environment variables
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
load_dotenv()

# Initialize Flask app
app = Flask(__name__, 
    template_folder='templates',
    static_folder='static'
)
CORS(app)
API_KEY = os.getenv("API_KEY")

# Configure retry strategy
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
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
    """Get parcel data for multiple ZPIDs in a single request"""
    url = "https://api.bridgedataoutput.com/api/v2/pub/parcels"
    
    chunk_size = 10  # API limit per request
    all_parcel_data = {}
    
    # Process ZPIDs in chunks of 10
    for i in range(0, len(zpids), chunk_size):
        chunk = zpids[i:i + chunk_size]  # This gets elements i through i+10
        params = {
            "access_token": API_KEY,
            "zpid.in": ",".join(chunk)
        }
        
        try:
            logger.debug(f"Fetching parcel data for ZPIDs: {chunk}")
            response = http.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if 'bundle' in data and data['bundle']:
                for parcel in data['bundle']:
                    zpid = str(parcel.get('zpid'))
                    building = parcel.get('building', [{}])[0]
                    
                    # Get area info
                    living_area = next((area['areaSquareFeet'] for area in parcel.get('areas', []) 
                                     if area.get('type') == 'Living Building Area'), None)
                    
                    all_parcel_data[zpid] = {
                        'bedrooms': safe_float(building.get('bedrooms')),
                        'bathrooms': safe_float(building.get('fullBaths')),
                        'lotSize': safe_float(parcel.get('lotSizeSquareFeet')),
                        'yearBuilt': building.get('yearBuilt'),
                        'livingArea': safe_float(living_area),
                        'propertyType': parcel.get('landUseDescription'),
                        'stories': safe_float(building.get('totalStories')),
                        'foundation': building.get('foundation'),
                        'constructionType': None,
                        'roofType': None,
                        'zoning': parcel.get('zoningDescription'),
                        'parkingSpaces': len(parcel.get('garages', [])),
                        'totalRooms': safe_float(building.get('totalRooms'))
                    }
            
            logger.debug(f"Processed chunk {i//chunk_size + 1}, total data points so far: {len(all_parcel_data)}")
            time.sleep(1)  # Rate limiting between chunks
            
        except Exception as e:
            logger.error(f"Error fetching parcel data batch starting at index {i}: {str(e)}")
            continue
    
    logger.debug(f"Completed processing all chunks. Total properties: {len(all_parcel_data)}")
    return all_parcel_data

@app.route('/')
def home():
    """Render the main dashboard page"""
    return render_template('index.html')

@app.route('/portfolio')
def portfolio():
    """Render the portfolios list page"""
    return render_template('portfolio.html')

@app.route('/api/properties', methods=['POST'])
def get_properties():
    zpid_list = request.json.get('zpids', [])
    logger.debug(f"Received request for {len(zpid_list)} ZPIDs")
    
    if not zpid_list:
        return jsonify({"error": "No ZPIDs provided"}), 400

    api_url = "https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates"
    all_results = []
    
    # Process Zestimates in batches of 8
    batch_size = 8
    for i in range(0, len(zpid_list), batch_size):
        batch = zpid_list[i:i+batch_size]
        logger.debug(f"Processing Zestimate batch {i//batch_size + 1} with {len(batch)} ZPIDs")
        
        params = {
            "access_token": API_KEY,
            "zpid.in": ",".join(batch)
        }
        
        try:
            response = http.get(api_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if 'bundle' in data:
                all_results.extend(data['bundle'])
                logger.debug(f"Added {len(data['bundle'])} results, total so far: {len(all_results)}")
            
            time.sleep(1)  # Rate limiting between batches
            
        except requests.RequestException as e:
            logger.error(f"Error fetching Zestimate batch starting at index {i}: {str(e)}")
            continue

    logger.debug(f"Completed Zestimate fetching. Total properties: {len(all_results)}")

    if all_results:
        # Get parcel data for all properties in batch
        parcel_data = get_parcel_data_batch([str(r.get('zpid')) for r in all_results])
        
        # Process results and merge data
        processed_results = []
        for result in all_results:
            zpid = str(result.get('zpid'))
            
            # Merge parcel data if available
            if zpid in parcel_data:
                result.update(parcel_data[zpid])
            
            # Calculate financial metrics
            zestimate = safe_float(result.get('zestimate'))
            rental_zestimate = safe_float(result.get('rentalZestimate'))
            cap_rate = (rental_zestimate * 12 * 0.60 / zestimate * 100) if zestimate != 0 else 0
            result['capRate'] = cap_rate
            
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

@app.route('/api/nearby-properties/<zpid>', methods=['GET'])
def nearby_properties(zpid):
    try:
        logger.debug(f"Fetching nearby properties for ZPID: {zpid}")
        api_url = "https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates"
        
        # First get the target property's details
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
                    "limit": 200
                }
                
                response = http.get(api_url, params=params)
                response.raise_for_status()
                data = response.json()
                
                if 'bundle' in data:
                    nearby_properties = data['bundle']
                    
                    # Get parcel data for all nearby properties
                    zpids = [str(p.get('zpid')) for p in nearby_properties]
                    parcel_data = get_parcel_data_batch(zpids)
                    
                    # Process and merge data
                    processed_properties = []
                    for prop in nearby_properties:
                        zpid = str(prop.get('zpid'))
                        
                        # Calculate financial metrics
                        zestimate = safe_float(prop.get('zestimate'))
                        rental_zestimate = safe_float(prop.get('rentalZestimate'))
                        cap_rate = (rental_zestimate * 12 * 0.60 / zestimate * 100) if zestimate != 0 else 0
                        
                        # Get property details
                        details = parcel_data.get(zpid, {})
                        living_area = safe_float(details.get('livingArea'))
                        
                        processed_prop = {
                            'address': prop.get('address', ''),
                            'zipcode': prop.get('zipcode', ''),
                            'zestimate': zestimate,
                            'rentalZestimate': rental_zestimate,
                            'capRate': round(cap_rate, 2),
                            'bedrooms': details.get('bedrooms', 0),
                            'bathrooms': details.get('bathrooms', 0),
                            'sqft': living_area,
                            'pricePerSqft': round(zestimate / living_area, 2) if living_area > 0 else 0,
                            'yearBuilt': details.get('yearBuilt', 'N/A')
                        }
                        
                        processed_properties.append(processed_prop)
                    
                    return jsonify(processed_properties), 200
                
        return jsonify({"error": "Property coordinates not found"}), 404
        
    except Exception as e:
        logger.error(f"Error in nearby properties: {str(e)}")
        return jsonify({"error": str(e)}), 500
    
@app.route('/api/save-portfolio', methods=['POST'])
def save_portfolio():
    portfolio_data = request.json
    logger.debug(f"Saving portfolio: {portfolio_data}")
    
    if not portfolio_data or not portfolio_data.get('name'):
        return jsonify({"error": "Portfolio name is required"}), 400
        
    try:
        try:
            with open('portfolios.json', 'r') as f:
                portfolios = json.load(f)
        except FileNotFoundError:
            portfolios = []
        except json.JSONDecodeError:
            portfolios = []
        
        portfolio_data['timestamp'] = datetime.now().isoformat()
        
        portfolio_index = next((i for i, p in enumerate(portfolios) 
                              if p['name'] == portfolio_data['name']), None)
        
        if portfolio_index is not None:
            portfolios[portfolio_index] = portfolio_data
        else:
            portfolios.append(portfolio_data)
        
        with open('portfolios.json', 'w') as f:
            json.dump(portfolios, f)
        
        return jsonify({"message": "Portfolio saved successfully"}), 200
    except Exception as e:
        logger.error(f"Error saving portfolio: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/get-portfolios', methods=['GET'])
def get_portfolios():
    try:
        with open('portfolios.json', 'r') as f:
            portfolios = json.load(f)
        return jsonify(portfolios), 200
    except FileNotFoundError:
        return jsonify([]), 200
    except json.JSONDecodeError:
        logger.error("Invalid JSON in portfolios.json")
        return jsonify([]), 200

@app.route('/api/delete-portfolio', methods=['POST'])
def delete_portfolio():
    portfolio_name = request.json.get('name')
    
    if not portfolio_name:
        return jsonify({"error": "Portfolio name is required"}), 400
        
    try:
        with open('portfolios.json', 'r') as f:
            portfolios = json.load(f)
            
        updated_portfolios = [p for p in portfolios if p.get('name') != portfolio_name]
        
        with open('portfolios.json', 'w') as f:
            json.dump(updated_portfolios, f)
            
        return jsonify({"message": "Portfolio deleted successfully"}), 200
    except FileNotFoundError:
        return jsonify({"error": "No portfolios found"}), 404
    except Exception as e:
        logger.error(f"Error deleting portfolio: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)