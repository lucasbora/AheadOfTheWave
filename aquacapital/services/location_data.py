"""
Location data orchestrator.
Fetches real, location-specific risk inputs from external APIs in parallel.
Priority: user override > real API data > Romania national defaults.

Key design decisions:
- Per-location threading lock: if score + explain fire simultaneously for the
  same coordinates, only ONE fetch runs; the second waits and reuses the result.
  This prevents duplicate Open-Meteo requests and 429 rate limit errors.
- 5-minute in-process cache: subsequent calls for the same location are instant.
- 28-second pool timeout: all three API calls run in parallel threads.
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import ROMANIA_DEFAULTS
from services.data_sources.climate import fetch_drought_indices, fetch_flood_metrics
from services.data_sources.water_quality import fetch_water_quality
from services.finland.prefetch_cache import is_finland, get_risk_inputs

logger = logging.getLogger(__name__)

_CACHE: dict[tuple, tuple[float, dict]] = {}
_CACHE_TTL = 300.0  # 5 minutes

# Per-location locks — prevents duplicate concurrent fetches for the same coords
_LOCKS: dict[tuple, threading.Lock] = {}
_LOCKS_META = threading.Lock()


def _cache_key(lat: float, lon: float) -> tuple:
    return (round(lat, 2), round(lon, 2))


def _get_lock(key: tuple) -> threading.Lock:
    with _LOCKS_META:
        if key not in _LOCKS:
            _LOCKS[key] = threading.Lock()
        return _LOCKS[key]


def fetch_location_inputs(lat: float, lon: float) -> dict:
    """
    Fetch real risk inputs for a location from Open-Meteo ERA5 and EEA WISE.
    All three API calls run in parallel threads (max 28s total).
    Results are cached 5 minutes per (lat, lon) rounded to 2 decimal places.

    Per-location lock: if two requests arrive simultaneously for the same
    coordinates (e.g. score + explain firing in parallel from the frontend),
    the second request blocks until the first completes, then reads from cache.
    """
    key = _cache_key(lat, lon)
    now = time.monotonic()

    # Fast path — cache hit (no lock needed)
    cached = _CACHE.get(key)
    if cached and now - cached[0] < _CACHE_TTL:
        logger.debug("Cache hit for (%s, %s)", lat, lon)
        return cached[1]

    # Finland prefetch — instant, no API calls
    if is_finland(lat, lon):
        prefetched = get_risk_inputs(lat, lon)
        if prefetched is not None:
            result = dict(prefetched)
            for k, v in ROMANIA_DEFAULTS.items():
                if k not in result:
                    result[k] = v
            result["_data_sources"] = ["Finland prefetch cache (offline)"]
            result["_fallbacks"]    = []
            result["_using_defaults"] = False
            logger.info("[location_data] prefetch hit for (%s, %s)", lat, lon)
            _CACHE[key] = (time.monotonic(), result)
            return result

    # Acquire per-location lock — second concurrent request waits here
    lock = _get_lock(key)
    with lock:
        # Re-check cache after acquiring lock (another thread may have populated it)
        cached = _CACHE.get(key)
        if cached and time.monotonic() - cached[0] < _CACHE_TTL:
            logger.debug("Cache hit (after lock) for (%s, %s)", lat, lon)
            return cached[1]

        result: dict = {}
        log_sources: list[str] = []
        log_failures: list[str] = []

        tasks = {
            "drought":       lambda: fetch_drought_indices(lat, lon),
            "floods":        lambda: fetch_flood_metrics(lat, lon),
            "water_quality": lambda: fetch_water_quality(lat, lon),
        }

        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(fn): name for name, fn in tasks.items()}
            for future in as_completed(futures, timeout=28):
                name = futures[future]
                try:
                    data = future.result(timeout=0)
                    if name == "drought":
                        result.update(data)
                        log_sources.append("Open-Meteo ERA5 (drought/groundwater)")
                    elif name == "floods":
                        result.update(data)
                        log_sources.append("Open-Meteo ERA5 (flood events/depth)")
                    elif name == "water_quality":
                        result["bod_mg_per_l"]      = data["bod_mg_per_l"]
                        result["nitrate_mg_per_l"]  = data["nitrate_mg_per_l"]
                        result["salinity_tds_mg_l"] = data["salinity_tds_mg_l"]
                        result["_wq_source"] = (
                            f"EEA WISE WFD ({data['wfd_status']} — {data['station_name']})"
                        )
                        log_sources.append(result["_wq_source"])
                except Exception as exc:
                    logger.warning(
                        "[location_data] %s failed for (%s, %s): %s",
                        name, lat, lon, exc,
                    )
                    log_failures.append(f"{name}: {type(exc).__name__}")

        # Fill missing keys from Romania defaults
        for k, default_val in ROMANIA_DEFAULTS.items():
            if k not in result:
                result[k] = default_val

        result["_data_sources"]    = log_sources
        result["_fallbacks"]       = log_failures
        result["_using_defaults"]  = len(log_failures) > 0

        if log_sources:
            logger.info(
                "[location_data] LIVE data for (%s,%s): %s",
                lat, lon, ", ".join(log_sources),
            )
        if log_failures:
            logger.warning(
                "[location_data] DEFAULTS used for (%s,%s): %s",
                lat, lon, ", ".join(log_failures),
            )

        _CACHE[key] = (time.monotonic(), result)
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
