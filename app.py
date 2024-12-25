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
    total=20,
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

def calculate_financial_metrics(property_data):
    """Calculate financial metrics for a property"""
    zestimate = safe_float(property_data.get('zestimate'))
    rental_zestimate = safe_float(property_data.get('rentalZestimate'))
    
    # Calculate cap rate (annual net operating income / property value)
    # Assuming 60% of gross rent after expenses
    cap_rate = (rental_zestimate * 12 * 0.60 / zestimate * 100) if zestimate != 0 else 0
    
    return {
        'zestimate': zestimate,
        'rentalZestimate': rental_zestimate,
        'capRate': round(cap_rate, 2)
    }

def get_property_details(zpid):
    """Get detailed property information from the API"""
    url = f"https://api.bridgedataoutput.com/api/v2/pub/properties/{zpid}"
    
    try:
        params = {
            "access_token": API_KEY
        }
        response = http.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if data.get('status', {}).get('code') == 0:
            property_data = data.get('bundle', [{}])[0]
            return {
                'bedrooms': safe_float(property_data.get('BedroomsTotal')),
                'bathrooms': safe_float(property_data.get('BathroomsTotalInteger')),
                'lotSize': safe_float(property_data.get('LotSizeSquareFeet')),
                'yearBuilt': property_data.get('YearBuilt'),
                'livingArea': safe_float(property_data.get('BuildingAreaTotal')),
                'propertyType': property_data.get('PropertyType'),
                'lastSalePrice': safe_float(property_data.get('ListPrice')),
                'lastSaleDate': property_data.get('CloseDate'),
                'stories': safe_float(property_data.get('Stories')),
                'parkingSpaces': safe_float(property_data.get('ParkingTotal')),
                'taxAssessedValue': safe_float(property_data.get('TaxAssessedValue')),
                'taxYear': property_data.get('TaxYear'),
                'propertyTax': safe_float(property_data.get('TaxAnnualAmount')),
                'constructionType': property_data.get('ConstructionMaterials'),
                'roofType': property_data.get('RoofType'),
                'foundation': property_data.get('Foundation'),
                'zoning': property_data.get('Zoning')
            }
    except Exception as e:
        logger.error(f"Error fetching property details for ZPID {zpid}: {str(e)}")
        return {}

def get_property_details_batch(zpids):
    """Get property details for multiple ZPIDs"""
    property_details = {}
    chunk_size = 10
    
    for i in range(0, len(zpids), chunk_size):
        chunk = zpids[i:i + chunk_size]
        for zpid in chunk:
            property_details[zpid] = get_property_details(zpid)
            time.sleep(0.5)  # Rate limiting
    
    return property_details

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
    logger.debug(f"Received request for ZPIDs: {zpid_list}")
    
    if not zpid_list:
        return jsonify({"error": "No ZPIDs provided"}), 400

    api_url = "https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates"
    all_results = []
    
    # Get Zestimate data in batches
    batch_size = 8
    for i in range(0, len(zpid_list), batch_size):
        batch = zpids[i:i+batch_size]
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
            
            time.sleep(1)  # Rate limiting
            
        except requests.RequestException as e:
            logger.error(f"Error fetching Zestimate data: {str(e)}")
            return jsonify({"error": str(e)}), 500

    if all_results:
        # Get property details for all properties
        property_details = get_property_details_batch([str(r.get('zpid')) for r in all_results])
        
        # Process results and merge data
        processed_results = []
        for result in all_results:
            zpid = str(result.get('zpid'))
            
            # Merge property details
            if zpid in property_details:
                result.update(property_details[zpid])
            
            # Calculate financial metrics
            financial_metrics = calculate_financial_metrics(result)
            result.update(financial_metrics)
            
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
        
        # First get the target property's location
        property_url = f"https://api.bridgedataoutput.com/api/v2/pub/properties/{zpid}"
        params = {
            "access_token": API_KEY
        }
        
        response = http.get(property_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if data.get('status', {}).get('code') == 0 and data.get('bundle'):
            property_data = data['bundle'][0]
            latitude = property_data.get('Latitude')
            longitude = property_data.get('Longitude')
            
            if latitude and longitude:
                # Get nearby properties with Zestimates
                zestimate_url = "https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates"
                params = {
                    "access_token": API_KEY,
                    "near": f"{longitude},{latitude}",
                    "limit": 200
                }
                
                response = http.get(zestimate_url, params=params)
                response.raise_for_status()
                nearby_data = response.json()
                
                if 'bundle' in nearby_data:
                    nearby_properties = nearby_data['bundle']
                    
                    # Get property details for nearby properties
                    nearby_zpids = [str(p.get('zpid')) for p in nearby_properties]
                    property_details = get_property_details_batch(nearby_zpids)
                    
                    # Process each nearby property
                    processed_properties = []
                    for prop in nearby_properties:
                        zpid = str(prop.get('zpid'))
                        
                        # Merge property details
                        if zpid in property_details:
                            prop.update(property_details[zpid])
                        
                        # Calculate financial metrics
                        financial_metrics = calculate_financial_metrics(prop)
                        prop.update(financial_metrics)
                        
                        processed_properties.append(prop)
                    
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
