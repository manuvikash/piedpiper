"""Graph node implementations.

Owner: Person 1 (Core Workflow)

Each node receives FocusGroupState, performs its work, and returns
updated state. Nodes call into agents/ and infra/ modules but don't
implement agent or infrastructure logic themselves.
"""

from __future__ import annotations

from uuid import uuid4

from piedpiper.models.state import (
    DEFAULT_WORKERS,
    FocusGroupState,
    Phase,
    WorkerExpertise,
    WorkerState,
)
from piedpiper.agents.worker import WorkerAgent
from piedpiper.config import settings


async def init_node(state: FocusGroupState) -> dict:
    """Initialize workers and reset state."""
    # Generate session ID if not set
    if not state.session_id:
        state.session_id = str(uuid4())
    
    # Create WorkerState for each DEFAULT_WORKERS config
    workers = []
    for config in DEFAULT_WORKERS:
        worker_state = WorkerState(
            worker_id=config.id,
            config=config,
        )
        
        # Initialize Daytona sandbox for this worker
        agent = WorkerAgent(config)
        sandbox_id = await agent.initialize_sandbox()
        worker_state.sandbox_id = sandbox_id
        
        workers.append(worker_state)
    
    state.workers = workers
    state.current_phase = Phase.ASSIGN_TASK
    
    return {"workers": workers, "current_phase": Phase.ASSIGN_TASK}


async def assign_task_node(state: FocusGroupState) -> dict:
    """Assign the full task to all workers."""
    # Give the same task to all 3 workers
    for worker in state.workers:
        worker.subtask = state.task

    state.current_phase = Phase.WORKER_EXECUTE
    
    return {"workers": state.workers, "current_phase": Phase.WORKER_EXECUTE}


async def worker_execute_node(state: FocusGroupState) -> dict:
    """Run worker code in Daytona sandbox.

    Delegates to agents.worker.execute()
    """
    # For now, just mark all workers as completed (stub implementation)
    # TODO: actually call WorkerAgent.execute_subtask() for each worker
    for worker in state.workers:
        if not worker.completed:
            # Placeholder: mark as completed for now
            worker.completed = True
            worker.output = {
                "status": "completed",
                "result": f"Stub result for {worker.worker_id}",
            }
    
    state.current_phase = Phase.CHECK_PROGRESS
    return {"workers": state.workers, "current_phase": Phase.CHECK_PROGRESS}


async def check_progress_node(state: FocusGroupState) -> dict:
    """Check if workers are making progress.

    Updates worker.stuck and worker.minutes_without_progress.
    """
    # Check if all workers are completed
    all_completed = all(worker.completed for worker in state.workers)
    
    if all_completed:
        # All done, move to browserbase test
        state.current_phase = Phase.BROWSERBASE_TEST
        return {"workers": state.workers, "current_phase": Phase.BROWSERBASE_TEST}
    
    # Check for stuck workers
    any_stuck = any(worker.stuck for worker in state.workers)
    
    if any_stuck:
        state.current_phase = Phase.ARBITER
        return {"workers": state.workers, "current_phase": Phase.ARBITER}
    
    # Workers still executing
    state.current_phase = Phase.WORKER_EXECUTE
    return {"workers": state.workers, "current_phase": Phase.WORKER_EXECUTE}


async def arbiter_node(state: FocusGroupState) -> dict:
    """Evaluate stuck workers and decide on escalation.

    Delegates to agents.arbiter.evaluate()
    """
    # Stub: mark stuck workers as unstuck and continue
    for worker in state.workers:
        if worker.stuck:
            worker.stuck = False
    
    state.current_phase = Phase.HYBRID_SEARCH
    return {"workers": state.workers, "current_phase": Phase.HYBRID_SEARCH}


async def hybrid_search_node(state: FocusGroupState) -> dict:
    """Search Redis vector cache for existing answers.

    Delegates to infra.search.hybrid_search()
    """
    # Stub: skip cache, go straight to human review
    state.current_phase = Phase.HUMAN_REVIEW
    return {"current_phase": Phase.HUMAN_REVIEW}


async def human_review_node(state: FocusGroupState) -> dict:
    """Queue question for human review and wait for decision.

    Delegates to review.queue.submit()
    This node will pause the workflow until human responds.
    """
    # Stub: auto-approve and continue
    state.current_phase = Phase.EXPERT_ANSWER
    return {"current_phase": Phase.EXPERT_ANSWER}


async def expert_answer_node(state: FocusGroupState) -> dict:
    """Query expert LLM for answer.

    Delegates to agents.expert.answer()
    """
    # Stub: add a placeholder answer to first stuck worker
    for worker in state.workers:
        if not worker.completed:
            worker.conversation_history.append({
                "role": "expert",
                "content": "Stub expert answer: try checking the documentation."
            })
            break
    
    state.current_phase = Phase.WORKER_EXECUTE
    return {"workers": state.workers, "current_phase": Phase.WORKER_EXECUTE}


async def browserbase_test_node(state: FocusGroupState) -> dict:
    """Validate worker output in browser.

    Delegates to infra.browserbase.validate()
    """
    # Stub: auto-pass
    state.current_phase = Phase.GENERATE_REPORT
    return {"current_phase": Phase.GENERATE_REPORT}


async def generate_report_node(state: FocusGroupState) -> dict:
    """Compile insights into final report."""
    # Stub: create simple report
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
    """Update expert agent based on effectiveness metrics.

    Delegates to agents.learning.evaluate_and_learn()
    """
    # Stub: mark as completed
    state.current_phase = Phase.COMPLETED
    return {"current_phase": Phase.COMPLETED}
