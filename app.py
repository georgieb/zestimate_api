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
# Removed geopy imports - using direct API address filtering instead

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

# Using direct Bridge API address filtering - no geocoding needed

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
    parts = [part.strip() for part in normalized.split(',') if part.strip()]
    
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
    
    # Handle state and zip - could be in different formats
    if len(parts) >= 3:
        # Look through remaining parts for state and zip
        for i in range(2, len(parts)):
            part = parts[i].strip().upper()
            
            # Check if this part contains both state and zip
            state_zip_match = re.match(r'^([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$', part)
            if state_zip_match:
                components['state'] = state_zip_match.group(1)
                components['zip'] = state_zip_match.group(2)
                break
            
            # Check if this is just a state
            state_match = re.match(r'^([A-Z]{2})$', part)
            if state_match:
                components['state'] = state_match.group(1)
                continue
            
            # Check if this is just a zip code
            zip_match = re.match(r'^(\d{5}(?:-\d{4})?)$', part)
            if zip_match:
                components['zip'] = zip_match.group(1)
                continue
    
    return components

def is_zpid(input_str):
    """Check if input string is a ZPID (numeric)"""
    if not input_str:
        return False
    return input_str.strip().isdigit()

def find_best_address_match(address, nearby_zpids):
    """Find the best matching property from nearby results by comparing addresses"""
    if not nearby_zpids or not address:
        return []
    
    search_components = parse_address_components(address)
    search_house_number = search_components.get('house_number', '').lower()
    search_street = search_components.get('street', '').lower().replace('nw', 'northwest').replace('ne', 'northeast').replace('sw', 'southwest').replace('se', 'southeast')
    search_city = search_components.get('city', '').lower()
    
    logger.info(f"Looking for match - House: {search_house_number}, Street: {search_street}, City: {search_city}")
    logger.info(f"Checking {len(nearby_zpids)} nearby properties for address match")
    
    # Get addresses from zestimates API to compare
    api_url = "https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates"
    
    exact_matches = []
    close_matches = []
    
    for i, zpid in enumerate(nearby_zpids[:15]):  # Check more properties
        try:
            response = http.get(api_url, params={
                "access_token": API_KEY,
                "zpid": zpid
            })
            response.raise_for_status()
            data = response.json()
            
            if data.get('bundle'):
                prop = data['bundle'][0]
                prop_address = prop.get('address', '').lower()
                
                if prop_address:
                    logger.info(f"Property {i+1}: ZPID {zpid} = '{prop_address}'")
                    
                    # Simple but effective matching - look for house number in the address
                    if search_house_number and search_house_number in prop_address:
                        # Also check if street name appears (even partially)
                        street_words = search_street.split()
                        street_matches = 0
                        for word in street_words:
                            if len(word) > 2 and word in prop_address:  # Skip tiny words like "nw"
                                street_matches += 1
                        
                        if street_matches > 0:
                            logger.info(f"*** MATCH FOUND: House number {search_house_number} and street components found in {prop_address}")
                            exact_matches.append(zpid)
                            break  # Take the first good match
            
            time.sleep(0.2)  # Rate limiting
            
        except Exception as e:
            logger.error(f"Error checking address for ZPID {zpid}: {str(e)}")
            continue
    
    # Return the best match found
    if exact_matches:
        logger.info(f"Returning exact match: {exact_matches[0]}")
        return exact_matches[:1]
    else:
        logger.warning(f"No address matches found for {address}")
        return []

