# Data fields usage in semantic and structured search

## Analysis of Property Fields

Below, I evaluate each field from the `property` object:

1. **id**: `"177020"`
   - **Use**: Structured search (payload for result retrieval).
   - **Reason**: Stored in `payload.id` for unique identification but not used in filters or embeddings.

2. **name**: `"GrandStory Nishiazabu #303"`
   - **Use**: Semantic search.
   - **Reason**: Included in embedding text (`text = f"{prop.name}, ..."`) for queries like "apartments in Nishiazabu." Not filtered structurally.

3. **unit_number**: `"#303"`
   - **Use**: Neither (stored in payload for display).
   - **Reason**: Stored in `payload.unit_number` (implicitly via `name`) but not queried.

4. **building_id**: `"160694"`
   - **Use**: Neither (stored in payload for reference).
   - **Reason**: Administrative field, not used in search.

5. **address**:
   - **full**: `"2-20-11 Nishiazabu, Minato-ku, Tokyo"`
     - **Use**: Semantic and structured search.
     - **Reason**: Included in embedding text for semantic queries (e.g., "Minato-ku apartments"). `payload.ward` (extracted as "Minato-ku") is filtered in structured search (`ward` filter).
   - **latitude**: `35.6617691`
     - **Use**: Structured search (output only).
     - **Reason**: Stored in `payload.latitude` for map display in results, not filtered.
   - **longitude**: `139.7191087`
     - **Use**: Structured search (output only).
     - **Reason**: Stored in `payload.longitude` for map display, not filtered.

6. **area**:
   - **m2**: `94.21`
     - **Use**: Semantic and structured search.
     - **Reason**: Included in embedding text (`Area: {prop.area.m2} m2`) for queries like "spacious apartments." Filtered via `payload.area_m2` (`min_area_m2`).
   - **ft2**: `1014.0`
     - **Use**: Neither.
     - **Reason**: Redundant with `m2`, not used in Japan-focused queries.
   - **price_per_m2**: `7430`
     - **Use**: Neither (potential for structured).
     - **Reason**: Not currently used but could be filtered for cost-efficiency queries.
   - **price_per_ft2**: `690`
     - **Use**: Neither.
     - **Reason**: Redundant with `price_per_m2`.

7. **type**: `"Apartment"`
   - **Use**: Semantic search.
   - **Reason**: Included in embedding text (`Type: {prop.type}`) for queries like "apartments." Not filtered structurally but could be.

8. **floor**: `"3F  (of 0F)"`
   - **Use**: Semantic search.
   - **Reason**: Included in embedding text (`Floor: {prop.floor or 'N/A'}`) for queries like "high-floor apartments." Stored in `payload.floor` for display.

9. **floor_number** (derived from `floor`):
   - **Use**: Structured search.
   - **Reason**: Derived via `parse_floor` in `index_properties.py` and stored in `payload.floor_number`. Filtered for `min_floor` and `max_floor` (e.g., `floor_number >= 2`).

10. **contract**:
    - **length**: `"2 YearsStandard"`
      - **Use**: Structured search.
      - **Reason**: Stored in `payload.contract_length` and filtered for `contract_length` (e.g., "short-term").
    - **type**: `"Standard"`
      - **Use**: Structured search.
      - **Reason**: Stored in `payload.contract_type` and could be filtered, though not currently used in `QueryElements`.

11. **year_built**: `2022`
    - **Use**: Semantic and structured search.
    - **Reason**: Included in embedding text (`Built: {prop.year_built}`) for "new apartments." Filtered via `payload.year_built` (`min_year_built`).

12. **price**:
    - **monthly_total**: `700000`
      - **Use**: Semantic and structured search.
      - **Reason**: Included in embedding text (`Price: ¥{prop.price.monthly_total}/month`) for "affordable" queries. Filtered via `payload.monthly_total` (`max_price`).
    - **rent**: `680000`
      - **Use**: Neither (potential for structured).
      - **Reason**: Redundant with `monthly_total`, not currently used.
    - **management_fee**: `20000`
      - **Use**: Structured search.
      - **Reason**: Stored in `payload.management_fee` and filtered for `max_management_fee` (e.g., 0 for no fee).
    - **currency**: `"JPY"`
      - **Use**: Neither.
      - **Reason**: Always JPY, not queried.

