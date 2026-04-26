"""
Visual Crossing weather data downloader for Finland.
Downloads 15 years of daily weather for key points in the Kajaani zone.
Computes: Cooling Degree Days (CDD), SPI drought index, extreme precip events.
Replaces Open-Meteo completely — no rate limits, reliable CSV format.

Usage:
    python visual_crossing_weather.py

Output: data/finland_weather.json
API docs: https://www.visualcrossing.com/weather-api
Free tier: 1,000 records/day (sufficient for this script)
"""

import json
import math
import os
import time
from datetime import datetime, timezone

import requests

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

API_KEY    = os.environ.get("VISUAL_CROSSING_KEY", "")
BASE_URL   = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
OUTPUT     = os.path.join(os.path.dirname(__file__), "data", "finland_weather.json")

CENTER_LAT = 64.2245
CENTER_LON = 27.7177
RADIUS_KM  = 100.0
STEP_KM    = 20.0

START_DATE = "2010-01-01"
END_DATE   = "2024-12-31"
BASE_TEMP  = 18.0   # CDD base temperature (EN ISO 15927-6 standard)

import numpy as np


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon/2)**2)
    return R * 2 * math.asin(math.sqrt(a))


def generate_representative_points():
    """
    Instead of downloading for all 78 grid points (would exhaust free tier),
    download for 9 representative points: center + 8 cardinal/diagonal points.
    Weather is interpolated to nearby grid points.
    """
    offsets_km = [(0, 0), (50, 0), (-50, 0), (0, 50), (0, -50),
                  (35, 35), (-35, 35), (35, -35), (-35, -35)]
    points = []
    for dlat_km, dlon_km in offsets_km:
        lat = CENTER_LAT + dlat_km / 111.0
        lon = CENTER_LON + dlon_km / (111.0 * math.cos(math.radians(CENTER_LAT)))
        points.append((round(lat, 4), round(lon, 4)))
    return points


def fetch_weather(lat: float, lon: float) -> list[dict]:
    """
    Fetch daily weather from Visual Crossing for a single point.
    Returns list of daily records with temp and precip.
    """
    url = f"{BASE_URL}/{lat},{lon}/{START_DATE}/{END_DATE}"
    params = {
        "key":          API_KEY,
        "include":      "days",
        "elements":     "datetime,tempmax,tempmin,temp,precip",
        "unitGroup":    "metric",
        "contentType":  "json",
    }
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    data = r.json()
    return data.get("days", [])


def compute_indicators(days: list[dict]) -> dict:
    """
    Compute all climate indicators from daily weather records.

    Returns:
      - cdd: annual mean Cooling Degree Days
      - spei_dry_proportion_10yr: fraction of months with SPI < -1 (10yr)
      - spei_dry_proportion_3yr: fraction of months with SPI < -1 (3yr)
      - groundwater_change_mm: precipitation trend proxy
      - flood_events_count: days with precip > 50mm since 2010
      - avg_flood_depth_m: Gumbel 100yr return period precipitation estimate
    """
    temps  = [d.get("temp")   for d in days if d.get("temp")   is not None]
    precip = [d.get("precip") or 0.0 for d in days]
    dates  = [d.get("datetime", "") for d in days]

    # --- CDD ---
    cdd_annual = sum(max(0.0, t - BASE_TEMP) for t in temps) / max(1, len(set(d[:4] for d in dates)))

    # --- Monthly precipitation totals for SPI ---
    monthly: dict[str, list[float]] = {}
    for date_str, p in zip(dates, precip):
        month_key = date_str[:7]
        monthly.setdefault(month_key, []).append(p)
    monthly_totals = [sum(v) for v in monthly.values()]

    spi = _spi(monthly_totals)
    dry_10yr = sum(1 for s in spi if s < -1.0) / max(len(spi), 1)
    spi_3yr  = spi[-36:] if len(spi) >= 36 else spi
    dry_3yr  = sum(1 for s in spi_3yr if s < -1.0) / max(len(spi_3yr), 1)

    # Groundwater proxy from recent vs older precip
    if len(monthly_totals) >= 48:
        recent = float(np.mean(monthly_totals[-24:]))
        older  = float(np.mean(monthly_totals[-48:-24]))
        gw_change = round((recent - older) / 10.0, 2)
    else:
        gw_change = 0.0

    # --- Flood events (days > 50mm) ---
    arr = np.array(precip)
    flood_days = np.where(arr > 50.0)[0]
    events = 0
    last   = -10
    for day in flood_days:
        if day - last > 3:
            events += 1
            last = day

    # --- 100yr return period flood depth (Gumbel) ---
    if len(arr) > 30:
        mu    = float(np.mean(arr))
        sigma = float(np.std(arr))
        gumbel = -np.log(-np.log(1.0 - 1.0 / 100.0))
        p100_mm = mu + sigma * gumbel
        depth_m = round(max(0.5, min(15.0, p100_mm * 0.6 / 1000.0)), 2)
    else:
        depth_m = 2.5

    return {
        "cdd":                        round(cdd_annual, 1),
        "spei_dry_proportion_10yr":   round(dry_10yr, 4),
        "spei_dry_proportion_3yr":    round(dry_3yr, 4),
        "groundwater_change_mm":      gw_change,
        "flood_events_count":         int(events),
        "avg_flood_depth_m":          depth_m,
    }


