from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import os
import requests
from dotenv import load_dotenv
import json
from datetime import datetime
import logging
import time
import re
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

def normalize_address(address):
    """Normalize an address string for consistent searching"""
    if not address:
        return ""
    
    # Remove extra whitespace and convert to title case
    address = re.sub(r'\s+', ' ', address.strip()).title()
    
    # Common abbreviation standardizations
    abbreviations = {
        'Street': 'St', 'St.': 'St',
        'Avenue': 'Ave', 'Ave.': 'Ave', 
        'Road': 'Rd', 'Rd.': 'Rd',
        'Drive': 'Dr', 'Dr.': 'Dr',
        'Court': 'Ct', 'Ct.': 'Ct',
        'Lane': 'Ln', 'Ln.': 'Ln',
        'Place': 'Pl', 'Pl.': 'Pl',
        'Boulevard': 'Blvd', 'Blvd.': 'Blvd',
        'Circle': 'Cir', 'Cir.': 'Cir',
        'Terrace': 'Ter', 'Ter.': 'Ter',
        'Way': 'Way',
        'North': 'N', 'South': 'S', 'East': 'E', 'West': 'W',
        'Northeast': 'NE', 'Northwest': 'NW', 'Southeast': 'SE', 'Southwest': 'SW'
    }
    
    for full, abbrev in abbreviations.items():
        address = re.sub(rf'\b{full}\b', abbrev, address, flags=re.IGNORECASE)
    
    return address

def parse_address_components(address):
    """Parse address into searchable components"""
    if not address:
        return {}
    
    # Normalize the address first
    normalized = normalize_address(address)
    
    # Split address by commas to separate components
    parts = [part.strip() for part in normalized.split(',')]
    
    components = {}
    
    if len(parts) >= 1:
        # First part is typically street address
        street_part = parts[0]
        
        # Extract house number (digits at the beginning)
        house_match = re.match(r'^(\d+)\s+(.+)', street_part)
        if house_match:
            components['house_number'] = house_match.group(1)
            components['street'] = house_match.group(2)
        else:
            components['street'] = street_part
    
    if len(parts) >= 2:
        # Second part is typically city
        components['city'] = parts[1]
    
    if len(parts) >= 3:
        # Third part is typically state and zip
        state_zip = parts[2].strip().upper()
        state_zip_match = re.match(r'^([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$', state_zip)
        if state_zip_match:
            components['state'] = state_zip_match.group(1)
            components['zip'] = state_zip_match.group(2)
        else:
            # Try to extract just state if no zip
            state_match = re.match(r'^([A-Z]{2})$', state_zip)
            if state_match:
                components['state'] = state_match.group(1)
    
    return components

def is_zpid(input_str):
    """Check if input string is a ZPID (numeric)"""
    if not input_str:
        return False
    return input_str.strip().isdigit()

def search_properties_by_address(address):
    """Search for properties by address using the parcels API"""
    if not address:
        return []
    
    components = parse_address_components(address)
    logger.debug(f"Parsed address components: {components}")
    
    # Build search parameters
    params = {"access_token": API_KEY}
    
    # Add address components to search
    if 'house_number' in components:
        params['address.house'] = components['house_number']
    if 'street' in components:
        params['address.street'] = components['street']
    if 'city' in components:
        params['address.city'] = components['city']
    if 'state' in components:
        params['address.state'] = components['state']
    if 'zip' in components:
        params['address.zip'] = components['zip']
    
    url = "https://api.bridgedataoutput.com/api/v2/pub/parcels"
    
    try:
        logger.debug(f"Searching parcels with params: {params}")
        response = http.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        logger.debug(f"Parcels search response: {data}")
        
        if data.get('success') and data.get('bundle'):
            zpids = []
            for parcel in data['bundle']:
                zpid = parcel.get('zpid')
                if zpid:
                    zpids.append(str(zpid))
            
            logger.debug(f"Found ZPIDs from address search: {zpids}")
            return zpids
        
        return []
        
    except Exception as e:
        logger.error(f"Error searching by address: {str(e)}")
        return []

