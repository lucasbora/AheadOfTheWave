from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class PhysicalRiskRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    buffer_km: float = Field(default=5.0, gt=0)
    # Sentinel-2 optical bands (B03, B08, B11)
    green_band: float = Field(default=0.3, ge=0, le=1)
    nir_band: float = Field(default=0.15, ge=0, le=1)
    swir_band: float = Field(default=0.1, ge=0, le=1)
    # Sentinel-1 SAR bands (VV, VH) — normalised DN 0-1
    vv_band: Optional[float] = Field(default=None, ge=0, le=1)
    vh_band: Optional[float] = Field(default=None, ge=0, le=1)


class FloodRiskRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    flood_depth_m: float = Field(default=2.5, ge=0)
    return_period_years: int = Field(default=100, ge=1)
    land_use_type: str = Field(default="industrial_park")
    gdp_per_capita_usd: float = Field(default=14000.0, gt=0)

    @field_validator("land_use_type")
    @classmethod
    def validate_land_use(cls, v: str) -> str:
        allowed = {"residential", "commercial", "industrial", "data_center"}
        if v not in allowed:
            raise ValueError(f"land_use_type must be one of {allowed}")
        return v


class ComplianceRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    iwrm_policy_exists: bool = True
    iwrm_in_law: bool = True
    water_authority_exists: bool = True
    water_authority_has_enforcement: bool = True
    clean_water_standards_penalties: bool = True
    wastewater_penalties: bool = True
    wetland_harm_penalties: bool = True
    water_management_plans_required: bool = True
    plans_enforceable: bool = False
    monitoring_water_quality: bool = True
    flood_disaster_framework: bool = True
    governance_score: float = Field(default=0.3, ge=-2.5, le=2.5)


class InvestmentGradeRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    buffer_km: float = Field(default=5.0, gt=0)
    user_type: str = Field(default="generic_investor")
    location_name: Optional[str] = None
    # Physical risk overrides
    depletion_ratio: Optional[float] = None
    annual_depletion_pct: Optional[float] = None
    dry_year_months: Optional[int] = None
    seasonal_months: Optional[int] = None
    groundwater_change_mm: Optional[float] = None
    spei_dry_proportion_10yr: Optional[float] = None
    spei_dry_proportion_3yr: Optional[float] = None
    flood_events_count: Optional[int] = None
    avg_flood_depth_m: Optional[float] = None
    # Water quality overrides
    bod_mg_per_l: Optional[float] = None
    nitrate_mg_per_l: Optional[float] = None
    salinity_tds_mg_l: Optional[float] = None
    # Flood risk overrides
    flood_depth_m: Optional[float] = None
    return_period_years: Optional[int] = None
    land_use_type: Optional[str] = None
    gdp_per_capita_usd: Optional[float] = None
    protection_return_period: Optional[int] = None
    # Compliance overrides
    iwrm_policy_exists: Optional[bool] = None
    iwrm_in_law: Optional[bool] = None
    water_authority_exists: Optional[bool] = None
    water_authority_has_enforcement: Optional[bool] = None
    clean_water_standards_penalties: Optional[bool] = None
    wastewater_penalties: Optional[bool] = None
    wetland_harm_penalties: Optional[bool] = None
    water_management_plans_required: Optional[bool] = None
    plans_enforceable: Optional[bool] = None
    monitoring_water_quality: Optional[bool] = None
    flood_disaster_framework: Optional[bool] = None
    governance_score: Optional[float] = None
    # Sentinel-2 band overrides
    green_band: Optional[float] = None
    nir_band: Optional[float] = None
    swir_band: Optional[float] = None
    # Sentinel-1 SAR band overrides (normalised DN 0-1)
    vv_band: Optional[float] = None
    vh_band: Optional[float] = None

    @field_validator("user_type")
    @classmethod
    def validate_user_type(cls, v: str) -> str:
        allowed = {"data_center", "industrial_park", "logistics", "residential_developer", "generic_investor"}
        if v not in allowed:
            raise ValueError(f"user_type must be one of {allowed}")
        return v


