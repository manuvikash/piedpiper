# PiedPiper Focus Group - Implementation TODO

**Last Updated:** January 31, 2026  
**Status:** Phase 1 - MVP Development

---

## 🎯 Project Overview

AI Focus Group Simulation with 3 worker agents testing SDK/API products in Daytona sandboxes. Includes expert agent with learning capabilities, human review queue, and Browserbase validation.

---

## ✅ COMPLETED

- [x] Project structure and module organization
- [x] All Pydantic models (state, queries, review, cost, validation)
- [x] Config system with .env support
- [x] Daytona SDK integration in WorkerAgent
- [x] FastAPI app skeleton with health endpoint
- [x] Docker compose (Redis, Postgres)
- [x] Cost tracking structure
- [x] Circuit breaker skeleton
- [x] W&B Weave tracing setup
- [x] Requirements.txt with all dependencies

---

## 🔴 PHASE 1: MVP - Core Execution (Priority: CRITICAL)

**Goal:** Workers can execute tasks in Daytona sandboxes with LLM calls

### Person 2: Worker Agent Implementation

**File:** `backend/src/piedpiper/agents/worker.py`

- [ ] **`execute_subtask`** implementation
  - [ ] Build persona-based system prompt (junior/intermediate/senior)
  - [ ] Construct messages from subtask + conversation history
  - [ ] Call W&B Inference API (OpenAI-compatible)
  - [ ] Parse LLM response for code/actions
  - [ ] Execute code in Daytona sandbox using SDK
  - [ ] Track actions in `action_history`
  - [ ] Capture errors in `recent_errors`
  - [ ] Update `llm_confidence` score
  - [ ] Update `minutes_without_progress` tracker
  - [ ] Set `completed` flag when done
  - [ ] Return updated WorkerState

- [ ] **`apply_expert_answer`** implementation
  - [ ] Add expert answer to conversation_history
  - [ ] Reset stuck flag
  - [ ] Re-call execute_subtask with new context

- [ ] **`cleanup`** testing
  - [ ] Test sandbox deletion works correctly
  - [ ] Handle errors gracefully

### Person 1: Core Workflow Nodes

**File:** `backend/src/piedpiper/workflow/nodes.py`

- [ ] **`init_node`**
  - [ ] Generate session_id using uuid4
  - [ ] Create WorkerState for each DEFAULT_WORKERS config
  - [ ] Call `WorkerAgent.initialize_sandbox()` for each worker
  - [ ] Set sandbox_id in WorkerState
  - [ ] Set current_phase to ASSIGN_TASK
  - [ ] Return updated state dict

- [ ] **`assign_task_node`**
  - [ ] Call LLM to break main task into 3 subtasks
  - [ ] Match subtasks to worker expertise levels
  - [ ] Assign subtask to each worker.subtask
  - [ ] Set current_phase to WORKER_EXECUTE
  - [ ] Return updated state dict

- [ ] **`worker_execute_node`**
  - [ ] Loop through workers where completed=False
  - [ ] Create WorkerAgent instance for each
  - [ ] Call `agent.execute_subtask(worker_state, worker.subtask)`
  - [ ] Update worker state with results
  - [ ] Set current_phase to CHECK_PROGRESS
  - [ ] Return updated state dict

- [ ] **`check_progress_node`**
  - [ ] Check if all workers completed
  - [ ] If all complete → set phase to BROWSERBASE_TEST
  - [ ] Evaluate each worker's progress
  - [ ] Update minutes_without_progress
  - [ ] Set stuck=True if no progress for 5+ minutes
  - [ ] If any stuck → set phase to ARBITER
  - [ ] Otherwise → stay in WORKER_EXECUTE
  - [ ] Return updated state dict

**File:** `backend/src/piedpiper/workflow/graph.py`

- [ ] **Routing function:** `_route_after_progress_check`
  - [ ] Check state.current_phase
  - [ ] Return "arbiter" if any worker stuck
  - [ ] Return "browserbase_test" if all complete
  - [ ] Return "worker_execute" otherwise

- [ ] **Wire up routing**
  - [ ] Add conditional_edges after check_progress node
  - [ ] Connect to routing function

