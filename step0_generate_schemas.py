import json
from genson import SchemaBuilder
from loguru import logger
import os
import traceback
from typing import Dict, List, Set, Any
from collections import Counter, defaultdict
from jsonschema import validate, ValidationError
from pprint import pformat

# Configure logging
logger.add("schema_generation.log", rotation="10 MB", level="INFO")

# Directory containing the full dataset JSON files
DATA_DIR = "data/json/"

# Full dataset JSON files
JSON_FILES = {
    "rent": "rent_details_20250519.json",
    "buy": "buy_details_20250519.json",
    "short_term": "short_term_details_20250519.json"
}

# Output directory for schema files
OUTPUT_DIR = "data/schemas/"

# Minimum ratio of unique values to total values to consider a field as an enum
ENUM_THRESHOLD = 0.1  # If unique values are less than 10% of total values, consider it an enum

# Minimum occurrences for a value to be included in enum
MIN_ENUM_OCCURRENCES = 3

# Critical enum fields that should include all values, even single occurrences
CRITICAL_ENUM_FIELDS = {
    "type",
    "property_type",
    "contract.type",
    "contract.length",
    "details.land_rights",
    "details.transaction_type",
    "amenities[]",  # Include all amenities across property types
    "nearest_stations[].lines[].name",  # Include all train line names
    "features.unit[]"  # Include all unit features
}

# Fields that should always be treated as free text (not enum)
FORCE_TEXT_FIELDS = {
    "name", "description", "additional_info", "unit_notes", 
    "full", "summary", "bedrooms", "balcony",
    "nearest_stations[].walk_time_min",  # Treat walk time as numeric, not enum
    "nearest_stations[].station_name",    # Treat station names as free text
    "building.total_floors",              # Treat total floors as numeric
    "building.structure",                 # Building structure should be free text
    "layout",                            # Layout can vary (SOHO, 6 Bedrooms, etc.)
    "details.layout",                    # Layout in details can also vary
    "details.floor",                     # Floor can vary (16F, etc.)
    "built_year",                        # Built year should be numeric
    "year_built",                        # Alternative field name for built year
    "details.balcony_direction",         # Balcony direction can have varying formats
    "price.management_fee",              # Management fee should be numeric with range
    "price.fire_insurance",              # Fire insurance should be numeric with range
    "initial_cost_estimate.fire_insurance",  # Initial fire insurance should be numeric with range
    "features.building[]",               # Building features can vary (especially parking fees)
    "facilities[]"                       # Facility descriptions should be free text
}

# Fields that should always be treated as enums
FORCE_ENUM_FIELDS = {
    "price.currency", 
    "status", 
    "features.unit[]",
    "nearest_stations[].lines[].company",  # Train companies
    "nearest_stations[].lines[].name"      # Train line names
}

# Known enums for specific fields
KNOWN_ENUMS = {
    # Only keep truly fixed enums that shouldn't vary
    "price.currency": ["JPY"],
    "status": ["Available", "Under Contract", "Sold"]
}

# Required fields by property type
REQUIRED_FIELDS = {
    "common": [
        "id", "url", "name", "property_type", "address", "area", "type", "price", "images"
    ],
    "rent": [
        "initial_cost_estimate"
    ],
    "buy": [
        "status", "listing_id", "last_updated"
    ],
    "short_term": [
        "contract"
    ]
}

# Format validations for specific fields
FORMAT_VALIDATIONS = {
    "url": "uri",
    "last_updated": "date"
}

class GlobalEnumCollector:
    def __init__(self):
        self.field_values = defaultdict(Counter)
    
    def add_values(self, field_path: str, values: Counter):
        """Add values to the global counter for a field"""
        self.field_values[field_path].update(values)
    
    def get_enum_values(self, field_path: str) -> List[str]:
        """Get enum values for a field across all property types"""
        if field_path not in self.field_values:
            return []
        
        # For critical fields, include all values
        min_occurrences = 1 if field_path in CRITICAL_ENUM_FIELDS else MIN_ENUM_OCCURRENCES
        values = [v for v, c in self.field_values[field_path].items() 
                 if c >= min_occurrences and v != "None"]
        return sorted(values)

