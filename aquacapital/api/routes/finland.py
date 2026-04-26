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

# Investment advisor prompt — tells Claude to act as a water-focused investment advisor
_ADVISOR_SYSTEM = """You are a senior investment analyst specialising in data centre infrastructure and water risk.
Your job: analyse the provided scoring data and give a direct, evidence-based investment recommendation.

Rules:
1. Cite every claim with the exact data field provided.
2. Focus specifically on water cooling requirements for AI data centres.
3. The key insight: Finland's cold climate (low CDD) enables free-air cooling, eliminating 30-40% of typical CAPEX.
4. If the year is 2018 and the site is LUMI Kajaani, mention that the LUMI EuroHPC supercomputer was built here in 2021 — this validates the model.
5. Be direct. No marketing language.
6. Structure your response in exactly 3 sections:
   INVESTMENT VERDICT: one sentence, direct recommendation
   WHY WATER MATTERS HERE: 2-3 sentences on the cooling + water risk story
   KEY RISKS: 2-3 bullet points, evidence-based only"""

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
    # Return dict directly — FastAPI coerces instrument dict -> GalileoInstrumentSpec
    return result


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


# ---------------------------------------------------------------------------
# Kajaani backtest — the core validation story
# ---------------------------------------------------------------------------

@router.get("/kajaani-backtest")
def kajaani_backtest(year: int = Query(default=2018)) -> dict:
    """
    Score the LUMI site using real Sentinel-1 + Sentinel-2 + Visual Crossing + SYKE.
    year=2018: site was empty. LUMI built 2021. High score = model validated.
    """
    from services.finland.kajaani_scoring import calculate_kajaani_score
    from config import settings
    import anthropic

    result_year = calculate_kajaani_score(LUMI_LAT, LUMI_LON, year=year)
    result_now  = calculate_kajaani_score(LUMI_LAT, LUMI_LON, year=None)

    timeline = [
        {"year": 2018, "event": "Site assessment (empty land)",
         "score": result_year["score"] if year == 2018 else None,
         "grade": result_year["grade"] if year == 2018 else None},
        {"year": 2020, "event": "LUMI EuroHPC announced", "score": None, "grade": None},
        {"year": 2021, "event": "LUMI supercomputer operational", "score": None, "grade": None},
        {"year": 2026, "event": "Current conditions",
         "score": result_now["score"], "grade": result_now["grade"]},
    ]

    verified = result_year["score"] >= 80

    advisor_text = None
    if settings.ANTHROPIC_API_KEY:
        try:
            user_msg = f"""Analyse this data centre site investment assessment:

SITE: LUMI Supercomputer Site, Kajaani, Finland (64.22N, 27.72E)
ASSESSMENT YEAR: {year}
REAL-WORLD OUTCOME: LUMI EuroHPC supercomputer built here in 2021

SCORE: {result_year['score']}/100 ({result_year['grade']} - {result_year['grade_label']})

COMPONENTS (all from real satellite and climate data):
- Sentinel-1 SAR flood frequency (GEE 2017-2025): {result_year['raw_inputs']['flood_freq']} - contribution {result_year['components']['s1_flood_contribution']}/30
- Cooling Degree Days (Visual Crossing {year}): {result_year['raw_inputs']['cdd']} CDD/year - contribution {result_year['components']['cooling_cdd_contribution']}/25
- Drought index: {result_year['raw_inputs']['drought_index']} - contribution {result_year['components']['drought_contribution']}/20
- SYKE groundwater class: {result_year['raw_inputs']['groundwater_class']} (weight {result_year['raw_inputs']['groundwater_weight']}) - contribution {result_year['components']['groundwater_contribution']}/15
- Sentinel-2 NDWI: {result_year['raw_inputs']['ndwi']} - contribution {result_year['components']['surface_water_contribution']}/10

DATA SOURCES: {list(result_year['data_sources'].values())}"""

            client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            msg = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=600,
                system=_ADVISOR_SYSTEM,
                messages=[{"role": "user", "content": user_msg}],
            )
            advisor_text = msg.content[0].text
        except Exception as exc:
            advisor_text = f"Advisor unavailable: {exc}"

    return {
        "site":            "LUMI Supercomputer Site — CSC Data Centre, Kajaani",
        "location":        {"lat": LUMI_LAT, "lon": LUMI_LON},
        "year_scored":     year,
        "verified":        verified,
        "validation_note": "LUMI EuroHPC built 2021 — model correctly identified Prime Zone" if verified else "Score below threshold",
        "score_year":      result_year,
        "score_current":   result_now,
        "delta":           round(result_now["score"] - result_year["score"], 2),
        "timeline":        timeline,
        "advisor":         advisor_text,
        "methodology":     "S1 SAR x30% + CDD x25% + Drought x20% + SYKE GW x15% + S2 NDWI x10%",
    }
