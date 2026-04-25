"""
Finnish-specific API routes and Historical Oracle backtest endpoint.
All routes are traceable to government-validated data sources (SYKE, ERA5, Aqueduct 4.0).
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from models.finland_schemas import (
    FinnishSiteRequest,
    CNDCPScoreResponse,
    WatershedTargetResponse,
    GalileoSubsidenceResponse,
    LegalAssessmentResponse,
    FinnishFullReportResponse,
    OracleValidationResponse,
)
from services.finland.syke_ingest import fetch_all_syke
from services.finland.cndcp_scoring import calculate_cndcp_score
from services.finland.watershed_targets import calculate_watershed_target
from services.finland.galileo_subsidence import simulate_galileo_has_monitoring
from services.finland.legal_agent import run_legal_assessment

router = APIRouter(prefix="/api/v1/finland", tags=["finland"])

# LUMI Supercomputer site — CSC Data Centre, Kajaani
LUMI_LAT = 64.2245
LUMI_LON = 27.7177
KAJAANI_RADIUS_KM = 100


# ---------------------------------------------------------------------------
# CNDCP scoring
# ---------------------------------------------------------------------------

@router.post("/cndcp-score", response_model=CNDCPScoreResponse)
def cndcp_score(req: FinnishSiteRequest) -> CNDCPScoreResponse:
    """
    Climate Neutral Data Centre Pact score for a Finnish location.
    Deterministic formula: Norm(1/CDD)×0.4 + (1−BWS)×0.4 + GW_weight×0.2
    """
    syke = fetch_all_syke(req.lat, req.lon)
    gw_weight = syke["groundwater"].get("class_weight", 0.3)

    result = calculate_cndcp_score(req.lat, req.lon, gw_weight, req.year)
    return CNDCPScoreResponse(**result)


# ---------------------------------------------------------------------------
# Watershed targets
# ---------------------------------------------------------------------------

@router.post("/watershed-target", response_model=WatershedTargetResponse)
def watershed_target(req: FinnishSiteRequest) -> WatershedTargetResponse:
    """
    Cargill/WRI watershed replenishment target for the facility.
    Target = (Current_BWD − Desired_BWD) / Current_BWD × Footprint
    """
    result = calculate_watershed_target(
        req.lat, req.lon,
        req.facility_footprint_m3yr,
        req.ambition_tier,
    )
    return WatershedTargetResponse(**result)


# ---------------------------------------------------------------------------
# Galileo HAS subsidence monitoring
# ---------------------------------------------------------------------------

@router.post("/galileo-subsidence", response_model=GalileoSubsidenceResponse)
def galileo_subsidence(req: FinnishSiteRequest) -> GalileoSubsidenceResponse:
    """
    Galileo HAS PPP-RTK simulated subsidence monitoring.
    Models GIA uplift (NKG2016LU) vs extraction-induced subsidence.
    """
    result = simulate_galileo_has_monitoring(
        req.lat, req.lon,
        req.water_abstraction_m3day,
        req.monitoring_months,
    )
    return GalileoSubsidenceResponse(**result)


# ---------------------------------------------------------------------------
# Vesilaki legal assessment
# ---------------------------------------------------------------------------

@router.post("/legal-assessment", response_model=LegalAssessmentResponse)
def legal_assessment(req: FinnishSiteRequest) -> LegalAssessmentResponse:
    """
    Vesilaki 587/2011 legal consultant (Claude AI).
    Checks permit requirements and construction restrictions using SYKE data.
    Requires ANTHROPIC_API_KEY.
    """
    syke = fetch_all_syke(req.lat, req.lon)
    assessment_text = run_legal_assessment(
        req.lat, req.lon, syke,
        req.facility_type,
        req.water_abstraction_m3day,
    )
    flood = syke.get("flood_hazard", {})
    gw    = syke.get("groundwater", {})

    return LegalAssessmentResponse(
        assessment=assessment_text,
        location={"lat": req.lat, "lon": req.lon},
        facility_type=req.facility_type,
        water_abstraction_m3day=req.water_abstraction_m3day,
        syke_flood_zone=flood.get("flood_zone_label", "None"),
        syke_groundwater_class=gw.get("groundwater_class"),
    )


# ---------------------------------------------------------------------------
# Full Finnish site report
# ---------------------------------------------------------------------------

@router.post("/full-report", response_model=FinnishFullReportResponse)
def full_report(req: FinnishSiteRequest, include_legal: bool = Query(default=False)) -> FinnishFullReportResponse:
    """
    Complete Finnish site assessment: SYKE + CNDCP + Watershed + Galileo + Legal.
    Set include_legal=true to invoke Claude (requires ANTHROPIC_API_KEY + credits).
    """
    syke     = fetch_all_syke(req.lat, req.lon)
    gw_w     = syke["groundwater"].get("class_weight", 0.3)
    cndcp    = calculate_cndcp_score(req.lat, req.lon, gw_w, req.year)
    ws       = calculate_watershed_target(req.lat, req.lon, req.facility_footprint_m3yr, req.ambition_tier)
    galileo  = simulate_galileo_has_monitoring(req.lat, req.lon, req.water_abstraction_m3day, req.monitoring_months)

    legal_text = None
    if include_legal:
        legal_text = run_legal_assessment(req.lat, req.lon, syke, req.facility_type, req.water_abstraction_m3day)

    # Investment verdict
    score = cndcp["cndcp_score"]
    alert = galileo["alert"]["level"]
    flood = syke["flood_hazard"]
    in_100 = flood.get("in_100yr_zone", False)

    if score >= 0.80 and alert == "green" and not in_100:
        verdict = "PRIME — All indicators green. Recommended for data centre investment."
    elif score >= 0.65 and alert in ("green", "yellow") and not in_100:
        verdict = "VIABLE — Good cooling efficiency. Minor risk factors present."
    elif in_100:
        verdict = "RESTRICTED — Site in 100-year flood zone. Requires ELY Centre flood risk assessment."
    elif alert in ("amber", "red"):
        verdict = "CAUTION — Galileo subsidence monitoring indicates extraction risk."
    else:
        verdict = "REVIEW — Multiple risk factors require further assessment."

    lineage = [
        f"SYKE Tulvavaarakartat — flood zones {datetime.utcnow().strftime('%Y-%m-%d')}",
        f"SYKE Pohjavesialueet — groundwater class {syke['groundwater'].get('groundwater_class', 'N/A')}",
        f"ERA5-Land CDD — {cndcp['data_sources']['cdd'].get('source', 'Open-Meteo')}",
        f"Aqueduct 4.0 BWS/BWD — {cndcp['data_sources']['bws'].get('source', 'WRI')}",
        f"NKG2016LU GIA model — Galileo HAS simulation",
        f"Cargill/WRI Practice Note (2022) — watershed target",
    ]

    return FinnishFullReportResponse(
        location={"lat": req.lat, "lon": req.lon},
        facility_type=req.facility_type,
        timestamp=datetime.utcnow(),
        syke_data=syke,
        cndcp=CNDCPScoreResponse(**cndcp),
        watershed_target=WatershedTargetResponse(**ws),
        galileo_subsidence=GalileoSubsidenceResponse(**galileo),
        legal_assessment=legal_text,
        investment_verdict=verdict,
        data_lineage=lineage,
    )


# ---------------------------------------------------------------------------
# Historical Oracle — GET /validate/kajaani
# ---------------------------------------------------------------------------

@router.get("/validate/kajaani", response_model=OracleValidationResponse)
def validate_kajaani() -> OracleValidationResponse:
    """
    Historical Oracle backtest for the LUMI Supercomputer site (Kajaani, Finland).
    Fetches 2015 ERA5-Land data and scores the site as if assessing it in 2015.
    Validation goal: if 2015 score > 0.90, the model is 'Verified'.
    LUMI was built at this site in 2021 — a confirmed optimal data centre location.
    Source: CSC (2021), Open-Meteo ERA5-Land archive.
    """
    syke = fetch_all_syke(LUMI_LAT, LUMI_LON)
    gw_w = syke["groundwater"].get("class_weight", 0.3)

    # 2015 scoring
    cndcp_2015 = calculate_cndcp_score(LUMI_LAT, LUMI_LON, gw_w, year=2015)

    # Current year scoring
    current_year = datetime.utcnow().year - 1
    cndcp_current = calculate_cndcp_score(LUMI_LAT, LUMI_LON, gw_w, year=current_year)

    score_2015   = cndcp_2015["cndcp_score"]
    score_current = cndcp_current["cndcp_score"]
    delta = round(score_current - score_2015, 4)
    verified = score_2015 >= 0.90

    verdict = (
        f"VERIFIED — 2015 CNDCP score {score_2015:.3f} exceeds 0.90 threshold. "
        f"Model correctly identifies LUMI site as Prime Investment Zone. "
        f"LUMI supercomputer was commissioned at this location in 2021, confirming prediction accuracy."
        if verified else
        f"PARTIAL — 2015 score {score_2015:.3f} below 0.90 threshold. "
        f"Model identifies site as viable but does not reach 'Prime' classification for 2015 conditions."
    )

    return OracleValidationResponse(
        site_name="LUMI Supercomputer — CSC Data Centre, Kajaani",
        location={"lat": LUMI_LAT, "lon": LUMI_LON},
        validation_year=2015,
        current_year=current_year,
        score_2015=score_2015,
        score_current=score_current,
        delta=delta,
        verified=verified,
        verdict=verdict,
        cndcp_2015=cndcp_2015,
        cndcp_current=cndcp_current,
        methodology=(
            "Open-Meteo ERA5-Land CDD (2015 annual), WRI Aqueduct 4.0 BWS, "
            "SYKE Pohjavesialueet groundwater class, CNDCP formula (2021). "
            "Validation criterion: score ≥ 0.90 → site classified as 'Prime Investment Zone'."
        ),
        data_lineage=[
            f"ERA5-Land CDD 2015: {cndcp_2015['data_sources']['cdd'].get('source', 'Open-Meteo')}",
            f"ERA5-Land CDD {current_year}: {cndcp_current['data_sources']['cdd'].get('source', 'Open-Meteo')}",
            f"BWS: {cndcp_2015['data_sources']['bws'].get('source', 'WRI Aqueduct 4.0')}",
            f"Groundwater: SYKE Pohjavesialueet, class={syke['groundwater'].get('groundwater_class', 'N/A')}",
            "SYKE flood hazard: Tulvavaarakartat MapServer",
        ],
    )
