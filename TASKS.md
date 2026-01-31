# PiedPiper - Parallel Work Assignments

## Shared Foundation (DO NOT modify without coordinating)

These files are the contract between all three work streams. Changes require team agreement:

- `backend/src/piedpiper/models/` - All Pydantic models (state, queries, review, cost, validation)
- `backend/src/piedpiper/config.py` - App settings
- `backend/src/piedpiper/main.py` - FastAPI app entry point
- `docker-compose.yml` - Dev infrastructure

---

## Person 1: Core Workflow (LangGraph + State Management)

**Your domain:** `backend/src/piedpiper/workflow/`

### Files you own:
- `workflow/graph.py` - Main LangGraph graph definition
- `workflow/nodes.py` - All graph node implementations

### Your tasks (in order):

1. **Implement `init_node`** - Create 3 WorkerState instances from DEFAULT_WORKERS, assign session_id (uuid)
2. **Implement `assign_task_node`** - Use an LLM call to break the main task into 3 subtasks matched to worker expertise levels
3. **Implement routing functions** - `_route_after_progress_check`, `_route_after_search`, `_route_after_review`, `_route_after_test` based on state fields
4. **Implement `check_progress_node`** - Evaluate worker progress, update `stuck` and `minutes_without_progress` fields
5. **Implement `worker_execute_node`** - Orchestrate calling `WorkerAgent.execute_subtask()` for each active worker
6. **Implement `arbiter_node`** - Call `ArbiterAgent.should_escalate()` for stuck workers, build ExpertQuery
7. **Implement `hybrid_search_node`** - Call `HybridKnowledgeBase.search()`, attach results
8. **Implement `human_review_node`** - Call `HumanReviewQueue.submit()`, implement wait mechanism
9. **Implement `expert_answer_node`** - Call `ExpertAgent.answer()`, store in cache
10. **Implement remaining nodes** - browserbase_test, generate_report, expert_learn
11. **Wire up session API** - Implement `POST /api/sessions` and `GET /api/sessions/{id}` to invoke the graph

### Integration points (you call into):
- `agents.worker.WorkerAgent` (Person 2)
- `agents.arbiter.ArbiterAgent` (Person 2)
- `agents.expert.ExpertAgent` (Person 2)
- `infra.search.HybridKnowledgeBase` (Person 3)
- `infra.cost.CostController` (Person 3)
- `review.queue.HumanReviewQueue` (Person 3)

### Tests to write:
- `tests/workflow/test_graph.py` - Graph compilation and edge cases
- `tests/workflow/test_nodes.py` - Each node with mocked dependencies

---

## Person 2: Agents (Workers, Arbiter, Expert + Learning)

**Your domain:** `backend/src/piedpiper/agents/`

### Files you own:
- `agents/worker.py` - Worker agent
- `agents/arbiter.py` - Arbiter agent
- `agents/expert.py` - Expert agent
- `agents/learning.py` - Expert learning module

### Your tasks (in order):

1. **Implement `WorkerAgent.initialize_sandbox`** - Daytona SDK integration, sandbox provisioning
2. **Implement `WorkerAgent.execute_subtask`** - Build persona prompts, call LLM, execute code in sandbox, track actions/errors/confidence
3. **Implement `WorkerAgent.apply_expert_answer`** - Inject answer into context, re-attempt task
4. **Implement `ArbiterAgent.build_query`** - Summarize worker context into an ExpertQuery
5. **Implement `ArbiterAgent._classify_issue`** - Full classification logic using signals
6. **Implement `ArbiterAgent._detect_dead_end`** - Dead-end pattern detection
7. **Implement `ExpertAgent.answer`** - Full expert answer pipeline with learned context
8. **Implement `ExpertLearningModule.track_answer`** - Store answers in learning DB
9. **Implement `ExpertLearningModule.evaluate_effectiveness`** - Multi-factor scoring (success 40%, speed 20%, independence 20%, calibration 20%)
10. **Implement `ExpertLearningModule.update_learned_patterns`** - Extract success/failure patterns
11. **Implement `ExpertLearningModule.get_context`** - Format learned patterns for prompt enhancement
12. **Implement `ExpertLearningModule.track_human_correction`** - Learn from human corrections
13. **Implement `ExpertAutoImprovement.periodic_review`** - Category-level analysis, prompt suggestions
14. **Set up learning DB schema** - Alembic migrations for the learning database