13. **initial_cost_estimate**:
    - **first_month_rent**: `700000`
      - **Use**: Neither (potential for structured).
      - **Reason**: Not currently used but could be filtered.
    - **guarantor_service**: `350000`
      - **Use**: Structured search.
      - **Reason**: Stored in `payload.guarantor_service` and filtered for `max_guarantor_service` (e.g., 0).
    - **fire_insurance**: `23000`
      - **Use**: Structured search.
      - **Reason**: Stored in `payload.fire_insurance` and filtered for `max_fire_insurance` (e.g., 0).
    - **agency_fee**: `680000`
      - **Use**: Neither (potential for structured).
      - **Reason**: Not currently used but could be filtered.
    - **estimated_total**: `1821000`
      - **Use**: Neither (potential for structured).
      - **Reason**: Not currently used but could be filtered for total initial cost.

14. **requirements**:
    - **japanese_required**: `null` (or `true` in some cases)
      - **Use**: Structured search.
      - **Reason**: Stored in `payload.japanese_required` and filtered for `japanese_required` (e.g., `false` for non-Japanese speakers).
    - **note**: `null` (or text in some cases)
      - **Use**: Neither (potential for semantic).
      - **Reason**: Not used but could be included in embedding if descriptive.

15. **features**:
    - **unit**: `["Pet Friendly(+1 mo deposit)", "Intercom", ...]`
      - **Use**: Semantic and structured search.
      - **Reason**: Included in embedding text (`Features: {', '.join(prop.features.unit + ...)}`) for queries like "pet-friendly." `payload.unit_features` is filtered for `unit_features`, and `pet_friendly` is derived for filtering.
    - **building**: `["Autolock", "Parcel Locker"]`
      - **Use**: Semantic and structured search.
      - **Reason**: Included in embedding text and filtered via `payload.building_features` for `building_features`.

16. **images**:
    - **main**, **thumbnails**, **floorplan**: URLs
      - **Use**: Structured search (output only).
      - **Reason**: Stored in `payload.images` for result visualization, not filtered or embedded.

17. **unit_notes**: `null`
    - **Use**: Neither (potential for semantic).
    - **Reason**: Not populated but could be included in embedding if descriptive.

18. **unit_notes_amenities**: `[]`
    - **Use**: Neither (potential for semantic).
    - **Reason**: Empty but could be included in embedding if populated.

19. **bedrooms**: `null`
    - **Use**: Neither (potential for structured).
    - **Reason**: Not populated but could be filtered if data is added.

20. **balcony**: `null`
    - **Use**: Neither (potential for structured).
    - **Reason**: Not populated but could be filtered if data is added.

21. **nearest_stations**:
    - **station_name**: `"Omotesando Station"`, `"Nogizaka Station"`
      - **Use**: Semantic and structured search.
      - **Reason**: Included in embedding text (`Stations: {s.station_name} ...`) for "near Omotesando" queries. Filtered via `payload.nearest_stations[].name` for `station_name`.
    - **walk_time_min**: `9`, `14`
      - **Use**: Structured search.
      - **Reason**: Filtered via `payload.nearest_stations[].walk_time_min` for `max_walk_time`.
    - **lines**: `[]`
      - **Use**: Semantic and structured search.
      - **Reason**: Included in embedding text (if populated) for queries like "near Odawara Line." Filtered via `payload.nearest_stations[].lines` for `train_lines`.

---

## Field Usage in Hybrid Search

Below is the updated table, including an example natural language semantic search query for each field. The queries are designed to work with the current system and demonstrate both semantic and structured search components.

