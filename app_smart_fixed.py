from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import traceback
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
app = Flask(__name__)

# Simple CORS configuration that WILL work
CORS(app, origins="*", methods=["GET", "POST", "OPTIONS"], allow_headers="*")

# Additional CORS handler to ensure headers are ALWAYS added
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-Requested-With')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'false')
    return response

# Configure Gemini with better error handling
gemini_api_key = os.getenv('VITE_GEMINI_API_KEY') or os.getenv('GEMINI_API_KEY')
gemini_configured = False

if not gemini_api_key:
    print("⚠️  Warning: GEMINI_API_KEY not found in environment variables")
    print("   Please add your Gemini API key to .env file as VITE_GEMINI_API_KEY or GEMINI_API_KEY")
else:
    try:
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        print("✅ Gemini API configured successfully")
        gemini_configured = True
    except Exception as e:
        print(f"❌ Error configuring Gemini API: {str(e)}")
        gemini_configured = False

# Global variable to store the master data
master_data = None

def load_master_json():
    """Load the master JSON file with enhanced error handling"""
    global master_data
    try:
        # Try multiple possible paths, prioritizing production path
        possible_paths = [
            '/app/courier_rates_master.json',  # For Google Cloud Run
            'courier_rates_master.json',
            os.path.join(os.path.dirname(__file__), 'courier_rates_master.json'),
            os.path.join(os.getcwd(), 'courier_rates_master.json')
        ]
        
        print(f"🔍 Checking paths for master JSON: {possible_paths}")
        for json_path in possible_paths:
            if os.path.exists(json_path):
                print(f"📁 Found master JSON at: {json_path}")
                with open(json_path, 'r', encoding='utf-8') as f:
                    master_data = json.load(f)
                print("✅ Master JSON loaded successfully!")
                print(f"📊 Loaded {len(master_data.get('carriers', {}))} carriers")
                return True
            else:
                print(f"⚠️ Path not found: {json_path}")
        
        print("❌ courier_rates_master.json not found in any expected location")
        return False
        
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing master JSON: {e}")
        return False
    except Exception as e:
        print(f"❌ Error loading master JSON: {e}")
        return False

# Initialize master data
load_master_json()

