# Redis Implementation

This document describes the Redis caching and memory system implementation for the PiedPiper AI Focus Group Simulation.

## Overview

The Redis implementation provides:

1. **Hybrid Knowledge Base** - Vector + keyword search for cached expert answers
2. **Medium-Term Memory** - Worker memory with 24-hour TTL
3. **Embedding Service** - Text embedding generation with caching
4. **Cost Tracking** - Automatic tracking of embedding costs

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Arbitrary Agent (Worker)                  │
│                         gets stuck                           │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      Arbiter Agent                           │
│                  evaluates & escalates                       │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Redis Hybrid Search (Vector + BM25)             │
│                                                               │
│  ┌─────────────────┐      ┌──────────────────┐              │
│  │ Vector Search   │      │ Keyword Search   │              │
│  │ (Semantic)      │ ───▶ │    (BM25)        │              │
│  └─────────────────┘      └──────────────────┘              │
│           │                        │                         │
│           └────────┬───────────────┘                         │
│                    ▼                                         │
│          Reciprocal Rank Fusion                              │
└───────────────────────────┬─────────────────────────────────┘
                            │
            ┌───────────────┴────────────────┐
            │                                │
            ▼                                ▼
    ┌──────────────┐              ┌────────────────┐
    │  CACHE HIT   │              │  CACHE MISS    │
    │              │              │                │
    │ Return to    │              │ Expert Agent   │
    │   Worker     │              │   (Claude)     │
    └──────────────┘              └────────┬───────┘
                                           │
                                           ▼
                                  ┌────────────────┐
                                  │ Human Review   │
                                  │   & Approval   │
                                  └────────┬───────┘
                                           │
                                           ▼
                                  ┌────────────────┐
                                  │ Store in Cache │
                                  │  + Vectorize   │
                                  └────────────────┘
```

## Components

### 1. Embedding Service (`infra/embeddings.py`)

Generates text embeddings using local sentence-transformers (`all-MiniLM-L6-v2`).

**Features:**
- 1536-dimensional embeddings
- Redis caching with 7-day TTL
- Batch embedding support
- Cost tracking ($0.02 / 1M tokens)

**Usage:**
```python
from piedpiper.infra.embeddings import EmbeddingService

service = EmbeddingService(model_name="all-MiniLM-L6-v2", redis_client=redis)
embedding = await service.embed("How do I authenticate?")
```

### 2. Hybrid Knowledge Base (`infra/search.py`)

Redis-backed search combining vector similarity and keyword matching.

**Features:**
- Vector search using cosine similarity
- BM25 keyword search for exact matches
- Reciprocal Rank Fusion (RRF) for result reranking
- Automatic cost tracking

**Schema:**
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

**Usage:**
```python
from piedpiper.infra.search import HybridKnowledgeBase

kb = HybridKnowledgeBase(redis_client=redis, embedding_service=service)

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

### 3. Medium-Term Memory (`infra/memory.py`)

Redis-backed worker memory with 24-hour TTL.

**Features:**
- Automatic TTL management
- Semantic search over stored memories
- Filter support (worker_id, outcome, etc.)
- Custom sorting

**Usage:**
```python
from piedpiper.infra.memory import RedisMediumTermStore

store = RedisMediumTermStore(redis_client=redis, embedding_service=service)

# Store worker solution
await store.store({
    "worker_id": "junior",
    "problem": "Authentication failing",
    "solution": "Added Bearer token to header",
    "outcome": "success"
})

# Search for similar solutions
results = await store.search(
    query="API authentication issues",
    filters={"worker_id": "junior", "outcome": "success"}
)
```

## Redis Indices

The system creates a single Redis Search index that supports both vector and keyword search:

**Index Name:** `idx:knowledge:vector`

**Fields:**
- `question` (TEXT) - Full-text searchable question
- `answer` (TEXT) - Full-text searchable answer
- `question_vector` (VECTOR) - 1536-dim question embedding
- `answer_vector` (VECTOR) - 1536-dim answer embedding
- `category` (TAG) - Filterable category
- `approved_by` (TEXT) - Approver identifier

**Key Prefix:** `knowledge:*`

## Workflow Integration

### Hybrid Search Node (`workflow/nodes.py`)

When a worker gets stuck, the arbiter escalates to the hybrid search node:

```python
async def hybrid_search_node(state: FocusGroupState) -> dict:
    # 1. Extract question from expert query
    question = state.expert_queries[-1]["question"]
    
    # 2. Search cache
    results, cost = await knowledge_base.search(question, top_k=3)
    
    # 3. Track costs
    state.costs.spent_embeddings += cost
    
    # 4. Return results for human review
    if results:
        # Cache HIT - show human for approval
        state.expert_queries[-1]["cache_hit"] = True
        state.expert_queries[-1]["cache_results"] = results
    else:
        # Cache MISS - proceed to expert agent
        state.expert_queries[-1]["cache_hit"] = False
```

