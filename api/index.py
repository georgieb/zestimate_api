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
from urllib3.util.retry import Retry
from pymongo import MongoClient

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
load_dotenv()

# Initialize Flask app
app = Flask(__name__, 
    template_folder='../templates',
    static_folder='../static'
)
CORS(app)

# Environment variables
API_KEY = os.environ.get("API_KEY")
MONGODB_URI = os.environ.get('MONGODB_URI')

# MongoDB setup
client = MongoClient(MONGODB_URI) if MONGODB_URI else None
db = client.get_database("property_portfolio") if client else None
portfolios_collection = db.portfolios if db else None

# Configure retry strategy with backoff
retry_strategy = Retry(
    total=5,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "POST", "OPTIONS"]
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
    """Get parcel data for multiple ZPIDs in a single request with improved rate limiting"""
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
            logger.debug(f"Fetching parcel data for ZPIDs: {chunk}")
            response = http.get(url, params=params)
            
            if response.status_code == 429:
                logger.warning("Rate limit hit, waiting...")
                time.sleep(2)
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
                        'lastSalePrice': safe_float(parcel.get('LastSalePrice')),
                        'lastSaleDate': parcel.get('LastSaleDate'),
                        'stories': safe_float(parcel.get('StoriesCount')),
                        'parkingSpaces': safe_float(parcel.get('ParkingSpaces')),
                        'taxAssessedValue': safe_float(parcel.get('TaxAssessedValue')),
                        'taxYear': parcel.get('TaxYear'),
                        'propertyTax': safe_float(parcel.get('TaxAmount')),
                        'constructionType': parcel.get('ConstructionType'),
                        'roofType': parcel.get('RoofType'),
                        'foundation': parcel.get('Foundation'),
                        'zoning': parcel.get('Zoning'),
                        'address': parcel.get('address', {}).get('full', 'N/A')
                    }
            
            time.sleep(1.5)
            
        except Exception as e:
            logger.error(f"Error fetching parcel data batch: {str(e)}")
            continue
    
    return all_parcel_data

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/portfolio')
def portfolio():
    return render_template('portfolio.html')

@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('../static', path)

@app.route('/api/properties', methods=['POST'])
def get_properties():
    zpid_list = request.json.get('zpids', [])
    logger.debug(f"Received request for ZPIDs: {zpid_list}")
    
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
            
            if response.status_code == 429:
                logger.warning("Rate limit hit, waiting...")
                time.sleep(2)
                response = http.get(api_url, params=params)
                
            response.raise_for_status()
            data = response.json()
            
            if 'bundle' in data:
                all_results.extend(data['bundle'])
            
            time.sleep(1.5)
            
        except requests.RequestException as e:
            logger.error(f"Error fetching Zestimate data: {str(e)}")
            return jsonify({"error": str(e)}), 500

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
                'avg_cap_rate': sum(safe_float(p.get('capRate', 0)) for p in processed_results) / len(processed_results),
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
                    "limit": 200
                }
                
                time.sleep(1)  # Rate limiting
                response = http.get(api_url, params=params)
                response.raise_for_status()
                nearby_data = response.json()
                
                if 'bundle' in nearby_data:
                    properties = nearby_data['bundle']
                    # Add parcel data and calculate metrics
                    zpids = [str(p.get('zpid')) for p in properties]
                    parcel_data = get_parcel_data_batch(zpids)
                    
                    for prop in properties:
                        zpid = str(prop.get('zpid'))
                        if zpid in parcel_data:
                            prop.update(parcel_data[zpid])
                            
                        zestimate = safe_float(prop.get('zestimate'))
                        rental_zestimate = safe_float(prop.get('rentalZestimate'))
                        cap_rate = (rental_zestimate * 12 * 0.60 / zestimate * 100) if zestimate != 0 else 0
                        prop['capRate'] = cap_rate
                    
                    return jsonify(properties), 200
                
        return jsonify({"error": "Property coordinates not found"}), 404
        
    except Exception as e:
        logger.error(f"Error in nearby properties: {str(e)}")
        return jsonify({"error": str(e)}), 500

# In the save_portfolio route, modify to only store ZPIDs and metadata
@app.route('/api/save-portfolio', methods=['POST'])
def save_portfolio():
    portfolio_data = request.json
    logger.debug(f"Saving portfolio: {portfolio_data}")
    
    if not portfolio_data or not portfolio_data.get('name'):
        return jsonify({"error": "Portfolio name is required"}), 400
        
    try:
        # Only store essential non-API data
        stored_portfolio = {
            'name': portfolio_data['name'],
            'zpids': portfolio_data['zpids'],
            'timestamp': datetime.now().isoformat()
        }
        
        if portfolios_collection:
            # Update or insert portfolio in MongoDB
            portfolios_collection.update_one(
                {"name": stored_portfolio['name']},
                {"$set": stored_portfolio},
                upsert=True
            )
        else:
            # Fallback to file storage
            try:
                with open('portfolios.json', 'r') as f:
                    portfolios = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                portfolios = []
            
            # Update existing or add new
            portfolio_index = next((i for i, p in enumerate(portfolios) 
                                  if p['name'] == stored_portfolio['name']), None)
            
            if portfolio_index is not None:
                portfolios[portfolio_index] = stored_portfolio
            else:
                portfolios.append(stored_portfolio)
            
            with open('portfolios.json', 'w') as f:
                json.dump(portfolios, f)
        
        return jsonify({"message": "Portfolio saved successfully"}), 200
    except Exception as e:
        logger.error(f"Error saving portfolio: {str(e)}")
        return jsonify({"error": str(e)}), 500
