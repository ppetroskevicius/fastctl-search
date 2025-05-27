# Vector/Semantic vs Keyword/Index Search

To recommend which data fields from the unified data model (defined in the consolidated schema and implemented in `models.py`) should be included in semantic search, payload indexes, or both for your real estate application, I'll analyze the fields based on their relevance to semantic search (via `query_vector`) and filtering (via `query_filter`) in the context of your Qdrant-based setup. Semantic search involves embedding text fields for vector similarity, while payload indexes optimize structured filtering. Some fields may be used in both, depending on their role in queries like those in `search_cli.py`.

### Analysis Approach
- **Unified Data Model**: Based on the `Property` model in `models.py` and the consolidated schema, which includes fields like `id`, `name`, `address`, `price`, `features`, etc., with `features` unifying `features` and `amenities`, and excluding `other_requirements` and `building_id`.
- **Semantic Search Fields**:
  - Text fields that contribute to natural language queries (e.g., "pet-friendly apartment in Minato").
  - Fields embedded in `index_properties.py` (e.g., `name`, `unit_notes`, `building_notes.summary`).
  - Fields with descriptive content for vector similarity.
- **Payload Index Fields**:
  - Structured fields used for filtering in `search_cli.py` (e.g., `property_type`, `area.m2`, `price.monthly_total`).
  - Fields likely to be filtered in future queries (e.g., `year_built`, `nearest_stations.walk_time_min`).
  - Scalar or enumerable fields (e.g., strings, numbers, lists of keywords).
- **Both Semantic Search and Indexes**:
  - Fields that are both searched semantically (via text embeddings) and filtered structurally (e.g., `features.unit` for "pet-friendly" queries and `--feature Pet Friendly` filters).
- **Collection Size**: Assuming ~3,000 properties (as per your previous question), which informs index overhead.
- **Use Case**: The `search_cli.py` supports queries like "luxury short-term rental" with filters (`--property-type`, `--min-price`, `--feature`), guiding field selection.

### Recommendations
- **Semantic Search**: Include text-rich fields that capture property descriptions, locations, or attributes relevant to natural language queries. These are embedded into vectors for similarity search.
- **Payload Indexes**: Index fields used for filtering to improve query performance, focusing on scalars and keyword lists. Avoid indexing fields only used in semantic search or rarely filtered.
- **Both**: Fields that are both embedded for semantic search and filtered structurally, ensuring they’re searchable and filterable efficiently.

### Table of Recommended Fields

Below is a table listing all fields from the unified data model (`Property` model in `models.py`), with recommendations for inclusion in semantic search, payload indexes, or both, along with justifications. The table is organized by top-level fields, with nested fields (e.g., `address.full`) listed under their parent.

