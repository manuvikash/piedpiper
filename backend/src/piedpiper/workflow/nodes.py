"""Graph node implementations.

Each node receives FocusGroupState, performs its work, and returns
updated state. Nodes call into agents/ and infra/ modules but don't
implement agent or infrastructure logic themselves.
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import uuid4

from openai import AsyncOpenAI

from piedpiper.agents.arbiter import ArbiterAgent
from piedpiper.agents.expert import ExpertAgent
from piedpiper.agents.worker import WorkerAgent
from piedpiper.api.events import event_bus
from piedpiper.config import settings
from piedpiper.models.state import (
    DEFAULT_WORKERS,
    FocusGroupState,
    Phase,
    WorkerAction,
    WorkerConfig,
    WorkerState,
)

logger = logging.getLogger(__name__)


async def init_node(state: FocusGroupState) -> dict:
    """Initialize workers and provision sandboxes."""
    if not state.session_id:
        state.session_id = str(uuid4())

    sid = state.session_id
    await event_bus.emit(sid, "system", "phase_change", {"phase": "init"})

    workers = []
    for config in DEFAULT_WORKERS:
        worker_state = WorkerState(
            worker_id=config.id,
            config=config,
        )

        agent = WorkerAgent(config)
        agent.set_emitter(event_bus.make_emitter(sid))

        try:
            sandbox_id = await agent.initialize_sandbox()
            worker_state.sandbox_id = sandbox_id
            await event_bus.emit(sid, config.id, "ready", {
                "sandbox_id": sandbox_id,
            })
        except Exception as e:
            logger.error(f"Failed to initialize sandbox for {config.id}: {e}")
            await event_bus.emit(sid, config.id, "error", {
                "error": str(e)[:300],
            })

        workers.append(worker_state)

    state.workers = workers
    state.current_phase = Phase.ASSIGN_TASK

    return {"workers": workers, "current_phase": Phase.ASSIGN_TASK}


async def assign_task_node(state: FocusGroupState) -> dict:
    """Assign the full task to all workers."""
    sid = state.session_id
    await event_bus.emit(sid, "system", "phase_change", {"phase": "assign_task"})

    for worker in state.workers:
        worker.subtask = state.task
        worker.conversation_history.append({
            "role": "user",
            "content": f"Your task is to test and implement: {state.task}\n\nPlease start by exploring what needs to be done and write code to accomplish this.",
        })
        await event_bus.emit(sid, worker.worker_id, "task_assigned", {
            "task": state.task[:200],
        })

    state.current_phase = Phase.WORKER_EXECUTE
    return {"workers": state.workers, "current_phase": Phase.WORKER_EXECUTE}


async def worker_execute_node(state: FocusGroupState) -> dict:
    """Run worker code in Daytona sandboxes."""
    sid = state.session_id
    await event_bus.emit(sid, "system", "phase_change", {"phase": "worker_execute"})

    for worker in state.workers:
        if not worker.completed and not worker.stuck:
            logger.info(f"Executing subtask for worker {worker.worker_id}")

            agent = WorkerAgent(worker.config)
            agent.sandbox_id = worker.sandbox_id
            agent.set_emitter(event_bus.make_emitter(sid))

            try:
                updated_worker = await agent.execute_subtask(worker, worker.subtask)

                worker.action_history = updated_worker.action_history
                worker.conversation_history = updated_worker.conversation_history
                worker.recent_errors = updated_worker.recent_errors
                worker.llm_confidence = updated_worker.llm_confidence
                worker.minutes_without_progress = updated_worker.minutes_without_progress
                worker.completed = updated_worker.completed
                worker.output = updated_worker.output

                logger.info(
                    f"Worker {worker.worker_id}: "
                    f"completed={worker.completed}, "
                    f"confidence={worker.llm_confidence:.2f}, "
                    f"actions={len(worker.action_history)}"
                )

            except Exception as e:
                logger.error(f"Error executing worker {worker.worker_id}: {e}")
                worker.recent_errors.append(str(e))
                worker.recent_errors = worker.recent_errors[-5:]
                await event_bus.emit(sid, worker.worker_id, "error", {
                    "error": str(e)[:300],
                })

    state.current_phase = Phase.CHECK_PROGRESS
    return {"workers": state.workers, "current_phase": Phase.CHECK_PROGRESS}


async def check_progress_node(state: FocusGroupState) -> dict:
    """Check if workers are making progress."""
    sid = state.session_id
    all_completed = all(worker.completed for worker in state.workers)

    if all_completed:
        logger.info("All workers completed, moving to browserbase test")
        await event_bus.emit(sid, "system", "phase_change", {"phase": "browserbase_test"})
        state.current_phase = Phase.BROWSERBASE_TEST
        return {"workers": state.workers, "current_phase": Phase.BROWSERBASE_TEST}

    for worker in state.workers:
        if not worker.completed and not worker.stuck:
            if worker.minutes_without_progress >= 5.0:
                worker.stuck = True
                await event_bus.emit(sid, worker.worker_id, "stuck", {
                    "reason": "no progress",
                    "minutes": worker.minutes_without_progress,
                })
            elif len(worker.recent_errors) >= 3:
                worker.stuck = True
                await event_bus.emit(sid, worker.worker_id, "stuck", {
                    "reason": "repeated errors",
                    "error_count": len(worker.recent_errors),
                })

    any_stuck = any(worker.stuck for worker in state.workers)

    if any_stuck:
        await event_bus.emit(sid, "system", "phase_change", {"phase": "arbiter"})
        state.current_phase = Phase.ARBITER
        return {"workers": state.workers, "current_phase": Phase.ARBITER}

    state.current_phase = Phase.WORKER_EXECUTE
    return {"workers": state.workers, "current_phase": Phase.WORKER_EXECUTE}


async def arbiter_node(state: FocusGroupState) -> dict:
    """Evaluate stuck workers and decide on escalation."""
    sid = state.session_id
    await event_bus.emit(sid, "system", "phase_change", {"phase": "arbiter"})
    
    arbiter = ArbiterAgent()
    expert_queries = list(state.expert_queries)  # Copy existing queries
    
    for worker in state.workers:
        if worker.stuck:
            logger.info(f"Arbiter evaluating stuck worker {worker.worker_id}")
            
            # Evaluate escalation
            should_escalate, issue_type, urgency = arbiter.should_escalate(worker)
            
            if should_escalate:
                # Build query for this worker
                query = arbiter.build_query(worker, issue_type, urgency)
                expert_queries.append(query.model_dump())
                
                await event_bus.emit(sid, worker.worker_id, "escalated", {
                    "issue_type": issue_type.value,
                    "urgency": urgency,
                    "question": query.question[:200],
                })
                logger.info(f"Worker {worker.worker_id} escalated: {issue_type.value} (urgency={urgency:.2f})")
            else:
                # Not severe enough to escalate, just reset stuck flag
                worker.stuck = False
                logger.info(f"Worker {worker.worker_id} not escalated, resuming")
    
    state.current_phase = Phase.HYBRID_SEARCH
    return {
        "workers": state.workers,
        "expert_queries": expert_queries,
        "current_phase": Phase.HYBRID_SEARCH,
    }


async def hybrid_search_node(state: FocusGroupState) -> dict:
    """Search Redis vector cache for existing answers."""
    from piedpiper.main import app_state

    if not state.expert_queries:
        logger.warning("No expert queries to search for")
        return {"current_phase": Phase.HUMAN_REVIEW}

    current_query = state.expert_queries[-1]
    question = current_query.get("question", "")

    if not question:
        logger.warning("Expert query has no question")
        return {"current_phase": Phase.HUMAN_REVIEW}

    logger.info(f"Searching cache for: {question[:100]}...")

    if app_state.knowledge_base:
        results, embedding_cost = await app_state.knowledge_base.search(question, top_k=3)

        updated_costs = state.costs.model_copy()
        updated_costs.spent_embeddings += embedding_cost

        if results:
            logger.info(
                f"Cache HIT! Found {len(results)} similar answers "
                f"(best score: {results[0].get('relevance_score', 0):.3f})"
            )
            current_query["cache_results"] = results
            current_query["cache_hit"] = True
            return {
                "expert_queries": state.expert_queries,
                "costs": updated_costs,
                "current_phase": Phase.HUMAN_REVIEW,
            }
        else:
            logger.info("Cache MISS - no similar answers found")
            current_query["cache_hit"] = False
    else:
        logger.warning("Knowledge base not initialized")
        current_query["cache_hit"] = False

    return {
        "expert_queries": state.expert_queries,
        "current_phase": Phase.HUMAN_REVIEW,
    }


async def human_review_node(state: FocusGroupState) -> dict:
    """Queue question for human review.
    
    For Phase 2 MVP, we auto-approve to keep the flow moving.
    Full implementation with async waiting will be in Phase 5.
    """
    sid = state.session_id
    await event_bus.emit(sid, "system", "phase_change", {"phase": "human_review"})
    
    if not state.expert_queries:
        logger.warning("No expert queries for human review")
        state.current_phase = Phase.EXPERT_ANSWER
        return {"current_phase": Phase.EXPERT_ANSWER}
    
    current_query = state.expert_queries[-1]
    
    # Emit event for UI notification
    await event_bus.emit(sid, "review", "pending", {
        "question": current_query.get("question", "")[:200] if isinstance(current_query, dict) else current_query.question[:200],
        "worker_id": current_query.get("worker_id", "") if isinstance(current_query, dict) else current_query.worker_id,
    })
    
    # For Phase 2 MVP: auto-approve after short delay to simulate review
    # In production, this would wait for actual human decision
    logger.info("Human review: auto-approving for MVP (no UI yet)")
    
    # Mark as reviewed
    if isinstance(current_query, dict):
        current_query["reviewed"] = True
        current_query["review_decision"] = "approved"
    
    state.current_phase = Phase.EXPERT_ANSWER
    return {
        "expert_queries": state.expert_queries,
        "current_phase": Phase.EXPERT_ANSWER,
    }


async def expert_answer_node(state: FocusGroupState) -> dict:
    """Query expert LLM for answer and store in cache."""
    from piedpiper.main import app_state
    from piedpiper.models.queries import ExpertQuery
    
    sid = state.session_id
    await event_bus.emit(sid, "system", "phase_change", {"phase": "expert_answer"})
    
    if not state.expert_queries:
        logger.warning("No expert queries to answer")
        state.current_phase = Phase.WORKER_EXECUTE
        return {"current_phase": Phase.WORKER_EXECUTE}
    
    # Get the latest query
    query_data = state.expert_queries[-1]
    query = ExpertQuery(**query_data) if isinstance(query_data, dict) else query_data
    
    logger.info(f"Expert answering query: {query.question[:100]}...")
    
    try:
        # Get expert answer
        expert = ExpertAgent()
        answer = await expert.answer(query)
        
        await event_bus.emit(sid, "expert", "answer_generated", {
            "answer_id": answer.answer_id,
            "confidence": answer.estimated_confidence,
            "answer_preview": answer.content[:200],
        })
        
        # Store in cache if knowledge base available
        if app_state.knowledge_base:
            try:
                doc_id, cost = await app_state.knowledge_base.store(
                    question=query.question,
                    answer=answer.content,
                    approved_by="expert_agent",
                    category=query.category,
                )
                logger.info(f"Cached expert answer as {doc_id}")
            except Exception as e:
                logger.warning(f"Failed to cache answer: {e}")
        
        # Apply answer to the worker who asked
        for worker in state.workers:
            if worker.worker_id == query.worker_id:
                agent = WorkerAgent(worker.config)
                agent.sandbox_id = worker.sandbox_id
                agent.set_emitter(event_bus.make_emitter(sid))
                
                updated_worker = await agent.apply_expert_answer(worker, answer.content)
                
                worker.action_history = updated_worker.action_history
                worker.conversation_history = updated_worker.conversation_history
                worker.stuck = False
                worker.completed = updated_worker.completed
                worker.output = updated_worker.output
                
                logger.info(f"Applied expert answer to worker {worker.worker_id}")
                break
        
        # Update query with answer
        query_data["answer"] = answer.model_dump()
        
    except Exception as e:
        logger.error(f"Expert answer failed: {e}")
        await event_bus.emit(sid, "expert", "error", {"error": str(e)[:300]})
        
        # Fallback: give generic guidance
        for worker in state.workers:
            if worker.worker_id == query.worker_id:
                worker.conversation_history.append({
                    "role": "user",
                    "content": "Expert guidance: Please check the documentation and error messages carefully. Try breaking down the problem into smaller steps.",
                })
                worker.stuck = False
                break
    
    state.current_phase = Phase.WORKER_EXECUTE
    return {
        "workers": state.workers,

async def browserbase_test_node(state: FocusGroupState) -> dict:
    """Validate worker output in browser.
    
    Runs Browserbase validation for each completed worker.
    Validates page loads, console errors, API endpoints, and user flows.
    """
    from piedpiper.infra.browserbase import BrowserbaseValidator
    from piedpiper.models.state import Phase
    
    sid = state.session_id
    await event_bus.emit(sid, "system", "phase_change", {"phase": "browserbase_test"})
    
    if not settings.browserbase_api_key:
        logger.warning("Browserbase API key not configured, skipping validation")
        state.current_phase = Phase.GENERATE_REPORT
        return {"current_phase": Phase.GENERATE_REPORT, "validations": []}
    
    validator = BrowserbaseValidator()
    validations = []
    all_passed = True
    
    for worker in state.workers:
        if not worker.completed or not worker.output:
            logger.info(f"Skipping validation for worker {worker.worker_id} - not completed")
            continue
        
        logger.info(f"Validating worker {worker.worker_id} output...")
        await event_bus.emit(sid, worker.worker_id, "validation_started", {})
        
        try:
            result = await validator.validate_worker_output(
                worker_id=worker.worker_id,
                output=worker.output,
            )
            validations.append(result)
            
            # Emit results
            await event_bus.emit(sid, worker.worker_id, "validation_complete", {
                "passed": result.passed,
                "score": result.score,
                "check_count": len(result.checks),
                "passed_checks": len([c for c in result.checks if c.passed]),
            })
            
            if not result.passed:
                all_passed = False
                logger.warning(
                    f"Worker {worker.worker_id} validation failed: "
                    f"score={result.score:.2f}, errors={result.errors[:2]}"
                )
            else:
                logger.info(f"Worker {worker.worker_id} validation passed: score={result.score:.2f}")
                
        except Exception as e:
            logger.error(f"Validation error for worker {worker.worker_id}: {e}")
            all_passed = False
            await event_bus.emit(sid, worker.worker_id, "validation_error", {
                "error": str(e)[:200],
            })
    
    state.current_phase = Phase.GENERATE_REPORT
    return {
        "current_phase": Phase.GENERATE_REPORT,
        "validations": validations,
    }


async def generate_report_node(state: FocusGroupState) -> dict:
    """Compile insights into final report."""
    sid = state.session_id
    await event_bus.emit(sid, "system", "phase_change", {"phase": "generate_report"})

    report = {
        "session_id": state.session_id,
        "task": state.task[:100] + "..." if len(state.task) > 100 else state.task,
        "workers": [
            {
                "id": w.worker_id,
                "completed": w.completed,
                "output": w.output,
            }
            for w in state.workers
        ],
    }
    state.current_phase = Phase.EXPERT_LEARN
    return {"report": report, "current_phase": Phase.EXPERT_LEARN}


async def expert_learn_node(state: FocusGroupState) -> dict:
    """Update expert agent based on effectiveness metrics."""
    state.current_phase = Phase.COMPLETED
    return {"current_phase": Phase.COMPLETED}