def add_cors_headers(response):
    """Add CORS headers to response"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With')
    response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
    return response

def get_relevant_data_for_country(country):
    """Extract relevant data subset for the country to send to Gemini"""
    if not master_data:
        return {}
    
    relevant_data = {
        "carriers": {},
        "zone_mappings": master_data.get("zone_mappings", {})
    }
    
    country_upper = country.upper()
    carriers = master_data.get('carriers', {})
    
    for carrier_name, carrier_data in carriers.items():
        services = carrier_data.get('services', {})
        relevant_services = {}
        
        for service_name, service_data in services.items():
            # Check if this service has data for the country (direct or zone-based)
            has_country_data = False
            service_subset = {}
            
            # Check direct country matches
            for location_key in service_data.keys():
                if country_upper in location_key.upper() or location_key.upper() in country_upper:
                    has_country_data = True
                    service_subset[location_key] = list(service_data[location_key].keys())  # Just weight tiers
            
            # Check zone-based matches
            for zone_carrier, zone_mapping in relevant_data["zone_mappings"].items():
                if zone_carrier.lower() == carrier_name.lower():
                    for mapped_country, zone in zone_mapping.items():
                        if country_upper in mapped_country or mapped_country in country_upper:
                            zone_key = f"ZONE {zone}" if not str(zone).startswith("ZONE") else str(zone)
                            if zone_key in service_data:
                                has_country_data = True
                                service_subset[zone_key] = list(service_data[zone_key].keys())
            
            if has_country_data:
                relevant_services[service_name] = service_subset
        
        if relevant_services:
            relevant_data["carriers"][carrier_name] = {"services": relevant_services}
    
    return relevant_data

def validate_weight_input(weight):
    """Validate that weight is in 0.5kg increments"""
    try:
        weight_float = float(weight)
        # Check if weight is a multiple of 0.5
        if (weight_float * 2) % 1 != 0:
            return False, "Weight must be in 0.5kg increments (0.5, 1.0, 1.5, 2.0, etc.)"
        if weight_float <= 0:
            return False, "Weight must be greater than 0"
        return True, None
    except ValueError:
        return False, "Invalid weight format"

def find_best_weight_match(weight, available_weights):
    """Find the best weight tier for the given weight using CEILING approach"""
    weight = float(weight)
    available_weights = [float(w) for w in available_weights]
    available_weights.sort()
    
    # CEILING APPROACH: Find the smallest weight tier that is >= requested weight
    for w in available_weights:
        if w >= weight:
            return str(w)
    
    # If no weight tier is >= requested weight, return None (don't serve this weight)
    return None

def expand_country_zones(country, relevant_data):
    """Expand country search to include sub-zones like Australia Metro, NZ Zone 1, etc."""
    country_upper = country.upper()
    expanded_locations = set()
    
    # Add the original country
    expanded_locations.add(country_upper)
    
    # Search for sub-zones in all carrier data
    for carrier_data in relevant_data.get('carriers', {}).values():
        for service_data in carrier_data.get('services', {}).values():
            for location_key in service_data.keys():
                location_upper = location_key.upper()
                # Check for sub-zones (e.g., AUSTRALIA METRO, NEW ZEALAND ZONE 1)
                if country_upper in location_upper or any(word in location_upper for word in country_upper.split()):
                    expanded_locations.add(location_key)
    
    return list(expanded_locations)

def ask_gemini_for_comprehensive_search(country, weight, relevant_data):
    """Use Gemini to find all possible rate options for the country"""
    
    if not gemini_configured:
        return {"error": "Gemini API not configured", "matches_found": [], "total_carriers_found": 0}
    
    prompt = f"""
You are a shipping rate analysis expert. I need you to find ALL possible shipping rates for:
DESTINATION: {country}
WEIGHT: {weight} kg

Here is the relevant shipping data (JSON format):
{json.dumps(relevant_data, indent=2)}

TASK: Analyze this data and return ALL carriers and services that can ship to {country}. 

IMPORTANT RULES:
1. Check DIRECT country matches (exact or partial country name matches)
2. Check ZONE-based matches using the zone_mappings 
3. For zone-based carriers (FedEx, DHL, UPS), find which zone {country} belongs to and look for rates in that zone
4. Include sub-zones like 'AUSTRALIA METRO', 'NEW ZEALAND ZONE 1', etc. if searching for Australia or New Zealand
5. ONLY include services that have weight tier >= {weight}kg (CEILING approach - no floor)
6. Be comprehensive - don't miss any carrier that serves this destination

Return your response as a JSON object with this exact structure:
{{
  "analysis": "Brief explanation of your search strategy",
  "matches_found": [
    {{
      "carrier": "carrier_name",
      "service": "service_name", 
      "location_key": "exact_key_found_in_data",
      "match_type": "direct_country|zone_based",
      "zone": "zone_if_applicable",
      "weight_tiers": ["0.5", "1.0", "1.5", "etc"],
      "reasoning": "why this carrier serves this destination"
    }}
  ],
  "total_carriers_found": number
}}

