"""DAG Executor using LangGraph.

Builds and runs the orchestration state graph.  In MVP mode execution is
sequential; the parallel executor (Phase 7) is scaffolded here too.
"""

from __future__ import annotations

import logging
from typing import List

from orchestrator.graph.builder import build_orchestrator_graph
from orchestrator.models import AgentResult, TaskDAG

logger = logging.getLogger(__name__)


class DAGExecutor:
    """Executes a :class:`~orchestrator.models.TaskDAG` using LangGraph."""

    def __init__(self, project: str = "orchestrator") -> None:
        self._project = project
        self._graph = build_orchestrator_graph()

    def run(self, dag: TaskDAG) -> List[AgentResult]:
        """Execute all subtasks in dependency order and collect results.

        Args:
            dag: The task DAG to execute.

        Returns:
            List of :class:`~orchestrator.models.AgentResult` for each subtask.
        """
        logger.info("Starting DAG execution for: %s", dag.original_task)

        initial_state = {
            "task_description": dag.original_task,
            "dag": dag,
            "results": [],
            "completed_task_ids": set(),
            "project": self._project,
            "error": None,
        }

        final_state = self._graph.invoke(initial_state)
        results: List[AgentResult] = final_state.get("results", [])
        logger.info("DAG execution finished. %d results collected.", len(results))
        return results
