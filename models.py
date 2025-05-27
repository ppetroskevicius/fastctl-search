from typing import List, Optional, Dict, Union, Literal
from pydantic import BaseModel, model_validator, Field, computed_field
from loguru import logger
from datetime import datetime
from enum import Enum

# Enums - Define these first
class PropertyType(str, Enum):
    RENT = "Rent"
    BUY = "Buy"
    SHORT_TERM = "Short-Term"

class PropertyStatus(str, Enum):
    AVAILABLE = "Available"
    UNDER_CONTRACT = "Under Contract"
    SOLD = "Sold"

class PropertyCategory(str, Enum):
    APARTMENT = "Apartment"
    HOUSE = "House"
    OFFICE_STORE = "Office / Store"
    BUILDING_WITH_TENANTS = "Building with tenants"
    HOME_WITH_TENANT = "Home with tenant"
    LAND = "Land"
    MONTHLY_RENTAL = "Monthly Rental"

class ContractType(str, Enum):
    FIXED = "Fixed"
    STANDARD = "Standard"
    MONTHLY = "Monthly"

class LandRights(str, Enum):
    FREEHOLD = "Freehold"
    LEASEHOLD = "Leasehold"

# Property-related models
class Address(BaseModel):
    full: str
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    ward: Optional[str] = None  # Added for better location search
    city: Optional[str] = None  # Added for better location search
    postal_code: Optional[str] = None  # Added for better location search

    @computed_field
    def location_description(self) -> str:
        """Generate a human-readable location description for semantic search"""
        parts = [self.full]
        if self.ward:
            parts.append(f"in {self.ward}")
        if self.city:
            parts.append(f"in {self.city}")
        return " ".join(parts)

class Area(BaseModel):
    m2: float = Field(..., gt=0)
    ft2: Optional[float] = Field(None, gt=0)
    price_per_m2: Optional[int] = Field(None, gt=0)
    price_per_ft2: Optional[int] = Field(None, gt=0)

    @computed_field
    def size_description(self) -> str:
        """Generate a human-readable size description for semantic search"""
        return f"{self.m2:.1f}㎡ ({self.ft2:.1f}ft² if self.ft2 else '')"

class Price(BaseModel):
    currency: str
    total: Optional[int] = None  # For Buy
    monthly_total: Optional[int] = None  # For Rent/Short-term
    rent: Optional[int] = None  # For Rent/Short-term
    management_fee: Optional[int] = None
    short_term_monthly_total: Optional[int] = None
    short_term_rent: Optional[int] = None
    short_term_management_fee: Optional[int] = None
    long_term_duration: Optional[str] = None
    short_term_duration: Optional[str] = None

    @computed_field
    def price_description(self) -> str:
        """Generate a human-readable price description for semantic search"""
        if self.total:
            return f"{self.total:,} {self.currency} (total)"
        elif self.monthly_total:
            return f"{self.monthly_total:,} {self.currency}/month"
        else:
            return f"{self.short_term_monthly_total:,} {self.currency}/month (short-term)"

class InitialCostEstimate(BaseModel):
    first_month_rent: int
    guarantor_service: int
    fire_insurance: Optional[int] = None
    agency_fee: int
    estimated_total: int

    @computed_field
    def cost_summary(self) -> str:
        """Generate a human-readable cost summary for semantic search"""
        return f"Initial costs: {self.estimated_total:,} including {self.first_month_rent:,} first month rent"

class Contract(BaseModel):
    length: str  # Keep as string due to varied formats like "2 YearsFixed"
    type: ContractType
    
    @computed_field
    def contract_description(self) -> str:
        """Generate a human-readable contract description for semantic search"""
        return f"{self.type} contract for {self.length}"

class StationLine(BaseModel):
    name: str
    company: Optional[str] = None