| **Field**                          | **Semantic Search** | **Structured Search** | **Example Query**                                                                 | **Reason / Notes**                                                                 |
|------------------------------------|---------------------|-----------------------|----------------------------------------------------------------------------------|-----------------------------------------------------------------------------------|
| `id`                               | No                  | Yes (payload)         | "Show me the property with ID 177020"                                            | Used for retrieval, not queried directly; query unlikely in practice.              |
| `name`                             | Yes                 | No                    | "Apartments in Nishiazabu"                                                       | In embedding for location/branding; matches "Nishiazabu" in `name`.               |
| `unit_number`                      | No                  | No                    | "Apartment unit #303 in Minato-ku"                                               | Display only; rarely queried, included in `name` for display.                     |
| `building_id`                      | No                  | No                    | "Properties in building 160694"                                                  | Administrative; not queried, unlikely in user search.                             |
| `address.full`                     | Yes                 | Yes                   | "Apartments in Minato-ku"                                                        | In embedding for semantic match; `ward` ("Minato-ku") filtered structurally.      |
| `address.latitude`                 | No                  | Yes (output)          | "Properties near Shibuya Station within 1 km"                                     | In payload for map display; query implies geospatial filter (not implemented).    |
| `address.longitude`                | No                  | Yes (output)          | "Properties near Shibuya Station within 1 km"                                     | Same as `latitude`.                                                              |
| `area.m2`                          | Yes                 | Yes                   | "Spacious apartments over 50 square meters"                                      | In embedding for "spacious"; filtered for `min_area_m2 >= 50`.                    |
| `area.ft2`                         | No                  | No                    | "Apartments over 500 square feet"                                                | Redundant with `m2`; query unlikely in Japan.                                    |
| `area.price_per_m2`                | No                  | Potential             | "Cost-effective apartments under ¥6000 per square meter"                         | Could filter `price_per_m2`; not currently used.                                 |
| `area.price_per_ft2`               | No                  | No                    | "Cheap apartments under ¥600 per square foot"                                    | Redundant with `price_per_m2`; query unlikely.                                   |
| `type`                             | Yes                 | Potential             | "Apartments in Tokyo"                                                            | In embedding for "apartment"; could filter `type` if implemented.                 |
| `floor`                            | Yes                 | No                    | "High-floor apartments in Setagaya-ku"                                           | In embedding for "high-floor"; display only in payload.                          |
| `floor_number` (derived)           | No                  | Yes                   | "Apartments not on the first floor"                                              | Filtered for `min_floor >= 2`; derived from `floor`.                             |
| `contract.length`                  | No                  | Yes                   | "Short-term lease apartments"                                                    | Filtered for `contract_length` (e.g., "short-term").                             |
| `contract.type`                    | No                  | Potential             | "Standard contract apartments"                                                   | In payload; could filter `contract_type` if added to `QueryElements`.            |
| `year_built`                       | Yes                 | Yes                   | "New apartments built after 2020"                                                | In embedding for "new"; filtered for `min_year_built >= 2020`.                   |
| `price.monthly_total`              | Yes                 | Yes                   | "Affordable apartments under ¥200,000"                                           | In embedding for "affordable"; filtered for `max_price <= 200000`.               |
| `price.rent`                       | No                  | Potential             | "Apartments with base rent under ¥150,000"                                       | Redundant with `monthly_total`; could be filtered.                               |
| `price.management_fee`             | No                  | Yes                   | "Apartments with no management fee"                                              | Filtered for `max_management_fee = 0`.                                          |
| `price.currency`                   | No                  | No                    | "Apartments priced in JPY"                                                       | Always JPY; query irrelevant.                                                   |
| `initial_cost_estimate.first_month_rent` | No            | Potential             | "Apartments with first month rent under ¥200,000"                                | Not used; could filter if added.                                                 |
| `initial_cost_estimate.guarantor_service` | No           | Yes                   | "Apartments with no guarantor service fee"                                       | Filtered for `max_guarantor_service = 0`.                                       |
| `initial_cost_estimate.fire_insurance` | No             | Yes                   | "Apartments with no fire insurance fee"                                          | Filtered for `max_fire_insurance = 0`.                                          |
| `initial_cost_estimate.agency_fee` | No               | Potential             | "Apartments with agency fee under ¥100,000"                                      | Not used; could filter if added.                                                 |
| `initial_cost_estimate.estimated_total` | No          | Potential             | "Apartments with move-in costs under ¥500,000"                                   | Not used; could filter for total initial cost.                                   |
| `requirements.japanese_required`   | No                  | Yes                   | "Apartments for non-Japanese speakers"                                           | Filtered for `japanese_required = false`.                                        |
| `requirements.note`                | No                  | Potential             | "Apartments with specific tenant notes"                                          | Not used; could be in embedding if descriptive.                                  |
| `features.unit`                    | Yes                 | Yes                   | "Pet-friendly apartments with a dishwasher"                                      | In embedding; filtered for `unit_features` (e.g., "Dishwasher"), `pet_friendly`.  |
| `features.building`                | Yes                 | Yes                   | "Apartments in buildings with an elevator"                                       | In embedding; filtered for `building_features` (e.g., "Elevator").               |
| `images.main`                      | No                  | Yes (output)          | "Apartments with available photos"                                               | In payload for visualization; query unlikely.                                    |
| `images.thumbnails`                | No                  | Yes (output)          | "Apartments with multiple photos"                                                | In payload for visualization; query unlikely.                                    |
| `images.floorplan`                 | No                  | Yes (output)          | "Apartments with floorplan images"                                               | In payload for visualization; query unlikely.                                    |
| `unit_notes`                       | Potential           | No                    | "Apartments with special unit notes"                                             | Not populated; could be in embedding if descriptive.                             |
| `unit_notes_amenities`             | Potential           | No                    | "Apartments with extra amenities like a gym"                                     | Empty; could be in embedding if populated.                                       |
| `bedrooms`                         | No                  | Potential             | "Two-bedroom apartments in Bunkyo-ku"                                            | Not populated; could filter if added to `QueryElements`.                         |
| `balcony`                          | No                  | Potential             | "Apartments with a balcony"                                                      | Not populated; could filter if added to `QueryElements`.                         |
| `nearest_stations.station_name`    | Yes                 | Yes                   | "Apartments near Omotesando Station"                                             | In embedding for "near Omotesando"; filtered for `station_name`.                  |
| `nearest_stations.walk_time_min`   | Yes (text)          | Yes                   | "Apartments within 10 minutes of a station"                                      | In embedding as text; filtered for `max_walk_time`.                              |
| `nearest_stations.lines`           | Yes                 | Yes                   | "Apartments near the Odawara Line"                                               | In embedding for "Odawara Line"; filtered for `train_lines`.                     |

