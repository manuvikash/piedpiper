"""Arbiter agent implementation.

Owner: Person 2 (Agents)

The arbiter evaluates whether a worker is stuck and classifies
the issue type. It uses multi-signal detection:
- Time without progress
- Error loops
- Low LLM confidence
- Action repetition
- Dead ends
"""

from __future__ import annotations

from piedpiper.models.queries import ExpertQuery, IssueType
from piedpiper.models.state import WorkerState


class ArbiterAgent:
    """Evaluates worker states and decides whether to escalate."""

    def should_escalate(self, worker_state: WorkerState) -> tuple[bool, IssueType, float]:
        """Determine if a worker needs escalation.

        Returns (should_escalate, issue_type, urgency_score).
        """
        signals = {
            "time_stuck": worker_state.minutes_without_progress > 5,
            "error_loop": len(worker_state.recent_errors) > 3,
            "low_confidence": worker_state.llm_confidence < 0.6,
            "repetition": self._detect_repetition(worker_state),
            "dead_end": self._detect_dead_end(worker_state),
        }

        urgency_score = (
            signals["time_stuck"] * 0.3
            + signals["error_loop"] * 0.25
            + signals["low_confidence"] * 0.2
            + signals["repetition"] * 0.15
            + signals["dead_end"] * 0.1
        )

        should_escalate = urgency_score > 0.5 or (
            signals["time_stuck"] and signals["error_loop"]
        ) or signals["dead_end"]

        issue_type = self._classify_issue(signals)
        return should_escalate, issue_type, urgency_score

    def build_query(self, worker_state: WorkerState, issue_type: IssueType, urgency: float) -> ExpertQuery:
        """Build an ExpertQuery from a stuck worker's state."""
        # TODO: summarize worker context into a clear question
        raise NotImplementedError

    def _detect_repetition(self, state: WorkerState) -> bool:
        """Check if worker is repeating the same actions."""
        if len(state.action_history) < 5:
            return False
        recent = state.action_history[-10:]
        signatures = [f"{a.action_type}:{a.description[:50]}" for a in recent]
        return len(set(signatures)) < 3

    def _detect_dead_end(self, state: WorkerState) -> bool:
        """Check if worker has hit a dead end."""
        # TODO: analyze action history for dead-end patterns
        return False

    def _classify_issue(self, signals: dict[str, bool]) -> IssueType:
        """Classify the type of issue based on signals."""
        # TODO: implement classification logic
        if signals.get("error_loop"):
            return IssueType.API_ERROR
        if signals.get("dead_end"):
            return IssueType.CONCEPTUAL_BLOCK
        return IssueType.DOCUMENTATION_GAP
