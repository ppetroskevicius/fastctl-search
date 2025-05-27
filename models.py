from typing import List, Optional, Dict, Union, Literal
from pydantic import BaseModel, model_validator, Field, computed_field
from loguru import logger
from datetime import datetime
from enum import Enum
from pydantic import HttpUrl

class PropertyType(str, Enum):
    RENT = "Rent"
    BUY = "Buy"
    SHORT_TERM = "Short-Term"

class PropertyCategory(str, Enum):
    APARTMENT = "Apartment"
    BUILDING_WITH_TENANTS = "Building with tenants"
    HOME_WITH_TENANT = "Home with tenant"
    HOUSE = "House"
    LAND = "Land"
    MONTHLY_RENTAL = "Monthly Rental"
    OFFICE_STORE = "Office / Store"

class ContractType(str, Enum):
    FIXED = "Fixed"
    MONTHLY = "Monthly"
    STANDARD = "Standard"

class Status(str, Enum):
    AVAILABLE = "Available"
    UNDER_CONTRACT = "Under Contract"
    SOLD = "Sold"

class LandRights(str, Enum):
    FREEHOLD = "Freehold"
    LEASEHOLD = "Leasehold"

class LineCompany(str, Enum):
    JR = "JR"
    KEIKYU = "Keikyu"
    KEIO = "Keio"
    KEISEI = "Keisei"
    METROPOLITAN_INTERCITY = "Metropolitan Intercity Railway"
    ODAKYU = "Odakyu"
    SR = "SR"
    SEIBU = "Seibu"
    SOTETSU = "Sotetsu"
    TWR = "TWR"
    TOBU = "Tobu"
    TODEN = "Toden"
    TOEI = "Toei"
    TOKYO_METRO = "Tokyo Metro"
    TOKYO_MONORAIL = "Tokyo Monorail"
    TOKYU = "Tokyu"

