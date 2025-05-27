import os
import json
import logging
from typing import Optional, List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.http.models import VectorParams, Distance, PointStruct, PayloadSchemaType
from openai import OpenAI
from models import Property, Feature, PropertyType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration
TEST_MODE = True
TEST_PROPERTIES_PER_TYPE = 20
QDRANT_BATCH_SIZE = 100
OPENAI_BATCH_SIZE = 50

# Initialize clients
qdrant_url = os.getenv("QDRANT_URL")
qdrant_api_key = os.getenv("QDRANT_API_KEY")
if not qdrant_url or not qdrant_api_key:
    logger.error("QDRANT_URL and QDRANT_API_KEY must be set in environment variables")
    raise ValueError("QDRANT_URL and QDRANT_API_KEY must be set in environment variables")

qdrant_client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
if not os.getenv("OPENAI_API_KEY"):
    logger.error("OPENAI_API_KEY must be set in environment variables")
    raise ValueError("OPENAI_API_KEY must be set in environment variables")

# Collection name
COLLECTION_NAME = "real_estate"

# JSON files to process
json_files = [
    "data/json/rent_details_20250519.json",
    "data/json/buy_details_20250519.json",
    "data/json/short_term_details_20250519.json",
]

def create_collection():
    """Create or recreate Qdrant collection with specified configuration and payload indexes."""
    try:
        if qdrant_client.collection_exists(COLLECTION_NAME):
            logger.info(f"Deleting existing collection {COLLECTION_NAME}")
            qdrant_client.delete_collection(COLLECTION_NAME)
        qdrant_client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
        )
        # Add payload indexes for frequently filtered fields
        payload_indexes = [
            ("property_type", "keyword"),
            ("area.m2", "float"),
            ("price.monthly_total", "integer"),
            ("price.total", "integer"),
            ("price.short_term_monthly_total", "integer"),
            ("features.unit", "keyword"),
            ("features.building", "keyword"),
            ("type", "keyword"),
            ("nearest_stations.station_name", "keyword"),
            ("nearest_stations.walk_time_min", "integer"),
            ("nearest_stations.lines.company", "keyword"),
            ("nearest_stations.lines.name", "keyword"),
            ("floor", "keyword"),
            ("contract.length", "keyword"),
            ("contract.type", "keyword"),
            ("year_built", "integer"),
            ("address.latitude", "float"),
            ("address.longitude", "float"),
            ("layout", "keyword"),
            ("status", "keyword"),
            ("last_updated", "keyword"),
            ("details.layout", "keyword"),
            ("details.floor", "keyword"),
            ("details.balcony_direction", "keyword"),
            ("details.land_rights", "keyword"),
            ("details.transaction_type", "keyword"),
            ("building.total_floors", "integer"),
            ("building.structure", "keyword"),
        ]
        for field_name, field_type in payload_indexes:
            qdrant_client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name=field_name,
                field_schema=field_type
            )
            logger.info(f"Created {field_type} index on {field_name}")

        # Create geo index for coordinates
        qdrant_client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="geo_location",
            field_schema=PayloadSchemaType.GEO
        )
        logger.info("Created geo index on geo_location")

        logger.info(f"Created Qdrant collection: {COLLECTION_NAME}")
    except Exception as e:
        logger.error(f"Failed to create Qdrant collection: {e}")
        raise

