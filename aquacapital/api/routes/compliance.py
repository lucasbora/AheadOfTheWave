from fastapi import APIRouter
from models.schemas import ComplianceRequest, ComplianceResponse
from services.compliance import run_compliance_check, romania_compliance_defaults

router = APIRouter(prefix="/api/v1/compliance", tags=["compliance"])


@router.post("/check", response_model=ComplianceResponse)
def compliance_check(req: ComplianceRequest) -> ComplianceResponse:
    answers = req.model_dump(exclude={"lat", "lon"})
    result = run_compliance_check(answers)
    return ComplianceResponse(
        total_score=result["total_score"],
        risk_value=result["risk_value"],
        normalized=result["normalized"],
        failed_criteria=result["failed_criteria"],
        implementation_adjusted_risk=result["implementation_adjusted_risk"],
        governance_score=result["governance_score"],
    )


@router.post("/romania-defaults", response_model=ComplianceResponse)
def romania_defaults() -> ComplianceResponse:
    """
    Returns pre-filled compliance answers and scores for Romania.
    Based on EU Water Framework Directive transposition, Romanian Water Law (107/1996),
    and World Bank Governance Indicators 2024.
    """
    defaults = romania_compliance_defaults()
    result = run_compliance_check(defaults)
    return ComplianceResponse(
        total_score=result["total_score"],
        risk_value=result["risk_value"],
        normalized=result["normalized"],
        failed_criteria=result["failed_criteria"],
        implementation_adjusted_risk=result["implementation_adjusted_risk"],
        governance_score=result["governance_score"],
    )
