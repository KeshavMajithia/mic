from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import traceback
from dotenv import load_dotenv
import logging
from functools import lru_cache
import time

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Configure CORS properly
CORS(app, 
     origins=["https://keshavmajithia.github.io", "http://localhost:3000", "http://localhost:5000", "http://localhost:8080"],
     methods=["GET", "POST", "OPTIONS"],
     allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
     supports_credentials=False)

# Alternative CORS setup using after_request (backup method)
@app.after_request
def after_request(response):
    origin = request.headers.get('Origin')
    allowed_origins = [
        'https://keshavmajithia.github.io',
        'http://localhost:3000',
        'http://localhost:5000',
        'http://localhost:8080'
    ]
    
    if origin in allowed_origins:
        response.headers['Access-Control-Allow-Origin'] = origin
    else:
        response.headers['Access-Control-Allow-Origin'] = '*'
    
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS, PUT, DELETE'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
    response.headers['Access-Control-Allow-Credentials'] = 'false'
    response.headers['Access-Control-Max-Age'] = '86400'
    return response

# Rate Finding Service (replaces Gemini)
class RateFinderService:
    def __init__(self):
        logger.info("✅ Rate finder service initialized")
    
    def analyze_shipping_rates(self, country, weight, relevant_data):
        """Comprehensive search that finds ALL matches programmatically"""
        logger.info(f"🔍 Starting comprehensive search for {country} at {weight}kg")
        
        all_matches = []
        country_upper = country.upper().strip()
        
        # Get carriers data
        carriers = relevant_data.get('carriers', {})
        zone_mappings = relevant_data.get('zone_mappings', {})
        
        # Debug: Log what we're searching for
        logger.info(f"🔎 Searching for: '{country}' (normalized: '{country_upper}')")
        logger.info(f"📊 Available carriers: {list(carriers.keys())}")
        
        # 1. DIRECT COUNTRY MATCHES - Search all carriers and services
        for carrier_name, carrier_data in carriers.items():
            services = carrier_data.get('services', {})
            logger.info(f"🔍 Checking {carrier_name} with services: {list(services.keys())}")
            
            for service_name, service_data in services.items():
                location_keys = list(service_data.keys())
                logger.info(f"  📍 {carrier_name}-{service_name} locations: {location_keys[:5]}{'...' if len(location_keys) > 5 else ''}")
                
                # Check each location key in this service
                for location_key, rate_data in service_data.items():
                    location_upper = location_key.upper()
                    
                    # More flexible matching
                    is_match = False
                    match_reason = ""
                    
                    # Exact match
                    if country_upper == location_upper:
                        is_match = True
                        match_reason = "exact"
                    # Country contains location (e.g., "USA" in "USA ZONE 1")
                    elif country_upper in location_upper:
                        is_match = True
                        match_reason = "country_in_location"
                    # Location contains country (e.g., "UNITED STATES" contains "USA")
                    elif location_upper in country_upper:
                        is_match = True
                        match_reason = "location_in_country"
                    # Special cases for common country variations
                    elif self._is_country_variation(country_upper, location_upper):
                        is_match = True
                        match_reason = "variation"
                    
                    if is_match:
                        # Check if weight is available
                        weight_valid = self._has_valid_weight(rate_data, weight)
                        all_matches.append({
                            "carrier": carrier_name,
                            "service": service_name,
                            "location_key": location_key,
                            "match_type": "direct_country",
                            "match_reason": match_reason,
                            "weight_available": weight_valid
                        })
                        logger.info(f"✅ Direct match ({match_reason}): {carrier_name} {service_name} -> {location_key} (weight_valid={weight_valid})")
        
        # 2. ZONE-BASED MATCHES - Check zone mappings for each carrier
        logger.info(f"🌍 Starting zone-based search...")
        
        for zone_carrier, zone_mapping in zone_mappings.items():
            carrier_key = next((ck for ck in carriers if ck.lower() == zone_carrier.lower()), None)
            if carrier_key:
                logger.info(f"🔍 Checking {carrier_key} ({zone_carrier}) zone mappings...")
                
                # Find zone for this country
                country_zone = None
                matched_zone_country = None
                
                for mapped_country, zone in zone_mapping.items():
                    mapped_upper = mapped_country.upper()
                    
                    # More comprehensive zone matching
                    if (country_upper == mapped_upper or
                        country_upper in mapped_upper or 
                        mapped_upper in country_upper or
                        self._is_country_variation(country_upper, mapped_upper)):
                        country_zone = zone
                        matched_zone_country = mapped_country
                        logger.info(f"🎯 Found zone mapping: {country} -> {mapped_country} -> Zone {zone}")
                        break
                
                if country_zone:
                    # Look for services with this zone
                    services = carriers[carrier_key].get('services', {})
                    for service_name, service_data in services.items():
                        
                        # Look for zone-based location keys
                        zone_matches = []
                        
                        for location_key, rate_data in service_data.items():
                            location_upper = location_key.upper()
                            zone_str = str(country_zone).upper()
                            
                            logger.info(f"🔍 Checking location: '{location_key}' (upper: '{location_upper}') for zone '{country_zone}' (str: '{zone_str}')")
                            
                            # Multiple zone matching patterns
                            zone_patterns = [
                                f"ZONE {zone_str}",  # "ZONE I", "ZONE 8"
                                f"ZONE{zone_str}",   # "ZONEI", "ZONE8"
                                f"Z{zone_str}",      # "ZI", "Z8"
                                zone_str             # "I", "8"
                            ]
                            
                            is_zone_match = False
                            match_pattern = None
                            
                            for pattern in zone_patterns:
                                logger.info(f"  🔎 Testing pattern: '{pattern}' vs '{location_upper}'")
                                if location_upper == pattern:
                                    is_zone_match = True
                                    match_pattern = pattern
                                    logger.info(f"  ✅ EXACT MATCH: '{pattern}'")
                                    break
                                elif pattern in location_upper:
                                    is_zone_match = True
                                    match_pattern = pattern
                                    logger.info(f"  ✅ CONTAINS MATCH: '{pattern}' in '{location_upper}'")
                                    break
                                else:
                                    logger.info(f"  ❌ No match: '{pattern}'")
                            
                            logger.info(f"🎯 Zone matching result: '{location_key}' -> {is_zone_match} (pattern: {match_pattern})")
                            
                            if is_zone_match:
                                weight_valid = self._has_valid_weight(rate_data, weight)
                                logger.info(f"⚖️ Weight validation for {location_key}: {weight_valid}")
                                
                                zone_matches.append({
                                    "carrier": carrier_key,
                                    "service": service_name,
                                    "location_key": location_key,
                                    "match_type": "zone_based",
                                    "zone": country_zone,
                                    "zone_country": matched_zone_country,
                                    "weight_available": weight_valid
                                })
                                logger.info(f"✅ Added zone match: {carrier_key} {service_name} -> {location_key} (weight_valid={weight_valid})")
                        
                        # Add all zone matches for this service
                        for match in zone_matches:
                            # Avoid duplicates
                            match_exists = any(
                                m['carrier'] == carrier_key and 
                                m['service'] == service_name and 
                                m['location_key'] == location_key 
                                for m in all_matches
                            )
                            
                            if not match_exists:
                                all_matches.append(match)
                                logger.info(f"✅ Zone match: {carrier_key} {service_name} -> {match['location_key']} (Zone {country_zone} via {matched_zone_country})")
                            else:
                                logger.info(f"⚠️ Duplicate match skipped: {carrier_key} {service_name} -> {location_key}")
                else:
                    logger.info(f"⚠️ No zone mapping found for {country} in {carrier_key}")
        
        logger.info(f"🎯 Found {len(all_matches)} total matches for {country}")
        
        return {
            "analysis": f"Smart search found {len(all_matches)} shipping options for {country} at {weight}kg",
            "matches_found": all_matches,
            "total_carriers_found": len(set(match['carrier'] for match in all_matches))
        }
    
    def _has_valid_weight(self, rate_data, target_weight):
        """Check if rate data has valid weight tier for target weight"""
        logger.debug(f"Checking rate_data: {rate_data}")
        if not isinstance(rate_data, dict):
            logger.debug(f"Rate data is not dict: {type(rate_data)}, data: {rate_data}")
            return False
        
        # Look for weight keys (numbers)
        weight_keys = []
        for key in rate_data.keys():
            try:
                weight_val = float(key)
                weight_keys.append(weight_val)
            except (ValueError, TypeError):
                logger.debug(f"Invalid weight key: {key} (type: {type(key)})")
                continue
        
        logger.debug(f"Available weights for target {target_weight}kg: {sorted(weight_keys)}")
        
        if not weight_keys:
            logger.debug("No valid weight keys found in rate data")
            return False
        
        # Use ceiling approach - find smallest weight >= target_weight
        target_float = float(target_weight)
        valid_weights = [w for w in weight_keys if w >= target_float]
        
        logger.debug(f"Valid weights (>= {target_float}kg): {valid_weights}")
        return len(valid_weights) > 0
    
    def _is_country_variation(self, country_upper, location_upper):
        """Check for common country name variations"""
        variations = {
            'USA': ['UNITED STATES', 'AMERICA', 'US'],
            'UK': ['UNITED KINGDOM', 'BRITAIN', 'ENGLAND'],
            'UAE': ['UNITED ARAB EMIRATES'],
            'CYPRUS': ['EUROPE'],  # Cyprus might be under Europe
            'RUSSIA': ['RUSSIAN FEDERATION'],
            'SOUTH KOREA': ['KOREA'],
            'NORTH KOREA': ['KOREA']
        }
        
        # Check if country has known variations
        if country_upper in variations:
            for variation in variations[country_upper]:
                if variation in location_upper or location_upper in variation:
                    return True
        
        # Check reverse mapping
        for main_country, var_list in variations.items():
            if country_upper in var_list:
                if main_country in location_upper or location_upper in main_country:
                    return True
        
        return False