def collect_field_values(data: List[Dict], path: str = "") -> Dict[str, Counter]:
    """Collect all values for each field to detect enums"""
    field_values = {}
    
    def process_value(current_path: str, value: Any):
        if current_path not in field_values:
            field_values[current_path] = Counter()
            
        if isinstance(value, dict):
            for k, v in value.items():
                new_path = f"{current_path}.{k}" if current_path else k
                process_value(new_path, v)
        elif isinstance(value, list):
            array_path = f"{current_path}[]" if current_path else "[]"
            if array_path not in field_values:
                field_values[array_path] = Counter()
                
            if value and isinstance(value[0], dict):
                for item in value:
                    for k, v in item.items():
                        new_path = f"{array_path}.{k}"
                        process_value(new_path, v)
            else:
                for item in value:
                    field_values[array_path][str(item)] += 1
        else:
            field_values[current_path][str(value)] += 1
    
    for item in data:
        for field, value in item.items():
            process_value(field, value)
    
    return field_values

def should_be_enum(field_path: str, values: Counter) -> bool:
    """Determine if a field should be treated as an enum"""
    if field_path in FORCE_ENUM_FIELDS:
        return True
    if field_path in FORCE_TEXT_FIELDS:
        return False
    
    unique_values = len(values)
    total_values = sum(values.values())
    
    if unique_values <= 1:
        return False
        
    return unique_values / total_values <= ENUM_THRESHOLD

def generate_field_description(field_path: str, values: Counter, property_type: str) -> str:
    """Generate a description for a field based on its values and context"""
    # Get the field type(s)
    types = set()
    for value in values:
        if value == "None":
            types.add("null")
        elif value.isdigit():
            types.add("integer")
        elif value.replace(".", "", 1).isdigit():
            types.add("number")
        elif value.lower() in ("true", "false"):
            types.add("boolean")
        else:
            types.add("string")
    
    type_str = " or ".join(sorted(types))
    base_desc = f"Field type: {type_str}. "
    
    # Add usage context
    if field_path in REQUIRED_FIELDS["common"]:
        base_desc += "Required field across all property types. "
    elif field_path in REQUIRED_FIELDS.get(property_type, []):
        base_desc += f"Required field for {property_type} properties. "
    
    # Add enum information if applicable
    if should_be_enum(field_path, values):
        if field_path in KNOWN_ENUMS:
            enum_values = KNOWN_ENUMS[field_path]
        else:
            enum_values = [v for v, c in values.most_common() 
                         if c >= MIN_ENUM_OCCURRENCES and v != "None"]
        if enum_values:
            base_desc += f"Possible values: {', '.join(sorted(enum_values))}. "
    # Add numeric range for numeric fields
    elif any(field in field_path for field in ["walk_time_min", "total_floors", "built_year", "year_built", 
                                             "price.management_fee", "price.fire_insurance", 
                                             "initial_cost_estimate.fire_insurance"]):
        numeric_values = [int(v) for v in values.keys() if v.isdigit()]
        if numeric_values:
            if "walk_time_min" in field_path:
                base_desc += f"Range: {min(numeric_values)} to {max(numeric_values)} minutes. "
            elif "total_floors" in field_path:
                base_desc += f"Range: {min(numeric_values)} to {max(numeric_values)} floors. "
            elif any(year_field in field_path for year_field in ["built_year", "year_built"]):
                base_desc += f"Range: {min(numeric_values)} to {max(numeric_values)}. "
            elif field_path == "price.management_fee":
                base_desc += f"Range: {min(numeric_values):,} to {max(numeric_values):,} JPY per month. "
            elif any(field in field_path for field in ["price.fire_insurance", "initial_cost_estimate.fire_insurance"]):
                base_desc += f"Range: {min(numeric_values):,} to {max(numeric_values):,} JPY per year. "
    # Add pattern hint for station names
    elif "station_name" in field_path:
        base_desc += "Format: Usually a station name followed by 'Station', but can also be other location references. "
    # Add format hints for specific fields
    elif "layout" in field_path:  # Changed to match both layout fields
        base_desc += "Format: Number of bedrooms (e.g. '2 Bedrooms') or specific layout type (e.g. 'SOHO', 'Studio'). "
    elif field_path == "details.floor":
        base_desc += "Format: Floor number followed by 'F' (e.g. '16F'). "
    elif field_path == "details.balcony_direction":
        base_desc += "Format: Cardinal or intercardinal direction (e.g. 'North', 'North-east', 'Northeast'). "
    elif field_path == "features.building[]":
        base_desc += "Format: Building feature name, optionally with additional details in parentheses (e.g. 'Parking(41,580JPY/mo)', 'Elevator'). "
    elif field_path == "facilities[]":
        base_desc += "Format: Descriptive text about facilities, amenities, and surroundings. "
    
    # Add example
    example = next((v for v in values if v != "None"), None)
    if example and len(example) <= 50:
        base_desc += f"Example: {example}"
    
    return base_desc.strip()