Be thorough and don't miss any carriers that could serve {country}!
"""

    try:
        response = model.generate_content(prompt)
        # Parse the JSON response
        response_text = response.text.strip()
        
        # Clean up the response if it has markdown formatting
        if response_text.startswith('```json'):
            response_text = response_text.replace('```json', '').replace('```', '').strip()
        
        return json.loads(response_text)
    except Exception as e:
        print(f"❌ Gemini error: {str(e)}")
        return {"error": str(e), "matches_found": [], "total_carriers_found": 0}

def get_actual_rates_from_matches(matches, weight):
    """Get actual rate values from the master data based on Gemini's matches"""
    results = []
    
    for match in matches:
        carrier = match['carrier']
        service = match['service']
        location_key = match['location_key']
        
        try:
            # Navigate to the specific service data
            service_data = master_data['carriers'][carrier]['services'][service]
            
            # For zone-based matches, construct the proper zone key
            if match['match_type'] == 'zone_based' and match.get('zone'):
                zone = match['zone']
                zone_key = f"ZONE {zone}" if not str(zone).startswith("ZONE") else str(zone)
                actual_location_key = zone_key
            else:
                actual_location_key = location_key
            
            print(f"🔍 Looking for {carrier} {service} in location: {actual_location_key}")
            
            if actual_location_key in service_data:
                weight_data = service_data[actual_location_key]
                
                available_weights = list(weight_data.keys())
                best_weight = find_best_weight_match(weight, available_weights)
                
                if best_weight and best_weight in weight_data:
                    rate_info = weight_data[best_weight]
                    
                    result = {
                        'carrier': carrier,
                        'service_type': (
    f"{service} ({actual_location_key.split(' ', 1)[-1]})" if (
        (location_key.lower() == 'australia' and actual_location_key.lower() != 'australia') or
        (location_key.lower() in ['new zealand', 'nz'] and actual_location_key.lower() not in ['new zealand', 'nz'])
    ) else service
),
                        'rate': f"₹{rate_info['rate']}",
                        'currency': rate_info.get('currency', 'INR'),
                        'zone': match.get('zone', ''),
                        'calculation': f"₹{rate_info['rate']} for {best_weight}kg tier",
                        'matched_country': (
    f"Australia ({actual_location_key.split(' ', 1)[-1]})" if location_key.lower() == 'australia' and actual_location_key.lower() != 'australia'
    else f"New Zealand ({actual_location_key.split(' ', 1)[-1]})" if location_key.lower() in ['new zealand', 'nz'] and actual_location_key.lower() not in ['new zealand', 'nz']
    else (f"{location_key} ({actual_location_key})" if actual_location_key != location_key else location_key)
),
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
                    
        except Exception as e:
            print(f"❌ Error processing match {match}: {e}")
            continue
    
    return results

@app.route('/api/get-rates', methods=['POST', 'OPTIONS'])
def get_rates():
    """API endpoint to get rates for country and weight using Gemini intelligence"""
    if request.method == 'OPTIONS':
        print("📥 Handling OPTIONS request")
        return add_cors_headers(jsonify({'status': 'ok'})), 200
    
    try:
        print(f"📥 Request received from origin: {request.headers.get('Origin')}")
        data = request.get_json()
        print(f"📥 Request data: {data}")
        
        if not data:
            return add_cors_headers(jsonify({'error': 'Invalid JSON data'})), 400
            
        country = data.get('country', '').strip()
        weight = data.get('weight', 0)
        
        if not country:
            return add_cors_headers(jsonify({'error': 'Country is required'})), 400
        
        if not weight or float(weight) <= 0:
            return add_cors_headers(jsonify({'error': 'Valid weight is required'})), 400
        
        is_valid, error_msg = validate_weight_input(weight)
        if not is_valid:
            return add_cors_headers(jsonify({'error': error_msg})), 400
        
        if not master_data:
            print("❌ Master data not loaded")
            return add_cors_headers(jsonify({
                'error': 'Master shipping data not loaded',
                'details': 'courier_rates_master.json file is missing or invalid'
            })), 500
        
        if not gemini_configured:
            print("❌ Gemini API not configured")
            return add_cors_headers(jsonify({
                'error': 'AI service not available',
                'details': 'Gemini API key not configured'
            })), 500
        
        print(f"🔍 Searching rates for {country}, {weight}kg...")
        relevant_data = get_relevant_data_for_country(country)
        expanded_locations = expand_country_zones(country, relevant_data)
        
        if not relevant_data.get('carriers'):
            print(f"⚠️ No shipping data found for {country}")
            return jsonify({
                'error': f'No shipping data found for {country}',
                'country': country,
                'weight': weight
            }), 404
        
        print(f"📊 Found relevant data for {len(relevant_data['carriers'])} carriers")
        gemini_analysis = ask_gemini_for_comprehensive_search(country, weight, relevant_data)
        
        if 'error' in gemini_analysis:
            print(f"❌ Gemini analysis error: {gemini_analysis['error']}")
            return jsonify({'error': f'Analysis error: {gemini_analysis["error"]}'}), 500
        
        print(f"🤖 Gemini found {gemini_analysis.get('total_carriers_found', 0)} potential matches")
        print(f"📋 Gemini matches: {json.dumps(gemini_analysis.get('matches_found', []), indent=2)}")
        
        rate_results = get_actual_rates_from_matches(gemini_analysis.get('matches_found', []), weight)
        
        zone_mappings = {}
        for carrier_name in ['fedex', 'dhl', 'ups']:
            zone_mapping = master_data.get('zone_mappings', {}).get(carrier_name, {})
            country_upper = country.upper()
            for mapped_country, zone in zone_mapping.items():
                if country_upper in mapped_country or mapped_country in country_upper:
                    zone_mappings[f'{carrier_name}_zone'] = zone
                    break
        
        print("=== DEBUG: rate_results ===")
        for r in rate_results:
            print(f"Carrier: {r['carrier']}, Service: {r['service_type']}, Matched: {r['matched_country']}, Rate: {r['rate']}")
        
        print(f"✅ Returning {len(rate_results)} rate results")
        response = {
            'country': country,
            'weight': weight,
            'data': {
                'zone_mappings': zone_mappings,
                'gemini_response': {
                    'results': rate_results,
                    'total_found': len(rate_results),
                    'search_country': country,
                    'search_weight': weight,
                    'analysis': gemini_analysis.get('analysis', ''),
                    'gemini_matches': gemini_analysis.get('total_carriers_found', 0)
                }
            }
        }
        return add_cors_headers(jsonify(response))
        
    except Exception as e:
        print(f"❌ Server error: {str(e)}")
        print(f"❌ Traceback: {traceback.format_exc()}")
        return add_cors_headers(jsonify({'error': f'Server error: {str(e)}'})), 500

@app.route('/api/carriers', methods=['GET'])
def get_carriers():
    """Get list of all available carriers"""
    if not master_data:
        print("❌ Master data not loaded for /api/carriers")
        return jsonify({'error': 'Master data not loaded'}), 500
    
    carriers = list(master_data.get('carriers', {}).keys())
    return jsonify({'carriers': carriers})

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    status = "healthy" if master_data and gemini_configured else "unhealthy"
    return jsonify({
        'status': status,
        'master_data_loaded': master_data is not None,
        'carriers_count': len(master_data.get('carriers', {})) if master_data else 0,
        'gemini_configured': gemini_configured,
        'gemini_api_key_present': bool(gemini_api_key)
    })

@app.route('/')
def index():
    """Serve the Majithia International Courier frontend"""
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
            .gemini-badge { 
                background: linear-gradient(45deg, #4285f4, #34a853); 
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
                <h1>🏢 Majithia International Courier</h1>
                <div class="subtitle">Professional International Shipping Rate Calculator</div>
                <div class="gemini-badge">Powered by Gemini AI</div>
            </div>
            
            <div class="form-section">
                <div class="form-group">
                    <label for="country">🌍 Destination Country:</label>
                    <input type="text" id="country" placeholder="e.g., Canada, Australia, UAE, Singapore" />
                </div>
                
                <div class="form-group">
                    <label>📦 Package Weight (kg):</label>
                    <div class="weight-control">
                        <button type="button" class="weight-btn decrease" onclick="decreaseWeight()">−</button>
                        <div class="weight-display" id="weight-display">0.5</div>
                        <button type="button" class="weight-btn increase" onclick="increaseWeight()">+</button>
                    </div>
                    <div class="weight-note">Weight increments: 0.5kg steps only (0.5, 1.0, 1.5, 2.0...)</div>
                </div>
                
                <button class="search-btn" onclick="findRates()">🔍 Find Best Shipping Rates</button>
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
                    resultsDiv.innerHTML = '<div class="error">⚠️ Please enter a destination country.</div>';
                    return;
                }
                
                resultsDiv.innerHTML = '<div class="loading">🏢 Majithia International Courier AI is finding best rates...</div>';
                
                try {
                    const response = await fetch('/api/get-rates', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ country, weight })
                    });
                    
                    const data = await response.json();
                    
                    if (data.error) {
                        resultsDiv.innerHTML = `<div class="error">❌ ${data.error}</div>`;
                        return;
                    }
                    
                    if (data.data && data.data.gemini_response && data.data.gemini_response.results.length > 0) {
                        const geminiData = data.data.gemini_response;
                        let html = `
                            <div class="results-header">
                                <h3>📦 Found ${geminiData.total_found} shipping options for ${data.country} (${data.weight}kg)</h3>
                            </div>
                        `;
                        
                        if (geminiData.analysis) {
                            html += `<div class="analysis"><strong>🤖 AI Analysis:</strong> ${geminiData.analysis}</div>`;
                        }
                        
                        geminiData.results.sort((a, b) => a.final_rate - b.final_rate);
                        
                        geminiData.results.forEach((rate, index) => {
                            const rankBadge = index === 0 ? '🥇 BEST RATE' : index === 1 ? '🥈' : index === 2 ? '🥉' : '';
                            html += `
                                <div class="rate-card">
                                    <div class="carrier-name">${rate.carrier} - ${rate.service_type} ${rankBadge}</div>
                                    <div class="rate-details">
                                        <div class="detail-item">
                                            <strong>💰 Rate:</strong> ${rate.rate}
                                        </div>
                                        <div class="detail-item">
                                            <strong>🧮 Calculation:</strong> ${rate.calculation}
                                        </div>
                                        <div class="detail-item">
                                            <strong>🎯 Match:</strong> ${rate.matched_country}
                                        </div>
                                        <div class="detail-item">
                                            <strong>⚖️ Weight Tier:</strong> ${rate.weight_tier}kg
                                        </div>
                                        <div class="detail-item">
                                            <strong>🔍 Method:</strong> ${rate.match_type.replace('_', ' ')}
                                        </div>
                                        ${rate.zone ? `<div class="detail-item"><strong>🌐 Zone:</strong> ${rate.zone}</div>` : ''}
                                        ${rate.reasoning ? `<div class="detail-item"><strong>💡 Why:</strong> ${rate.reasoning}</div>` : ''}
                                    </div>
                                </div>
                            `;
                        });
                        
                        resultsDiv.innerHTML = html;
                    } else {
                        resultsDiv.innerHTML = '<div class="no-results">🏢 No shipping options available for this destination and weight combination.</div>';
                    }
                    
                } catch (error) {
                    resultsDiv.innerHTML = `<div class="error">❌ Network error: ${error.message}</div>`;
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

if __name__ == '__main__':
    print("🏢 Starting Majithia International Courier Rate Finder...")
    print("✨ Professional shipping rate calculator with AI intelligence")
    
    if not gemini_api_key:
        print("⚠️  Warning: GEMINI_API_KEY not found in environment variables")
        print("   Please add your Gemini API key to .env file")
    
    if master_data:
        print("✅ Ready to serve professional rate requests!")
        print("🌐 Access your app at: http://localhost:5000")
        app.run(debug=True, host='0.0.0.0', port=5000)
    else:
        print("❌ Master data not loaded. Starting server anyway for debugging...")
        print("🌐 Access your app at: http://localhost:5000")
        app.run(debug=True, host='0.0.0.0', port=5000)
