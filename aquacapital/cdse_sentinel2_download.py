"""
Sentinel-2 L2A download script.
Reads credentials from .env via config.py.
Downloads to data/processed/ inside the aquacapital project.
Usage:
    python cdse_sentinel2_download.py                        # Bucharest defaults
    python cdse_sentinel2_download.py 44.43 26.10 5          # lat lon buffer_km
"""

import sys
import os
from datetime import datetime, timedelta, timezone
import math

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
SEARCH_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
DOWNLOAD_BASE = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"

CLOUD_COVER_MAX = 20.0
DAYS_BACK = 60


def get_token(username: str, password: str) -> str:
    response = requests.post(
        TOKEN_URL,
        data={
            "client_id": "cdse-public",
            "grant_type": "password",
            "username": username,
            "password": password,
        },
        timeout=30,
    )
    response.raise_for_status()
    print("[auth] token acquired")
    return response.json()["access_token"]


def build_bbox(lat: float, lon: float, buffer_km: float) -> tuple:
    """Bounding box from lat/lon using Haversine-derived degree offset."""
    delta_lat = buffer_km / 111.0
    delta_lon = buffer_km / (111.0 * math.cos(math.radians(lat)))
    return (lon - delta_lon, lat - delta_lat, lon + delta_lon, lat + delta_lat)


