"""Three-tier memory system.

Owner: Person 3 (Infrastructure)

- Short-term: in-memory dict (current session)
- Medium-term: Redis with TTL (24h session persistence)
- Long-term: PostgreSQL (permanent storage)
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class MemorySystem:
    """Manages the three-tier memory architecture."""

    def __init__(self, redis_client: Any, pg_pool: Any, embedding_service: Any):
        self.short_term: dict[str, Any] = {}
        self.medium_term = RedisMediumTermStore(redis_client, embedding_service)
        self.long_term = PostgresLongTermStore(pg_pool)


class RedisMediumTermStore:
    """Redis-backed medium-term storage with 24h TTL."""

    TTL_SECONDS = 86400  # 24 hours
    KEY_PREFIX = "memory:"

    def __init__(self, redis_client: Any, embedding_service: Any):
        self.redis = redis_client
        self.embedding_service = embedding_service

    async def store(self, data: dict[str, Any]) -> str:
        """Store data with automatic TTL.
        
        Args:
            data: Dictionary containing the data to store. Should include
                  a 'problem' or similar text field for semantic search.
        
        Returns:
            The ID of the stored item
        """
        # Generate unique ID
        item_id = f"mem_{uuid.uuid4().hex[:12]}"
        key = f"{self.KEY_PREFIX}{item_id}"
        
        # Add metadata
        data["id"] = item_id
        data["timestamp"] = data.get("timestamp", datetime.utcnow().isoformat())
        
        # Generate embedding for semantic search
        # Use 'problem' field if available, otherwise use first text field found
        text_for_embedding = data.get("problem") or data.get("solution") or str(data)
        if text_for_embedding:
            try:
                embedding = await self.embedding_service.embed(text_for_embedding)
                data["embedding"] = embedding.tolist()
            except Exception as e:
                logger.warning(f"Failed to generate embedding for memory: {e}")
                data["embedding"] = None
        
        # Store in Redis with TTL
        data_json = json.dumps(data)
        await self.redis.setex(key, self.TTL_SECONDS, data_json)
        
        logger.debug(f"Stored memory item {item_id} with {self.TTL_SECONDS}s TTL")
        return item_id

    async def search(
        self, query: str, filters: dict | None = None, sort_by: str | None = None
    ) -> list[dict]:
        """Semantic search over medium-term memory.
        
        Args:
            query: Text query to search for
            filters: Optional filters (e.g., {"worker_id": "junior", "outcome": "success"})
            sort_by: Optional field to sort by (e.g., "usage_count")
        
        Returns:
            List of matching memory items
        """
        start_time = time.time()
        
        # Get all memory keys
        pattern = f"{self.KEY_PREFIX}*"
        cursor = 0
        all_items = []
        
        # Scan through all keys (SCAN is non-blocking)
        while True:
            cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)
            if keys:
                # Fetch all items in batch
                values = await self.redis.mget(keys)
                for value in values:
                    if value:
                        try:
                            item = json.loads(value)
                            all_items.append(item)
                        except Exception as e:
                            logger.warning(f"Failed to parse memory item: {e}")
            
            if cursor == 0:
                break
        
        # Apply filters
        if filters:
            filtered_items = []
            for item in all_items:
                matches = True
                for key, value in filters.items():
                    if item.get(key) != value:
                        matches = False
                        break
                if matches:
                    filtered_items.append(item)
            all_items = filtered_items
        
        # Generate query embedding and compute similarity scores
        if all_items and query:
            try:
                query_embedding = await self.embedding_service.embed(query)
                
                # Compute cosine similarity for each item
                for item in all_items:
                    if item.get("embedding"):
                        import numpy as np
                        item_embedding = np.array(item["embedding"])
                        # Cosine similarity
                        similarity = np.dot(query_embedding, item_embedding) / (
                            np.linalg.norm(query_embedding) * np.linalg.norm(item_embedding)
                        )
                        item["similarity_score"] = float(similarity)
                    else:
                        item["similarity_score"] = 0.0
                
                # Sort by similarity score (highest first)
                all_items.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)
            except Exception as e:
                logger.warning(f"Failed to compute similarity scores: {e}")
        
        # Apply custom sorting if requested
        if sort_by and sort_by != "similarity_score":
            try:
                all_items.sort(
                    key=lambda x: x.get(sort_by, 0),
                    reverse=True  # Assume higher is better
                )
            except Exception as e:
                logger.warning(f"Failed to sort by {sort_by}: {e}")
        
        elapsed = time.time() - start_time
        logger.debug(
            f"Memory search returned {len(all_items)} items in {elapsed:.3f}s "
            f"(filters: {filters}, sort_by: {sort_by})"
        )
        
        return all_items


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
