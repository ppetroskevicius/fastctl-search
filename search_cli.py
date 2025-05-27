import os
import json
import requests
from typing import List, Optional, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue, Range, GeoRadius
from openai import OpenAI
from models import PropertyType, Feature, PropertyCategory, ContractType, Status, LineCompany, LineName
import click
from loguru import logger

# Configure logging
logger.remove()
logger.add(
    sink=lambda msg: print(msg, end=""),
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}",
    level="INFO"
)

# Initialize clients
qdrant_url = os.getenv("QDRANT_URL")
qdrant_api_key = os.getenv("QDRANT_API_KEY")
openai_api_key = os.getenv("OPENAI_API_KEY")
google_maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY")

if not qdrant_url or not qdrant_api_key or not openai_api_key:
    logger.error("QDRANT_URL, QDRANT_API_KEY, and OPENAI_API_KEY must be set in environment variables")
    raise ValueError("Missing required environment variables")
if not google_maps_api_key:
    logger.warning("GOOGLE_MAPS_API_KEY not set; geo search will be limited")

qdrant_client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
openai_client = OpenAI(api_key=openai_api_key)

# Collection name
COLLECTION_NAME = "real_estate"

def geocode_location(location: str) -> Optional[Dict[str, float]]:
    """Geocode a location using Google Maps API."""
    if not google_maps_api_key:
        logger.warning("Google Maps API key missing; skipping geocoding")
        return None
    try:
        response = requests.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={"address": f"{location}, Tokyo, Japan", "key": google_maps_api_key}
        )
        response.raise_for_status()
        data = response.json()
        if data["status"] != "OK" or not data.get("results"):
            logger.warning(f"No geocoding results for location: {location}, status={data['status']}")
            return None
        location_data = data["results"][0]["geometry"]["location"]
        logger.debug(f"Google Maps geocoding successful for location '{location}': lat={location_data['lat']}, lon={location_data['lng']}")
        return {"lat": location_data["lat"], "lon": location_data["lng"]}
    except Exception as e:
        logger.error(f"Google Maps geocoding error for location {location}: {e}")
        return None

