import os
import logging
import click
from typing import List, Optional
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue, Range
from openai import OpenAI
from models import PropertyType, Feature

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize clients
qdrant_url = os.getenv("QDRANT_URL")
qdrant_api_key = os.getenv("QDRANT_API_KEY")
openai_api_key = os.getenv("OPENAI_API_KEY")

if not qdrant_url or not qdrant_api_key or not openai_api_key:
    logger.error("QDRANT_URL, QDRANT_API_KEY, and OPENAI_API_KEY must be set in environment variables")
    raise ValueError("Missing required environment variables")

qdrant_client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
openai_client = OpenAI(api_key=openai_api_key)

# Collection name
COLLECTION_NAME = "real_estate"

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

def build_filter(
    property_types: Optional[List[str]] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_area: Optional[float] = None,
    max_area: Optional[float] = None,
    features: Optional[List[str]] = None
) -> Optional[Filter]:
    """Build Qdrant filter based on provided criteria."""
    must_conditions = []
    
    # Property type filter
    if property_types:
        valid_types = [pt.value for pt in PropertyType]
        property_types = [pt for pt in property_types if pt in valid_types]
        if property_types:
            must_conditions.append(
                FieldCondition(
                    key="property_type",
                    match=MatchValue(value=property_types[0]) if len(property_types) == 1 else {"any": property_types}
                )
            )
    
    # Price filter
    if min_price is not None or max_price is not None:
        price_conditions = []
        # Handle Rent/Short-Term (monthly_total) and Buy (total)
        for price_field in ["price.monthly_total", "price.total"]:
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
        range_condition = {}
        if min_area is not None:
            range_condition["gte"] = min_area
        if max_area is not None:
            range_condition["lte"] = max_area
        if range_condition:
            must_conditions.append(
                Range(**range_condition, key="area.m2")
            )
    
    # Feature filter
    if features:
        valid_features = [f.value for f in Feature]
        features = [f for f in features if f in valid_features]
        for feature in features:
            must_conditions.append(
                FieldCondition(
                    key="features.unit",
                    match=MatchValue(value=feature)
                )
            )
    
    return Filter(must=must_conditions) if must_conditions else None

def format_price(payload: dict) -> str:
    """Format price based on property type."""
    price_data = payload.get("price", {})
    if payload.get("property_type") == PropertyType.BUY.value:
        total = price_data.get("total")
        return f"{total:,} JPY (total)" if total else "Price not specified"
    else:
        monthly = price_data.get("monthly_total") or price_data.get("short_term_monthly_total")
        return f"{monthly:,} JPY/month" if monthly else "Price not specified"

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
@click.option("--limit", type=int, default=5, help="Number of results to return")
def search(query: str, property_type: List[str], min_price: float, max_price: float, min_area: float, max_area: float, feature: List[str], limit: int):
    """Perform a natural language search on real estate properties."""
    logger.info(f"Executing search with query: {query}")
    
    try:
        # Embed the query
        query_vector = embed_query(query)
        
        # Build filter
        query_filter = build_filter(
            property_types=property_type,
            min_price=min_price,
            max_price=max_price,
            min_area=min_area,
            max_area=max_area,
            features=feature
        )
        
        # Perform search
        results = qdrant_client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=limit
        )
        
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