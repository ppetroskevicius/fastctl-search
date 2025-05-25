import json
import os
from loguru import logger
from typing import List
from collections import defaultdict
from models import Properties, Property

# Configure logging
logger.remove()
logger.add("test_models.log", rotation="10 MB", level="INFO")
logger.add(lambda msg: print(msg, end=""), level="INFO")

def test_file(json_file: str) -> None:
    """
    Test validation of a JSON file against the Properties model.
    
    Args:
        json_file (str): Path to the JSON file.
    """
    logger.info(f"Testing file: {json_file}")
    
    # Check if file exists
    if not os.path.exists(json_file):
        logger.error(f"File not found: {json_file}")
        return
    
    # Load JSON data
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"Loaded {json_file} with {len(data.get('properties', []))} properties")
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error in {json_file}: {e}")
        return
    except Exception as e:
        logger.error(f"Unexpected error loading {json_file}: {e}")
        return
    
    # Validate with Pydantic
    try:
        properties = Properties(**data)
        logger.info(f"Successfully validated {len(properties.properties)} properties in {json_file}")
        
        # Check for duplicate latitude/longitude in Buy properties
        if "buy_details" in json_file.lower():
            coords = defaultdict(list)
            for idx, prop in enumerate(properties.properties, 1):
                coord = (prop.address.latitude, prop.address.longitude)
                coords[coord].append((idx, prop.name))
            for coord, props in coords.items():
                if len(props) > 1:
                    logger.warning(f"Duplicate coordinates {coord} in {json_file}: {props}")
        
        # Check each property for specific fields
        for idx, prop in enumerate(properties.properties, 1):
            try:
                # Log key fields for debugging
                logger.debug(
                    f"Property {idx} ({prop.name}, {prop.property_type}): "
                    f"ID={prop.id}, Type={prop.type}, Price={prop.price.model_dump()}, "
                    f"Amenities={len(prop.amenities)}, Stations={len(prop.nearest_stations)}"
                )
                
                # Verify required fields
                required_fields = [
                    "id", "name", "property_type", "type", "url",
                    "address", "area", "price", "images"
                ]
                for field in required_fields:
                    if getattr(prop, field) is None:
                        logger.warning(f"Property {idx} ({prop.name}): Missing required field {field}")
                
                # Verify price fields based on property_type
                if prop.property_type == "Buy":
                    if prop.price.total is None:
                        logger.warning(f"Property {idx} ({prop.name}): Buy property missing price.total")
                elif prop.property_type in ["Rent", "Short-Term"]:
                    if prop.price.monthly_total is None:
                        logger.warning(f"Property {idx} ({prop.name}): {prop.property_type} property missing price.monthly_total")
                
                # Check for invalid floor values (e.g., "0F")
                if prop.floor == "0F":
                    logger.warning(f"Property {idx} ({prop.name}): Invalid floor value '0F'")
                
                # Verify nested fields
                if prop.address and not all([prop.address.full, prop.address.latitude, prop.address.longitude]):
                    logger.warning(f"Property {idx} ({prop.name}): Incomplete address")
                
                if prop.images and not all([prop.images.main, prop.images.floorplan]):
                    logger.warning(f"Property {idx} ({prop.name}): Incomplete images")
                
            except Exception as e:
                logger.error(f"Error validating property {idx} ({prop.name}): {e}")
                
    except Exception as e:
        logger.error(f"Validation failed for {json_file}: {e}")
        return

def main():
    # Define JSON files to test
    json_files = [
        "data/json/rent_details_20250519.json",
        "data/json/buy_details_20250519.json",
        "data/json/short_term_details_20250519.json",
    ]
    
    logger.info(f"Starting validation for {len(json_files)} JSON files")
    
    # Test each file
    for json_file in json_files:
        test_file(json_file)
    
    logger.info("Validation completed")

if __name__ == "__main__":
    main()
