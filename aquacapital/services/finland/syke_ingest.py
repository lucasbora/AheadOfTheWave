"""
SYKE (Finnish Environment Institute) data ingestion.
All services are public ArcGIS REST endpoints — no API key required.
Coordinate input: WGS84 (EPSG:4326). SYKE data is natively in ETRS-TM35FIN
(EPSG:3067) but the REST services accept inSR=4326 for point queries.

Source datasets:
  - Tulvavaarakartat: flood hazard zones (20/50/100/250/1000-year return periods)
    https://paikkatieto.ymparisto.fi/arcgis/rest/services/Tulvat/Tulvavaarakartat/MapServer
  - SYKE_Pohjavesi: groundwater classification (Class 1A, 1B, 2)
    https://paikkatieto.ymparisto.fi/arcgis/rest/services/SYKE/SYKE_Pohjavesi/MapServer
  - SYKE_Jarvet: lake registry with surface area and depth
    https://paikkatieto.ymparisto.fi/arcgis/rest/services/SYKE/SYKE_Jarvet/MapServer
  - SYKE_Merijaotus: marine area divisions (coastal expansion support)
    https://paikkatieto.ymparisto.fi/arcgis/rest/services/SYKE/SYKE_Merijaotus/MapServer
"""

from __future__ import annotations

import math
import requests

SYKE_BASE = "https://paikkatieto.ymparisto.fi/arcgis/rest/services"
TIMEOUT = 20

# Return period layers in Tulvavaarakartat MapServer
FLOOD_LAYERS = {
    50:   0,   # 1-in-50-year flood zone
    100:  1,   # 1-in-100-year flood zone
    250:  2,   # 1-in-250-year flood zone
}

# Groundwater classification layers
GW_LAYERS = {
    "1A": 0,   # Class 1A — most critical for water supply
    "1B": 1,   # Class 1B — important for water supply
    "2":  2,   # Class 2  — significant for local supply
}

# Groundwater class → CNDCP cooling weight
GW_CLASS_WEIGHTS = {
    "1A": 1.0,
    "1B": 0.9,
    "2":  0.7,
    None: 0.3,
}