def collect_field_values_from_file(json_file: str) -> Dict[str, Counter]:
    """Collect field values from a single JSON file"""
    try:
        with open(os.path.join(DATA_DIR, json_file), "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if not isinstance(data, dict) or "properties" not in data:
            logger.error(f"Invalid data structure in {json_file}")
            return {}
        
        return collect_field_values(data["properties"])
    except Exception as e:
        logger.error(f"Error collecting values from {json_file}: {str(e)}")
        return {}

def enhance_schema(schema: dict, field_values: Dict[str, Counter], property_type: str, global_enums: GlobalEnumCollector) -> dict:
    """Enhance the generated schema with enums, descriptions, and formats"""
    def process_properties(properties: dict, parent_path: str = ""):
        for field, schema_def in properties.items():
            current_path = f"{parent_path}.{field}" if parent_path else field
            
            # Special handling for facilities
            if current_path == "building_notes.facilities":
                schema_def["type"] = "object"
                schema_def["properties"] = {}  # Empty properties object
                schema_def["additionalProperties"] = {"type": "string"}
                schema_def["description"] = "Object containing facility descriptions and nearby amenities as key-value pairs"
                continue
            
            # Add format validation if applicable
            if current_path in FORMAT_VALIDATIONS:
                schema_def["format"] = FORMAT_VALIDATIONS[current_path]
            
            # Add description
            if current_path in field_values:
                schema_def["description"] = generate_field_description(
                    current_path, field_values[current_path], property_type)
                
                # Handle numeric fields specifically
                if any(field in current_path for field in ["walk_time_min", "total_floors", "built_year", "year_built", 
                                                         "price.management_fee", "price.fire_insurance", 
                                                         "initial_cost_estimate.fire_insurance"]):
                    schema_def["type"] = "integer"
                    numeric_values = [int(v) for v in field_values[current_path].keys() if v.isdigit()]
                    if numeric_values:
                        schema_def["minimum"] = min(numeric_values)
                        schema_def["maximum"] = max(numeric_values)
            
            # Handle array items
            if schema_def.get("type") == "array" and "items" in schema_def:
                if isinstance(schema_def["items"], dict):
                    if "properties" in schema_def["items"]:
                        process_properties(schema_def["items"]["properties"], f"{current_path}[]")
                    else:
                        array_path = f"{current_path}[]"
                        if array_path in field_values and should_be_enum(array_path, field_values[array_path]):
                            values = global_enums.get_enum_values(array_path)
                            if values:
                                schema_def["items"]["enum"] = values
            
            # Handle nested objects
            elif schema_def.get("type") == "object" and "properties" in schema_def:
                process_properties(schema_def["properties"], current_path)
            
            # Handle regular fields
            elif current_path in field_values:
                if should_be_enum(current_path, field_values[current_path]):
                    if current_path in KNOWN_ENUMS:
                        schema_def["enum"] = KNOWN_ENUMS[current_path]
                    else:
                        values = global_enums.get_enum_values(current_path)
                        if values:
                            schema_def["enum"] = values
    
    # Add required fields
    schema["required"] = (
        REQUIRED_FIELDS["common"] + 
        REQUIRED_FIELDS.get(property_type, [])
    )
    
    # Process all properties
    if "properties" in schema:
        process_properties(schema["properties"])
    
    return schema

def validate_data_against_schema(data: dict, schema: dict, property_type: str) -> bool:
    """Validate the data against the generated schema"""
    try:
        if not isinstance(data, dict) or "properties" not in data:
            logger.error(f"Invalid data structure: 'properties' key missing or not a dict")
            return False
            
        properties = data["properties"]
        validation_errors = []
        
        # Validate each property individually to collect all errors
        for idx, prop in enumerate(properties):
            try:
                # Transform facilities data before validation
                if "building_notes" in prop and "facilities" in prop["building_notes"]:
                    facilities = prop["building_notes"]["facilities"]
                    transformed_facilities = {}
                    for key, value in facilities.items():
                        # Convert empty arrays or any arrays to empty string
                        transformed_facilities[key] = "" if isinstance(value, list) else str(value)
                    prop["building_notes"]["facilities"] = transformed_facilities
                
                validate(instance=prop, schema=schema)
            except ValidationError as e:
                validation_errors.append(f"Property {idx}: {str(e)}")
        
        if validation_errors:
            logger.error(f"Validation errors found in {property_type} data:")
            for error in validation_errors:
                logger.error(error)
            return False
            
        logger.info(f"Successfully validated {len(properties)} {property_type} properties")
        return True
        
    except Exception as e:
        logger.error(f"Error during validation of {property_type} data: {str(e)}")
        return False

def generate_and_save_schema(json_file: str, property_type: str, global_enums: GlobalEnumCollector) -> None:
    """Generate and save JSON schema for a specific property type"""
    try:
        logger.debug(f"Opening file {os.path.join(DATA_DIR, json_file)}")
        
        # Load and validate input data
        with open(os.path.join(DATA_DIR, json_file), "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if not isinstance(data, dict) or "properties" not in data:
            logger.error(f"Invalid data structure in {json_file}: 'properties' key missing or not a dict")
            return
        
        properties = data["properties"]
        logger.debug(f"Found {len(properties)} properties in {json_file}")
        
        # Initialize SchemaBuilder with base schema
        builder = SchemaBuilder(schema_uri="http://json-schema.org/draft-07/schema#")
        
        # Add each property to build the base schema
        for prop in properties:
            builder.add_object(prop)
        
        # Get the base schema from GenSON
        schema = builder.to_schema()
        
        # Collect field values for enum detection and descriptions
        field_values = collect_field_values(properties)
        
        # Enhance schema with our custom logic, using global enums
        schema = enhance_schema(schema, field_values, property_type, global_enums)
        
        # Save schema
        output_file = os.path.join(OUTPUT_DIR, f"{property_type}_schema.json")
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(schema, f, indent=2)
        
        logger.info(f"Generated and saved schema for {property_type} properties ({len(properties)} items)")
        
        # Validate data against the generated schema
        validation_success = validate_data_against_schema(data, schema, property_type)
        if validation_success:
            logger.info(f"Schema validation successful for {property_type} data")
        else:
            logger.warning(f"Schema validation failed for {property_type} data")
        
    except Exception as e:
        logger.error(f"Error processing {json_file}: {str(e)}")
        logger.error(f"Stack trace: {traceback.format_exc()}")

def main():
    """Generate and save JSON schemas for all property types"""
    try:
        logger.info("Starting schema generation for real estate property types")
        
        # First pass: collect all enum values across all property types
        global_enums = GlobalEnumCollector()
        for property_type, json_file in JSON_FILES.items():
            logger.info(f"Collecting enum values from {json_file}")
            field_values = collect_field_values_from_file(json_file)
            for field_path, values in field_values.items():
                # Always collect values for FORCE_ENUM_FIELDS and CRITICAL_ENUM_FIELDS
                if field_path in FORCE_ENUM_FIELDS or field_path in CRITICAL_ENUM_FIELDS or should_be_enum(field_path, values):
                    global_enums.add_values(field_path, values)
        
        # Log collected enum values for critical fields
        for field in CRITICAL_ENUM_FIELDS:
            values = global_enums.get_enum_values(field)
            logger.info(f"Collected values for {field}: {values}")
        
        # Second pass: generate schemas using global enum values
        for property_type, json_file in JSON_FILES.items():
            logger.info(f"Processing {property_type} properties from {json_file}")
            generate_and_save_schema(json_file, property_type, global_enums)
        
        logger.info("Completed schema generation")
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        logger.error(f"Stack trace: {traceback.format_exc()}")

if __name__ == "__main__":
    main() 