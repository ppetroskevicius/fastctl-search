import json
import re
from loguru import logger
import os
from typing import Optional, List, Dict
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct, PayloadSchemaType
from openai import OpenAI
from models import Properties, Property
from dotenv import load_dotenv
from collections import defaultdict
import time

# Configure logging
logger.remove()  # Remove default handler
logger.add(
    "index_properties.log",
    rotation="100 MB",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"
)
logger.info("Starting property indexing process")

load_dotenv()

# Configuration for testing mode
TEST_MODE = True  # Set to False for processing all properties
TEST_PROPERTIES_PER_TYPE = 20  # Number of properties to process per type when TEST_MODE is True

# Initialize clients
qdrant_url = os.getenv("QDRANT_URL")
qdrant_api_key = os.getenv("QDRANT_API_KEY")
if not qdrant_url or not qdrant_api_key:
    logger.error("QDRANT_URL and QDRANT_API_KEY must be set in environment variables")
    raise ValueError("QDRANT_URL and QDRANT_API_KEY must be set in environment variables")

qdrant_client = QdrantClient(
    url=qdrant_url,
    api_key=qdrant_api_key,
)
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Collection name
COLLECTION_NAME = "real_estate"

# Batch sizes
OPENAI_BATCH_SIZE = 50  # Number of texts per OpenAI embedding request
QDRANT_BATCH_SIZE = 100  # Number of points per Qdrant upsert request

def parse_floor(floor: str) -> Optional[int]:
    """Parse floor string (e.g., '2F' or '1F (of 5F)') to a numeric value or None if invalid."""
    if not floor or floor == "0F":
        return None
    match = re.match(r"(\d+)", floor)
    return int(match.group(1)) if match else None

def normalize_facility_key(comment: str) -> str:
    """Normalize facility comments to generic categories."""
    comment = comment.lower()
    if "supermarket" in comment:
        return "Supermarket"
    elif "convenience store" in comment:
        return "Convenience Store"
    elif "park" in comment:
        return "Park"
    elif "drug store" in comment or "drugstore" in comment:
        return "Drug Store"
    elif "cafe" in comment or "restaurant" in comment:
        return "Cafe/Restaurant"
    else:
        return "Other Facility"  # Catch-all for other descriptive comments

def preprocess_raw_data(raw_data: Dict, json_file: str) -> Dict:
    """Preprocess raw JSON data to unify amenities, normalize facilities, and fix floor."""
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
        if "features" in prop and isinstance(prop["features"], dict):
            if "unit" in prop["features"]:
                amenities.extend(prop["features"]["unit"])
            if "building" in prop["features"]:
                amenities.extend(prop["features"]["building"])
        if "amenities" in prop and isinstance(prop["amenities"], list):
            amenities.extend(prop["amenities"])
        if "unit_notes_amenities" in prop and isinstance(prop["unit_notes_amenities"], list):
            amenities.extend(prop["unit_notes_amenities"])
        
        # Handle facilities in both list and dict formats
        if "building_notes" in prop and isinstance(prop["building_notes"], dict):
            facilities = prop["building_notes"].get("facilities", [])
            
            # Convert facilities to structured format
            structured_facilities = []
            
            if isinstance(facilities, list):
                # Handle list format (old format)
                for facility in facilities:
                    if isinstance(facility, str):
                        category = normalize_facility_key(facility)
                        structured_facilities.append({
                            "category": category,
                            "name": facility,
                            "distance_description": "nearby",
                            "additional_info": None
                        })
                        if category not in amenities:
                            amenities.append(category)
            
            elif isinstance(facilities, dict):
                # Handle dict format (new format)
                for key, value in facilities.items():
                    category = normalize_facility_key(key)
                    if isinstance(value, list):
                        for item in value:
                            structured_facilities.append({
                                "category": category,
                                "name": key,
                                "distance_description": item,
                                "additional_info": None
                            })
                    else:
                        structured_facilities.append({
                            "category": category,
                            "name": key,
                            "distance_description": str(value),
                            "additional_info": None
                        })
                    if category not in amenities:
                        amenities.append(category)
            
            # Update the facilities in the data
            prop["building_notes"]["facilities"] = structured_facilities
            logger.debug(f"Processed {len(structured_facilities)} facilities for {prop.get('name', 'Unknown')}")
        
        prop["amenities"] = list(set(amenities))  # Remove duplicates
        logger.debug(f"Unified amenities for {prop.get('name', 'Unknown')}: {len(amenities)} items")

        # Fix invalid floor
        if prop.get("floor") == "0F":
            logger.debug(f"Fixed floor '0F' to None for {prop.get('name', 'Unknown')}")
            prop["floor"] = None

        # Log if features is missing for Short-Term
        if "short_term" in json_file.lower() and "features" not in prop:
            logger.debug(f"Missing features field in Short-Term property: {prop.get('name', 'Unknown')}")

    return raw_data

