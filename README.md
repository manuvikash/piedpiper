# PiedPiper - AI Focus Group Simulation

AI-powered focus group simulation with 3 worker agents, expert assistance, and intelligent caching.

## Quick Start

### 1. Prerequisites

- Python 3.11+
- Node.js 18+
- OpenAI API key
- Redis Cloud account (free tier works!)

### 2. Redis Cloud Setup

**The system uses Redis Cloud** instead of local Docker for caching and vector search.

**Quick setup:**
1. Sign up at https://redis.com/try-free/ (free 30MB tier)
2. Create a database with **Redis Stack** type
3. Copy connection details

See [Redis Cloud Setup Guide](docs/redis-cloud-setup.md) for detailed instructions.

### 3. Environment Configuration

```bash
# Copy example env file
cp .env.example .env

# Edit .env with your credentials
nano .env
```

**Required variables:**
```bash
OPENAI_API_KEY=sk-...
REDIS_URL=redis://default:password@redis-xxxxx.c123.region.cloud.redislabs.com:12345
```

### 4. Install Dependencies

```bash
# Backend
cd backend
pip install -e .

# Frontend
cd ../frontend
npm install
```

### 5. Run the Application

```bash
# Terminal 1: Backend
cd backend
uvicorn piedpiper.main:app --reload

# Terminal 2: Frontend
cd frontend
npm run dev
```

Visit: http://localhost:3000

## Architecture

```
Worker Agents (3) → Get Stuck → Arbiter → Redis Cache Search
                                               ↓
                                    Cache Hit? ─┬─ Yes → Return to Worker
                                                └─ No  → Expert Agent
                                                           ↓
                                                    Human Approval
                                                           ↓
                                                    Cache + Vectorize
```

**Key Features:**
- 🤖 **3 AI Workers** - Junior, Intermediate, Senior personas
- 🧠 **Intelligent Caching** - Vector + keyword hybrid search
- 👤 **Human-in-the-Loop** - Approve answers before caching
- 📊 **Cost Tracking** - Monitor LLM and embedding costs
- 🔄 **Self-Improving Expert** - Learns from effectiveness

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Workflow | LangGraph |
| Backend | FastAPI |
| Frontend | Next.js + React |
| Vector DB | Redis Cloud (Stack) |
| Embeddings | OpenAI text-embedding-3-small |
| LLMs | GPT-4, Claude 3.5 Sonnet |
| Sandboxes | Daytona |
| Browser Testing | Browserbase |
| Monitoring | W&B Weave |

## Documentation

- [Redis Implementation](docs/redis-implementation.md) - Caching architecture
- [Redis Cloud Setup](docs/redis-cloud-setup.md) - Step-by-step setup guide
- [Architecture Plan](plan.md) - Full system design

## Testing

### Test Redis Integration

```bash
export OPENAI_API_KEY="sk-..."
export REDIS_URL="redis://default:password@host:port"
python backend/tests/test_redis_integration.py
```

Expected:
```
✓ Redis Cloud connected
✓ Indices created
✓ Hybrid search working
✓ All tests passed!
```

## Project Structure

```
piedpiper/
├── backend/
│   ├── src/piedpiper/
│   │   ├── agents/          # Worker, Arbiter, Expert agents
│   │   ├── infra/           # Redis, embeddings, memory
│   │   ├── workflow/        # LangGraph nodes & graph
│   │   ├── api/             # FastAPI routes
│   │   └── main.py          # App entry point
│   └── tests/               # Integration tests
├── frontend/
│   └── src/                 # Next.js app
├── docs/                    # Documentation
├── plan.md                  # Architecture specification
└── .env.example             # Environment template
```

## Development

### Backend Development

```bash
cd backend

# Install dev dependencies
pip install -e ".[dev]"

# Run with hot reload
uvicorn piedpiper.main:app --reload --log-level debug

# Run tests
pytest
```

### Frontend Development

```bash
cd frontend

# Run dev server
npm run dev

# Build for production
npm run build
```

## Environment Variables

See `.env.example` for all available configuration options.

**Essential:**
- `OPENAI_API_KEY` - OpenAI API key
- `REDIS_URL` - Redis Cloud connection URL
- `ANTHROPIC_API_KEY` - Anthropic API key (for Claude)

**Optional:**
- `DATABASE_URL` - PostgreSQL connection (for long-term storage)
- `DAYTONA_API_KEY` - Daytona API key (for sandboxes)
- `BROWSERBASE_API_KEY` - Browserbase API key (for testing)
- `WANDB_API_KEY` - Weights & Biases API key (for monitoring)

## Redis Cloud Benefits

**Why Redis Cloud over Docker?**
- ✅ No local infrastructure needed
- ✅ Always available (cloud-hosted)
- ✅ Free tier with Redis Stack (vector search)
- ✅ Automatic backups
- ✅ SSL/TLS support
- ✅ Global availability

**Free Tier Limits:**
- 30MB storage (~2,000 cached Q&A pairs)
- Redis Stack features included
- 30 concurrent connections
- Unlimited bandwidth

## Cost Estimates

| Component | Cost |
|-----------|------|
| Redis Cloud | Free (30MB tier) |
| OpenAI Embeddings | ~$0.000002 per text |
| OpenAI GPT-4 | ~$0.03 per 1K tokens |
| Anthropic Claude | ~$0.015 per 1K tokens |
| **Total per session** | ~$0.10 - $2.00 |

Budget controls enforced at $50/session.

## Roadmap

- [x] Redis Cloud integration
- [x] Hybrid search (vector + keyword)
- [x] Embedding service with caching
- [x] Cost tracking
- [ ] Worker agents (in progress)
- [ ] Arbiter agent
- [ ] Expert agent
- [ ] Human review UI
- [ ] Browserbase integration
- [ ] W&B Weave monitoring
- [ ] Self-improvement system

## Contributing

See `plan.md` for the complete architecture and implementation plan.

## License

MIT
