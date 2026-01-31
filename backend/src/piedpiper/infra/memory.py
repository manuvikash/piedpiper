"""Three-tier memory system.

Owner: Person 3 (Infrastructure)

- Short-term: in-memory dict (current session)
- Medium-term: Redis with TTL (24h session persistence)
- Long-term: PostgreSQL (permanent storage)
"""

from __future__ import annotations

from typing import Any


class MemorySystem:
    """Manages the three-tier memory architecture."""

    def __init__(self, redis_client: Any, pg_pool: Any):
        self.short_term: dict[str, Any] = {}
        self.medium_term = RedisMediumTermStore(redis_client)
        self.long_term = PostgresLongTermStore(pg_pool)


class RedisMediumTermStore:
    """Redis-backed medium-term storage with 24h TTL."""

    TTL_SECONDS = 86400  # 24 hours

    def __init__(self, redis_client: Any):
        self.redis = redis_client

    async def store(self, data: dict[str, Any]):
        """Store data with automatic TTL."""
        # TODO: serialize and store in Redis with TTL
        raise NotImplementedError

    async def search(self, query: str, filters: dict | None = None, sort_by: str | None = None) -> list[dict]:
        """Semantic search over medium-term memory."""
        # TODO: embed query, search Redis
        raise NotImplementedError


class PostgresLongTermStore:
    """PostgreSQL-backed permanent storage."""

    def __init__(self, pg_pool: Any):
        self.pool = pg_pool

    async def store(self, data: dict[str, Any]):
        """Store data permanently."""
        # TODO: insert into Postgres
        raise NotImplementedError

    async def query(self, filters: dict[str, Any]) -> list[dict]:
        """Query long-term storage."""
        # TODO: query Postgres
        raise NotImplementedError


class WorkerMemory:
    """Per-worker memory interface."""

    def __init__(self, worker_id: str, memory: MemorySystem):
        self.worker_id = worker_id
        self.memory = memory

    async def recall_similar_tasks(self, task: str) -> list[dict]:
        """Find similar successful tasks from this worker's history."""
        return await self.memory.medium_term.search(
            query=task, filters={"worker_id": self.worker_id, "outcome": "success"}
        )

    async def remember_solution(self, problem: str, solution: str, success: bool):
        """Store solution for future recall."""
        await self.memory.medium_term.store({
            "worker_id": self.worker_id,
            "problem": problem,
            "solution": solution,
            "outcome": "success" if success else "failure",
        })


class SharedPlaybook:
    """Cross-worker collaborative memory."""

    def __init__(self, memory: MemorySystem):
        self.memory = memory

    async def contribute_solution(self, worker_id: str, pattern: dict):
        """Worker shares a successful pattern with others."""
        await self.memory.medium_term.store({
            "type": "shared_pattern",
            "contributed_by": worker_id,
            "pattern": pattern,
            "usage_count": 0,
        })

    async def get_relevant_patterns(self, task: str) -> list[dict]:
        """Get patterns that might help with the current task."""
        return await self.memory.medium_term.search(
            query=task, filters={"type": "shared_pattern"}, sort_by="usage_count"
        )