def limit_properties_for_testing(properties: List[Property], property_type: str) -> List[Property]:
    """Limit the number of properties for testing purposes."""
    if not TEST_MODE:
        return properties
    
    logger.info(f"TEST MODE: Limiting {property_type} properties to {TEST_PROPERTIES_PER_TYPE}")
    return properties[:TEST_PROPERTIES_PER_TYPE]

# JSON files to process
json_files = [
    "data/json/rent_details_20250519.json",
    "data/json/buy_details_20250519.json",
    "data/json/short_term_details_20250519.json",
]

logger.info(f"Starting to index {len(json_files)} JSON files")

# Create Qdrant collection with indexes
try:
    if qdrant_client.collection_exists(COLLECTION_NAME):
        logger.info(f"Deleting existing collection {COLLECTION_NAME} to recreate with indexes")
        qdrant_client.delete_collection(COLLECTION_NAME)
    qdrant_client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
    )
    logger.info(f"Created Qdrant collection: {COLLECTION_NAME}")

    # Create keyword indexes for categorical fields
    keyword_fields = [
        "property_type",
        "type",
        "address.ward",
        "address.city",
        "address.postal_code",
        "unit.number",
        "unit.floor",
        "unit.layout",
        "unit.bedrooms",
        "building.structure",
        "building.id",
        "contract.type",
        "contract.length",
        "status",
        "amenities",
        "features.unit",
        "features.building",
        "nearest_stations[].name",
        "nearest_stations[].lines",
        "search_keywords",
        "building_notes.facilities[].category",
        "building_notes.facilities[].name"
    ]
    for field in keyword_fields:
        qdrant_client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name=field,
            field_schema=PayloadSchemaType.KEYWORD
        )

    # Create numeric indexes for range filtering
    numeric_fields = [
        "area.m2",
        "area.ft2",
        "area.price_per_m2",
        "area.price_per_ft2",
        "price.total",
        "price.monthly_total",
        "price.rent",
        "price.management_fee",
        "price.short_term_monthly_total",
        "price.short_term_rent",
        "price.short_term_management_fee",
        "building.year_built",
        "building.total_floors",
        "building.total_units",
        "unit.floor_number",
        "initial_costs.first_month_rent",
        "initial_costs.guarantor_service",
        "initial_costs.fire_insurance",
        "initial_costs.agency_fee",
        "initial_costs.estimated_total",
        "nearest_stations[].walk_time_min",
        "nearest_stations[].accessibility_score",
        "accessibility_metrics.overall_score",
        "accessibility_metrics.best_station_score",
        "accessibility_metrics.average_walk_time"
    ]
    for field in numeric_fields:
        qdrant_client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name=field,
            field_schema=PayloadSchemaType.FLOAT
        )

    # Create geo index for coordinates
    qdrant_client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="geo_location",
        field_schema=PayloadSchemaType.GEO
    )

    logger.info("Created keyword, numeric, and geo indexes for filtering fields")
except Exception as e:
    logger.error(f"Failed to create Qdrant collection or indexes: {e}")
    raise