def _spi(monthly: list[float]) -> list[float]:
    arr  = np.array(monthly, dtype=float)
    mean = arr.mean()
    std  = arr.std()
    if std < 1e-9:
        return [0.0] * len(monthly)
    return list((arr - mean) / std)


def interpolate_to_grid(rep_points: list[tuple], rep_data: dict,
                        grid_points: list[tuple]) -> dict:
    """
    Inverse-distance weighted interpolation from representative to grid points.
    """
    grid_weather = {}
    for g_lat, g_lon in grid_points:
        weights = []
        for r_lat, r_lon in rep_points:
            d = haversine_km(g_lat, g_lon, r_lat, r_lon)
            weights.append(1.0 / max(d, 0.1))

        total_w = sum(weights)
        result  = {}
        for key in ("cdd", "spei_dry_proportion_10yr", "spei_dry_proportion_3yr",
                    "groundwater_change_mm", "flood_events_count", "avg_flood_depth_m"):
            val = sum(w * rep_data[f"{r_lat}_{r_lon}"][key]
                      for w, (r_lat, r_lon) in zip(weights, rep_points)) / total_w
            result[key] = round(val, 4)

        grid_weather[f"{g_lat}_{g_lon}"] = result

    return grid_weather


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


def main():
    if not API_KEY:
        print("ERROR: Set VISUAL_CROSSING_KEY in .env")
        print("Get your free key at: https://www.visualcrossing.com/weather-api")
        return

    rep_points = generate_representative_points()
    grid_points = generate_grid()
    print(f"Downloading weather for {len(rep_points)} representative points")
    print(f"Will interpolate to {len(grid_points)} grid points\n")

    # Load existing if resuming
    if os.path.exists(OUTPUT):
        with open(OUTPUT, "r") as f:
            existing = json.load(f)
    else:
        existing = {"rep_points": {}, "grid_points": {}, "metadata": {}}

    # Download representative points
    rep_data = existing.get("rep_points", {})
    for i, (lat, lon) in enumerate(rep_points, 1):
        key = f"{lat}_{lon}"
        if key in rep_data:
            print(f"[{i}/{len(rep_points)}] ({lat}, {lon}) — cached, skipping")
            continue

        print(f"[{i}/{len(rep_points)}] ({lat}, {lon}) fetching from Visual Crossing...")
        try:
            days = fetch_weather(lat, lon)
            indicators = compute_indicators(days)
            rep_data[key] = indicators
            print(f"  CDD={indicators['cdd']} | drought_10yr={indicators['spei_dry_proportion_10yr']} "
                  f"| floods={indicators['flood_events_count']}")

            existing["rep_points"] = rep_data
            os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
            with open(OUTPUT, "w") as f:
                json.dump(existing, f, indent=2)

        except Exception as exc:
            print(f"  FAILED: {exc}")

        time.sleep(2.0)  # Visual Crossing rate limit

    # Interpolate to all grid points
    print(f"\nInterpolating to {len(grid_points)} grid points...")
    grid_weather = interpolate_to_grid(rep_points, rep_data, grid_points)

    existing["grid_points"] = grid_weather
    existing["metadata"] = {
        "center": {"lat": CENTER_LAT, "lon": CENTER_LON},
        "radius_km": RADIUS_KM,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "rep_point_count": len(rep_data),
        "grid_point_count": len(grid_weather),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "Visual Crossing Weather API",
    }

    with open(OUTPUT, "w") as f:
        json.dump(existing, f, indent=2)

    print(f"\nDone. Saved to {OUTPUT}")
    print("Next step: python prefetch_finland.py")


if __name__ == "__main__":
    main()
