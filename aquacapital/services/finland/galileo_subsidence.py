"""
Galileo HAS (High Accuracy Service) subsidence monitoring mock service.
Simulates millimetre-level vertical displacement monitoring for infrastructure
subjected to industrial water extraction.

Physical basis:
  Finland experiences significant post-glacial isostatic rebound (GIA) of +4 to +8 mm/year
  (Lidberg et al., 2010; NLS Finland EUREF-FIN reference frame).
  Industrial water extraction causes local subsidence of −0.1 to −5 mm/year.
  Net displacement = GIA_rebound − extraction_subsidence.

  Galileo HAS achieves <2 cm horizontal, <4 cm vertical accuracy (1σ) in real-time.
  With PPP-RTK correction: σ_vertical ≈ 5–10 mm, enabling meaningful subsidence detection.

Sources:
  - Lidberg et al. (2010), J. Geodesy 84:49–65 — Finnish GIA model NKG2005LU
  - ESA Galileo HAS ICD (2023), OS SIS ICD Issue 2.1
  - Peltier (2004) ICE-5G VM2 glacial isostatic model
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta

# Finnish GIA rebound rates mm/year (NKG2016LU model, Vestøl et al. 2019)
# Kajaani area: ~7 mm/year uplift
GIA_RATES_BY_REGION: dict[str, float] = {
    "kajaani":    7.2,
    "helsinki":   4.3,
    "oulu":       8.1,
    "tampere":    5.1,
    "turku":      3.8,
    "rovaniemi":  9.4,
    "default":    6.0,
}

# Extraction subsidence rates by activity level (mm/year, negative = downward)
EXTRACTION_SUBSIDENCE: dict[str, float] = {
    "none":     0.0,
    "low":     -0.3,    # <100 m³/day
    "moderate":-1.2,    # 100–500 m³/day
    "high":    -3.5,    # 500–2000 m³/day
    "extreme": -7.0,    # >2000 m³/day
}

# Galileo HAS measurement uncertainty (1σ, mm)
HAS_SIGMA_VERTICAL = 8.0
HAS_SIGMA_HORIZONTAL = 4.0


def _gia_rate(lat: float, lon: float) -> float:
    """
    Return GIA uplift rate in mm/year using NKG2016LU model approximation.
    For Finland: uplift increases from south (~3 mm) to north (~10 mm).
    Linear interpolation: rate ≈ -0.17 × lat + 18.2 (simplified)
    Source: NKG2016LU, Vestøl et al. (2019).
    """
    if 60 <= lat <= 70 and 20 <= lon <= 32:  # Finland bounding box
        return round(-0.17 * lat + 18.2, 2)
    return GIA_RATES_BY_REGION["default"]


def _extraction_level(abstraction_m3day: float) -> str:
    if abstraction_m3day <= 0:       return "none"
    if abstraction_m3day < 100:      return "low"
    if abstraction_m3day < 500:      return "moderate"
    if abstraction_m3day < 2000:     return "high"
    return "extreme"


def simulate_galileo_has_monitoring(
    lat: float,
    lon: float,
    abstraction_m3day: float = 300.0,
    monitoring_months: int = 24,
    seed: int | None = None,
) -> dict:
    """
    Simulate Galileo HAS PPP-RTK vertical displacement time series.
    Returns monthly displacement readings in mm with realistic noise and trend.

    The simulation models:
    1. Steady GIA uplift (deterministic trend from NKG2016LU)
    2. Extraction-induced subsidence (counter-trend)
    3. Seasonal soil moisture variation (sinusoidal, ±3 mm amplitude)
    4. Galileo HAS measurement noise (Gaussian, σ = 8 mm vertical)
    """
    if seed is not None:
        random.seed(seed)

    gia_rate_yr = _gia_rate(lat, lon)
    ext_level   = _extraction_level(abstraction_m3day)
    ext_rate_yr = EXTRACTION_SUBSIDENCE[ext_level]

    net_rate_yr     = gia_rate_yr + ext_rate_yr       # mm/year (positive = uplift)
    net_rate_month  = net_rate_yr / 12.0

    readings = []
    cumulative_mm = 0.0
    base_date = datetime.utcnow() - timedelta(days=monitoring_months * 30)

    for m in range(monitoring_months):
        date = base_date + timedelta(days=m * 30)

        # Deterministic trend
        trend = net_rate_month * m

        # Seasonal variation (soil moisture / thermal expansion)
        seasonal = 3.0 * math.sin(2 * math.pi * m / 12)

        # Galileo HAS noise
        noise = random.gauss(0, HAS_SIGMA_VERTICAL / math.sqrt(4))  # 4 obs averaged

        displacement = trend + seasonal + noise
        cumulative_mm = trend  # noise-free cumulative for alert logic

        readings.append({
            "month": date.strftime("%Y-%m"),
            "displacement_mm": round(displacement, 2),
            "cumulative_trend_mm": round(cumulative_mm, 2),
            "gia_contribution_mm": round(net_rate_month * m, 2),
            "extraction_contribution_mm": round(ext_rate_yr / 12 * m, 2),
        })

    # Alert thresholds
    total_trend = net_rate_yr * (monitoring_months / 12)
    alert_level = "green"
    alert_msg   = "Stable — GIA uplift dominant"

    if ext_rate_yr < -5.0:
        alert_level = "red"
        alert_msg   = "Critical subsidence risk — extraction exceeds GIA uplift"
    elif net_rate_yr < 0:
        alert_level = "amber"
        alert_msg   = "Net subsidence detected — extraction partially offsetting GIA"
    elif total_trend < 2.0:
        alert_level = "yellow"
        alert_msg   = "Near-neutral displacement — monitor closely"

    return {
        "location": {"lat": lat, "lon": lon},
        "monitoring_period_months": monitoring_months,
        "gia_uplift_rate_mm_yr": gia_rate_yr,
        "extraction_subsidence_rate_mm_yr": ext_rate_yr,
        "net_vertical_rate_mm_yr": round(net_rate_yr, 2),
        "extraction_level": ext_level,
        "abstraction_m3day": abstraction_m3day,
        "alert": {
            "level": alert_level,
            "message": alert_msg,
            "safe_for_infrastructure": alert_level == "green",
        },
        "instrument": {
            "service": "Galileo HAS PPP-RTK (simulated)",
            "sigma_vertical_mm": HAS_SIGMA_VERTICAL,
            "sigma_horizontal_mm": HAS_SIGMA_HORIZONTAL,
            "esa_reference": "ESA Galileo HAS ICD (2023), OS SIS ICD Issue 2.1",
        },
        "gia_model": "NKG2016LU (Vestøl et al., 2019), Lidberg et al. (2010)",
        "monthly_readings": readings,
        "total_displacement_trend_mm": round(total_trend, 2),
    }