def embed_query(text: str) -> List[float]:
    """Generate embedding for the query text using OpenAI."""
    try:
        response = openai_client.embeddings.create(
            model="text-embedding-ada-002",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Failed to embed query: {e}")
        raise

def extract_keywords(query: str) -> Dict[str, Any]:
    """Extract indexed keywords and geo search parameters from the query using an LLM."""
    valid_values = {
        "property_type": [pt.value for pt in PropertyType],
        "type": [pc.value for pc in PropertyCategory],
        "features.unit": [f.value for f in Feature],
        "features.building": ["Autolock", "Parcel Locker", "Bicycle Storage", "On-site Garbage Room"],
        "address.ward": ["Minato-ku", "Shibuya-ku", "Bunkyo-ku", "Setagaya-ku", "Arakawa-ku", "Edogawa-ku", "Naka-ku", "Shinjuku-ku"],
        "address.city": ["Tokyo", "Yokohama", "Kanagawa"],
        "contract.length": ["2 YearsStandard", "AskMonthly", "Flexible", "1 YearStandard", "AskFixed"],
        "contract.type": [ct.value for ct in ContractType],
        "status": [s.value for s in Status],
        "layout": ["3LDK", "2 BR", "Studio", "1K", "2LDK"],
        "nearest_stations.station_name": ["Omotesando Station", "Shibuya Station", "Sengoku Station", "Chitose Funabashi Station", "Hiroo Station"],
        "nearest_stations.lines.company": [lc.value for lc in LineCompany],
        "nearest_stations.lines.name": [ln.value for ln in LineName],
    }
    
    prompt = f"""
You are an assistant that extracts keywords and geo search parameters from a natural language query for a real estate search system in Tokyo, Japan. The query is: "{query}".

Extract values for the following fields, matching the provided valid options or inferring from the query. Return a JSON dictionary with only the fields that have matches. Use lists for fields that allow multiple values (e.g., features.unit). For numeric fields, extract ranges if mentioned (e.g., "under 500,000" → {{"max": 500000}}). For geo search, extract the location name (e.g., "Shibuya") and walking distance in meters (e.g., "within 10 minutes" → 800 meters, assuming 80 meters/minute).

Fields and Valid Values:
- property_type (string): {', '.join(valid_values['property_type'])}
- type (string): {', '.join(valid_values['type'])}
- features.unit (list of strings): {', '.join(valid_values['features.unit'])}
- features.building (list of strings): {', '.join(valid_values['features.building'])}
- address.ward (string): {', '.join(valid_values['address.ward'])}
- address.city (string): {', '.join(valid_values['address.city'])}
- contract.length (string): {', '.join(valid_values['contract.length'])}
- contract.type (string): {', '.join(valid_values['contract.type'])}
- status (string): {', '.join(valid_values['status'])}
- layout (string): {', '.join(valid_values['layout'])}
- nearest_stations.station_name (string): {', '.join(valid_values['nearest_stations.station_name'])}
- price.monthly_total (numeric range): e.g., {{"min": 100000, "max": 500000}}
- price.total (numeric range): e.g., {{"min": 50000000, "max": 200000000}}
- area.m2 (numeric range): e.g., {{"min": 50, "max": 100}}
- geo_location (string): e.g., "Shibuya", "Omotesando"
- geo_distance_meters (number): e.g., 800 (default to 800 if "walking distance" mentioned)

Example:
Query: "apartments within 10 minutes walk from Shibuya"
Output:
{{
  "type": "Apartment",
  "geo_location": "Shibuya",
  "geo_distance_meters": 800
}}

Query: "pet-friendly short-term apartment in Minato under 300,000 JPY near Omotesando"
Output:
{{
  "property_type": "Short-Term",
  "type": "Apartment",
  "features.unit": ["Pet Friendly"],
  "address.ward": "Minato-ku",
  "price.monthly_total": {{"max": 300000}},
  "geo_location": "Omotesando",
  "geo_distance_meters": 800
}}

Return the JSON dictionary for the query: "{query}"
"""
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        keywords = json.loads(response.choices[0].message.content)
        return keywords
    except Exception as e:
        logger.error(f"Failed to extract keywords: {e}")
        return {}


def build_filter(
    property_types: Optional[List[str]] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_area: Optional[float] = None,
    max_area: Optional[float] = None,
    features: Optional[List[str]] = None,
    llm_keywords: Dict[str, Any] = None,
    location: Optional[str] = None,
    max_distance_meters: Optional[float] = None
) -> Optional[Filter]:
    must_conditions = []
    geo_filter = None

    llm_keywords = llm_keywords or {}

    # Merge LLM keywords with CLI options (CLI takes precedence)
    property_types = property_types or llm_keywords.get("property_type", [])
    if isinstance(property_types, str):
        property_types = [property_types]

    features = features or llm_keywords.get("features.unit", [])
    min_price = min_price or (llm_keywords.get("price.monthly_total", {}).get("min") or llm_keywords.get("price.total", {}).get("min"))
    max_price = max_price or (llm_keywords.get("price.monthly_total", {}).get("max") or llm_keywords.get("price.total", {}).get("max"))
    min_area = min_area or llm_keywords.get("area.m2", {}).get("min")
    max_area = max_area or llm_keywords.get("area.m2", {}).get("max")
    location = location or llm_keywords.get("geo_location")
    max_distance_meters = max_distance_meters or llm_keywords.get("geo_distance_meters", 800)  # Default to 800m (10 min walk)

    # Property type filter
    if property_types:
        valid_types = [pt.value for pt in PropertyType]
        property_types = [pt for pt in property_types if pt in valid_types]
        if property_types:
            logger.debug(f"Filtering property_type: {property_types}")
            must_conditions.append(
                FieldCondition(
                    key="property_type",
                    match=MatchValue(value=property_types[0]) if len(property_types) == 1 else {"any": property_types}
                )
            )

    # Price filter
    if min_price is not None or max_price is not None:
        logger.debug(f"Filtering price: min={min_price}, max={max_price}")
        price_conditions = []
        for price_field in ["price.monthly_total", "price.total", "price.short_term_monthly_total"]:
            range_condition = {}
            if min_price is not None:
                range_condition["gte"] = min_price
            if max_price is not None:
                range_condition["lte"] = max_price
            if range_condition:
                price_conditions.append(
                    Range(**range_condition, key=price_field)
                )
        if price_conditions:
            must_conditions.append({"should": price_conditions})

    # Area filter
    if min_area is not None or max_area is not None:
        logger.debug(f"Filtering area: min={min_area}, max={max_area}")
        range_condition = {}
        if min_area is not None:
            range_condition["gte"] = min_area
        if max_area is not None:
            range_condition["lte"] = max_area
        if range_condition:
            must_conditions.append(
                Range(**range_condition, key="area.m2")
            )

    # Feature filter (unit)
    if features:
        valid_features = [f.value for f in Feature]
        features = [f for f in features if f in valid_features]
        for feature in features:
            logger.debug(f"Filtering feature: {feature}")
            must_conditions.append(
                FieldCondition(
                    key="features.unit",
                    match=MatchValue(value=feature)
                )
            )

    # LLM-derived indexed fields
    indexed_fields = [
        "type", "features.building", "contract.length", "contract.type", "status",
        "layout", "details.layout", "details.balcony_direction", "details.land_rights",
        "details.transaction_type", "building.structure", "nearest_stations.station_name",
        "address.ward", "address.city"
    ]
    for field, value in llm_keywords.items():
        if field in ["property_type", "features.unit", "price.monthly_total", "price.total", "area.m2", "geo_location", "geo_distance_meters"]:
            continue  # Already handled
        if field in indexed_fields:
            try:
                if isinstance(value, list):
                    for v in value:
                        logger.debug(f"Filtering {field}: {v}")
                        must_conditions.append(
                            FieldCondition(key=field, match=MatchValue(value=v))
                        )
                else:
                    logger.debug(f"Filtering {field}: {value}")
                    must_conditions.append(
                        FieldCondition(key=field, match=MatchValue(value=value))
                    )
            except Exception as e:
                logger.warning(f"Skipping filter for {field}: {e}")
                continue

    # Geo filter as a FieldCondition with geo_radius param!
    if location:
        coords = geocode_location(location)
        logger.info(f"Geocoded location for '{location}': {coords}")
        if coords:
            must_conditions.append(
                FieldCondition(
                    key="geo_location",
                    geo_radius={
                        "center": {"lat": coords["lat"], "lon": coords["lon"]},
                        "radius": max_distance_meters
                    }
                )
            )
        else:
            logger.warning(f"Falling back to station name match due to missing geocode for {location}")
            must_conditions.append(
                FieldCondition(
                    key="nearest_stations.station_name",
                    match=MatchValue(value=f"{location} Station")
                )
            )

    if must_conditions:
        return Filter(must=must_conditions)
    else:
        return None




def format_price(payload: dict) -> str:
    """Format price based on property type."""
    price_data = payload.get("price", {})
    if payload.get("property_type") == PropertyType.BUY.value:
        total = price_data.get("total")
        return f"{total:,} JPY (total)" if total is not None else "Price not specified"
    else:
        monthly = price_data.get("monthly_total") or price_data.get("short_term_monthly_total")
        return f"{monthly:,} JPY/month" if monthly is not None else "Price not specified"

def display_result(result) -> None:
    """Display a single search result."""
    payload = result.payload
    print(f"\nProperty: {payload.get('name', 'Unknown')}")
    print(f"Address: {payload.get('address', {}).get('full', 'Unknown')}")
    print(f"Price: {format_price(payload)}")
    print(f"Area: {payload.get('area', {}).get('m2', 'Unknown')} m²")
    print("Features (Unit):", ", ".join(payload.get('features', {}).get('unit', [])) or "None")
    print("Features (Building):", ", ".join(payload.get('features', {}).get('building', [])) or "None")
    print(f"Relevance Score: {result.score:.4f}")

@click.group()
def cli():
    """CLI for searching real estate properties."""
    pass

@cli.command()
@click.argument("query")
@click.option("--property-type", multiple=True, type=click.Choice([pt.value for pt in PropertyType]), help="Filter by property type")
@click.option("--min-price", type=float, help="Minimum price (JPY)")
@click.option("--max-price", type=float, help="Maximum price (JPY)")
@click.option("--min-area", type=float, help="Minimum area (m²)")
@click.option("--max-area", type=float, help="Maximum area (m²)")
@click.option("--feature", multiple=True, type=click.Choice([f.value for f in Feature]), help="Filter by feature")
@click.option("--location", type=str, help="Reference location for geo search (e.g., Shibuya)")
@click.option("--max-distance-meters", type=float, default=800, help="Maximum walking distance in meters (default: 800)")
@click.option("--limit", type=int, default=5, help="Number of results to return")
def search(query: str, property_type: List[str], min_price: float, max_price: float, min_area: float, max_area: float, feature: List[str], location: str, max_distance_meters: float, limit: int):
    """Perform a natural language search on real estate properties."""
    logger.info(f"Executing search with query: {query}")
    
    try:
        # Extract keywords using LLM
        llm_keywords = extract_keywords(query)
        logger.info(f"Extracted keywords: {llm_keywords}")
        
        # Embed the query
        query_vector = embed_query(query)
        
        # Build filter
        query_filter = build_filter(
            property_types=property_type,
            min_price=min_price,
            max_price=max_price,
            min_area=min_area,
            max_area=max_area,
            features=feature,
            llm_keywords=llm_keywords,
            location=location,
            max_distance_meters=max_distance_meters
        )
        
        # Perform search
        results = qdrant_client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            query_filter=query_filter,
            limit=limit
        ).points
        
        # Display results
        if not results:
            print("No results found.")
            return
        
        print(f"\nFound {len(results)} results for query: '{query}'")
        for result in results:
            display_result(result)
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        print(f"Error: {e}")

if __name__ == "__main__":
    cli()