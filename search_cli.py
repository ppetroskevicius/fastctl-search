
import click
from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue, Range, GeoBoundingBox
from openai import OpenAI
from models import QueryElements
from dotenv import load_dotenv
import os
import json
import time
from typing import List, Dict, Optional
from collections import defaultdict

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

def parse_floor(floor: str) -> Optional[int]:
    """Parse floor string (e.g., '2F') to a numeric value or None if invalid."""
    if not floor:
        return None
    match = re.match(r"(\d+)", floor)
    return int(match.group(1)) if match else None

def normalize_ward(ward: str) -> str:
    """Normalize ward for flexible matching (e.g., 'Shibuya-ku' -> 'Shibuya')."""
    if not ward:
        return ward
    ward = ward.lower().replace("-ku", "").strip()
    return ward.capitalize()

def extract_query_elements(query: str) -> QueryElements:
    """Extract structured query elements from a natural language query using LLM."""
    prompt = """
    You are a real estate search assistant. Parse the user's query into structured elements for filtering properties. The properties can be for rent, purchase (buy), or short-term rental. Extract the following fields, if mentioned, and return them in JSON format:

    - keywords: List of keywords or phrases describing the property (e.g., ["modern", "pet-friendly"]).
    - property_type: Type of property ("Rent", "Buy", "Short-Term", or null).
    - max_total_price: Maximum purchase price for Buy properties (integer, null if not specified).
    - max_monthly_price: Maximum monthly price for Rent or Short-Term properties (integer, null if not specified).
    - short_term_duration: Duration for Short-Term rentals (e.g., "1 month", "3 months", null if not specified).
    - min_area_m2: Minimum area in square meters (float, null if not specified).
    - ward: Specific ward or area in the city (string, null if not specified).
    - pet_friendly: Whether pets are allowed (boolean, null if not specified).
    - max_walk_time: Maximum walk time to a station in minutes (integer, null if not specified).
    - station_name: Specific station name (string, null if not specified).
    - train_lines: List of train line names (list of strings, null if not specified).
    - min_year_built: Minimum year the property was built (integer, null if not specified).
    - min_floor: Minimum floor (string, e.g., "2F", null if not specified).
    - max_floor: Maximum floor (string, e.g., "10F", null if not specified).
    - contract_length: Contract length for Rent (e.g., "2 years", null if not specified).
    - max_management_fee: Maximum management fee (integer, null if not specified).
    - max_guarantor_service: Maximum guarantor service fee (integer, null if not specified).
    - max_fire_insurance: Maximum fire insurance fee (integer, null if not specified).
    - japanese_required: Whether Japanese language is required (boolean, null if not specified).
    - amenities: List of specific amenities (e.g., ["autolock", "balcony"], null if not specified).
    - layout: Layout for Buy properties (e.g., "2LDK", null if not specified).
    - land_rights: Land rights for Buy properties (e.g., "Freehold", null if not specified).
    - status: Status for Buy properties (e.g., "Available", null if not specified).
    - building_id: Building identifier for multi-unit buildings (string, null if not specified).

    Examples:
    - Query: "modern apartment for rent in Shibuya under 200,000 yen per month, pet-friendly, near Shibuya station"
      Output: {
        "keywords": ["modern", "apartment"],
        "property_type": "Rent",
        "max_monthly_price": 200000,
        "ward": "Shibuya",
        "pet_friendly": true,
        "station_name": "Shibuya",
        "amenities": null,
        ...
      }
    - Query: "buy a 3LDK freehold apartment in Meguro, max 100 million yen"
      Output: {
        "keywords": ["apartment"],
        "property_type": "Buy",
        "max_total_price": 100000000,
        "ward": "Meguro",
        "layout": "3LDK",
        "land_rights": "Freehold",
        "amenities": null,
        ...
      }
    - Query: "short-term furnished apartment in Roppongi for 1 month"
      Output: {
        "keywords": ["furnished", "apartment"],
        "property_type": "Short-Term",
        "short_term_duration": "1 month",
        "ward": "Roppongi",
        "amenities": ["furnished"],
        ...
      }

    Query: {query}
    Output in JSON format:
    """
    try:
        start_time = time.time()
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": query}
            ],
            response_format={"type": "json_object"}
        )
        query_elements_json = json.loads(response.choices[0].message.content)
        logger.debug(f"Extracted query elements in {time.time() - start_time:.2f} seconds: {query_elements_json}")
        return QueryElements(**query_elements_json)
    except Exception as e:
        logger.error(f"Failed to extract query elements: {e}")
        return QueryElements()

