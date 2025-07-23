import json
import os
import glob
import pandas as pd
import re

def parse_csv_file(csv_file_path):
    """Parse individual CSV file and extract structured data"""
    
    try:
        # Get carrier name from filename
        filename = os.path.basename(csv_file_path)
        carrier_name = filename.split(' csv')[0].strip()
        
        # Clean up carrier name
        if 'aramax' in carrier_name.lower():
            carrier_name = 'Aramax'
        elif 'purolator' in carrier_name.lower():
            carrier_name = 'Purolator'
        elif 'ups' in carrier_name.lower():
            carrier_name = 'UPS'
        elif 'dhl' in carrier_name.lower():
            carrier_name = 'DHL'
        elif 'fedex' in carrier_name.lower():
            carrier_name = 'FedEx'
        elif 'dpex' in carrier_name.lower():
            carrier_name = 'DPEX'
        elif 'dpd' in carrier_name.lower():
            if 'fast' in carrier_name.lower():
                carrier_name = 'DPD Fast'
            elif 'std' in carrier_name.lower():
                carrier_name = 'DPD Standard'
            else:
                carrier_name = 'DPD'
        elif 'skynet' in carrier_name.lower():
            if 'aus nz' in carrier_name.lower():
                carrier_name = 'Skynet Australia/NZ'
            elif 'europe' in carrier_name.lower():
                carrier_name = 'Skynet Europe'
            elif 'all' in carrier_name.lower():
                carrier_name = 'Skynet All'
            else:
                carrier_name = 'Skynet'
        elif 'skysaver' in carrier_name.lower():
            carrier_name = 'SkySaver'
        else:
            carrier_name = carrier_name.title()
        
        print(f"Processing {carrier_name} from {filename}")
        
        # Read the CSV file
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
        
        if len(lines) < 2:
            print(f"  ⚠️  Skipping {filename} - insufficient data")
            return None
        
        # Parse header row (usually line 2, line 1 is carrier name)
        header_line = lines[1].strip()
        headers = [h.strip() for h in header_line.split(',')]
        
        # Initialize carrier data structure
        carrier_data = {
            'name': carrier_name,
            'services': {},
            'countries': set(),
            'weight_tiers': set()
        }
        
        # Determine service type from filename or content
        service_type = 'Standard'
        if 'doc' in filename.lower() and 'non' not in filename.lower():
            service_type = 'Document'
        elif 'non doc' in filename.lower():
            service_type = 'Non-Document'
        elif 'fast' in filename.lower():
            service_type = 'Fast'
        elif 'express' in filename.lower():
            service_type = 'Express'
        
        # Initialize service
        carrier_data['services'][service_type] = {}
        
        # Process each country column (skip first column which is weight)
        for col_idx, header in enumerate(headers[1:], 1):
            if not header or header.lower() in ['', 'weight', 'weight (kg)', 'weight_kg']:
                continue
            
            country_name = header.upper().strip()
            
            # Handle multiple countries in one column (e.g., "BAHRAIN/OMAN/KUWAIT")
            if '/' in country_name:
                main_country = country_name.split('/')[0].strip()
                country_name = main_country
            
            # Clean country name
            country_name = country_name.replace('*', '').replace('(', '').replace(')', '')
            
            if country_name:
                carrier_data['countries'].add(country_name)
                carrier_data['services'][service_type][country_name] = {}
        
        # Process data rows (skip header rows)
        for line_idx, line in enumerate(lines[2:], 2):
            if not line.strip():
                continue
            
            parts = [p.strip() for p in line.split(',')]
            
            if len(parts) < 2:
                continue
            
            # Get weight from first column
            weight_str = parts[0]
            if not weight_str or weight_str.lower() in ['weight', 'weight (kg)', 'weight_kg']:
                continue
            
            # Parse weight
            weight_value = None
            is_per_kg = False
            weight_range = None
            
            try:
                if '/kg' in weight_str.lower():
                    # Per kg rate
                    is_per_kg = True
                    weight_match = re.search(r'(\d+(?:\.\d+)?)', weight_str)
                    if weight_match:
                        weight_value = float(weight_match.group(1))
                elif '-' in weight_str and weight_str.count('-') == 1:
                    # Weight range like "6-10"
                    range_parts = weight_str.split('-')
                    if len(range_parts) == 2:
                        start_weight = float(range_parts[0])
                        end_weight = float(range_parts[1])
                        weight_range = (start_weight, end_weight)
                        weight_value = start_weight  # Use start weight as key
                elif weight_str.replace('.', '').isdigit():
                    weight_value = float(weight_str)
                else:
                    # Try to extract number from string like "Dox 500 Gm"
                    weight_match = re.search(r'(\d+(?:\.\d+)?)', weight_str)
                    if weight_match:
                        weight_value = float(weight_match.group(1))
                        if 'gm' in weight_str.lower() or 'gram' in weight_str.lower():
                            weight_value = weight_value / 1000  # Convert grams to kg
            except:
                continue
            
            if weight_value is None:
                continue
            
            carrier_data['weight_tiers'].add(weight_value)
            
            # Process rates for each country
            for col_idx, header in enumerate(headers[1:], 1):
                if col_idx >= len(parts):
                    break
                
                if not header:
                    continue
                
                country_name = header.upper().strip()
                if '/' in country_name:
                    country_name = country_name.split('/')[0].strip()
                
                country_name = country_name.replace('*', '').replace('(', '').replace(')', '')
                
                if not country_name:
                    continue
                
                rate_str = parts[col_idx]
                if not rate_str or rate_str in ['0', '-', '']:
                    continue
                
                try:
                    # Clean and parse rate
                    rate_clean = rate_str.replace(',', '').replace('/kg', '').strip()
                    rate_value = float(rate_clean)
                    
                    if rate_value > 0:
                        rate_info = {
                            'rate': rate_value,
                            'currency': 'INR',
                            'is_per_kg': is_per_kg,
                            'weight_range': weight_range
                        }
                        
                        if country_name in carrier_data['services'][service_type]:
                            carrier_data['services'][service_type][country_name][weight_value] = rate_info
                
                except:
                    continue
        
        # Convert sets to lists for JSON serialization
        carrier_data['countries'] = sorted(list(carrier_data['countries']))
        carrier_data['weight_tiers'] = sorted(list(carrier_data['weight_tiers']))
        
        print(f"  ✅ Processed {len(carrier_data['countries'])} countries, {len(carrier_data['weight_tiers'])} weight tiers")
        return carrier_data
    
    except Exception as e:
        print(f"  ❌ Error processing {csv_file_path}: {e}")
        return None