def get_living_area_from_parcel(areas):
    """Extract living area from parcel data areas, checking multiple area types"""
    if not areas:
        return 0
        
    # Check different area types in order of preference
    area_types = [
        'Living Building Area',
        'Finished Building Area',
        'Total Building Area',
        'Zillow Calculated Finished Area'
    ]
    
    for area_type in area_types:
        area = next((
            area.get('areaSquareFeet', 0)
            for area in areas
            if area.get('type') == area_type
        ), 0)
        if area:
            return area
    return 0

def process_parcel_data(parcel):
    """Process a single parcel record and extract relevant data"""
    if not parcel:
        return None
        
    # Get building info
    buildings = parcel.get('building', [])
    building = buildings[0] if buildings else {}
    
    # Get living area
    areas = parcel.get('areas', [])
    living_area = get_living_area_from_parcel(areas)
    
    return {
        'bedrooms': safe_float(building.get('bedrooms')),
        'bathrooms': safe_float(building.get('fullBaths', building.get('baths'))),
        'livingArea': living_area,
        'yearBuilt': building.get('yearBuilt'),
        'propertyType': parcel.get('landUseDescription'),
        'stories': safe_float(building.get('totalStories')),
        'lotSize': safe_float(parcel.get('lotSizeSquareFeet'))
    }

def get_parcel_data_batch(zpids):
    """Get parcel data for multiple ZPIDs in a single request"""
    if not zpids:
        return {}
        
    url = "https://api.bridgedataoutput.com/api/v2/pub/parcels"
    all_parcel_data = {}
    chunk_size = 10
    
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
            logger.debug(f"Parcel API response: {data}")
            
            if data.get('success') and data.get('bundle'):
                for parcel in data['bundle']:
                    zpid = str(parcel.get('zpid'))
                    if not zpid:
                        continue
                    
                    parcel_info = process_parcel_data(parcel)
                    if parcel_info:
                        all_parcel_data[zpid] = parcel_info
            
            time.sleep(1)  # Rate limiting
            
        except Exception as e:
            logger.error(f"Error processing parcel data for chunk {chunk}: {str(e)}")
            continue
    
    logger.debug(f"Final parcel data count: {len(all_parcel_data)}")
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
    data = request.json
    zpid_list = data.get('zpids', [])
    address_list = data.get('addresses', [])
    
    logger.debug(f"Received request for {len(zpid_list)} ZPIDs and {len(address_list)} addresses")
    
    # Convert addresses to ZPIDs
    all_zpids = list(zpid_list)  # Start with existing ZPIDs
    
    if address_list:
        for address in address_list:
            if address.strip():
                found_zpids = search_properties_by_address(address.strip())
                if found_zpids:
                    all_zpids.extend(found_zpids)
                    logger.debug(f"Address '{address}' converted to ZPIDs: {found_zpids}")
                else:
                    logger.warning(f"No properties found for address: {address}")
    
    if not all_zpids:
        return jsonify({"error": "No properties found for the provided addresses/ZPIDs"}), 400
    
    # Remove duplicates while preserving order
    zpid_list = list(dict.fromkeys(all_zpids))
    logger.debug(f"Final ZPID list after address conversion: {zpid_list}")

    api_url = "https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates"
    all_results = []
    
    # Process Zestimates in batches
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
        # Get parcel data for all properties
        zpids = [str(r.get('zpid')) for r in all_results]
        parcel_data = get_parcel_data_batch(zpids)
        
        # Process results and merge data
        processed_results = []
        for result in all_results:
            zpid = str(result.get('zpid'))
            
            # Start with basic property info
            property_info = {
                'zpid': zpid,
                'address': result.get('address'),
                'zestimate': safe_float(result.get('zestimate')),
                'rentalZestimate': safe_float(result.get('rentalZestimate')),
                'latitude': result.get('Latitude'),
                'longitude': result.get('Longitude'),
                'bedrooms': 0,
                'bathrooms': 0,
                'livingArea': 0,
                'yearBuilt': 'N/A',
                'propertyType': None,
                'stories': 0,
                'lotSize': 0
            }
            
            # Merge parcel data if available
            if zpid in parcel_data:
                property_info.update(parcel_data[zpid])
            
            # Calculate cap rate
            if property_info['zestimate'] > 0:
                property_info['capRate'] = round(
                    (property_info['rentalZestimate'] * 12 * 0.60 / property_info['zestimate'] * 100),
                    2
                )
            else:
                property_info['capRate'] = 0
            
            processed_results.append(property_info)

        # Calculate portfolio metrics
        total_value = sum(safe_float(p['zestimate']) for p in processed_results)
        total_rental = sum(safe_float(p['rentalZestimate']) for p in processed_results)
        total_sqft = sum(safe_float(p['livingArea']) for p in processed_results)
        
        portfolio_metrics = {
            'properties': processed_results,
            'summary': {
                'total_value': total_value,
                'total_rental': total_rental,
                'avg_cap_rate': sum(p['capRate'] for p in processed_results) / len(processed_results),
                'property_count': len(processed_results),
                'total_sqft': total_sqft,
                'avg_price_per_sqft': total_value / total_sqft if total_sqft > 0 else 0,
                'total_bedrooms': sum(safe_float(p['bedrooms']) for p in processed_results),
                'total_bathrooms': sum(safe_float(p['bathrooms']) for p in processed_results)
            }
        }
        
        return jsonify(portfolio_metrics), 200
    
    return jsonify({"error": "No results found"}), 404

