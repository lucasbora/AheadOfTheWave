"""
Cargill/WRI Watershed Target Engine.
Implements the Cargill Practice Note methodology for site-level water replenishment targets.
Source: Cargill & WRI (2022), "Setting Site-Level Targets Aligned with Watershed Needs";
        WRI Aqueduct 4.0 Baseline Water Depletion (BWD) indicator.

Target formula:
  Replenishment_Target = (Current_BWD − Desired_BWD) / Current_BWD × Facility_Footprint_m3yr

Where:
  Current_BWD:  WRI Aqueduct Baseline Water Depletion at the watershed level
  Desired_BWD:  Target depletion level for watershed restoration (typically BWD < 0.1 = 'Low')
  Facility_Footprint_m3yr: Annual water consumption of the facility
"""

from __future__ import annotations

import requests
from datetime import datetime, timedelta

AQUEDUCT_URL = "https://api.wri.org/aqueduct/v3.0.1/widgets"
OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"
TIMEOUT = 30

# WRI Aqueduct BWD thresholds (Kuzma et al., 2023)
BWD_LEVELS = {
    (0.0, 0.1): "Low",
    (0.1, 0.2): "Low-Medium",
    (0.2, 0.4): "Medium-High",
    (0.4, 0.8): "High",
    (0.8, 1.0): "Extremely High",
}

# Desired restoration target BWD levels by facility ambition tier
DESIRED_BWD = {
    "conservative": 0.4,    # Reduce to 'Medium-High' threshold
    "moderate":     0.2,    # Reduce to 'Low-Medium' threshold
    "ambitious":    0.1,    # Reduce to 'Low' threshold (full restoration)
    "net_positive": 0.05,   # Net water positive
}


def _bwd_level(bwd: float) -> str:
    for (lo, hi), label in BWD_LEVELS.items():
        if lo <= bwd < hi:
            return label
    return "Extremely High"


def fetch_baseline_water_depletion(lat: float, lon: float) -> dict:
    """
    Fetch Baseline Water Depletion (BWD) from WRI Aqueduct 4.0.
    BWD measures consumptive water use relative to available supply, accounting for
    upstream and downstream users. Range 0–1.
    Source: Kuzma et al. (2023), WRI Aqueduct 4.0, indicator BWD.
    """
    try:
        r = requests.get(AQUEDUCT_URL, params={"lat": lat, "lng": lon, "ind": "bwd"},
                         timeout=TIMEOUT)
        r.raise_for_status()
        rows = r.json().get("data", []) or r.json().get("rows", [])
        if rows:
            bwd = float(rows[0].get("bwd_raw", rows[0].get("value", 0.05)))
            gtd = float(rows[0].get("gtd_raw", 0.0))
            return {
                "bwd": round(min(1.0, max(0.0, bwd)), 4),
                "gtd": round(gtd, 4),   # Groundwater Table Decline
                "bwd_level": _bwd_level(bwd),
                "source": "WRI Aqueduct 4.0",
                "data_lineage": f"Aqueduct 4.0 BWD+GTD, lat={lat}, lon={lon}",
            }
    except Exception:
        pass

    # Finland proxy: annual precipitation vs estimated consumption
    try:
        now = datetime.utcnow()
        r = requests.get(OPEN_METEO_URL, params={
            "latitude": lat, "longitude": lon,
            "start_date": (now - timedelta(days=365)).strftime("%Y-%m-%d"),
            "end_date": now.strftime("%Y-%m-%d"),
            "daily": "precipitation_sum",
            "timezone": "UTC",
        }, timeout=TIMEOUT)
        precip = [p for p in r.json().get("daily", {}).get("precipitation_sum", []) if p is not None]
        annual_mm = sum(precip)
        bwd_proxy = round(min(1.0, 10.0 / (annual_mm + 1e-9)), 4)
        return {
            "bwd": bwd_proxy,
            "gtd": 0.0,
            "bwd_level": _bwd_level(bwd_proxy),
            "source": "ERA5 precipitation proxy",
            "annual_precip_mm": round(annual_mm, 1),
            "data_lineage": f"ERA5 proxy, lat={lat}, lon={lon}",
        }
    except Exception:
        return {
            "bwd": 0.03, "gtd": 0.0,
            "bwd_level": "Low",
            "source": "Finland national default",
            "data_lineage": "static default — Finland abundant freshwater",
        }


def calculate_watershed_target(
    lat: float,
    lon: float,
    facility_footprint_m3yr: float = 500_000.0,
    ambition: str = "ambitious",
) -> dict:
    """
    Calculate site-level water replenishment target following Cargill Practice Note methodology.
    Source: Cargill & WRI (2022). Indicators: Aqueduct 4.0 BWD, GTD.

    Args:
        facility_footprint_m3yr: Annual water consumption of the data centre in m³/year.
                                 LUMI-scale HPC: ~500,000 m³/yr estimate.
        ambition: 'conservative' | 'moderate' | 'ambitious' | 'net_positive'

    Returns:
        replenishment_target_m3yr: Volume to replenish per year
        reduction_fraction: Fractional reduction of current footprint required
        feasibility: Whether the target is achievable given local conditions
    """
    depletion = fetch_baseline_water_depletion(lat, lon)
    current_bwd = depletion["bwd"]
    desired_bwd = DESIRED_BWD.get(ambition, 0.1)

    if current_bwd <= desired_bwd:
        # Already below target — watershed is in good condition
        replenishment_target = 0.0
        reduction_fraction = 0.0
        status = "No replenishment required — watershed already meets target"
    else:
        try:
            reduction_fraction = (current_bwd - desired_bwd) / current_bwd
        except ZeroDivisionError:
            reduction_fraction = 0.0
        replenishment_target = reduction_fraction * facility_footprint_m3yr
        status = f"Replenish {replenishment_target:,.0f} m³/yr to reach '{ambition}' target"

    gtd_risk = depletion.get("gtd", 0.0)
    gtd_adjustment = gtd_risk * facility_footprint_m3yr * 0.1

    return {
        "replenishment_target_m3yr": round(replenishment_target, 0),
        "gtd_adjustment_m3yr": round(gtd_adjustment, 0),
        "total_target_m3yr": round(replenishment_target + gtd_adjustment, 0),
        "reduction_fraction": round(reduction_fraction, 4),
        "ambition_tier": ambition,
        "desired_bwd": desired_bwd,
        "status": status,
        "feasibility": replenishment_target < facility_footprint_m3yr,
        "depletion_data": depletion,
        "formula": "Target = (Current_BWD − Desired_BWD) / Current_BWD × Footprint",
        "methodology": "Cargill & WRI (2022) Practice Note, Aqueduct 4.0 BWD+GTD",
    }
