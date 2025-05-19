import json
import re
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

def parse_floor(floor: str) -> int:
    """Parse floor string (e.g., '2F' or '1F (of 5F)') to a numeric value."""
    if not floor:
        return 0
    # Extract numeric part (e.g., '2' from '2F' or '1F (of 5F)')
    match = re.match(r"(\d+)", floor)
    return int(match.group(1)) if match else 0

def extract_query_elements(query: str) -> QueryElements:
    """Use LLM to parse natural language query into structured elements."""
    prompt = """
    You are a real estate search assistant. Parse the following user query into structured elements for searching properties in Tokyo, Japan. Extract the following if mentioned:
    - Keywords for semantic search (general terms like "apartment", "modern", include query-specific terms like "cat")
    - Maximum monthly price (in JPY, as an integer, e.g., 200000 for ¥200,000)
    - Minimum area (in square meters, as a float)
    - Ward (e.g., "Minato-ku")
    - Pet-friendly requirement (true if pets like "cat" or "dog" are mentioned, else null)
    - Maximum walk time to a station (in minutes, as an integer)
    - Specific station name (e.g., "Omotesando Station")
    - Minimum year built (e.g., 2020 for "new" or "recent", use ≥2020 unless a specific year is mentioned)
    - Minimum floor (numeric, e.g., 2 for "2F" or "above 1F", to exclude 1F)
    - Maximum floor (numeric, e.g., 10 for "10F" or "high floors")
    - Contract length (e.g., "2 YearsStandard", or "short-term" for non-long-term)
    - Maximum management fee (in JPY, as an integer, e.g., 0 for no fee)
    - Maximum guarantor service fee (in JPY, as an integer, e.g., 0 for no fee)
    - Maximum fire insurance fee (in JPY, as an integer, e.g., 0 for no fee)
    - Japanese language required (true, false, or null if not mentioned)
    - Unit features (list of strings, e.g., ["Dishwasher", "Balcony"])
    - Building features (list of strings, e.g., ["Elevator", "Autolock"])
    - Train lines (list of strings, e.g., ["Odawara Line"])

    Return a JSON object. Set fields to null if not mentioned. For "new" apartments, assume min_year_built is 2020 unless specified. For pets, set pet_friendly to true if mentioned. For floors, convert to numeric values (e.g., "2F" to 2, "above 1F" to 2).

    Query: "{query}"

    Example outputs:
    1. Query: "I have a cat. I am looking for the new apartments for less than ¥200,000"
       {{
           "keywords": ["apartment", "new", "cat"],
           "max_price": 200000,
           "min_area_m2": null,
           "ward": null,
           "pet_friendly": true,
           "max_walk_time": null,
           "station_name": null,
           "min_year_built": 2020,
           "min_floor": null,
           "max_floor": null,
           "contract_length": null,
           "max_management_fee": null,
           "max_guarantor_service": null,
           "max_fire_insurance": null,
           "japanese_required": null,
           "unit_features": null,
           "building_features": null,
           "train_lines": null
       }}
    2. Query: "Pet-friendly apartments in Minato-ku on 2F or higher with no management fee"
       {{
           "keywords": ["apartment", "pet-friendly", "Minato-ku"],
           "max_price": null,
           "min_area_m2": null,
           "ward": "Minato-ku",
           "pet_friendly": true,
           "max_walk_time": null,
           "station_name": null,
           "min_year_built": null,
           "min_floor": 2,
           "max_floor": null,
           "contract_length": null,
           "max_management_fee": 0,
           "max_guarantor_service": null,
           "max_fire_insurance": null,
           "japanese_required": null,
           "unit_features": null,
           "building_features": null,
           "train_lines": null
       }}
    3. Query: "any apartments that are not on the 1F"
       {{
           "keywords": ["apartment"],
           "max_price": null,
           "min_area_m2": null,
           "ward": null,
           "pet_friendly": null,
           "max_walk_time": null,
           "station_name": null,
           "min_year_built": null,
           "min_floor": 2,
           "max_floor": null,
           "contract_length": null,
           "max_management_fee": null,
           "max_guarantor_service": null,
           "max_fire_insurance": null,
           "japanese_required": null,
           "unit_features": null,
           "building_features": null,
           "train_lines": null
       }}
    """
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt.format(query=query)},
                {"role": "user", "content": query}
            ],
            response_format={"type": "json_object"}
        )
        raw_elements = json.loads(response.choices[0].message.content)
        elements = QueryElements(**raw_elements)
        click.echo(f"Parsed QueryElements: {elements.model_dump()}")
        return elements
    except Exception as e:
        click.echo(f"Error parsing query with LLM: {e}")
        return QueryElements(keywords=[query], max_price=None, min_area_m2=None, ward=None, pet_friendly=None,
                            max_walk_time=None, station_name=None, min_year_built=None, min_floor=None,
                            max_floor=None, contract_length=None, max_management_fee=None,
                            max_guarantor_service=None, max_fire_insurance=None, japanese_required=None,
                            unit_features=None, building_features=None, train_lines=None)

