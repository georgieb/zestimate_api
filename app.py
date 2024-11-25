from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import os
import requests
import pandas as pd
from datetime import datetime
import logging
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
import json
import sqlite3
from dataclasses import dataclass
from typing import Optional, List

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

class BridgeTransactions:
    def __init__(self):
        self.api_key = API_KEY
        if not self.api_key:
            raise ValueError("Missing API_KEY in environment variables")

    def get_parcel_details(self, parcel_id):
        """Get building and lot details for a parcel"""
        url = f"https://api.bridgedataoutput.com/api/v2/pub/parcels/{parcel_id}"
        params = {'access_token': self.api_key}
        
        try:
            response = http.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            result = {
                'finished_sqft': None,
                'lot_size_sqft': None,
                'bedrooms': None,
                'bathrooms': None,
                'yearBuilt': None,
                'propertyType': None,
                'zestimate': None,
                'taxAssessedValue': None
            }
            
            if 'bundle' in data:
                bundle = data['bundle']
                if 'areas' in bundle:
                    for area in bundle['areas']:
                        if area.get('type') == 'Zillow Calculated Finished Area':
                            result['finished_sqft'] = area.get('areaSquareFeet')
                
                if 'lot' in bundle:
                    lot_data = bundle['lot']
                    if 'lotSizeSquareFeet' in lot_data:
                        result['lot_size_sqft'] = lot_data['lotSizeSquareFeet']
                    elif 'lotSizeAcres' in lot_data:
                        result['lot_size_sqft'] = lot_data['lotSizeAcres'] * 43560
                
                result['bedrooms'] = safe_float(bundle.get('BedroomsCount'))
                result['bathrooms'] = safe_float(bundle.get('BathroomsTotalCount'))
                result['yearBuilt'] = bundle.get('YearBuilt')
                result['propertyType'] = bundle.get('PropertyTypeName')
                result['taxAssessedValue'] = safe_float(bundle.get('TaxAssessedValue'))
            
            return result
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting parcel details: {e}")
            return result

    def get_zillow_link(self, address, city, state):
        """Generate Zillow search link for property"""
        search_address = f"{address}, {city}, {state}".replace(' ', '-')
        return f"https://www.zillow.com/homes/{search_address}_rb/"

    def get_transactions_near(self, location, radius="0.5", limit=10):
        """Get transactions near a location"""
        logger.debug(f"Fetching transactions near: {location}")
        
        params = {
            'access_token': self.api_key,
            'limit': limit,
            'sortBy': 'recordingDate',
            'order': 'desc',
            'near': location,
            'radius': radius
        }
        
        try:
            response = http.get(
                "https://api.bridgedataoutput.com/api/v2/pub/transactions",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            
            transactions = []
            
            if 'bundle' in data:
                for item in data['bundle']:
                    if 'parcels' not in item or not item['parcels']:
                        continue
                        
                    parcel = item['parcels'][0] if isinstance(item['parcels'], list) else item['parcels']
                    if not isinstance(parcel, dict):
                        continue
                        
                    # Get property details including Zestimate data
                    details = self.get_parcel_details(parcel.get('parcelID', ''))
                    
                    # Calculate price metrics
                    price = item.get('salesPrice')
                    square_feet = details['finished_sqft']
                    lot_size = details['lot_size_sqft']
                    
                    price_per_sqft = None
                    if price and square_feet:
                        price_per_sqft = price / square_feet
                        
                    price_per_lot_sqft = None
                    if price and lot_size:
                        price_per_lot_sqft = price / lot_size
                    
                    # Generate Zillow link
                    zillow_link = self.get_zillow_link(
                        parcel.get('full', ''),
                        parcel.get('city', ''),
                        parcel.get('state', '')
                    )
                    
                    transaction = {
                        'parcel_id': parcel.get('parcelID', ''),
                        'address': parcel.get('full', ''),
                        'city': parcel.get('city', ''),
                        'state': parcel.get('state', ''),
                        'price': price,
                        'square_feet': square_feet,
                        'lot_size_sqft': lot_size,
                        'price_per_sqft': price_per_sqft,
                        'price_per_lot_sqft': price_per_lot_sqft,
                        'recording_date': item.get('recordingDate', ''),
                        'document_type': item.get('documentType', ''),
                        'transaction_type': item.get('category', ''),
                        'buyer_name': ', '.join(item['buyerName']) if isinstance(item.get('buyerName'), list) else item.get('buyerName', ''),
                        'seller_name': ', '.join(item['sellerName']) if isinstance(item.get('sellerName'), list) else item.get('sellerName', ''),
                        'zillow_link': zillow_link,
                        'bedrooms': details['bedrooms'],
                        'bathrooms': details['bathrooms'],
                        'year_built': details['yearBuilt'],
                        'property_type': details['propertyType'],
                        'tax_assessed_value': details['taxAssessedValue']
                    }
                    
                    transactions.append(transaction)
            
            return transactions
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting transactions: {e}")
            return []

# Initialize database
def init_db():
    with sqlite3.connect('real_estate.db') as conn:
        conn.execute('''
        CREATE TABLE IF NOT EXISTS searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location TEXT,
            radius TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        conn.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_id INTEGER,
            parcel_id TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            price REAL,
            square_feet REAL,
            lot_size_sqft REAL,
            price_per_sqft REAL,
            price_per_lot_sqft REAL,
            recording_date DATE,
            document_type TEXT,
            transaction_type TEXT,
            buyer_name TEXT,
            seller_name TEXT,
            zillow_link TEXT,
            bedrooms REAL,
            bathrooms REAL,
            year_built INTEGER,
            property_type TEXT,
            tax_assessed_value REAL,
            FOREIGN KEY (search_id) REFERENCES searches (id)
        )
        ''')

init_db()

# Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    location = request.args.get('location')
    radius = request.args.get('radius', '0.5')
    limit = request.args.get('limit', '10')
    
    if not location:
        return jsonify({"error": "Location is required"}), 400
    
    try:
        api = BridgeTransactions()
        transactions = api.get_transactions_near(location, radius, int(limit))
        
        # Save to database
        with sqlite3.connect('real_estate.db') as conn:
            cursor = conn.execute(
                'INSERT INTO searches (location, radius) VALUES (?, ?)',
                (location, radius)
            )
            search_id = cursor.lastrowid
            
            for t in transactions:
                conn.execute('''
                    INSERT INTO transactions (
                        search_id, parcel_id, address, city, state, price,
                        square_feet, lot_size_sqft, price_per_sqft, price_per_lot_sqft,
                        recording_date, document_type, transaction_type,
                        buyer_name, seller_name, zillow_link, bedrooms,
                        bathrooms, year_built, property_type, tax_assessed_value
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    search_id, t['parcel_id'], t['address'], t['city'], t['state'],
                    t['price'], t['square_feet'], t['lot_size_sqft'],
                    t['price_per_sqft'], t['price_per_lot_sqft'], t['recording_date'],
                    t['document_type'], t['transaction_type'], t['buyer_name'],
                    t['seller_name'], t['zillow_link'], t['bedrooms'], t['bathrooms'],
                    t['year_built'], t['property_type'], t['tax_assessed_value']
                ))
        
        # Calculate summary statistics
        if transactions:
            summary = {
                'total_transactions': len(transactions),
                'average_price': sum(t['price'] for t in transactions if t['price']) / len([t for t in transactions if t['price']]),
                'average_sqft': sum(t['square_feet'] for t in transactions if t['square_feet']) / len([t for t in transactions if t['square_feet']]),
                'average_price_per_sqft': sum(t['price_per_sqft'] for t in transactions if t['price_per_sqft']) / len([t for t in transactions if t['price_per_sqft']]),
                'average_lot_size': sum(t['lot_size_sqft'] for t in transactions if t['lot_size_sqft']) / len([t for t in transactions if t['lot_size_sqft']])
            }
        else:
            summary = {}
        
        return jsonify({
            'transactions': transactions,
            'summary': summary
        }), 200
        
    except Exception as e:
        logger.error(f"Error in get_transactions: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/comps/<parcel_id>')
def get_comps(parcel_id):
    try:
        with sqlite3.connect('real_estate.db') as conn:
            conn.row_factory = sqlite3.Row
            property_data = conn.execute(
                'SELECT * FROM transactions WHERE parcel_id = ?',
                (parcel_id,)
            ).fetchone()
            
            if not property_data:
                return jsonify({'error': 'Property not found'}), 404
            
            api = BridgeTransactions()
            comps = api.get_transactions_near(
                f"{property_data['address']}, {property_data['city']}, {property_data['state']}",
                radius="0.5",
                limit=5
            )
            
            return jsonify({
                'property': dict(property_data),
                'comps': comps
            }), 200
            
    except Exception as e:
        logger.error(f"Error getting comps: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)