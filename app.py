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
    
    chunk_size = 10
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
                        'zoning': parcel.get('Zoning')
                    }
            
            # Add delay between batches to avoid rate limiting
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Error fetching parcel data batch: {str(e)}")
            continue
    
    return all_parcel_data



def get_parcel_square_footage(parcel_id):
    """Get Zillow Calculated Finished Area for a parcel"""
    url = f"https://api.bridgedataoutput.com/api/v2/pub/parcels/{parcel_id}"
    params = {'access_token': API_KEY}
    
    try:
        response = http.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if 'bundle' in data and 'areas' in data['bundle']:
            # Look specifically for Zillow Calculated Finished Area
            for area in data['bundle']['areas']:
                if area.get('type') == 'Zillow Calculated Finished Area':
                    return area.get('areaSquareFeet')
        return None
    except Exception as e:
        logger.error(f"Error getting parcel square footage: {str(e)}")
        return None

@app.route('/api/nearby-transactions', methods=['GET'])
def get_nearby_transactions():
    """Get nearby property transactions with square footage data"""
    address = request.args.get('address')
    radius = request.args.get('radius', '0.5')
    limit = request.args.get('limit', '10')
    
    if not address:
        return jsonify({"error": "Address is required"}), 400
        
    try:
        # Get transactions
        url = "https://api.bridgedataoutput.com/api/v2/pub/transactions"
        params = {
            'access_token': API_KEY,
            'limit': limit,
            'sortBy': 'recordingDate',
            'order': 'desc',
            'near': address,
            'radius': radius
        }
        
        logger.debug(f"Fetching transactions near: {address}")
        response = http.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if not data.get('bundle'):
            return jsonify({"error": "No transactions found"}), 404
            
        transactions = data['bundle']
        processed_transactions = []
        
        for transaction in transactions:
            # Get square footage for each property
            square_feet = None
            if 'parcels' in transaction and transaction['parcels']:
                parcel = transaction['parcels'][0] if isinstance(transaction['parcels'], list) else transaction['parcels']
                if parcel and 'parcelID' in parcel:
                    square_feet = get_parcel_square_footage(parcel['parcelID'])
            
            # Process transaction data
            processed_transaction = {
                'recordingDate': transaction.get('recordingDate'),
                'salesPrice': transaction.get('salesPrice'),
                'documentType': transaction.get('documentType'),
                'category': transaction.get('category'),
                'squareFeet': square_feet,
                'pricePerSqFt': round(transaction.get('salesPrice', 0) / square_feet, 2) if square_feet and transaction.get('salesPrice') else None,
                'address': parcel.get('full') if parcel else None,
                'city': parcel.get('city') if parcel else None,
                'state': parcel.get('state') if parcel else None,
                'buyerName': transaction.get('buyerName'),
                'sellerName': transaction.get('sellerName'),
                'loanAmount': transaction.get('loanAmount')
            }
            
            processed_transactions.append(processed_transaction)
        
        # Calculate summary statistics
        sales_transactions = [t for t in processed_transactions if t['salesPrice'] is not None]
        sqft_transactions = [t for t in sales_transactions if t['squareFeet'] is not None]
        
        summary = {
            'totalTransactions': len(processed_transactions),
            'salesTransactions': len(sales_transactions),
            'averagePrice': sum(t['salesPrice'] for t in sales_transactions) / len(sales_transactions) if sales_transactions else 0,
            'medianPrice': sorted([t['salesPrice'] for t in sales_transactions])[len(sales_transactions)//2] if sales_transactions else 0,
            'averageSquareFeet': sum(t['squareFeet'] for t in sqft_transactions) / len(sqft_transactions) if sqft_transactions else 0,
            'averagePricePerSqFt': sum(t['pricePerSqFt'] for t in sqft_transactions) / len(sqft_transactions) if sqft_transactions else 0
        }
        
        return jsonify({
            'transactions': processed_transactions,
            'summary': summary
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching nearby transactions: {str(e)}")
        return jsonify({"error": str(e)}), 500
@app.route('/')
def home():
    """Render the main dashboard page"""
    return render_template('index.html')

@app.route('/portfolio')
def portfolio():
    """Render the portfolios list page"""
    return render_template('portfolio.html')

@app.route('/transactions')
def transactions():
    """Render the transactions search page"""
    return render_template('transactions.html')

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
        batch = zpid_list[i:i+batch_size]
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
            
            # Add delay between batches
            time.sleep(1)
            
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
                
                response = http.get(api_url, params=params)
                response.raise_for_status()
                data = response.json()
                
                if 'bundle' in data:
                    return jsonify(data['bundle']), 200
                
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