"""Hybrid search system - Redis vector + BM25.

Owner: Person 3 (Infrastructure)

Implements Reciprocal Rank Fusion (RRF) over vector similarity
and keyword search results from Redis Stack.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any

import numpy as np
from redis.commands.search.field import TagField, TextField, VectorField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.query import Query

logger = logging.getLogger(__name__)


class HybridKnowledgeBase:
    """Redis-backed hybrid search with vector + BM25 + RRF."""

    VECTOR_INDEX_NAME = "idx:knowledge:vector"
    KEYWORD_INDEX_NAME = "idx:knowledge:keyword"
    KEY_PREFIX = "knowledge:"
    
    def __init__(self, redis_client: Any, embedding_service: Any):
        self.redis = redis_client
        self.embedding_service = embedding_service

    async def initialize_indices(self):
        """Create Redis search indices (vector_idx and keyword_idx).

        Call once on startup.
        """
        try:
            # Try to get existing index info - if it exists, we're done
            await self.redis.ft(self.VECTOR_INDEX_NAME).info()
            logger.info(f"Vector index '{self.VECTOR_INDEX_NAME}' already exists")
        except Exception:
            # Index doesn't exist, create it
            logger.info(f"Creating vector index '{self.VECTOR_INDEX_NAME}'...")
            
            schema = (
                TextField("$.question", as_name="question"),
                TextField("$.answer", as_name="answer"),
                VectorField(
                    "$.question_embedding",
                    "FLAT",
                    {
                        "TYPE": "FLOAT32",
                        "DIM": self.embedding_service.EMBEDDING_DIMENSIONS,
                        "DISTANCE_METRIC": "COSINE",
                    },
                    as_name="question_vector",
                ),
                VectorField(
                    "$.answer_embedding",
                    "FLAT",
                    {
                        "TYPE": "FLOAT32",
                        "DIM": self.embedding_service.EMBEDDING_DIMENSIONS,
                        "DISTANCE_METRIC": "COSINE",
                    },
                    as_name="answer_vector",
                ),
                TagField("$.metadata.category", as_name="category"),
                TextField("$.metadata.approved_by", as_name="approved_by"),
            )
            
            definition = IndexDefinition(
                prefix=[self.KEY_PREFIX],
                index_type=IndexType.JSON,
            )
            
            await self.redis.ft(self.VECTOR_INDEX_NAME).create_index(
                fields=schema,
                definition=definition,
            )
            logger.info(f"✓ Created vector index '{self.VECTOR_INDEX_NAME}'")
        
        # Note: We use the same index for keyword search since Redis Search
        # supports both vector and full-text search in a single index

    async def search(self, query: str, top_k: int = 5) -> tuple[list[dict], float]:
        """Hybrid search: vector + BM25 with RRF reranking.

        Returns:
            Tuple of (list of cached answers ranked by relevance, embedding cost in USD)
        """
        if not query or not query.strip():
            return [], 0.0
        
        logger.debug(f"Searching cache for: {query[:100]}...")
        start_time = time.time()
        
        # 1. Generate query embedding
        query_embedding = await self.embedding_service.embed(query)
        embedding_cost = self.embedding_service.get_cost_per_embedding()
        query_bytes = query_embedding.astype(np.float32).tobytes()
        
        # 2. Vector search (semantic similarity)
        vector_results = await self._vector_search(query_bytes, top_k=top_k * 2)
        
        # 3. Keyword search (BM25)
        keyword_results = await self._keyword_search(query, top_k=top_k * 2)
        
        # 4. Reciprocal Rank Fusion
        fused_items = self.rerank_fusion(vector_results, keyword_results, k=60)
        
        # 5. Fetch and return top-k results
        results = []
        for doc_id, score in fused_items[:top_k]:
            try:
                # Get full document from Redis
                doc_key = f"{self.KEY_PREFIX}{doc_id}"
                doc_json = await self.redis.json().get(doc_key)
                if doc_json:
                    doc_json["relevance_score"] = score
                    results.append(doc_json)
            except Exception as e:
                logger.warning(f"Failed to fetch document {doc_id}: {e}")
        
        elapsed = time.time() - start_time
        logger.info(
            f"Hybrid search returned {len(results)} results in {elapsed:.3f}s "
            f"(vector: {len(vector_results)}, keyword: {len(keyword_results)})"
        )
        
        return results, embedding_cost

    async def _vector_search(self, query_bytes: bytes, top_k: int = 10) -> list[dict]:
        """Perform vector similarity search."""
        try:
            query_obj = (
                Query(f"*=>[KNN {top_k} @question_vector $vec AS score]")
                .return_fields("id", "question", "answer", "score")
                .sort_by("score")
                .dialect(2)
            )
            
            params = {"vec": query_bytes}
            result = await self.redis.ft(self.VECTOR_INDEX_NAME).search(query_obj, params)
            
            # Convert to list of dicts with normalized structure
            hits = []
            for doc in result.docs:
                # Extract ID from the document key (format: "knowledge:q_abc123")
                doc_id = doc.id.split(":")[-1] if ":" in doc.id else doc.id
                hits.append({
                    "id": doc_id,
                    "question": getattr(doc, "question", ""),
                    "answer": getattr(doc, "answer", ""),
                    "score": float(getattr(doc, "score", 0)),
                })
            
            return hits
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    async def _keyword_search(self, query: str, top_k: int = 10) -> list[dict]:
        """Perform BM25 keyword search."""
        try:
            # Escape special characters and create search query
            escaped_query = query.replace("-", "\\-").replace(":", "\\:")
            query_obj = (
                Query(f"@question|answer:({escaped_query})")
                .return_fields("id", "question", "answer")
                .paging(0, top_k)
                .dialect(2)
            )
            
            result = await self.redis.ft(self.VECTOR_INDEX_NAME).search(query_obj)
            
            # Convert to list of dicts
            hits = []
            for doc in result.docs:
                # Extract ID from the document key
                doc_id = doc.id.split(":")[-1] if ":" in doc.id else doc.id
                hits.append({
                    "id": doc_id,
                    "question": getattr(doc, "question", ""),
                    "answer": getattr(doc, "answer", ""),
                })
            
            return hits
        except Exception as e:
            logger.error(f"Keyword search failed: {e}")
            return []

    async def store(
        self,
        question: str,
        answer: str,
        approved_by: str,
        approval_timestamp: str | None = None,
        human_modified: bool = False,
        original_expert_answer: str | None = None,
        category: str = "general",
    ) -> tuple[str, float]:
        """Store a human-approved answer in the cache.
        
        Returns:
            Tuple of (document ID, embedding cost in USD)
        """
        if not question or not answer:
            raise ValueError("Question and answer cannot be empty")
        
        logger.info(f"Storing cached answer for: {question[:100]}...")
        start_time = time.time()
        
        # Generate embeddings for both question and answer
        question_embedding, answer_embedding = await self.embedding_service.embed_batch(
            [question, answer]
        )
        embedding_cost = self.embedding_service.get_cost_for_batch(2)
        
        # Create unique ID
        doc_id = f"q_{uuid.uuid4().hex[:12]}"
        doc_key = f"{self.KEY_PREFIX}{doc_id}"
        
        # Prepare document
        timestamp = approval_timestamp or datetime.utcnow().isoformat()
        document = {
            "id": doc_id,
            "question": question,
            "answer": answer,
            "question_embedding": question_embedding.tolist(),
            "answer_embedding": answer_embedding.tolist(),
            "metadata": {
                "human_approved": True,
                "approved_by": approved_by,
                "approval_timestamp": timestamp,
                "category": category,
                "human_modified": human_modified,
                "times_asked": 1,
                "asked_by": [],
                "effectiveness_score": None,
            },
        }
        
        if original_expert_answer:
            document["metadata"]["original_expert_answer"] = original_expert_answer
        
        # Store in Redis as JSON
        await self.redis.json().set(doc_key, "$", document)
        
        elapsed = time.time() - start_time
        logger.info(f"✓ Cached answer stored as {doc_id} in {elapsed:.3f}s")
        
        return doc_id, embedding_cost

    def rerank_fusion(
        self, vector_hits: list, keyword_hits: list, k: int = 60
    ) -> list[tuple[str, float]]:
        """Reciprocal Rank Fusion over two result lists."""
        fused_scores: dict[str, float] = {}
        for rank, hit in enumerate(vector_hits):
            hit_id = hit["id"] if isinstance(hit, dict) else hit.id
            fused_scores[hit_id] = fused_scores.get(hit_id, 0) + 1 / (k + rank)
        for rank, hit in enumerate(keyword_hits):
            hit_id = hit["id"] if isinstance(hit, dict) else hit.id
            fused_scores[hit_id] = fused_scores.get(hit_id, 0) + 1 / (k + rank)
        return sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
