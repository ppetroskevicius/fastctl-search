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

load_dotenv()

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
OPENAI_BATCH_SIZE = 10  # Number of texts per OpenAI embedding request
QDRANT_BATCH_SIZE = 100  # Number of points per Qdrant upsert request

def parse_floor(floor: str) -> Optional[int]:
    """Parse floor string (e.g., '2F' or '1F (of 5F)') to a numeric value or None if invalid."""
    if not floor or floor == "0F":
        return None
    match = re.match(r"(\d+)", floor)
    return int(match.group(1)) if match else None

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

    # Create keyword indexes for filtering
    for field in [
        "ward",
        "contract_length",
        "contract_type",
        "nearest_stations[].name",
        "nearest_stations[].lines",
        "property_type",
        "building_id",
        "layout",
        "land_rights",
        "status",
        "short_term_duration",
        "amenities",
    ]:
        qdrant_client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name=field,
            field_schema=PayloadSchemaType.KEYWORD
        )
    logger.info("Created keyword indexes for filtering fields")
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

    # Validate with Pydantic
    try:
        properties_data = Properties(**raw_data)
        properties = properties_data.properties
        total_properties += len(properties)
        logger.info(f"Validated {len(properties)} properties from {json_file}")
    except Exception as e:
        logger.error(f"Failed to validate properties in {json_file}: {e}")
        continue

    # Generate embeddings in batches
    for i in range(0, len(properties), OPENAI_BATCH_SIZE):
        batch = properties[i:i + OPENAI_BATCH_SIZE]
        logger.debug(f"Generating embeddings for batch {i//OPENAI_BATCH_SIZE + 1} of {len(batch)} properties in {json_file}")
        
        try:
            # Create texts for embedding
            texts = []
            for prop in batch:
                text = f"{prop.name}, {prop.address.full}, Type: {prop.type}, Property Type: {prop.property_type}, "
                text += f"Area: {prop.area.m2} m2, "
                if prop.property_type == "Buy":
                    text += f"Price: ¥{prop.price.total or 'N/A'}, "
                else:
                    text += f"Price: ¥{prop.price.monthly_total or prop.price.short_term_monthly_total or 'N/A'}/month, "
                text += f"Built: {prop.year_built or 'N/A'}, Floor: {prop.floor or 'N/A'}, "
                text += f"Amenities: {', '.join(prop.amenities) if prop.amenities else 'None'}, "
                if prop.building_notes:
                    text += f"Building Notes: {prop.building_notes.summary}, {prop.building_notes.description}, "
                if prop.additional_info:
                    text += f"Additional Info: {prop.additional_info}, "
                text += f"Stations: {', '.join([f'{s.station_name} ({s.walk_time_min} min, Lines: {', '.join(sl.name for sl in s.lines) if s.lines else 'N/A'})' for s in prop.nearest_stations])}"
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
                        "id": prop.id,
                        "name": prop.name,
                        "address_full": prop.address.full,
                        "ward": prop.address.full.split(", ")[1] if ", " in prop.address.full else "",
                        "latitude": prop.address.latitude,
                        "longitude": prop.address.longitude,
                        "property_type": prop.property_type,
                        "monthly_total": prop.price.monthly_total,
                        "total": prop.price.total,
                        "management_fee": prop.price.management_fee,
                        "short_term_monthly_total": prop.price.short_term_monthly_total,
                        "short_term_duration": prop.price.short_term_duration,
                        "area_m2": prop.area.m2,
                        "year_built": prop.year_built,
                        "floor": prop.floor,
                        "floor_number": parse_floor(prop.floor),
                        "contract_length": prop.contract.length if prop.contract else None,
                        "contract_type": prop.contract.type if prop.contract else None,
                        "guarantor_service": prop.initial_cost_estimate.guarantor_service if prop.initial_cost_estimate else None,
                        "fire_insurance": prop.initial_cost_estimate.fire_insurance if prop.initial_cost_estimate else None,
                        "japanese_required": prop.other_requirements.japanese_required if prop.other_requirements else None,
                        "pet_friendly": any("Pet Friendly" in amenity or "Pet Negotiable" in amenity for amenity in prop.amenities),
                        "amenities": prop.amenities,
                        "building_id": prop.building_id,
                        "layout": prop.layout,
                        "land_rights": prop.details.land_rights if prop.details else None,
                        "status": prop.status,
                        "images": {
                            "main": prop.images.main,
                            "thumbnails": prop.images.thumbnails or [],
                            "floorplan": prop.images.floorplan
                        },
                        "nearest_stations": [
                            {
                                "name": s.station_name,
                                "walk_time_min": s.walk_time_min,
                                "lines": [sl.name for sl in s.lines]
                            }
                            for s in prop.nearest_stations
                        ]
                    }
                    
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
for i in range(0, len(all_points), QDRANT_BATCH_SIZE):
    batch = all_points[i:i + QDRANT_BATCH_SIZE]
    try:
        start_time = time.time()
        qdrant_client.upsert(
            collection_name=COLLECTION_NAME,
            points=batch
        )
        logger.info(f"Indexed batch {i//QDRANT_BATCH_SIZE + 1} of {len(batch)} points in {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Failed to index batch {i//QDRANT_BATCH_SIZE + 1}: {e}")

logger.info(f"Completed indexing {total_properties} properties in QdrantDB")