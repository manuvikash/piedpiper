"""Expert agent implementation.

Owner: Person 2 (Agents)

The expert agent answers questions from stuck workers using
W&B Inference (DeepSeek R1). It incorporates learned patterns from the
learning module to improve answers over time.
"""

from __future__ import annotations

from openai import AsyncOpenAI

from piedpiper.agents.learning import ExpertLearningModule
from piedpiper.config import settings
from piedpiper.models.queries import ExpertAnswer, ExpertQuery


EXPERT_SYSTEM_PROMPT = """You are an expert developer helping other developers \
who are stuck while using an SDK/API product. Provide clear, actionable answers \
with code examples when appropriate. Be concise but thorough."""


class ExpertAgent:
    """Answers escalated questions with self-improving context."""

    def __init__(self, model: str = "deepseek-ai/DeepSeek-R1-0528"):
        self.model = model
        self.system_prompt = EXPERT_SYSTEM_PROMPT
        self.learning = ExpertLearningModule()
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        """Get or create OpenAI client for W&B Inference."""
        if self._client is None:
            self._client = AsyncOpenAI(
                base_url=settings.wandb_base_url,
                api_key=settings.wandb_api_key,
            )
        return self._client

    async def answer(self, query: ExpertQuery) -> ExpertAnswer:
        """Generate an expert answer for a worker's question.

        1. Load learned context for the query's category
        2. Build prompt with system + learned patterns + question
        3. Call LLM via W&B Inference
        4. Track answer for effectiveness measurement
        """
        # Get learned optimizations
        learned_context = await self.learning.get_context(query.category)

        # Build messages
        messages = [
            {"role": "system", "content": self.system_prompt},
        ]
        
        if learned_context:
            messages.append({
                "role": "system", 
                "content": f"Learned patterns: {learned_context}"
            })
        
        messages.append({
            "role": "user",
            "content": f"Worker question: {query.question}\n\nContext: {query.worker_context}"
        })

        # Call W&B Inference
        client = self._get_client()
        response = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
        )
        
        answer_text = response.choices[0].message.content
        confidence = self._estimate_confidence(answer_text)

        # Track answer for learning
        answer_id = await self.learning.track_answer(
            query=query,
            answer=answer_text,
            initial_confidence=confidence,
        )

        return ExpertAnswer(
            answer_id=answer_id,
            content=answer_text,
            estimated_confidence=confidence,
            model_used=self.model,
        )

    def _estimate_confidence(self, response: str) -> float:
        """Estimate confidence in the answer quality."""
        # TODO: use heuristics or a classifier
        return 0.7
