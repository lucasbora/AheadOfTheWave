"""
AI explanation layer — translates deterministic risk scores into investment guidance.
Uses Claude claude-opus-4-5. AI does not calculate; it only explains.
"""

import anthropic
from fastapi import HTTPException

from config import settings

_SYSTEM_PROMPT = (
    "You are AquaCapital's investment intelligence engine. "
    "You translate water risk scores into actionable investment guidance for real estate developers. "
    "You always cite that data comes from ESA Copernicus validated satellites and peer-reviewed "
    "methodologies (WWF Water Risk Filter v3.0, WRI Aqueduct Floods). "
    "You never make legal guarantees. "
    "Be direct, professional, and specific. "
    "Focus on what the investor needs to do next."
)

_USER_PROMPT_TEMPLATE = """
Location: {location_name}
User type: {user_type}
Investment grade: {grade} ({grade_label})
Score: {score}/100

Risk breakdown:
- Physical risk composite (0=low, 1=high): {physical_risk_composite}
- Regulatory risk composite (0=low, 1=high): {regulatory_risk_composite}
- Compliance score (0=low, 1=high): {compliance_score}
- Expected Annual Damage index (0=low, 1=high): {ead_index}

Score contributions:
{breakdown}

Satellite metadata: {satellite_metadata}

Provide:
1. One-paragraph executive summary of the water risk profile and investment suitability.
2. Top 3 specific risk factors driving this score.
3. Three concrete mitigation recommendations tailored to this user type.
4. How this score compares to typical investment thresholds for {user_type} (benchmark: {benchmark_threshold}/100).
"""

_USER_BENCHMARKS: dict[str, int] = {
    "data_center": 70,
    "industrial_park": 60,
    "logistics": 65,
    "residential_developer": 65,
    "generic_investor": 55,
}


def explain_investment_grade(grade_response: dict, user_type: str, location_name: str | None = None) -> str:
    """
    Call Claude claude-opus-4-5 to generate a natural-language explanation of the investment grade.
    Returns the explanation as a string.
    Raises HTTPException 502 if the API call fails.
    """
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY is not configured. Set it in your .env file.",
        )

    benchmark = _USER_BENCHMARKS.get(user_type, 55)

    breakdown_lines = "\n".join(
        f"  - {k}: {v}" for k, v in grade_response.get("breakdown", {}).items()
    )

    satellite_note = (
        grade_response.get("satellite_metadata", {}).get("note")
        or grade_response.get("satellite_metadata", {}).get("acquisition_date")
        or "not available"
    )

    user_prompt = _USER_PROMPT_TEMPLATE.format(
        location_name=location_name or "Unknown location",
        user_type=user_type,
        grade=grade_response.get("grade", "N/A"),
        grade_label=grade_response.get("grade_label", "N/A"),
        score=grade_response.get("score", 0),
        physical_risk_composite=grade_response.get("physical_risk_composite", "N/A"),
        regulatory_risk_composite=grade_response.get("regulatory_risk_composite", "N/A"),
        compliance_score=grade_response.get("compliance_score", "N/A"),
        ead_index=grade_response.get("ead_index", "N/A"),
        breakdown=breakdown_lines,
        satellite_metadata=satellite_note,
        benchmark_threshold=benchmark,
    )

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return message.content[0].text
    except anthropic.APIError as exc:
        raise HTTPException(status_code=502, detail=f"Claude API error: {exc}") from exc
