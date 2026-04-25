"""
Regulatory Deficiency Risk engine.
Source: WWF WRF v3.0 Sections 7-14, Wingard et al. (2026), Legal Atlas methodology.
"""

_CRITERIA_WEIGHTS: dict[str, float] = {
    "iwrm_policy_exists": 10.0,
    "iwrm_in_law": 10.0,
    "water_authority_exists": 8.0,
    "water_authority_has_enforcement": 12.0,
    "clean_water_standards_penalties": 10.0,
    "wastewater_penalties": 10.0,
    "wetland_harm_penalties": 8.0,
    "water_management_plans_required": 10.0,
    "plans_enforceable": 12.0,
    "monitoring_water_quality": 5.0,
    "flood_disaster_framework": 5.0,
}

_GOVERNANCE_RISK_MAP: list[tuple[float, int]] = [
    (1.5, 1),
    (0.5, 2),
    (-0.5, 3),
    (-1.5, 4),
]


def _governance_to_risk(governance_score: float) -> int:
    """Map World Bank governance score (-2.5 to +2.5) to risk value 1-5."""
    for threshold, risk in _GOVERNANCE_RISK_MAP:
        if governance_score >= threshold:
            return risk
    return 5


def _score_to_risk(total_score: int) -> int:
    """Legal Atlas threshold mapping: score -> risk value 1-5."""
    if total_score > 90:
        return 1
    if total_score > 70:
        return 2
    if total_score > 40:
        return 3
    if total_score > 0:
        return 4
    return 5


def calculate_regulatory_deficiency_score(answers: dict) -> dict:
    """
    Based on WWF WRF v3.0 Regulatory Deficiency Risk framework.
    Source: Wingard et al. (2026), Legal Atlas Methods.

    Each True answer contributes its weight to the total score (max 100).
    Returns:
    - total_score: int 0-100 (higher = better regulation = lower risk)
    - risk_value: int 1-5 following Legal Atlas thresholds
    - normalized: float 0-1
    - failed_criteria: list of strings
    - implementation_adjusted_risk: int (applies World Bank Governance adjustment)
    """
    earned = 0.0
    failed: list[str] = []

    for criterion, weight in _CRITERIA_WEIGHTS.items():
        if answers.get(criterion, False):
            earned += weight
        else:
            failed.append(criterion)

    total_score = int(round(earned))
    risk_value = _score_to_risk(total_score)

    try:
        normalized = earned / 100.0
    except ZeroDivisionError:
        normalized = 0.0

    governance_score: float = answers.get("governance_score", 0.3)
    adjusted = apply_implementation_adjustment(risk_value, governance_score)

    return {
        "total_score": total_score,
        "risk_value": risk_value,
        "normalized": round(normalized, 4),
        "failed_criteria": failed,
        "implementation_adjusted_risk": adjusted,
    }


def apply_implementation_adjustment(regulatory_risk: int, governance_score: float) -> int:
    """
    Applies World Bank Worldwide Governance Indicators as adjusting factor.
    Source: WWF WRF v3.0 Section 14, Wingard et al. (2026).
    governance_score: World Bank governance indicator value (-2.5 to +2.5).

    Per WWF WRF methodology: implementation adjustment can NEVER decrease regulatory risk,
    only increase it. Poor regulation with good implementation has no effect.
    Romania 2024 approximate governance score: 0.3 (Moderate).
    Returns adjusted risk value 1-5.
    """
    governance_risk = _governance_to_risk(governance_score)
    # Risk can only be pushed higher by weak governance, never lower
    return max(regulatory_risk, governance_risk)
