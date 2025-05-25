from loguru import logger
import os
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter
from dotenv import load_dotenv
import click

load_dotenv()

def get_qdrant_client():
    """Initialize Qdrant Cloud client."""
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")
    if not qdrant_url or not qdrant_api_key:
        logger.error("QDRANT_URL and QDRANT_API_KEY must be set in environment variables")
        raise ValueError("QDRANT_URL and QDRANT_API_KEY must be set in environment variables")
    return QdrantClient(url=qdrant_url, api_key=qdrant_api_key)

def list_collections():
    """List all collections and their record counts."""
    try:
        client = get_qdrant_client()
        collections = client.get_collections().collections
        if not collections:
            logger.info("No collections found in Qdrant Cloud")
            return
        logger.info("Listing all collections and record counts:")
        for collection in collections:
            count = client.count(collection_name=collection.name).count
            logger.info(f"Collection: {collection.name}, Records: {count}")
    except Exception as e:
        logger.error(f"Failed to list collections: {e}")

def delete_all_records(client, collection_name):
    """Delete all records in a specified collection."""
    try:
        if not client.collection_exists(collection_name):
            logger.warning(f"Collection {collection_name} does not exist")
            return
        client.delete(
            collection_name=collection_name,
            points_selector=Filter(must=[])  # Empty filter matches all points
        )
        logger.info(f"Deleted all records in collection: {collection_name}")
    except Exception as e:
        logger.error(f"Failed to delete records in {collection_name}: {e}")

def delete_records_by_ids(client, collection_name, ids):
    """Delete records by a list of IDs."""
    try:
        if not client.collection_exists(collection_name):
            logger.warning(f"Collection {collection_name} does not exist")
            return
        client.delete(
            collection_name=collection_name,
            points_selector=ids
        )
        logger.info(f"Deleted {len(ids)} records from collection: {collection_name}")
    except Exception as e:
        logger.error(f"Failed to delete records from {collection_name}: {e}")

def delete_all_collections():
    """Delete all records in all collections."""
    try:
        client = get_qdrant_client()
        collections = client.get_collections().collections
        if not collections:
            logger.info("No collections to delete")
            return
        for collection in collections:
            delete_all_records(client, collection.name)
    except Exception as e:
        logger.error(f"Failed to delete all collections: {e}")

@click.group()
def cli():
    """Qdrant Cloud utility for managing collections in a real estate search application.

    This tool connects to Qdrant Cloud using QDRANT_URL and QDRANT_API_KEY environment variables.
    It provides commands to list collections, count records, and delete records (all or by IDs).

    Sample use cases:
    - List all collections and their record counts:
      $ python qdrant_utils.py list
    - Delete all records in the 'real_estate' collection to reload new production data:
      $ python qdrant_utils.py delete-collection real_estate
    - Delete specific property IDs (e.g., outdated test data):
      $ python qdrant_utils.py delete-ids real_estate 200001 200002
    - Delete all records across all collections for a full reset:
      $ python qdrant_utils.py delete-all

    Environment variables:
    - QDRANT_URL: Your Qdrant Cloud cluster URL (e.g., https://your-cluster-id.qdrant.cloud:6333)
    - QDRANT_API_KEY: Your Qdrant Cloud API key
    """
    pass

@cli.command()
def list():
    """List all collections and their record counts.

    Example:
    $ python qdrant_utils.py list
    Output:
      INFO: Listing all collections and record counts:
      INFO: Collection: real_estate, Records: 15
    """
    list_collections()

@cli.command()
@click.argument("collection_name")
def delete_collection(collection_name):
    """Delete all records in a specified collection.

    Args:
        collection_name: Name of the collection (e.g., real_estate)

    Example:
    $ python qdrant_utils.py delete-collection real_estate
    Prompt: Are you sure you want to delete all records in real_estate? (y/n):
    Output (after entering 'y'):
      INFO: Deleted all records in collection: real_estate
    """
    confirm = input(f"Are you sure you want to delete all records in {collection_name}? (y/n): ").strip().lower()
    if confirm == 'y':
        client = get_qdrant_client()
        delete_all_records(client, collection_name)
    else:
        logger.info("Deletion cancelled")

@cli.command()
@click.argument("collection_name")
@click.argument("ids", nargs=-1, type=int)
def delete_ids(collection_name, ids):
    """Delete records by IDs in a specified collection.

    Args:
        collection_name: Name of the collection (e.g., real_estate)
        ids: One or more integer IDs to delete (e.g., 200001 200002)

    Example:
    $ python qdrant_utils.py delete-ids real_estate 200001 200002
    Prompt: Are you sure you want to delete 2 records from real_estate? (y/n):
    Output (after entering 'y'):
      INFO: Deleted 2 records from collection: real_estate
    """
    if not ids:
        logger.warning("No IDs provided for deletion")
        return
    confirm = input(f"Are you sure you want to delete {len(ids)} records from {collection_name}? (y/n): ").strip().lower()
    if confirm == 'y':
        client = get_qdrant_client()
        delete_records_by_ids(client, collection_name, list(ids))
    else:
        logger.info("Deletion cancelled")

@cli.command()
def delete_all():
    """Delete all records in all collections.

    Example:
    $ python qdrant_utils.py delete-all
    Prompt: Are you sure you want to delete all records in all collections? (y/n):
    Output (after entering 'y'):
      INFO: Deleted all records in collection: real_estate
      INFO: Deleted all records in collection: other_collection
    """
    confirm = input("Are you sure you want to delete all records in all collections? (y/n): ").strip().lower()
    if confirm == 'y':
        delete_all_collections()
    else:
        logger.info("Deletion cancelled")

if __name__ == "__main__":
    cli()