def create_master_json():
    """Create master JSON from all CSV files"""
    
    # Get all CSV files from price directory
    price_dir = os.path.join(os.getcwd(), 'price')
    csv_files = glob.glob(os.path.join(price_dir, '*.csv'))
    
    print(f"Found {len(csv_files)} CSV files in {price_dir}")
    
    # Master data structure
    master_data = {
        'carriers': {},
        'zone_mappings': {
            'FedEx': {
                'U.A.E.': 'A', 'BANGLADESH': 'B', 'BRUTAN': 'B', 'MALDIVES': 'B', 'NEPAL': 'B', 'PAKISTAN': 'B', 
                'SINGAPORE': 'B', 'SRI LANKA': 'B', 'AFGHANISTAN': 'C', 'IRAQ REPUBLIC': 'C', 'JORDAN': 'C', 
                'LEBANON': 'C', 'MYAMMAR': 'C', 'PALESTINE': 'C', 'SAUDI ARABIA': 'C', 'SYRIA': 'C', 
                'TURKMENISTAN': 'C', 'YEMEN': 'C', 'EGYPT': 'C', 'IRAN': 'C', 'CHINA': 'D', 'THAILAND': 'D', 
                'HONG KONG': 'D', 'AMERICAN SAMOA': 'E', 'AUSTRALIA': 'E', 'BRUNEI': 'E', 'CAMBODIA': 'E', 
                'COOK ISLANDS': 'E', 'LAOS': 'E', 'MACAU': 'E', 'MALAYSIA': 'E', 'MARSHALL ISLANDS': 'E', 
                'MICRONESIA': 'E', 'MONGOLIA': 'E', 'NEW CALEDONIA': 'E', 'NEW ZEALAND': 'E', 'PALAU': 'E', 
                'PAPUA NEW': 'E', 'PHILIPPINES': 'E', 'SAPAN': 'E', 'SAMOA': 'E', 'SOLOMON ISLANDS': 'E', 
                'SOUTH KOREA': 'E', 'TAWAN': 'E', 'TONGA': 'E', 'TUVALU': 'E', 'VANUATU': 'E', 'VIETNAM': 'E', 
                'EAST TIMOR': 'E', 'FIJI': 'E', 'FRENCH': 'E', 'GUAM': 'E', 'INDONESIA': 'E', 'BELGIUM': 'F', 
                'ITALY': 'F', 'LIECHTENSTEIN': 'F', 'LUXEMBOURG': 'F', 'NETHERLANDS': 'F', 'SPAIN': 'F', 
                'SWITZERLAND': 'F', 'UNITED': 'F', 'DENMARK': 'F', 'FAROE ISLANDS': 'F', 'FRANCE': 'F', 
                'GERMANY': 'F', 'GREENLAND': 'F', 'MEXICO': 'G', 'REST OF': 'G', 'U.S.A.': 'G', 'JAPAN': 'H', 
                'ALBANIA': 'I', 'ANDORRA': 'I', 'ARMENIA': 'I', 'AUSTRIA': 'I', 'AZERBAIJAN': 'I', 'BELARUS': 'I', 
                'BOSNIA': 'I', 'BULGARIA': 'I', 'IRELAND': 'I', 'ISRAEL': 'I', 'KAZAKHSTAN': 'I', 'KIRIBATI': 'I', 
                'KYRCYZSTAN': 'I', 'LATVIA': 'I', 'LITHUANIA': 'I', 'MACEDONIA': 'I', 'MALTA': 'I', 'MOLDOVA': 'I', 
                'MONACO': 'I', 'MONTENEGRO': 'I', 'NORWAY': 'I', 'POLAND': 'I', 'PORTUGAL': 'I', 'ROMANIA': 'I', 
                'RUSSIA': 'I', 'SERBIA': 'I', 'SLOVAK': 'I', 'SLOVENIA': 'I', 'SWEDEN': 'I', 'TURKEY': 'I', 
                'UKRAINE': 'I', 'UZBEKISTAN': 'I', 'GROATIA': 'I', 'CYPRUS': 'I', 'CZECH REPUBLIC': 'I', 
                'ESTONIA': 'I', 'FINLAND': 'I', 'GEORGIA': 'I', 'GIBRALTAR': 'I', 'GREECE': 'I', 'HUNGARY': 'I', 
                'ICELAND': 'I', 'ANGUILLA': 'J', 'ANTIGUA': 'J', 'ARGENTINA': 'J', 'ARUBA': 'J', 'BAHAMAS': 'J', 
                'BARBADOS': 'J', 'BELIZE': 'J', 'BERMUDA': 'J', 'BOLIVIA': 'J', 'BONAIRE': 'J', 'BRAZIL': 'J', 
                'BRITISH VIRGIN': 'J', 'CAYMAN': 'J', 'CHILE': 'J', 'COLOMBIA': 'J', 'JAMAICA': 'J', 
                'MARTINIQUE': 'J', 'MONTSEBRAT': 'J', 'NICARAGUA': 'J', 'PANAMA': 'J', 'PARAGUAY': 'J', 
                'ST KITTS & NEWS': 'J', 'ST MARRTEN': 'J', 'ST MARTIN': 'J', 'ST. LUCIA': 'J', 'ST. VINCENT': 'J', 
                'SUBINAME': 'J', 'TRINIDAD &': 'J', 'TURKS & CALCOS I': 'J', 'ARE': 'J', 'BQN': 'J', 'FAJ': 'J', 
                'MAZ': 'J', 'NRR': 'J', 'PSE': 'J', 'SIG': 'J', 'URUGUAY': 'J', 'VENEZUELA': 'J', 
                'VIRGIN ISLANDS': 'J', 'COSTA RICA': 'J', 'CURACAO': 'J', 'DOMINICA': 'J', 'DOMINICAN': 'J', 
                'ECUADOR': 'J', 'EL SALVADOR': 'J', 'FRENCH GUIANA': 'J', 'GRENADA': 'J', 'GUADELOUPE': 'J', 
                'GUATEMALA': 'J', 'GUYANA': 'J', 'HAITI': 'J', 'HONDURAS': 'J', 'SOUTH AFRICA': 'K', 'CANADA': 'L', 
                'BAHRAIN': 'M', 'KUWAIT': 'M', 'OMAN': 'M', 'QATAR': 'M', 'CENT AFR REP': 'N', 'CHAD': 'N', 
                'KENYA': 'N', 'MAURITIUS': 'N', 'SUDAN': 'N', 'TANZANIA': 'N', 'UGANDA': 'N', 
                'DEMOCRATIC REPUBLIC OF': 'N', 'DJIBOUTI': 'N', 'ERITREA': 'N', 'ETHIOPIA': 'N', 'ALGERIA': 'O', 
                'ANGOLA': 'O', 'IVORY COAST': 'O', 'LIBYA': 'O', 'MOROCCO': 'O', 'NIGERIA': 'O', 'SEYCHELLES': 'O', 
                'GHANA': 'O', 'BOTSWANA': 'P', 'LESOTHO': 'P', 'NAMIBIA': 'P', 'RWANDA': 'P', 'SWAZILAND': 'P', 
                'ZAMBIA': 'P', 'ZIMBABWE': 'P', 'BENIN': 'Q', 'BURKINA FASO': 'Q', 'BURUNDI': 'Q', 'CAMEROON': 'Q', 
                'CAPE VERDE': 'Q', 'CONGO': 'Q', 'LIBERIA': 'Q', 'MADAGASCAR': 'Q', 'MALAVII': 'Q', 'MALI': 'Q', 
                'MAURITANIA': 'Q', 'MOZAMBIQUE': 'Q', 'NIGER': 'Q', 'REUNION ISLAND': 'Q', 'SENEGAL': 'Q', 
                'SIERRA LEONE': 'Q', 'TOGO': 'Q', 'TUNISIA': 'Q', 'EQUATORIAL GUINEA': 'Q', 'GABON': 'Q', 
                'GAMBIA': 'Q', 'GUINEA': 'Q', 'GUINEA BISSAU': 'Q'
            },
            'DHL': {
                'BANGLADESH': '1', 'BHUTAN': '1', 'MALDIVES': '1', 'NEPAL': '1', 'SRI LANKA': '1', 
                'UNITED ARAB EMIRATES': '1', 'HONG KONG': '2', 'MALAYSIA': '2', 'SINGAPORE': '2', 'THAILAND': '2', 
                'CHINA': '3', 'BAHRAIN': '4', 'JORDAN': '4', 'KUWAIT': '4', 'OMAN': '4', 'PAKISTAN': '4', 
                'QATAR': '4', 'SAUDI ARABIA': '4', 'BRUNEI': '5', 'CAMBODIA': '5', 'EAST TIMOR': '5', 
                'INDONESIA': '5', 'JAPAN': '5', 'KOREA': '5', 'LAOS': '5', 'MACAU': '5', 'MYANMAR': '5', 
                'PHILIPPINES': '5', 'TAIWAN': '5', 'VIETNAM': '5', 'NEW ZEALAND': '6', 'PAPUA NEW GUINEA': '6', 
                'AUSTRIA': '7', 'BELGIUM': '7', 'CZECH REPUBLIC': '7', 'DENMARK': '7', 'FRANCE': '7', 
                'GERMANY': '7', 'HUNGARY': '7', 'IRELAND': '7', 'ITALY': '7', 'LIECHTENSTEIN': '7', 
                'LUXEMBOURG': '7', 'MONACO': '7', 'NETHERLANDS': '7', 'POLAND': '7', 'PORTUGAL': '7', 
                'ROMANIA': '7', 'SLOVAKIA': '7', 'SPAIN': '7', 'SWEDEN': '7', 'SWITZERLAND': '7', 
                'UNITED KINGDOM': '7', 'VATICAN CITY STATE': '7', 'ANDORRA': '8', 'BELARUS': '8', 
                'BULGARIA': '8', 'CANARY ISLANDS': '8', 'CYPRUS': '8', 'ESTONIA': '8', 'FALKLAND ISLANDS': '8', 
                'FAROE ISLANDS': '8', 'GIBRALTAR': '8', 'GREECE': '8', 'GREENLAND': '8', 'GUERNSEY': '8', 
                'ICELAND': '8', 'ISRAEL': '8', 'JERSEY': '8', 'LATVIA': '8', 'LITHUANIA': '8', 'MALTA': '8', 
                'NORWAY': '8', 'SLOVENIA': '8', 'TURKEY': '8', 'AMERICAN SAMOA': '9', 'CANADA': '9', 
                'GUAM': '9', 'MARSHALL ISLANDS': '9', 'MEXICO': '9', 'PUERTO RICO': '9', 'VIRGIN ISLANDS': '9', 
                'ARGENTINA': '10', 'ANTIGUA AND BARBUDA': '10', 'ARUBA': '10', 'BAHAMAS': '10', 'BARBADOS': '10', 
                'BELIZE': '10', 'BOLIVIA': '10', 'BRAZIL': '10', 'CAYMAN ISLANDS': '10', 'CHILE': '10', 
                'COLOMBIA': '10', 'COSTA RICA': '10', 'CUBA': '10', 'CURACAO': '10', 'DOMINICA': '10', 
                'DOMINICAN REPUBLIC': '10', 'ECUADOR': '10', 'EL SALVADOR': '10', 'FRENCH GUYANA': '10', 
                'GRENADA': '10', 'GUADELOUPE': '10', 'GUATEMALA': '10', 'HAITI': '10', 'HONDURAS': '10', 
                'JAMAICA': '10', 'MARTINIQUE': '10', 'MONTSERRAT': '10', 'NICARAGUA': '10', 'PANAMA': '10', 
                'PARAGUAY': '10', 'PERU': '10', 'ST. BARTHELEMY': '10', 'ST. LUCIA': '10', 'ST. MAARTEN': '10', 
                'SURINAME': '10', 'TRINIDAD AND TOBAGO': '10', 'TURKS AND CAICOS ISLANDS': '10', 'URUGUAY': '10', 
                'VENEZUELA': '10', 'TANZANIA': '13', 'UGANDA': '13', 'ZIMBABWE': '13', 'AUSTRALIA': '14'
            },
            'UPS': {
                'BANGLADESH': '1', 'NEPAL': '1', 'SRI LANKA': '1', 'UAE': '1',
                'MACAO': '2', 'TAIWAN': '2', 'VIETNAM': '2',
                'BRUNEI': '3', 'INDONESIA': '3', 'JORDAN': '3', 'KUWAIT': '3', 'LEBANON': '3', 'NORFOLK ISLAND': '3', 'OMAN': '3', 'PAKISTAN': '3', 'PHILIPPINES': '3', 'QATAR': '3', 'ARABIA': '3', 'YEMEN': '3', 'CHINA': '3',
                'ANDORRA': '4', 'LIECHTENSTEIN': '4', 'MONACO': '4', 'SAN MARINO': '4',
                'CHANNEL ISLANDS': '5', 'GUERNSEY': '5', 'JERSEY': '5', 'NEW CALEDONIA': '5', 'MAURITIUS': '5',
                'CANADA': '6', 'USA': '6', 'UNITED STATES': '6', 'GERMANY': '6', 'FRANCE': '6', 'UNITED KINGDOM': '6', 'UK': '6', 'ITALY': '6', 'SPAIN': '6', 'NETHERLANDS': '6', 'BELGIUM': '6', 'AUSTRIA': '6', 'SWITZERLAND': '6', 'DENMARK': '6', 'SWEDEN': '6', 'NORWAY': '6', 'FINLAND': '6', 'IRELAND': '6', 'PORTUGAL': '6', 'GREECE': '6', 'TURKEY': '6', 'RUSSIA': '6', 'UKRAINE': '6', 'BELARUS': '6', 'KAZAKHSTAN': '6', 'JAPAN': '6', 'SOUTH KOREA': '6', 'HONG KONG': '6', 'SINGAPORE': '6', 'MALAYSIA': '6', 'THAILAND': '6', 'AUSTRALIA': '6', 'NEW ZEALAND': '6', 'BRAZIL': '6', 'ARGENTINA': '6', 'CHILE': '6', 'COLOMBIA': '6', 'PERU': '6', 'VENEZUELA': '6', 'MEXICO': '6', 'INDIA': '6',
                'CZECH REPUBLIC': '7', 'HUNGARY': '7', 'POLAND': '7'
            }
        },
        'metadata': {
            'generated_at': '2025-01-23',
            'source': 'Multiple CSV files from price directory',
            'total_carriers': 0,
            'total_countries': set(),
            'total_weight_tiers': set()
        }
    }
    
    # Process each CSV file
    for csv_file in csv_files:
        carrier_data = parse_csv_file(csv_file)
        
        if carrier_data:
            carrier_name = carrier_data['name']
            master_data['carriers'][carrier_name] = {
                'services': carrier_data['services'],
                'countries': carrier_data['countries'],
                'weight_tiers': carrier_data['weight_tiers']
            }
            
            # Update metadata
            master_data['metadata']['total_countries'].update(carrier_data['countries'])
            master_data['metadata']['total_weight_tiers'].update(carrier_data['weight_tiers'])
    
    # Finalize metadata
    master_data['metadata']['total_carriers'] = len(master_data['carriers'])
    master_data['metadata']['total_countries'] = sorted(list(master_data['metadata']['total_countries']))
    master_data['metadata']['total_weight_tiers'] = sorted(list(master_data['metadata']['total_weight_tiers']))
    
    # Save to JSON file
    output_file = 'courier_rates_master.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(master_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n🎉 Master JSON created successfully!")
    print(f"📁 File: {output_file}")
    print(f"🚚 Total carriers: {master_data['metadata']['total_carriers']}")
    print(f"🌍 Total countries: {len(master_data['metadata']['total_countries'])}")
    print(f"⚖️  Total weight tiers: {len(master_data['metadata']['total_weight_tiers'])}")
    
    # Print carrier summary
    print(f"\n📊 Carrier Summary:")
    for carrier_name, carrier_info in master_data['carriers'].items():
        print(f"  🚚 {carrier_name}: {len(carrier_info['countries'])} countries, {len(carrier_info['weight_tiers'])} weight tiers")
    
    return master_data

if __name__ == '__main__':
    create_master_json()