def search_properties(query: str, limit: int = 10) -> List[Dict]:
    """Perform hybrid search (semantic + structured) in Qdrant."""
    # Extract query elements
    elements = extract_query_elements(query)
    
    # Generate query embedding for semantic search
    try:
        start_time = time.time()
        response = openai_client.embeddings.create(
            input=query,
            model="text-embedding-ada-002"
        )
        query_embedding = response.data[0].embedding
        logger.debug(f"Generated query embedding in {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Failed to generate query embedding: {e}")
        return []

    # Build Qdrant filters
    must_conditions = []
    if elements.property_type:
        must_conditions.append(FieldCondition(
            key="property_type",
            match=MatchValue(value=elements.property_type)
        ))
    if elements.max_total_price and elements.property_type == "Buy":
        must_conditions.append(FieldCondition(
            key="total",
            range=Range(lte=elements.max_total_price)
        ))
    if elements.max_monthly_price and elements.property_type in ["Rent", "Short-Term"]:
        must_conditions.append(FieldCondition(
            key="monthly_total",
            range=Range(lte=elements.max_monthly_price)
        ))
    if elements.short_term_duration and elements.property_type == "Short-Term":
        must_conditions.append(FieldCondition(
            key="short_term_duration",
            match=MatchValue(value=elements.short_term_duration)
        ))
    if elements.min_area_m2:
        must_conditions.append(FieldCondition(
            key="area_m2",
            range=Range(gte=elements.min_area_m2)
        ))
    if elements.ward:
        normalized_ward = normalize_ward(elements.ward)
        must_conditions.append(FieldCondition(
            key="ward",
            match=MatchValue(value=normalized_ward)
        ))
        logger.debug(f"Normalized ward filter: {elements.ward} -> {normalized_ward}")
    if elements.pet_friendly is not None:
        must_conditions.append(FieldCondition(
            key="pet_friendly",
            match=MatchValue(value=elements.pet_friendly)
        ))
    if elements.max_walk_time:
        for i in range(3):  # Check up to 3 nearest stations
            must_conditions.append(FieldCondition(
                key=f"nearest_stations[{i}].walk_time_min",
                range=Range(lte=elements.max_walk_time)
            ))
    if elements.station_name:
        must_conditions.append(FieldCondition(
            key="nearest_stations[].name",
            match=MatchValue(value=elements.station_name)
        ))
    if elements.train_lines:
        for line in elements.train_lines:
            must_conditions.append(FieldCondition(
                key="nearest_stations[].lines",
                match=MatchValue(value=line)
            ))
    if elements.min_year_built:
        must_conditions.append(FieldCondition(
            key="year_built",
            range=Range(gte=elements.min_year_built)
        ))
    if elements.min_floor:
        min_floor_num = parse_floor(elements.min_floor)
        if min_floor_num:
            must_conditions.append(FieldCondition(
                key="floor_number",
                range=Range(gte=min_floor_num)
            ))
    if elements.max_floor:
        max_floor_num = parse_floor(elements.max_floor)
        if max_floor_num:
            must_conditions.append(FieldCondition(
                key="floor_number",
                range=Range(lte=max_floor_num)
            ))
    if elements.contract_length and elements.property_type == "Rent":
        must_conditions.append(FieldCondition(
            key="contract_length",
            match=MatchValue(value=elements.contract_length)
        ))
    if elements.max_management_fee:
        must_conditions.append(FieldCondition(
            key="management_fee",
            range=Range(lte=elements.max_management_fee)
        ))
    if elements.max_guarantor_service:
        must_conditions.append(FieldCondition(
            key="guarantor_service",
            range=Range(lte=elements.max_guarantor_service)
        ))
    if elements.max_fire_insurance:
        must_conditions.append(FieldCondition(
            key="fire_insurance",
            range=Range(lte=elements.max_fire_insurance)
        ))
    if elements.japanese_required is not None:
        must_conditions.append(FieldCondition(
            key="japanese_required",
            match=MatchValue(value=elements.japanese_required)
        ))
    if elements.amenities:
        for amenity in elements.amenities:
            must_conditions.append(FieldCondition(
                key="amenities",
                match=MatchValue(value=amenity)
            ))
    if elements.layout and elements.property_type == "Buy":
        must_conditions.append(FieldCondition(
            key="layout",
            match=MatchValue(value=elements.layout)
        ))
    if elements.land_rights and elements.property_type == "Buy":
        must_conditions.append(FieldCondition(
            key="land_rights",
            match=MatchValue(value=elements.land_rights)
        ))
    if elements.status and elements.property_type == "Buy":
        must_conditions.append(FieldCondition(
            key="status",
            match=MatchValue(value=elements.status)
        ))
    if elements.building_id:
        must_conditions.append(FieldCondition(
            key="building_id",
            match=MatchValue(value=elements.building_id)
        ))

    # Perform hybrid search
    try:
        start_time = time.time()
        results = qdrant_client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_embedding,
            query_filter=Filter(must=must_conditions) if must_conditions else None,
            limit=limit,
            with_payload=True
        ).points
        logger.debug(f"Performed Qdrant search in {time.time() - start_time:.2f} seconds, found {len(results)} results, filters: {must_conditions}")
        
        # Log raw results for debugging
        logger.debug(f"Raw search results: {[r.payload for r in results]}")
        
        # Group results by building_id or coordinates for multi-unit buildings
        grouped_results = defaultdict(list)
        for result in results:
            building_key = result.payload.get("building_id") or f"{result.payload['latitude']}_{result.payload['longitude']}"
            grouped_results[building_key].append(result.payload)
        
        # Format results
        formatted_results = []
        for building_key, payloads in grouped_results.items():
            if len(payloads) > 1:
                # Multi-unit building
                formatted_results.append({
                    "building_key": building_key,
                    "property_type": payloads[0]["property_type"],
                    "units": [
                        {
                            "id": p["id"],
                            "name": p["name"],
                            "unit_number": p.get("unit_number"),
                            "price": p["total"] if p["property_type"] == "Buy" else p["monthly_total"] or p["short_term_monthly_total"],
                            "area_m2": p["area_m2"],
                            "floor": p["floor"],
                            "amenities": p["amenities"],
                            "address": p["address_full"],
                            "images": p["images"]
                        } for p in payloads
                    ],
                    "count": len(payloads)
                })
            else:
                # Single unit
                p = payloads[0]
                formatted_results.append({
                    "building_key": building_key,
                    "property_type": p["property_type"],
                    "units": [{
                        "id": p["id"],
                        "name": p["name"],
                        "unit_number": p.get("unit_number"),
                        "price": p["total"] if p["property_type"] == "Buy" else p["monthly_total"] or p["short_term_monthly_total"],
                        "area_m2": p["area_m2"],
                        "floor": p["floor"],
                        "amenities": p["amenities"],
                        "address": p["address_full"],
                        "images": p["images"]
                    }],
                    "count": 1
                })
        
        return formatted_results
    except Exception as e:
        logger.error(f"Failed to perform Qdrant search: {e}")
        return []

