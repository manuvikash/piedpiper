"""Core state models shared across all modules.

These are the canonical data structures. All three work streams import from here.
Changes to these models should be coordinated across the team.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WorkerExpertise(str, enum.Enum):
    BEGINNER = "beginner"
    MID_LEVEL = "mid-level"
    ADVANCED = "advanced"


class WorkerConfig(BaseModel):
    id: str
    model: str
    expertise: WorkerExpertise


DEFAULT_WORKERS = [
    WorkerConfig(id="junior", model="microsoft/Phi-4-mini-instruct", expertise=WorkerExpertise.BEGINNER),
    WorkerConfig(id="intermediate", model="meta-llama/Llama-3.1-8B-Instruct", expertise=WorkerExpertise.MID_LEVEL),
    WorkerConfig(id="senior", model="Qwen/Qwen2.5-14B-Instruct", expertise=WorkerExpertise.ADVANCED),
]


class Phase(str, enum.Enum):
    INIT = "init"
    ASSIGN_TASK = "assign_task"
    WORKER_EXECUTE = "worker_execute"
    CHECK_PROGRESS = "check_progress"
    ARBITER = "arbiter"
    HYBRID_SEARCH = "hybrid_search"
    HUMAN_REVIEW = "human_review"
    EXPERT_ANSWER = "expert_answer"
    BROWSERBASE_TEST = "browserbase_test"
    GENERATE_REPORT = "generate_report"
    EXPERT_LEARN = "expert_learn"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkerAction(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    action_type: str
    description: str
    result: str | None = None
    error: str | None = None


class WorkerState(BaseModel):
    worker_id: str
    config: WorkerConfig
    subtask: str = ""
    conversation_history: list[dict[str, Any]] = Field(default_factory=list)
    action_history: list[WorkerAction] = Field(default_factory=list)
    recent_errors: list[str] = Field(default_factory=list)
    llm_confidence: float = 1.0
    minutes_without_progress: float = 0.0
    sandbox_id: str | None = None
    output: dict[str, Any] | None = None
    completed: bool = False
    stuck: bool = False


class CostEntry(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    agent_type: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float


class CostTracker(BaseModel):
    entries: list[CostEntry] = Field(default_factory=list)
    spent_workers: float = 0.0
    spent_expert: float = 0.0
    spent_browserbase: float = 0.0
    spent_embeddings: float = 0.0
    spent_redis: float = 0.0


class ExpertLearningLog(BaseModel):
    answer_ids: list[str] = Field(default_factory=list)
    effectiveness_scores: list[float] = Field(default_factory=list)
    patterns_learned: int = 0


class SharedMemory(BaseModel):
    shared_patterns: list[dict[str, Any]] = Field(default_factory=list)
    cross_worker_solutions: list[dict[str, Any]] = Field(default_factory=list)


class FocusGroupState(BaseModel):
    """Top-level state for the LangGraph workflow.

    This is the single source of truth passed between graph nodes.
    """

    session_id: str = ""
    task: str = ""
    workers: list[WorkerState] = Field(default_factory=list)
    current_phase: Phase = Phase.INIT
    expert_queries: list[dict[str, Any]] = Field(default_factory=list)
    costs: CostTracker = Field(default_factory=CostTracker)
    shared_memory: SharedMemory = Field(default_factory=SharedMemory)
    expert_learning: ExpertLearningLog = Field(default_factory=ExpertLearningLog)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
