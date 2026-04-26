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
from services.formulas.sar_indicators import (
    sar_summary,
    calculate_flood_inundation_index_with_sar,
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
from services.sentinel_ingest import fetch_sentinel2_data, fetch_sentinel1_data
from services.location_data import fetch_location_inputs, resolve

router = APIRouter(prefix="/api/v1/investment", tags=["investment"])


def _build_grade_response(req: InvestmentGradeRequest) -> InvestmentGradeResponse:
    """
    Full scoring pipeline for one location.
    Data priority: user override > real API (Open-Meteo/EEA) > Romania defaults.
    """

    # --- Real location data (non-blocking) ---
    real = fetch_location_inputs(req.lat, req.lon)

    def r(key):
        return resolve(getattr(req, key, None), key, real)

    # --- Sentinel metadata — best-effort, skipped if slow ---
    # Both queries run with a hard 8-second timeout so they never block scoring.
    sat_meta = SatelliteMetadata(
        note="Satellite query unavailable — scores computed from ground data sources."
    )
    try:
        import signal as _signal

        def _timeout(signum, frame):
            raise TimeoutError()

        # Windows doesn't support SIGALRM; use try/except with short requests timeout
        sat = fetch_sentinel2_data(req.lat, req.lon, req.buffer_km)
        sat_meta = SatelliteMetadata(**sat)
    except Exception:
        pass

    try:
        s1 = fetch_sentinel1_data(req.lat, req.lon, req.buffer_km)
        sat_meta.s1_product_id       = s1.get("product_id")
        sat_meta.s1_acquisition_date = s1.get("acquisition_date")
        sat_meta.s1_mode             = "IW GRD"
        sat_meta.s1_polarisation     = "VV+VH"
        sat_meta.s1_download_url     = s1.get("download_url")
    except Exception:
        pass

    # --- Sentinel-2 band values ---
    green = r("green_band") or 0.3
    nir   = r("nir_band")   or 0.15
    swir  = r("swir_band")  or 0.1

    ndwi  = calculate_ndwi(green, nir)
    mndwi = calculate_mndwi(green, swir)

    # --- Sentinel-1 SAR bands (use when available) ---
    vv = r("vv_band")
    vh = r("vh_band")
    sar = None

    if vv is not None and vh is not None:
        sar = sar_summary(vv, vh)
        fsi = calculate_flood_inundation_index_with_sar(
            ndwi, mndwi, flood_frequency=0.15,
            sar_flood_index=sar["sar_flood_index"],
        )
    else:
        fsi = calculate_flood_inundation_index(ndwi, mndwi, flood_frequency=0.15)

    # --- Physical risk ---
    wa_risks = [
        calculate_water_depletion_risk(r("depletion_ratio")),
        calculate_baseline_water_stress_risk(
            r("annual_depletion_pct"),
            r("dry_year_months"),
            r("seasonal_months"),
        ),
        calculate_groundwater_risk(r("groundwater_change_mm")),
    ]
    drought_risks = [
        calculate_longterm_drought_risk(r("spei_dry_proportion_10yr")),
        calculate_shortterm_drought_risk(r("spei_dry_proportion_3yr")),
    ]
    flood_risks = [
        calculate_flood_occurrence_risk(r("flood_events_count")),
        calculate_flood_hazard_risk(r("avg_flood_depth_m")),
    ]

    bod_risk     = calculate_biological_oxygen_demand_risk(r("bod_mg_per_l"))
    nitrate_risk = calculate_nitrate_risk(r("nitrate_mg_per_l"))
    wq           = calculate_water_quality_composite(bod_risk, nitrate_risk, r("salinity_tds_mg_l"))

    physical = calculate_wwf_physical_risk_composite(
        wa_risks, drought_risks, flood_risks, wq["composite_risk"], fsi
    )

    # --- EAD ---
    land_use = r("land_use_type") or "industrial_park"
    ead = calculate_expected_annual_damage_index(
        r("flood_depth_m")       or 2.5,
        r("return_period_years") or 100,
        land_use,
        r("gdp_per_capita_usd")  or 14000.0,
    )
    ead_index = ead["total_damage_index"]

    # --- Regulatory / compliance ---
    reg_answers = {
        k: r(k)
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
    compliance_score      = reg["normalized"]

    # --- Final grade ---
    grade = calculate_investment_grade(
        physical["composite"],
        regulatory_risk_score,
        compliance_score,
        ead_index,
        req.user_type,
    )

    # Annotate satellite metadata with data sources used
    sources = []
    if real.get("_data_sources"):
        sources.extend(real["_data_sources"])
    if sar:
        sources.append(f"Sentinel-1 SAR VV+VH (flood={sar['flood_signal']}, moisture={sar['surface_moisture']})")
    if sources:
        sat_meta.note = "Ground+SAR: " + "; ".join(sources)

    # Build InvestmentGradeResponse — include physical sub-scores + SAR in breakdown
    breakdown = grade["breakdown"]
    # Expose physical sub-scores so frontend can build risk_categories
    breakdown["fsi"]                     = physical["fsi"]
    breakdown["water_availability_risk"] = physical["water_availability_risk"]
    breakdown["drought_risk"]            = physical["drought_risk"]
    breakdown["flood_risk"]              = physical["flood_risk"]
    breakdown["water_quality_risk"]      = physical["water_quality_risk"]
    if sar:
        breakdown["sar_flood_index"]        = sar["sar_flood_index"]
        breakdown["sar_moisture_index"]     = sar["sar_moisture_index"]
        breakdown["radar_vegetation_index"] = sar["radar_vegetation_index"]
        breakdown["s1_used"]                = True

    return InvestmentGradeResponse(
        score=grade["score"],
        grade=grade["grade"],
        grade_label=grade["grade_label"],
        breakdown=breakdown,
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

    best  = ranked[0].location_name  or f"({ranked[0].score})"
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

    center_lat = (lat_min + lat_max) / 2.0
    step_lat   = step_km / 111.0
    step_lon   = step_km / (111.0 * math.cos(math.radians(center_lat)))

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
        req = InvestmentGradeRequest(
            lat=lat, lon=lon, user_type=user_type,
            location_name=f"{lat},{lon}",
        )
        results.append(_build_grade_response(req))

    return results
