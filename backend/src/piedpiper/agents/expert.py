"""Expert agent implementation.

Owner: Person 2 (Agents)

The expert agent answers questions from stuck workers using
Claude 3.5 Sonnet. It incorporates learned patterns from the
learning module to improve answers over time.
"""

from __future__ import annotations

from piedpiper.agents.learning import ExpertLearningModule
from piedpiper.models.queries import ExpertAnswer, ExpertQuery


EXPERT_SYSTEM_PROMPT = """You are an expert developer helping other developers \
who are stuck while using an SDK/API product. Provide clear, actionable answers \
with code examples when appropriate. Be concise but thorough."""


class ExpertAgent:
    """Answers escalated questions with self-improving context."""

    def __init__(self, model: str = "claude-3-5-sonnet-20241022"):
        self.model = model
        self.system_prompt = EXPERT_SYSTEM_PROMPT
        self.learning = ExpertLearningModule()

    async def answer(self, query: ExpertQuery) -> ExpertAnswer:
        """Generate an expert answer for a worker's question.

        1. Load learned context for the query's category
        2. Build prompt with system + learned patterns + question
        3. Call LLM
        4. Track answer for effectiveness measurement
        """
        # Get learned optimizations
        learned_context = await self.learning.get_context(query.category)

        # TODO: build messages with system_prompt + learned_context + query
        # TODO: call LLM
        # TODO: estimate confidence
        # TODO: track answer via learning module
        raise NotImplementedError

    def _estimate_confidence(self, response: str) -> float:
        """Estimate confidence in the answer quality."""
        # TODO: use heuristics or a classifier
        return 0.7
