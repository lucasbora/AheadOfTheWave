"""
Google Earth Engine — Sentinel-1 SAR flood frequency + ESA WorldCover for Finland.

Computation runs on Google's servers. Results export to your Google Drive.
You then download the JSON file and place it at data/gee_finland_points.json.

Usage:
    python gee_sentinel1_finland.py

What this does:
1. Defines the same 20km grid used by prefetch_finland.py (78 points, 100km radius around Kajaani)
2. For each point: extracts Sentinel-1 SAR flood frequency (2017-2025) and ESA WorldCover land class
3. Exports results as GeoJSON to Google Drive → file: gee_finland_points.json
4. Also exports a flood frequency GeoTIFF for visualisation

Sentinel-1 flood detection method:
  - Collection: COPERNICUS/S1_GRD (IW mode, VV+VH, 10m)
  - Wet season: March–May (snow melt + rain, highest flood risk in Finland)
  - Flood signal: VV backscatter < -15 dB (open water returns very low backscatter)
  - Flood frequency: fraction of wet-season images where pixel is flooded (0–1)
  Source: Twele et al. (2016) Remote Sensing 8(3):217; ESA Sentinel-1 SAR handbook

WorldCover built-up detection:
  - Collection: ESA/WorldCover/v200 (2021, 10m resolution)
  - Class 50 = Built-up land
  - built_fraction: proportion of 1km buffer that is built-up (0–1)
  Source: ESA WorldCover 2021 Product User Manual v2.0
"""

import json
import math
import os
import sys
import time

try:
    import ee
except ImportError:
    print("ERROR: earthengine-api not installed. Run: pip install earthengine-api")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CENTER_LAT = 64.2245
CENTER_LON = 27.7177
RADIUS_KM  = 100.0
STEP_KM    = 20.0

# S1 analysis period and flood threshold
S1_START       = "2017-01-01"
S1_END         = "2025-12-31"
FLOOD_VV_DB    = -15.0   # dB threshold for open water / flood detection
WET_MONTHS     = [3, 4, 5]  # March-April-May = snowmelt + spring rain

DRIVE_FOLDER   = "AquaCapital"   # Google Drive folder for exports
OUTPUT_POINTS  = os.path.join(os.path.dirname(__file__), "data", "gee_finland_points.json")


# ---------------------------------------------------------------------------
# Grid generation (same as prefetch_finland.py)
# ---------------------------------------------------------------------------

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2)
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
            if haversine_km(CENTER_LAT, CENTER_LON, lat, lon) <= RADIUS_KM:
                points.append((round(lat, 4), round(lon, 4)))
            lon += step_lon
        lat += step_lat
    return points


# ---------------------------------------------------------------------------
# GEE analysis
# ---------------------------------------------------------------------------

def build_s1_flood_frequency():
    """
    Build Sentinel-1 flood frequency image for the Kajaani region.
    Returns an ee.Image with band 'flood_freq' (0-1, higher = more frequently flooded).
    """
    region = ee.Geometry.Point([CENTER_LON, CENTER_LAT]).buffer(RADIUS_KM * 1000 + 5000)

    s1 = (ee.ImageCollection("COPERNICUS/S1_GRD")
          .filterBounds(region)
          .filterDate(S1_START, S1_END)
          .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
          .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
          .filter(ee.Filter.eq("instrumentMode", "IW"))
          .select(["VV", "VH"]))

    # Filter to wet season (March-May) for flood detection
    def filter_wet_season(img):
        month = img.date().get("month")
        return img.set("wet", ee.Number(month).gte(3).And(ee.Number(month).lte(5)))

    s1_wet = s1.filter(ee.Filter.calendarRange(3, 5, "month"))
    total_count = s1_wet.size()

    # Flood mask: VV < threshold
    def is_flooded(img):
        return img.select("VV").lt(FLOOD_VV_DB).rename("flooded")

    flood_count = s1_wet.map(is_flooded).sum().rename("flood_count")
    flood_freq  = flood_count.divide(total_count).rename("flood_freq")

    # Mean VV and VH for the full period (not just wet season)
    mean_vv = s1.select("VV").mean().rename("mean_vv")
    mean_vh = s1.select("VH").mean().rename("mean_vh")

    return ee.Image.cat([flood_freq, mean_vv, mean_vh])


