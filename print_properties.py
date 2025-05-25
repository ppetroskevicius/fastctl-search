import json
import re
from loguru import logger
import os
from typing import Optional, List, Dict
from models import Properties, Property
from dotenv import load_dotenv
from collections import defaultdict
import time

load_dotenv()

# Collection name
COLLECTION_NAME = "real_estate"

def parse_floor(floor: str) -> Optional[int]:
    """Parse floor string (e.g., '2F' or '1F (of 5F)') to a numeric value or None if invalid."""
    if not floor or floor == "0F":
        return None
    match = re.match(r"(\d+)", floor)
    return int(match.group(1)) if match else None

def normalize_ward(ward: str) -> str:
    """Normalize ward for consistent indexing (e.g., 'Shibuya-ku' -> 'Shibuya')."""
    if not ward:
        return ""
    ward = ward.lower().replace("-ku", "").replace("ward", "").replace(",", "").strip()
    return ward.capitalize()

def preprocess_raw_data(raw_data: Dict, json_file: str) -> Dict:
    """Preprocess raw JSON data to unify amenities and fix floor."""
    if not isinstance(raw_data, dict) or "properties" not in raw_data:
        return raw_data

    # Check for duplicate coordinates in Buy properties
    if "buy_details" in json_file.lower():
        coords = defaultdict(list)
        for idx, prop in enumerate(raw_data["properties"], 1):
            if "address" in prop and "latitude" in prop["address"] and "longitude" in prop["address"]:
                coord = (prop["address"]["latitude"], prop["address"]["longitude"])
                coords[coord].append((idx, prop.get("name", "Unknown"), prop.get("address", {}).get("full", "Unknown")))
        for coord, props in coords.items():
            if len(props) > 1:
                addresses = [p[2] for p in props]
                if len(set(addresses)) > 1:
                    logger.warning(f"Inconsistent addresses for coordinate {coord} in {json_file}: {addresses}")
                else:
                    logger.debug(f"Valid multi-unit coordinates {coord} in {json_file}: {len(props)} units")

    for prop in raw_data["properties"]:
        # Unify amenities
        amenities = []
        if "features" in prop:
            if isinstance(prop["features"], dict):
                if "unit" in prop["features"]:
                    amenities.extend(prop["features"]["unit"])
                if "building" in prop["features"]:
                    amenities.extend(prop["features"]["building"])
        if "amenities" in prop and isinstance(prop["amenities"], list):
            amenities.extend(prop["amenities"])
        if "unit_notes_amenities" in prop and isinstance(prop["unit_notes_amenities"], list):
            amenities.extend(prop["unit_notes_amenities"])
        if "building_notes" in prop and isinstance(prop["building_notes"], dict) and "facilities" in prop["building_notes"]:
            for key in prop["building_notes"]["facilities"]:
                amenities.append(key)
        prop["amenities"] = amenities
        logger.debug(f"Unified amenities for {prop.get('name', 'Unknown')}: {len(amenities)} items")

        # Fix invalid floor
        if prop.get("floor") == "0F":
            logger.debug(f"Fixed floor '0F' to None for {prop.get('name', 'Unknown')}")
            prop["floor"] = None

        # Remove features to avoid schema mismatch
        if "features" in prop:
            del prop["features"]

    return raw_data

# JSON files to process
json_files = [
    "data/json/rent_details_20250519.json",
    "data/json/buy_details_20250519.json",
    "data/json/short_term_details_20250519.json",
]

# Output dictionary
all_properties = {}

logger.info(f"Processing {len(json_files)} JSON files for JSON output")

for json_file in json_files:
    logger.info(f"Processing {json_file}")
    
    # Load JSON data
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        logger.info(f"Loaded {json_file} with {len(raw_data.get('properties', []))} properties")
    except Exception as e:
        logger.error(f"Failed to load JSON data from {json_file}: {e}")
        continue

    # Preprocess raw data
    raw_data = preprocess_raw_data(raw_data, json_file)

    # Validate with Pydantic
    try:
        properties_data = Properties(**raw_data)
        properties = properties_data.properties
        logger.info(f"Validated {len(properties)} properties from {json_file}")
        
        # Convert properties to JSON-serializable format
        properties_list = []
        for prop in properties:
            prop_dict = prop.dict(exclude_none=True)
            # Normalize ward and compute pet_friendly as in index_properties.py
            prop_dict["ward"] = normalize_ward(prop.address.full.split(", ")[1] if ", " in prop.address.full else "")
            prop_dict["pet_friendly"] = any("Pet Friendly" in amenity or "Pet Negotiable" in amenity for amenity in prop_dict.get("amenities", []))
            prop_dict["floor_number"] = parse_floor(prop_dict.get("floor"))
            # Ensure nested objects are serialized
            if "nearest_stations" in prop_dict:
                prop_dict["nearest_stations"] = [
                    {
                        "name": s.station_name,
                        "walk_time_min": s.walk_time_min,
                        "lines": [sl.name for sl in s.lines]
                    } for s in prop.nearest_stations
                ]
            properties_list.append(prop_dict)
        
        # Store in output dictionary
        file_key = os.path.basename(json_file).replace(".json", "")
        all_properties[file_key] = properties_list
        
    except Exception as e:
        logger.error(f"Failed to validate properties in {json_file}: {e}")
        continue

# Save all properties to JSON file
output_file = "properties_output.json"
try:
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_properties, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved all properties to {output_file}")
except Exception as e:
    logger.error(f"Failed to save properties to {output_file}: {e}")

# Print sample properties inline (5 per file)
print("\nSample Properties (5 per file):")
for file_key, props in all_properties.items():
    print(f"\n{file_key}:")
    for i, prop in enumerate(props[:5], 1):
        print(f"Property {i}:")
        print(json.dumps(prop, indent=2, ensure_ascii=False))