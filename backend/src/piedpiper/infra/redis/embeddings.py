"""Embedding generation service.

Owner: Person 3 (Infrastructure)

Handles text embedding generation using local sentence-transformers.
No external API calls needed - runs entirely on-device.
"""

from __future__ import annotations

import hashlib
import json
import logging
from functools import lru_cache
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_model(model_name: str):
    """Load sentence-transformers model (cached singleton)."""
    from sentence_transformers import SentenceTransformer

    logger.info(f"Loading embedding model: {model_name}")
    return SentenceTransformer(model_name)


class EmbeddingService:
    """Manages text embeddings using local sentence-transformers with Redis caching.

    Uses all-MiniLM-L6-v2 by default (384 dimensions, fast, good quality).
    No API keys required - runs locally.
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        redis_client: Any | None = None,
    ):
        self.model_name = model_name
        self.redis = redis_client
        self._cache_prefix = "embedding:"
        self._model = None

    @property
    def embedding_dimensions(self) -> int:
        """Return the embedding dimensions for the current model."""
        model = self._get_model()
        return model.get_sentence_embedding_dimension()

    def _get_model(self):
        """Lazy-load the sentence-transformers model."""
        if self._model is None:
            self._model = _load_model(self.model_name)
        return self._model

    async def embed(self, text: str) -> np.ndarray:
        """Generate embedding for text with Redis caching.

        Args:
            text: Text to embed

        Returns:
            numpy array of shape (embedding_dimensions,)
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

        # Generate embedding locally
        logger.debug(f"Generating embedding for: {text[:50]}...")
        model = self._get_model()
        embedding = model.encode(text, convert_to_numpy=True).astype(np.float32)

        # Cache the result
        if self.redis:
            await self._cache_embedding(cache_key, embedding)

        return embedding

    async def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """Generate embeddings for multiple texts efficiently.

        Sentence-transformers batches internally for GPU/CPU efficiency.

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

        # Generate embeddings for uncached texts in a single batch
        if texts_to_generate:
            logger.debug(f"Generating {len(texts_to_generate)} embeddings in batch")
            model = self._get_model()
            batch_texts = [text for _, text in texts_to_generate]
            batch_embeddings = model.encode(batch_texts, convert_to_numpy=True).astype(np.float32)

            for i, (original_idx, text) in enumerate(texts_to_generate):
                embedding = batch_embeddings[i]
                embeddings[original_idx] = embedding

                # Cache the result
                if self.redis:
                    cache_key = self._get_cache_key(text)
                    await self._cache_embedding(cache_key, embedding)

        return [emb for emb in embeddings if emb is not None]

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        return f"{self._cache_prefix}{self.model_name}:{text_hash}"

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
            embedding_json = json.dumps(embedding.tolist())
            await self.redis.setex(cache_key, 604800, embedding_json)  # 7 days
        except Exception as e:
            logger.warning(f"Failed to cache embedding: {e}")

    def get_cost_per_embedding(self) -> float:
        """Get cost per embedding in USD.

        Local sentence-transformers: $0 (runs on device).
        """
        return 0.0

    def get_cost_for_batch(self, num_texts: int, avg_tokens_per_text: int = 100) -> float:
        """Estimate cost for batch embedding.

        Returns 0.0 since sentence-transformers runs locally.
        """
        return 0.0
