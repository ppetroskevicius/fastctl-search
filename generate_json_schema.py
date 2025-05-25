import json
import os
from typing import List, Dict
from loguru import logger
from genson import SchemaBuilder

def preprocess_data(data: Dict) -> Dict:
    """
    Preprocess JSON data to normalize building_notes.facilities field.
    
    Args:
        data (Dict): Raw JSON data.
        
    Returns:
        Dict: Preprocessed JSON data.
    """
    if not isinstance(data, dict) or "properties" not in data:
        return data
    
    for prop in data["properties"]:
        if "building_notes" in prop and isinstance(prop["building_notes"], dict):
            facilities = prop["building_notes"].get("facilities", {})
            if isinstance(facilities, dict):
                # Replace facilities with a generic structure
                prop["building_notes"]["facilities"] = {
                    "generic_facility": []
                }
    return data

def generate_schema_from_file(json_file: str) -> Dict:
    """
    Generate a JSON schema from a single JSON file, with preprocessing.
    
    Args:
        json_file (str): Path to the JSON file.
        
    Returns:
        Dict: Generated JSON schema, or empty dict if file processing fails.
    """
    builder = SchemaBuilder()
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        # Preprocess data to normalize facilities
        data = preprocess_data(raw_data)
        if not isinstance(data, dict) or "properties" not in data:
            logger.error(f"Invalid structure in {json_file}: Expected dict with 'properties' key")
            return {}
        for prop in data["properties"]:
            builder.add_object(prop)
        schema = builder.to_schema()
        logger.info(f"Generated schema for {json_file} with {len(raw_data['properties'])} properties")
        return schema
    except FileNotFoundError:
        logger.error(f"File {json_file} not found")
        return {}
    except json.JSONDecodeError:
        logger.error(f"Error parsing JSON in {json_file}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error processing {json_file}: {e}")
        return {}

def merge_schemas(schemas: List[Dict]) -> Dict:
    """
    Merge multiple JSON schemas into a single comprehensive schema.
    
    Args:
        schemas (List[Dict]): List of JSON schemas to merge.
        
    Returns:
        Dict: Merged JSON schema.
    """
    if not schemas:
        logger.warning("No schemas provided to merge")
        return {"type": "object", "properties": {}, "required": []}
    
    merged_builder = SchemaBuilder()
    
    for schema in schemas:
        if schema:
            merged_builder.add_schema(schema)
    
    merged_schema = merged_builder.to_schema()
    
    # Ensure all properties are optional unless present in all schemas
    if schemas:
        all_required = set()
        for schema in schemas:
            required = set(schema.get("required", []))
            if not all_required:
                all_required = required
            else:
                all_required &= required
        merged_schema["required"] = list(all_required)
    
    logger.info(f"Merged {len(schemas)} schemas with {len(merged_schema.get('required', []))} required fields")
    return merged_schema

def generate_comprehensive_schema(json_files: List[str], output_file: str) -> None:
    """
    Generate a comprehensive JSON schema from multiple JSON files and save it.
    
    Args:
        json_files (List[str]): List of paths to JSON files.
        output_file (str): Path to save the merged schema.
    """
    # Generate schemas for each file
    schemas = []
    for json_file in json_files:
        schema = generate_schema_from_file(json_file)
        if schema:
            schemas.append(schema)
    
    # Merge schemas
    comprehensive_schema = merge_schemas(schemas)
    
    # Save to output file
    try:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(comprehensive_schema, f, indent=2, sort_keys=True)
        logger.info(f"Saved comprehensive schema to {output_file}")
    except Exception as e:
        logger.error(f"Failed to save schema to {output_file}: {e}")

def main():
    # Configure logging
    logger.remove()
    logger.add("generate_schema.log", rotation="10 MB", level="INFO")
    logger.add(lambda msg: print(msg, end=""), level="INFO")
    
    # Define input JSON files
    json_files = [
        "data/json/rent_details_20250519.json",
        "data/json/buy_details_20250519.json",
        "data/json/short_term_details_20250519.json",
    ]
    
    # Define output file
    output_file = "data/comprehensive_real_estate_schema.json"
    
    logger.info(f"Starting schema generation for {len(json_files)} JSON files")
    generate_comprehensive_schema(json_files, output_file)
    logger.info("Schema generation completed")

if __name__ == "__main__":
    main()
