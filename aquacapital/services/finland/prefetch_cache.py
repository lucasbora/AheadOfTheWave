"""
Finland pre-fetch cache — instant lookup from data/finland_grid.json.
Replaces all live API calls for Finnish coordinates during app scoring.
"""

from __future__ import annotations

import json
import math
import os
from functools import lru_cache

CACHE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "finland_grid.json"
)

# Finland bounding box
FI_LAT_MIN, FI_LAT_MAX = 59.5, 70.5
FI_LON_MIN, FI_LON_MAX = 19.0, 32.0


def is_finland(lat: float, lon: float) -> bool:
    return FI_LAT_MIN <= lat <= FI_LAT_MAX and FI_LON_MIN <= lon <= FI_LON_MAX


@lru_cache(maxsize=1)
def _load_grid() -> dict:
    """Load the pre-fetch JSON once and keep in memory."""
    if not os.path.exists(CACHE_PATH):
        return {}
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("points", {})


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def lookup_nearest(lat: float, lon: float, max_km: float = 25.0) -> dict | None:
    """
    Return the nearest pre-fetched point within max_km km.
    Returns None if cache is empty or no point is within range.
    """
    grid = _load_grid()
    if not grid:
        return None

    best_key  = None
    best_dist = float("inf")

    for key, point in grid.items():
        d = _haversine_km(lat, lon, point["lat"], point["lon"])
        if d < best_dist:
            best_dist = d
            best_key  = key

    if best_dist > max_km:
        return None

    point = grid[best_key].copy()
    point["_cache_distance_km"] = round(best_dist, 2)
    point["_cache_key"]         = best_key
    return point


def get_risk_inputs(lat: float, lon: float) -> dict | None:
    """
    Return risk_inputs dict from prefetch cache for use in location_data.
    Returns None if no cache data available for this location.
    """
    point = lookup_nearest(lat, lon)
    if point is None:
        return None
    return point.get("risk_inputs")


def get_syke_data(lat: float, lon: float) -> dict | None:
    """Return SYKE data from prefetch cache."""
    point = lookup_nearest(lat, lon)
    if point is None:
        return None
    return point.get("syke")


def get_sentinel_bands(lat: float, lon: float) -> dict | None:
    """Return Sentinel band values from prefetch cache."""
    point = lookup_nearest(lat, lon)
    if point is None:
        return None
    bands = point.get("sentinel", {})
    if not any(v is not None for v in bands.values()):
        return None
    return bands


def get_cndcp_data(lat: float, lon: float) -> dict | None:
    """Return pre-computed CNDCP score from cache."""
    point = lookup_nearest(lat, lon)
    if point is None:
        return None
    return point.get("cndcp")


def cache_status() -> dict:
    """Return metadata about the current prefetch cache."""
    if not os.path.exists(CACHE_PATH):
        return {"status": "empty", "points": 0, "path": CACHE_PATH}
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    meta = data.get("metadata", {})
    return {
        "status":        "ready" if meta.get("fetched_points", 0) > 0 else "empty",
        "fetched_points": meta.get("fetched_points", 0),
        "total_points":   meta.get("total_points", 0),
        "grid_step_km":   meta.get("grid_step_km"),
        "radius_km":      meta.get("radius_km"),
        "last_updated":   meta.get("last_updated"),
        "path":           CACHE_PATH,
    }
