"""
Investment Grade engine — aggregates all risk dimensions into a final investability score.
Weights sourced from WWF WRF v3.0 sector-specific logic and WRI Aqueduct Floods methodology.
"""

from __future__ import annotations

_USER_TYPE_WEIGHTS: dict[str, dict[str, float]] = {
    "data_center": {
        "physical_risk": 0.40,
        "regulatory_risk": 0.20,
        "compliance": 0.15,
        "ead_index": 0.25,
    },
    "industrial_park": {
        "physical_risk": 0.35,
        "regulatory_risk": 0.25,
        "compliance": 0.25,
        "ead_index": 0.15,
    },
    "logistics": {
        "physical_risk": 0.45,
        "regulatory_risk": 0.15,
        "compliance": 0.15,
        "ead_index": 0.25,
    },
    "residential_developer": {
        "physical_risk": 0.30,
        "regulatory_risk": 0.30,
        "compliance": 0.30,
        "ead_index": 0.10,
    },
    "generic_investor": {
        "physical_risk": 0.30,
        "regulatory_risk": 0.25,
        "compliance": 0.25,
        "ead_index": 0.20,
    },
}

_GRADE_THRESHOLDS: list[tuple[float, str, str]] = [
    (88.0, "A+", "Prime Investment Zone"),
    (80.0, "A", "Investment Grade"),
    (65.0, "B", "Acceptable with Mitigation"),
    (50.0, "C", "Elevated Risk — Due Diligence Required"),
    (35.0, "D", "High Risk — Avoid or Hedge"),
    (0.0, "F", "No-Go Zone"),
]


def _normalize_risk(risk_value: int) -> float:
    """Convert 1-5 WWF risk scale to 0-1 (1=0.0, 5=1.0)."""
    try:
        return (risk_value - 1) / 4.0
    except ZeroDivisionError:
        return 0.0


def _grade(score: float) -> tuple[str, str]:
    for threshold, grade, label in _GRADE_THRESHOLDS:
        if score >= threshold:
            return grade, label
    return "F", "No-Go Zone"


def _recommendation_summary(grade: str, user_type: str, score: float) -> str:
    profile_labels = {
        "data_center": "data center development",
        "industrial_park": "industrial park development",
        "logistics": "logistics hub development",
        "residential_developer": "residential development",
        "generic_investor": "investment",
    }
    label = profile_labels.get(user_type, "investment")
    if grade in ("A+", "A"):
        return f"Location scores {score:.1f}/100 — strong suitability for {label} with low water risk exposure."
    if grade == "B":
        return f"Location scores {score:.1f}/100 — viable for {label} subject to targeted flood and regulatory mitigation."
    if grade == "C":
        return f"Location scores {score:.1f}/100 — elevated water risk for {label}; independent due diligence and risk hedging required."
    if grade == "D":
        return f"Location scores {score:.1f}/100 — high water risk profile; {label} should be avoided unless risk premiums are reflected in asset pricing."
    return f"Location scores {score:.1f}/100 — no-go zone for {label} under current water risk conditions."


def calculate_wwf_physical_risk_composite(
    water_availability_risks: list[int],
    drought_risks: list[int],
    flood_risks: list[int],
    water_quality_risk: int,
    fsi: float,
) -> dict:
    """
    Composite Physical Risk following WWF WRF v3.0 weighting logic.
    Source: WWF WRF Methodology Documentation v3.0.

    Category weights (industrial/commercial sector):
    - Water Availability (BRC1): 25%
    - Drought (BRC2): 15%
    - Flooding (BRC3): 35%  ← highest for industrial RE
    - Water Quality (BRC4): 25%

    Within flooding: occurrence 50%, hazard 50%.
    FSI > 0.6 applies a 1.2x multiplier to flood score (capped at 1.0).
    Returns normalized composite 0-1 and breakdown dict.
    """
    try:
        wa_score = _normalize_risk(round(sum(water_availability_risks) / len(water_availability_risks)))
    except ZeroDivisionError:
        wa_score = 0.5

    try:
        drought_score = _normalize_risk(round(sum(drought_risks) / len(drought_risks)))
    except ZeroDivisionError:
        drought_score = 0.5

    try:
        flood_score = _normalize_risk(round(sum(flood_risks) / len(flood_risks)))
    except ZeroDivisionError:
        flood_score = 0.5

    if fsi > 0.6:
        flood_score = min(1.0, flood_score * 1.2)

    wq_score = _normalize_risk(water_quality_risk)

    composite = (
        0.25 * wa_score
        + 0.15 * drought_score
        + 0.35 * flood_score
        + 0.25 * wq_score
    )

    return {
        "composite": round(composite, 4),
        "water_availability_risk": round(wa_score, 4),
        "drought_risk": round(drought_score, 4),
        "flood_risk": round(flood_score, 4),
        "water_quality_risk": round(wq_score, 4),
        "fsi": round(fsi, 4),
        "category_contributions": {
            "water_availability": round(0.25 * wa_score, 4),
            "drought": round(0.15 * drought_score, 4),
            "flooding": round(0.35 * flood_score, 4),
            "water_quality": round(0.25 * wq_score, 4),
        },
    }


def calculate_investment_grade(
    physical_risk_score: float,
    regulatory_risk_score: float,
    compliance_score: float,
    ead_index: float,
    user_type: str = "generic_investor",
) -> dict:
    """
    Final Investment Grade Calculator.

    Formula: raw_score = (1-physical)*w1 + (1-regulatory)*w2 + compliance*w3 + (1-ead)*w4
    final_score = raw_score * 100, rounded to 2 decimals.

    Grade mapping:
    A+>=88, A>=80, B>=65, C>=50, D>=35, F<35.
    Returns score, grade, grade_label, breakdown, user_type, recommendation_summary.
    """
    weights = _USER_TYPE_WEIGHTS.get(user_type, _USER_TYPE_WEIGHTS["generic_investor"])

    w1 = weights["physical_risk"]
    w2 = weights["regulatory_risk"]
    w3 = weights["compliance"]
    w4 = weights["ead_index"]

    raw_score = (
        (1.0 - physical_risk_score) * w1
        + (1.0 - regulatory_risk_score) * w2
        + compliance_score * w3
        + (1.0 - ead_index) * w4
    )

    final_score = round(raw_score * 100.0, 2)
    grade, grade_label = _grade(final_score)

    return {
        "score": final_score,
        "grade": grade,
        "grade_label": grade_label,
        "breakdown": {
            "physical_risk_contribution": round((1.0 - physical_risk_score) * w1 * 100, 2),
            "regulatory_risk_contribution": round((1.0 - regulatory_risk_score) * w2 * 100, 2),
            "compliance_contribution": round(compliance_score * w3 * 100, 2),
            "ead_contribution": round((1.0 - ead_index) * w4 * 100, 2),
        },
        "user_type": user_type,
        "recommendation_summary": _recommendation_summary(grade, user_type, final_score),
    }


def compare_locations(locations: list[dict], user_type: str) -> list[dict]:
    """
    Compares multiple locations and returns them ranked by investment grade (best first).
    Each location dict must contain score, grade, grade_label, and location_name.
    Returns sorted list with rank and delta_from_best added.
    """
    sorted_locs = sorted(locations, key=lambda x: x.get("score", 0.0), reverse=True)
    best_score = sorted_locs[0]["score"] if sorted_locs else 0.0

    for rank, loc in enumerate(sorted_locs, start=1):
        loc["rank"] = rank
        loc["delta_from_best"] = round(loc.get("score", 0.0) - best_score, 2)

    return sorted_locs