# Initialize rate finder service
rate_finder_service = RateFinderService()

# Data management
class DataManager:
    def __init__(self):
        self.master_data = None
        self.load_master_json()
    
    def load_master_json(self):
        """Load master JSON with improved error handling"""
        try:
            possible_paths = [
                '/app/courier_rates_master.json',  # Google Cloud Run
                'courier_rates_master.json',
                os.path.join(os.path.dirname(__file__), 'courier_rates_master.json'),
                os.path.join(os.getcwd(), 'courier_rates_master.json')
            ]
            
            logger.info(f"🔍 Checking paths: {possible_paths}")
            
            for json_path in possible_paths:
                if os.path.exists(json_path):
                    logger.info(f"📁 Found master JSON at: {json_path}")
                    with open(json_path, 'r', encoding='utf-8') as f:
                        self.master_data = json.load(f)
                    logger.info(f"✅ Loaded {len(self.master_data.get('carriers', {}))} carriers")
                    return True
            
            logger.error("❌ courier_rates_master.json not found")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error loading master JSON: {e}")
            return False
    
    @lru_cache(maxsize=128)
    def get_relevant_data_for_country(self, country):
        """Cached method to get relevant data for country"""
        if not self.master_data:
            return {}
        
        relevant_data = {
            "carriers": {},
            "zone_mappings": self.master_data.get("zone_mappings", {})
        }
        
        country_upper = country.upper()
        carriers = self.master_data.get('carriers', {})
        
        for carrier_name, carrier_data in carriers.items():
            services = carrier_data.get('services', {})
            relevant_services = {}
            
            for service_name, service_data in services.items():
                has_country_data = False
                service_subset = {}
                
                # Check direct country matches
                for location_key in service_data.keys():
                    if country_upper in location_key.upper() or location_key.upper() in country_upper:
                        has_country_data = True
                        service_subset[location_key] = list(service_data[location_key].keys())
                
                # Check zone-based matches
                for zone_carrier, zone_mapping in relevant_data["zone_mappings"].items():
                    if zone_carrier.lower() == carrier_name.lower():
                        for mapped_country, zone in zone_mapping.items():
                            if country_upper in mapped_country.upper() or mapped_country.upper() in country_upper:
                                zone_key = f"ZONE {zone}" if not str(zone).startswith("ZONE") else str(zone)
                                if zone_key in service_data:
                                    has_country_data = True
                                    service_subset[zone_key] = list(service_data[zone_key].keys())
                
                if has_country_data:
                    relevant_services[service_name] = service_subset
            
            if relevant_services:
                relevant_data["carriers"][carrier_name] = {"services": relevant_services}
        
        return relevant_data

