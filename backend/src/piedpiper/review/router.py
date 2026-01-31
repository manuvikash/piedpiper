"""FastAPI routes for human review dashboard.

Owner: Person 3 (Infrastructure)

These endpoints power the Next.js review dashboard.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from piedpiper.models.review import ReviewDecision, ReviewItem
from piedpiper.review.queue import HumanReviewQueue

router = APIRouter(tags=["review"])

# Singleton queue instance (will be injected via dependency in production)
_queue = HumanReviewQueue()


def get_queue() -> HumanReviewQueue:
    return _queue


@router.get("/items", response_model=list[ReviewItem])
async def list_review_items():
    """List all review items."""
    return await get_queue().get_all()


@router.get("/items/pending", response_model=list[ReviewItem])
async def list_pending_items():
    """List pending review items."""
    return await get_queue().get_pending()


@router.get("/items/{review_id}", response_model=ReviewItem)
async def get_review_item(review_id: str):
    """Get a specific review item."""
    item = await get_queue().get_item(review_id)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    return item


@router.post("/items/{review_id}/decide")
async def submit_decision(review_id: str, decision: ReviewDecision):
    """Submit a review decision (approve/reject/modify)."""
    if decision.review_id != review_id:
        raise HTTPException(status_code=400, detail="Review ID mismatch")
    try:
        await get_queue().process_decision(decision)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "ok"}
