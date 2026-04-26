from __future__ import annotations

from typing import Any, Optional
from fastapi import APIRouter
from pydantic import BaseModel

from models.schemas import ExplanationRequest
from services.ai_explainer import explain_investment_grade

router = APIRouter(prefix="/api/v1/explanation", tags=["explanation"])


class FeasibilityBucket(BaseModel):
    status: str
    reason: str
    evidence_paths: list[str]


class OverallAssessment(BaseModel):
    status: str
    confidence: str
    reason: str
    evidence_paths: list[str]


class TopRisk(BaseModel):
    risk: str
    impact: str
    reason: str
    evidence_paths: list[str]


class SupportedClaim(BaseModel):
    claim: str
    confidence: str
    evidence_paths: list[str]


class UnsupportedClaim(BaseModel):
    claim_attempted: str
    reason: str


class NextCheck(BaseModel):
    check: str
    priority: str
    why: str


class ConsistencyChecks(BaseModel):
    framework_mixing_detected: bool
    numeric_consistency_passed: bool
    threshold_claims_verified: bool
    sentinel_1_used_correctly: bool
    sentinel_2_used_correctly: bool
    satellite_metadata_not_overclaimed: bool


class AuditResponse(BaseModel):
    executive_summary: str
    overall_assessment: OverallAssessment
    water_feasibility: FeasibilityBucket
    cooling_feasibility: FeasibilityBucket
    permit_feasibility: FeasibilityBucket
    infrastructure_feasibility: Optional[FeasibilityBucket] = None  # Finland only
    top_risks: list[TopRisk]
    supported_claims: list[SupportedClaim]
    unsupported_or_removed_claims: list[UnsupportedClaim]
    data_gaps: list[str]
    recommended_next_checks: list[NextCheck]
    consistency_checks: dict[str, bool]  # flexible — Finland adds extra checks
    user_type: str
    location_name: Optional[str] = None


@router.post("/investment", response_model=AuditResponse)
def explain_investment(req: ExplanationRequest) -> AuditResponse:
    audit = explain_investment_grade(
        req.investment_grade_response,
        req.user_type,
        req.location_name,
    )
    return AuditResponse(
        **audit,
        user_type=req.user_type,
        location_name=req.location_name,
    )