# Initialize data manager
data_manager = DataManager()

# Utility functions
class RateCalculator:
    @staticmethod
    def validate_weight_input(weight):
        """Validate weight input"""
        try:
            weight_float = float(weight)
            if (weight_float * 2) % 1 != 0:
                return False, "Weight must be in 0.5kg increments (0.5, 1.0, 1.5, 2.0, etc.)"
            if weight_float <= 0:
                return False, "Weight must be greater than 0"
            return True, None
        except ValueError:
            return False, "Invalid weight format"
    
    @staticmethod
    def find_best_weight_match(weight, available_weights):
        """Find best weight tier using ceiling approach"""
        weight = float(weight)
        available_weights = [float(w) for w in available_weights]
        available_weights.sort()
        
        for w in available_weights:
            if w >= weight:
                return str(w)
        return None
    
    @staticmethod
    def get_actual_rates_from_matches(matches, weight, master_data):
        """Process matches to get actual rates"""
        results = []
        
        for match in matches:
            if not match.get('weight_available', False):
                continue
            
            try:
                carrier = match['carrier']
                service = match['service']
                location_key = match['location_key']
                
                service_data = master_data['carriers'][carrier]['services'][service]
                
                if match['match_type'] == 'zone_based' and match.get('zone'):
                    zone = match['zone']
                    actual_location_key = f"ZONE {zone}" if not str(zone).startswith("ZONE") else str(zone)
                    actual_location_key = actual_location_key.upper()  # Normalize to match JSON
                else:
                    actual_location_key = location_key  # Use original case first
                
                # Try original location_key first, then uppercase
                weight_data = None
                if actual_location_key in service_data:
                    weight_data = service_data[actual_location_key]
                elif actual_location_key.upper() in service_data:
                    weight_data = service_data[actual_location_key.upper()]
                elif actual_location_key.lower() in service_data:
                    weight_data = service_data[actual_location_key.lower()]
                else:
                    logger.error(f"Location key {actual_location_key} not found in service_data: {list(service_data.keys())}")
                    continue
                
                available_weights = list(weight_data.keys())
                best_weight = RateCalculator.find_best_weight_match(weight, available_weights)
                
                if best_weight and best_weight in weight_data:
                    rate_info = weight_data[best_weight]
                    
                    # Create result object
                    result = {
                        'carrier': carrier,
                        'service_type': RateCalculator._format_service_name(service, location_key, actual_location_key),
                        'rate': f"₹{rate_info['rate']}",
                        'currency': rate_info.get('currency', 'INR'),
                        'zone': match.get('zone', ''),
                        'calculation': f"₹{rate_info['rate']} for {best_weight}kg tier",
                        'matched_country': RateCalculator._format_matched_country(location_key, actual_location_key),
                        'weight_tier': best_weight,
                        'match_type': match['match_type'],
                        'reasoning': match.get('reasoning', ''),
                        'final_rate': rate_info['rate']
                    }
                    
                    # Handle per-kg rates
                    if rate_info.get('is_per_kg', False):
                        final_rate = rate_info['rate'] * float(weight)
                        result['final_rate'] = final_rate
                        result['rate'] = f"₹{final_rate}"
                        result['calculation'] = f"₹{rate_info['rate']}/kg × {weight}kg = ₹{final_rate}"
                    
                    results.append(result)
                else:
                    logger.error(f"No valid weight tier found for {carrier} {service} {actual_location_key}. Available weights: {available_weights}")
                    # Skip invalid
                
            except Exception as e:
                logger.error(f"❌ Error processing match {match}: {e}")
                # Skip
        
        return results
    
    @staticmethod
    def _format_service_name(service, location_key, actual_location_key):
        """Format service name with location info"""
        if ((location_key.lower() == 'australia' and actual_location_key.lower() != 'australia') or
            (location_key.lower() in ['new zealand', 'nz'] and actual_location_key.lower() not in ['new zealand', 'nz'])):
            return f"{service} ({actual_location_key.split(' ', 1)[-1]})"
        return service
    
    @staticmethod
    def _format_matched_country(location_key, actual_location_key):
        """Format matched country display"""
        if location_key.lower() == 'australia' and actual_location_key.lower() != 'australia':
            return f"Australia ({actual_location_key.split(' ', 1)[-1]})"
        elif location_key.lower() in ['new zealand', 'nz'] and actual_location_key.lower() not in ['new zealand', 'nz']:
            return f"New Zealand ({actual_location_key.split(' ', 1)[-1]})"
        elif actual_location_key != location_key:
            return f"{location_key} ({actual_location_key})"
        return location_key

