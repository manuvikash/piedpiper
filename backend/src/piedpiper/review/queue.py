"""Human review queue.

Owner: Person 3 (Infrastructure)

Manages the queue of questions awaiting human review.
Integrates with the Next.js dashboard via FastAPI endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from piedpiper.models.queries import ExpertQuery
from piedpiper.models.review import ReviewDecision, ReviewItem, ReviewStatus


class HumanReviewQueue:
    """In-memory review queue (will be backed by Postgres in production)."""

    def __init__(self):
        self._queue: dict[str, ReviewItem] = {}
        self._pending_futures: dict[str, object] = {}  # for async wait

    async def submit(self, query: ExpertQuery, arbiter_context: dict) -> str:
        """Submit a question for human review. Returns review_id."""
        review_id = str(uuid.uuid4())
        item = ReviewItem(
            id=review_id,
            timestamp=datetime.utcnow(),
            question=query.question,
            worker_id=query.worker_id,
            worker_context=query.worker_context,
            arbiter_urgency=arbiter_context.get("urgency_score", 0.0),
            arbiter_classification=arbiter_context.get("issue_type", ""),
            status=ReviewStatus.PENDING,
        )
        self._queue[review_id] = item
        return review_id

    async def get_pending(self) -> list[ReviewItem]:
        """Get all pending review items."""
        return [
            item for item in self._queue.values()
            if item.status == ReviewStatus.PENDING
        ]

    async def get_item(self, review_id: str) -> ReviewItem | None:
        """Get a specific review item."""
        return self._queue.get(review_id)

    async def get_all(self) -> list[ReviewItem]:
        """Get all review items."""
        return list(self._queue.values())

    async def process_decision(self, decision: ReviewDecision):
        """Process a human reviewer's decision."""
        item = self._queue.get(decision.review_id)
        if not item:
            raise ValueError(f"Review item {decision.review_id} not found")

        item.status = decision.decision
        item.reviewer_id = decision.reviewer_id
        item.reviewed_at = datetime.utcnow()

        # TODO: trigger downstream actions based on decision
        # - approved → expert_answer
        # - rejected → notify worker
        # - modified → store corrected answer + notify worker
