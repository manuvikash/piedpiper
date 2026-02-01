"""Redis integration package.

This package contains all Redis-related functionality:
- Embedding generation and caching
- Hybrid knowledge base (vector + keyword search)
- Medium-term memory storage
"""

from piedpiper.infra.redis.embeddings import EmbeddingService
from piedpiper.infra.redis.memory import (
    MemorySystem,
    PostgresLongTermStore,
    RedisMediumTermStore,
    SharedPlaybook,
    WorkerMemory,
)
from piedpiper.infra.redis.search import HybridKnowledgeBase

__all__ = [
    "EmbeddingService",
    "HybridKnowledgeBase",
    "MemorySystem",
    "RedisMediumTermStore",
    "PostgresLongTermStore",
    "WorkerMemory",
    "SharedPlaybook",
]