def load_json_file(file_path: str) -> List[Dict[str, Any]]:
    """Load JSON file and return list of properties."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data.get("properties"), list):
            logger.error(f"Invalid JSON format in {file_path}: 'properties' must be a list")
            raise ValueError("Invalid JSON format: 'properties' must be a list")
        return data["properties"]
    except Exception as e:
        logger.error(f"Failed to load JSON file {file_path}: {e}")
        raise

def normalize_features(data: Dict[str, Any]) -> Dict[str, List[str]]:
    """Normalize features and amenities into a unified Features structure."""
    features = {"unit": [], "building": []}
    
    # Handle rent/short-term features
    if "features" in data:
        if "unit" in data["features"]:
            for feature in data["features"]["unit"]:
                if feature.startswith("Pet Friendly"):
                    features["unit"].append(Feature.PET_FRIENDLY.value)
                elif feature in Feature.__members__.values():
                    features["unit"].append(feature)
        if "building" in data["features"]:
            features["building"] = data["features"]["building"]
    
    # Handle buy amenities
    if "amenities" in data:
        for amenity in data["amenities"]:
            if amenity == "Pet Negotiable":
                features["unit"].append(Feature.PET_FRIENDLY.value)
            elif amenity in ["Autolock", "Delivery Box", "Earthquake Resistance", "Gym", "Security"]:
                features["building"].append(amenity)
            elif amenity in Feature.__members__.values():
                features["unit"].append(amenity)
    
    return features

def normalize_agency_fee(fee: Any) -> Optional[int]:
    """Convert agency_fee to integer or None."""
    if fee is None:
        return None
    try:
        return int(fee)
    except (ValueError, TypeError):
        logger.warning(f"Invalid agency_fee format: {fee}, setting to None")
        return None

def preprocess_property(data: Dict[str, Any], property_type: str) -> Dict[str, Any]:
    """Preprocess raw property data to match Pydantic model."""
    processed = data.copy()
    processed["property_type"] = property_type
    
    # Normalize features/amenities
    if "features" in processed or "amenities" in processed:
        processed["features"] = normalize_features(processed)
        processed.pop("amenities", None)
    
    # Normalize agency_fee
    if "initial_cost_estimate" in processed and processed["initial_cost_estimate"]:
        processed["initial_cost_estimate"] = processed["initial_cost_estimate"].copy()
        processed["initial_cost_estimate"]["agency_fee"] = normalize_agency_fee(
            processed["initial_cost_estimate"].get("agency_fee")
        )
    
    # Convert last_updated to datetime if present
    if "last_updated" in processed and processed["last_updated"]:
        try:
            processed["last_updated"] = processed["last_updated"]
        except ValueError:
            logger.warning(f"Invalid date format for last_updated: {processed['last_updated']}")
            processed["last_updated"] = None
    
    return processed

def validate_property(data: Dict[str, Any]) -> Property:
    """Validate and convert raw data to Pydantic Property model."""
    try:
        return Property(**data)
    except Exception as e:
        logger.error(f"Validation failed for property ID {data.get('id', 'unknown')}: {e}")
        raise

def get_text_for_embedding(property: Property) -> str:
    """Generate text for embedding using computed fields."""
    parts = [
        property.semantic_description,
        " ".join(property.search_keywords) if property.search_keywords else "",
    ]
    return " ".join(filter(None, parts)).strip()

def embed_texts(texts: List[str]) -> List[List[float]]:
    """Generate embeddings using OpenAI."""
    try:
        response = openai_client.embeddings.create(
            model="text-embedding-ada-002",
            input=texts
        )
        return [data.embedding for data in response.data]
    except Exception as e:
        logger.error(f"Failed to generate embeddings: {e}")
        raise

def index_properties():
    """Index properties from JSON files into Qdrant."""
    create_collection()
    
    for file_path in json_files:
        # Determine property type from file name
        if "rent_details" in file_path:
            property_type = PropertyType.RENT.value
        elif "buy_details" in file_path:
            property_type = PropertyType.BUY.value
        elif "short_term_details" in file_path:
            property_type = PropertyType.SHORT_TERM.value
        else:
            logger.warning(f"Unknown property type for file: {file_path}")
            continue
        
        logger.info(f"Processing file: {file_path} ({property_type})")
        
        # Load JSON data
        properties_data = load_json_file(file_path)
        
        # Apply test mode limit
        if TEST_MODE:
            properties_data = properties_data[:TEST_PROPERTIES_PER_TYPE]
        
        points = []
        text_batch = []
        property_batch = []
        
        for i, raw_data in enumerate(properties_data):
            try:
                # Preprocess and validate
                processed_data = preprocess_property(raw_data, property_type)
                property = validate_property(processed_data)
                
                # Prepare text for embedding
                text = get_text_for_embedding(property)
                text_batch.append(text)
                property_batch.append(property)
                
                # Process embeddings in batches
                if len(text_batch) >= OPENAI_BATCH_SIZE or i == len(properties_data) - 1:
                    logger.info(f"Generating embeddings for batch of {len(text_batch)} properties")
                    embeddings = embed_texts(text_batch)
                    
                    # Create Qdrant points
                    for prop, embedding in zip(property_batch, embeddings):
                        payload = prop.model_dump(exclude_none=True)
                        point = PointStruct(
                            id=prop.id,
                            vector=embedding,
                            payload=payload
                        )
                        points.append(point)
                    
                    text_batch = []
                    property_batch = []
                
                # Upsert to Qdrant in batches
                if len(points) >= QDRANT_BATCH_SIZE or i == len(properties_data) - 1:
                    logger.info(f"Upserting {len(points)} points to Qdrant")
                    qdrant_client.upsert(
                        collection_name=COLLECTION_NAME,
                        points=points
                    )
                    points = []
                
            except Exception as e:
                logger.error(f"Failed to process property ID {raw_data.get('id', 'unknown')}: {e}")
                continue
        
        logger.info(f"Completed processing {file_path}: {len(properties_data)} properties")

if __name__ == "__main__":
    try:
        index_properties()
        logger.info("Indexing completed successfully")
    except Exception as e:
        logger.error(f"Indexing failed: {e}")
        raise