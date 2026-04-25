from fastapi import APIRouter
from models.schemas import (
    PhysicalRiskRequest,
    FloodRiskRequest,
    PhysicalRiskBreakdown,
    FloodRiskResponse,
    WaterQualityResponse,
)
from services.sentinel_ingest import fetch_sentinel2_data
from services.formulas.physical_risk import (
    calculate_water_depletion_risk,
    calculate_baseline_water_stress_risk,
    calculate_groundwater_risk,
    calculate_longterm_drought_risk,
    calculate_shortterm_drought_risk,
    calculate_flood_occurrence_risk,
    calculate_flood_hazard_risk,
    calculate_ndwi,
    calculate_mndwi,
    calculate_flood_inundation_index,
)
from services.formulas.flood_risk import (
    calculate_expected_annual_damage_index,
    calculate_flood_protection_standard_risk,
)
from services.formulas.water_quality import (
    calculate_biological_oxygen_demand_risk,
    calculate_nitrate_risk,
    calculate_water_quality_composite,
)
from services.formulas.investment_grade import calculate_wwf_physical_risk_composite
from config import ROMANIA_DEFAULTS
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/v1/risk", tags=["risk"])


class WaterQualityRequest(BaseModel):
    lat: float
    lon: float
    bod_mg_l: Optional[float] = None
    nitrate_mg_l: Optional[float] = None
    salinity_tds_mg_l: Optional[float] = None


@router.post("/physical", response_model=PhysicalRiskBreakdown)
def assess_physical_risk(req: PhysicalRiskRequest) -> PhysicalRiskBreakdown:
    # TODO: replace hardcoded band values with actual downloaded pixel statistics
    # when downstream band extraction pipeline is connected.
    green = req.green_band   # default 0.3
    nir = req.nir_band       # default 0.15
    swir = req.swir_band     # default 0.1

    try:
        satellite = fetch_sentinel2_data(req.lat, req.lon, req.buffer_km)
        sat_note = satellite.get("acquisition_date")
    except Exception:
        sat_note = None

    ndwi = calculate_ndwi(green, nir)
    mndwi = calculate_mndwi(green, swir)
    fsi = calculate_flood_inundation_index(ndwi, mndwi, flood_frequency=0.15)

    wa_risks = [
        calculate_water_depletion_risk(ROMANIA_DEFAULTS["depletion_ratio"]),
        calculate_baseline_water_stress_risk(
            ROMANIA_DEFAULTS["annual_depletion_pct"],
            ROMANIA_DEFAULTS["dry_year_months"],
            ROMANIA_DEFAULTS["seasonal_months"],
        ),
        calculate_groundwater_risk(ROMANIA_DEFAULTS["groundwater_change_mm"]),
    ]
    drought_risks = [
        calculate_longterm_drought_risk(ROMANIA_DEFAULTS["spei_dry_proportion_10yr"]),
        calculate_shortterm_drought_risk(ROMANIA_DEFAULTS["spei_dry_proportion_3yr"]),
    ]
    flood_risks = [
        calculate_flood_occurrence_risk(ROMANIA_DEFAULTS["flood_events_count"]),
        calculate_flood_hazard_risk(ROMANIA_DEFAULTS["avg_flood_depth_m"]),
    ]
    wq_composite = calculate_water_quality_composite(
        calculate_biological_oxygen_demand_risk(ROMANIA_DEFAULTS["bod_mg_per_l"]),
        calculate_nitrate_risk(ROMANIA_DEFAULTS["nitrate_mg_per_l"]),
        ROMANIA_DEFAULTS["salinity_tds_mg_l"],
    )

    result = calculate_wwf_physical_risk_composite(
        wa_risks, drought_risks, flood_risks, wq_composite["composite_risk"], fsi
    )

    return PhysicalRiskBreakdown(
        water_availability_risk=result["water_availability_risk"],
        drought_risk=result["drought_risk"],
        flood_risk=result["flood_risk"],
        water_quality_risk=result["water_quality_risk"],
        fsi=result["fsi"],
        composite=result["composite"],
        category_contributions=result["category_contributions"],
    )


@router.post("/flood", response_model=FloodRiskResponse)
def assess_flood_risk(req: FloodRiskRequest) -> FloodRiskResponse:
    ead = calculate_expected_annual_damage_index(
        req.flood_depth_m,
        req.return_period_years,
        req.land_use_type,
        req.gdp_per_capita_usd,
    )
    protection_risk = calculate_flood_protection_standard_risk(
        ROMANIA_DEFAULTS["protection_return_period"]
    )

    return FloodRiskResponse(
        structural_damage_index=ead["structural_damage_index"],
        content_damage_index=ead["content_damage_index"],
        total_damage_index=ead["total_damage_index"],
        damage_category=ead["damage_category"],
        occupancy_type=ead["occupancy_type"],
        flood_protection_risk=protection_risk,
        return_period_years=req.return_period_years,
        flood_depth_m=req.flood_depth_m,
    )


@router.post("/water-quality", response_model=WaterQualityResponse)
def assess_water_quality(req: WaterQualityRequest) -> WaterQualityResponse:
    bod = req.bod_mg_l if req.bod_mg_l is not None else ROMANIA_DEFAULTS["bod_mg_per_l"]
    nitrate = req.nitrate_mg_l if req.nitrate_mg_l is not None else ROMANIA_DEFAULTS["nitrate_mg_per_l"]
    salinity = req.salinity_tds_mg_l if req.salinity_tds_mg_l is not None else ROMANIA_DEFAULTS["salinity_tds_mg_l"]

    bod_risk = calculate_biological_oxygen_demand_risk(bod)
    nitrate_risk = calculate_nitrate_risk(nitrate)
    result = calculate_water_quality_composite(bod_risk, nitrate_risk, salinity)

    return WaterQualityResponse(
        bod_risk=result["bod_risk"],
        nitrate_risk=result["nitrate_risk"],
        salinity_risk=result["salinity_risk"],
        composite_risk=result["composite_risk"],
        composite_score=result["composite_score"],
        breakdown=result["breakdown"],
    )
