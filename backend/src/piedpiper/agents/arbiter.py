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

from uuid import uuid4

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
        # Extract recent context
        recent_actions = worker_state.action_history[-5:] if worker_state.action_history else []
        recent_errors = worker_state.recent_errors[-3:] if worker_state.recent_errors else []
        
        # Build context string
        context_parts = []
        context_parts.append(f"Task: {worker_state.subtask}")
        
        if recent_actions:
            actions_str = "; ".join([f"{a.action_type}: {a.description[:100]}" for a in recent_actions])
            context_parts.append(f"Recent actions: {actions_str}")
        
        if recent_errors:
            errors_str = "; ".join([e[:150] for e in recent_errors])
            context_parts.append(f"Errors encountered: {errors_str}")
        
        context_parts.append(f"Time stuck: {worker_state.minutes_without_progress:.1f} minutes")
        context_parts.append(f"LLM confidence: {worker_state.llm_confidence:.2f}")
        
        worker_context = "\n".join(context_parts)
        
        # Build question based on issue type
        question = self._build_question(worker_state, issue_type, recent_errors)
        
        # Determine category from subtask
        category = self._extract_category(worker_state.subtask)
        
        return ExpertQuery(
            query_id=str(uuid4()),
            question=question,
            worker_id=worker_state.worker_id,
            worker_context=worker_context,
            category=category,
            issue_type=issue_type,
            urgency_score=urgency,
        )
    
    def _build_question(self, state: WorkerState, issue_type: IssueType, errors: list[str]) -> str:
        """Build a clear question based on issue type and context."""
        task_summary = state.subtask[:200] if state.subtask else "unknown task"
        
        if issue_type == IssueType.API_ERROR:
            error_summary = errors[-1][:200] if errors else "unknown error"
            return f"I'm getting an error while working on: {task_summary}. The error is: {error_summary}. How can I fix this?"
        
        elif issue_type == IssueType.CONCEPTUAL_BLOCK:
            return f"I'm stuck on: {task_summary}. I've tried multiple approaches but can't make progress. What's the right way to approach this?"
        
        elif issue_type == IssueType.DOCUMENTATION_GAP:
            return f"I'm working on: {task_summary}. I can't find documentation on how to proceed. Can you explain how to do this?"
        
        elif issue_type == IssueType.BUG_SUSPECTED:
            return f"While working on: {task_summary}, I suspect there might be a bug in the SDK/API. The behavior I'm seeing doesn't match expectations. Can you help diagnose?"
        
        else:  # CLARIFICATION_NEEDED
            return f"I need clarification on: {task_summary}. What exactly should I be doing here?"
    
    def _extract_category(self, subtask: str) -> str:
        """Extract a category from the subtask for learning purposes."""
        subtask_lower = subtask.lower()
        if "api" in subtask_lower or "endpoint" in subtask_lower:
            return "api_usage"
        elif "auth" in subtask_lower or "login" in subtask_lower:
            return "authentication"
        elif "database" in subtask_lower or "sql" in subtask_lower:
            return "database"
        elif "test" in subtask_lower:
            return "testing"
        elif "deploy" in subtask_lower:
            return "deployment"
        return "general"

    def _detect_repetition(self, state: WorkerState) -> bool:
        """Check if worker is repeating the same actions."""
        if len(state.action_history) < 5:
            return False
        recent = state.action_history[-10:]
        signatures = [f"{a.action_type}:{a.description[:50]}" for a in recent]
        return len(set(signatures)) < 3

    def _detect_dead_end(self, state: WorkerState) -> bool:
        """Check if worker has hit a dead end."""
        if len(state.action_history) < 3:
            return False
        
        recent = state.action_history[-10:]
        
        # Check for repeated failed attempts
        failed_count = sum(1 for a in recent if a.error is not None)
        if failed_count >= 5:
            return True
        
        # Check for no new actions (all same type)
        action_types = [a.action_type for a in recent]
        if len(set(action_types)) == 1 and len(action_types) >= 5:
            return True
        
        # Check for alternating between same two actions (ping-pong)
        if len(recent) >= 6:
            signatures = [f"{a.action_type}:{a.description[:30]}" for a in recent[-6:]]
            if len(set(signatures)) <= 2:
                return True
        
        return False

    def _classify_issue(self, signals: dict[str, bool]) -> IssueType:
        """Classify the type of issue based on signals."""
        # Priority-based classification
        if signals.get("error_loop") and signals.get("repetition"):
            return IssueType.BUG_SUSPECTED
        
        if signals.get("error_loop"):
            return IssueType.API_ERROR
        
        if signals.get("dead_end"):
            return IssueType.CONCEPTUAL_BLOCK
        
        if signals.get("low_confidence") and signals.get("time_stuck"):
            return IssueType.CLARIFICATION_NEEDED
        
        if signals.get("time_stuck"):
            return IssueType.DOCUMENTATION_GAP
        
        return IssueType.DOCUMENTATION_GAP
