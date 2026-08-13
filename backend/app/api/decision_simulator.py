# backend/app/api/decision_simulator.py
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from ..security import get_current_user
from ..services.decision_simulator import DecisionSimulator, DecisionSimulatorError

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/decision-simulate", tags=["decision-simulator"])


class DecisionSimulateBody(BaseModel):
    question: str
    options: list[str]


@router.post("", status_code=status.HTTP_200_OK)
async def simulate(
    body: DecisionSimulateBody,
    request: Request,
    user=Depends(get_current_user),
):
    if len(body.options) < 2:
        raise HTTPException(status_code=400, detail="At least 2 options required")

    coordinator = getattr(request.app.state, "coordinator", None)
    gemini = getattr(coordinator, "gemini", None) if coordinator else None
    if gemini is None:
        raise HTTPException(status_code=503, detail="Gemini client not configured")

    try:
        return await DecisionSimulator(gemini=gemini).simulate(body.question, body.options)
    except DecisionSimulatorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
