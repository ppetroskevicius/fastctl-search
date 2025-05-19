import json
from pathlib import Path

# Load JSON data
with open("data/json/rent_details_20250519_big.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Sets for unique features
unit_features = set()
building_features = set()

# Extract features
for item in data.get("properties", []):
    features = item.get("property", {}).get("features", {})
    unit_features.update(features.get("unit", []))
    building_features.update(features.get("building", []))

# Convert to sorted lists
result = {
    "features": {
        "unit": sorted(unit_features),
        "building": sorted(building_features)
    }
}

# Print output
print(json.dumps(result, indent=2, ensure_ascii=False))
