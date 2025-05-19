import json
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from openai import OpenAI
from models import Properties, Property
from dotenv import load_dotenv
import os

load_dotenv()

# Initialize clients
qdrant_client = QdrantClient("localhost", port=6333)
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Collection name
COLLECTION_NAME = "real_estate"

# Load JSON data
with open("rent_details_20250519.json", "r") as f:
    raw_data = json.load(f)

# Validate with Pydantic
properties_data = Properties(**raw_data)
properties = [Property(**item["property"]) for item in properties_data.properties]

# Create Qdrant collection if it doesn't exist
if not qdrant_client.collection_exists(COLLECTION_NAME):
    qdrant_client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=1536, distance=Distance.COSINE),  # OpenAI text-embedding-ada-002 size
    )

# Generate embeddings and index
for prop in properties:
    # Create text for embedding (combine relevant fields)
    text = f"{prop.name}, {prop.address.full}, Type: {prop.type}, Area: {prop.area.m2} m2, "
    text += f"Price: ¥{prop.price.monthly_total}/month, Built: {prop.year_built}, "
    text += f"Features: {', '.join(prop.features.unit + prop.features.building)}, "
    text += f"Stations: {', '.join([s.station_name + f' ({s.walk_time_min} min)' for s in prop.nearest_stations])}"
    
    # Get embedding
    response = openai_client.embeddings.create(
        input=text,
        model="text-embedding-ada-002"
    )
    embedding = response.data[0].embedding
    
    # Create payload for structured filtering
    payload = {
        "id": prop.id,
        "name": prop.name,
        "address_full": prop.address.full,
        "ward": prop.address.full.split(", ")[1],  # Extract ward (e.g., "Minato-ku")
        "monthly_total": prop.price.monthly_total,
        "area_m2": prop.area.m2,
        "year_built": prop.year_built,
        "pet_friendly": "Pet Friendly(+1 mo deposit)" in prop.features.unit,
        "nearest_stations": [
            {"name": s.station_name, "walk_time_min": s.walk_time_min}
            for s in prop.nearest_stations
        ]
    }
    
    # Index in Qdrant
    qdrant_client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(
                id=int(prop.id),
                vector=embedding,
                payload=payload
            )
        ]
    )

print(f"Indexed {len(properties)} properties in QdrantDB")