### Person 1: API Implementation

**File:** `backend/src/piedpiper/api/routes.py`

- [ ] **`POST /api/sessions`**
  - [ ] Parse CreateSessionRequest
  - [ ] Build FocusGroupState with task and budget
  - [ ] Compile and invoke graph
  - [ ] Store session in memory/Redis
  - [ ] Return session_id and status

- [ ] **`GET /api/sessions/{session_id}`**
  - [ ] Retrieve session from storage
  - [ ] Return current state (phase, workers, costs)

- [ ] **`GET /api/sessions/{session_id}/costs`**
  - [ ] Retrieve session cost tracker
  - [ ] Return cost breakdown

### Testing

- [ ] Test worker sandbox creation (already working)
- [ ] Test worker execution with simple task
- [ ] Test task assignment LLM call
- [ ] Test progress checking logic
- [ ] Test API endpoint: create session
- [ ] Test API endpoint: get session status

---

## 🟡 PHASE 2: Escalation Flow (Priority: HIGH)

**Goal:** Workers can escalate to expert when stuck

### Person 2: Arbiter Agent

**File:** `backend/src/piedpiper/agents/arbiter.py`

- [ ] **`build_query`**
  - [ ] Extract worker context (subtask, recent actions, errors)
  - [ ] Format into clear question string
  - [ ] Include issue_type and urgency
  - [ ] Return ExpertQuery object

- [ ] **`_detect_dead_end`**
  - [ ] Analyze last 10 actions in action_history
  - [ ] Check for repeated failed attempts
  - [ ] Detect no new actions pattern
  - [ ] Return True if dead end detected

- [ ] **`_classify_issue`** (enhance)
  - [ ] Implement full classification logic
  - [ ] Map signals to IssueType enum values
  - [ ] Consider combinations of signals

### Person 2: Expert Agent

**File:** `backend/src/piedpiper/agents/expert.py`

- [ ] **`answer`** (basic version without learning)
  - [ ] Build system prompt with EXPERT_SYSTEM_PROMPT
  - [ ] Add query question and worker context to messages
  - [ ] Call Claude 3.5 Sonnet via Anthropic API
  - [ ] Extract answer from response
  - [ ] Call `_estimate_confidence`
  - [ ] Create and return ExpertAnswer object
  - [ ] (Skip learning tracking for now)

- [ ] **`_estimate_confidence`** (enhance)
  - [ ] Check answer length (longer = more confident)
  - [ ] Check for code examples (increases confidence)
  - [ ] Check for uncertainty phrases (decreases confidence)
  - [ ] Return float 0.0-1.0

### Person 3: Hybrid Search

**File:** `backend/src/piedpiper/infra/search.py`

- [ ] **`initialize_indices`**
  - [ ] Create Redis vector index with FT.CREATE
  - [ ] Define schema: question_vector, answer_text, metadata
  - [ ] Create keyword index with FT.CREATE
  - [ ] Test indices are created

- [ ] **`embed`**
  - [ ] Call OpenAI embeddings API (text-embedding-3-small)
  - [ ] Return numpy array of embeddings
  - [ ] Cache embeddings for reuse

- [ ] **`search`** (simplified version)
  - [ ] Generate query embedding
  - [ ] Run FT.SEARCH for vector similarity
  - [ ] Run FT.SEARCH for keyword match
  - [ ] Apply RRF fusion (already implemented)
  - [ ] Return top_k results

- [ ] **`store`**
  - [ ] Generate embeddings for question and answer
  - [ ] Store in Redis hash with metadata
  - [ ] Add to vector and keyword indices

### Person 3: Human Review Queue

**File:** `backend/src/piedpiper/review/queue.py`

- [ ] **`process_decision`** (enhance)
  - [ ] Add async event for workflow resumption
  - [ ] Trigger expert_answer if approved
  - [ ] Trigger worker notification if rejected
  - [ ] Store corrected answer if modified

- [ ] **Async wait mechanism**
  - [ ] Add asyncio.Event per review_id
  - [ ] Implement wait_for_decision method
  - [ ] Set event when decision received

**File:** `backend/src/piedpiper/review/router.py`

