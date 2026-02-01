"""Core API routes.

These endpoints manage focus group sessions.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from piedpiper.api.events import event_bus

router = APIRouter(tags=["focus-group"])

# In-memory session storage (will use Redis in production)
_session_store: dict[str, dict[str, Any]] = {}


class CreateSessionRequest(BaseModel):
    task: str
    task_markdown: str | None = None
    budget_usd: float | None = None


class SessionResponse(BaseModel):
    session_id: str
    status: str
    phase: str | None = None
    workers: list[dict] | None = None


class CostResponse(BaseModel):
    session_id: str
    total_spent_usd: float
    breakdown: dict[str, float]
    entries: list[dict] | None = None


@router.post("/sessions", response_model=SessionResponse)
async def create_session(request: CreateSessionRequest):
    """Create and start a new focus group session."""
    from piedpiper.workflow.graph import build_graph
    from piedpiper.models.state import FocusGroupState, Phase
    from piedpiper.config import settings

    session_id = str(uuid.uuid4())

    full_task = request.task_markdown if request.task_markdown else request.task

    state = FocusGroupState(
        session_id=session_id,
        task=full_task,
        current_phase=Phase.INIT,
    )

    budget = request.budget_usd if request.budget_usd else settings.total_budget_usd

    graph = build_graph()

    _session_store[session_id] = {
        "state": state.model_dump(),
        "status": "running",
        "budget": budget,
    }

    async def run_workflow():
        try:
            await event_bus.emit(session_id, "system", "session_started", {
                "task": full_task[:200],
            })

            final_state = await graph.ainvoke(state)

            if hasattr(final_state, "model_dump"):
                _session_store[session_id]["state"] = final_state.model_dump()
            else:
                _session_store[session_id]["state"] = dict(final_state)
            _session_store[session_id]["status"] = "completed"

            await event_bus.emit(session_id, "system", "session_done", {
                "status": "completed",
            })
        except Exception as e:
            _session_store[session_id]["status"] = f"failed: {str(e)}"

            await event_bus.emit(session_id, "system", "session_done", {
                "status": "failed",
                "error": str(e)[:300],
            })

    asyncio.create_task(run_workflow())

    return SessionResponse(
        session_id=session_id,
        status="running",
        phase=Phase.INIT.value,
    )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get the current state of a focus group session."""
    if session_id not in _session_store:
        raise HTTPException(status_code=404, detail="Session not found")

    session_data = _session_store[session_id]
    state_data = session_data["state"]

    workers_summary = []
    workers_data = state_data.get("workers", []) if isinstance(state_data, dict) else getattr(state_data, "workers", [])
    for worker in workers_data:
        # Handle both dict and Pydantic model
        if isinstance(worker, dict):
            workers_summary.append({
                "worker_id": worker.get("worker_id"),
                "completed": worker.get("completed"),
                "stuck": worker.get("stuck"),
                "actions_count": len(worker.get("action_history", [])),
                "errors_count": len(worker.get("recent_errors", [])),
            })
        else:
            workers_summary.append({
                "worker_id": worker.worker_id,
                "completed": worker.completed,
                "stuck": worker.stuck,
                "actions_count": len(worker.action_history),
                "errors_count": len(worker.recent_errors),
            })

    phase = state_data.get("current_phase") if isinstance(state_data, dict) else getattr(state_data, "current_phase", None)
    if hasattr(phase, "value"):
        phase = phase.value
    
    return SessionResponse(
        session_id=session_id,
        status=session_data["status"],
        phase=phase,
        workers=workers_summary,
    )


@router.get("/sessions/{session_id}/stream")
async def stream_session(session_id: str):
    """SSE endpoint for real-time session events."""
    if session_id not in _session_store:
        raise HTTPException(status_code=404, detail="Session not found")

    return StreamingResponse(
        event_bus.subscribe(session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sessions/{session_id}/costs", response_model=CostResponse)
async def get_session_costs(session_id: str):
    """Get cost breakdown for a session."""
    if session_id not in _session_store:
        raise HTTPException(status_code=404, detail="Session not found")

    session_data = _session_store[session_id]
    state_data = session_data["state"]
    costs_data = state_data.get("costs", {})

    total = (
        costs_data.get("spent_workers", 0.0)
        + costs_data.get("spent_expert", 0.0)
        + costs_data.get("spent_browserbase", 0.0)
        + costs_data.get("spent_embeddings", 0.0)
        + costs_data.get("spent_redis", 0.0)
    )

    return CostResponse(
        session_id=session_id,
        total_spent_usd=total,
        breakdown={
            "workers": costs_data.get("spent_workers", 0.0),
            "expert": costs_data.get("spent_expert", 0.0),
            "browserbase": costs_data.get("spent_browserbase", 0.0),
            "embeddings": costs_data.get("spent_embeddings", 0.0),
            "redis": costs_data.get("spent_redis", 0.0),
        },
        entries=[entry for entry in costs_data.get("entries", [])],
    )


@router.get("/health")
async def health_check():
    return {"status": "ok"}
