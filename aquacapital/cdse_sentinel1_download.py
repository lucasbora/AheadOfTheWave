"""
Sentinel-1 GRD download from CDSE OData API.
SAR backscatter penetrates cloud cover — critical for Nordic/Finnish weather patterns.
Downloads IW GRD dual-polarisation (VV+VH) products.

Usage:
    python cdse_sentinel1_download.py                        # Kajaani defaults
    python cdse_sentinel1_download.py 64.2245 27.7177 10     # lat lon buffer_km
    python cdse_sentinel1_download.py 44.43 26.1 5           # Bucharest
"""

import sys
import os
import math
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

USERNAME = os.environ.get("CDSE_USER", "")
PASSWORD = os.environ.get("CDSE_PASSWORD", "")

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data", "processed")

TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu"
    "/auth/realms/CDSE/protocol/openid-connect/token"
)
SEARCH_URL   = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
DOWNLOAD_BASE = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"

DAYS_BACK = 30


def get_token(username: str, password: str) -> str:
    r = requests.post(
        TOKEN_URL,
        data={"client_id": "cdse-public", "grant_type": "password",
              "username": username, "password": password},
        timeout=30,
    )
    r.raise_for_status()
    print("[auth] token acquired")
    return r.json()["access_token"]


def build_bbox(lat: float, lon: float, buffer_km: float) -> tuple:
    delta_lat = buffer_km / 111.0
    delta_lon = buffer_km / (111.0 * math.cos(math.radians(lat)))
    return (lon - delta_lon, lat - delta_lat, lon + delta_lon, lat + delta_lat)


def build_filter(bbox: tuple, days_back: int) -> str:
    lon_min, lat_min, lon_max, lat_max = bbox
    wkt = (
        f"POLYGON(("
        f"{lon_min} {lat_min},{lon_max} {lat_min},"
        f"{lon_max} {lat_max},{lon_min} {lat_max},"
        f"{lon_min} {lat_min}))"
    )
    now = datetime.now(timezone.utc)
    date_start = (now - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    date_end   = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    return " and ".join([
        "Collection/Name eq 'SENTINEL-1'",
        # IW GRD — Interferometric Wide swath, Ground Range Detected
        "Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' and att/OData.CSC.StringAttribute/Value eq 'GRD')",
        "Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'operationalMode' and att/OData.CSC.StringAttribute/Value eq 'IW')",
        f"OData.CSC.Intersects(area=geography'SRID=4326;{wkt}')",
        f"ContentDate/Start gt {date_start}",
        f"ContentDate/Start lt {date_end}",
    ])


def search_products(filter_str: str, max_results: int = 5) -> list[dict]:
    r = requests.get(SEARCH_URL, params={
        "$filter": filter_str,
        "$orderby": "ContentDate/Start desc",
        "$top": max_results,
        "$expand": "Attributes",
    }, timeout=60)
    r.raise_for_status()
    products = r.json().get("value", [])
    print(f"[search] {len(products)} Sentinel-1 GRD product(s) returned")
    return products


def _resolve_redirect(session: requests.Session, url: str) -> str:
    for _ in range(10):
        r = session.get(url, allow_redirects=False, timeout=30)
        if r.status_code in (301, 302, 303, 307, 308):
            url = r.headers["Location"]
            print(f"           -> {url}")
        else:
            break
    return url


def download_product(product: dict, token: str, output_dir: str,
                     max_retries: int = 5) -> str:
    """Stream-download with resume support and automatic retry."""
    product_id   = product["Id"]
    product_name = product.get("Name", product_id)
    url          = f"{DOWNLOAD_BASE}({product_id})/$value"
    os.makedirs(output_dir, exist_ok=True)
    output_path  = os.path.join(output_dir, f"{product_name}.zip")
    part_path    = output_path + ".part"

    if os.path.exists(output_path) and not os.path.exists(part_path):
        print(f"[download] already complete: {output_path}")
        return output_path

    print(f"[download] {product_name}")
    print(f"           dest : {output_path}")

    for attempt in range(1, max_retries + 1):
        session = requests.Session()
        session.headers["Authorization"] = f"Bearer {token}"

        existing = os.path.getsize(part_path) if os.path.exists(part_path) else 0
        if existing:
            print(f"           resuming from {existing/1e6:.1f} MB (attempt {attempt})")
            session.headers["Range"] = f"bytes={existing}-"

        try:
            dl_url = _resolve_redirect(session, url)
            with session.get(dl_url, stream=True, timeout=600) as response:
                if response.status_code == 416:
                    os.rename(part_path, output_path)
                    print(f"\n[download] complete -> {output_path}")
                    return output_path
                response.raise_for_status()

                total      = int(response.headers.get("Content-Length", 0)) + existing
                downloaded = existing

                with open(part_path, "ab") as f:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            pct = downloaded / total * 100
                            print(f"\r           {pct:5.1f}%  ({downloaded/1e6:.1f} / {total/1e6:.1f} MB)",
                                  end="", flush=True)

            print()
            os.rename(part_path, output_path)
            print(f"[download] complete -> {output_path}")
            return output_path

        except Exception as exc:
            print(f"\n[download] attempt {attempt}/{max_retries} failed: {exc}")
            if attempt == max_retries:
                raise
            print("           retrying ...")

    raise RuntimeError("Download failed after all retries")


def main():
    if not USERNAME or not PASSWORD:
        print("ERROR: Set CDSE_USER and CDSE_PASSWORD in aquacapital/.env")
        sys.exit(1)

    lat       = float(sys.argv[1]) if len(sys.argv) > 1 else 64.2245
    lon       = float(sys.argv[2]) if len(sys.argv) > 2 else 27.7177
    buffer_km = float(sys.argv[3]) if len(sys.argv) > 3 else 10.0

    print(f"[config] Sentinel-1 IW GRD search")
    print(f"         location: ({lat}, {lon}), buffer: {buffer_km} km")
    print(f"         last {DAYS_BACK} days\n")

    token      = get_token(USERNAME, PASSWORD)
    bbox       = build_bbox(lat, lon, buffer_km)
    filter_str = build_filter(bbox, DAYS_BACK)

    products = search_products(filter_str)
    if not products:
        print("[search] no Sentinel-1 GRD products found — try increasing DAYS_BACK or buffer_km")
        sys.exit(0)

    print(f"\n{'#':<4} {'Name':<80} {'Date'}")
    print("-" * 90)
    for i, p in enumerate(products):
        date = p.get("ContentDate", {}).get("Start", "")[:10]
        print(f"{i:<4} {p['Name']:<80} {date}")
    print()

    zip_path = download_product(products[0], token, OUTPUT_DIR)
    print(f"\nNext step: python ingest.py \"{zip_path}\" {lat} {lon}")


if __name__ == "__main__":
    main()
