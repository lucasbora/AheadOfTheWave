"""
Compliance service — wraps the regulatory risk formula and exposes
Romania-specific defaults for fast demo usage.
"""

from config import ROMANIA_DEFAULTS
from services.formulas.regulatory_risk import (
    calculate_regulatory_deficiency_score,
    apply_implementation_adjustment,
)


def run_compliance_check(answers: dict) -> dict:
    """Run full regulatory deficiency scoring and return enriched result."""
    result = calculate_regulatory_deficiency_score(answers)
    governance = answers.get("governance_score", ROMANIA_DEFAULTS["governance_score"])
    result["governance_score"] = governance
    return result


def romania_compliance_defaults() -> dict:
    """
    Pre-filled compliance answers for Romania based on known regulatory status.
    Sources: EU Water Framework Directive transposition, Romanian Water Law (107/1996),
    World Bank Governance Indicators 2024.
    """
    keys = [
        "iwrm_policy_exists",
        "iwrm_in_law",
        "water_authority_exists",
        "water_authority_has_enforcement",
        "clean_water_standards_penalties",
        "wastewater_penalties",
        "wetland_harm_penalties",
        "water_management_plans_required",
        "plans_enforceable",
        "monitoring_water_quality",
        "flood_disaster_framework",
        "governance_score",
    ]
    return {k: ROMANIA_DEFAULTS[k] for k in keys}
