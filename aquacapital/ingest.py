"""
Sentinel-1 and Sentinel-2 band extraction and sampling pipeline.

Sentinel-2 L2A: B03 (green), B08 (NIR), B11 (SWIR) → NDWI, MNDWI, soil moisture
Sentinel-1 GRD: VV, VH → SAR flood index, moisture index, RVI

Usage:
    python ingest.py <path/to/S2_product.SAFE.zip> <lat> <lon>
    python ingest.py <path/to/S1_product.SAFE.zip> <lat> <lon>
    python ingest.py                                          # auto-discovers latest zip

Outputs GeoTIFFs to data/processed/output/ and prints band values
ready to paste into the investment grade API.
"""

import os
import sys
import glob
import zipfile

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject
from rasterio.transform import rowcol

BASE_DIR   = os.path.dirname(__file__)
DATA_DIR   = os.path.join(BASE_DIR, "data", "processed")
OUTPUT_DIR = os.path.join(DATA_DIR, "output")


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def find_latest_zip(pattern: str = "*.zip") -> str:
    zips = glob.glob(os.path.join(DATA_DIR, pattern))
    if not zips:
        raise FileNotFoundError(f"No zip files matching '{pattern}' in {DATA_DIR}")
    return max(zips, key=os.path.getmtime)


def is_sentinel1(zip_path: str) -> bool:
    name = os.path.basename(zip_path).upper()
    return name.startswith("S1") or "GRD" in name or "_IW_" in name


def ensure_extracted(zip_path: str) -> str:
    safe_name = os.path.basename(zip_path).replace(".zip", "")
    safe_dir  = os.path.join(DATA_DIR, safe_name)
    if os.path.isdir(safe_dir):
        print(f"[unzip] already extracted: {safe_dir}")
        return safe_dir
    print(f"[unzip] extracting {os.path.basename(zip_path)} ...")
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(DATA_DIR)
    print(f"[unzip] done -> {safe_dir}")
    return safe_dir


def find_band(safe_dir: str, band: str, resolution: str) -> str:
    """Find Sentinel-2 band by name and resolution."""
    for ext in ("jp2", "tif", "tiff"):
        matches = glob.glob(
            os.path.join(safe_dir, "**", f"*_{band}_{resolution}.{ext}"),
            recursive=True,
        )
        if matches:
            return matches[0]
    raise FileNotFoundError(
        f"Band {band} at {resolution} not found in {safe_dir}"
    )


def find_s1_band(safe_dir: str, polarisation: str) -> str:
    """
    Find Sentinel-1 GRD measurement TIFF for a given polarisation (VV or VH).
    S1 GRD measurement files: s1*-iw-grd-{pol}-*.tiff inside measurement/ folder.
    """
    pol = polarisation.lower()
    for pattern in (
        f"*-iw-grd-{pol}-*.tiff",
        f"*-iw-grd-{pol}-*.tif",
        f"*{pol}*.tiff",
        f"*{pol}*.tif",
    ):
        matches = glob.glob(os.path.join(safe_dir, "**", pattern), recursive=True)
        if matches:
            return matches[0]
    raise FileNotFoundError(
        f"Sentinel-1 {polarisation.upper()} band not found in {safe_dir}. "
        f"Check measurement/ folder."
    )


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def read_band(path: str) -> tuple[np.ndarray, dict]:
    """Read Sentinel-2 band as float32 surface reflectance [0-1]."""
    with rasterio.open(path) as src:
        data = src.read(1).astype(np.float32)
        profile = src.profile.copy()
    data = np.where(data == 0, np.nan, data / 10_000.0)
    return data, profile


def read_s1_band(path: str) -> tuple[np.ndarray, dict]:
    """
    Read Sentinel-1 GRD DN values and normalise to [0, 1].
    GRD DN are uint16 (0-65535). Divide by 65535 for relative normalised values.
    Source: ESA Sentinel-1 Level-1 Product Specification (ESA, 2022).
    """
    with rasterio.open(path) as src:
        data = src.read(1).astype(np.float32)
        profile = src.profile.copy()
    # Replace 0 (no-data) with NaN, then normalise
    data = np.where(data == 0, np.nan, data / 65535.0)
    return data, profile


def resample_to_match(src_path: str, ref_profile: dict, scale: float = 10_000.0) -> np.ndarray:
    """Resample any band to match ref_profile resolution and extent."""
    with rasterio.open(src_path) as src:
        data = np.empty((ref_profile["height"], ref_profile["width"]), dtype=np.float32)
        reproject(
            source=rasterio.band(src, 1),
            destination=data,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=ref_profile["transform"],
            dst_crs=ref_profile["crs"],
            resampling=Resampling.bilinear,
        )
    data = np.where(data == 0, np.nan, data / scale)
    return data


