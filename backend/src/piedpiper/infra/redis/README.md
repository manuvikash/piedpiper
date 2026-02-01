# Redis Integration Module

This module provides Redis-based caching, vector search, and memory management for the PiedPiper AI Focus Group Simulation.

## Module Structure

```
piedpiper/infra/redis/
├── __init__.py           # Package initialization and exports
├── embeddings.py         # Embedding generation service (local sentence-transformers)
├── search.py            # Hybrid knowledge base (vector + keyword)
├── memory.py            # Three-tier memory system
└── README.md            # This file
```

## Components

### 1. EmbeddingService (`embeddings.py`)

Generates text embeddings using local sentence-transformers. No external API keys needed.

**Features:**
- all-MiniLM-L6-v2 model (384 dimensions, fast, good quality)
- Runs entirely on-device (zero API cost)
- Redis caching with 7-day TTL
- Batch embedding support

**Usage:**
```python
from piedpiper.infra.redis import EmbeddingService

service = EmbeddingService(
    model_name="all-MiniLM-L6-v2",
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

# Cost estimation (always $0 for local models)
cost = service.get_cost_per_embedding()  # $0.00
```

### 2. HybridKnowledgeBase (`search.py`)

Redis-backed hybrid search combining vector similarity and keyword matching.

**Features:**
- Vector search using cosine similarity
- BM25 keyword search for exact matches
- Reciprocal Rank Fusion (RRF) for result reranking
- Human-approved answer caching

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

### 3. Memory System (`memory.py`)

Three-tier memory architecture for worker state management.

**Components:**
- **Short-term:** In-memory dict (current session)
- **Medium-term:** Redis with 24h TTL (session persistence)
- **Long-term:** PostgreSQL (permanent storage)

## Integration

### FastAPI Application (`main.py`)

```python
from piedpiper.infra.redis import EmbeddingService, HybridKnowledgeBase

# In lifespan startup (no API key needed)
app_state.embedding_service = EmbeddingService(
    model_name=settings.embedding_model,
    redis_client=redis
)

app_state.knowledge_base = HybridKnowledgeBase(
    redis_client=redis,
    embedding_service=app_state.embedding_service
)

await app_state.knowledge_base.initialize_indices()
```

## LLM Provider

All LLM calls (chat completions) use **W&B Inference** via the OpenAI-compatible API:

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    base_url="https://api.inference.wandb.ai/v1",
    api_key=settings.wandb_api_key,
)

response = await client.chat.completions.create(
    model="deepseek-ai/DeepSeek-R1-0528",
    messages=[...],
)
```

Embeddings use **local sentence-transformers** (no API calls, zero cost).

## Configuration

### Environment Variables

```bash
# Required for LLM calls
WANDB_API_KEY=your-wandb-api-key
WANDB_BASE_URL=https://api.inference.wandb.ai/v1

# Required for cache
REDIS_URL=redis://default:password@host:port

# Optional
EMBEDDING_MODEL=all-MiniLM-L6-v2  # Local model, no API key needed
```

## Testing

```bash
# Test Redis connection + local embeddings
python backend/tests/test_redis_cloud_complete.py

# Test full integration with embeddings
python backend/tests/test_redis_integration.py
```

## Performance

| Operation | Latency | Cost |
|-----------|---------|------|
| Embedding generation (local) | ~5-20ms | $0.00 |
| Vector search | ~10-20ms | - |
| Keyword search | ~5-10ms | - |
| Hybrid search | ~20-50ms | $0.00 |
| Cache storage | ~20-30ms | $0.00 |