---

### Explanation of Example Queries
- **Natural Language**: Each query is phrased as a user might express it in a real estate search, avoiding technical terms (e.g., "ID 177020") and focusing on practical needs (e.g., "pet-friendly," "near Omotesando").
- **Hybrid Search**:
  - **Semantic Component**: Queries include terms that match the embedding text (e.g., "Nishiazabu" for `name`, "spacious" for `area.m2`). The LLM extracts `keywords` for vector search.
  - **Structured Component**: Queries trigger specific filters via `QueryElements` (e.g., `max_price: 200000`, `min_floor: 2`). The LLM parses numeric/categorical values for Qdrant filters.
- **Relevance to Tokyo**:
  - Queries reflect Tokyo’s context, using wards (e.g., "Minato-ku"), train lines (e.g., "Odawara Line"), and cultural factors (e.g., "non-Japanese speakers," "no guarantor fee").
  - For example, "not on the first floor" aligns with security concerns for single women, as you mentioned.
- **Potential Fields**: For fields not currently used (e.g., `bedrooms`, `price_per_m2`), queries assume implementation in `QueryElements` and filters, showing how they could be used.
- **Data Limitations**: Some queries (e.g., "near Odawara Line," "two-bedroom") may return no results with your current 3-property dataset due to empty fields (`lines`, `bedrooms`). They are designed to work with a populated dataset (e.g., 3000 properties).
