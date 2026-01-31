"""Core API routes.

These endpoints manage focus group sessions.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["focus-group"])


class CreateSessionRequest(BaseModel):
    task: str
    budget_usd: float | None = None


class SessionResponse(BaseModel):
    session_id: str
    status: str


@router.post("/sessions", response_model=SessionResponse)
async def create_session(request: CreateSessionRequest):
    """Create and start a new focus group session."""
    # TODO: build FocusGroupState, invoke graph
    raise NotImplementedError


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get the current state of a focus group session."""
    # TODO: retrieve session state
    raise NotImplementedError


@router.get("/sessions/{session_id}/costs")
async def get_session_costs(session_id: str):
    """Get cost breakdown for a session."""
    # TODO: return cost tracker data
    raise NotImplementedError


@router.get("/health")
async def health_check():
    return {"status": "ok"}