| **Field**                           | **Semantic Search** | **Payload Index** | **Justification**                                                                 |
|-------------------------------------|---------------------|-------------------|-----------------------------------------------------------------------------------|
| **id**                              | No                  | No                | Unique identifier, not relevant for search or filtering, used as Qdrant point ID. |
| **url**                             | No                  | No                | URL for property listing, used for display/linking, not searched or filtered.     |
| **property_type**                   | Yes                 | Yes (keyword)     | String ("Rent", "Buy", "Short-Term"). Searched semantically (e.g., "short-term rental") and filtered (`--property-type`). Index for fast filtering. |
| **name**                            | Yes                 | No                | Descriptive text (e.g., "GrandStory Nishiazabu #303"). Embedded for semantic search (e.g., "luxury apartment"). Not filtered. |
| **address**                         |                     |                   | Nested object. Subfields analyzed separately.                                     |
| ├─ **address.full**                 | Yes                 | No                | Text (e.g., "2-20-11 Nishiazabu, Minato-ku, Tokyo"). Embedded for location queries (e.g., "Minato apartment"). Rarely filtered. |
| ├─ **address.latitude**             | No                  | Yes (float)       | Numeric coordinate. Not embedded, but indexed for potential geospatial filtering (future extension). |
| ├─ **address.longitude**            | No                  | Yes (float)       | Same as latitude, indexed for geospatial queries.                                 |
| **area**                            |                     |                   | Nested object. Subfields analyzed separately.                                     |
| ├─ **area.m2**                      | No                  | Yes (float)       | Numeric (e.g., 94.21). Filtered (`--min-area`, `--max-area`). Indexed for performance. Not embedded. |
| ├─ **area.ft2**                     | No                  | No                | Numeric, redundant with `m2` (convertible). Rarely filtered, not embedded.        |
| ├─ **area.price_per_m2**            | No                  | No                | Numeric, not used in current filters or search. Optional field, low priority.     |
| ├─ **area.price_per_ft2**           | No                  | No                | Same as `price_per_m2`, not used.                                                 |
| **type**                            | Yes                 | Yes (keyword)     | String (e.g., "Apartment", "House"). Searched (e.g., "house in Tokyo") and potentially filtered (future). Indexed for filtering. |
| **price**                           |                     |                   | Nested object. Subfields analyzed separately.                                     |
| ├─ **price.currency**               | No                  | No                | String ("JPY"), constant, not searched or filtered.                               |
| ├─ **price.total**                  | No                  | Yes (integer)     | Numeric (e.g., 123000000 for Buy). Filtered (`--min-price`, `--max-price`). Indexed. |
| ├─ **price.monthly_total**          | No                  | Yes (integer)     | Numeric (e.g., 700000 for Rent). Filtered (`--min-price`, `--max-price`). Indexed. |
| ├─ **price.rent**                   | No                  | No                | Numeric, redundant with `monthly_total` for filtering, not embedded.              |
| ├─ **price.management_fee**         | No                  | No                | Numeric, not currently filtered or searched, low priority.                        |
| ├─ **price.short_term_monthly_total** | No                | Yes (integer)     | Numeric (e.g., 820000 for Short-Term). Filtered (`--min-price`, `--max-price`). Indexed. |
| ├─ **price.short_term_rent**        | No                  | No                | Redundant with `short_term_monthly_total`, not used.                              |
| ├─ **price.short_term_management_fee** | No               | No                | Not filtered or searched, low priority.                                          |
| ├─ **price.long_term_duration**     | Yes                 | No                | Text (e.g., "3+ months"). Embedded for semantic search (e.g., "long-term rental"). Rarely filtered. |
| ├─ **price.short_term_duration**    | Yes                 | No                | Text (e.g., "Less than 3 months"). Embedded for search. Not filtered.             |
| **images**                          |                     |                   | Nested object. Subfields not searched or filtered (URLs for display).             |
| ├─ **images.main**                  | No                  | No                | URL, not searched or filtered.                                                   |
| ├─ **images.thumbnails**            | No                  | No                | List of URLs, not used in queries.                                               |
| ├─ **images.floorplan**             | No                  | No                | URL, not searched or filtered.                                                   |
| **nearest_stations**                |                     |                   | List of objects. Subfields analyzed separately.                                  |
| ├─ **nearest_stations.station_name** | Yes                | Yes (keyword)     | Text (e.g., "Omotesando Station"). Embedded for search (e.g., "near Omotesando"). Indexed for potential filtering. |
| ├─ **nearest_stations.walk_time_min** | No                | Yes (integer)     | Numeric (e.g., 9). Filtered in future extensions (e.g., proximity). Indexed. Not embedded. |
| ├─ **nearest_stations.lines**       |                     |                   | List of objects. Subfields analyzed separately.                                  |
| │  ├─ **lines.company**             | Yes                 | Yes (keyword)     | Text (e.g., "Tokyo Metro"). Embedded for search (e.g., "near Metro"). Indexed for filtering. |
| │  ├─ **lines.name**                | Yes                 | Yes (keyword)     | Text (e.g., "Chiyoda Line"). Embedded and indexed for line-specific queries.      |
| **unit_number**                     | Yes                 | No                | Text (e.g., "#303"). Embedded for search (e.g., "apartment #303"). Rarely filtered. |
| **floor**                           | Yes                 | Yes (keyword)     | Text (e.g., "3F"). Embedded for search (e.g., "high floor"). Indexed for potential filtering. |
| **contract**                        |                     |                   | Nested object. Subfields analyzed separately.                                    |
| ├─ **contract.length**              | Yes                 | Yes (keyword)     | Text (e.g., "2 YearsStandard"). Embedded for search (e.g., "flexible contract"). Indexed for filtering. |
| ├─ **contract.type**                | Yes                 | Yes (keyword)     | Text (e.g., "Standard"). Embedded and indexed for contract type queries.          |
| **year_built**                      | No                  | Yes (integer)     | Numeric (e.g., 2022). Filtered for age (future). Indexed. Not embedded.           |
| **initial_cost_estimate**           |                     |                   | Nested object. Subfields not typically searched or filtered.                      |
| ├─ **initial_cost_estimate.first_month_rent** | No        | No                | Numeric, redundant with `price.monthly_total`, not used.                          |
| ├─ **initial_cost_estimate.guarantor_service** | No       | No                | Numeric, not searched or filtered.                                               |
| ├─ **initial_cost_estimate.fire_insurance** | No         | No                | Numeric, not used in queries.                                                    |
| ├─ **initial_cost_estimate.agency_fee** | No           | No                | Numeric, not filtered or searched.                                               |
| ├─ **initial_cost_estimate.estimated_total** | No       | No                | Numeric, not used in queries.                                                    |
| **features**                        |                     |                   | Nested object. Subfields analyzed separately.                                    |
| ├─ **features.unit**                | Yes                 | Yes (keyword)     | List of strings (e.g., ["Pet Friendly"]). Embedded for search (e.g., "pet-friendly"). Indexed for `--feature` filters. |
| ├─ **features.building**            | Yes                 | Yes (keyword)     | List of strings (e.g., ["Autolock"]). Embedded for search. Indexed for potential filtering. |
| **unit_notes**                      | Yes                 | No                | Text (e.g., "Fully furnished luxury apartment"). Embedded for semantic search. Not filtered. |
| **unit_notes_amenities**            | Yes                 | No                | List of strings (e.g., ["Nespresso Machine"]). Embedded for search. Rarely filtered. |
| **bedrooms**                        | Yes                 | No                | Text (e.g., "Bedroom 1: 1 Queen bed"). Embedded for search (e.g., "two-bedroom"). Not filtered. |
| **balcony**                         | Yes                 | No                | Text (e.g., "Grab coffee or tea"). Embedded for search (e.g., "apartment with balcony"). Not filtered. |
| **building_notes**                  |                     |                   | Nested object. Subfields analyzed separately.                                    |
| ├─ **building_notes.summary**       | Yes                 | No                | Text (e.g., "Renovated and fully furnished"). Embedded for search. Not filtered.  |
| ├─ **building_notes.description**   | Yes                 | No                | Text (e.g., "All utilities included"). Embedded for search. Not filtered.         |
| ├─ **building_notes.facilities**    | Yes                 | No                | Object (key-value strings). Embedded for search (if non-empty). Not filtered.     |
| **layout**                          | Yes                 | Yes (keyword)     | Text (e.g., "3LDK"). Embedded for search (e.g., "three-bedroom"). Indexed for potential filtering. |
| **status**                          | Yes                 | Yes (keyword)     | Text (e.g., "Available"). Embedded for search (e.g., "available property"). Indexed for filtering (Buy). |
| **listing_id**                      | No                  | No                | Text, internal identifier, not searched or filtered.                             |
| **last_updated**                    | No                  | Yes (integer)     | Date (ISO format, stored as timestamp). Indexed for potential recency filtering. Not embedded. |
| **details**                         |                     |                   | Nested object. Subfields analyzed separately.                                    |
| ├─ **details.layout**               | Yes                 | Yes (keyword)     | Text (e.g., "3LDK"). Embedded and indexed, redundant with top-level `layout`.     |
| ├─ **details.balcony_direction**    | Yes                 | Yes (keyword)     | Text (e.g., "North-east"). Embedded for search (e.g., "north-facing"). Indexed for filtering. |
| ├─ **details.floor**                | Yes                 | Yes (keyword)     | Text (e.g., "26F"). Embedded and indexed, redundant with top-level `floor`.       |
| ├─ **details.land_rights**          | Yes                 | Yes (keyword)     | Text (e.g., "Freehold"). Embedded for search (e.g., "freehold property"). Indexed. |
| ├─ **details.transaction_type**     | Yes                 | Yes (keyword)     | Text (e.g., "Broker"). Embedded for search. Indexed for potential filtering.      |
| ├─ **details.management_fee**       | No                  | No                | Numeric, not currently filtered or searched.                                      |
| ├─ **details.repair_reserve_fund**  | No                  | No                | Numeric, not used in queries.                                                    |
| **building**                        |                     |                   | Nested object. Subfields analyzed separately.                                    |
| ├─ **building.structure**           | Yes                 | Yes (keyword)     | Text (e.g., "Reinforced Concrete"). Embedded for search (e.g., "concrete building"). Indexed. |
| ├─ **building.year_built**          | No                  | Yes (integer)     | Numeric, same as top-level `year_built`. Indexed for filtering. Not embedded.     |
| ├─ **building.total_floors**        | No                  | Yes (integer)     | Numeric (e.g., 29). Indexed for potential filtering (e.g., high-rise). Not embedded. |
| ├─ **building.total_units**         | No                  | No                | Numeric, not currently filtered or searched.                                      |
| **additional_info**                 | Yes                 | No                | Text (e.g., "A redefinition of premium living"). Embedded for search. Not filtered. |

