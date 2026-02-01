"""Expert learning module - self-improvement system.

Owner: Person 2 (Agents)

Tracks answer effectiveness, extracts patterns from successes
and failures, and enhances the expert's prompts over time.
"""

from __future__ import annotations

import logging
from uuid import uuid4

from piedpiper.models.queries import ExpertQuery, WorkerOutcome

logger = logging.getLogger(__name__)


class ExpertLearningModule:
    """Tracks and learns from expert answer effectiveness.
    
    Currently uses in-memory storage. Will be backed by Postgres in Phase 4.
    """

    def __init__(self):
        # In-memory storage until Postgres is set up
        self._answers: dict[str, dict] = {}
        self._patterns: dict[str, list[dict]] = {}
        self._corrections: list[dict] = []

    async def track_answer(
        self, query: ExpertQuery, answer: str, initial_confidence: float
    ) -> str:
        """Record an answer for later effectiveness evaluation.

        Returns answer_id.
        """
        answer_id = str(uuid4())
        self._answers[answer_id] = {
            "query_id": query.query_id,
            "question": query.question,
            "category": query.category,
            "answer": answer,
            "confidence": initial_confidence,
            "effectiveness": None,
            "outcome": None,
        }
        logger.debug(f"Tracked answer {answer_id} for query {query.query_id}")
        return answer_id

    async def evaluate_effectiveness(self, answer_id: str, outcome: WorkerOutcome) -> float:
        """Evaluate how effective an answer was based on worker outcome.

        Effectiveness = weighted sum of:
        - success (40%): did worker succeed?
        - speed (20%): time to resolution vs 5 min target
        - independence (20%): no follow-up questions needed
        - confidence_calibration (20%): was confidence estimate accurate?
        """
        if answer_id not in self._answers:
            logger.warning(f"Answer {answer_id} not found for effectiveness evaluation")
            return 0.5
        
        record = self._answers[answer_id]
        
        # Calculate effectiveness components
        success_score = 1.0 if outcome.success else 0.0
        
        # Speed: target is 5 minutes (300 seconds)
        speed_score = max(0, 1 - (outcome.time_to_complete / 600))  # 10 min = 0
        
        # Independence: fewer follow-up questions = better
        independence_score = max(0, 1 - (len(outcome.subsequent_questions) * 0.25))
        
        # Calibration: how close was confidence to actual success
        actual_success = 1.0 if outcome.success else 0.0
        calibration_score = 1 - abs(record["confidence"] - actual_success)
        
        # Weighted sum
        effectiveness = (
            success_score * 0.4 +
            speed_score * 0.2 +
            independence_score * 0.2 +
            calibration_score * 0.2
        )
        
        # Update record
        record["effectiveness"] = effectiveness
        record["outcome"] = outcome.model_dump()
        
        # Update patterns
        await self.update_learned_patterns(record, effectiveness)
        
        logger.info(f"Answer {answer_id} effectiveness: {effectiveness:.2f}")
        return effectiveness

    async def update_learned_patterns(self, answer_record: dict, effectiveness: float):
        """Extract patterns from high/low effectiveness answers."""
        category = answer_record.get("category", "general")
        
        if category not in self._patterns:
            self._patterns[category] = []
        
        if effectiveness > 0.8:
            # Success pattern
            self._patterns[category].append({
                "type": "success",
                "pattern": answer_record["answer"][:500],
                "effectiveness": effectiveness,
            })
            logger.debug(f"Added success pattern for category {category}")
        elif effectiveness < 0.4:
            # Failure pattern
            self._patterns[category].append({
                "type": "failure",
                "pattern": answer_record["answer"][:500],
                "effectiveness": effectiveness,
            })
            logger.debug(f"Added failure pattern for category {category}")

    async def get_context(self, category: str) -> str:
        """Get learned context to enhance expert prompts.

        Returns formatted string with success patterns, common
        pitfalls, and style preferences for the category.
        """
        patterns = self._patterns.get(category, [])
        if not patterns:
            return ""
        
        # Get recent success patterns
        successes = [p for p in patterns if p["type"] == "success"][-3:]
        failures = [p for p in patterns if p["type"] == "failure"][-2:]
        
        context_parts = []
        if successes:
            context_parts.append("Successful approaches for this category:")
            for p in successes:
                context_parts.append(f"- {p['pattern'][:200]}...")
        
        if failures:
            context_parts.append("\nApproaches to avoid:")
            for p in failures:
                context_parts.append(f"- {p['pattern'][:100]}...")
        
        return "\n".join(context_parts)

    async def track_human_correction(
        self,
        question: str,
        original_answer: str | None,
        corrected_answer: str,
        correction_reason: str | None,
    ):
        """Record when a human corrects an expert answer (strong learning signal)."""
        self._corrections.append({
            "question": question,
            "original": original_answer,
            "corrected": corrected_answer,
            "reason": correction_reason,
        })
        logger.info(f"Tracked human correction: {correction_reason or 'no reason given'}")


class ExpertAutoImprovement:
    """Periodic review and prompt optimization."""

    def __init__(self, learning: ExpertLearningModule):
        self.learning = learning

    async def periodic_review(self):
        """Analyze recent answers and suggest prompt improvements.

        Reviews last 50 answers, identifies underperforming categories
        (avg score < 0.6), and proposes prompt updates.
        """
        # TODO: implement periodic review
        raise NotImplementedError

    async def apply_learned_preferences(self, category: str, base_prompt: str) -> str:
        """Enhance a prompt with learned style preferences."""
        # TODO: load preferences, append enhancements
        return base_prompt
