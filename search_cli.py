import json
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue, Range
from openai import OpenAI
from models import QueryElements
from dotenv import load_dotenv
import os
import click

load_dotenv()

# Initialize clients
qdrant_client = QdrantClient("localhost", port=6333)
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
COLLECTION_NAME = "real_estate"

def extract_query_elements(query: str) -> QueryElements:
    """Use LLM to parse natural language query into structured elements."""
    prompt = """
    You are a real estate search assistant. Parse the following user query into structured elements for searching properties. Extract the following if mentioned:
    - Keywords for semantic search (e.g., general terms like "apartment", "modern")
    - Maximum monthly price (in JPY, as an integer)
    - Minimum area (in square meters, as a float)
    - Ward (e.g., "Minato-ku")
    - Pet-friendly requirement (true if mentioned, else null)
    - Maximum walk time to a station (in minutes, as an integer)
    - Specific station name (e.g., "Omotesando Station")
    - Minimum year built (e.g., 2020)
    
    Return the result as a JSON object. If a field is not mentioned, set it to null. For keywords, include relevant terms for semantic search.

    Query: "{query}"

    Example output:
    {{
        "keywords": ["apartment", "modern"],
        "max_price": 300000,
        "min_area_m2": 50.0,
        "ward": "Minato-ku",
        "pet_friendly": true,
        "max_walk_time": 10,
        "station_name": "Omotesando Station",
        "min_year_built": 2020
    }}
    """
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": prompt.format(query=query)},
            {"role": "user", "content": query}
        ],
        response_format={"type": "json_object"}
    )
    raw_elements = json.loads(response.choices[0].message.content)
    return QueryElements(**raw_elements)

def perform_hybrid_search(query: str) -> list:
    """Perform hybrid search combining semantic and structured filtering."""
    # Extract query elements
    elements = extract_query_elements(query)
    
    # Generate query embedding for semantic search
    response = openai_client.embeddings.create(
        input=query,
        model="text-embedding-ada-002"
    )
    query_embedding = response.data[0].embedding
    
    # Build structured filters
    filters = []
    if elements.max_price:
        filters.append(
            FieldCondition(
                key="monthly_total",
                range=Range(lte=elements.max_price)
            )
        )
    if elements.min_area_m2:
        filters.append(
            FieldCondition(
                key="area_m2",
                range=Range(gte=elements.min_area_m2)
            )
        )
    if elements.ward:
        filters.append(
            FieldCondition(
                key="ward",
                match=MatchValue(value=elements.ward)
            )
        )
    if elements.pet_friendly:
        filters.append(
            FieldCondition(
                key="pet_friendly",
                match=MatchValue(value=True)
            )
        )
    if elements.min_year_built:
        filters.append(
            FieldCondition(
                key="year_built",
                range=Range(gte=elements.min_year_built)
            )
        )
    if elements.station_name and elements.max_walk_time:
        filters.append(
            FieldCondition(
                key="nearest_stations[].name",
                match=MatchValue(value=elements.station_name)
            )
        )
        filters.append(
            FieldCondition(
                key="nearest_stations[].walk_time_min",
                range=Range(lte=elements.max_walk_time)
            )
        )
    
    # Perform search
    search_result = qdrant_client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_embedding,
        query_filter=Filter(must=filters) if filters else None,
        limit=10
    )
    
    return search_result

@click.command()
@click.argument("query")
def search(query):
    """CLI command to search properties."""
    results = perform_hybrid_search(query)
    if not results:
        click.echo("No results found.")
        return
    
    for i, result in enumerate(results, 1):
        payload = result.payload
        click.echo(f"\nResult {i}:")
        click.echo(f"Name: {payload['name']}")
        click.echo(f"Address: {payload['address_full']}")
        click.echo(f"Price: ¥{payload['monthly_total']}/month")
        click.echo(f"Area: {payload['area_m2']} m²")
        click.echo(f"Built: {payload['year_built']}")
        click.echo(f"Pet Friendly: {'Yes' if payload['pet_friendly'] else 'No'}")
        click.echo(f"Stations: {', '.join([f'{s['name']} ({s['walk_time_min']} min)' for s in payload['nearest_stations']])}")
        click.echo(f"Score: {result.score:.3f}")

if __name__ == "__main__":
    search()