### Expert Answer Node (`workflow/nodes.py`)

After human approval, expert answers are cached:

```python
async def expert_answer_node(state: FocusGroupState) -> dict:
    # 1. Get expert answer (from LLM)
    answer = await expert_agent.answer(query)
    
    # 2. Store in cache after human approval
    doc_id, cost = await knowledge_base.store(
        question=query["question"],
        answer=answer,
        approved_by=query["approved_by"],
        category=query.get("category", "general")
    )
    
    # 3. Track costs
    state.costs.spent_embeddings += cost
```

## Cost Tracking

All embedding operations return cost information:

| Operation | Approximate Cost |
|-----------|-----------------|
| Single embedding | ~$0.000002 USD |
| Search (1 query) | ~$0.000002 USD |
| Store (Q&A pair) | ~$0.000004 USD |

Costs are tracked in `state.costs.spent_embeddings`.

## Environment Variables

Required:
- `EMBEDDING_MODEL` - Local embedding model (default: all-MiniLM-L6-v2, no API key needed)
- `REDIS_URL` - Redis Cloud connection URL

### Redis Cloud Setup

The system is configured to use **Redis Cloud** instead of local Docker Redis.

**URL Format:**
```bash
# Without password (basic)
redis://host:port

# With password (recommended)
redis://default:password@host:port

# With SSL (production)
rediss://default:password@host:port
```

**Example `.env` configuration:**
```bash
# Redis Cloud (free tier: 30MB storage)
REDIS_URL=redis://default:your_password@redis-12345.c123.us-east-1.cloud.redislabs.com:12345

# Or with SSL
REDIS_URL=rediss://default:your_password@redis-12345.c123.us-east-1.cloud.redislabs.com:12345
```

**Getting Redis Cloud credentials:**

1. **Sign up at Redis Cloud** (free tier available)
   - Go to https://redis.com/try-free/
   - Create a free account (30MB storage, perfect for development)

2. **Create a database**
   - Click "Create Database"
   - Choose "Redis Stack" (required for vector search)
   - Select your region (closest to your users)
   - Note: Free tier includes Redis Stack features

3. **Get connection details**
   - Public endpoint: `redis-xxxxx.c123.region.cloud.redislabs.com:12345`
   - Default user: `default`
   - Password: (shown in security tab)

4. **Update your `.env`**
   ```bash
   REDIS_URL=redis://default:your_password@redis-xxxxx.c123.region.cloud.redislabs.com:12345
   ```

**Benefits of Redis Cloud:**
- ✅ No Docker required
- ✅ Free tier (30MB)
- ✅ Redis Stack included (vector search, JSON, search)
- ✅ Automatic backups
- ✅ High availability
- ✅ SSL/TLS support
- ✅ Global replication (paid tiers)

## Testing

Run the integration test:

```bash
# Set environment variables
# No API key needed for embeddings (runs locally)
export REDIS_URL="redis://default:password@redis-xxxxx.c123.region.cloud.redislabs.com:12345"

# Run test
python backend/tests/test_redis_integration.py
```

Expected output:
```
============================================================
Testing Redis Integration (Redis Cloud)
============================================================
Redis URL: redis-xxxxx.c123.region.cloud.redislabs.com:12345

1. Connecting to Redis Cloud...
✓ Redis Cloud connected

2. Initializing embedding service...
✓ Embedding service initialized

3. Initializing hybrid knowledge base...
✓ Knowledge base initialized

...

✓ All tests passed!
✓ Using Redis Cloud: redis-xxxxx.c123.region.cloud.redislabs.com:12345
Total embedding cost: $0.000012
```

**Note:** No Docker required when using Redis Cloud!

## Performance Characteristics

**Search Latency:**
- Embedding generation: ~50-100ms
- Vector search: ~10-20ms
- Keyword search: ~5-10ms
- Total: ~100-150ms per search

**Throughput:**
- Embeddings: ~20-30 per second (batched)
- Searches: ~50-100 per second
- Writes: ~100-200 per second

**Memory:**
- Each Q&A pair: ~15KB (with embeddings)
- 1000 cached answers: ~15MB
- 10,000 cached answers: ~150MB

## Future Enhancements

1. **HNSW Index** - Switch from FLAT to HNSW for better vector search performance
2. **Answer Effectiveness Tracking** - Track which cached answers actually help workers
3. **Automatic Expiration** - Remove low-effectiveness answers after N days
4. **Query Rewriting** - Use LLM to reformulate unclear queries before search
5. **Multi-Index Search** - Separate indices for different product versions