# API Routes
@app.route('/api/get-rates', methods=['POST', 'OPTIONS'])
def get_rates():
    """Main API endpoint for getting shipping rates"""
    
    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        logger.info("📥 Handling OPTIONS preflight request")
        response = jsonify({'status': 'ok'})
        return response, 200
    
    try:
        logger.info(f"📥 POST request from origin: {request.headers.get('Origin')}")
        
        # Get and validate request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON data'}), 400
        
        country = data.get('country', '').strip()
        weight = data.get('weight', 0)
        
        if not country:
            return jsonify({'error': 'Country is required'}), 400
        
        if not weight or float(weight) <= 0:
            return jsonify({'error': 'Valid weight is required'}), 400
        
        # Validate weight format
        is_valid, error_msg = RateCalculator.validate_weight_input(weight)
        if not is_valid:
            return jsonify({'error': error_msg}), 400
        
        # Check if master data is loaded
        if not data_manager.master_data:
            logger.error("❌ Master data not loaded")
            return jsonify({
                'error': 'Master shipping data not loaded',
                'details': 'courier_rates_master.json file is missing or invalid'
            }), 500
        
        logger.info(f"🔍 Processing request: {country}, {weight}kg")
        
        # Get relevant data and analyze
        relevant_data = data_manager.get_relevant_data_for_country(country)
        
        if not relevant_data.get('carriers'):
            logger.warning(f"⚠️ No shipping data found for {country}")
            return jsonify({
                'error': f'No shipping data found for {country}',
                'country': country,
                'weight': weight
            }), 404
        
        logger.info(f"📊 Found relevant data for {len(relevant_data['carriers'])} carriers")
        
        # Use smart rate finder for analysis (no Gemini)
        analysis_result = rate_finder_service.analyze_shipping_rates(country, weight, relevant_data)
        
        logger.info(f"🤖 Smart finder found {analysis_result.get('total_carriers_found', 0)} matches")
        
        # Get actual rates from matches
        rate_results = RateCalculator.get_actual_rates_from_matches(
            analysis_result.get('matches_found', []), 
            weight, 
            data_manager.master_data
        )
        
        # Prepare zone mappings for response with case-insensitive matching
        zone_mappings = {}
        for carrier_name in ['fedex', 'dhl', 'ups']:
            zone_mapping = data_manager.master_data.get('zone_mappings', {}).get(carrier_name, {})
            country_upper = country.upper()
            for mapped_country, zone in zone_mapping.items():
                if country_upper in mapped_country.upper() or mapped_country.upper() in country_upper:
                    zone_mappings[f'{carrier_name}_zone'] = zone
                    break
        
        logger.info(f"✅ Returning {len(rate_results)} rate results")
        
        # Prepare response
        response_data = {
            'country': country,
            'weight': weight,
            'data': {
                'zone_mappings': zone_mappings,
                'smart_response': {
                    'results': rate_results,
                    'total_found': len(rate_results),
                    'search_country': country,
                    'search_weight': weight,
                    'analysis': analysis_result.get('analysis', ''),
                    'matches_found': analysis_result.get('total_carriers_found', 0)
                }
            }
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"❌ Server error: {str(e)}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/carriers', methods=['GET'])
def get_carriers():
    """Get list of available carriers"""
    if not data_manager.master_data:
        return jsonify({'error': 'Master data not loaded'}), 500
    
    carriers = list(data_manager.master_data.get('carriers', {}).keys())
    return jsonify({'carriers': carriers}), 200

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    status = "healthy" if data_manager.master_data else "unhealthy"
    return jsonify({
        'status': status,
        'master_data_loaded': data_manager.master_data is not None,
        'carriers_count': len(data_manager.master_data.get('carriers', {})) if data_manager.master_data else 0,
        'timestamp': time.time()
    }), 200

@app.route('/')
def index():
    """Serve the frontend"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Majithia International Courier - Professional Rate Finder</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * { box-sizing: border-box; }
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                margin: 0; 
                padding: 20px; 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
            }
            .container { 
                max-width: 1200px; 
                margin: 0 auto; 
                background: white; 
                padding: 40px; 
                border-radius: 15px; 
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            }
            .header {
                text-align: center;
                margin-bottom: 40px;
                border-bottom: 3px solid #007bff;
                padding-bottom: 20px;
            }
            h1 { 
                color: #2c3e50; 
                margin: 0; 
                font-size: 2.5em;
                font-weight: 700;
            }
            .subtitle {
                color: #7f8c8d;
                font-size: 1.2em;
                margin: 10px 0;
            }
            .smart-badge { 
                background: linear-gradient(45deg, #28a745, #20c997); 
                color: white; 
                padding: 8px 16px; 
                border-radius: 20px; 
                font-size: 14px;
                font-weight: 600;
                display: inline-block;
                margin-top: 10px;
            }
            .form-section {
                background: #f8f9fa;
                padding: 30px;
                border-radius: 10px;
                margin-bottom: 30px;
                border: 2px solid #e9ecef;
            }
            .form-group { 
                margin-bottom: 25px; 
            }
            label { 
                display: block; 
                margin-bottom: 8px; 
                font-weight: 600; 
                color: #495057; 
                font-size: 16px;
            }
            input[type="text"] { 
                width: 100%; 
                padding: 15px; 
                border: 2px solid #dee2e6; 
                border-radius: 8px; 
                font-size: 16px;
                transition: border-color 0.3s;
            }
            input[type="text"]:focus {
                outline: none;
                border-color: #007bff;
                box-shadow: 0 0 0 3px rgba(0,123,255,0.25);
            }
            .weight-control {
                display: flex;
                align-items: center;
                gap: 15px;
                justify-content: center;
                background: white;
                padding: 15px;
                border-radius: 10px;
                border: 2px solid #dee2e6;
            }
            .weight-btn {
                width: 50px;
                height: 50px;
                font-size: 24px;
                font-weight: bold;
                border: none;
                border-radius: 50%;
                cursor: pointer;
                transition: all 0.3s;
                color: white;
            }
            .weight-btn.decrease {
                background: linear-gradient(45deg, #dc3545, #c82333);
            }
            .weight-btn.increase {
                background: linear-gradient(45deg, #28a745, #218838);
            }
            .weight-btn:hover {
                transform: scale(1.1);
                box-shadow: 0 5px 15px rgba(0,0,0,0.3);
            }
            .weight-display {
                font-size: 28px;
                font-weight: bold;
                color: #007bff;
                min-width: 80px;
                text-align: center;
                background: #f8f9fa;
                padding: 10px 20px;
                border-radius: 8px;
                border: 2px solid #007bff;
            }
            .weight-note {
                color: #6c757d;
                font-size: 14px;
                text-align: center;
                margin-top: 10px;
                font-style: italic;
            }
            .search-btn { 
                background: linear-gradient(45deg, #007bff, #0056b3); 
                color: white; 
                padding: 18px 50px; 
                border: none; 
                border-radius: 10px; 
                cursor: pointer; 
                font-size: 18px;
                font-weight: 600;
                width: 100%;
                transition: all 0.3s;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            .search-btn:hover { 
                background: linear-gradient(45deg, #0056b3, #004085);
                transform: translateY(-2px);
                box-shadow: 0 10px 25px rgba(0,123,255,0.4);
            }
            .results { margin-top: 40px; }
            .analysis { 
                background: linear-gradient(135deg, #e3f2fd, #bbdefb); 
                border: 2px solid #2196f3; 
                border-radius: 10px; 
                padding: 20px; 
                margin-bottom: 25px;
                font-size: 16px;
            }
            .rate-card { 
                background: white; 
                border: 2px solid #e9ecef; 
                border-radius: 12px; 
                padding: 25px; 
                margin-bottom: 20px;
                transition: all 0.3s;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            .rate-card:hover {
                transform: translateY(-5px);
                box-shadow: 0 10px 30px rgba(0,0,0,0.15);
                border-color: #007bff;
            }
            .carrier-name { 
                font-size: 22px; 
                font-weight: bold; 
                color: #007bff; 
                margin-bottom: 15px;
                border-bottom: 2px solid #e9ecef;
                padding-bottom: 10px;
            }
            .rate-details { 
                display: grid; 
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
                gap: 15px; 
            }
            .detail-item { 
                background: #f8f9fa; 
                padding: 15px; 
                border-radius: 8px; 
                border-left: 4px solid #007bff;
                font-size: 14px;
            }
            .detail-item strong {
                color: #495057;
                display: block;
                margin-bottom: 5px;
            }
            .error { 
                color: #dc3545; 
                background: #f8d7da; 
                padding: 20px; 
                border-radius: 8px; 
                margin-top: 20px;
                border: 2px solid #dc3545;
                font-weight: 600;
            }
            .loading { 
                text-align: center; 
                color: #007bff; 
                margin-top: 30px;
                font-size: 18px;
                font-weight: 600;
            }
            .no-results { 
                text-align: center; 
                color: #6c757d; 
                background: #e9ecef; 
                padding: 30px; 
                border-radius: 10px; 
                margin-top: 30px;
                font-size: 18px;
            }
            .results-header {
                background: linear-gradient(135deg, #28a745, #20c997);
                color: white;
                padding: 20px;
                border-radius: 10px;
                margin-bottom: 25px;
                text-align: center;
            }
            .results-header h3 {
                margin: 0;
                font-size: 24px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Majithia International Courier</h1>
                <div class="subtitle">Professional International Shipping Rate Calculator</div>
                <div class="smart-badge">Smart Rate Finder</div>
            </div>
            
            <div class="form-section">
                <div class="form-group">
                    <label for="country">Destination Country:</label>
                    <input type="text" id="country" placeholder="e.g., Canada, Australia, UAE, Singapore" />
                </div>
                
                <div class="form-group">
                    <label>Package Weight (kg):</label>
                    <div class="weight-control">
                        <button type="button" class="weight-btn decrease" onclick="decreaseWeight()">−</button>
                        <div class="weight-display" id="weight-display">0.5</div>
                        <button type="button" class="weight-btn increase" onclick="increaseWeight()">+</button>
                    </div>
                    <div class="weight-note">Weight increments: 0.5kg steps only (0.5, 1.0, 1.5, 2.0...)</div>
                </div>
                
                <button class="search-btn" onclick="findRates()">Find Best Shipping Rates</button>
            </div>
            
            <div id="results" class="results"></div>
        </div>

        <script>
            let currentWeight = 0.5;
            
            function updateWeightDisplay() {
                document.getElementById('weight-display').textContent = currentWeight.toFixed(1);
            }
            
            function increaseWeight() {
                currentWeight += 0.5;
                updateWeightDisplay();
            }
            
            function decreaseWeight() {
                if (currentWeight > 0.5) {
                    currentWeight -= 0.5;
                    updateWeightDisplay();
                }
            }
            
            async function findRates() {
                const country = document.getElementById('country').value.trim();
                const weight = currentWeight;
                const resultsDiv = document.getElementById('results');
                
                if (!country) {
                    resultsDiv.innerHTML = '<div class="error">Please enter a destination country.</div>';
                    return;
                }
                
                resultsDiv.innerHTML = '<div class="loading">Smart rate finder is searching for best rates...</div>';
                
                try {
                    const response = await fetch('/api/get-rates', {
                        method: 'POST',
                        headers: { 
                            'Content-Type': 'application/json',
                            'Accept': 'application/json'
                        },
                        body: JSON.stringify({ country, weight })
                    });
                    
                    const data = await response.json();
                    
                    if (data.error) {
                        resultsDiv.innerHTML = `<div class="error">${data.error}</div>`;
                        return;
                    }
                    
                    if (data.data && data.data.smart_response && data.data.smart_response.results.length > 0) {
                        const smartData = data.data.smart_response;
                        let html = `
                            <div class="results-header">
                                <h3>Found ${smartData.total_found} shipping options for ${data.country} (${data.weight}kg)</h3>
                            </div>
                        `;
                        
                        if (smartData.analysis) {
                            html += `<div class="analysis"><strong>Smart Analysis:</strong> ${smartData.analysis}</div>`;
                        }
                        
                        smartData.results.sort((a, b) => a.final_rate - b.final_rate);
                        
                        smartData.results.forEach((rate, index) => {
                            if (rate.rate === 'N/A') return; // Skip invalid rates
                            const rankBadge = index === 0 ? 'BEST RATE' : index === 1 ? '2nd Best' : index === 2 ? '3rd Best' : '';
                            html += `
                                <div class="rate-card">
                                    <div class="carrier-name">${rate.carrier} - ${rate.service_type} ${rankBadge}</div>
                                    <div class="rate-details">
                                        <div class="detail-item">
                                            <strong>Rate:</strong> ${rate.rate}
                                        </div>
                                        <div class="detail-item">
                                            <strong>Calculation:</strong> ${rate.calculation}
                                        </div>
                                        <div class="detail-item">
                                            <strong>Match:</strong> ${rate.matched_country}
                                        </div>
                                        <div class="detail-item">
                                            <strong>Weight Tier:</strong> ${rate.weight_tier}kg
                                        </div>
                                        <div class="detail-item">
                                            <strong>Method:</strong> ${rate.match_type.replace('_', ' ')}
                                        </div>
                                        ${rate.zone ? `<div class="detail-item"><strong>Zone:</strong> ${rate.zone}</div>` : ''}
                                        ${rate.reasoning ? `<div class="detail-item"><strong>Details:</strong> ${rate.reasoning}</div>` : ''}
                                    </div>
                                </div>
                            `;
                        });
                        
                        resultsDiv.innerHTML = html;
                    } else {
                        resultsDiv.innerHTML = '<div class="no-results">No shipping options available for this destination and weight combination.</div>';
                    }
                    
                } catch (error) {
                    console.error('Network error:', error);
                    resultsDiv.innerHTML = `<div class="error">Network error: ${error.message}</div>`;
                }
            }
            
            document.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    findRates();
                }
            });
            
            updateWeightDisplay();
        </script>
    </body>
    </html>
    '''

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    print("Starting Majithia International Courier Rate Finder...")
    print("Smart shipping rate calculator with intelligent matching")
    
    if data_manager.master_data:
        print("Ready to serve professional rate requests!")
        print("Access your app at: http://localhost:5000")
    else:
        print("Master data not loaded. Starting server anyway for debugging...")
        print("Access your app at: http://localhost:5000")
    
    # Use different configurations for development vs production
    debug_mode = os.getenv('FLASK_ENV') == 'development'
    port = int(os.getenv('PORT', 5000))
    
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