@app.route('/nearby/<zpid>')
def nearby_page(zpid):
    """Render the nearby properties page"""
    return render_template('nearby.html', zpid=zpid)  # Pass zpid to template

@app.route('/api/nearby-properties/<zpid>', methods=['GET'])
def nearby_properties(zpid):
    try:
        logger.debug(f"Fetching nearby properties for ZPID: {zpid}")
        api_url = "https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates"
        
        # First get the source property
        response = http.get(api_url, params={
            "access_token": API_KEY,
            "zpid": zpid
        })
        response.raise_for_status()
        source_data = response.json()
        
        if not source_data.get('bundle'):
            return jsonify({"error": "Source property not found"}), 404
            
        property_data = source_data['bundle'][0]
        latitude = property_data.get('Latitude')
        longitude = property_data.get('Longitude')
        
        if not (latitude and longitude):
            return jsonify({"error": "Property coordinates not found"}), 404
            
        # Get nearby properties
        response = http.get(api_url, params={
            "access_token": API_KEY,
            "near": f"{longitude},{latitude}",
            "limit": 20
        })
        response.raise_for_status()
        data = response.json()
        logger.debug(f"Nearby properties response: {data}")
        
        if not data or not data.get('bundle'):
            return jsonify([]), 200

        # Extract all zpids from the nearby properties
        nearby_zpids = [str(prop['zpid']) for prop in data['bundle'] if prop.get('zpid')]
        logger.debug(f"Found {len(nearby_zpids)} nearby property ZPIDs")

        # Get parcel data for all properties in batches
        parcel_data = {}
        batch_size = 10
        
        for i in range(0, len(nearby_zpids), batch_size):
            batch = nearby_zpids[i:i + batch_size]
            logger.debug(f"Fetching parcel data for batch {i//batch_size + 1}")
            
            parcel_response = http.get(
                "https://api.bridgedataoutput.com/api/v2/pub/parcels",
                params={
                    "access_token": API_KEY,
                    "zpid.in": ",".join(batch)
                }
            )
            parcel_response.raise_for_status()
            parcel_results = parcel_response.json()
            
            if parcel_results.get('bundle'):
                for parcel in parcel_results['bundle']:
                    zpid = str(parcel.get('zpid'))
                    if not zpid:
                        continue
                        
                    # Get building info
                    buildings = parcel.get('building', [])
                    building = buildings[0] if buildings else {}
                    
                    # Get living area - check multiple area types
                    areas = parcel.get('areas', [])
                    living_area = 0
                    
                    # Check different area types in order of preference
                    area_types = [
                        'Living Building Area',
                        'Finished Building Area',
                        'Total Building Area',
                        'Zillow Calculated Finished Area'
                    ]
                    
                    for area_type in area_types:
                        area = next((
                            area.get('areaSquareFeet', 0)
                            for area in areas
                            if area.get('type') == area_type
                        ), 0)
                        if area:
                            living_area = area
                            break
                    
                    parcel_data[zpid] = {
                        'bedrooms': safe_float(building.get('bedrooms')),
                        'bathrooms': safe_float(building.get('fullBaths', building.get('baths'))),
                        'livingArea': living_area,
                        'yearBuilt': building.get('yearBuilt'),
                        'propertyType': parcel.get('landUseDescription')
                    }
            
            time.sleep(1)  # Rate limiting between batches
        
        # Process and combine the data
        nearby_properties = []
        for prop in data['bundle']:
            zpid = str(prop.get('zpid'))
            property_info = {
                'zpid': zpid,
                'address': prop.get('address'),
                'zestimate': safe_float(prop.get('zestimate')),
                'rentalZestimate': safe_float(prop.get('rentalZestimate')),
                'latitude': prop.get('Latitude'),
                'longitude': prop.get('Longitude'),
                'bedrooms': 0,
                'bathrooms': 0,
                'livingArea': 0,
                'yearBuilt': 'N/A',
                'propertyType': None
            }
            
            # Update with parcel data if available
            if zpid in parcel_data:
                property_info.update(parcel_data[zpid])
            
            # Calculate cap rate
            if property_info['zestimate'] > 0:
                property_info['capRate'] = round(
                    (property_info['rentalZestimate'] * 12 * 0.60 / property_info['zestimate'] * 100),
                    2
                )
            else:
                property_info['capRate'] = 0
            
            nearby_properties.append(property_info)
        
        logger.debug(f"Returning {len(nearby_properties)} properties with parcel data")
        return jsonify(nearby_properties), 200
        
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

