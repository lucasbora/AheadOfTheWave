from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class FinnishSiteRequest(BaseModel):
    lat: float = Field(..., ge=59.0, le=70.5, description="WGS84 latitude (Finland)")
    lon: float = Field(..., ge=19.0, le=32.0, description="WGS84 longitude (Finland)")
    facility_type: str = Field(default="data_center")
    water_abstraction_m3day: float = Field(default=300.0, gt=0)
    facility_footprint_m3yr: float = Field(default=500_000.0, gt=0)
    ambition_tier: str = Field(default="ambitious")
    monitoring_months: int = Field(default=24, ge=1, le=120)
    year: Optional[int] = Field(default=None, description="Year for CDD calculation")


class CNDCPScoreResponse(BaseModel):
    cndcp_score: float
    grade: str
    grade_label: str
    components: dict[str, float]
    weights: dict[str, float]
    raw_inputs: dict[str, float]
    data_sources: dict[str, Any]
    formula: str
    methodology: str


class WatershedTargetResponse(BaseModel):
    replenishment_target_m3yr: float
    gtd_adjustment_m3yr: float
    total_target_m3yr: float
    reduction_fraction: float
    ambition_tier: str
    desired_bwd: float
    status: str
    feasibility: bool
    depletion_data: dict[str, Any]
    formula: str
    methodology: str


class GalileoSubsidenceResponse(BaseModel):
    location: dict[str, float]
    monitoring_period_months: int
    gia_uplift_rate_mm_yr: float
    extraction_subsidence_rate_mm_yr: float
    net_vertical_rate_mm_yr: float
    extraction_level: str
    abstraction_m3day: float
    alert: dict[str, Any]
    instrument: dict[str, str]
    gia_model: str
    monthly_readings: list[dict[str, Any]]
    total_displacement_trend_mm: float


class LegalAssessmentResponse(BaseModel):
    assessment: str
    location: dict[str, float]
    facility_type: str
    water_abstraction_m3day: float
    syke_flood_zone: str
    syke_groundwater_class: Optional[str]
    legislation: str = "Vesilaki 587/2011"


class FinnishFullReportResponse(BaseModel):
    location: dict[str, float]
    facility_type: str
    timestamp: datetime
    syke_data: dict[str, Any]
    cndcp: CNDCPScoreResponse
    watershed_target: WatershedTargetResponse
    galileo_subsidence: GalileoSubsidenceResponse
    legal_assessment: Optional[str] = None
    investment_verdict: str
    data_lineage: list[str]


class OracleValidationResponse(BaseModel):
    site_name: str
    location: dict[str, float]
    validation_year: int
    current_year: int
    score_2015: float
    score_current: float
    delta: float
    verified: bool
    verdict: str
    cndcp_2015: dict[str, Any]
    cndcp_current: dict[str, Any]
    methodology: str
    data_lineage: list[str]