- [ ] **`GET /api/review/pending`**
  - [ ] Call queue.get_pending()
  - [ ] Return list of ReviewItem

- [ ] **`POST /api/review/{review_id}/decision`**
  - [ ] Parse ReviewDecision from request
  - [ ] Call queue.process_decision()
  - [ ] Return success response

- [ ] **`GET /api/review/history`**
  - [ ] Call queue.get_all()
  - [ ] Filter by status if requested
  - [ ] Return list of ReviewItem

### Person 1: Workflow Nodes

**File:** `backend/src/piedpiper/workflow/nodes.py`

- [ ] **`arbiter_node`**
  - [ ] Create ArbiterAgent instance
  - [ ] Loop through stuck workers
  - [ ] Call should_escalate for each
  - [ ] Call build_query to create ExpertQuery
  - [ ] Add to state.expert_queries
  - [ ] Set current_phase to HYBRID_SEARCH

- [ ] **`hybrid_search_node`**
  - [ ] Get latest ExpertQuery from state
  - [ ] Call HybridKnowledgeBase.search()
  - [ ] Attach results to query
  - [ ] If cache hit found → use cached answer
  - [ ] If no hit → set phase to HUMAN_REVIEW

- [ ] **`human_review_node`**
  - [ ] Get latest ExpertQuery
  - [ ] Call HumanReviewQueue.submit()
  - [ ] Wait for decision (async)
  - [ ] Update state based on decision
  - [ ] Route to expert_answer if approved

- [ ] **`expert_answer_node`**
  - [ ] Get latest ExpertQuery
  - [ ] Call ExpertAgent.answer()
  - [ ] Store answer in HybridKnowledgeBase
  - [ ] Apply answer to stuck worker via apply_expert_answer
  - [ ] Set phase to WORKER_EXECUTE (resume)

**File:** `backend/src/piedpiper/workflow/graph.py`

- [ ] **`_route_after_search`**
  - [ ] Check if cache hit exists
  - [ ] Return "worker_execute" if hit
  - [ ] Return "human_review" if miss

- [ ] **`_route_after_review`**
  - [ ] Check review decision
  - [ ] Return "expert_answer" if approved
  - [ ] Return "worker_execute" if rejected/modified

### Testing

- [ ] Test arbiter escalation detection
- [ ] Test expert answer generation
- [ ] Test hybrid search (with mock data)
- [ ] Test human review queue
- [ ] Test full escalation flow end-to-end

---

## 🟢 PHASE 3: Validation & Reporting (Priority: MEDIUM)

**Goal:** Validate worker output and generate reports

### Person 3: Browserbase Validation

**File:** `backend/src/piedpiper/infra/browserbase.py`

- [ ] **`validate_worker_output`**
  - [ ] Extract deployment info from worker output
  - [ ] Deploy app (if needed)
  - [ ] Create Browserbase session
  - [ ] Run all validation checks in parallel
  - [ ] Capture screenshots on failures
  - [ ] Aggregate results into ValidationResult
  - [ ] Cleanup session

- [ ] **`check_page_loads`**
  - [ ] Navigate to page URL
  - [ ] Wait for load event
  - [ ] Check response status
  - [ ] Return ValidationCheck

- [ ] **`check_no_console_errors`**
  - [ ] Listen to console events
  - [ ] Filter for errors only
  - [ ] Return ValidationCheck with error list

- [ ] **`check_api_endpoints`**
  - [ ] Intercept network requests
  - [ ] Match against expected_apis list
  - [ ] Verify responses are successful
  - [ ] Return ValidationCheck

- [ ] **`check_user_flows`**
  - [ ] Execute each flow step (click, type, etc.)
  - [ ] Verify expected outcomes
  - [ ] Return ValidationCheck with pass/fail

### Person 1: Workflow Nodes

**File:** `backend/src/piedpiper/workflow/nodes.py`

- [ ] **`browserbase_test_node`**
  - [ ] Loop through completed workers
  - [ ] Call BrowserbaseValidator.validate_worker_output()
  - [ ] Attach results to worker state
  - [ ] If all pass → set phase to GENERATE_REPORT
  - [ ] If any fail → set phase to WORKER_EXECUTE (retry)

