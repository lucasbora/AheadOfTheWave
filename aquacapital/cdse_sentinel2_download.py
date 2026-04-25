"""
Copernicus CDSE OData API — Sentinel-2 L2A search and download.
Area: bounding box around Bucharest, Romania
Filter: cloud cover < 20 %, last 30 days
Auth: username / password -> Keycloak OAuth2 token
"""

import sys
import os
from datetime import datetime, timedelta, timezone

import requests 

# ---------------------------------------------------------------------------
# Configuration — edit or export as env vars
# ---------------------------------------------------------------------------
USERNAME = os.environ.get("CDSE_USER", "your_email@example.com")
PASSWORD = os.environ.get("CDSE_PASS", "your_password")

# Bounding box around Bucharest  (lon_min, lat_min, lon_max, lat_max)
BBOX = (25.60, 43.90, 26.60, 44.90)

CLOUD_COVER_MAX = 20.0      # percent
DAYS_BACK = 30
OUTPUT_DIR = "."            # where to save the downloaded file

# ---------------------------------------------------------------------------
# CDSE endpoints
# ---------------------------------------------------------------------------
TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu"
    "/auth/realms/CDSE/protocol/openid-connect/token"
)
SEARCH_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
DOWNLOAD_BASE = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"


# ---------------------------------------------------------------------------
def get_token(username: str, password: str) -> str:
    """Obtain a short-lived Bearer token from CDSE Keycloak."""
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
    token = response.json()["access_token"]
    print("[auth] token acquired")
    return token


def build_filter(bbox: tuple, cloud_max: float, days_back: int) -> str:
    """Build the OData $filter string."""
    lon_min, lat_min, lon_max, lat_max = bbox

    # WKT polygon — close the ring
    wkt = (
        f"POLYGON(("
        f"{lon_min} {lat_min},"
        f"{lon_max} {lat_min},"
        f"{lon_max} {lat_max},"
        f"{lon_min} {lat_max},"
        f"{lon_min} {lat_min}"
        f"))"
    )

    now = datetime.now(timezone.utc)
    date_start = (now - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    date_end = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    parts = [
        "Collection/Name eq 'SENTINEL-2'",
        # L2A product type
        (
            "Attributes/OData.CSC.StringAttribute/any("
            "att:att/Name eq 'productType' and "
            "att/OData.CSC.StringAttribute/Value eq 'S2MSI2A')"
        ),
        # spatial intersection
        f"OData.CSC.Intersects(area=geography'SRID=4326;{wkt}')",
        # date range
        f"ContentDate/Start gt {date_start}",
        f"ContentDate/Start lt {date_end}",
        # cloud cover
        (
            f"Attributes/OData.CSC.DoubleAttribute/any("
            f"att:att/Name eq 'cloudCover' and "
            f"att/OData.CSC.DoubleAttribute/Value lt {cloud_max:.2f})"
        ),
    ]
    return " and ".join(parts)


def search_products(filter_str: str, max_results: int = 5) -> list[dict]:
    """Query the OData catalogue and return a list of product dicts."""
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


def download_product(product: dict, token: str, output_dir: str) -> str:
    """Stream-download a product by its Id and return the local file path."""
    product_id = product["Id"]
    product_name = product.get("Name", product_id)
    url = f"{DOWNLOAD_BASE}({product_id})/$value"

    output_path = os.path.join(output_dir, f"{product_name}.zip")

    print(f"[download] {product_name}")
    print(f"           dest : {output_path}")

    # CDSE redirects catalogue -> download subdomain; requests strips the
    # Authorization header on cross-domain redirects, causing a 401.
    # Resolve the redirect manually so the token travels with every hop.
    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {token}"

    download_url = url
    for _ in range(10):
        r = session.get(download_url, allow_redirects=False, timeout=30)
        if r.status_code in (301, 302, 303, 307, 308):
            download_url = r.headers["Location"]
            print(f"           -> {download_url}")
        else:
            break

    print(f"           url  : {download_url}")

    with session.get(download_url, stream=True, timeout=600) as response:
        response.raise_for_status()
        total = int(response.headers.get("Content-Length", 0))
        downloaded = 0
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):  # 1 MB
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    print(f"\r           {pct:5.1f}%  ({downloaded/1e6:.1f} / {total/1e6:.1f} MB)", end="", flush=True)
    print()  # newline after progress
    print(f"[download] complete -> {output_path}")
    return output_path


# ---------------------------------------------------------------------------
def main():
    if "your_email" in USERNAME:
        print(
            "Set CDSE_USER and CDSE_PASS environment variables (or edit USERNAME/PASSWORD in the script)."
        )
        sys.exit(1)

    token = get_token(USERNAME, PASSWORD)

    filter_str = build_filter(BBOX, CLOUD_COVER_MAX, DAYS_BACK)
    print(f"[search] filter:\n  {filter_str}\n")

    products = search_products(filter_str)
    if not products:
        print("[search] no products found — try widening the date range or cloud cover threshold")
        sys.exit(0)

    # Print summary table
    print(f"\n{'#':<4} {'Name':<70} {'Cloud%':>7} {'Date'}")
    print("-" * 95)
    for i, p in enumerate(products):
        cloud = next(
            (
                a["Value"]
                for a in p.get("Attributes", [])
                if a.get("Name") == "cloudCover"
            ),
            "n/a",
        )
        date = p.get("ContentDate", {}).get("Start", "")[:10]
        print(f"{i:<4} {p['Name']:<70} {str(cloud):>7} {date}")
    print()

    first = products[0]
    download_product(first, token, OUTPUT_DIR)


if __name__ == "__main__":
    main()
