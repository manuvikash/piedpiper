# PiedPiper - AI Focus Group Simulation

## What Is This?

PiedPiper simulates a focus group of 3 AI worker agents (junior, intermediate, senior) testing an SDK/API product. Workers attempt tasks independently in sandboxed environments. When they get stuck, an arbiter escalates to an expert agent through a human-approved review queue. The expert learns from answer effectiveness over time, creating a self-improving system.

**Core flow:**
```
3 Workers → Arbiter (when stuck) → Hybrid Search (cache check)
    → Human Review → Expert Agent → Cache Answer
    → Workers Continue → Browserbase Validation → Report
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.11 + FastAPI |
| Workflow | LangGraph (state machine) |
| LLM Provider | W&B Inference (OpenAI-compatible API) |
| LLM Models | DeepSeek R1/V3, Llama 3.x, Qwen, Phi-4 |
| Embeddings | sentence-transformers (local, zero cost) |
| Frontend | Next.js + TypeScript + Tailwind |
| Vector DB / Cache | Redis Stack (vector + BM25) |
| State Store | PostgreSQL |
| Learning DB | PostgreSQL (separate) |
| Sandboxes | Daytona |
| Browser Testing | Browserbase |
| LLM Ops | W&B Weave |
| Package Management | uv |
| Dev Infrastructure | Docker Compose |

## Project Structure

```
piedpiper/
├── backend/
│   ├── src/piedpiper/
│   │   ├── models/          # Shared data models (Pydantic) — THE CONTRACT
│   │   ├── workflow/         # LangGraph graph + node implementations
│   │   ├── agents/           # Worker, Arbiter, Expert, Learning agents
│   │   ├── infra/            # Redis search, memory, cost, browserbase, circuit breakers, tracing
│   │   ├── review/           # Human review queue + FastAPI endpoints
│   │   ├── api/              # Core session API endpoints
│   │   ├── main.py           # FastAPI application entry point
│   │   └── config.py         # Environment settings
│   ├── tests/                # Mirrors src/ structure
│   ├── scripts/init-db.sql   # Database initialization
│   ├── pyproject.toml        # Dependencies
│   └── Dockerfile
├── frontend/                 # Next.js review dashboard (scaffolded)
├── docker-compose.yml        # Redis, Postgres, backend, frontend
├── PLAN.md                   # Full architecture plan
├── TASKS.md                  # Parallel work assignments
└── .env.example              # All required environment variables
```

## Current Status

### Fully Implemented

| Module | What's Done |
|--------|-------------|
| **All Pydantic models** | `FocusGroupState`, `WorkerState`, `ExpertQuery`, `ExpertAnswer`, `ReviewItem`, `BudgetConfig`, `ValidationResult`, all enums (`Phase`, `IssueType`, `ReviewStatus`, `WorkerExpertise`) |
| **Cost controller** | `CostController.track_llm_call()`, `check_budget()`, `get_cost_saving_recommendation()`, model pricing table, `calculate_cost()` |
| **Circuit breakers** | All 5 types: `ConsecutiveFailureBreaker`, `RepetitionBreaker`, `CostSpikeBreaker`, `TimeoutBreaker`, `NoProgressBreaker` + `CircuitBreakerSystem` aggregator |
| **Arbiter scoring** | `should_escalate()` with multi-signal detection (time stuck, error loop, low confidence, repetition, dead end), weighted urgency scoring |
| **Review queue** | `HumanReviewQueue` with `submit()`, `get_pending()`, `get_item()`, `get_all()`, `process_decision()` (in-memory, needs Postgres backing) |
| **Review API** | 4 FastAPI endpoints: list all, list pending, get by ID, submit decision |
| **Search reranking** | Reciprocal Rank Fusion algorithm in `HybridKnowledgeBase.rerank_fusion()` |
| **FastAPI app** | CORS, lifespan, router wiring, health check endpoint |
| **Config** | All environment variables defined via Pydantic Settings |
| **Docker Compose** | Redis Stack, Postgres, backend, frontend services with health checks |

### Stubbed (Architecture in Place, Logic Not Implemented)

| Module | What Needs Building | Stub Count |
|--------|-------------------|------------|
| **Workflow graph** | 4 routing functions + 11 node implementations | 15 |
| **Worker agent** | Sandbox provisioning, task execution, answer injection, cleanup | 4 |
| **Expert agent** | Answer generation with learned context, confidence estimation | 2 |
| **Learning module** | Answer tracking, effectiveness evaluation, pattern extraction, human corrections, periodic review | 6 |
| **Hybrid search** | Index creation, search execution, answer storage, embedding generation | 4 |
| **Memory stores** | Redis medium-term (store, search), Postgres long-term (store, query) | 4 |
| **Browserbase** | Full validation pipeline + 4 individual checks | 5 |
| **W&B tracing** | 3 trace functions (LLM calls, worker actions, metrics) | 3 |
| **Session API** | Create session, get session, get costs | 3 |

### Not Started

- Database migrations (Alembic)
- Next.js dashboard UI (only default scaffold exists)
- WebSocket real-time updates
- Daytona SDK integration
- Browserbase SDK integration
- W&B Weave initialization
- Learning database schema

## What Needs To Be Done

### Person 1: Core Workflow (`workflow/`)

Owns the LangGraph state machine that orchestrates everything.

1. Implement `init_node` — create 3 workers, assign session ID
2. Implement `assign_task_node` — LLM call to split task by expertise level
3. Implement all 4 routing functions — read state fields to decide next node
4. Implement `check_progress_node` — evaluate worker stuck/progress signals
5. Implement `worker_execute_node` — call `WorkerAgent.execute_subtask()` per worker
6. Implement `arbiter_node` — call arbiter for stuck workers, build queries
7. Implement `hybrid_search_node` — call `HybridKnowledgeBase.search()`
8. Implement `human_review_node` — submit to queue, pause workflow until decision
9. Implement `expert_answer_node` — call expert, cache result
10. Implement `browserbase_test_node`, `generate_report_node`, `expert_learn_node`
11. Wire up `POST /api/sessions` and `GET /api/sessions/{id}` to invoke the graph

**Depends on:** Person 2 (agents) and Person 3 (infra) providing working implementations

### Person 2: Agents (`agents/`)

Owns all AI agent logic — the workers, arbiter decisions, expert answers, and learning.

1. Implement `WorkerAgent` — Daytona sandbox lifecycle + LLM-driven code execution
2. Complete `ArbiterAgent` — `build_query()`, `_detect_dead_end()`, full `_classify_issue()`
3. Implement `ExpertAgent.answer()` — prompt construction with learned context, LLM call, confidence estimation
4. Implement `ExpertLearningModule` — track answers, evaluate effectiveness (4-factor weighted score), extract patterns, handle human corrections
5. Implement `ExpertAutoImprovement` — periodic category-level review, prompt optimization
6. Set up learning database schema with Alembic migrations

**Depends on:** Person 3 (infra) for memory, cost tracking, and tracing

### Person 3: Infrastructure (`infra/`, `review/`, `frontend/`)

Owns all external integrations, data storage, and the human review dashboard.

1. Implement `HybridKnowledgeBase` — Redis FT index creation, embedding generation, full hybrid search
2. Implement `RedisMediumTermStore` and `PostgresLongTermStore` — actual Redis/Postgres operations
3. Set up Alembic migrations for main database
4. Implement `BrowserbaseValidator` — full browser validation pipeline
5. Implement W&B Weave tracing — initialization, all 3 trace functions
6. Back `HumanReviewQueue` with Postgres instead of in-memory dict
7. Build Next.js dashboard — review queue UI, session overview, cost breakdown, worker progress
8. Add WebSocket support for real-time updates
9. Wire up `FastAPI` lifespan — Redis, Postgres, and Weave initialization/cleanup

**Can start immediately** — no blockers from other work streams

## Branching Strategy

```
main
├── feat/workflow     ← Person 1
├── feat/agents       ← Person 2
└── feat/infra        ← Person 3
```

**Merge order:** `feat/infra` first → `feat/agents` second → `feat/workflow` last

Changes to `models/` require team coordination since all three streams depend on them.

## Running Locally

```bash
# Start infrastructure
docker compose up -d redis postgres

# Backend
cd backend
uv pip install -e ".[dev]"
uvicorn piedpiper.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Environment Variables

Copy `.env.example` to `.env` and fill in:
- `WANDB_API_KEY` — W&B Inference API key (all LLM calls go through this)
- `DAYTONA_API_KEY` / `DAYTONA_BASE_URL` — sandbox environments
- `BROWSERBASE_API_KEY` / `BROWSERBASE_PROJECT_ID` — browser testing
- `REDIS_URL` / `DATABASE_URL` / `LEARNING_DATABASE_URL` — data stores
- Embeddings run locally via sentence-transformers (no API key needed)