def _syke_point_query(service: str, layer: int, lat: float, lon: float,
                      out_fields: str = "*", radius_m: int = 5000) -> list[dict]:
    url = f"{SYKE_BASE}/{service}/MapServer/{layer}/query"
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "spatialRel": "esriSpatialRelIntersects",
        "inSR": "4326",
        "outFields": out_fields,
        "returnGeometry": "false",
        "f": "json",
        "distance": radius_m,
        "units": "esriSRUnit_Meter",
        "resultRecordCount": 10,
    }
    r = requests.get(url, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json().get("features", [])


def fetch_flood_hazard_zones(lat: float, lon: float) -> dict:
    """
    Query SYKE Tulvavaarakartat for flood zone membership at point.
    Returns which return-period flood zones contain this location.
    Source: SYKE Tulvavaarakartat MapServer, dataset ID SYKE_TULVA_2023.
    """
    result: dict[str, object] = {
        "in_50yr_zone": False,
        "in_100yr_zone": False,
        "in_250yr_zone": False,
        "flood_zone_label": "None",
        "syke_source": "SYKE Tulvavaarakartat MapServer",
        "data_lineage": [],
    }

    worst = None
    for rp, layer in FLOOD_LAYERS.items():
        try:
            features = _syke_point_query("Tulvat/Tulvavaarakartat", layer, lat, lon)
            if features:
                key = f"in_{rp}yr_zone"
                result[key] = True
                worst = rp
                attrs = features[0].get("attributes", {})
                result["data_lineage"].append({
                    "return_period_yr": rp,
                    "layer": layer,
                    "attributes": attrs,
                    "source": f"SYKE Tulvavaarakartat layer {layer}",
                })
        except Exception as exc:
            result["data_lineage"].append({"return_period_yr": rp, "error": str(exc)})

    if worst:
        result["flood_zone_label"] = f"{worst}-year flood zone"
    return result


def fetch_groundwater_class(lat: float, lon: float) -> dict:
    """
    Query SYKE Pohjavesialueet for groundwater classification at point.
    Class 1A/1B = essential for water supply, Class 2 = important.
    Source: SYKE Pohjavesialueet, Finnish Groundwater Act (Pohjavesiasetus 341/2015).
    """
    result: dict[str, object] = {
        "groundwater_class": None,
        "class_weight": GW_CLASS_WEIGHTS[None],
        "area_name": None,
        "syke_source": "SYKE SYKE_Pohjavesi MapServer",
        "data_lineage": [],
    }

    for cls, layer in GW_LAYERS.items():
        try:
            features = _syke_point_query("SYKE/SYKE_Pohjavesi", layer, lat, lon)
            if features:
                attrs = features[0].get("attributes", {})
                result["groundwater_class"] = cls
                result["class_weight"] = GW_CLASS_WEIGHTS[cls]
                result["area_name"] = (
                    attrs.get("NIMI") or attrs.get("NimiSuomi") or f"Pohjavesialue {cls}"
                )
                result["data_lineage"].append({
                    "class": cls,
                    "layer": layer,
                    "attributes": attrs,
                    "source": f"SYKE Pohjavesialueet layer {layer}",
                })
                break  # highest-priority class found
        except Exception as exc:
            result["data_lineage"].append({"class": cls, "error": str(exc)})

    return result


def fetch_lake_depth(lat: float, lon: float, radius_m: int = 10000) -> dict:
    """
    Query SYKE lake registry for nearest lake depth and surface area.
    Used for heat exchange capacity and water intake viability assessment.
    Source: SYKE Järvirekisteri (Lake Register), updated annually.
    """
    result: dict[str, object] = {
        "nearest_lake_name": None,
        "max_depth_m": None,
        "mean_depth_m": None,
        "surface_area_km2": None,
        "heat_exchange_viable": False,
        "syke_source": "SYKE SYKE_Jarvet MapServer",
        "data_lineage": [],
    }

    try:
        features = _syke_point_query("SYKE/SYKE_Jarvet", 0, lat, lon,
                                     out_fields="NIMI,SUURIN_SYVYYS,KESKISYVYYS,PINTA_ALA",
                                     radius_m=radius_m)
        if features:
            attrs = features[0].get("attributes", {})
            max_d = attrs.get("SUURIN_SYVYYS") or attrs.get("MaxDepth")
            mean_d = attrs.get("KESKISYVYYS") or attrs.get("MeanDepth")
            area = attrs.get("PINTA_ALA") or attrs.get("Area_km2")

            result["nearest_lake_name"] = attrs.get("NIMI") or attrs.get("Name")
            result["max_depth_m"] = float(max_d) if max_d else None
            result["mean_depth_m"] = float(mean_d) if mean_d else None
            result["surface_area_km2"] = float(area) if area else None
            # Viable for heat exchange if mean depth > 5m (thermocline stable)
            result["heat_exchange_viable"] = bool(mean_d and float(mean_d) > 5.0)
            result["data_lineage"].append({
                "source": "SYKE Järvirekisteri layer 0",
                "attributes": attrs,
            })
    except Exception as exc:
        result["data_lineage"].append({"error": str(exc)})

    return result


def fetch_marine_divisions(lat: float, lon: float) -> dict:
    """
    Query SYKE marine area divisions — supports coastal expansion logic.
    Returns coastal zone type; for inland locations like Kajaani returns 'inland'.
    Source: SYKE SYKE_Merijaotus MapServer.
    """
    result: dict[str, object] = {
        "is_coastal": False,
        "marine_zone": "inland",
        "syke_source": "SYKE SYKE_Merijaotus MapServer",
    }

    try:
        features = _syke_point_query("SYKE/SYKE_Merijaotus", 0, lat, lon)
        if features:
            attrs = features[0].get("attributes", {})
            result["is_coastal"] = True
            result["marine_zone"] = attrs.get("MERIALUE") or attrs.get("Zone") or "coastal"
    except Exception:
        pass  # Inland location — expected to return no marine features

    return result


def fetch_all_syke(lat: float, lon: float) -> dict:
    """Fetch all SYKE datasets for a location and return as a combined dict."""
    return {
        "flood_hazard": fetch_flood_hazard_zones(lat, lon),
        "groundwater": fetch_groundwater_class(lat, lon),
        "lake_depth": fetch_lake_depth(lat, lon),
        "marine": fetch_marine_divisions(lat, lon),
    }