def reproject_to_wgs84(data: np.ndarray, src_profile: dict) -> tuple[np.ndarray, dict]:
    dst_crs = "EPSG:4326"
    bounds = rasterio.transform.array_bounds(
        src_profile["height"], src_profile["width"], src_profile["transform"]
    )
    transform, width, height = calculate_default_transform(
        src_profile["crs"], dst_crs,
        src_profile["width"], src_profile["height"], *bounds,
    )
    dst_profile = src_profile.copy()
    dst_profile.update({"crs": dst_crs, "transform": transform, "width": width, "height": height})

    out = np.full((height, width), np.nan, dtype=np.float32)
    reproject(
        source=data, destination=out,
        src_transform=src_profile["transform"], src_crs=src_profile["crs"],
        dst_transform=transform, dst_crs=dst_crs,
        resampling=Resampling.bilinear,
    )
    return out, dst_profile


def save_geotiff(path: str, data: np.ndarray, profile: dict):
    p = profile.copy()
    p.update({"driver": "GTiff", "dtype": "float32", "count": 1,
              "nodata": np.nan, "compress": "deflate", "tiled": True})
    with rasterio.open(path, "w", **p) as dst:
        dst.write(data, 1)
    print(f"  saved -> {path}")


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------

def sample_band_at_point(geotiff_path: str, lat: float, lon: float) -> float:
    """Read pixel value at (lat, lon) from a WGS84 GeoTIFF. Returns NaN if outside."""
    with rasterio.open(geotiff_path) as src:
        row, col = rowcol(src.transform, lon, lat)
        row, col = int(row), int(col)
        if row < 0 or col < 0 or row >= src.height or col >= src.width:
            return float("nan")
        value = src.read(1)[row, col]
    return float(value)


def sample_for_api(lat: float, lon: float, output_dir: str = OUTPUT_DIR) -> dict:
    """
    Sample all available bands (S2 + S1) at (lat, lon).
    Returns dict ready to pass as overrides to POST /api/v1/investment/grade.
    """
    s2_paths = {
        "green_band": os.path.join(output_dir, "B03_10m.tif"),
        "nir_band":   os.path.join(output_dir, "B08_10m.tif"),
        "swir_band":  os.path.join(output_dir, "B11_10m.tif"),
    }
    s1_paths = {
        "vv_band": os.path.join(output_dir, "S1_VV_10m.tif"),
        "vh_band": os.path.join(output_dir, "S1_VH_10m.tif"),
    }

    result = {}

    # S2 bands (required)
    missing_s2 = [k for k, p in s2_paths.items() if not os.path.exists(p)]
    if missing_s2:
        raise FileNotFoundError(f"Missing S2 GeoTIFFs: {missing_s2}. Run ingest.py with S2 zip first.")
    for k, p in s2_paths.items():
        result[k] = round(sample_band_at_point(p, lat, lon), 6)

    # S1 bands (optional — included if processed)
    for k, p in s1_paths.items():
        if os.path.exists(p):
            result[k] = round(sample_band_at_point(p, lat, lon), 6)

    return result


# ---------------------------------------------------------------------------
# Sentinel-2 pipeline
# ---------------------------------------------------------------------------

def process_s2(zip_path: str, lat: float | None, lon: float | None) -> dict | None:
    safe_dir = ensure_extracted(zip_path)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("[S2 1/4] locating bands ...")
    b3_path  = find_band(safe_dir, "B03", "10m")
    b8_path  = find_band(safe_dir, "B08", "10m")
    b11_path = find_band(safe_dir, "B11", "20m")
    print(f"  B03 : {b3_path}")
    print(f"  B08 : {b8_path}")
    print(f"  B11 : {b11_path}")

    print("[S2 2/4] reading 10 m bands ...")
    b3, profile = read_band(b3_path)
    b8, _       = read_band(b8_path)

    print("[S2 3/4] resampling B11 (20 m -> 10 m) ...")
    b11 = resample_to_match(b11_path, profile)

    print("[S2 4/4] reprojecting to WGS84 and saving ...")
    b3_wgs,  p_wgs = reproject_to_wgs84(b3,  profile)
    b8_wgs,  _     = reproject_to_wgs84(b8,  profile)
    b11_wgs, _     = reproject_to_wgs84(b11, profile)

    save_geotiff(os.path.join(OUTPUT_DIR, "B03_10m.tif"), b3_wgs,  p_wgs)
    save_geotiff(os.path.join(OUTPUT_DIR, "B08_10m.tif"), b8_wgs,  p_wgs)
    save_geotiff(os.path.join(OUTPUT_DIR, "B11_10m.tif"), b11_wgs, p_wgs)

    with np.errstate(invalid="ignore"):
        ndwi = (b3_wgs - b8_wgs) / (b3_wgs + b8_wgs)
        smi  = 1.0 - b11_wgs

    save_geotiff(os.path.join(OUTPUT_DIR, "ndwi.tif"),          ndwi, p_wgs)
    save_geotiff(os.path.join(OUTPUT_DIR, "soil_moisture.tif"), smi,  p_wgs)

    if lat is not None and lon is not None:
        return _sample_and_print(lat, lon, sensor="S2")
    return None


