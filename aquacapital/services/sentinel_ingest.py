"""
Sentinel-1 and Sentinel-2 data ingestion from CDSE OData API.
Handles Keycloak token acquisition with retry on expiry.
"""

from __future__ import annotations

import math
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from fastapi import HTTPException

from config import settings

TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu"
    "/auth/realms/CDSE/protocol/openid-connect/token"
)
SEARCH_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"

_cached_token: Optional[str] = None
_token_expiry: float = 0.0


def _get_token() -> str:
    """Obtain or reuse a Keycloak Bearer token. Refreshes automatically on expiry."""
    global _cached_token, _token_expiry

    if _cached_token and time.time() < _token_expiry - 30:
        return _cached_token

    response = requests.post(
        TOKEN_URL,
        data={
            "client_id": "cdse-public",
            "grant_type": "password",
            "username": settings.CDSE_USER,
            "password": settings.CDSE_PASSWORD,
        },
        timeout=30,
    )
    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"CDSE authentication failed: {response.status_code} {response.text[:200]}",
        )

    data = response.json()
    _cached_token = data["access_token"]
    _token_expiry = time.time() + data.get("expires_in", 600)
    return _cached_token


def _bbox_from_latlon(lat: float, lon: float, buffer_km: float) -> tuple[float, float, float, float]:
    """
    Build a bounding box around lat/lon using the Haversine-derived degree offsets.
    Returns (lon_min, lat_min, lon_max, lat_max).
    """
    delta_lat = buffer_km / 111.0
    delta_lon = buffer_km / (111.0 * math.cos(math.radians(lat)))
    return (
        lon - delta_lon,
        lat - delta_lat,
        lon + delta_lon,
        lat + delta_lat,
    )


def _build_wkt_polygon(bbox: tuple[float, float, float, float]) -> str:
    lon_min, lat_min, lon_max, lat_max = bbox
    return (
        f"POLYGON(("
        f"{lon_min} {lat_min},"
        f"{lon_max} {lat_min},"
        f"{lon_max} {lat_max},"
        f"{lon_min} {lat_max},"
        f"{lon_min} {lat_min}"
        f"))"
    )


def _search(filter_str: str, top: int = 1) -> list[dict]:
    """Execute OData search and return product list. Retries once on token expiry."""
    for attempt in range(2):
        token = _get_token()
        response = requests.get(
            SEARCH_URL,
            params={
                "$filter": filter_str,
                "$orderby": "ContentDate/Start desc",
                "$top": top,
                "$expand": "Attributes",
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        )
        if response.status_code == 401 and attempt == 0:
            global _cached_token
            _cached_token = None
            continue
        response.raise_for_status()
        return response.json().get("value", [])
    return []


def fetch_sentinel2_data(lat: float, lon: float, buffer_km: float = 5.0) -> dict:
    """
    Search CDSE for the most recent Sentinel-2 L2A product over the given location.
    Filters: cloud cover < 20%, last 60 days.
    Returns: product_id, acquisition_date, cloud_cover_pct, bounding_box, tile_id, download_url.
    Raises HTTPException 404 if no products found.
    """
    bbox = _bbox_from_latlon(lat, lon, buffer_km)
    wkt = _build_wkt_polygon(bbox)

    now = datetime.now(timezone.utc)
    date_start = (now - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    date_end = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    filter_str = " and ".join([
        "Collection/Name eq 'SENTINEL-2'",
        "Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' and att/OData.CSC.StringAttribute/Value eq 'S2MSI2A')",
        f"OData.CSC.Intersects(area=geography'SRID=4326;{wkt}')",
        f"ContentDate/Start gt {date_start}",
        f"ContentDate/Start lt {date_end}",
        "Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' and att/OData.CSC.DoubleAttribute/Value lt 20.00)",
    ])

    products = _search(filter_str, top=1)

    if not products:
        raise HTTPException(
            status_code=404,
            detail=f"No Sentinel-2 L2A products found within {buffer_km} km of ({lat}, {lon}) in the last 60 days with cloud cover < 20%.",
        )

    p = products[0]
    attrs = {a["Name"]: a.get("Value") for a in p.get("Attributes", [])}
    tile_id = p.get("Name", "")[-11:-5] if p.get("Name") else None

    return {
        "product_id": p["Id"],
        "acquisition_date": p.get("ContentDate", {}).get("Start", "")[:10],
        "cloud_cover_pct": attrs.get("cloudCover"),
        "bounding_box": list(bbox),
        "tile_id": tile_id,
        "download_url": f"https://catalogue.dataspace.copernicus.eu/odata/v1/Products({p['Id']})/$value",
    }


def fetch_sentinel1_data(lat: float, lon: float, buffer_km: float = 5.0) -> dict:
    """
    Search CDSE for the most recent Sentinel-1 GRD product over the given location.
    Last 60 days.

    SAR backscatter from Sentinel-1 enables flood detection even under cloud cover,
    critical for Romania's weather patterns where optical Sentinel-2 may be blocked
    for weeks at a time.

    Returns: product_id, acquisition_date, cloud_cover_pct, bounding_box, tile_id, download_url.
    Raises HTTPException 404 if no products found.
    """
    bbox = _bbox_from_latlon(lat, lon, buffer_km)
    wkt = _build_wkt_polygon(bbox)

    now = datetime.now(timezone.utc)
    date_start = (now - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    date_end = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    filter_str = " and ".join([
        "Collection/Name eq 'SENTINEL-1'",
        "Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' and att/OData.CSC.StringAttribute/Value eq 'GRD')",
        f"OData.CSC.Intersects(area=geography'SRID=4326;{wkt}')",
        f"ContentDate/Start gt {date_start}",
        f"ContentDate/Start lt {date_end}",
    ])

    products = _search(filter_str, top=1)

    if not products:
        raise HTTPException(
            status_code=404,
            detail=f"No Sentinel-1 GRD products found within {buffer_km} km of ({lat}, {lon}) in the last 60 days.",
        )

    p = products[0]
    tile_id = p.get("Name", "")[:16] if p.get("Name") else None

    return {
        "product_id": p["Id"],
        "acquisition_date": p.get("ContentDate", {}).get("Start", "")[:10],
        "cloud_cover_pct": None,
        "bounding_box": list(bbox),
        "tile_id": tile_id,
        "download_url": f"https://catalogue.dataspace.copernicus.eu/odata/v1/Products({p['Id']})/$value",
    }
