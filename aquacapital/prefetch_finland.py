"""
Finland data prefetch script.
Runs ONCE to build data/finland_grid.json — a permanent local cache of all
risk inputs, SYKE government data, CNDCP components, and Sentinel band values
for a 20 km grid within 100 km of Kajaani (LUMI Supercomputer site).

After running this script, the app never calls Open-Meteo, EEA, or SYKE for
Finnish locations — scoring is instant deterministic calculation only.

Usage:
    python prefetch_finland.py

Resumable: already-fetched points are skipped on re-run.
Estimated time: 30–60 minutes for ~78 grid points (sequential to avoid 429).
"""

import json
import math
import os
import time
from datetime import datetime, timezone

CENTER_LAT = 64.2245
CENTER_LON = 27.7177
RADIUS_KM  = 100.0
STEP_KM    = 20.0

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "data", "finland_grid.json")
SENTINEL_OUTPUT = os.path.join(
    os.path.dirname(__file__), "data", "processed", "output"
)


# ---------------------------------------------------------------------------
# Grid generation
# ---------------------------------------------------------------------------

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def generate_grid():
    step_lat = STEP_KM / 111.0
    step_lon = STEP_KM / (111.0 * math.cos(math.radians(CENTER_LAT)))
    lat_range = RADIUS_KM / 111.0 + step_lat
    lon_range = RADIUS_KM / (111.0 * math.cos(math.radians(CENTER_LAT))) + step_lon

    points = []
    lat = CENTER_LAT - lat_range
    while lat <= CENTER_LAT + lat_range:
        lon = CENTER_LON - lon_range
        while lon <= CENTER_LON + lon_range:
            d = haversine_km(CENTER_LAT, CENTER_LON, lat, lon)
            if d <= RADIUS_KM:
                points.append((round(lat, 4), round(lon, 4)))
            lon += step_lon
        lat += step_lat

    return points


def point_key(lat, lon):
    return f"{lat:.4f}_{lon:.4f}"


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------

def load_existing():
    if not os.path.exists(OUTPUT_PATH):
        return {"metadata": {}, "points": {}}
    with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save(db):
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# Data fetchers (imported lazily to avoid loading everything upfront)
# ---------------------------------------------------------------------------

_VC_WEATHER = None   # loaded once from data/finland_weather.json
_GEE_POINTS = None   # loaded once from data/gee_finland_points.json


def _load_vc_weather():
    global _VC_WEATHER
    if _VC_WEATHER is not None:
        return _VC_WEATHER
    path = os.path.join(os.path.dirname(__file__), "data", "finland_weather.json")
    if os.path.exists(path):
        with open(path, "r") as f:
            data = json.load(f)
        _VC_WEATHER = data.get("grid_points", {})
        print(f"[prefetch] Loaded Visual Crossing weather for {len(_VC_WEATHER)} points")
    else:
        _VC_WEATHER = {}
        print("[prefetch] No Visual Crossing data — will use Open-Meteo fallback")
    return _VC_WEATHER


def _load_gee_points():
    global _GEE_POINTS
    if _GEE_POINTS is not None:
        return _GEE_POINTS
    path = os.path.join(os.path.dirname(__file__), "data", "gee_finland_points.json")
    if os.path.exists(path):
        with open(path, "r") as f:
            raw = json.load(f)
        # GeoJSON FeatureCollection → dict keyed by "lat_lon"
        features = raw.get("features", [])
        _GEE_POINTS = {}
        for feat in features:
            props = feat.get("properties", {})
            lat   = props.get("lat")
            lon   = props.get("lon")
            if lat and lon:
                _GEE_POINTS[f"{lat:.4f}_{lon:.4f}"] = props
        print(f"[prefetch] Loaded GEE SAR data for {len(_GEE_POINTS)} points")
    else:
        _GEE_POINTS = {}
        print("[prefetch] No GEE data yet — run gee_sentinel1_finland.py first")
    return _GEE_POINTS


def fetch_climate(lat, lon):
    """Use Visual Crossing data if available, fall back to Open-Meteo."""
    vc = _load_vc_weather()
    key = f"{lat:.4f}_{lon:.4f}"

    # Try exact key first, then nearest
    if key in vc:
        return vc[key]

    # Nearest neighbour from VC grid
    if vc:
        import math as _math
        best_key, best_d = None, float("inf")
        for k in vc:
            parts = k.split("_")
            if len(parts) == 2:
                try:
                    kl, ko = float(parts[0]), float(parts[1])
                    d = _math.sqrt((kl - lat)**2 + (ko - lon)**2)
                    if d < best_d:
                        best_d, best_key = d, k
                except ValueError:
                    pass
        if best_key and best_d < 0.5:
            return vc[best_key]

    # Fallback to Open-Meteo
    from services.data_sources.climate import fetch_drought_indices, fetch_flood_metrics
    drought = fetch_drought_indices(lat, lon)
    time.sleep(15.0)
    floods  = fetch_flood_metrics(lat, lon)
    return {**drought, **floods}


