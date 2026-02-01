"""Embedding generation service.

Owner: Person 3 (Infrastructure)

Handles text embedding generation using OpenAI's API.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import numpy as np
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Manages text embeddings with caching."""

    EMBEDDING_MODEL = "text-embedding-3-small"  # 1536 dimensions, cost-effective
    EMBEDDING_DIMENSIONS = 1536

    def __init__(self, openai_api_key: str, redis_client: Any | None = None):
        self.client = AsyncOpenAI(api_key=openai_api_key)
        self.redis = redis_client
        self._cache_prefix = "embedding:"

    async def embed(self, text: str) -> np.ndarray:
        """Generate embedding for text with Redis caching.

        Args:
            text: Text to embed

        Returns:
            numpy array of shape (1536,)
        """
        if not text or not text.strip():
            raise ValueError("Cannot embed empty text")

        # Check cache first
        if self.redis:
            cache_key = self._get_cache_key(text)
            cached = await self._get_cached_embedding(cache_key)
            if cached is not None:
                logger.debug(f"Embedding cache hit for: {text[:50]}...")
                return cached

        # Generate embedding
        logger.debug(f"Generating embedding for: {text[:50]}...")
        response = await self.client.embeddings.create(
            model=self.EMBEDDING_MODEL, input=text, encoding_format="float"
        )

        embedding = np.array(response.data[0].embedding, dtype=np.float32)

        # Cache the result
        if self.redis:
            await self._cache_embedding(cache_key, embedding)

        return embedding

    async def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """Generate embeddings for multiple texts efficiently.

        Args:
            texts: List of texts to embed

        Returns:
            List of numpy arrays
        """
        if not texts:
            return []

        # Filter out empty texts and track indices
        valid_texts = [(i, text) for i, text in enumerate(texts) if text and text.strip()]
        if not valid_texts:
            raise ValueError("Cannot embed batch of empty texts")

        # Check cache for all texts
        embeddings: list[np.ndarray | None] = [None] * len(texts)
        texts_to_generate: list[tuple[int, str]] = []

        if self.redis:
            for idx, text in valid_texts:
                cache_key = self._get_cache_key(text)
                cached = await self._get_cached_embedding(cache_key)
                if cached is not None:
                    embeddings[idx] = cached
                else:
                    texts_to_generate.append((idx, text))
        else:
            texts_to_generate = valid_texts

        # Generate embeddings for uncached texts
        if texts_to_generate:
            logger.debug(f"Generating {len(texts_to_generate)} embeddings in batch")
            response = await self.client.embeddings.create(
                model=self.EMBEDDING_MODEL,
                input=[text for _, text in texts_to_generate],
                encoding_format="float",
            )

            for i, (original_idx, text) in enumerate(texts_to_generate):
                embedding = np.array(response.data[i].embedding, dtype=np.float32)
                embeddings[original_idx] = embedding

                # Cache the result
                if self.redis:
                    cache_key = self._get_cache_key(text)
                    await self._cache_embedding(cache_key, embedding)

        return [emb for emb in embeddings if emb is not None]

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        return f"{self._cache_prefix}{self.EMBEDDING_MODEL}:{text_hash}"

    async def _get_cached_embedding(self, cache_key: str) -> np.ndarray | None:
        """Retrieve cached embedding from Redis."""
        try:
            cached_json = await self.redis.get(cache_key)
            if cached_json:
                data = json.loads(cached_json)
                return np.array(data, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to retrieve cached embedding: {e}")
        return None

    async def _cache_embedding(self, cache_key: str, embedding: np.ndarray):
        """Cache embedding in Redis with 7-day TTL."""
        try:
            # Store as JSON list for readability
            embedding_json = json.dumps(embedding.tolist())
            await self.redis.setex(cache_key, 604800, embedding_json)  # 7 days
        except Exception as e:
            logger.warning(f"Failed to cache embedding: {e}")

    def get_cost_per_embedding(self) -> float:
        """Get cost per embedding in USD.

        text-embedding-3-small costs $0.02 / 1M tokens
        Average text is ~100 tokens, so ~$0.000002 per embedding
        """
        return 0.000002

    def get_cost_for_batch(self, num_texts: int, avg_tokens_per_text: int = 100) -> float:
        """Estimate cost for batch embedding.

        Args:
            num_texts: Number of texts to embed
            avg_tokens_per_text: Average tokens per text (default 100)

        Returns:
            Estimated cost in USD
        """
        total_tokens = num_texts * avg_tokens_per_text
        cost_per_million = 0.02
        return (total_tokens / 1_000_000) * cost_per_million
