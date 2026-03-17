"""LangGraph graph builder for the orchestrator workflow."""

from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from orchestrator.graph.nodes import (
    classify_agents,
    collect_results,
    create_worktrees,
    decompose_task,
    execute_subtask,
    merge_results,
    save_memory,
)
from orchestrator.graph.state import OrchestratorState
from orchestrator.models import TaskStatus

logger = logging.getLogger(__name__)


def _should_continue_executing(state: OrchestratorState) -> str:
    """Routing function: keep executing subtasks until the DAG is complete.

    Args:
        state: Current orchestrator state.

    Returns:
        ``"execute"`` if more tasks remain, ``"collect"`` when done.
    """
    dag = state.get("dag")
    if dag is None or dag.is_complete():
        return "collect"
    completed_ids: set[str] = state.get("completed_task_ids", set())
    ready = dag.get_ready_tasks(completed_ids)
    if not ready:
        # No ready tasks but DAG is not complete → some tasks are blocked by failures
        return "collect"
    return "execute"


def build_orchestrator_graph() -> StateGraph:
    """Assemble and compile the orchestrator LangGraph.

    The graph follows this flow (MVP — sequential execution)::

        decompose_task
            ↓
        classify_agents
            ↓
        create_worktrees
            ↓
        execute_subtask ←─────────────────┐
            ↓                             │
        [should_continue?] ──"execute"────┘
            │
          "collect"
            ↓
        collect_results
            ↓
        merge_results
            ↓
        save_memory
            ↓
           END

    Returns:
        A compiled :class:`langgraph.graph.StateGraph` ready to invoke.
    """
    graph = StateGraph(OrchestratorState)

    # Add nodes
    graph.add_node("decompose", decompose_task)
    graph.add_node("classify", classify_agents)
    graph.add_node("create_worktrees", create_worktrees)
    graph.add_node("execute", execute_subtask)
    graph.add_node("collect", collect_results)
    graph.add_node("merge", merge_results)
    graph.add_node("save_memory", save_memory)

    # Set entry point
    graph.set_entry_point("decompose")

    # Linear edges
    graph.add_edge("decompose", "classify")
    graph.add_edge("classify", "create_worktrees")
    graph.add_edge("create_worktrees", "execute")

    # Conditional loop for task execution
    graph.add_conditional_edges(
        "execute",
        _should_continue_executing,
        {"execute": "execute", "collect": "collect"},
    )

    # Final linear chain
    graph.add_edge("collect", "merge")
    graph.add_edge("merge", "save_memory")
    graph.add_edge("save_memory", END)

    return graph.compile()
