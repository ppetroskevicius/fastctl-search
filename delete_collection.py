from qdrant_client import QdrantClient
import os
client = QdrantClient(url=os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY"))
client.delete_collection("real_estate")
print("Collection deleted")