def fetch_gee_data(lat, lon):
    """Return GEE SAR flood frequency and WorldCover built-up fraction for this point."""
    gee = _load_gee_points()
    key = f"{lat:.4f}_{lon:.4f}"
    if key in gee:
        return gee[key]
    # Nearest neighbour
    if gee:
        import math as _math
        best_key, best_d = None, float("inf")
        for k, props in gee.items():
            kl = props.get("lat", 0)
            ko = props.get("lon", 0)
            d  = _math.sqrt((kl - lat)**2 + (ko - lon)**2)
            if d < best_d:
                best_d, best_key = d, k
        if best_key and best_d < 0.3:
            return gee[best_key]
    return None


def fetch_water_quality_data(lat, lon):
    from services.data_sources.water_quality import fetch_water_quality
    return fetch_water_quality(lat, lon)


def fetch_syke(lat, lon):
    from services.finland.syke_ingest import fetch_all_syke
    raw = fetch_all_syke(lat, lon)
    flood = raw.get("flood_hazard", {})
    gw    = raw.get("groundwater", {})
    lake  = raw.get("lake_depth", {})
    return {
        "flood_zone":        flood.get("flood_zone_label", "None"),
        "in_50yr_zone":      flood.get("in_50yr_zone", False),
        "in_100yr_zone":     flood.get("in_100yr_zone", False),
        "in_250yr_zone":     flood.get("in_250yr_zone", False),
        "groundwater_class": gw.get("groundwater_class"),
        "class_weight":      gw.get("class_weight", 0.3),
        "area_name":         gw.get("area_name"),
        "nearest_lake":      lake.get("nearest_lake_name"),
        "lake_depth_m":      lake.get("mean_depth_m"),
        "heat_exchange_viable": lake.get("heat_exchange_viable", False),
    }


def fetch_cndcp(lat, lon, gw_weight):
    from services.finland.cndcp_scoring import calculate_cndcp_score
    result = calculate_cndcp_score(lat, lon, gw_weight)
    return {
        "cndcp_score":   result.get("cndcp_score"),
        "cdd":           result.get("raw_inputs", {}).get("cdd"),
        "bws":           result.get("raw_inputs", {}).get("bws"),
        "norm_inv_cdd":  result.get("components", {}).get("norm_inv_cdd"),
        "one_minus_bws": result.get("components", {}).get("one_minus_bws"),
        "grade":         result.get("grade"),
    }