class LocationCompareRequest(BaseModel):
    locations: list[InvestmentGradeRequest] = Field(..., min_length=1, max_length=10)
    user_type: str = Field(default="generic_investor")

    @field_validator("user_type")
    @classmethod
    def validate_user_type(cls, v: str) -> str:
        allowed = {"data_center", "industrial_park", "logistics", "residential_developer", "generic_investor"}
        if v not in allowed:
            raise ValueError(f"user_type must be one of {allowed}")
        return v


class HeatmapRequest(BaseModel):
    lat_min: float = Field(..., ge=-90, le=90)
    lat_max: float = Field(..., ge=-90, le=90)
    lon_min: float = Field(..., ge=-180, le=180)
    lon_max: float = Field(..., ge=-180, le=180)
    step_km: float = Field(default=10.0, gt=0)
    user_type: str = Field(default="generic_investor")
    max_points: int = Field(default=25, ge=1, le=25)


class ExplanationRequest(BaseModel):
    investment_grade_response: dict[str, Any]
    user_type: str = Field(default="generic_investor")
    location_name: Optional[str] = None


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class SatelliteMetadata(BaseModel):
    # Sentinel-2 (optical)
    product_id: Optional[str] = None
    acquisition_date: Optional[str] = None
    cloud_cover_pct: Optional[float] = None
    bounding_box: Optional[list[float]] = None
    tile_id: Optional[str] = None
    download_url: Optional[str] = None
    source: str = "ESA Copernicus CDSE"
    note: Optional[str] = None
    # Sentinel-1 (SAR)
    s1_product_id: Optional[str] = None
    s1_acquisition_date: Optional[str] = None
    s1_mode: Optional[str] = None       # e.g. "IW GRD"
    s1_polarisation: Optional[str] = None  # e.g. "VV+VH"
    s1_download_url: Optional[str] = None


class PhysicalRiskBreakdown(BaseModel):
    water_availability_risk: float
    drought_risk: float
    flood_risk: float
    water_quality_risk: float
    fsi: float
    composite: float
    category_contributions: dict[str, float]
    # SAR indicators (present when Sentinel-1 bands available)
    sar_flood_index: Optional[float] = None
    sar_moisture_index: Optional[float] = None
    radar_vegetation_index: Optional[float] = None
    s1_used: bool = False


class FloodRiskResponse(BaseModel):
    structural_damage_index: float
    content_damage_index: float
    total_damage_index: float
    damage_category: str
    occupancy_type: str
    flood_protection_risk: int
    return_period_years: int
    flood_depth_m: float


class ComplianceResponse(BaseModel):
    total_score: int
    risk_value: int
    normalized: float
    failed_criteria: list[str]
    implementation_adjusted_risk: int
    governance_score: float


class InvestmentGradeResponse(BaseModel):
    score: float
    grade: str
    grade_label: str
    breakdown: dict[str, float]
    satellite_metadata: SatelliteMetadata
    physical_risk_composite: float
    regulatory_risk_composite: float
    compliance_score: float
    ead_index: float
    recommendation_summary: str
    user_type: str
    location_name: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    rank: Optional[int] = None
    delta_from_best: Optional[float] = None


class CompareResponse(BaseModel):
    ranked_locations: list[InvestmentGradeResponse]
    best_location: str
    worst_location: str
    user_type: str


class WaterQualityResponse(BaseModel):
    bod_risk: int
    nitrate_risk: int
    salinity_risk: int
    composite_risk: int
    composite_score: float
    breakdown: dict[str, int]


class UserProfileResponse(BaseModel):
    user_type: str
    description: str
    critical_indicators: list[str]
    regulatory_focus: list[str]
    key_question: str
    benchmark_threshold: int
    risk_tolerance: str