def build_filter(bbox: tuple, cloud_max: float, days_back: int) -> str:
    lon_min, lat_min, lon_max, lat_max = bbox
    wkt = (
        f"POLYGON(("
        f"{lon_min} {lat_min},{lon_max} {lat_min},"
        f"{lon_max} {lat_max},{lon_min} {lat_max},"
        f"{lon_min} {lat_min}))"
    )
    now = datetime.now(timezone.utc)
    date_start = (now - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    date_end = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return " and ".join([
        "Collection/Name eq 'SENTINEL-2'",
        "Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' and att/OData.CSC.StringAttribute/Value eq 'S2MSI2A')",
        f"OData.CSC.Intersects(area=geography'SRID=4326;{wkt}')",
        f"ContentDate/Start gt {date_start}",
        f"ContentDate/Start lt {date_end}",
        f"Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' and att/OData.CSC.DoubleAttribute/Value lt {cloud_max:.2f})",
    ])


def search_products(filter_str: str, max_results: int = 5) -> list[dict]:
    params = {
        "$filter": filter_str,
        "$orderby": "ContentDate/Start desc",
        "$top": max_results,
        "$expand": "Attributes",
    }
    response = requests.get(SEARCH_URL, params=params, timeout=60)
    response.raise_for_status()
    products = response.json().get("value", [])
    print(f"[search] {len(products)} product(s) returned")
    return products


def _resolve_redirect(session: requests.Session, url: str) -> str:
    """Follow redirects manually so Authorization header is preserved across domains."""
    for _ in range(10):
        r = session.get(url, allow_redirects=False, timeout=30)
        if r.status_code in (301, 302, 303, 307, 308):
            url = r.headers["Location"]
            print(f"           -> {url}")
        else:
            break
    return url


def download_product(product: dict, token: str, output_dir: str, max_retries: int = 5) -> str:
    """
    Stream-download with resume support and automatic retry.
    Uses HTTP Range header to continue interrupted downloads from the byte offset
    of any existing partial file — avoids re-downloading from zero on connection drops.
    """
    product_id   = product["Id"]
    product_name = product.get("Name", product_id)
    url          = f"{DOWNLOAD_BASE}({product_id})/$value"
    os.makedirs(output_dir, exist_ok=True)
    output_path  = os.path.join(output_dir, f"{product_name}.zip")

    # Already fully downloaded
    if os.path.exists(output_path) and not os.path.exists(output_path + ".part"):
        print(f"[download] already complete, skipping: {output_path}")
        return output_path

    part_path = output_path + ".part"
    print(f"[download] {product_name}")
    print(f"           dest : {output_path}")

    for attempt in range(1, max_retries + 1):
        session = requests.Session()
        session.headers["Authorization"] = f"Bearer {token}"

        # Check how many bytes we already have
        existing_bytes = os.path.getsize(part_path) if os.path.exists(part_path) else 0
        if existing_bytes:
            print(f"           resuming from {existing_bytes / 1e6:.1f} MB (attempt {attempt})")
            session.headers["Range"] = f"bytes={existing_bytes}-"

        try:
            download_url = _resolve_redirect(session, url)
            with session.get(download_url, stream=True, timeout=600) as response:
                if response.status_code == 416:
                    # Range not satisfiable — file already complete
                    os.rename(part_path, output_path)
                    print(f"\n[download] complete -> {output_path}")
                    return output_path
                response.raise_for_status()

                total = int(response.headers.get("Content-Length", 0)) + existing_bytes
                downloaded = existing_bytes

                with open(part_path, "ab") as f:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            pct = downloaded / total * 100
                            print(
                                f"\r           {pct:5.1f}%  "
                                f"({downloaded/1e6:.1f} / {total/1e6:.1f} MB)",
                                end="", flush=True,
                            )

            # Download finished — rename .part -> .zip
            print()
            os.rename(part_path, output_path)
            print(f"[download] complete -> {output_path}")
            return output_path

        except Exception as exc:
            print(f"\n[download] attempt {attempt}/{max_retries} failed: {exc}")
            if attempt == max_retries:
                raise
            print(f"           retrying ...")

    raise RuntimeError("Download failed after all retries")


def download_for_location(lat: float, lon: float, buffer_km: float = 5.0) -> str:
    """Importable entry point: download best product for a location, return zip path."""
    if not USERNAME or not PASSWORD:
        raise RuntimeError("CDSE_USER and CDSE_PASSWORD must be set in aquacapital/.env")
    token = get_token(USERNAME, PASSWORD)
    bbox = build_bbox(lat, lon, buffer_km)
    filter_str = build_filter(bbox, CLOUD_COVER_MAX, DAYS_BACK)
    products = search_products(filter_str)
    if not products:
        raise RuntimeError(f"No Sentinel-2 products found for ({lat}, {lon}) in the last {DAYS_BACK} days")
    return download_product(products[0], token, OUTPUT_DIR)


def main():
    if not USERNAME or not PASSWORD:
        print("ERROR: Set CDSE_USER and CDSE_PASSWORD in aquacapital/.env")
        sys.exit(1)

    lat = float(sys.argv[1]) if len(sys.argv) > 1 else 44.43
    lon = float(sys.argv[2]) if len(sys.argv) > 2 else 26.10
    buffer_km = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0

    print(f"[config] location: ({lat}, {lon}), buffer: {buffer_km} km")

    token = get_token(USERNAME, PASSWORD)
    bbox = build_bbox(lat, lon, buffer_km)
    filter_str = build_filter(bbox, CLOUD_COVER_MAX, DAYS_BACK)
    print(f"[search] filter built, searching ...\n")

    products = search_products(filter_str)
    if not products:
        print("[search] no products found — try increasing DAYS_BACK or cloud cover threshold")
        sys.exit(0)

    print(f"\n{'#':<4} {'Name':<70} {'Cloud%':>7} {'Date'}")
    print("-" * 95)
    for i, p in enumerate(products):
        cloud = next(
            (a["Value"] for a in p.get("Attributes", []) if a.get("Name") == "cloudCover"),
            "n/a",
        )
        date = p.get("ContentDate", {}).get("Start", "")[:10]
        print(f"{i:<4} {p['Name']:<70} {str(cloud):>7} {date}")
    print()

    zip_path = download_product(products[0], token, OUTPUT_DIR)
    print(f"\nNext step: python ingest.py \"{zip_path}\" {lat} {lon}")


if __name__ == "__main__":
    main()