def sample_sentinel_bands(lat, lon):
    """Sample Sentinel-2 and Sentinel-1 bands from pre-processed GeoTIFFs if available."""
    result = {}
    band_files = {
        "green_band": os.path.join(SENTINEL_OUTPUT, "B03_10m.tif"),
        "nir_band":   os.path.join(SENTINEL_OUTPUT, "B08_10m.tif"),
        "swir_band":  os.path.join(SENTINEL_OUTPUT, "B11_10m.tif"),
        "vv_band":    os.path.join(SENTINEL_OUTPUT, "S1_VV_10m.tif"),
        "vh_band":    os.path.join(SENTINEL_OUTPUT, "S1_VH_10m.tif"),
    }
    try:
        import rasterio
        from rasterio.transform import rowcol
        for key, path in band_files.items():
            if not os.path.exists(path):
                result[key] = None
                continue
            try:
                with rasterio.open(path) as src:
                    row, col = rowcol(src.transform, lon, lat)
                    row, col = int(row), int(col)
                    if 0 <= row < src.height and 0 <= col < src.width:
                        val = float(src.read(1)[row, col])
                        result[key] = None if (val != val or val == 0) else round(val, 6)
                    else:
                        result[key] = None
            except Exception:
                result[key] = None
    except ImportError:
        for key in band_files:
            result[key] = None
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"Finland grid prefetch — {STEP_KM:.0f}km grid, {RADIUS_KM:.0f}km radius around Kajaani")
    grid = generate_grid()
    print(f"Grid: {len(grid)} points to fetch\n")

    db = load_existing()
    existing = db.get("points", {})
    skipped  = sum(1 for (la, lo) in grid if point_key(la, lo) in existing)
    to_fetch = [(la, lo) for (la, lo) in grid if point_key(la, lo) not in existing]
    print(f"Already cached: {skipped}  |  To fetch: {len(to_fetch)}\n")

    for i, (lat, lon) in enumerate(to_fetch, 1):
        key = point_key(lat, lon)
        dist = haversine_km(CENTER_LAT, CENTER_LON, lat, lon)
        print(f"[{i:3d}/{len(to_fetch)}] ({lat}, {lon})  dist={dist:.1f}km")

        point_data = {"lat": lat, "lon": lon, "fetched_at": datetime.now(timezone.utc).isoformat()}
        errors = []

        # --- Climate (Open-Meteo) ---
        try:
            climate = fetch_climate(lat, lon)
            point_data["risk_inputs"] = climate
            print(f"         ERA5: drought={climate.get('spei_dry_proportion_10yr'):.3f} "
                  f"floods={climate.get('flood_events_count')}")
        except Exception as exc:
            errors.append(f"climate: {exc}")
            from config import ROMANIA_DEFAULTS
            point_data["risk_inputs"] = {
                k: v for k, v in ROMANIA_DEFAULTS.items()
                if k in ("spei_dry_proportion_10yr","spei_dry_proportion_3yr",
                         "groundwater_change_mm","flood_events_count","avg_flood_depth_m",
                         "depletion_ratio","annual_depletion_pct","dry_year_months",
                         "seasonal_months")
            }
            print(f"         ERA5: FAILED ({exc})")

        # Wait between climate and next call to avoid rate limiting
        time.sleep(15.0)

        # --- Water quality (EEA WISE) ---
        try:
            wq = fetch_water_quality_data(lat, lon)
            point_data["risk_inputs"].update({
                "bod_mg_per_l":      wq["bod_mg_per_l"],
                "nitrate_mg_per_l":  wq["nitrate_mg_per_l"],
                "salinity_tds_mg_l": wq["salinity_tds_mg_l"],
            })
            point_data["wq_status"] = wq.get("wfd_status", "Unknown")
            print(f"         EEA WISE: {wq.get('wfd_status')} — {wq.get('station_name','')[:40]}")
        except Exception as exc:
            errors.append(f"water_quality: {exc}")
            print(f"         EEA WISE: FAILED ({exc})")

        # --- SYKE (Finnish government data) ---
        try:
            syke = fetch_syke(lat, lon)
            point_data["syke"] = syke
            print(f"         SYKE: flood={syke['flood_zone']} gw={syke['groundwater_class']}")
        except Exception as exc:
            errors.append(f"syke: {exc}")
            point_data["syke"] = {}
            print(f"         SYKE: FAILED ({exc})")

        time.sleep(15.0)  # wait before CNDCP — it also calls Open-Meteo for CDD

        # --- CNDCP score ---
        try:
            gw_w = point_data.get("syke", {}).get("class_weight", 0.3)
            cndcp = fetch_cndcp(lat, lon, gw_w)
            point_data["cndcp"] = cndcp
            print(f"         CNDCP: {cndcp.get('cndcp_score'):.3f} (CDD={cndcp.get('cdd'):.0f})")
        except Exception as exc:
            errors.append(f"cndcp: {exc}")
            point_data["cndcp"] = {}
            print(f"         CNDCP: FAILED ({exc})")

        # --- Sentinel bands ---
        bands = sample_sentinel_bands(lat, lon)
        point_data["sentinel"] = bands
        s2_ok = any(v is not None for k, v in bands.items() if k in ("green_band","nir_band","swir_band"))
        s1_ok = any(v is not None for k, v in bands.items() if k in ("vv_band","vh_band"))
        print(f"         Sentinel: S2={'OK' if s2_ok else 'no GeoTIFF'} S1={'OK' if s1_ok else 'no GeoTIFF'}")

        point_data["errors"] = errors
        existing[key] = point_data

        # Save after every point — makes script resumable
        db["points"] = existing
        db["metadata"] = {
            "center": {"lat": CENTER_LAT, "lon": CENTER_LON},
            "radius_km": RADIUS_KM,
            "grid_step_km": STEP_KM,
            "total_points": len(grid),
            "fetched_points": len(existing),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
        save(db)

        print()
        time.sleep(20.0)  # pause between points — Open-Meteo rate limit recovery

    print(f"\nDone. {len(existing)}/{len(grid)} points in {OUTPUT_PATH}")
    print("The app will now use this cache for all Finnish locations.")


if __name__ == "__main__":
    main()
