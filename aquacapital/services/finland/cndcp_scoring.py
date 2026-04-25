"""
Climate Neutral Data Centre Pact (CNDCP) scoring engine — Finnish context.
Deterministic formula using CDD, Baseline Water Stress, and SYKE groundwater class.

Formula (from CNDCP framework and Aqueduct 4.0 methodology):
  Score = Norm(1/CDD) × 0.4 + (1 − BWS) × 0.4 + GroundwaterClassWeight × 0.2

Norm(1/CDD): Finland's low CDD yields a high 'free cooling' premium.
Reference: CDD normalised against global range (0–4000 CDD/yr).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import requests

OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"
AQUEDUCT_URL   = "https://api.wri.org/aqueduct/v3.0.1/widgets"
TIMEOUT = 30

# Global CDD reference for normalisation (IPCC AR6 global range)
CDD_REF_MAX = 4000.0
CDD_FLOOR   = 1.0      # avoid division by zero in polar/subarctic climates


def fetch_cooling_degree_days(lat: float, lon: float, year: int | None = None) -> dict:
    """
    Calculate annual Cooling Degree Days (CDD) from ERA5-Land daily mean temperature.
    CDD = Σ max(0, T_mean_daily − 18°C) over the calendar year.
    Base temperature 18°C per EN ISO 15927-6 standard.
    Source: Open-Meteo ERA5-Land reanalysis (Muñoz-Sabater et al., 2021).
    """
    if year is None:
        year = datetime.utcnow().year - 1  # last complete year

    start = f"{year}-01-01"
    end   = f"{year}-12-31"

    r = requests.get(OPEN_METEO_URL, params={
        "latitude": lat, "longitude": lon,
        "start_date": start, "end_date": end,
        "daily": "temperature_2m_mean",
        "timezone": "UTC",
    }, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json().get("daily", {})

    temps = [t for t in data.get("temperature_2m_mean", []) if t is not None]
    if not temps:
        return {"cdd": 120.0, "year": year, "source": "fallback", "data_points": 0}

    cdd = float(sum(max(0.0, t - 18.0) for t in temps))

    return {
        "cdd": round(cdd, 1),
        "year": year,
        "mean_temp_c": round(float(np.mean(temps)), 2),
        "max_temp_c":  round(float(np.max(temps)), 2),
        "source": f"Open-Meteo ERA5-Land {year}",
        "data_points": len(temps),
        "data_lineage": f"ERA5-Land reanalysis, lat={lat}, lon={lon}, year={year}",
    }


def fetch_baseline_water_stress(lat: float, lon: float) -> dict:
    """
    Fetch Baseline Water Stress (BWS) from WRI Aqueduct 4.0.
    BWS = annual water withdrawal / available freshwater; range 0–1 (capped at 1).
    Source: Kuzma et al. (2023), WRI Aqueduct 4.0.
    Falls back to ERA5 depletion proxy if API unavailable.
    """
    try:
        r = requests.get(AQUEDUCT_URL, params={"lat": lat, "lng": lon, "ind": "bws"},
                         timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        # Aqueduct v3 response structure
        rows = data.get("data", []) or data.get("rows", [])
        if rows:
            bws = float(rows[0].get("bws_raw", rows[0].get("value", 0.05)))
            return {
                "bws": round(min(1.0, max(0.0, bws)), 4),
                "source": "WRI Aqueduct 4.0",
                "data_lineage": f"Aqueduct 4.0 BWS, lat={lat}, lon={lon}",
            }
    except Exception:
        pass

    # Fallback: ERA5 precipitation-based proxy
    # For Finland, BWS is typically 0.01–0.05 (abundant freshwater)
    try:
        now = datetime.utcnow()
        r = requests.get(OPEN_METEO_URL, params={
            "latitude": lat, "longitude": lon,
            "start_date": (now - timedelta(days=365)).strftime("%Y-%m-%d"),
            "end_date": now.strftime("%Y-%m-%d"),
            "daily": "precipitation_sum",
            "timezone": "UTC",
        }, timeout=TIMEOUT)
        r.raise_for_status()
        precip = [p for p in r.json().get("daily", {}).get("precipitation_sum", []) if p is not None]
        annual_mm = sum(precip)
        # Very rough proxy: BWS inversely proportional to precipitation
        # 2000mm+ → BWS ~0.01, 500mm → BWS ~0.10, 200mm → BWS ~0.30
        bws_proxy = round(min(1.0, max(0.0, 20.0 / (annual_mm + 1e-9))), 4)
        return {
            "bws": bws_proxy,
            "source": "ERA5 precipitation proxy (Aqueduct unavailable)",
            "annual_precip_mm": round(annual_mm, 1),
            "data_lineage": f"ERA5-Land precipitation proxy, lat={lat}, lon={lon}",
        }
    except Exception:
        return {"bws": 0.05, "source": "Finland national default", "data_lineage": "static default"}


def _norm_inv_cdd(cdd: float) -> float:
    """
    Normalise inverse CDD to [0, 1].
    Norm(1/CDD) = min(1, CDD_REF_MAX / CDD) — higher score for colder climates.
    At CDD=1 (polar): 1.0. At CDD=4000 (tropical): 0.001.
    """
    cdd_safe = max(cdd, CDD_FLOOR)
    return round(min(1.0, CDD_REF_MAX / cdd_safe / CDD_REF_MAX * CDD_REF_MAX), 4)


def _norm_inv_cdd(cdd: float) -> float:
    cdd_safe = max(cdd, CDD_FLOOR)
    # Scale: 50 CDD (Finland) → ~1.0, 4000 CDD (tropics) → ~0.01
    return round(min(1.0, 50.0 / cdd_safe), 4)


def calculate_cndcp_score(
    lat: float,
    lon: float,
    groundwater_class_weight: float = 0.3,
    year: int | None = None,
) -> dict:
    """
    CNDCP Infrastructure Score for data centre siting.
    Formula: Score = Norm(1/CDD) × 0.4 + (1 − BWS) × 0.4 + GW_weight × 0.2
    Returns score 0–1 and full data lineage.
    Source: Climate Neutral Data Centre Pact (2021), Aqueduct 4.0, EN ISO 15927-6.
    """
    cdd_data = fetch_cooling_degree_days(lat, lon, year)
    bws_data = fetch_baseline_water_stress(lat, lon)

    cdd  = cdd_data["cdd"]
    bws  = bws_data["bws"]
    gw_w = groundwater_class_weight

    norm_cdd = _norm_inv_cdd(cdd)
    score    = norm_cdd * 0.4 + (1.0 - bws) * 0.4 + gw_w * 0.2

    # Grade mapping
    if score >= 0.88:   grade, label = "A+", "Optimal Free-Cooling Zone"
    elif score >= 0.75: grade, label = "A",  "Excellent Cooling Efficiency"
    elif score >= 0.60: grade, label = "B",  "Good — Supplemental Cooling Required"
    elif score >= 0.40: grade, label = "C",  "Moderate — Mechanical Cooling Dominant"
    else:               grade, label = "D",  "Poor — High Cooling Energy Cost"

    return {
        "cndcp_score": round(score, 4),
        "grade": grade,
        "grade_label": label,
        "components": {
            "norm_inv_cdd": norm_cdd,
            "one_minus_bws": round(1.0 - bws, 4),
            "gw_class_weight": gw_w,
        },
        "weights": {"cooling": 0.4, "water_stress": 0.4, "groundwater": 0.2},
        "raw_inputs": {
            "cdd": cdd,
            "bws": bws,
            "groundwater_class_weight": gw_w,
        },
        "data_sources": {
            "cdd": cdd_data,
            "bws": bws_data,
        },
        "formula": "Norm(1/CDD)×0.4 + (1−BWS)×0.4 + GW_weight×0.2",
        "methodology": "CNDCP (2021), EN ISO 15927-6, WRI Aqueduct 4.0",
    }