- [ ] **`generate_report_node`**
  - [ ] Aggregate all worker outputs
  - [ ] Include validation results
  - [ ] Calculate success metrics
  - [ ] Include cost breakdown
  - [ ] List lessons learned
  - [ ] Format as structured report
  - [ ] Set phase to EXPERT_LEARN (if learning enabled)
  - [ ] Otherwise set phase to COMPLETED

**File:** `backend/src/piedpiper/workflow/graph.py`

- [ ] **`_route_after_test`**
  - [ ] Check validation results
  - [ ] Return "generate_report" if all pass
  - [ ] Return "worker_execute" if retry needed
  - [ ] Limit retries to prevent infinite loops

### Testing

- [ ] Test Browserbase validation (with mock browser)
- [ ] Test report generation
- [ ] Test routing after validation
- [ ] Test retry logic

---

## 🔵 PHASE 4: Expert Learning System (Priority: MEDIUM)

**Goal:** Expert agent improves over time from effectiveness metrics

### Database Setup

- [ ] **Create learning database schema**
  - [ ] expert_answers table (answer_id, query, answer, category, timestamp)
  - [ ] effectiveness_scores table (answer_id, success, speed, independence, calibration, total_score)
  - [ ] learned_patterns table (category, pattern_text, success_count, usage_count)
  - [ ] Alembic migration for learning DB

### Person 2: Expert Learning Module

**File:** `backend/src/piedpiper/agents/learning.py`

- [ ] **`__init__`**
  - [ ] Connect to learning database
  - [ ] Initialize SQLAlchemy session

- [ ] **`track_answer`**
  - [ ] Store answer in expert_answers table
  - [ ] Create pending effectiveness record
  - [ ] Return answer_id

- [ ] **`evaluate_effectiveness`**
  - [ ] Calculate success metric (40%): Did worker complete task?
  - [ ] Calculate speed metric (20%): Time to resolution
  - [ ] Calculate independence metric (20%): No follow-up questions?
  - [ ] Calculate calibration metric (20%): Confidence matched outcome?
  - [ ] Store in effectiveness_scores table
  - [ ] Call update_learned_patterns

- [ ] **`update_learned_patterns`**
  - [ ] Extract patterns from successful answers
  - [ ] Extract anti-patterns from failed answers
  - [ ] Update learned_patterns table
  - [ ] Increment usage_count for applied patterns

- [ ] **`get_context`**
  - [ ] Query learned_patterns by category
  - [ ] Format top patterns as context string
  - [ ] Include success rates
  - [ ] Return formatted context

- [ ] **`track_human_correction`**
  - [ ] Store original vs corrected answer
  - [ ] Extract difference as learning signal
  - [ ] Update patterns based on correction

### Person 2: Expert Agent Enhancement

**File:** `backend/src/piedpiper/agents/expert.py`

- [ ] **`answer`** (add learning)
  - [ ] Call `learning.get_context(query.category)`
  - [ ] Include learned_context in prompt
  - [ ] After generating answer, call `learning.track_answer()`
  - [ ] Store answer_id in ExpertAnswer

### Person 1: Workflow Node

**File:** `backend/src/piedpiper/workflow/nodes.py`

- [ ] **`expert_learn_node`**
  - [ ] Loop through all expert_queries with answers
  - [ ] Call learning.evaluate_effectiveness() for each
  - [ ] Update expert_learning log in state
  - [ ] Set phase to COMPLETED

### Testing

- [ ] Test effectiveness calculation
- [ ] Test pattern extraction
- [ ] Test learned context formatting
- [ ] Test expert improvement over multiple sessions

---

## 🟣 PHASE 5: Infrastructure & Polish (Priority: LOW)

### Person 3: Memory System

**File:** `backend/src/piedpiper/infra/memory.py`

- [ ] **`RedisMediumTermStore.store`**
  - [ ] Serialize data to JSON
  - [ ] Store in Redis with TTL
  - [ ] Add to search index

- [ ] **`RedisMediumTermStore.search`**
  - [ ] Generate query embedding
  - [ ] Search Redis index
  - [ ] Apply filters
  - [ ] Return results

