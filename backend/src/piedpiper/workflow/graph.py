"""LangGraph workflow definition.

Owner: Person 1 (Core Workflow)

This is the main orchestration graph. It wires together all nodes
and defines state transitions per the plan:

INIT → ASSIGN_TASK → WORKER_EXECUTE → CHECK_PROGRESS
    ↓ (stuck)
    → ARBITER → HYBRID_SEARCH → {CACHE_HIT → WORKER_CONTINUE}
                                  ↓ (miss)
                                  → HUMAN_REVIEW → EXPERT_ANSWER → STORE_CACHE
    ↓ (success)
    → BROWSERBASE_TEST → {PASS → GENERATE_REPORT}
                        → {FAIL → WORKER_EXECUTE (retry)}
    ↓ (complete)
    → EXPERT_LEARN
"""

from langgraph.graph import END, StateGraph

from piedpiper.models.state import FocusGroupState
from piedpiper.workflow.nodes import (
    arbiter_node,
    assign_task_node,
    browserbase_test_node,
    check_progress_node,
    expert_answer_node,
    expert_learn_node,
    generate_report_node,
    human_review_node,
    hybrid_search_node,
    init_node,
    worker_execute_node,
)


def build_graph() -> StateGraph:
    """Build and compile the focus group workflow graph."""
    graph = StateGraph(FocusGroupState)

    # Add nodes
    graph.add_node("init", init_node)
    graph.add_node("assign_task", assign_task_node)
    graph.add_node("worker_execute", worker_execute_node)
    graph.add_node("check_progress", check_progress_node)
    graph.add_node("arbiter", arbiter_node)
    graph.add_node("hybrid_search", hybrid_search_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("expert_answer", expert_answer_node)
    graph.add_node("browserbase_test", browserbase_test_node)
    graph.add_node("generate_report", generate_report_node)
    graph.add_node("expert_learn", expert_learn_node)

    # Set entry point
    graph.set_entry_point("init")

    # Linear transitions
    graph.add_edge("init", "assign_task")
    graph.add_edge("assign_task", "worker_execute")
    graph.add_edge("worker_execute", "check_progress")

    # Conditional: check_progress → arbiter (stuck) or browserbase_test (success)
    graph.add_conditional_edges(
        "check_progress",
        _route_after_progress_check,
        {
            "stuck": "arbiter",
            "continue": "worker_execute",
            "success": "browserbase_test",
            "failed": "generate_report",
        },
    )

    # Arbiter → hybrid search
    graph.add_edge("arbiter", "hybrid_search")

    # Conditional: hybrid_search → cache hit goes back to worker, miss goes to human review
    graph.add_conditional_edges(
        "hybrid_search",
        _route_after_search,
        {
            "cache_hit": "worker_execute",
            "cache_miss": "human_review",
        },
    )

    # Conditional: human_review → approved goes to expert, rejected goes back to worker
    graph.add_conditional_edges(
        "human_review",
        _route_after_review,
        {
            "approved": "expert_answer",
            "rejected": "worker_execute",
            "modified": "worker_execute",
        },
    )

    # Expert answer → back to worker
    graph.add_edge("expert_answer", "worker_execute")

    # Conditional: browserbase_test → pass to report, fail to retry
    graph.add_conditional_edges(
        "browserbase_test",
        _route_after_test,
        {
            "pass": "generate_report",
            "fail": "worker_execute",
        },
    )

    # Report → learn → end
    graph.add_edge("generate_report", "expert_learn")
    graph.add_edge("expert_learn", END)

    return graph.compile()


def _route_after_progress_check(state: FocusGroupState) -> str:
    """Route based on worker progress."""
    # Check if all workers completed
    all_completed = all(worker.completed for worker in state.workers)
    if all_completed:
        return "success"
    
    # Check if any worker is stuck
    any_stuck = any(worker.stuck for worker in state.workers)
    if any_stuck:
        return "stuck"
    
    return "continue"


def _route_after_search(state: FocusGroupState) -> str:
    """Route based on cache hit/miss."""
    if not state.expert_queries:
        return "cache_miss"
    
    current_query = state.expert_queries[-1]
    if isinstance(current_query, dict) and current_query.get("cache_hit"):
        # Check if the cache result is good enough (relevance > 0.7)
        results = current_query.get("cache_results", [])
        if results and results[0].get("relevance_score", 0) > 0.7:
            return "cache_hit"
    
    return "cache_miss"


def _route_after_review(state: FocusGroupState) -> str:
    """Route based on human review decision."""
    # For now, assume approved (no human review implementation yet)
    return "approved"


def _route_after_test(state: FocusGroupState) -> str:
    """Route based on browserbase test result."""
    # For now, always pass (no browserbase implementation yet)
    return "pass"