class LineName(str, Enum):
    AIRPORT_LINE = "Airport Line"
    ARAKAWA_LINE = "Arakawa Line"
    ASAKUSA_LINE = "Asakusa Line"
    CHIBA_LINE = "Chiba Line"
    CHIBA_URBAN_MONORAIL_LINE_1 = "Chiba Urban Monorail Line 1"
    CHIBA_URBAN_MONORAIL_LINE_2 = "Chiba Urban Monorail Line 2"
    CHIHARA_LINE = "Chihara Line"
    CHIYODA_BRANCH_LINE = "Chiyoda Branch Line"
    CHIYODA_LINE = "Chiyoda Line"
    CHUO_LINE = "Chuo Line"
    CHUO_SOBU_LINE = "Chuo-Sobu Line"
    DAISHI_LINE = "Daishi Line"
    DEN_EN_TOSHI_LINE = "Den-en-toshi Line"
    ENOSHIMA_ELECTRIC_RAILWAY = "Enoshima Electric Railway"
    ENOSHIMA_LINE = "Enoshima Line"
    FUKUTOSHIN_LINE = "Fukutoshin Line"
    GINZA_LINE = "Ginza Line"
    HACHIKO_LINE = "Hachiko Line"
    HAIJIMA_LINE = "Haijima Line"
    HANZOMON_LINE = "Hanzomon Line"
    HIBIYA_LINE = "Hibiya Line"
    HOKUSO_LINE = "Hokuso Line"
    IKEBUKURO_LINE = "Ikebukuro Line"
    IKEGAMI_LINE = "Ikegami Line"
    INOKASHIRA_LINE = "Inokashira Line"
    ISESAKI_EXTENSION_LINE = "Isesaki Extension Line"
    ITSUKAICHI_LINE = "Itsukaichi Line"
    IZUMINO_LINE = "Izumino Line"
    JOBAN_EXPRESS_LINE = "Joban Express Line"
    JOBAN_LOCAL_LINE = "Joban Local Line"
    KAMEIDO_LINE = "Kameido Line"
    KANAMACHI_LINE = "Kanamachi Line"
    KEIBA_LINE = "Keiba Line"
    KEIHIN_TOHOKU_LINE = "Keihin-Tohoku Line"
    KEIKYU_LINE = "Keikyu Line"
    KEIO_LINE = "Keio Line"
    KEISEI_LINE = "Keisei Line"
    KEIYO_LINE = "Keiyo Line"
    KOKUBUNJI_LINE = "Kokubunji Line"
    KURIHAMA_LINE = "Kurihama Line"
    MARUNOUCHI_BRANCH_LINE = "Marunouchi Branch Line"
    MARUNOUCHI_LINE = "Marunouchi Line"
    MEGURO_LINE = "Meguro Line"
    MINATO_MIRAI_LINE = "Minato Mirai Line"
    MITA_LINE = "Mita Line"
    MUSASHINO_LINE = "Musashino Line"
    NAGAREYAMA_LINE = "Nagareyama Line"
    NAMBUKU_LINE = "Namboku Line"
    NAMBU_BRANCH_LINE = "Nambu Branch Line"
    NAMBU_LINE = "Nambu Line"
    NARITA_EXPRESS = "Narita Express"
    NARITA_LINE = "Narita Line"
    NEW_LINE = "New Line"
    NIPPORI_TONERI_LINER = "Nippori-Toneri Liner"
    NODA_LINE = "Noda Line"
    ODAWARA_LINE = "Odawara Line"
    OEDO_LINE = "Oedo Line"
    OGOSE_LINE = "Ogose Line"
    OIMACHI_LINE = "Oimachi Line"
    OME_LINE = "Ome Line"
    OSHIAGE_LINE = "Oshiage Line"
    RINKAI_LINE = "Rinkai Line"
    SAGAMI_LINE = "Sagami Line"
    SAGAMIHARA_LINE = "Sagamihara Line"
    SAIKYO_LINE = "Saikyo Line"
    SAITAMA_RAPID_RAILWAY_LINE = "Saitama Rapid Railway Line"
    SEIBU_SHINJUKU_LINE = "Seibu Shinjuku Line"
    SEIBU_EN_LINE = "Seibu-en Line"
    SETAGAYA_LINE = "Setagaya Line"
    SHIN_KEISEI_LINE = "Shin-Keisei Line"
    SHONAN_MONORAIL = "Shonan Monorail"
    SHONAN_SHINJUKU_LINE = "Shonan Shinjuku Line"
    SKYLINER = "Skyliner"
    SKYTREE_LINE = "Skytree Line"
    SOBU_LINE_RAPID = "Sobu Line (Rapid)"
    SOTETSU_LINE = "Sotetsu Line"
    TAKAO_LINE = "Takao Line"
    TAKASAKI_LINE = "Takasaki Line"
    TAMA_LINE = "Tama Line"
    TAMA_MONORAIL = "Tama Monorail"
    TAMAGAWA_LINE = "Tamagawa Line"
    TAMAKO_LINE = "Tamako Line"
    TOEI_SHINJUKU_LINE = "Toei Shinjuku Line"
    TOJO_LINE = "Tojo Line"
    TOKAIDO_MAIN_LINE = "Tokaido Main Line"
    TOKYO_MONORAIL = "Tokyo Monorail"
    TOSHIMA_LINE = "Toshima Line"
    TOYO_RAPID_LINE = "Toyo Rapid Line"
    TOYOKO_LINE = "Toyoko Line"
    TOZAI_LINE = "Tozai Line"
    TSUKUBA_EXPRESS_LINE = "Tsukuba Express Line"
    TSURUMI_LINE = "Tsurumi Line"
    TSURUMI_OKAWA_BRANCH_LINE = "Tsurumi Okawa Branch Line"
    UTSUNOMIYA_LINE = "Utsunomiya Line"
    YAMANOTE_LINE = "Yamanote Line"
    YOKOHAMA_LINE = "Yokohama Line"
    YOKOHAMA_SUBWAY_BLUE_LINE = "Yokohama Subway Blue Line"
    YOKOHAMA_SUBWAY_GREEN_LINE = "Yokohama Subway Green Line"
    YOKOSUKA_LINE = "Yokosuka Line"
    YURAKUCHO_LINE = "Yurakucho Line"
    YURAKUCHO_LINE_SEIBU = "Yurakucho Line (Seibu)"
    YURIKAMOME_LINE = "Yurikamome Line"

class Feature(str, Enum):
    AIR_CONDITIONING = "Air Conditioning"
    AUTO_LOCK = "Autolock"
    BALCONY = "Balcony"
    DELIVERY_BOX = "Delivery Box"
    DISHWASHER = "Dishwasher"
    DISPOSER = "Disposer"
    EARTHQUAKE_RESISTANCE = "Earthquake Resistance"
    FLOOR_HEATING = "Floor Heating"
    FREE_INTERNET = "Free Internet"
    FULLY_FURNISHED = "Fully Furnished"
    FURNISHED = "Furnished"
    GYM = "Gym"
    HIGH_SPEED_INTERNET = "High-speed Internet"
    INTERCOM = "Intercom"
    LOFT = "Loft"
    OVEN = "Oven"
    PARKING = "Parking"
    PET_FRIENDLY = "Pet Friendly"
    PET_NEGOTIABLE = "Pet Negotiable"
    RANGE_ELECTRIC = "Range Type: Electric"
    RANGE_GAS = "Range Type: Gas"
    RANGE_IH = "Range Type: IH"
    REFRIGERATOR = "Refrigerator"
    SECURITY = "Security"
    SECURITY_SYSTEM = "Security system for each unit"
    TATAMI_ROOM = "Tatami Room"
    TOILET_BATHROOM_SEPARATE = "Toilet / Bathroom Separate"
    WALK_IN_CLOSET = "Walk-in Closet"
    WASHER_DRYER = "Washer & Dryer"
    WASHER_IN_UNIT = "Washer In-Unit"
    WASHLET_TOILET = "Washlet Toilet"

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
        ft2_part = f" ({self.ft2:.1f}ft²)" if self.ft2 is not None else ""
        return f"{self.m2:.1f}㎡{ft2_part}"

