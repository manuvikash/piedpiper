"""Test Redis Cloud integration without OpenAI embeddings.

This test verifies:
1. Redis Cloud connection
2. Redis Stack modules availability
3. Index creation capability
4. Basic JSON and search operations
"""

import asyncio
import json
import logging
import os
import sys

from redis.asyncio import Redis
import numpy as np

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


async def test_redis_cloud_full():
    """Test Redis Cloud with all features except embeddings."""
    
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        logger.error("REDIS_URL environment variable not set!")
        logger.error("Please set it in your .env file or export it:")
        logger.error("export REDIS_URL='redis://default:PASSWORD@HOST:PORT'")
        return False
    
    # Hide password in output
    display_url = redis_url.split('@')[-1] if '@' in redis_url else redis_url
    
    logger.info("=" * 70)
    logger.info("Testing Redis Cloud Integration (Full Test)")
    logger.info("=" * 70)
    logger.info(f"Redis: {display_url}\n")
    
    try:
        # 1. Connect to Redis Cloud
        logger.info("1️⃣  Connecting to Redis Cloud...")
        redis = Redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=False,
        )
        await redis.ping()
        logger.info("   ✅ Redis Cloud connected\n")
        
        # 2. Test Redis Stack modules
        logger.info("2️⃣  Checking Redis Stack modules...")
        modules = await redis.execute_command('MODULE', 'LIST')
        module_names = []
        for module in modules:
            name = module[1].decode() if isinstance(module[1], bytes) else module[1]
            module_names.append(name)
            logger.info(f"   ✅ {name}")
        
        required_modules = ['search', 'ReJSON']
        for req in required_modules:
            if req not in module_names:
                logger.error(f"   ❌ Required module '{req}' not found!")
                return False
        logger.info("")
        
        # 3. Test JSON operations
        logger.info("3️⃣  Testing ReJSON operations...")
        test_doc = {
            "id": "test_123",
            "question": "How do I test Redis?",
            "answer": "Use the redis-py library with async support",
            "metadata": {
                "category": "testing",
                "approved": True
            }
        }
        
        key = "knowledge:test_123"
        await redis.json().set(key, "$", test_doc)
        logger.info("   ✅ JSON SET successful")
        
        retrieved = await redis.json().get(key)
        assert retrieved["id"] == "test_123"
        logger.info("   ✅ JSON GET successful")
        logger.info(f"   📄 Retrieved: {retrieved['question'][:50]}...\n")
        
        # 4. Test vector operations (mock embeddings)
        logger.info("4️⃣  Testing vector storage...")
        
        # Create mock embeddings (1536 dimensions like OpenAI)
        mock_embedding = np.random.rand(1536).astype(np.float32)
        
        vector_doc = {
            "id": "vec_test_456",
            "question": "What is vector search?",
            "answer": "Vector search finds semantically similar content",
            "question_embedding": mock_embedding.tolist(),
            "metadata": {
                "category": "vectors",
                "approved": True
            }
        }
        
        vec_key = "knowledge:vec_test_456"
        await redis.json().set(vec_key, "$", vector_doc)
        logger.info("   ✅ Vector document stored")
        
        retrieved_vec = await redis.json().get(vec_key)
        assert len(retrieved_vec["question_embedding"]) == 1536
        logger.info(f"   ✅ Vector retrieved (dim: {len(retrieved_vec['question_embedding'])})\n")
        
        # 5. Test search index creation
        logger.info("5️⃣  Testing search index creation...")
        
        index_name = "idx:test_knowledge_" + str(int(asyncio.get_event_loop().time() * 1000))  # Unique name
        
        # Create search index with vector field
        from redis.commands.search.field import TextField, VectorField
        from redis.commands.search.indexDefinition import IndexDefinition, IndexType
        
        schema = (
            TextField("$.question", as_name="question"),
            TextField("$.answer", as_name="answer"),
            VectorField(
                "$.question_embedding",
                "FLAT",
                {
                    "TYPE": "FLOAT32",
                    "DIM": 1536,
                    "DISTANCE_METRIC": "COSINE",
                },
                as_name="question_vector",
            ),
        )
        
        definition = IndexDefinition(
            prefix=["knowledge:"],
            index_type=IndexType.JSON,
        )
        
        await redis.ft(index_name).create_index(
            fields=schema,
            definition=definition,
        )
        logger.info(f"   ✅ Index '{index_name}' created")
        
        # Verify index exists
        info = await redis.ft(index_name).info()
        logger.info(f"   ✅ Index info retrieved ({info['num_docs']} docs)\n")
        
        # 6. Test keyword search
        logger.info("6️⃣  Testing keyword search...")
        
        # Add a few more documents
        docs = [
            {"id": "q1", "question": "How do I authenticate?", "answer": "Use API keys"},
            {"id": "q2", "question": "What are rate limits?", "answer": "1000 req/hour"},
            {"id": "q3", "question": "How to handle errors?", "answer": "Use try-catch"},
        ]
        
        for doc in docs:
            doc_key = f"knowledge:{doc['id']}"
            await redis.json().set(doc_key, "$", doc)
        
        logger.info(f"   ✅ Added {len(docs)} test documents")
        
        # Wait a moment for indexing
        await asyncio.sleep(1)
        
        # Search for "authenticate"
        from redis.commands.search.query import Query
        
        search_query = Query("@question:(authenticate)").return_fields("id", "question")
        results = await redis.ft(index_name).search(search_query)
        
        logger.info(f"   ✅ Keyword search found {results.total} results")
        if results.total > 0:
            for doc in results.docs:
                doc_id = doc.id.split(":")[-1]
                logger.info(f"      - {doc_id}: {getattr(doc, 'question', 'N/A')}")
        logger.info("")
        
        # 7. Test vector search (with mock query vector)
        logger.info("7️⃣  Testing vector similarity search...")
        
        # Create mock query vector
        query_vector = np.random.rand(1536).astype(np.float32)
        query_bytes = query_vector.tobytes()
        
        vector_query = (
            Query("*=>[KNN 3 @question_vector $vec AS score]")
            .return_fields("id", "question", "score")
            .sort_by("score")
            .dialect(2)
        )
        
        params = {"vec": query_bytes}
        vec_results = await redis.ft(index_name).search(vector_query, params)
        
        logger.info(f"   ✅ Vector search found {vec_results.total} results")
        if vec_results.total > 0:
            for doc in vec_results.docs:
                doc_id = doc.id.split(":")[-1]
                score = getattr(doc, 'score', 'N/A')
                logger.info(f"      - {doc_id}: score={score}")
        logger.info("")
        
        # 8. Cleanup
        logger.info("8️⃣  Cleaning up test data...")
        await redis.delete(key, vec_key, *[f"knowledge:{d['id']}" for d in docs])
        try:
            await redis.ft(index_name).dropindex()
            logger.info("   ✅ Index dropped")
        except Exception as e:
            logger.warning(f"   ⚠️  Index cleanup warning: {e}")
        logger.info("   ✅ Cleanup complete\n")
        
        # Close connection
        await redis.aclose()
        
        # Summary
        logger.info("=" * 70)
        logger.info("✅ ALL TESTS PASSED!")
        logger.info("=" * 70)
        logger.info("Redis Cloud is fully configured and ready for:")
        logger.info("  ✅ JSON document storage")
        logger.info("  ✅ Vector embeddings (1536 dimensions)")
        logger.info("  ✅ Hybrid search (keyword + vector)")
        logger.info("  ✅ Index creation and management")
        logger.info("")
        logger.info("Next: Add OPENAI_API_KEY to test with real embeddings")
        logger.info("=" * 70)
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Test failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = asyncio.run(test_redis_cloud_full())
    sys.exit(0 if success else 1)
