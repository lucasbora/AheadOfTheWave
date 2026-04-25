from fastapi import APIRouter
from models.schemas import ExplanationRequest
from services.ai_explainer import explain_investment_grade
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/explanation", tags=["explanation"])


class ExplanationResponse(BaseModel):
    explanation: str
    user_type: str
    location_name: str | None = None


@router.post("/investment", response_model=ExplanationResponse)
def explain_investment(req: ExplanationRequest) -> ExplanationResponse:
    text = explain_investment_grade(
        req.investment_grade_response,
        req.user_type,
        req.location_name,
    )
    return ExplanationResponse(
        explanation=text,
        user_type=req.user_type,
        location_name=req.location_name,
    )
