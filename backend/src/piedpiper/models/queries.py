"""Models for expert queries, answers, and worker outcomes."""

from __future__ import annotations

import enum
from datetime import datetime

from pydantic import BaseModel, Field


class IssueType(str, enum.Enum):
    DOCUMENTATION_GAP = "documentation_gap"
    API_ERROR = "api_error"
    CONCEPTUAL_BLOCK = "conceptual_block"
    BUG_SUSPECTED = "bug_suspected"
    CLARIFICATION_NEEDED = "clarification_needed"


class ExpertQuery(BaseModel):
    query_id: str = ""
    question: str
    worker_id: str
    worker_context: str = ""
    category: str = ""
    issue_type: IssueType = IssueType.DOCUMENTATION_GAP
    urgency_score: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ExpertAnswer(BaseModel):
    answer_id: str = ""
    query_id: str = ""
    content: str
    estimated_confidence: float = 0.0
    model_used: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WorkerOutcome(BaseModel):
    worker_id: str
    answer_id: str
    success: bool
    time_to_complete: float = 0.0  # seconds
    subsequent_questions: list[str] = Field(default_factory=list)
    worker_feedback: str = ""