# Process each JSON file
total_properties = 0
all_points = []
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

    # Determine property type from filename
    property_type = "Unknown"
    if "rent_details" in json_file:
        property_type = "Rent"
        logger.debug(f"Setting property type to Rent for {json_file}")
    elif "buy_details" in json_file:
        property_type = "Buy"
        logger.debug(f"Setting property type to Buy for {json_file}")
    elif "short_term_details" in json_file:
        property_type = "Short-Term"
        logger.debug(f"Setting property type to Short-Term for {json_file}")

    # Override property type in raw data
    for prop in raw_data["properties"]:
        prop["property_type"] = property_type
    logger.info(f"Overrode property type to {property_type} for all properties in {json_file}")

    # Validate with Pydantic and collect valid properties
    valid_properties = []
    for idx, prop in enumerate(raw_data["properties"]):
        try:
            valid_prop = Property(**prop)
            valid_properties.append(valid_prop)
        except Exception as prop_e:
            logger.error(f"Validation failed for property {idx+1} ({prop.get('name', 'Unknown')}) in {json_file}: {prop_e}")
            continue

    if not valid_properties:
        logger.error(f"No valid properties found in {json_file}")
        continue

    # Log property type counts before processing
    type_counts = defaultdict(int)
    for prop in valid_properties:
        type_counts[prop.property_type] += 1
    logger.info(f"Property type counts in {json_file}: {dict(type_counts)}")
    
    # Limit properties if in test mode
    properties = limit_properties_for_testing(valid_properties, property_type)
    total_properties += len(properties)
    logger.info(f"Validated {len(properties)} properties from {json_file}")
    
    # Log sample property data for each type
    if properties:
        sample_prop = properties[0]
        logger.debug(f"Sample property from {json_file}:")
        logger.debug(f"- ID: {sample_prop.id}")
        logger.debug(f"- Name: {sample_prop.name}")
        logger.debug(f"- Type: {sample_prop.property_type}")
        logger.debug(f"- Price: {sample_prop.price.model_dump()}")
        logger.debug(f"- Address: {sample_prop.address.model_dump()}")

    # Generate embeddings in batches
    for i in range(0, len(properties), OPENAI_BATCH_SIZE):
        batch = properties[i:i + OPENAI_BATCH_SIZE]
        logger.debug(f"Generating embeddings for batch {i//OPENAI_BATCH_SIZE + 1} of {len(batch)} properties in {json_file}")
        
        try:
            # Create texts for embedding
            texts = []
            for prop in batch:
                # Use computed fields for richer semantic descriptions
                text = prop.semantic_description + "\n"
                
                # Add property highlights
                highlights = prop.property_highlights
                text += f"Highlights: {', '.join(f'{k}: {v}' for k, v in highlights.items())}\n"
                
                # Add accessibility information
                if prop.nearest_stations:
                    metrics = prop.accessibility_metrics
                    text += f"Accessibility: Overall Score {metrics['overall_score']:.1f}, "
                    text += f"Best Station Score {metrics['best_station_score']:.1f}, "
                    text += f"Average Walk Time {metrics['average_walk_time']:.1f} minutes\n"
                
                # Add search keywords
                text += f"Keywords: {', '.join(prop.search_keywords)}"
                
                texts.append(text)

            # Get embeddings
            start_time = time.time()
            response = openai_client.embeddings.create(
                input=texts,
                model="text-embedding-ada-002"
            )
            embeddings = [item.embedding for item in response.data]
            logger.debug(f"Generated embeddings for batch in {time.time() - start_time:.2f} seconds")

            # Create points for Qdrant
            for prop, embedding in zip(batch, embeddings):
                try:
                    # Create payload for structured filtering
                    payload = {
                        # Basic Information
                        "id": prop.id,
                        "name": prop.name,
                        "property_type": prop.property_type,
                        "type": prop.type,
                        
                        # Location Information
                        "address": {
                            "full": prop.address.full,
                            "ward": prop.address.ward,
                            "city": prop.address.city,
                            "postal_code": prop.address.postal_code
                        },
                        "geo_location": {
                            "lat": prop.address.latitude,
                            "lon": prop.address.longitude
                        } if prop.address.latitude is not None and prop.address.longitude is not None else None,
                        
                        # Area and Price
                        "area": {
                            "m2": prop.area.m2,
                            "ft2": prop.area.ft2,
                            "price_per_m2": prop.area.price_per_m2,
                            "price_per_ft2": prop.area.price_per_ft2
                        },
                        
                        # Price Information
                        "price": {
                            "total": prop.price.total,
                            "monthly_total": prop.price.monthly_total,
                            "rent": prop.price.rent,
                            "management_fee": prop.price.management_fee,
                            "short_term_monthly_total": prop.price.short_term_monthly_total,
                            "short_term_rent": prop.price.short_term_rent,
                            "short_term_management_fee": prop.price.short_term_management_fee
                        },
                        
                        # Unit Information
                        "unit": {
                            "number": prop.unit.number if prop.unit else None,
                            "floor": prop.unit.floor if prop.unit else None,
                            "layout": prop.unit.layout if prop.unit else None,
                            "bedrooms": prop.unit.bedrooms if prop.unit else None,
                            "floor_number": parse_floor(prop.unit.floor if prop.unit else None)
                        },
                        
                        # Building Information
                        "building": {
                            "id": prop.building.id if prop.building else None,
                            "structure": prop.building.structure if prop.building else None,
                            "year_built": prop.building.year_built if prop.building else None,
                            "total_floors": prop.building.total_floors if prop.building else None,
                            "total_units": prop.building.total_units if prop.building else None
                        },
                        
                        # Contract Information
                        "contract": {
                            "type": prop.contract.type if prop.contract else None,
                            "length": prop.contract.length if prop.contract else None
                        },
                        
                        # Status and Features
                        "status": prop.status,
                        "amenities": prop.amenities or [],
                        "features": {
                            "unit": prop.features.unit if prop.features else [],
                            "building": prop.features.building if prop.features else []
                        },
                        
                        # Search Keywords and Highlights
                        "search_keywords": prop.search_keywords,
                        "property_highlights": prop.property_highlights,
                        
                        # Accessibility Information
                        "nearest_stations": [
                            {
                                "name": s.station_name,
                                "walk_time_min": s.walk_time_min,
                                "lines": [sl.name for sl in s.lines],
                                "accessibility_score": s.accessibility_score
                            }
                            for s in prop.nearest_stations
                        ],
                        "accessibility_metrics": prop.accessibility_metrics,
                        
                        # Additional Information
                        "building_notes": {
                            "summary": prop.building_notes.summary if prop.building_notes else None,
                            "description": prop.building_notes.description if prop.building_notes else None,
                            "facilities": [
                                {
                                    "category": f.category,
                                    "name": f.name,
                                    "distance": f.distance_description,
                                    "additional_info": f.additional_info
                                }
                                for f in (prop.building_notes.facilities if prop.building_notes else [])
                            ]
                        },
                        
                        # Images
                        "images": {
                            "main": prop.images.main,
                            "thumbnails": prop.images.thumbnails or [],
                            "floorplan": prop.images.floorplan
                        }
                    }
                    
                    # Log property type being added
                    logger.debug(f"Creating point for property {prop.id} of type {prop.property_type}")
                    
                    # Add point to batch
                    all_points.append(PointStruct(
                        id=int(prop.id),
                        vector=embedding,
                        payload=payload
                    ))
                except Exception as e:
                    logger.error(f"Failed to create point for property {prop.name} in {json_file}: {e}")
                    continue
                
        except Exception as e:
            logger.error(f"Failed to generate embeddings for batch {i//OPENAI_BATCH_SIZE + 1} in {json_file}: {e}")
            continue

# Index all points in Qdrant in batches
logger.info(f"Indexing {len(all_points)} points in Qdrant")

# Log property type distribution before indexing
type_counts = defaultdict(int)
for point in all_points:
    type_counts[point.payload["property_type"]] += 1
logger.info(f"Property type distribution before indexing: {dict(type_counts)}")

for i in range(0, len(all_points), QDRANT_BATCH_SIZE):
    batch = all_points[i:i + QDRANT_BATCH_SIZE]
    try:
        start_time = time.time()
        qdrant_client.upsert(
            collection_name=COLLECTION_NAME,
            points=batch
        )
        # Log property types in this batch
        batch_type_counts = defaultdict(int)
        for point in batch:
            batch_type_counts[point.payload["property_type"]] += 1
        logger.info(f"Indexed batch {i//QDRANT_BATCH_SIZE + 1} of {len(batch)} points in {time.time() - start_time:.2f} seconds. Types: {dict(batch_type_counts)}")
    except Exception as e:
        logger.error(f"Failed to index batch {i//QDRANT_BATCH_SIZE + 1}: {e}")

logger.info(f"Completed indexing {total_properties} properties in QdrantDB")