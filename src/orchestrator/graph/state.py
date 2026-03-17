"""LangGraph state definitions for the orchestrator workflow."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from typing_extensions import TypedDict

from orchestrator.models import AgentResult, TaskDAG


class OrchestratorState(TypedDict, total=False):
    """Shared mutable state passed between LangGraph nodes.

    Attributes:
        task_description: The original high-level task from the user.
        dag: The decomposed :class:`~orchestrator.models.TaskDAG`.
        results: Accumulated :class:`~orchestrator.models.AgentResult` list.
        completed_task_ids: Set of task IDs that have reached a terminal state.
        project: Engram project name used for memory scoping.
        error: Optional error message from the latest node.
    """

    task_description: str
    dag: Optional[TaskDAG]
    results: List[AgentResult]
    completed_task_ids: Set[str]
    project: str
    error: Optional[str]
