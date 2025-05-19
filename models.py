from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# Property-related models
class Address(BaseModel):
    full: str
    latitude: float
    longitude: float

class Area(BaseModel):
    m2: float
    ft2: float
    price_per_m2: float
    price_per_ft2: float

class Price(BaseModel):
    monthly_total: int
    rent: int
    management_fee: int
    currency: str

class InitialCostEstimate(BaseModel):
    first_month_rent: int
    guarantor_service: int
    fire_insurance: Optional[int]
    agency_fee: int
    estimated_total: int

class Contract(BaseModel):
    length: Optional[str]
    type: Optional[str]

class Station(BaseModel):
    station_name: str
    walk_time_min: int
    lines: List[str]

class Features(BaseModel):
    unit: List[str]
    building: List[str]

class Images(BaseModel):
    main: str
    thumbnails: List[str]
    floorplan: str

class Property(BaseModel):
    id: str
    name: str
    unit_number: Optional[str]
    building_id: str
    address: Address
    area: Area
    type: str
    floor: Optional[str]
    contract: Optional[Contract]
    year_built: int
    price: Price
    initial_cost_estimate: InitialCostEstimate
    requirements: Optional[dict]
    features: Features
    images: Images
    unit_notes: Optional[str]
    unit_notes_amenities: List[str]
    bedrooms: Optional[int]
    balcony: Optional[str]
    nearest_stations: List[Station]

class Properties(BaseModel):
    properties: List[dict]  # List of dictionaries containing "property" key

# Query elements extracted by LLM
class QueryElements(BaseModel):
    keywords: List[str]  # For semantic search
    max_price: Optional[int]  # Monthly total in JPY
    min_area_m2: Optional[float]  # Minimum area in square meters
    ward: Optional[str]  # e.g., "Minato-ku"
    pet_friendly: Optional[bool]  # True if pet-friendly required
    max_walk_time: Optional[int]  # Max walk time to station in minutes
    station_name: Optional[str]  # Specific station
    min_year_built: Optional[int]  # Minimum year built