from typing import List, Optional

from pydantic import BaseModel


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


class Requirements(BaseModel):
  japanese_required: Optional[bool]
  note: Optional[str]


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
  requirements: Optional[Requirements]
  features: Features
  images: Images
  unit_notes: Optional[str]
  unit_notes_amenities: List[str]
  bedrooms: Optional[int]
  balcony: Optional[str]
  nearest_stations: List[Station]


class Properties(BaseModel):
  properties: List[dict]


# Query elements extracted by LLM
class QueryElements(BaseModel):
  keywords: List[str]
  max_price: Optional[int]
  min_area_m2: Optional[float]
  ward: Optional[str]
  pet_friendly: Optional[bool]
  max_walk_time: Optional[int]
  station_name: Optional[str]
  min_year_built: Optional[int]
  min_floor: Optional[str]  # e.g., "2F" to exclude 1F
  max_floor: Optional[str]  # e.g., "10F" for high floors
  contract_length: Optional[str]  # e.g., "2 YearsStandard"
  max_management_fee: Optional[int]  # e.g., 0 for no fee
  max_guarantor_service: Optional[int]  # e.g., 0 for no fee
  max_fire_insurance: Optional[int]  # e.g., 0 for no fee
  japanese_required: Optional[bool]  # e.g., False for non-Japanese speakers
  unit_features: Optional[List[str]]  # e.g., ["Dishwasher", "Balcony"]
  building_features: Optional[List[str]]  # e.g., ["Elevator", "Autolock"]
  train_lines: Optional[List[str]]  # e.g., ["Odawara Line"]
