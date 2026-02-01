"""Budget configuration and cost models.

All LLM calls go through W&B Inference. Embeddings use local
sentence-transformers (zero API cost).
"""

from __future__ import annotations

from pydantic import BaseModel


class BudgetConfig(BaseModel):
    total_budget_usd: float = 50.00
    worker_cost_limit: float = 30.00    # 60% for 3 workers
    expert_cost_limit: float = 15.00    # 30% for expert
    browserbase_limit: float = 3.00     # 6% for testing
    buffer: float = 2.00               # 4% buffer


# W&B Inference model costs per 1M tokens (input, output)
# Pricing from https://wandb.ai/site/pricing/inference
# Using conservative estimates where exact pricing is unavailable
MODEL_COSTS: dict[str, tuple[float, float]] = {
    # Workers
    "microsoft/Phi-4-mini-instruct": (0.10, 0.10),           # 3.8B, cheapest
    "meta-llama/Llama-3.1-8B-Instruct": (0.20, 0.20),       # 8B
    "meta-llama/Llama-3.3-70B-Instruct": (0.80, 0.80),      # 70B
    "Qwen/Qwen2.5-14B-Instruct": (0.30, 0.30),              # 14.7B
    "OpenPipe/Qwen3-14B-Instruct": (0.30, 0.30),            # 14.8B
    # Expert models (larger, more capable)
    "deepseek-ai/DeepSeek-R1-0528": (1.00, 1.00),           # 37B-680B MoE reasoning
    "deepseek-ai/DeepSeek-V3-0324": (0.80, 0.80),           # 37B-680B MoE
    "deepseek-ai/DeepSeek-V3.1": (0.80, 0.80),              # 37B-671B
    "Qwen/Qwen3-235B-A22B-Thinking-2507": (1.20, 1.20),    # 22B-235B MoE reasoning
    "Qwen/Qwen3-235B-A22B-Instruct-2507": (1.00, 1.00),    # 22B-235B MoE
    "Qwen/Qwen3-Coder-480B-A35B-Instruct": (1.50, 1.50),   # 35B-480B coding
    "moonshotai/Kimi-K2-Instruct": (0.60, 0.60),            # 32B-1T MoE
    "moonshotai/Kimi-K2-Instruct-0905": (0.60, 0.60),       # 32B-1T MoE
    "openai/gpt-oss-20b": (0.30, 0.30),                     # 3.6B-20B MoE
    "openai/gpt-oss-120b": (1.00, 1.00),                    # 5.1B-117B MoE
    "Qwen/Qwen3-30B-A3B-Instruct-2507": (0.30, 0.30),      # 3.3B-30.5B MoE
    "zai-org/GLM-4.5": (0.80, 0.80),                        # 32B-355B MoE
    "meta-llama/Llama-4-Scout-17B-16E-Instruct": (0.40, 0.40),  # 17B-109B multimodal
}


def calculate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Calculate cost for a W&B Inference LLM call."""
    costs = MODEL_COSTS.get(model, (1.00, 1.00))  # default to $1/1M
    return (tokens_in * costs[0] + tokens_out * costs[1]) / 1_000_000