- [ ] **`PostgresLongTermStore.store`**
  - [ ] Insert data into Postgres
  - [ ] Handle conflicts

- [ ] **`PostgresLongTermStore.query`**
  - [ ] Build SQL query with filters
  - [ ] Execute and return results

### Person 3: Frontend Dashboard

**Directory:** `frontend/`

- [ ] **Review Queue Page** (`app/review/page.tsx`)
  - [ ] Fetch pending reviews from API
  - [ ] Display question, worker context, urgency
  - [ ] Approve/Reject/Modify buttons
  - [ ] Text input for modifications
  - [ ] Submit decision to API

- [ ] **Session Dashboard** (`app/sessions/[id]/page.tsx`)
  - [ ] Fetch session state from API
  - [ ] Display worker statuses (running/stuck/completed)
  - [ ] Show current phase
  - [ ] Display worker outputs
  - [ ] Show cost breakdown
  - [ ] Real-time updates (polling or WebSocket)

- [ ] **Cost Dashboard** (`app/costs/page.tsx`)
  - [ ] Display total spending
  - [ ] Break down by agent type
  - [ ] Show cost per session
  - [ ] Budget alerts

- [ ] **Sessions List** (`app/sessions/page.tsx`)
  - [ ] List all sessions
  - [ ] Filter by status
  - [ ] Click to view details

### Testing & Quality

- [ ] **Unit Tests**
  - [ ] All workflow nodes with mocked dependencies
  - [ ] All agents with mocked LLM/sandbox
  - [ ] All infrastructure modules

- [ ] **Integration Tests**
  - [ ] Full workflow path: init → execute → complete
  - [ ] Escalation path: stuck → expert → resume
  - [ ] Validation path: execute → browserbase → report

- [ ] **End-to-End Test**
  - [ ] Real task with 3 workers in Daytona sandboxes
  - [ ] Real LLM calls (staging environment)
  - [ ] Real human review interaction
  - [ ] Verify report generation

### Documentation

- [ ] API documentation (OpenAPI/Swagger)
- [ ] Deployment guide
- [ ] Configuration guide
- [ ] Architecture diagram updates
- [ ] Code comments and docstrings

### Error Handling

- [ ] LLM API failures (retry with backoff)
- [ ] Daytona sandbox failures (cleanup + retry)
- [ ] Redis connection failures (fallback)
- [ ] Postgres connection failures (queue writes)
- [ ] Browserbase API failures (mark as inconclusive)
- [ ] Budget exceeded (graceful shutdown)

### Monitoring & Observability

- [ ] W&B Weave tracing for all LLM calls
- [ ] Cost tracking for all operations
- [ ] Structured logging throughout
- [ ] Health check endpoints
- [ ] Metrics endpoint (Prometheus format)

---

## 📊 Estimated Timeline

- **Phase 1 (MVP):** 2 days
- **Phase 2 (Escalation):** 2 days
- **Phase 3 (Validation):** 1-2 days
- **Phase 4 (Learning):** 2 days
- **Phase 5 (Polish):** 1-2 days

**Total: 5-8 days** of focused development

---

## 🚀 Quick Start Commands

```bash
# Start infrastructure
docker-compose up -d

# Start backend (with venv activated)
cd backend
PYTHONPATH=./src uvicorn piedpiper.main:app --reload

# Start frontend
cd frontend
npm run dev

# Run tests
cd backend
pytest tests/ -v

# Test Daytona sandbox creation
cd backend
python scripts/keep_session_alive.py
```

---

## 📝 Notes

- Daytona sandboxes are working ✅
- .env file configured with API keys ✅
- All dependencies installed ✅
- Ready to implement Phase 1 🚀

---

## 🔗 Key Files Reference

- **Models:** `backend/src/piedpiper/models/`
- **Workflow:** `backend/src/piedpiper/workflow/`
- **Agents:** `backend/src/piedpiper/agents/`
- **Infrastructure:** `backend/src/piedpiper/infra/`
- **Review:** `backend/src/piedpiper/review/`
- **API:** `backend/src/piedpiper/api/`
- **Config:** `backend/src/piedpiper/config.py`
- **Main:** `backend/src/piedpiper/main.py`
