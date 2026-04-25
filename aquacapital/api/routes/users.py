from fastapi import APIRouter, HTTPException
from models.schemas import UserProfileResponse

router = APIRouter(prefix="/api/v1/users", tags=["users"])

USER_PROFILES: dict[str, dict] = {
    "data_center": {
        "description": "AI/Cloud Data Center Developer",
        "critical_indicators": ["water_availability", "flood_hazard", "ead_index"],
        "regulatory_focus": ["water_use_permits", "environmental_impact"],
        "key_question": "Is there enough water for cooling, and will it flood?",
        "benchmark_threshold": 70,
        "risk_tolerance": "low",
    },
    "industrial_park": {
        "description": "Industrial Real Estate Developer",
        "critical_indicators": ["flood_occurrence", "regulatory_deficiency", "compliance"],
        "regulatory_focus": ["construction_permits", "wastewater_standards", "zoning"],
        "key_question": "Can we build here legally and will operations survive floods?",
        "benchmark_threshold": 60,
        "risk_tolerance": "medium",
    },
    "logistics": {
        "description": "Logistics Hub / Distribution Center Developer",
        "critical_indicators": ["flood_occurrence", "flood_hazard", "transport_access"],
        "regulatory_focus": ["flood_zone_restrictions", "infrastructure_permits"],
        "key_question": "Will roads and access routes flood?",
        "benchmark_threshold": 65,
        "risk_tolerance": "medium",
    },
    "residential_developer": {
        "description": "Residential Real Estate Developer",
        "critical_indicators": ["flood_hazard", "water_quality", "regulatory_deficiency"],
        "regulatory_focus": ["building_permits", "water_access_rights", "wetland_restrictions"],
        "key_question": "Is this safe and habitable long-term?",
        "benchmark_threshold": 65,
        "risk_tolerance": "medium-low",
    },
    "generic_investor": {
        "description": "Financial Investor / Fund Manager",
        "critical_indicators": ["ead_index", "investment_grade", "regulatory_risk"],
        "regulatory_focus": ["all"],
        "key_question": "What is the risk-adjusted return profile?",
        "benchmark_threshold": 55,
        "risk_tolerance": "medium",
    },
}


@router.get("/profiles", response_model=dict[str, UserProfileResponse])
def get_all_profiles() -> dict:
    return {k: {**v, "user_type": k} for k, v in USER_PROFILES.items()}


@router.get("/profiles/{user_type}", response_model=UserProfileResponse)
def get_profile(user_type: str) -> dict:
    if user_type not in USER_PROFILES:
        raise HTTPException(
            status_code=404,
            detail=f"User type '{user_type}' not found. Valid types: {list(USER_PROFILES.keys())}",
        )
    return {**USER_PROFILES[user_type], "user_type": user_type}