@click.command()
@click.argument("query", type=str)
@click.option("--limit", type=int, default=10, help="Maximum number of results to return")
def search(query: str, limit: int):
    """Search for real estate properties based on a natural language query."""
    logger.info(f"Executing search query: {query} with limit {limit}")
    results = search_properties(query, limit)
    
    if not results:
        click.echo("No results found.")
        return

    for result in results:
        click.echo(f"\nBuilding: {result['building_key']} ({result['count']} unit{'s' if result['count'] > 1 else ''}, Type: {result['property_type']})")
        for unit in result["units"]:
            price = f"¥{unit['price']:,}" if unit['price'] else "N/A"
            if result['property_type'] == "Buy":
                price += " (Purchase)"
            else:
                price += "/month"
            click.echo(f"- Unit: {unit['name']} (ID: {unit['id']})")
            if unit['unit_number']:
                click.echo(f"  Unit Number: {unit['unit_number']}")
            click.echo(f"  Price: {price}")
            click.echo(f"  Area: {unit['area_m2']} m2")
            click.echo(f"  Floor: {unit['floor'] or 'N/A'}")
            click.echo(f"  Amenities: {', '.join(unit['amenities']) if unit['amenities'] else 'None'}")
            click.echo(f"  Address: {unit['address']}")
            click.echo(f"  Main Image: {unit['images']['main']}")
            click.echo(f"  Floorplan: {unit['images']['floorplan']}")

if __name__ == "__main__":
    logger.add("search_cli.log", rotation="10 MB", level="INFO")
    search()