# ---------------------------------------------------------------------------
# Sentinel-1 pipeline
# ---------------------------------------------------------------------------

def process_s1(zip_path: str, lat: float | None, lon: float | None) -> dict | None:
    """
    Extract Sentinel-1 GRD VV and VH bands, normalise, reproject to WGS84.
    Derives SAR flood index and moisture index.
    """
    safe_dir = ensure_extracted(zip_path)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("[S1 1/3] locating VV and VH bands ...")
    vv_path = find_s1_band(safe_dir, "vv")
    vh_path = find_s1_band(safe_dir, "vh")
    print(f"  VV : {vv_path}")
    print(f"  VH : {vh_path}")

    print("[S1 2/3] reading and normalising bands ...")
    vv, vv_profile = read_s1_band(vv_path)
    vh, _          = read_s1_band(vh_path)

    print("[S1 3/3] reprojecting to WGS84 and saving ...")
    vv_wgs, p_wgs = reproject_to_wgs84(vv, vv_profile)
    vh_wgs, _     = reproject_to_wgs84(vh, vv_profile)

    save_geotiff(os.path.join(OUTPUT_DIR, "S1_VV_10m.tif"), vv_wgs, p_wgs)
    save_geotiff(os.path.join(OUTPUT_DIR, "S1_VH_10m.tif"), vh_wgs, p_wgs)

    # SAR flood index: low VV = open water
    with np.errstate(invalid="ignore"):
        sar_flood = np.where(vv_wgs < 0.08, 1.0, 0.0).astype(np.float32)
        # SAR moisture: VH / (VV + eps), normalised
        sar_moisture = np.clip(vh_wgs / (vv_wgs + 1e-9) / 0.6, 0.0, 1.0).astype(np.float32)

    save_geotiff(os.path.join(OUTPUT_DIR, "sar_flood_index.tif"),    sar_flood,    p_wgs)
    save_geotiff(os.path.join(OUTPUT_DIR, "sar_moisture_index.tif"), sar_moisture, p_wgs)

    if lat is not None and lon is not None:
        return _sample_and_print(lat, lon, sensor="S1")
    return None


# ---------------------------------------------------------------------------
# Shared sampling + print
# ---------------------------------------------------------------------------

def _sample_and_print(lat: float, lon: float, sensor: str = "") -> dict:
    print(f"\n[sample] extracting pixel values at ({lat}, {lon}) ...")
    bands = sample_for_api(lat, lon, OUTPUT_DIR)

    valid = {k: v for k, v in bands.items() if not np.isnan(v)}
    if not valid:
        print("  WARNING: coordinates outside raster extent — check lat/lon")
        return {}

    print(f"\n--- API override values ({sensor}) ---")
    for k, v in bands.items():
        print(f"  {k}: {v}")

    print("\nPaste these into POST /api/v1/investment/grade:")
    print("{")
    print(f'  "lat": {lat},')
    print(f'  "lon": {lon},')
    for k, v in bands.items():
        print(f'  "{k}": {v},')
    print('  "user_type": "data_center"')
    print("}")
    return bands


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) >= 2:
        zip_path = sys.argv[1]
    else:
        zip_path = find_latest_zip()
        print(f"[auto] using latest zip: {zip_path}")

    lat = float(sys.argv[2]) if len(sys.argv) >= 3 else None
    lon = float(sys.argv[3]) if len(sys.argv) >= 4 else None

    if not os.path.exists(zip_path):
        print(f"ERROR: file not found: {zip_path}")
        sys.exit(1)

    if is_sentinel1(zip_path):
        print(f"[detect] Sentinel-1 product")
        process_s1(zip_path, lat, lon)
    else:
        print(f"[detect] Sentinel-2 product")
        process_s2(zip_path, lat, lon)


if __name__ == "__main__":
    main()