### Integration points (you call into):
- `infra.memory.WorkerMemory` (Person 3) - for worker recall
- `infra.cost.CostController` (Person 3) - track LLM costs
- `infra.tracing` (Person 3) - trace LLM calls

### Tests to write:
- `tests/agents/test_worker.py` - Worker execution with mocked sandbox
- `tests/agents/test_arbiter.py` - Escalation logic, signal detection
- `tests/agents/test_expert.py` - Expert answer generation
- `tests/agents/test_learning.py` - Effectiveness scoring, pattern extraction

---

## Person 3: Infrastructure (Redis, Browserbase, Cost, W&B, Dashboard)

**Your domain:** `backend/src/piedpiper/infra/`, `backend/src/piedpiper/review/`, `frontend/`

### Files you own:
- `infra/search.py` - Hybrid search (Redis vector + BM25)
- `infra/memory.py` - Three-tier memory system
- `infra/cost.py` - Cost tracking (skeleton provided, extend as needed)
- `infra/browserbase.py` - Browser validation
- `infra/circuit_breaker.py` - Circuit breakers (skeleton provided, extend as needed)
- `infra/tracing.py` - W&B Weave integration
- `review/queue.py` - Human review queue (skeleton provided, extend with Postgres)
- `review/router.py` - FastAPI review endpoints
- `frontend/` - Next.js review dashboard

### Your tasks (in order):

1. **Implement `HybridKnowledgeBase.initialize_indices`** - Create Redis FT indices for vector and keyword search
2. **Implement `HybridKnowledgeBase.search`** - Full hybrid search with embedding generation
3. **Implement `HybridKnowledgeBase.store`** - Store approved answers with embeddings
4. **Implement `HybridKnowledgeBase.embed`** - OpenAI/Anthropic embedding API call
5. **Implement `RedisMediumTermStore`** - Redis storage with TTL and semantic search
6. **Implement `PostgresLongTermStore`** - Postgres CRUD operations
7. **Set up Alembic migrations** - Main DB schema (sessions, workers, reviews)
8. **Implement `BrowserbaseValidator`** - Full validation pipeline with Browserbase SDK
9. **Implement W&B Weave tracing** - Initialize Weave, implement all trace functions
10. **Extend `HumanReviewQueue`** - Back with Postgres instead of in-memory dict
11. **Build Next.js dashboard** - Review queue UI with approve/reject/modify actions
12. **Add WebSocket support** - Real-time updates for review queue and session progress
13. **Implement dashboard pages** - Session overview, cost breakdown, worker progress

### Tests to write:
- `tests/infra/test_search.py` - Hybrid search with mocked Redis
- `tests/infra/test_cost.py` - Budget checking, cost calculation
- `tests/infra/test_circuit_breaker.py` - All breaker types
- `tests/review/test_queue.py` - Queue operations
- `tests/review/test_router.py` - API endpoint tests

---

## Git Branching Strategy

Each person works on their own branch:

```
main
├── feat/workflow     ← Person 1
├── feat/agents       ← Person 2
└── feat/infra        ← Person 3
```

Merge order: Person 3 first (infra), then Person 2 (agents), then Person 1 (workflow) — since workflow depends on both.

## Coordination Checkpoints

- **Before changing any model in `models/`**: Post in team chat, get agreement
- **Before adding new dependencies**: Add to pyproject.toml on your branch, flag to team
- **Integration test**: After all 3 branches merge, run full integration test
