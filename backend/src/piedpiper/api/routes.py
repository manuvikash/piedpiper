"""Core API routes.

These endpoints manage focus group sessions.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["focus-group"])


class CreateSessionRequest(BaseModel):
    task: str
    task_markdown: str | None = None
    budget_usd: float | None = None


class SessionResponse(BaseModel):
    session_id: str
    status: str


@router.post("/sessions", response_model=SessionResponse)
async def create_session(request: CreateSessionRequest):
    """Create and start a new focus group session."""
    from piedpiper.workflow.graph import build_graph
    from piedpiper.models.state import FocusGroupState, Phase
    from piedpiper.config import settings
    import uuid

    session_id = str(uuid.uuid4())
    
    # Use markdown if provided, otherwise fall back to plain task
    full_task = request.task_markdown if request.task_markdown else request.task
    
    # Build initial state
    state = FocusGroupState(
        session_id=session_id,
        task=full_task,
        current_phase=Phase.INIT,
    )
    
    # Set custom budget if provided
    budget = request.budget_usd if request.budget_usd else settings.total_budget_usd
    
    # Compile and run the graph
    graph = build_graph()
    # TODO: Run graph in background task since it's long-running
    # For now, just return the session ID
    
    return SessionResponse(
        session_id=session_id,
        status="initialized"
    )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get the current state of a focus group session."""
    # TODO: retrieve actual session state from database
    # For now, return stub response
    return SessionResponse(
        session_id=session_id,
        status="running"
    )


@router.get("/sessions/{session_id}/costs")
async def get_session_costs(session_id: str):
    """Get cost breakdown for a session."""
    # TODO: return cost tracker data
    raise NotImplementedError


@router.get("/health")
async def health_check():
    return {"status": "ok"}
