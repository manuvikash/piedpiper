# Redis Integration Module

This module provides Redis-based caching, vector search, and memory management for the PiedPiper AI Focus Group Simulation.

## Module Structure

```
piedpiper/infra/redis/
├── __init__.py           # Package initialization and exports
├── embeddings.py         # Embedding generation service
├── search.py            # Hybrid knowledge base (vector + keyword)
├── memory.py            # Three-tier memory system
└── README.md            # This file
```

## Components

### 1. EmbeddingService (`embeddings.py`)

Generates text embeddings using OpenAI's API with Redis caching.

**Features:**
- OpenAI text-embedding-3-small (1536 dimensions)
- Redis caching with 7-day TTL
- Batch embedding support
- Automatic cost tracking

**Usage:**
```python
from piedpiper.infra.redis import EmbeddingService

service = EmbeddingService(
    openai_api_key="sk-...",
    redis_client=redis
)

# Single embedding
embedding = await service.embed("How do I authenticate?")

# Batch embeddings
embeddings = await service.embed_batch([
    "Question 1",
    "Question 2",
    "Question 3"
])

# Cost estimation
cost = service.get_cost_per_embedding()  # ~$0.000002
```

### 2. HybridKnowledgeBase (`search.py`)

Redis-backed hybrid search combining vector similarity and keyword matching.

**Features:**
- Vector search using cosine similarity
- BM25 keyword search for exact matches
- Reciprocal Rank Fusion (RRF) for result reranking
- Human-approved answer caching
- Automatic cost tracking

**Usage:**
```python
from piedpiper.infra.redis import HybridKnowledgeBase

kb = HybridKnowledgeBase(
    redis_client=redis,
    embedding_service=service
)

# Initialize indices (once on startup)
await kb.initialize_indices()

# Search for cached answers
results, cost = await kb.search("How do I authenticate?", top_k=5)

# Store human-approved answer
doc_id, cost = await kb.store(
    question="How do I authenticate?",
    answer="Use the API key in the Authorization header",
    approved_by="reviewer@example.com",
    category="authentication"
)
```

**Redis Schema:**
```json
{
  "id": "q_abc123",
  "question": "How do I authenticate?",
  "answer": "Use API key in header: Authorization: Bearer <token>",
  "question_embedding": [0.1, 0.2, ...],
  "answer_embedding": [0.3, 0.4, ...],
  "metadata": {
    "human_approved": true,
    "approved_by": "human_reviewer_1",
    "approval_timestamp": "2024-01-31T10:00:00Z",
    "category": "authentication",
    "effectiveness_score": 0.85
  }
}
```

### 3. Memory System (`memory.py`)

Three-tier memory architecture for worker state management.

**Components:**
- **Short-term:** In-memory dict (current session)
- **Medium-term:** Redis with 24h TTL (session persistence)
- **Long-term:** PostgreSQL (permanent storage)

**Usage:**
```python
from piedpiper.infra.redis import MemorySystem, WorkerMemory

# Initialize memory system
memory = MemorySystem(
    redis_client=redis,
    pg_pool=pg_pool,
    embedding_service=service
)

# Worker-specific memory
worker_memory = WorkerMemory(worker_id="junior", memory=memory)

# Store solution
await worker_memory.remember_solution(
    problem="Authentication failing",
    solution="Added Bearer token to header",
    success=True
)

# Recall similar solutions
similar = await worker_memory.recall_similar_tasks(
    "API authentication issues"
)
```

## Integration

### FastAPI Application (`main.py`)

```python
from piedpiper.infra.redis import (
    EmbeddingService,
    HybridKnowledgeBase
)

# In lifespan startup
app_state.embedding_service = EmbeddingService(
    openai_api_key=settings.openai_api_key,
    redis_client=redis
)

app_state.knowledge_base = HybridKnowledgeBase(
    redis_client=redis,
    embedding_service=app_state.embedding_service
)

await app_state.knowledge_base.initialize_indices()
```

### Workflow Nodes (`workflow/nodes.py`)

```python
from piedpiper.main import app_state

async def hybrid_search_node(state: FocusGroupState) -> dict:
    question = state.expert_queries[-1]["question"]
    
    # Search cache
    results, cost = await app_state.knowledge_base.search(
        question, 
        top_k=3
    )
    
    # Track costs
    state.costs.spent_embeddings += cost
    
    return {
        "expert_queries": state.expert_queries,
        "costs": state.costs
    }
```

## Configuration

### Environment Variables

```bash
# Required
OPENAI_API_KEY=sk-...
REDIS_URL=redis://default:password@host:port

# Optional
REDIS_CACHE_TTL=604800  # 7 days for embeddings
REDIS_MEMORY_TTL=86400  # 24 hours for worker memory
```

### Redis Cloud Setup