def perform_hybrid_search(query: str) -> list:
    """Perform hybrid search combining semantic and structured filtering."""
    # Extract query elements
    elements = extract_query_elements(query)
    
    # Generate query embedding for semantic search
    try:
        response = openai_client.embeddings.create(
            input=query,
            model="text-embedding-ada-002"
        )
        query_embedding = response.data[0].embedding
    except Exception as e:
        click.echo(f"Error generating embedding: {e}")
        return []
    
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
    if elements.min_floor is not None:
        filters.append(
            FieldCondition(
                key="floor_number",
                range=Range(gte=elements.min_floor)
            )
        )
    if elements.max_floor is not None:
        filters.append(
            FieldCondition(
                key="floor_number",
                range=Range(lte=elements.max_floor)
            )
        )
    if elements.contract_length:
        filters.append(
            FieldCondition(
                key="contract_length",
                match=MatchValue(value=elements.contract_length)
            )
        )
    if elements.max_management_fee is not None:
        filters.append(
            FieldCondition(
                key="management_fee",
                range=Range(lte=elements.max_management_fee)
            )
        )
    if elements.max_guarantor_service is not None:
        filters.append(
            FieldCondition(
                key="guarantor_service",
                range=Range(lte=elements.max_guarantor_service)
            )
        )
    if elements.max_fire_insurance is not None:
        filters.append(
            FieldCondition(
                key="fire_insurance",
                range=Range(lte=elements.max_fire_insurance)
            )
        )
    if elements.japanese_required is not None:
        filters.append(
            FieldCondition(
                key="japanese_required",
                match=MatchValue(value=elements.japanese_required)
            )
        )
    if elements.unit_features:
        for feature in elements.unit_features:
            filters.append(
                FieldCondition(
                    key="unit_features",
                    match=MatchValue(value=feature)
                )
            )
    if elements.building_features:
        for feature in elements.building_features:
            filters.append(
                FieldCondition(
                    key="building_features",
                    match=MatchValue(value=feature)
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
    if elements.train_lines:
        for line in elements.train_lines:
            filters.append(
                FieldCondition(
                    key="nearest_stations[].lines",
                    match=MatchValue(value=line)
                )
            )
    
    # Perform search
    try:
        search_result = qdrant_client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_embedding,
            query_filter=Filter(must=filters) if filters else None,
            limit=10
        ).points
        return search_result
    except Exception as e:
        click.echo(f"Error performing search: {e}")
        return []

@click.command()
@click.argument("query")
def search(query):
    """CLI command to search properties."""
    results = perform_hybrid_search(query)
    if not results:
        click.echo("No results found.")
        # Try relaxed search with only semantic component
        click.echo("Trying relaxed search with semantic component only...")
        elements = QueryElements(keywords=[query], max_price=None, min_area_m2=None, ward=None, pet_friendly=None,
                                max_walk_time=None, station_name=None, min_year_built=None, min_floor=None,
                                max_floor=None, contract_length=None, max_management_fee=None,
                                max_guarantor_service=None, max_fire_insurance=None, japanese_required=None,
                                unit_features=None, building_features=None, train_lines=None)
        try:
            response = openai_client.embeddings.create(
                input=query,
                model="text-embedding-ada-002"
            )
            query_embedding = response.data[0].embedding
            search_result = qdrant_client.query_points(
                collection_name=COLLECTION_NAME,
                query=query_embedding,
                limit=10
            ).points
            if search_result:
                click.echo("Relaxed search found results:")
                for i, result in enumerate(search_result, 1):
                    payload = result.payload
                    click.echo(f"\nResult {i}:")
                    click.echo(f"Name: {payload['name']}")
                    click.echo(f"Address: {payload['address_full']}")
                    click.echo(f"Latitude: {payload['latitude']}")
                    click.echo(f"Longitude: {payload['longitude']}")
                    click.echo(f"Price: ¥{payload['monthly_total']}/month")
                    click.echo(f"Management Fee: ¥{payload['management_fee']}/month")
                    click.echo(f"Area: {payload['area_m2']} m²")
                    click.echo(f"Built: {payload['year_built']}")
                    click.echo(f"Floor: {payload['floor'] or 'N/A'}")
                    click.echo(f"Contract Length: {payload['contract_length'] or 'N/A'}")
                    click.echo(f"Guarantor Service: ¥{payload['guarantor_service']}")
                    click.echo(f"Fire Insurance: ¥{payload['fire_insurance'] or 'N/A'}")
                    click.echo(f"Japanese Required: {payload['japanese_required'] or 'N/A'}")
                    click.echo(f"Pet Friendly: {'Yes' if payload['pet_friendly'] else 'No'}")
                    click.echo(f"Unit Features: {', '.join(payload['unit_features'])}")
                    click.echo(f"Building Features: {', '.join(payload['building_features'])}")
                    click.echo(f"Stations: {', '.join([f'{s['name']} ({s['walk_time_min']} min, Lines: {', '.join(s['lines']) if s['lines'] else 'N/A'})' for s in payload['nearest_stations']])}")
                    click.echo(f"Images:")
                    click.echo(f"  Main: {payload['images']['main']}")
                    click.echo(f"  Floorplan: {payload['images']['floorplan']}")
                    click.echo(f"  Thumbnails: {', '.join(payload['images']['thumbnails'])}")
                    click.echo(f"Score: {result.score:.3f}")
            else:
                click.echo("No results found even with relaxed search.")
        except Exception as e:
            click.echo(f"Error in relaxed search: {e}")
        return
    
    for i, result in enumerate(results, 1):
        payload = result.payload
        click.echo(f"\nResult {i}:")
        click.echo(f"Name: {payload['name']}")
        click.echo(f"Address: {payload['address_full']}")
        click.echo(f"Latitude: {payload['latitude']}")
        click.echo(f"Longitude: {payload['longitude']}")
        click.echo(f"Price: ¥{payload['monthly_total']}/month")
        click.echo(f"Management Fee: ¥{payload['management_fee']}/month")
        click.echo(f"Area: {payload['area_m2']} m²")
        click.echo(f"Built: {payload['year_built']}")
        click.echo(f"Floor: {payload['floor'] or 'N/A'}")
        click.echo(f"Contract Length: {payload['contract_length'] or 'N/A'}")
        click.echo(f"Guarantor Service: ¥{payload['guarantor_service']}")
        click.echo(f"Fire Insurance: ¥{payload['fire_insurance'] or 'N/A'}")
        click.echo(f"Japanese Required: {payload['japanese_required'] or 'N/A'}")
        click.echo(f"Pet Friendly: {'Yes' if payload['pet_friendly'] else 'No'}")
        click.echo(f"Unit Features: {', '.join(payload['unit_features'])}")
        click.echo(f"Building Features: {', '.join(payload['building_features'])}")
        click.echo(f"Stations: {', '.join([f'{s['name']} ({s['walk_time_min']} min, Lines: {', '.join(s['lines']) if s['lines'] else 'N/A'})' for s in payload['nearest_stations']])}")
        click.echo(f"Images:")
        click.echo(f"  Main: {payload['images']['main']}")
        click.echo(f"  Floorplan: {payload['images']['floorplan']}")
        click.echo(f"  Thumbnails: {', '.join(payload['images']['thumbnails'])}")
        click.echo(f"Score: {result.score:.3f}")

if __name__ == "__main__":
    search()