@app.route('/api/validate-address', methods=['POST'])
def validate_address():
    """Validate an address and return parsed components and potential matches"""
    data = request.json
    address = data.get('address', '')
    
    if not address:
        return jsonify({"error": "Address is required"}), 400
    
    try:
        # Parse address components
        components = parse_address_components(address)
        normalized = normalize_address(address)
        
        # Search for properties with this address
        zpids = search_properties_by_address(address)
        
        result = {
            "original": address,
            "normalized": normalized,
            "components": components,
            "zpids_found": zpids,
            "is_valid": len(zpids) > 0,
            "property_count": len(zpids)
        }
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error validating address: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/parse-input', methods=['POST'])
def parse_input():
    """Parse mixed input of addresses and ZPIDs"""
    data = request.json
    input_text = data.get('input', '')
    
    if not input_text:
        return jsonify({"error": "Input is required"}), 400
    
    try:
        lines = [line.strip() for line in input_text.split('\n') if line.strip()]
        
        zpids = []
        addresses = []
        invalid_entries = []
        
        for line in lines:
            # Check if the entire line is a ZPID first
            if is_zpid(line):
                zpids.append(line)
            elif len(line) > 10 and ',' in line:  # Likely a full address with commas
                addresses.append(line)
            else:
                # Split by comma and process each item
                items = [item.strip() for item in line.split(',') if item.strip()]
                
                for item in items:
                    if is_zpid(item):
                        zpids.append(item)
                    elif len(item) > 3:  # Assume anything longer than 3 chars might be an address
                        addresses.append(item)
                    else:
                        invalid_entries.append(item)
        
        # Validate addresses and get ZPIDs
        address_results = []
        for address in addresses:
            found_zpids = search_properties_by_address(address)
            address_results.append({
                "address": address,
                "zpids": found_zpids,
                "found": len(found_zpids) > 0
            })
        
        result = {
            "zpids": zpids,
            "addresses": addresses,
            "address_results": address_results,
            "invalid_entries": invalid_entries,
            "total_properties_found": len(zpids) + sum(len(r["zpids"]) for r in address_results)
        }
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error parsing input: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)