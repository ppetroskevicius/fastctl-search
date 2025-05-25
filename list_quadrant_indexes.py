from qdrant_client import QdrantClient
from dotenv import load_dotenv
import os

load_dotenv()

# Initialize Qdrant client
qdrant_url = os.getenv("QDRANT_URL")
qdrant_api_key = os.getenv("QDRANT_API_KEY")
if not qdrant_url or not qdrant_api_key:
    print("Error: QDRANT_URL and QDRANT_API_KEY must be set in .env")
    exit(1)

client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
collection_name = "real_estate"

# Get collection info
try:
    collection_info = client.get_collection(collection_name)
    print(f"\nCollection '{collection_name}' exists.")
    print("Payload indexes:")
    if collection_info.payload_schema:
        for field, schema in collection_info.payload_schema.items():
            print(f"- {field}: {schema.data_type}")
    else:
        print("No payload indexes found.")
except Exception as e:
    print(f"Error retrieving collection info: {e}")