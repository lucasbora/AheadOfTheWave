"""
Frontend adapter — maps Emergent frontend's expected endpoint URLs and response
shapes to the existing AquaCapital FastAPI logic.

Frontend expects:          Backend has:
POST /api/v1/score/investment     POST /api/v1/investment/grade
GET  /api/v1/explanation/investment   POST /api/v1/explanation/investment
POST /api/v1/heatmap              GET  /api/v1/investment/heatmap-points
POST /api/v1/finland/oracle       GET  /api/v1/finland/validate/kajaani
POST /api/v1/legal/vesilaki       POST /api/v1/finland/legal-assessment
GET  /api/v1/lineage              (new — derived from location_data)
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from api.routes.investment import _build_grade_response
from models.schemas import InvestmentGradeRequest
from services.ai_explainer import explain_investment_grade
from services.finland.syke_ingest import fetch_all_syke
from services.finland.cndcp_scoring import calculate_cndcp_score
from services.finland.watershed_targets import calculate_watershed_target
from services.finland.galileo_subsidence import simulate_galileo_has_monitoring
from services.finland.legal_agent import run_legal_assessment
from services.location_data import fetch_location_inputs

router = APIRouter(tags=["frontend"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ScoreRequest(BaseModel):
    lat: float
    lon: float
    user_type: str = "data_center"
    location_name: Optional[str] = None
    buffer_km: float = 5.0
    green_band: Optional[float] = None
    nir_band: Optional[float] = None
    swir_band: Optional[float] = None
    vv_band: Optional[float] = None
    vh_band: Optional[float] = None


class HeatmapRequest(BaseModel):
    bbox: dict        # {n, s, e, w}
    grid_step_km: float = 10.0
    user_type: str = "data_center"


class OracleRequest(BaseModel):
    lat: float = 64.22
    lon: float = 27.72
    location_name: Optional[str] = None


class VesilakiRequest(BaseModel):
    syke: dict        # {lat, lon, flood_zone, groundwater_class, abstraction_m3_day}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CATEGORY_WEIGHTS = {
    "water_availability": 25.0,
    "drought":            15.0,
    "flooding":           35.0,
    "water_quality":      25.0,
}
_CATEGORY_KEYS = {
    "water_availability": "water_availability_risk",
    "drought":            "drought_risk",
    "flooding":           "flood_risk",
    "water_quality":      "water_quality_risk",
}


def _risk_categories(breakdown: dict) -> list[dict]:
    """
    Build risk_categories array from physical sub-scores.
    RiskBreakdownPanel reads: name/key, score_1_5, contribution_pct.
    """
    cats = []
    for cat, weight in _CATEGORY_WEIGHTS.items():
        norm = breakdown.get(_CATEGORY_KEYS[cat], 0.0)
        score_1_5 = max(1, min(5, round(norm * 4) + 1))
        cats.append({
            "name":             cat,
            "key":              cat,
            "score_1_5":        score_1_5,
            "contribution_pct": weight,
            "normalized":       norm,
        })
    return cats


def _normalise_breakdown(raw: dict) -> dict:
    """
    InvestmentGradeCard expects: physical_risk, regulatory_risk, compliance, ead.
    Our engine returns: physical_risk_contribution, regulatory_risk_contribution, etc.
    """
    return {
        "physical_risk":   raw.get("physical_risk_contribution", 0.0),
        "regulatory_risk": raw.get("regulatory_risk_contribution", 0.0),
        "compliance":      raw.get("compliance_contribution", 0.0),
        "ead":             raw.get("ead_contribution", 0.0),
        **{k: v for k, v in raw.items()
           if k not in {"physical_risk_contribution", "regulatory_risk_contribution",
                        "compliance_contribution", "ead_contribution"}},
    }


def _flatten_sat(sm) -> dict:
    """Flatten SatelliteMetadata into the shape RiskBreakdownPanel expects."""
    if hasattr(sm, "model_dump"):
        sm = sm.model_dump()
    if not sm:
        return {}
    return {
        "tile_id":          sm.get("tile_id"),
        "acquisition_date": sm.get("acquisition_date"),
        "cloud_cover":      sm.get("cloud_cover_pct"),
        "source":           sm.get("source", "ESA Copernicus"),
        "note":             sm.get("note"),
        "s1_date":          sm.get("s1_acquisition_date"),
        "s1_mode":          sm.get("s1_mode"),
    }


def _grade_response_to_dict(gr) -> dict:
    d = gr.model_dump() if hasattr(gr, "model_dump") else dict(gr)
    raw_breakdown = d.get("breakdown", {})
    d["breakdown"] = _normalise_breakdown(raw_breakdown)
    d["label"]     = d.get("grade_label", "")
    # Add risk_categories for RiskBreakdownPanel
    d["risk_categories"] = _risk_categories(raw_breakdown)
    # Add fsi at top level for RiskBreakdownPanel
    d["fsi"] = raw_breakdown.get("fsi")
    # Flatten satellite_metadata into "satellite" key
    d["satellite"] = _flatten_sat(d.get("satellite_metadata"))
    return d


def _reshape_audit(audit: dict) -> dict:
    """
    Reshape Claude audit response to match ClaudeAuditPanel's expected field names:
      overall_assessment  → overall
      water_feasibility   → feasibility.water
      recommended_next_checks → next_checks (with .text from .check)
    """
    reshaped = dict(audit)

    # Feasibility pills
    reshaped["feasibility"] = {
        "water":   (audit.get("water_feasibility")   or {}).get("status", "unknown"),
        "cooling": (audit.get("cooling_feasibility") or {}).get("status", "unknown"),
        "permit":  (audit.get("permit_feasibility")  or {}).get("status", "unknown"),
    }

    # Overall assessment
    reshaped["overall"] = audit.get("overall_assessment") or audit.get("overall") or {}

    # Next checks — panel reads n.text or n.check
    raw_checks = audit.get("recommended_next_checks") or audit.get("next_checks") or []
    reshaped["next_checks"] = [
        {**c, "text": c.get("check") or c.get("text") or ""}
        for c in raw_checks
    ]

    return reshaped


# ---------------------------------------------------------------------------
# POST /api/v1/score/investment
# ---------------------------------------------------------------------------

@router.post("/api/v1/score/investment")
def score_investment(req: ScoreRequest) -> dict:
    """
    Investment grade scoring — called by Dashboard and Compare pages.
    For Finnish coordinates, injects prefetched Sentinel bands automatically
    so no manual ingest.py step is needed during the demo.
    """
    from services.finland.prefetch_cache import is_finland, get_sentinel_bands

    green, nir, swir, vv, vh = (
        req.green_band, req.nir_band, req.swir_band, req.vv_band, req.vh_band
    )

    # If no bands provided and we have prefetched Sentinel data, inject them
    if green is None and is_finland(req.lat, req.lon):
        bands = get_sentinel_bands(req.lat, req.lon)
        if bands:
            green = bands.get("green_band")
            nir   = bands.get("nir_band")
            swir  = bands.get("swir_band")
            vv    = bands.get("vv_band")
            vh    = bands.get("vh_band")

    ig_req = InvestmentGradeRequest(
        lat=req.lat, lon=req.lon,
        user_type=req.user_type,
        location_name=req.location_name,
        buffer_km=req.buffer_km,
        green_band=green, nir_band=nir, swir_band=swir,
        vv_band=vv, vh_band=vh,
    )
    gr = _build_grade_response(ig_req)
    return _grade_response_to_dict(gr)


# ---------------------------------------------------------------------------
# GET /api/v1/explanation/investment
# ---------------------------------------------------------------------------

@router.get("/api/v1/explanation/investment")
def explain_investment(
    lat: float = Query(...),
    lon: float = Query(...),
    user_type: str = Query(default="data_center"),
    location_name: Optional[str] = Query(default=None),
) -> dict:
    """Score then explain — called by Dashboard after scoring."""
    ig_req = InvestmentGradeRequest(lat=lat, lon=lon, user_type=user_type,
                                     location_name=location_name)
    gr = _build_grade_response(ig_req)
    grade_dict = _grade_response_to_dict(gr)
    raw_audit = explain_investment_grade(grade_dict, user_type, location_name)
    return _reshape_audit(raw_audit)


# ---------------------------------------------------------------------------
# POST /api/v1/heatmap
# ---------------------------------------------------------------------------

@router.post("/api/v1/heatmap")
def heatmap(req: HeatmapRequest) -> dict:
    """
    Grid scoring over bounding box.
    Points processed sequentially to avoid Open-Meteo 429 rate limiting.
    Coordinates clamped to valid WGS84 range — Leaflet can produce lon < -180.
    """
    bbox = req.bbox
    lat_min = float(bbox.get("s", bbox.get("lat_min", 0.0)))
    lat_max = float(bbox.get("n", bbox.get("lat_max", 1.0)))
    lon_min = float(bbox.get("w", bbox.get("lon_min", 0.0)))
    lon_max = float(bbox.get("e", bbox.get("lon_max", 1.0)))

    # Clamp to valid WGS84 — Leaflet wraps past ±180 when map panned
    lat_min = max(-90.0,  min(90.0,  lat_min))
    lat_max = max(-90.0,  min(90.0,  lat_max))
    lon_min = max(-180.0, min(180.0, lon_min))
    lon_max = max(-180.0, min(180.0, lon_max))

    # Ensure min < max after clamping
    if lat_min > lat_max: lat_min, lat_max = lat_max, lat_min
    if lon_min > lon_max: lon_min, lon_max = lon_max, lon_min

    center_lat = (lat_min + lat_max) / 2.0
    step_lat   = req.grid_step_km / 111.0
    step_lon   = req.grid_step_km / (111.0 * math.cos(math.radians(center_lat)) + 1e-9)

    # Build grid point list first
    grid: list[tuple[float, float]] = []
    lat = lat_min
    while lat <= lat_max and len(grid) < 25:
        lon = lon_min
        while lon <= lon_max and len(grid) < 25:
            grid.append((round(lat, 4), round(lon, 4)))
            lon += step_lon
        lat += step_lat

    # Score sequentially — prevents flooding Open-Meteo with parallel requests (429)
    # Cache means 2nd+ requests for nearby points are instant anyway
    points: list[dict] = []
    for pt_lat, pt_lon in grid:
        try:
            ig_req = InvestmentGradeRequest(
                lat=pt_lat, lon=pt_lon,
                user_type=req.user_type,
                location_name=f"{pt_lat},{pt_lon}",
            )
            gr = _build_grade_response(ig_req)
            d  = _grade_response_to_dict(gr)
            points.append({
                "lat": pt_lat,
                "lon": pt_lon,
                "score": d["score"],
                "grade": d["grade"],
                "grade_label": d["grade_label"],
                "location_name": d.get("location_name", ""),
            })
        except Exception:
            pass  # skip invalid points silently

    return {"points": points, "count": len(points)}


# ---------------------------------------------------------------------------
# POST /api/v1/finland/oracle
# ---------------------------------------------------------------------------

@router.post("/api/v1/finland/oracle")
def finland_oracle(req: OracleRequest) -> dict:
    """
    Full Kajaani Oracle backtest + SYKE + Galileo + Watershed.
    Returns the shape expected by FinlandOracle.jsx.
    """
    lat, lon = req.lat, req.lon

    syke_data  = fetch_all_syke(lat, lon)
    gw_w       = syke_data["groundwater"].get("class_weight", 0.3)

    # CNDCP 2015 (backtest)
    cndcp_2015    = calculate_cndcp_score(lat, lon, gw_w, year=2015)
    # CNDCP current
    current_year  = datetime.utcnow().year - 1
    cndcp_current = calculate_cndcp_score(lat, lon, gw_w, year=current_year)

    # Galileo subsidence
    galileo_raw = simulate_galileo_has_monitoring(lat, lon, abstraction_m3day=1500, monitoring_months=24)
    series = [
        {
            "month": r["month"],
            "gia_uplift": round(r["gia_contribution_mm"], 2),
            "net_displacement": round(r["cumulative_trend_mm"], 2),
        }
        for r in galileo_raw.get("monthly_readings", [])
    ]

    # Watershed
    ws = calculate_watershed_target(lat, lon, facility_footprint_m3yr=500_000, ambition="ambitious")

    # SYKE simplified
    flood    = syke_data.get("flood_hazard", {})
    gw       = syke_data.get("groundwater", {})
    lake     = syke_data.get("lake_depth", {})

    def _fmt_score(c: dict) -> dict:
        comp = c.get("components", {})
        return {
            "score":         c.get("cndcp_score", 0.0),
            "cndcp":         c.get("cndcp_score", 0.0),
            "norm_inv_cdd":  comp.get("norm_inv_cdd", 0.0),
            "one_minus_bws": comp.get("one_minus_bws", 0.0),
            "gw_class_weight": comp.get("gw_class_weight", gw_w),
            "grade":         c.get("grade", ""),
            "verified":      c.get("cndcp_score", 0.0) >= 0.90,
        }

    return {
        "scores": {
            "baseline_2015": _fmt_score(cndcp_2015),
            "current":       _fmt_score(cndcp_current),
        },
        "baseline_2015": _fmt_score(cndcp_2015),
        "current":       _fmt_score(cndcp_current),
        "verified":      cndcp_2015.get("cndcp_score", 0.0) >= 0.90,
        "galileo": {
            "series":      series,
            "alert_level": galileo_raw["alert"]["level"],
            "net_rate_mm_yr": galileo_raw.get("net_vertical_rate_mm_yr"),
            "gia_rate_mm_yr": galileo_raw.get("gia_uplift_rate_mm_yr"),
        },
        "watershed": {
            "reduction_fraction":   ws.get("reduction_fraction", 0.0),
            "replenishment_m3_year": ws.get("total_target_m3yr", 0.0),
            "status":               ws.get("status", ""),
        },
        "syke": {
            "flood_zone":        flood.get("flood_zone_label", "None"),
            "groundwater_class": gw.get("groundwater_class", "—"),
            "nearest_lake":      lake.get("nearest_lake_name", "—"),
            "lake_depth_m":      lake.get("mean_depth_m"),
            "abstraction_m3_day": 1500,
        },
        "data_lineage": [
            f"ERA5-Land CDD 2015: {cndcp_2015['data_sources']['cdd'].get('source', 'Open-Meteo')}",
            f"ERA5-Land CDD {current_year}: {cndcp_current['data_sources']['cdd'].get('source', 'Open-Meteo')}",
            f"BWS: {cndcp_2015['data_sources']['bws'].get('source', 'WRI Aqueduct 4.0')}",
            f"Groundwater: SYKE Pohjavesialueet class={gw.get('groundwater_class', 'N/A')}",
            "Galileo HAS: NKG2016LU GIA model (Vestøl et al., 2019) — simulated",
            "Watershed: Cargill/WRI Practice Note (2022)",
        ],
    }


# ---------------------------------------------------------------------------
# POST /api/v1/legal/vesilaki
# ---------------------------------------------------------------------------

@router.post("/api/v1/legal/vesilaki")
def legal_vesilaki(req: VesilakiRequest) -> dict:
    """Vesilaki 587/2011 legal assessment via Claude."""
    syke_arg = req.syke
    lat = syke_arg.get("lat", 64.22)
    lon = syke_arg.get("lon", 27.72)
    abstraction = syke_arg.get("abstraction_m3_day", 300.0)

    # Build SYKE data structure from what the frontend passes
    syke_data = {
        "flood_hazard": {
            "flood_zone_label": syke_arg.get("flood_zone", "None"),
            "in_100yr_zone": syke_arg.get("flood_zone", "None") != "None",
            "syke_source": "SYKE Tulvavaarakartat",
        },
        "groundwater": {
            "groundwater_class": syke_arg.get("groundwater_class"),
            "class_weight": 1.0 if (syke_arg.get("groundwater_class") or "").startswith("1") else 0.7,
            "syke_source": "SYKE Pohjavesialueet",
        },
        "lake_depth": {"nearest_lake_name": syke_arg.get("nearest_lake", "N/A")},
        "marine": {"is_coastal": False},
    }

    assessment = run_legal_assessment(lat, lon, syke_data, "data_center", abstraction)
    return {"assessment": assessment, "text": assessment, "legislation": "Vesilaki 587/2011"}


# ---------------------------------------------------------------------------
# GET /api/v1/lineage
# ---------------------------------------------------------------------------

@router.get("/api/v1/finland/prefetch-status")
def prefetch_status() -> dict:
    """Check how many Finland grid points are pre-fetched."""
    from services.finland.prefetch_cache import cache_status
    return cache_status()


@router.get("/api/v1/lineage")
def lineage(
    lat: float = Query(...),
    lon: float = Query(...),
    user_type: str = Query(default="data_center"),
) -> dict:
    """Data lineage for a location — called by DataLineageDrawer."""
    real = fetch_location_inputs(lat, lon)
    sources_raw = real.get("_data_sources", [])
    failures    = real.get("_fallbacks", [])

    sources = []
    for s in sources_raw:
        sources.append({
            "name":       s,
            "status":     "live",
            "confidence": "high",
            "fetch_date": datetime.utcnow().strftime("%Y-%m-%d"),
        })
    for f in failures:
        sources.append({
            "name":       f,
            "status":     "fallback",
            "confidence": "medium",
            "fetch_date": datetime.utcnow().strftime("%Y-%m-%d"),
        })

    # Always include satellite metadata sources
    sources += [
        {"name": "ESA Copernicus Sentinel-2 L2A", "status": "live", "confidence": "high",
         "dataset_id": "SENTINEL-2", "fetch_date": datetime.utcnow().strftime("%Y-%m-%d")},
        {"name": "ESA Copernicus Sentinel-1 GRD", "status": "live", "confidence": "high",
         "dataset_id": "SENTINEL-1", "fetch_date": datetime.utcnow().strftime("%Y-%m-%d")},
        {"name": "WWF Water Risk Filter v3.0", "status": "cached", "confidence": "high",
         "dataset_id": "WWF-WRF-3.0", "fetch_date": datetime.utcnow().strftime("%Y-%m-%d")},
        {"name": "WRI Aqueduct 4.0", "status": "live" if not failures else "fallback",
         "confidence": "high", "dataset_id": "WRI-AQ-4.0",
         "fetch_date": datetime.utcnow().strftime("%Y-%m-%d")},
    ]

    return {
        "sources": sources,
        "location": {"lat": lat, "lon": lon},
        "user_type": user_type,
        "generated_at": datetime.utcnow().isoformat(),
    }
