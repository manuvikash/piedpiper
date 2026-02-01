"""Cost tracking and budget enforcement.

Owner: Person 3 (Infrastructure)

Tracks all LLM calls, embedding costs, and external service usage.
Enforces budget limits and suggests cost-saving strategies.
"""

from __future__ import annotations

import asyncio

from piedpiper.models.cost import BudgetConfig, calculate_cost
from piedpiper.models.state import CostEntry, CostTracker


class CostController:
    """Real-time cost tracking with budget enforcement."""

    def __init__(self, budget: BudgetConfig | None = None):
        self.budget = budget or BudgetConfig()
        self.tracker = CostTracker()
        self._lock = asyncio.Lock()

    async def track_llm_call(
        self, agent_type: str, model: str, tokens_in: int, tokens_out: int
    ) -> float:
        """Track cost of an LLM API call. Returns the cost in USD."""
        cost = calculate_cost(model, tokens_in, tokens_out)
        entry = CostEntry(
            agent_type=agent_type, model=model,
            tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost,
        )

        async with self._lock:
            self.tracker.entries.append(entry)
            if agent_type == "workers":
                self.tracker.spent_workers += cost
            elif agent_type == "expert":
                self.tracker.spent_expert += cost
            elif agent_type == "browserbase":
                self.tracker.spent_browserbase += cost
            elif agent_type == "embeddings":
                self.tracker.spent_embeddings += cost

        return cost

    async def check_budget(self) -> tuple[bool, str, float]:
        """Check if we can continue spending.

        Returns (can_continue, message, remaining_usd).
        """
        total_spent = (
            self.tracker.spent_workers
            + self.tracker.spent_expert
            + self.tracker.spent_browserbase
            + self.tracker.spent_embeddings
            + self.tracker.spent_redis
        )
        remaining = self.budget.total_budget_usd - total_spent

        if total_spent > self.budget.total_budget_usd:
            return False, "Total budget exceeded", 0.0

        if self.tracker.spent_expert > self.budget.expert_cost_limit:
            return False, "Expert budget depleted", remaining

        if self.tracker.spent_workers > self.budget.worker_cost_limit:
            return True, "WARNING: Worker budget nearly depleted", remaining

        if remaining < self.budget.buffer:
            return True, "WARNING: Approaching budget limit", remaining

        return True, "OK", remaining

    def get_cost_saving_recommendation(self) -> str:
        """Suggest cost-saving measures based on current spend."""
        if self.tracker.spent_expert > self.budget.expert_cost_limit * 0.8:
            return "Switch workers to cheaper models (microsoft/Phi-4-mini-instruct)"
        if self.tracker.spent_workers > self.budget.worker_cost_limit * 0.7:
            return "Reduce arbiter sensitivity to decrease escalations"
        return "No action needed"
