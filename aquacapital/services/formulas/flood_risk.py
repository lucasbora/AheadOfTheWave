"""
Flood risk formulas based on WRI Aqueduct Floods Methodology.
Source: Ward et al. (2020), Huizinga et al. (2017), Scussolini et al. (2016).
"""

import math


_CONTENT_FACTORS: dict[str, float] = {
    "residential": 0.5,
    "commercial": 1.0,
    "industrial": 1.5,
    "data_center": 3.0,
}

_DEPRECIATION_FACTOR = 0.6
_UNDAMAGEABLE_FACTOR = 0.6
_HUIZINGA_A = 24.08
_HUIZINGA_B = 0.385


def _structural_cost_usd(gdp_per_capita: float) -> float:
    """Huizinga et al. (2017) GDP-based structural replacement cost formula: y = a * x^b."""
    try:
        return _HUIZINGA_A * math.pow(gdp_per_capita, _HUIZINGA_B)
    except (ValueError, ZeroDivisionError):
        return 0.0


def _depth_damage_fraction(flood_depth_m: float) -> float:
    """
    Simplified piecewise depth-damage function.
    At 0 m → 0; at 1 m → 0.35; at 3 m → 0.65; at 6 m → 0.85; at >=10 m → 1.0.
    Linear interpolation between breakpoints.
    """
    breakpoints = [(0.0, 0.0), (1.0, 0.35), (3.0, 0.65), (6.0, 0.85), (10.0, 1.0)]
    if flood_depth_m <= 0.0:
        return 0.0
    if flood_depth_m >= 10.0:
        return 1.0
    for i in range(len(breakpoints) - 1):
        x0, y0 = breakpoints[i]
        x1, y1 = breakpoints[i + 1]
        if x0 <= flood_depth_m <= x1:
            try:
                return y0 + (flood_depth_m - x0) * (y1 - y0) / (x1 - x0)
            except ZeroDivisionError:
                return y0
    return 1.0


def _damage_category(total_index: float) -> str:
    if total_index < 0.05:
        return "negligible"
    if total_index < 0.20:
        return "low"
    if total_index < 0.45:
        return "moderate"
    if total_index < 0.70:
        return "high"
    return "critical"


def calculate_expected_annual_damage_index(
    flood_depth_m: float,
    return_period_years: int,
    land_use_type: str = "industrial_park",
    gdp_per_capita_usd: float = 14000.0,
) -> dict:
    """
    Simplified EAD calculation based on WRI Aqueduct Floods methodology.
    Source: Ward et al. (2020), Huizinga et al. (2017).

    Uses depth-damage functions per occupancy type:
    - residential:  content factor 0.5x structural cost
    - commercial:   content factor 1.0x structural cost
    - industrial:   content factor 1.5x structural cost
    - data_center:  content factor 3.0x structural cost

    Structural cost from GDP per capita using Huizinga et al. (2017) formula: y = a * x^b
    (a=24.08, b=0.385 for residential).
    Depreciation factor: 0.6. Undamageable parts factor: 0.6.

    Returns dict with structural_damage_index, content_damage_index, total_damage_index,
    damage_category, occupancy_type.
    """
    occupancy = land_use_type if land_use_type in _CONTENT_FACTORS else "industrial"
    content_factor = _CONTENT_FACTORS[occupancy]

    depth_fraction = _depth_damage_fraction(flood_depth_m)

    structural_cost = _structural_cost_usd(gdp_per_capita_usd)
    try:
        structural_damage_index = (
            depth_fraction * _DEPRECIATION_FACTOR * _UNDAMAGEABLE_FACTOR
        )
    except ZeroDivisionError:
        structural_damage_index = 0.0

    content_damage_index = min(1.0, structural_damage_index * content_factor)

    # Scale total by content_factor relative to residential baseline (1.5).
    # Higher content_factor (data_center=4.0) produces a proportionally larger index
    # than residential (1.5), reflecting higher-value asset exposure per Huizinga et al.
    total_damage_index = min(
        1.0, structural_damage_index * (1.0 + content_factor) / 1.5
    )

    # Annual probability weight
    try:
        annual_prob = 1.0 / return_period_years
    except ZeroDivisionError:
        annual_prob = 0.0

    weighted_total = min(1.0, total_damage_index * (1.0 + annual_prob))

    return {
        "structural_damage_index": round(structural_damage_index, 4),
        "content_damage_index": round(content_damage_index, 4),
        "total_damage_index": round(weighted_total, 4),
        "damage_category": _damage_category(weighted_total),
        "occupancy_type": occupancy,
    }


def calculate_flood_protection_standard_risk(protection_return_period: int) -> int:
    """
    Based on FLOPROS methodology. Source: Scussolini et al. (2016), Ward et al. (2020).
    Assesses adequacy of existing flood protection infrastructure.
    protection_return_period: current flood protection standard in years.

    Risk values:
    - >=500 year: 1 (Very Low)
    - 100-499 year: 2 (Low)
    - 50-99 year: 3 (Moderate)
    - 10-49 year: 4 (High)
    - <10 year: 5 (Very High)
    Returns risk value 1-5.
    """
    if protection_return_period >= 500:
        return 1
    if protection_return_period >= 100:
        return 2
    if protection_return_period >= 50:
        return 3
    if protection_return_period >= 10:
        return 4
    return 5