See `docs/redis-cloud-setup.md` for detailed setup instructions.

**Quick setup:**
1. Sign up at https://redis.com/try-free/
2. Create database with **Redis Stack** type
3. Copy connection details to `.env`

## Testing

### Unit Tests

```bash
# Test Redis connection
python backend/tests/test_redis_connection.py

# Test full integration (without OpenAI)
python backend/tests/test_redis_cloud_complete.py

# Test with real embeddings (requires OPENAI_API_KEY)
export OPENAI_API_KEY="sk-..."
python backend/tests/test_redis_integration.py
```

### Expected Output

```
✅ Redis Cloud connected
✅ Embedding service initialized
✅ Indices created
✅ Hybrid search working
✅ All tests passed!
```

## Performance

| Operation | Latency | Cost |
|-----------|---------|------|
| Embedding generation | ~50-100ms | $0.000002 |
| Vector search | ~10-20ms | - |
| Keyword search | ~5-10ms | - |
| Hybrid search | ~100-150ms | $0.000002 |
| Cache storage | ~20-30ms | $0.000004 |

## Storage Capacity

**Free Tier (Redis Cloud):**
- Storage: 30 MB
- Cached Q&A pairs: ~2,000
- Per Q&A pair: ~15 KB (with embeddings)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Worker Gets Stuck                     │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│                   Arbiter Escalates                      │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│         Redis Hybrid Search (Vector + Keyword)          │
│                                                           │
│  EmbeddingService → HybridKnowledgeBase                  │
│        │                     │                            │
│        ▼                     ▼                            │
│  Generate Embedding    Search Indices                    │
│  (OpenAI API)         (Redis Stack)                      │
│        │                     │                            │
│        └─────────┬───────────┘                           │
│                  ▼                                        │
│         RRF Fusion Reranking                             │
└───────────────────────┬─────────────────────────────────┘
                        │
            ┌───────────┴──────────┐
            ▼                      ▼
    ┌──────────────┐      ┌─────────────┐
    │  CACHE HIT   │      │ CACHE MISS  │
    │              │      │             │
    │ Return to    │      │ Expert      │
    │   Worker     │      │  Agent      │
    └──────────────┘      └──────┬──────┘
                                 │
                                 ▼
                        ┌─────────────┐
                        │   Human     │
                        │  Approval   │
                        └──────┬──────┘
                               │
                               ▼
                        ┌─────────────┐
                        │   Store +   │
                        │  Vectorize  │
                        └─────────────┘
```

## Error Handling

All components handle errors gracefully:

```python
try:
    results, cost = await kb.search(query)
except redis.ConnectionError:
    logger.error("Redis connection failed")
    # Fallback to expert agent
except Exception as e:
    logger.error(f"Search failed: {e}")
    # Track error and continue
```

## Monitoring

### Logging

```python
import logging

logger = logging.getLogger(__name__)

# Embedding service logs
logger.info("✓ Generated embedding for: text...")
logger.debug("Embedding cache hit for: text...")

# Knowledge base logs
logger.info("Hybrid search returned 5 results in 0.123s")
logger.info("✓ Cached answer stored as q_abc123")

# Memory logs
logger.debug("Stored memory item mem_xyz789")
```

### Metrics

Track these metrics for observability:

- Embedding cache hit rate
- Search latency (p50, p95, p99)
- Cache hit/miss ratio
- Total embedding costs
- Redis memory usage

## Best Practices

1. **Initialize once:** Create indices on application startup, not per request
2. **Batch embeddings:** Use `embed_batch()` for multiple texts
3. **Cache results:** Embeddings are cached automatically in Redis
4. **Track costs:** All operations return cost information
5. **Handle errors:** Implement fallbacks for Redis failures
6. **Monitor usage:** Track Redis memory to avoid free tier limits

## Troubleshooting

### Connection Issues

```python
# Test Redis connection
await redis.ping()  # Should return True
```

### Module Not Found

```python
# Check Redis Stack modules
modules = await redis.execute_command('MODULE', 'LIST')
# Should include: search, ReJSON, vectorset
```

### Index Errors

```python
# Drop and recreate index
await redis.ft(index_name).dropindex()
await kb.initialize_indices()
```

## Related Documentation

- `docs/redis-implementation.md` - Architecture details
- `docs/redis-cloud-setup.md` - Redis Cloud setup guide
- `REDIS_TEST_RESULTS.md` - Test results and verification
- `REDIS_SETUP_COMPLETE.md` - Configuration summary

## Support

For issues or questions:
1. Check test scripts: `backend/tests/test_redis_*.py`
2. Review documentation: `docs/redis-*.md`
3. Check Redis Cloud dashboard: https://app.redislabs.com
4. Redis documentation: https://redis.io/docs/stack/
