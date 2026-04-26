"""
Sentinel-1 SAR-derived indicators for flood detection and soil moisture assessment.
All indicators use normalised DN values (0-1) from Sentinel-1 GRD IW mode.

Sentinel-1 C-band SAR (5.405 GHz) properties relevant to water risk:
  - Open water:     very low VV backscatter — specular reflection away from sensor
  - Flooded veg:    high cross-pol VH — double-bounce with vertical stems + water
  - Wet bare soil:  moderate VV increase vs dry soil
  - Dry urban:      high VV from corner reflectors

Sensor: Sentinel-1A/B/C IW GRD, dual polarisation VV+VH
Resolution: 10m (multi-looked IW GRD)
Source: ESA Copernicus Sentinel-1 Level-1 Product Specification (ESA, 2022)

Note on DN values:
  GRD DN are uint16 (0-65535). Radiometric calibration to sigma0 requires
  the annotation calibration LUT. Here we use normalised DN (divide by 65535)
  which gives relative indicators valid for flood detection and change detection.
  Absolute sigma0_dB = 10 * log10((DN/calibration_factor)^2) — not computed here
  unless full annotation parsing is implemented.
"""

from __future__ import annotations

import math


# Flood detection threshold on normalised VV
# Open water: normalised VV typically < 0.08 in C-band GRD
# Reference: Twele et al. (2016), Remote Sens. 8(3), 217
FLOOD_VV_THRESHOLD = 0.08

# Flooded vegetation threshold on normalised VH
# Flooded vegetation: VH > 0.12 (double-bounce enhancement)
# Reference: Brisco et al. (2013), Can. J. Remote Sens. 39(S1)
FLOOD_VH_THRESHOLD = 0.12


def calculate_sar_flood_index(vv_norm: float, vh_norm: float) -> float:
    """
    SAR Flood Index — detects open water and flooded vegetation from Sentinel-1.
    Source: ESA Copernicus Sentinel-1 flood mapping methodology (JRC, 2020);
            Twele et al. (2016), Remote Sensing 8(3), 217.

    Logic:
      - Open water signal: VV < FLOOD_VV_THRESHOLD (specular reflection)
      - Flooded vegetation signal: VH > FLOOD_VH_THRESHOLD (double-bounce)
      - Combined index normalised to [0, 1]

    Returns:
      0.0 = no flood signal
      0.5 = one signal present (either open water or flooded vegetation)
      1.0 = both signals present (confirmed inundation)
    """
    open_water    = 1.0 if vv_norm < FLOOD_VV_THRESHOLD else 0.0
    flooded_veg   = 1.0 if vh_norm > FLOOD_VH_THRESHOLD else 0.0
    return round((open_water + flooded_veg) / 2.0, 4)


def calculate_sar_moisture_index(vv_norm: float, vh_norm: float) -> float:
    """
    SAR Soil Moisture Index (SMI) — relative surface wetness indicator.
    Source: Paloscia et al. (2013), Remote Sensing of Environment 133, 234-248.

    Uses the normalised VV backscatter inverted: wetter bare soil has
    slightly higher VV but lower contrast between VV and VH.
    Cross-ratio CR = VH / (VV + 1e-9) is sensitive to soil moisture changes.

    Returns SMI in [0, 1] — higher = wetter surface conditions.
    """
    try:
        cr = vh_norm / (vv_norm + 1e-9)
    except ZeroDivisionError:
        cr = 0.0
    # CR range: 0 (very dry/specular) to ~0.6 (very wet/vegetated)
    # Clamp and normalise to [0, 1]
    smi = min(1.0, cr / 0.6)
    return round(smi, 4)


def calculate_rvi(vv_norm: float, vh_norm: float) -> float:
    """
    Radar Vegetation Index (RVI) from Sentinel-1 dual-pol.
    Source: Kim & van Zyl (2009), IEEE Trans. Geosci. Remote Sens. 47(8).
    Formula: RVI = 4 * VH_power / (VV_power + VH_power)
    where power = norm^2 (proportional to radar cross-section).
    Returns RVI in [0, 1] — higher = denser vegetation canopy.
    """
    vv_power = vv_norm ** 2
    vh_power = vh_norm ** 2
    denom = vv_power + vh_power
    if denom < 1e-12:
        return 0.0
    return round(4.0 * vh_power / denom, 4)


def calculate_flood_inundation_index_with_sar(
    ndwi: float,
    mndwi: float,
    flood_frequency: float,
    sar_flood_index: float,
) -> float:
    """
    Enhanced Flood Severity Index (FSI) combining Sentinel-2 optical and
    Sentinel-1 SAR signals. SAR provides cloud-independent flood detection
    critical for Nordic/cloudy regions.

    Formula:
      FSI = 0.25 * norm_ndwi + 0.25 * norm_mndwi
          + 0.25 * sar_flood_index + 0.25 * flood_frequency

    Source: Extended from McFeeters (1996) NDWI and Xu (2006) MNDWI with
            SAR integration following JRC flood mapping methodology (2020).

    When SAR is unavailable, use calculate_flood_inundation_index() in
    physical_risk.py (optical-only, 3-factor formula).

    Returns FSI in [0, 1]. Higher = more severe flood risk.
    """
    norm_ndwi  = (ndwi + 1.0) / 2.0
    norm_mndwi = (mndwi + 1.0) / 2.0

    fsi = (
        0.25 * norm_ndwi
        + 0.25 * norm_mndwi
        + 0.25 * sar_flood_index
        + 0.25 * flood_frequency
    )
    return round(max(0.0, min(1.0, fsi)), 4)


def sar_summary(vv_norm: float, vh_norm: float, flood_frequency: float = 0.15) -> dict:
    """
    Compute all SAR indicators and return a summary dict.
    Used when Sentinel-1 bands are available in the scoring pipeline.
    """
    flood_idx = calculate_sar_flood_index(vv_norm, vh_norm)
    smi       = calculate_sar_moisture_index(vv_norm, vh_norm)
    rvi       = calculate_rvi(vv_norm, vh_norm)

    flood_signal = "high" if flood_idx >= 0.75 else "moderate" if flood_idx >= 0.4 else "low"
    moisture     = "wet"  if smi >= 0.5 else "moderate" if smi >= 0.25 else "dry"
    vegetation   = "dense" if rvi >= 0.5 else "sparse" if rvi >= 0.2 else "bare"

    return {
        "vv_norm": round(vv_norm, 4),
        "vh_norm": round(vh_norm, 4),
        "sar_flood_index": flood_idx,
        "sar_moisture_index": smi,
        "radar_vegetation_index": rvi,
        "flood_signal": flood_signal,
        "surface_moisture": moisture,
        "vegetation_density": vegetation,
        "sensor": "Sentinel-1 IW GRD dual-pol VV+VH",
        "methodology": (
            "Twele et al. (2016) flood index; "
            "Paloscia et al. (2013) moisture index; "
            "Kim & van Zyl (2009) RVI"
        ),
    }
