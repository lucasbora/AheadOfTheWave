from __future__ import annotations

import math
from datetime import datetime

from fastapi import APIRouter, HTTPException
from models.schemas import (
    InvestmentGradeRequest,
    InvestmentGradeResponse,
    LocationCompareRequest,
    CompareResponse,
    HeatmapRequest,
    SatelliteMetadata,
)
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
from services.formulas.regulatory_risk import calculate_regulatory_deficiency_score
from services.formulas.investment_grade import (
    calculate_wwf_physical_risk_composite,
    calculate_investment_grade,
    compare_locations,
)
from services.sentinel_ingest import fetch_sentinel2_data
from config import ROMANIA_DEFAULTS

router = APIRouter(prefix="/api/v1/investment", tags=["investment"])


def _r(req: InvestmentGradeRequest, key: str):
    """Return override value from request, falling back to Romania defaults."""
    val = getattr(req, key, None)
    return val if val is not None else ROMANIA_DEFAULTS.get(key)


def _build_grade_response(req: InvestmentGradeRequest) -> InvestmentGradeResponse:
    """Run the full scoring pipeline for a single location."""
    # Satellite metadata — best effort, non-blocking
    sat_meta: SatelliteMetadata
    try:
        sat = fetch_sentinel2_data(req.lat, req.lon, req.buffer_km)
        sat_meta = SatelliteMetadata(**sat)
    except Exception:
        sat_meta = SatelliteMetadata(
            note="Satellite query unavailable — formula scores computed with Romania defaults."
        )

    # Band values
    green = _r(req, "green_band") or 0.3
    nir = _r(req, "nir_band") or 0.15
    swir = _r(req, "swir_band") or 0.1

    ndwi = calculate_ndwi(green, nir)
    mndwi = calculate_mndwi(green, swir)
    fsi = calculate_flood_inundation_index(ndwi, mndwi, flood_frequency=0.15)

    # Physical risk
    wa_risks = [
        calculate_water_depletion_risk(_r(req, "depletion_ratio")),
        calculate_baseline_water_stress_risk(
            _r(req, "annual_depletion_pct"),
            _r(req, "dry_year_months"),
            _r(req, "seasonal_months"),
        ),
        calculate_groundwater_risk(_r(req, "groundwater_change_mm")),
    ]
    drought_risks = [
        calculate_longterm_drought_risk(_r(req, "spei_dry_proportion_10yr")),
        calculate_shortterm_drought_risk(_r(req, "spei_dry_proportion_3yr")),
    ]
    flood_risks = [
        calculate_flood_occurrence_risk(_r(req, "flood_events_count")),
        calculate_flood_hazard_risk(_r(req, "avg_flood_depth_m")),
    ]

    bod_risk = calculate_biological_oxygen_demand_risk(_r(req, "bod_mg_per_l"))
    nitrate_risk = calculate_nitrate_risk(_r(req, "nitrate_mg_per_l"))
    wq = calculate_water_quality_composite(bod_risk, nitrate_risk, _r(req, "salinity_tds_mg_l"))

    physical = calculate_wwf_physical_risk_composite(
        wa_risks, drought_risks, flood_risks, wq["composite_risk"], fsi
    )

    # EAD
    land_use = _r(req, "land_use_type") or "industrial_park"
    ead = calculate_expected_annual_damage_index(
        _r(req, "flood_depth_m") or 2.5,
        _r(req, "return_period_years") or 100,
        land_use,
        _r(req, "gdp_per_capita_usd") or 14000.0,
    )
    ead_index = ead["total_damage_index"]

    # Regulatory / compliance
    reg_answers = {
        k: _r(req, k)
        for k in [
            "iwrm_policy_exists", "iwrm_in_law", "water_authority_exists",
            "water_authority_has_enforcement", "clean_water_standards_penalties",
            "wastewater_penalties", "wetland_harm_penalties",
            "water_management_plans_required", "plans_enforceable",
            "monitoring_water_quality", "flood_disaster_framework", "governance_score",
        ]
    }
    reg = calculate_regulatory_deficiency_score(reg_answers)
    regulatory_risk_score = (reg["implementation_adjusted_risk"] - 1) / 4.0
    compliance_score = reg["normalized"]

    # Investment grade
    grade = calculate_investment_grade(
        physical["composite"],
        regulatory_risk_score,
        compliance_score,
        ead_index,
        req.user_type,
    )

    return InvestmentGradeResponse(
        score=grade["score"],
        grade=grade["grade"],
        grade_label=grade["grade_label"],
        breakdown=grade["breakdown"],
        satellite_metadata=sat_meta,
        physical_risk_composite=physical["composite"],
        regulatory_risk_composite=regulatory_risk_score,
        compliance_score=compliance_score,
        ead_index=ead_index,
        recommendation_summary=grade["recommendation_summary"],
        user_type=req.user_type,
        location_name=req.location_name,
        timestamp=datetime.utcnow(),
    )


@router.post("/grade", response_model=InvestmentGradeResponse)
def investment_grade(req: InvestmentGradeRequest) -> InvestmentGradeResponse:
    return _build_grade_response(req)


@router.post("/compare", response_model=CompareResponse)
def compare(req: LocationCompareRequest) -> CompareResponse:
    results: list[InvestmentGradeResponse] = []
    for loc in req.locations:
        loc.user_type = req.user_type
        results.append(_build_grade_response(loc))

    ranked_dicts = compare_locations(
        [r.model_dump() for r in results], req.user_type
    )

    ranked = [InvestmentGradeResponse(**d) for d in ranked_dicts]

    best = ranked[0].location_name or f"({ranked[0].score})"
    worst = ranked[-1].location_name or f"({ranked[-1].score})"

    return CompareResponse(
        ranked_locations=ranked,
        best_location=best,
        worst_location=worst,
        user_type=req.user_type,
    )


@router.get("/heatmap-points", response_model=list[InvestmentGradeResponse])
def heatmap_points(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    step_km: float = 10.0,
    user_type: str = "generic_investor",
    max_points: int = 25,
) -> list[InvestmentGradeResponse]:
    if max_points > 25:
        raise HTTPException(status_code=400, detail="max_points cannot exceed 25.")

    # Convert step_km to approximate degree steps
    center_lat = (lat_min + lat_max) / 2.0
    step_lat = step_km / 111.0
    step_lon = step_km / (111.0 * math.cos(math.radians(center_lat)))

    points: list[tuple[float, float]] = []
    lat = lat_min
    while lat <= lat_max and len(points) < max_points:
        lon = lon_min
        while lon <= lon_max and len(points) < max_points:
            points.append((round(lat, 4), round(lon, 4)))
            lon += step_lon
        lat += step_lat

    results = []
    for lat, lon in points[:max_points]:
        req = InvestmentGradeRequest(lat=lat, lon=lon, user_type=user_type, location_name=f"{lat},{lon}")
        results.append(_build_grade_response(req))

    return results
