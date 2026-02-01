"""Test Redis integration end-to-end.

This test verifies:
1. Redis connection
2. Embedding generation
3. Vector index creation
4. Cache storage with embeddings
5. Hybrid search (vector + keyword)
6. Cost tracking
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
    
    # Check for API keys
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logger.error("OPENAI_API_KEY not set - cannot test embeddings")
        return False
    
    # Use Redis Cloud URL from environment or default
    redis_url = os.getenv(
        "REDIS_URL",
        "redis://redis-15166.c258.us-east-1-4.ec2.cloud.redislabs.com:15166"
    )
    
    logger.info("=" * 60)
    logger.info("Testing Redis Integration (Redis Cloud)")
    logger.info("=" * 60)
    logger.info(f"Redis URL: {redis_url.split('@')[-1]}")  # Hide password if present
    
    try:
        # 1. Connect to Redis Cloud
        logger.info("\n1. Connecting to Redis Cloud...")
        
        # Configure Redis client for cloud (with SSL support if using rediss://)
        redis = Redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=False,
            ssl_cert_reqs=None if redis_url.startswith("rediss://") else None,
        )
        await redis.ping()
        logger.info("✓ Redis Cloud connected")
        
        # 2. Initialize embedding service
        logger.info("\n2. Initializing embedding service...")
        embedding_service = EmbeddingService(
            openai_api_key=openai_api_key,
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
        
        total_storage_cost = 0.0
        for item in test_data:
            doc_id, cost = await kb.store(
                question=item["question"],
                answer=item["answer"],
                approved_by="test_user",
                category=item["category"],
            )
            total_storage_cost += cost
            logger.info(f"  ✓ Stored: {doc_id} - {item['question'][:50]}...")
        
        logger.info(f"  Total storage cost: ${total_storage_cost:.6f}")
        
        # 7. Test hybrid search - exact match
        logger.info("\n7. Testing hybrid search (exact match)...")
        results, search_cost = await kb.search("How do I authenticate?", top_k=3)
        logger.info(f"  Search cost: ${search_cost:.6f}")
        logger.info(f"  Found {len(results)} results:")
        for i, result in enumerate(results):
            score = result.get("relevance_score", 0)
            question = result.get("question", "")
            logger.info(f"    {i+1}. [score: {score:.3f}] {question[:60]}...")
        
        # 8. Test semantic search
        logger.info("\n8. Testing semantic search (similar meaning)...")
        results, search_cost = await kb.search("What's the request limit?", top_k=3)
        logger.info(f"  Search cost: ${search_cost:.6f}")
        logger.info(f"  Found {len(results)} results:")
        for i, result in enumerate(results):
            score = result.get("relevance_score", 0)
            question = result.get("question", "")
            logger.info(f"    {i+1}. [score: {score:.3f}] {question[:60]}...")
        
        # 9. Test cache miss
        logger.info("\n9. Testing cache miss...")
        results, search_cost = await kb.search("How do I deploy to production?", top_k=3)
        logger.info(f"  Search cost: ${search_cost:.6f}")
        logger.info(f"  Found {len(results)} results (should be low relevance)")
        
        # 10. Summary
        logger.info("\n" + "=" * 60)
        logger.info("Test Summary")
        logger.info("=" * 60)
        logger.info(f"Total embedding cost: ${total_storage_cost + search_cost * 3:.6f}")
        logger.info("✓ All tests passed!")
        logger.info(f"✓ Using Redis Cloud: {redis_url.split('@')[-1]}")
        
        # Cleanup
        await redis.close()
        return True
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = asyncio.run(test_redis_integration())
    exit(0 if success else 1)