### Explanation of Recommendations
- **Semantic Search**:
  - **Included**: Text fields (`name`, `address.full`, `unit_notes`, `building_notes.summary`, `additional_info`) for descriptive matching.
  - **Included (Enums)**: Fields like `property_type`, `type`, `features.unit`, `contract.length` are embedded as text for semantic queries (e.g., "short-term" matches `property_type="Short-Term"`).
  - **Excluded**: Numeric fields (`area.m2`, `price.total`) and URLs (`images.main`) lack semantic content. Fields like `id`, `listing_id` are non-descriptive.
  - **Rationale**: Matches `index_properties.py`’s `get_text_for_embedding`, which embeds `name`, `unit_notes`, `building_notes`, `additional_info`, `contract.length`. Extended to include fields like `features.unit`, `address.full` for broader query coverage.

- **Payload Indexes**:
  - **Included**: Fields used in `search_cli.py` filters (`property_type`, `area.m2`, `price.monthly_total`, `price.total`, `features.unit`) and likely future filters (`year_built`, `nearest_stations.walk_time_min`, `type`, `contract.length`, `status`).
  - **Index Types**:
    - **Keyword**: Strings or lists (`property_type`, `features.unit`, `type`, `nearest_stations.station_name`, `contract.length`).
    - **Float**: `area.m2`, `address.latitude`, `address.longitude`.
    - **Integer**: `price.monthly_total`, `price.total`, `year_built`, `nearest_stations.walk_time_min`, `building.total_floors`, `last_updated` (as timestamp).
  - **Excluded**: Fields not filtered (`url`, `images.main`, `unit_notes`, `initial_cost_estimate.*`) or redundant (`details.layout`, `details.floor` overlap with top-level `layout`, `floor`).
  - **Rationale**: Optimizes filtering performance for ~3,000 properties, with minimal overhead (~3–5 MB storage, ~15–30 seconds indexing time).

- **Both Semantic Search and Indexes**:
  - Fields like `property_type`, `features.unit`, `contract.length`, `type`, `nearest_stations.station_name`, `floor`, `layout`, `status`, `building.structure` are:
    - **Embedded**: Included in vectors for queries (e.g., "pet-friendly apartment" matches `features.unit=["Pet Friendly"]`).
    - **Indexed**: Filtered via `query_filter` (e.g., `--feature Pet Friendly`, `--property-type Rent`).
  - **Rationale**: These fields are both descriptive (for semantic matching) and structured (for exact filtering), making them dual-purpose.

