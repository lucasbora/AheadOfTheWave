"""
Location data orchestrator.
Fetches real, location-specific risk inputs from external APIs.
Priority: user override > real API data > Romania national defaults.
All external calls are wrapped in try/except so a single source failure
never blocks the scoring pipeline.
"""

from __future__ import annotations

import logging

from config import ROMANIA_DEFAULTS
from services.data_sources.climate import fetch_drought_indices, fetch_flood_metrics
from services.data_sources.water_quality import fetch_water_quality

logger = logging.getLogger(__name__)


def fetch_location_inputs(lat: float, lon: float) -> dict:
    """
    Fetch real risk inputs for a location from all available data sources.
    Returns a dict with the same keys as ROMANIA_DEFAULTS.
    Any source that fails silently falls back to the Romania default for that key.
    """
    result: dict = {}
    log_sources: list[str] = []
    log_failures: list[str] = []

    # --- Climate: drought indices + groundwater + flood metrics ---
    try:
        drought = fetch_drought_indices(lat, lon)
        result.update(drought)
        log_sources.append("Open-Meteo ERA5 (drought/groundwater)")
    except Exception as exc:
        logger.warning("Climate fetch failed for (%s, %s): %s", lat, lon, exc)
        log_failures.append(f"climate: {exc}")

    try:
        floods = fetch_flood_metrics(lat, lon)
        result.update(floods)
        log_sources.append("Open-Meteo ERA5 (flood events/depth)")
    except Exception as exc:
        logger.warning("Flood metrics fetch failed for (%s, %s): %s", lat, lon, exc)
        log_failures.append(f"floods: {exc}")

    # --- Water quality from EEA WISE ---
    try:
        wq = fetch_water_quality(lat, lon)
        result["bod_mg_per_l"]      = wq["bod_mg_per_l"]
        result["nitrate_mg_per_l"]  = wq["nitrate_mg_per_l"]
        result["salinity_tds_mg_l"] = wq["salinity_tds_mg_l"]
        result["_wq_source"] = f"EEA WISE WFD ({wq['wfd_status']} — {wq['station_name']})"
        log_sources.append(result["_wq_source"])
    except Exception as exc:
        logger.warning("Water quality fetch failed for (%s, %s): %s", lat, lon, exc)
        log_failures.append(f"water_quality: {exc}")

    # Fill any missing keys from Romania defaults
    for key, default_val in ROMANIA_DEFAULTS.items():
        if key not in result:
            result[key] = default_val

    result["_data_sources"] = log_sources
    result["_fallbacks"]    = log_failures

    if log_sources:
        logger.info("Real data fetched for (%s, %s): %s", lat, lon, ", ".join(log_sources))
    if log_failures:
        logger.info("Fell back to Romania defaults for: %s", ", ".join(log_failures))

    return result


def resolve(req_val, key: str, real_data: dict) -> object:
    """
    Three-tier priority resolver:
    1. User override in request body (not None)
    2. Real API value from location_data
    3. Romania national default
    """
    if req_val is not None:
        return req_val
    if key in real_data and not key.startswith("_"):
        return real_data[key]
    return ROMANIA_DEFAULTS.get(key)