class Station(BaseModel):
    station_name: str
    walk_time_min: int = Field(..., ge=0, le=60)
    lines: List[StationLine]

    @computed_field
    def station_description(self) -> str:
        """Generate a human-readable station description for semantic search"""
        lines_str = ", ".join(line.name for line in self.lines)
        return f"{self.station_name} Station ({self.walk_time_min} min walk) - Lines: {lines_str}"
    
    @computed_field
    def accessibility_score(self) -> float:
        """Calculate an accessibility score based on walk time and number of lines"""
        base_score = 100 - (self.walk_time_min * 2)  # Decrease score by 2 points per minute
        line_bonus = len(self.lines) * 5  # Add 5 points per line
        return min(100, max(0, base_score + line_bonus))

class Images(BaseModel):
    main: str
    floorplan: str
    thumbnails: Optional[List[str]] = None

class OtherRequirements(BaseModel):
    japanese_required: bool
    note: str

class Building(BaseModel):
    structure: Optional[str] = None
    year_built: Optional[int] = Field(None, ge=1900, le=datetime.now().year + 1)
    total_floors: Optional[int] = Field(None, gt=0)
    total_units: Optional[int] = Field(None, gt=0)
    building_id: Optional[str] = None  # Moved from Property to Building

    @computed_field
    def building_description(self) -> str:
        """Generate a human-readable building description for semantic search"""
        desc_parts = []
        if self.year_built:
            desc_parts.append(f"Built in {self.year_built}")
        if self.structure:
            desc_parts.append(f"{self.structure} structure")
        if self.total_floors:
            desc_parts.append(f"{self.total_floors} floors")
        return ", ".join(desc_parts) if desc_parts else ""

class Details(BaseModel):
    layout: Optional[str] = None
    balcony_direction: Optional[str] = None
    floor: Optional[str] = None
    land_rights: Optional[LandRights] = None
    transaction_type: Optional[str] = None
    management_fee: Optional[int] = Field(None, gt=0)
    repair_reserve_fund: Optional[int] = Field(None, gt=0)

    @computed_field
    def details_description(self) -> str:
        """Generate a human-readable details description for semantic search"""
        desc_parts = []
        if self.layout:
            desc_parts.append(f"Layout: {self.layout}")
        if self.floor:
            desc_parts.append(f"Floor: {self.floor}")
        if self.balcony_direction:
            desc_parts.append(f"Balcony facing {self.balcony_direction}")
        if self.land_rights:
            desc_parts.append(f"Land rights: {self.land_rights}")
        return ", ".join(desc_parts) if desc_parts else ""

class Facility(BaseModel):
    """New model for structured facility information"""
    category: str  # e.g., 'Supermarket', 'Convenience Store', 'Park'
    name: str
    distance_description: str  # e.g., '2min walk', '300m'
    additional_info: Optional[str] = None

class BuildingNotes(BaseModel):
    summary: str
    description: str
    facilities: List[Facility] = []  # Changed to structured Facility objects

    @computed_field
    def notes_description(self) -> str:
        """Generate a human-readable notes description for semantic search"""
        facility_desc = "\n".join(f"{f.category}: {f.name} ({f.distance_description})" 
                                for f in self.facilities)
        return f"{self.summary}\n\n{self.description}\n\nNearby Facilities:\n{facility_desc}"

