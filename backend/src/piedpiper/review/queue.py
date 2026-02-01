"""Human review queue.

Owner: Person 3 (Infrastructure)

Manages the queue of questions awaiting human review.
Integrates with the Next.js dashboard via FastAPI endpoints.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime

from piedpiper.models.queries import ExpertQuery
from piedpiper.models.review import ReviewDecision, ReviewItem, ReviewStatus

logger = logging.getLogger(__name__)


class HumanReviewQueue:
    """In-memory review queue (will be backed by Postgres in production)."""

    def __init__(self):
        self._queue: dict[str, ReviewItem] = {}
        self._events: dict[str, asyncio.Event] = {}
        self._decisions: dict[str, ReviewDecision] = {}

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
        self._events[review_id] = asyncio.Event()
        logger.info(f"Submitted review {review_id} for question: {query.question[:100]}...")
        return review_id
    
    async def wait_for_decision(self, review_id: str, timeout: float = 300.0) -> ReviewDecision | None:
        """Wait for a human decision on a review item.
        
        Args:
            review_id: The review ID to wait for
            timeout: Maximum seconds to wait (default 5 minutes)
        
        Returns:
            ReviewDecision if decision made, None if timeout
        """
        event = self._events.get(review_id)
        if not event:
            logger.warning(f"No event found for review {review_id}")
            return None
        
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return self._decisions.get(review_id)
        except asyncio.TimeoutError:
            logger.warning(f"Review {review_id} timed out after {timeout}s")
            return None

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
        if decision.corrected_answer:
            item.corrected_answer = decision.corrected_answer

        # Store decision and trigger event for async waiters
        self._decisions[decision.review_id] = decision
        event = self._events.get(decision.review_id)
        if event:
            event.set()
            logger.info(f"Review {decision.review_id} decision: {decision.decision.value}")