class Price(BaseModel):
    currency: str = "JPY"
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

class Images(BaseModel):
    main: str
    thumbnails: List[str] = []
    floorplan: Optional[str] = None

class Line(BaseModel):
    company: Optional[LineCompany] = None
    name: LineName

class Station(BaseModel):
    station_name: str
    walk_time_min: int
    lines: List[Line]

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

class Contract(BaseModel):
    length: Optional[str] = None
    type: Optional[ContractType] = None

    @computed_field
    def contract_description(self) -> str:
        """Generate a human-readable contract description for semantic search"""
        return f"{self.type} contract for {self.length}"

class InitialCostEstimate(BaseModel):
    first_month_rent: Optional[int] = None
    guarantor_service: Optional[int] = None
    fire_insurance: Optional[int] = None
    agency_fee: Optional[int] = None
    estimated_total: Optional[int] = None

    @computed_field
    def cost_summary(self) -> str:
        """Generate a human-readable cost summary for semantic search"""
        return f"Initial costs: {self.estimated_total:,} including {self.first_month_rent:,} first month rent"

class Features(BaseModel):
    unit: List[Feature] = []
    building: List[str] = []

class BuildingNotes(BaseModel):
    summary: Optional[str] = None
    description: Optional[str] = None
    facilities: Optional[dict] = None

    @computed_field
    def notes_description(self) -> str:
        """Generate a human-readable notes description for semantic search"""
        parts = []
        if self.summary:
            parts.append(self.summary)
        if self.description:
            parts.append(self.description)
        if self.facilities:
            parts.append("Nearby Facilities:")
            for key, value in self.facilities.items():
                parts.append(f"{key}: {value}")
        
        return "\n\n".join(parts) if parts else ""

class Details(BaseModel):
    layout: Optional[str] = None
    balcony_direction: Optional[str] = None
    floor: Optional[str] = None
    land_rights: Optional[LandRights] = None
    transaction_type: Optional[str] = None
    management_fee: Optional[int] = None
    repair_reserve_fund: Optional[int] = None

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

class Building(BaseModel):
    structure: Optional[str] = None
    year_built: Optional[int] = None
    total_floors: Optional[int] = None
    total_units: Optional[int] = None

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

class Property(BaseModel):
    id: int
    url: HttpUrl
    property_type: PropertyType
    name: str
    address: Address
    area: Area
    type: PropertyCategory
    price: Price
    images: Images
    nearest_stations: List[Station] = []
    unit_number: Optional[str] = None
    floor: Optional[str] = None
    contract: Optional[Contract] = None
    year_built: Optional[int] = None
    initial_cost_estimate: Optional[InitialCostEstimate] = None
    features: Optional[Features] = None
    unit_notes: Optional[str] = None
    unit_notes_amenities: Optional[List[str]] = None
    bedrooms: Optional[str] = None
    balcony: Optional[str] = None
    building_notes: Optional[BuildingNotes] = None
    layout: Optional[str] = None
    status: Optional[Status] = None
    listing_id: Optional[str] = None
    last_updated: Optional[datetime] = None
    details: Optional[Details] = None
    building: Optional[Building] = None
    additional_info: Optional[str] = None

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
            
        if self.features:
            all_features = []
            if self.features.unit:
                all_features.extend(self.features.unit)
            if self.features.building:
                all_features.extend(self.features.building)
            if all_features:
                parts.append("Features: " + ", ".join(all_features))
            
        if self.unit_notes_amenities:
            parts.append("Amenities: " + ", ".join(self.unit_notes_amenities))
            
        return "\n".join(filter(None, parts))

    @computed_field
    def search_keywords(self) -> List[str]:
        """Generate relevant keywords for search enhancement"""
        keywords = []
        if self.layout:
            keywords.extend(self.layout.split())
        if self.features:
            if self.features.unit:
                keywords.extend(self.features.unit)
            if self.features.building:
                keywords.extend(self.features.building)
        if self.unit_notes_amenities:
            keywords.extend(self.unit_notes_amenities)
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