class Property(BaseModel):
    id: int
    name: str
    property_type: PropertyType
    type: PropertyCategory
    url: str
    address: Address
    area: Area
    price: Price
    images: Images
    amenities: List[str] = []
    unit_number: Optional[str] = None
    floor: Optional[str] = None
    contract: Optional[Contract] = None
    year_built: Optional[int] = Field(None, ge=1900, le=datetime.now().year + 1)
    initial_cost_estimate: Optional[InitialCostEstimate] = None
    other_requirements: Optional[OtherRequirements] = None
    additional_info: Optional[str] = None
    balcony: Optional[str] = None
    bedrooms: Optional[str] = None
    layout: Optional[str] = None
    listing_id: Optional[str] = None
    status: Optional[PropertyStatus] = None
    unit_notes: Optional[str] = None
    unit_notes_amenities: Optional[List[str]] = None
    building: Optional[Building] = None
    details: Optional[Details] = None
    building_notes: Optional[BuildingNotes] = None
    nearest_stations: List[Station] = []
    features: Optional[Dict[str, List[str]]] = None
    last_updated: Optional[datetime] = None

    class Config:
        use_enum_values = True  # This ensures enum values are used in JSON output

    @computed_field
    def semantic_description(self) -> str:
        """Generate a comprehensive description for semantic search"""
        parts = [
            f"{self.name} - {self.type} for {self.property_type}",
            f"Location: {self.address.location_description}",
            self.area.size_description,
            self.price.price_description
        ]
        
        if self.nearest_stations:
            station_desc = [s.station_description for s in self.nearest_stations]
            parts.append("Stations: " + "; ".join(station_desc))
            
        if self.building:
            parts.append(self.building.building_description)
            
        if self.details:
            parts.append(self.details.details_description)
            
        if self.building_notes:
            parts.append(self.building_notes.notes_description)
            
        if self.amenities:
            parts.append("Amenities: " + ", ".join(self.amenities))
            
        return "\n".join(filter(None, parts))

    @computed_field
    def search_keywords(self) -> List[str]:
        """Generate relevant keywords for search enhancement"""
        keywords = []
        if self.layout:
            keywords.extend(self.layout.split())
        if self.features:
            for feature_list in self.features.values():
                keywords.extend(feature_list)
        if self.amenities:
            keywords.extend(self.amenities)
        return list(set(keywords))

    @computed_field
    def property_highlights(self) -> Dict[str, str]:
        """Generate key highlights for quick property overview"""
        return {
            "size": self.area.size_description,
            "price": self.price.price_description,
            "location": self.address.location_description,
            "nearest_station": self.nearest_stations[0].station_description if self.nearest_stations else "No station info",
            "year_built": str(self.year_built) if self.year_built else "Unknown",
            "key_features": ", ".join(self.search_keywords[:5]) if self.search_keywords else "No features listed"
        }

    @computed_field
    def accessibility_metrics(self) -> Dict[str, float]:
        """Calculate various accessibility metrics"""
        if not self.nearest_stations:
            return {"overall_score": 0.0}
            
        station_scores = [s.accessibility_score for s in self.nearest_stations]
        return {
            "overall_score": sum(station_scores) / len(station_scores),
            "best_station_score": max(station_scores),
            "average_walk_time": sum(s.walk_time_min for s in self.nearest_stations) / len(self.nearest_stations)
        }

class Properties(BaseModel):
    properties: List[Property]

# Query elements for semantic search
class SemanticSearchQuery(BaseModel):
    """Enhanced query model for semantic search"""
    query_text: str
    property_type: Optional[str] = None
    price_range: Optional[tuple[int, int]] = None
    area_range: Optional[tuple[float, float]] = None
    location_preference: Optional[str] = None
    max_walk_time: Optional[int] = Field(None, ge=0, le=60)
    amenities_required: List[str] = []
    exclude_keywords: List[str] = []
    sort_by: Optional[str] = Field(None, pattern="^(price|distance|newest)$")

# Query elements extracted by LLM
class QueryElements(BaseModel):
    keywords: List[str] = []
    property_type: Optional[str] = None
    max_total_price: Optional[int] = None
    max_monthly_price: Optional[int] = None
    short_term_duration: Optional[str] = None
    min_area_m2: Optional[float] = None
    ward: Optional[str] = None
    pet_friendly: Optional[bool] = None
    max_walk_time: Optional[int] = None
    station_name: Optional[str] = None
    train_lines: Optional[List[str]] = None
    min_year_built: Optional[int] = None
    min_floor: Optional[str] = None
    max_floor: Optional[str] = None
    contract_length: Optional[str] = None
    max_management_fee: Optional[int] = None
    max_guarantor_service: Optional[int] = None
    max_fire_insurance: Optional[int] = None
    japanese_required: Optional[bool] = None
    amenities: Optional[List[str]] = None
    unit_notes_amenities: Optional[List[str]] = None
    layout: Optional[str] = None
    land_rights: Optional[str] = None
    status: Optional[str] = None
    building_id: Optional[str] = None