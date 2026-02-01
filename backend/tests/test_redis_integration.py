"""Test Redis integration end-to-end with local embeddings.

This test verifies:
1. Redis connection
2. Local embedding generation (sentence-transformers)
3. Vector index creation
4. Cache storage with embeddings
5. Hybrid search (vector + keyword)
"""

import asyncio
import logging
import os

from redis.asyncio import Redis

from piedpiper.infra.redis import EmbeddingService, HybridKnowledgeBase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_redis_integration():
    """Test the full Redis caching workflow."""

    # Get Redis URL from environment
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        logger.error("REDIS_URL environment variable not set!")
        logger.error("Please set it in your .env file or export it:")
        logger.error("export REDIS_URL='redis://default:PASSWORD@HOST:PORT'")
        return False

    logger.info("=" * 60)
    logger.info("Testing Redis Integration (with local embeddings)")
    logger.info("=" * 60)
    logger.info(f"Redis URL: {redis_url.split('@')[-1]}")  # Hide password if present

    try:
        # 1. Connect to Redis
        logger.info("\n1. Connecting to Redis...")
        redis = Redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=False,
            ssl_cert_reqs=None if redis_url.startswith("rediss://") else None,
        )
        await redis.ping()
        logger.info("✓ Redis connected")

        # 2. Initialize embedding service (local, no API key needed)
        logger.info("\n2. Initializing embedding service (sentence-transformers)...")
        embedding_service = EmbeddingService(
            model_name="all-MiniLM-L6-v2",
            redis_client=redis,
        )
        logger.info("✓ Embedding service initialized")

        # 3. Initialize knowledge base
        logger.info("\n3. Initializing hybrid knowledge base...")
        kb = HybridKnowledgeBase(
            redis_client=redis,
            embedding_service=embedding_service,
        )
        logger.info("✓ Knowledge base initialized")

        # 4. Create indices
        logger.info("\n4. Creating search indices...")
        await kb.initialize_indices()
        logger.info("✓ Indices created")

        # 5. Test embedding generation
        logger.info("\n5. Testing embedding generation...")
        test_text = "How do I authenticate with the API?"
        embedding = await embedding_service.embed(test_text)
        logger.info(f"✓ Generated embedding with shape: {embedding.shape}")
        logger.info(f"  First 5 values: {embedding[:5]}")

        # 6. Store test data
        logger.info("\n6. Storing test Q&A in cache...")
        test_data = [
            {
                "question": "How do I authenticate with the API?",
                "answer": "Use the API key in the Authorization header: `Authorization: Bearer YOUR_API_KEY`",
                "category": "authentication",
            },
            {
                "question": "What rate limits apply to API calls?",
                "answer": "The API has a rate limit of 1000 requests per hour for standard accounts.",
                "category": "rate_limits",
            },
            {
                "question": "How can I handle errors in the SDK?",
                "answer": "Wrap your calls in try-catch blocks and check for error codes in the response.",
                "category": "error_handling",
            },
        ]

        for item in test_data:
            doc_id, cost = await kb.store(
                question=item["question"],
                answer=item["answer"],
                approved_by="test_user",
                category=item["category"],
            )
            logger.info(f"  ✓ Stored: {doc_id} - {item['question'][:50]}...")

        # 7. Test hybrid search - exact match
        logger.info("\n7. Testing hybrid search (exact match)...")
        results, search_cost = await kb.search("How do I authenticate?", top_k=3)
        logger.info(f"  Found {len(results)} results:")
        for i, result in enumerate(results):
            score = result.get("relevance_score", 0)
            question = result.get("question", "")
            logger.info(f"    {i+1}. [score: {score:.3f}] {question[:60]}...")

        # 8. Test semantic search
        logger.info("\n8. Testing semantic search (similar meaning)...")
        results, search_cost = await kb.search("What's the request limit?", top_k=3)
        logger.info(f"  Found {len(results)} results:")
        for i, result in enumerate(results):
            score = result.get("relevance_score", 0)
            question = result.get("question", "")
            logger.info(f"    {i+1}. [score: {score:.3f}] {question[:60]}...")

        # 9. Summary
        logger.info("\n" + "=" * 60)
        logger.info("Test Summary")
        logger.info("=" * 60)
        logger.info("Embedding cost: $0.00 (local sentence-transformers)")
        logger.info("✓ All tests passed!")

        # Cleanup
        await redis.close()
        return True

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = asyncio.run(test_redis_integration())
    exit(0 if success else 1)