# Add a new route to load portfolio with fresh data
@app.route('/api/load-portfolio/<name>', methods=['GET'])
def load_portfolio(name):
    try:
        # Get stored portfolio data
        if portfolios_collection:
            stored_portfolio = portfolios_collection.find_one({"name": name}, {'_id': 0})
        else:
            try:
                with open('portfolios.json', 'r') as f:
                    portfolios = json.load(f)
                stored_portfolio = next((p for p in portfolios if p['name'] == name), None)
            except (FileNotFoundError, json.JSONDecodeError):
                stored_portfolio = None

        if not stored_portfolio:
            return jsonify({"error": "Portfolio not found"}), 404

        # Fetch fresh data for the stored ZPIDs
        zpids = stored_portfolio.get('zpids', [])
        if not zpids:
            return jsonify({"error": "No properties in portfolio"}), 400

        # Reuse the existing property fetching logic
        api_url = "https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates"
        all_results = []
        
        # Get Zestimate data in batches
        batch_size = 5
        for i in range(0, len(zpids), batch_size):
            batch = zpids[i:i+batch_size]
            params = {
                "access_token": API_KEY,
                "zpid.in": ",".join(batch)
            }
            
            try:
                response = http.get(api_url, params=params)
                if response.status_code == 429:
                    time.sleep(2)
                    response = http.get(api_url, params=params)
                    
                response.raise_for_status()
                data = response.json()
                
                if 'bundle' in data:
                    all_results.extend(data['bundle'])
                
                time.sleep(1.5)
                
            except requests.RequestException as e:
                logger.error(f"Error fetching Zestimate data: {str(e)}")
                continue

        if all_results:
            # Get fresh parcel data
            parcel_data = get_parcel_data_batch([str(r.get('zpid')) for r in all_results])
            
            # Process results and merge data
            processed_results = []
            for result in all_results:
                zpid = str(result.get('zpid'))
                
                if zpid in parcel_data:
                    result.update(parcel_data[zpid])
                
                zestimate = safe_float(result.get('zestimate'))
                rental_zestimate = safe_float(result.get('rentalZestimate'))
                cap_rate = (rental_zestimate * 12 * 0.60 / zestimate * 100) if zestimate != 0 else 0
                result['capRate'] = cap_rate
                
                processed_results.append(result)

            # Calculate fresh portfolio metrics
            total_value = sum(safe_float(p.get('zestimate')) for p in processed_results)
            total_rental = sum(safe_float(p.get('rentalZestimate')) for p in processed_results)
            total_sqft = sum(safe_float(p.get('livingArea', 0)) for p in processed_results)
            
            portfolio_data = {
                'name': stored_portfolio['name'],
                'timestamp': stored_portfolio['timestamp'],
                'properties': processed_results,
                'summary': {
                    'total_value': total_value,
                    'total_rental': total_rental,
                    'avg_cap_rate': sum(safe_float(p.get('capRate', 0)) for p in processed_results) / len(processed_results),
                    'property_count': len(processed_results),
                    'total_sqft': total_sqft,
                    'avg_price_per_sqft': total_value / total_sqft if total_sqft > 0 else 0,
                    'total_bedrooms': sum(safe_float(p.get('bedrooms', 0)) for p in processed_results),
                    'total_bathrooms': sum(safe_float(p.get('bathrooms', 0)) for p in processed_results)
                }
            }
            
            return jsonify(portfolio_data), 200

        return jsonify({"error": "Failed to fetch property data"}), 500

    except Exception as e:
        logger.error(f"Error loading portfolio: {str(e)}")
        return jsonify({"error": str(e)}), 500
    
@app.route('/api/get-portfolios', methods=['GET'])
def get_portfolios():
    try:
        if portfolios_collection:
            # Get portfolios from MongoDB
            portfolios = list(portfolios_collection.find({}, {'_id': 0}))
        else:
            # Fallback to file storage
            try:
                with open('portfolios.json', 'r') as f:
                    portfolios = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                portfolios = []
        
        return jsonify(portfolios), 200
    except Exception as e:
        logger.error(f"Error getting portfolios: {str(e)}")
        return jsonify([]), 200

@app.route('/api/delete-portfolio', methods=['POST'])
def delete_portfolio():
    portfolio_name = request.json.get('name')
    
    if not portfolio_name:
        return jsonify({"error": "Portfolio name is required"}), 400
        
    try:
        if portfolios_collection:
            # Delete from MongoDB
            result = portfolios_collection.delete_one({"name": portfolio_name})
            success = result.deleted_count > 0
        else:
            # Fallback to file storage
            try:
                with open('portfolios.json', 'r') as f:
                    portfolios = json.load(f)
                
                original_length = len(portfolios)
                portfolios = [p for p in portfolios if p.get('name') != portfolio_name]
                success = len(portfolios) < original_length
                
                with open('portfolios.json', 'w') as f:
                    json.dump(portfolios, f)
            except FileNotFoundError:
                success = False
        
        if success:
            return jsonify({"message": "Portfolio deleted successfully"}), 200
        return jsonify({"error": "Portfolio not found"}), 404
        
    except Exception as e:
        logger.error(f"Error deleting portfolio: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Required for Vercel
app.debug = True