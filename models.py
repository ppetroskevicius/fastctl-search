from typing import List, Optional, Dict
from pydantic import BaseModel, model_validator

# Property-related models
class Address(BaseModel):
    full: str
    latitude: float  # Can be shared for multi-unit buildings
    longitude: float  # Can be shared for multi-unit buildings

    @model_validator(mode='after')
    def validate_coordinates(self):
        """Validate latitude/longitude ranges."""
        if not -90 <= self.latitude <= 90:
            raise ValueError(f"Invalid latitude: {self.latitude}, must be between -90 and 90")
        if not -180 <= self.longitude <= 180:
            raise ValueError(f"Invalid longitude: {self.longitude}, must be between -180 and 180")
        return self

class Area(BaseModel):
    m2: float
    ft2: Optional[float] = None
    price_per_m2: Optional[int] = None
    price_per_ft2: Optional[int] = None

class Price(BaseModel):
    currency: str
    total: Optional[int] = None  # For Buy
    monthly_total: Optional[int] = None  # For Rent/Short-term
    rent: Optional[int] = None  # For Rent/Short-term
    management_fee: Optional[int] = None  # For Rent/Short-term, some Buy
    short_term_monthly_total: Optional[int] = None  # For Short-term
    short_term_rent: Optional[int] = None  # For Short-term
    short_term_management_fee: Optional[int] = None  # For Short-term
    long_term_duration: Optional[str] = None  # For Short-term
    short_term_duration: Optional[str] = None  # For Short-term

class InitialCostEstimate(BaseModel):
    first_month_rent: int
    guarantor_service: int
    fire_insurance: Optional[int] = None
    agency_fee: int
    estimated_total: int

class Contract(BaseModel):
    length: str
    type: str

class StationLine(BaseModel):
    name: str
    company: Optional[str] = None

class Station(BaseModel):
    station_name: str
    walk_time_min: int
    lines: List[StationLine]

class Images(BaseModel):
    main: str
    floorplan: str
    thumbnails: Optional[List[str]] = None

class OtherRequirements(BaseModel):
    japanese_required: bool
    note: str

class Building(BaseModel):
    structure: Optional[str] = None
    year_built: int
    total_floors: Optional[int] = None
    total_units: Optional[int] = None

class Details(BaseModel):
    layout: Optional[str] = None
    balcony_direction: Optional[str] = None
    floor: Optional[str] = None
    land_rights: Optional[str] = None
    transaction_type: Optional[str] = None
    management_fee: Optional[int] = None
    repair_reserve_fund: Optional[int] = None

class BuildingNotes(BaseModel):
    summary: str
    description: str
    facilities: Optional[Dict[str, List[dict]]] = None

class Property(BaseModel):
    id: int
    name: str
    property_type: str
    type: str
    url: str
    address: Address
    area: Area
    price: Price
    images: Images
    amenities: List[str] = []  # Unified from features, amenities, unit_notes_amenities
    unit_number: Optional[str] = None  # Distinguishes flats in multi-unit buildings
    building_id: Optional[str] = None  # May group units in the same building
    floor: Optional[str] = None
    contract: Optional[Contract] = None
    year_built: Optional[int] = None
    initial_cost_estimate: Optional[InitialCostEstimate] = None
    other_requirements: Optional[OtherRequirements] = None
    additional_info: Optional[str] = None
    balcony: Optional[str] = None
    bedrooms: Optional[str] = None
    layout: Optional[str] = None
    listing_id: Optional[str] = None
    status: Optional[str] = None
    unit_notes: Optional[str] = None
    building: Optional[Building] = None
    details: Optional[Details] = None
    building_notes: Optional[BuildingNotes] = None
    nearest_stations: List[Station] = []

class Properties(BaseModel):
    properties: List[Property]

# Query elements extracted by LLM
class QueryElements(BaseModel):
    keywords: List[str] = []
    property_type: Optional[str] = None  # e.g., "Rent", "Buy", "Short-Term"
    max_total_price: Optional[int] = None  # For Buy
    max_monthly_price: Optional[int] = None  # For Rent/Short-term
    short_term_duration: Optional[str] = None  # For Short-term
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
    amenities: Optional[List[str]] = None  # Unified features
    layout: Optional[str] = None  # For Buy
    land_rights: Optional[str] = None  # For Buy
    status: Optional[str] = None  # For Buy
    building_id: Optional[str] = None  # For querying multi-unit buildings