def search_properties_by_address(address):
    """Search for properties by address using Bridge parcels API address.full parameter"""
    if not address:
        return []
    
    logger.info(f"Searching for property at address: {address}")
    
    parcels_url = "https://api.bridgedataoutput.com/api/v2/pub/parcels"
    
    # Normalize the address for search
    normalized_address = normalize_address(address)
    
    # Try multiple search strategies
    search_attempts = [
        # Strategy 1: Exact address as provided
        {"address.full": address},
        # Strategy 2: Normalized address
        {"address.full": normalized_address},
        # Strategy 3: Try with different comma placement
        {"address.full": address.replace(",", "")},
        # Strategy 4: Try with title case
        {"address.full": address.title()},
    ]
    
    for attempt_num, search_params in enumerate(search_attempts, 1):
        try:
            params = {
                "access_token": API_KEY,
                **search_params
            }
            
            logger.info(f"Attempt {attempt_num}: Searching with address.full = '{list(search_params.values())[0]}'")
            
            response = http.get(parcels_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('success') and data.get('bundle'):
                zpids = []
                for parcel in data['bundle']:
                    zpid = parcel.get('zpid')
                    if zpid:
                        zpids.append(str(zpid))
                        parcel_address = parcel.get('address', {})
                        if isinstance(parcel_address, dict):
                            full_addr = parcel_address.get('full', 'N/A')
                        else:
                            full_addr = str(parcel_address)
                        logger.info(f"MATCH FOUND: {full_addr} -> ZPID {zpid}")
                
                if zpids:
                    logger.info(f"Successfully found {len(zpids)} properties on attempt {attempt_num}")
                    return zpids
            
        except Exception as e:
            logger.error(f"Attempt {attempt_num} failed: {str(e)}")
            continue
    
    # If direct address.full searches didn't work, try fallback with city/zip area search
    logger.info("Direct address search failed, trying fallback city/zip search")
    return search_properties_by_address_fallback(address)

def are_property_types_compatible(source_type, target_type):
    """Check if two property types are compatible for comparison - strict matching"""
    if not source_type or not target_type:
        return False  # If we don't know the type, don't allow it for better filtering
    
    source_type = source_type.lower().strip()
    target_type = target_type.lower().strip()
    
    # Define strict property type groups for matching
    single_family_types = [
        'single family residential', 
        'single family dwelling', 
        'single-family residential',
        'residential single family',
        'detached single family', 
        'single family detached'
    ]
    
    condo_types = [
        'condominium', 
        'condo', 
        'residential condo', 
        'condominium unit',
        'townhouse', 
        'townhome', 
        'row house',
        'townhouse residential'
    ]
    
    multi_family_types = [
        'duplex', 
        'triplex', 
        'quadruplex', 
        'multi-family', 
        'multifamily',
        'apartment', 
        'apartment building', 
        '2-4 family',
        'multi family residential'
    ]
    
    mobile_home_types = [
        'mobile home', 
        'manufactured home', 
        'mobile home park',
        'manufactured housing', 
        'trailer',
        'mobile home residential'
    ]
    
    # Check if both types are in the same specific category
    type_groups = [
        ('single_family', single_family_types),
        ('condo', condo_types), 
        ('multi_family', multi_family_types),
        ('mobile_home', mobile_home_types)
    ]
    
    source_category = None
    target_category = None
    
    # Determine source category
    for category_name, group in type_groups:
        if any(group_type in source_type for group_type in group):
            source_category = category_name
            break
    
    # Determine target category  
    for category_name, group in type_groups:
        if any(group_type in target_type for group_type in group):
            target_category = category_name
            break
    
    # Only match if both are in the same specific category
    if source_category and target_category and source_category == target_category:
        return True
    
    # Special case: if source is "Single Family Residential" and target is generic "Residential"
    # but only if target is NOT mobile home, condo, or multi-family
    if source_category == 'single_family' and 'residential' in target_type:
        # Make sure target is not in other specific categories
        if not any(category in target_category for category in ['mobile_home', 'condo', 'multi_family'] if target_category):
            return True
    
    return False

def search_properties_by_address_fallback(address):
    """Fallback search using city/zip when address.full doesn't work"""
    components = parse_address_components(address)
    search_city = components.get('city', '')
    search_zip = components.get('zip', '')
    
    if not search_city or not search_zip:
        logger.warning(f"Fallback failed - address missing city or zip: {address}")
        return []
    
    parcels_url = "https://api.bridgedataoutput.com/api/v2/pub/parcels"
    
    try:
        params = {
            "access_token": API_KEY,
            "address.city": search_city,
            "address.zip": search_zip,
            "limit": 100
        }
        
        logger.info(f"Fallback: Searching parcels in {search_city}, {search_zip}")
        
        response = http.get(parcels_url, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        if not data.get('success') or not data.get('bundle'):
            logger.warning(f"Fallback: No parcels found in {search_city}, {search_zip}")
            return []
        
        # Look for exact address matches in the area results
        search_house_number = components.get('house_number', '').lower()
        search_street = components.get('street', '').lower()
        
        matching_zpids = []
        
        for parcel in data['bundle']:
            parcel_address = parcel.get('address', {})
            
            if isinstance(parcel_address, dict):
                parcel_house = str(parcel_address.get('house', '')).lower()
                parcel_street = parcel_address.get('street', '').lower()
                full_addr = parcel_address.get('full', '')
            else:
                # Try to parse from string
                house_match = re.match(r'^(\d+)\s+(.+)', str(parcel_address).strip())
                if house_match:
                    parcel_house = house_match.group(1).lower()
                    parcel_street = house_match.group(2).lower()
                else:
                    continue
                full_addr = str(parcel_address)
            
            # Check for house number and street match
            if (search_house_number and parcel_house and search_house_number == parcel_house and
                search_street and parcel_street and search_street in parcel_street):
                zpid = parcel.get('zpid')
                if zpid:
                    logger.info(f"Fallback MATCH: {full_addr} -> ZPID {zpid}")
                    matching_zpids.append(str(zpid))
        
        return matching_zpids
        
    except Exception as e:
        logger.error(f"Fallback search failed: {str(e)}")
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
        logger.info(f"Fetching nearby properties for ZPID: {zpid}")
        api_url = "https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates"
        
        # First get the source property
        logger.debug(f"Getting source property data for ZPID: {zpid}")
        response = http.get(api_url, params={
            "access_token": API_KEY,
            "zpid": zpid
        })
        
        if response.status_code != 200:
            logger.error(f"Failed to get source property. Status: {response.status_code}, Response: {response.text}")
            return jsonify({"error": f"Failed to get source property: {response.status_code}"}), 500
            
        source_data = response.json()
        logger.debug(f"Source property response: {source_data}")
        
        if not source_data.get('bundle'):
            logger.warning(f"No source property found for ZPID: {zpid}")
            return jsonify({"error": "Source property not found"}), 404
            
        property_data = source_data['bundle'][0]
        latitude = property_data.get('Latitude')
        longitude = property_data.get('Longitude')
        
        logger.debug(f"Source property coordinates: lat={latitude}, lng={longitude}")
        
        if not (latitude and longitude):
            logger.error(f"Property coordinates not found for ZPID: {zpid}")
            return jsonify({"error": "Property coordinates not found"}), 404
            
        # Always get the source property type from parcels API (zestimates API doesn't have landUseDescription)
        source_property_type = None
        logger.debug(f"Getting source property type from parcels API for ZPID: {zpid}")
        
        source_parcel_response = http.get(
            "https://api.bridgedataoutput.com/api/v2/pub/parcels",
            params={
                "access_token": API_KEY,
                "zpid": zpid
            }
        )
        
        if source_parcel_response.status_code == 200:
            source_parcel_data = source_parcel_response.json()
            if source_parcel_data.get('bundle'):
                source_property_type = source_parcel_data['bundle'][0].get('landUseDescription')
                logger.info(f"Source property ZPID {zpid} has landUseDescription: '{source_property_type}'")
            else:
                logger.warning(f"No parcel data found for source ZPID: {zpid}")
        else:
            logger.error(f"Failed to get source parcel data. Status: {source_parcel_response.status_code}")
        
        if not source_property_type:
            logger.warning(f"Could not determine source property type for ZPID: {zpid}, proceeding without strict filtering")
            return jsonify([]), 200
        
        # Get nearby properties - increase limit to get more candidates before filtering
        logger.debug(f"Getting nearby properties for coordinates: {longitude},{latitude}")
        response = http.get(api_url, params={
            "access_token": API_KEY,
            "near": f"{longitude},{latitude}",
            "limit": 50  # Get more candidates to filter down to 20 matches
        })
        
        if response.status_code != 200:
            logger.error(f"Failed to get nearby properties. Status: {response.status_code}, Response: {response.text}")
            return jsonify({"error": f"Failed to get nearby properties: {response.status_code}"}), 500
            
        data = response.json()
        logger.debug(f"Nearby properties API response success: {data.get('success', False)}, count: {len(data.get('bundle', []))}")
        
        if not data or not data.get('bundle'):
            logger.info("No nearby properties found, returning empty list")
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
        
        # Process and combine the data - filter for matching property types
        nearby_properties = []
        compatible_properties = []
        residential_property_types = [
            'Single Family Residential',
            'Single Family Dwelling',
            'Residential',
            'Single-Family',
            'Duplex',
            'Triplex',
            'Quadruplex',
            'Condominium',
            'Apartment',
            'Townhouse',
            'Multi-Family',
            'Residential Condo',
            'Mobile Home',
            'Manufactured Home'
        ]
        
        # Property types to exclude completely
        excluded_property_types = [
            'vacant land',
            'residential vacant land',
            'vacant',
            'land',
            'commercial',
            'industrial',
            'retail',
            'office',
            'warehouse',
            'parking'
        ]
        
        for prop in data['bundle']:
            prop_zpid = str(prop.get('zpid'))
            
            # Skip the source property itself
            if prop_zpid == str(zpid):
                logger.debug(f"Skipping source property ZPID: {prop_zpid}")
                continue
                
            property_info = {
                'zpid': prop_zpid,
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
            
            # Update with parcel data if available - REQUIRED for property type filtering
            if prop_zpid in parcel_data:
                property_info.update(parcel_data[prop_zpid])
            else:
                # Skip properties without parcel data since we can't determine their type
                logger.debug(f"Skipping property without parcel data: ZPID {prop_zpid}")
                continue
            
            # Filter for residential properties only
            property_type = property_info.get('propertyType') or ''
            property_type = property_type.strip() if property_type else ''
            property_type_lower = property_type.lower()
            
            logger.debug(f"Property ZPID {prop_zpid} has landUseDescription: '{property_type}'")
            
            # First check if it's an excluded property type (vacant land, commercial, etc.)
            is_excluded = False
            if property_type:
                for excluded_type in excluded_property_types:
                    if excluded_type.lower() in property_type_lower:
                        is_excluded = True
                        logger.debug(f"Excluding property type: ZPID {prop_zpid}, Type: '{property_type}'")
                        break
            
            if is_excluded:
                continue
            
            # Now check if it's residential
            is_residential = False
            
            if property_type:
                # Check if property type contains any residential keywords
                for residential_type in residential_property_types:
                    if residential_type.lower() in property_type_lower:
                        is_residential = True
                        break
                
                # Also include properties with bedrooms as likely residential
                if not is_residential and property_info.get('bedrooms', 0) > 0:
                    is_residential = True
                    logger.debug(f"Including property with bedrooms as residential: ZPID {prop_zpid}, Type: {property_type}, Bedrooms: {property_info.get('bedrooms')}")
            else:
                # If no property type, check if it has bedrooms (likely residential)
                if property_info.get('bedrooms', 0) > 0:
                    is_residential = True
                    logger.debug(f"Including property with bedrooms and no type as residential: ZPID {prop_zpid}, Bedrooms: {property_info.get('bedrooms')}")
            
            # Skip non-residential properties
            if not is_residential:
                logger.debug(f"Filtering out non-residential property: ZPID {prop_zpid}, Type: '{property_type}', Bedrooms: {property_info.get('bedrooms', 0)}")
                continue
            
            # Check if property type matches source property type
            is_compatible = are_property_types_compatible(source_property_type, property_type)
            logger.debug(f"Property type compatibility check: Source='{source_property_type}' vs Target='{property_type}' -> Compatible={is_compatible}")
            
            # Calculate cap rate
            if property_info['zestimate'] > 0:
                property_info['capRate'] = round(
                    (property_info['rentalZestimate'] * 12 * 0.60 / property_info['zestimate'] * 100),
                    2
                )
            else:
                property_info['capRate'] = 0
            
            if is_compatible:
                compatible_properties.append(property_info)
                logger.info(f"✅ COMPATIBLE: ZPID {prop_zpid}, Type: '{property_type}' matches source type: '{source_property_type}'")
            else:
                nearby_properties.append(property_info)
                logger.info(f"❌ DIFFERENT TYPE: ZPID {prop_zpid}, Type: '{property_type}' vs source: '{source_property_type}'")
        
        # Prioritize compatible properties, then add others if we need more
        final_properties = compatible_properties[:20]  # Take up to 20 compatible properties first
        
        if len(final_properties) < 20:
            # Add other residential properties to reach 20 if needed
            remaining_slots = 20 - len(final_properties)
            final_properties.extend(nearby_properties[:remaining_slots])
        
        nearby_properties = final_properties
        
        compatible_count = len(compatible_properties)
        other_count = len(nearby_properties) - compatible_count
        logger.info(f"Source property type: '{source_property_type}' -> Found {len(nearby_properties)} properties ({compatible_count} compatible + {other_count} other residential) from {len(data['bundle'])} total nearby properties")
        
        # If no residential properties found, return a limited set of all properties as fallback
        if not nearby_properties and data['bundle']:
            logger.warning("No residential properties found with filtering, returning all properties as fallback")
            for prop in data['bundle'][:10]:  # Limit to 10 properties as fallback
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
        
        return jsonify(nearby_properties), 200
        
    except Exception as e:
        logger.error(f"Error in nearby properties for ZPID {zpid}: {str(e)}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
    
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

@app.route('/api/debug-parcels', methods=['POST'])
def debug_parcels():
    """Debug endpoint to see what parcels are found in an area"""
    data = request.json
    address = data.get('address', '')
    
    if not address:
        return jsonify({"error": "Address is required"}), 400
    
    components = parse_address_components(address)
    search_city = components.get('city', '')
    search_zip = components.get('zip', '')
    
    if not search_city or not search_zip:
        return jsonify({"error": "Address missing city or zip"}), 400
    
    parcels_url = "https://api.bridgedataoutput.com/api/v2/pub/parcels"
    
    try:
        params = {
            "access_token": API_KEY,
            "address.city": search_city,
            "address.zip": search_zip,
            "limit": 20
        }
        
        response = http.get(parcels_url, params=params)
        response.raise_for_status()
        
        data_result = response.json()
        
        parcels_info = []
        for parcel in data_result.get('bundle', []):
            parcel_address = parcel.get('address', {})
            
            if isinstance(parcel_address, dict):
                full_addr = parcel_address.get('full', 'N/A')
            else:
                full_addr = str(parcel_address)
            
            parcels_info.append({
                "zpid": parcel.get('zpid'),
                "address": full_addr,
                "address_obj": parcel_address
            })
        
        return jsonify({
            "search": f"{search_city}, {search_zip}",
            "components": components,
            "found_count": len(parcels_info),
            "parcels": parcels_info
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/test-address-fields', methods=['POST'])
def test_address_fields():
    """Test direct address field filtering on Bridge API"""
    data = request.json
    address = data.get('address', '')
    
    if not address:
        return jsonify({"error": "Address is required"}), 400
    
    components = parse_address_components(address)
    
    results = {}
    
    # Test both APIs with different address field combinations
    test_apis = [
        {
            "name": "zestimates_api",
            "url": "https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates"
        },
        {
            "name": "parcels_api", 
            "url": "https://api.bridgedataoutput.com/api/v2/pub/parcels"
        }
    ]
    
    # Different parameter combinations to test
    test_combinations = [
        # Test 1: Full address components
        {
            "name": "full_components",
            "params": {
                "access_token": API_KEY,
                "address.street": components.get('street', ''),
                "address.city": components.get('city', ''),
                "address.state": components.get('state', ''),
                "address.zip": components.get('zip', '')
            }
        },
        # Test 2: House number + street
        {
            "name": "house_and_street", 
            "params": {
                "access_token": API_KEY,
                "address.house": components.get('house_number', ''),
                "address.street": components.get('street', ''),
                "address.city": components.get('city', '')
            }
        },
        # Test 3: Just city and zip
        {
            "name": "city_and_zip",
            "params": {
                "access_token": API_KEY,
                "address.city": components.get('city', ''),
                "address.zip": components.get('zip', '')
            }
        },
        # Test 4: Try different field names
        {
            "name": "alt_field_names",
            "params": {
                "access_token": API_KEY,
                "street": components.get('street', ''),
                "city": components.get('city', ''),
                "state": components.get('state', ''),
                "zip": components.get('zip', '')
            }
        }
    ]
    
    for api in test_apis:
        api_results = {}
        
        for test in test_combinations:
            try:
                # Remove empty parameters
                clean_params = {k: v for k, v in test["params"].items() if v}
                
                logger.info(f"Testing {api['name']} - {test['name']} with params: {clean_params}")
                
                response = http.get(api["url"], params=clean_params)
                
                # Check if it's a 400 error (bad parameters) vs other errors
                if response.status_code == 400:
                    api_results[test["name"]] = {
                        "error": f"400 Bad Request - Parameters not supported: {list(clean_params.keys())}",
                        "params_used": clean_params
                    }
                    continue
                
                response.raise_for_status()
                data_result = response.json()
                
                api_results[test["name"]] = {
                    "params_used": clean_params,
                    "success": data_result.get('success', False),
                    "count": len(data_result.get('bundle', [])),
                    "sample_addresses": [
                        prop.get('address', {}).get('full', prop.get('address', 'N/A')) if isinstance(prop.get('address'), dict) else prop.get('address', 'N/A')
                        for prop in data_result.get('bundle', [])[:3]
                    ] if data_result.get('bundle') else []
                }
                
                # If we found results, also get ZPIDs
                if data_result.get('bundle'):
                    api_results[test["name"]]["zpids"] = [
                        str(prop.get('zpid', ''))
                        for prop in data_result.get('bundle', [])[:3]
                    ]
                
            except Exception as e:
                api_results[test["name"]] = {
                    "error": str(e),
                    "params_used": clean_params
                }
        
        results[api["name"]] = api_results
    
    return jsonify({
        "address": address,
        "components": components,
        "tests": results
    }), 200

# Removed old geocoding debug endpoint - using direct address search now

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
            result = {
                "address": address,
                "zpids": found_zpids,
                "found": len(found_zpids) > 0
            }
            
            # Add helpful messages for debugging
            if not result["found"]:
                components = parse_address_components(address)
                if not components.get('zip'):
                    result["message"] = "Address missing ZIP code - try adding it"
                elif not components.get('house_number'):
                    result["message"] = "Address missing house number"
                else:
                    result["message"] = "Address geocoded successfully but exact property not found in database. Try checking the address format or use the ZPID instead."
            
            address_results.append(result)
        
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