def build_worldcover():
    """
    Load ESA WorldCover 2021 (10m). Class 50 = Built-up.
    Returns binary image: 1 = built-up, 0 = not built-up.
    Source: ESA/WorldCover/v200
    """
    wc = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map")
    built_up = wc.eq(50).rename("built_up")
    return built_up


def extract_point_values(grid_points, s1_image, worldcover_image):
    """
    Extract SAR and land cover values at each grid point.
    Uses a 500m buffer around each point for spatial averaging.
    """
    features = []
    for lat, lon in grid_points:
        feat = ee.Feature(
            ee.Geometry.Point([lon, lat]),
            {"lat": lat, "lon": lon}
        )
        features.append(feat)

    fc = ee.FeatureCollection(features)

    combined = ee.Image.cat([s1_image, worldcover_image])

    def reduce_point(feat):
        geom = feat.geometry().buffer(500)  # 500m radius buffer
        vals = combined.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geom,
            scale=10,
            maxPixels=1e6,
        )
        return feat.set(vals)

    return fc.map(reduce_point)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Initialising Google Earth Engine...")
    try:
        ee.Initialize()
        print("GEE authenticated OK\n")
    except Exception as exc:
        print(f"GEE init failed: {exc}")
        print("Run: earthengine authenticate")
        sys.exit(1)

    grid = generate_grid()
    print(f"Grid: {len(grid)} points in {RADIUS_KM:.0f}km radius around Kajaani\n")

    print("Building Sentinel-1 flood frequency image (2017-2025, wet season Mar-May)...")
    s1_image = build_s1_flood_frequency()

    print("Loading ESA WorldCover 2021 built-up mask...")
    worldcover = build_worldcover()

    print("Extracting values at grid points (500m buffer each)...")
    result_fc = extract_point_values(grid, s1_image, worldcover)

    # ---------------------------------------------------------------------------
    # Export 1: Point data as GeoJSON → download from Drive
    # ---------------------------------------------------------------------------
    print("\nSubmitting export task to Google Drive...")
    task_points = ee.batch.Export.table.toDrive(
        collection=result_fc,
        description="AquaCapital_Finland_Points",
        folder=DRIVE_FOLDER,
        fileNamePrefix="gee_finland_points",
        fileFormat="GeoJSON",
    )
    task_points.start()
    print(f"Task started: AquaCapital_Finland_Points")
    print(f"Monitor at: https://code.earthengine.google.com/tasks\n")

    # ---------------------------------------------------------------------------
    # Export 2: Flood frequency raster (for map visualisation)
    # ---------------------------------------------------------------------------
    region = ee.Geometry.Point([CENTER_LON, CENTER_LAT]).buffer(RADIUS_KM * 1000 + 5000)

    task_raster = ee.batch.Export.image.toDrive(
        image=s1_image.select("flood_freq"),
        description="AquaCapital_S1_FloodFreq",
        folder=DRIVE_FOLDER,
        fileNamePrefix="s1_flood_frequency_kajaani",
        region=region,
        scale=100,
        crs="EPSG:4326",
        maxPixels=1e9,
    )
    task_raster.start()
    print("Task started: AquaCapital_S1_FloodFreq (flood frequency raster for visualisation)")

    # ---------------------------------------------------------------------------
    # Monitor until complete
    # ---------------------------------------------------------------------------
    print("\nWaiting for tasks to complete (this may take 5-20 minutes)...")
    tasks = [task_points, task_raster]
    names  = ["Points GeoJSON", "Flood frequency raster"]

    while True:
        statuses = [t.status()["state"] for t in tasks]
        for name, st in zip(names, statuses):
            print(f"  {name}: {st}")

        if all(s in ("COMPLETED", "FAILED", "CANCELLED") for s in statuses):
            break

        time.sleep(30)
        print()

    print("\n=== DONE ===")
    print("1. Go to Google Drive → AquaCapital folder")
    print("2. Download 'gee_finland_points.geojson'")
    print(f"3. Place it at: {OUTPUT_POINTS}")
    print("4. Then run: python prefetch_finland.py")


if __name__ == "__main__":
    main()
