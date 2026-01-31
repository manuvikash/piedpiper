"""Models for the human review queue."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ReviewStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"


class ReviewItem(BaseModel):
    id: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    question: str
    worker_id: str
    worker_context: str = ""
    arbiter_urgency: float = 0.0
    arbiter_classification: str = ""
    similar_cached: list[dict[str, Any]] = Field(default_factory=list)
    status: ReviewStatus = ReviewStatus.PENDING
    reviewer_id: str | None = None
    reviewed_at: datetime | None = None


class ReviewDecision(BaseModel):
    review_id: str
    decision: ReviewStatus
    reviewer_id: str
    reason: str = ""
    corrected_answer: str | None = None
    correction_reason: str | None = None
