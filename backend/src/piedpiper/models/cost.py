"""Budget configuration and cost models."""

from __future__ import annotations

from pydantic import BaseModel


class BudgetConfig(BaseModel):
    total_budget_usd: float = 50.00
    worker_cost_limit: float = 30.00    # 60% for 3 workers
    expert_cost_limit: float = 15.00    # 30% for expert
    browserbase_limit: float = 3.00     # 6% for testing
    buffer: float = 2.00               # 4% buffer


# Cost per 1M tokens (input, output) as of plan writing
MODEL_COSTS: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
}


def calculate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    costs = MODEL_COSTS.get(model, (3.00, 15.00))  # default to sonnet pricing
    return (tokens_in * costs[0] + tokens_out * costs[1]) / 1_000_000
