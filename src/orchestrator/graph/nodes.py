"""LangGraph node functions for the orchestrator workflow.

Each function here maps to a node in the orchestrator state graph.  Nodes
receive the current :class:`~orchestrator.graph.state.OrchestratorState` and
return a (possibly partial) dict of updated state keys.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from orchestrator.decomposer import TaskDecomposer
from orchestrator.errors import MaxRetriesExceededError, make_failed_result, with_retry
from orchestrator.graph.state import OrchestratorState
from orchestrator.memory import EngramClient
from orchestrator.models import AgentResult, SubTask, TaskStatus
from orchestrator.reporter import CompactReporter
from orchestrator.spawner import SubAgentSpawner
from orchestrator.worktree import WorktreeManager

logger = logging.getLogger(__name__)

_decomposer = TaskDecomposer()
_reporter = CompactReporter()


# ---------------------------------------------------------------------------
# Node: decompose_task
# ---------------------------------------------------------------------------

def decompose_task(state: OrchestratorState) -> Dict[str, Any]:
    """Send the task description to the LLM and build the TaskDAG.

    Args:
        state: Current orchestrator state.

    Returns:
        Partial state update with ``dag`` populated.
    """
    try:
        dag = _decomposer.decompose(state["task_description"])
        logger.info("Decomposed into %d subtasks.", len(dag.subtasks))
        return {"dag": dag, "error": None}
    except Exception as exc:
        logger.error("decompose_task failed: %s", exc)
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Node: classify_agents
# ---------------------------------------------------------------------------

def classify_agents(state: OrchestratorState) -> Dict[str, Any]:
    """Verify and (re-)assign agent types using the classifier.

    The decomposer already sets types; this node acts as a validation/override
    pass.  It is a no-op in the MVP but is kept for future extension.

    Args:
        state: Current orchestrator state.

    Returns:
        Partial state update (unchanged in MVP).
    """
    from orchestrator.classifier import AgentClassifier  # local to avoid circular import

    classifier = AgentClassifier(use_llm_fallback=False)
    dag = state.get("dag")
    if dag is None:
        return {}

    for task in dag.subtasks:
        keyword_type = classifier.classify(task.title, task.description)
        if keyword_type != task.type:
            logger.debug(
                "Classifier override for %s: %s → %s", task.id, task.type, keyword_type
            )
            task.type = keyword_type

    return {"dag": dag}


# ---------------------------------------------------------------------------
# Node: create_worktrees
# ---------------------------------------------------------------------------

def create_worktrees(state: OrchestratorState) -> Dict[str, Any]:
    """Create a git worktree for every subtask in the DAG.

    Args:
        state: Current orchestrator state.

    Returns:
        Partial state update with worktree paths set on each subtask.
    """
    dag = state.get("dag")
    if dag is None:
        return {}

    try:
        mgr = WorktreeManager()
    except Exception as exc:
        logger.warning("Could not initialise WorktreeManager: %s — skipping worktree creation", exc)
        return {}

    for task in dag.subtasks:
        if not task.branch_name:
            task.branch_name = f"feature/{task.id}"
        try:
            path = mgr.create_worktree(task.id, task.branch_name)
            task.worktree_path = path
            logger.info("Created worktree for %s at %s", task.id, path)
        except Exception as exc:
            logger.warning("Could not create worktree for %s: %s", task.id, exc)

    return {"dag": dag}


# ---------------------------------------------------------------------------
# Node: execute_subtask
# ---------------------------------------------------------------------------

def execute_subtask(state: OrchestratorState) -> Dict[str, Any]:
    """Execute the next ready subtask (sequential MVP implementation).

    Picks the first subtask whose dependencies are all satisfied and runs it.

    Args:
        state: Current orchestrator state.

    Returns:
        Partial state update with the new result appended and task IDs updated.
    """
    dag = state.get("dag")
    if dag is None:
        return {}

    completed_ids: set[str] = state.get("completed_task_ids", set())
    results: list[AgentResult] = list(state.get("results", []))
    project: str = state.get("project", "orchestrator")

    ready_tasks = dag.get_ready_tasks(completed_ids)
    if not ready_tasks:
        logger.info("No ready tasks — execution complete or blocked.")
        return {}

    task: SubTask = ready_tasks[0]
    task.status = TaskStatus.RUNNING

    memory = EngramClient()
    prior = memory.search(task.title)
    prior_context = "\n".join(r.get("content", "") for r in prior[:3]) if prior else ""

    spawner = SubAgentSpawner(memory=memory, project=project)

    try:
        result = with_retry(lambda: spawner.run(task, prior_context), task=task)
        task.status = result.status
    except MaxRetriesExceededError as exc:
        result = make_failed_result(task, str(exc))
        task.status = TaskStatus.FAILED

    results.append(result)
    completed_ids = set(completed_ids)  # copy to avoid mutating the set in state
    completed_ids.add(task.id)

    logger.info("Task %s finished with status=%s", task.id, result.status)
    return {"results": results, "completed_task_ids": completed_ids, "dag": dag}


# ---------------------------------------------------------------------------
# Node: collect_results
# ---------------------------------------------------------------------------

def collect_results(state: OrchestratorState) -> Dict[str, Any]:
    """Log and return a no-op state update — results are already in state.

    Args:
        state: Current orchestrator state.

    Returns:
        Empty dict (no state change needed).
    """
    results = state.get("results", [])
    completed = sum(1 for r in results if r.status == TaskStatus.COMPLETED)
    failed = sum(1 for r in results if r.status == TaskStatus.FAILED)
    logger.info("Results collected: %d completed, %d failed.", completed, failed)
    return {}


# ---------------------------------------------------------------------------
# Node: merge_results
# ---------------------------------------------------------------------------

def merge_results(state: OrchestratorState) -> Dict[str, Any]:
    """Merge all completed worktree branches into main.

    Args:
        state: Current orchestrator state.

    Returns:
        Empty dict (merging is a side-effect, no state key update required).
    """
    from orchestrator.merger import MergeCoordinator  # local to avoid circular import

    results = state.get("results", [])
    try:
        coordinator = MergeCoordinator()
        merged = coordinator.merge_all(results)
        logger.info("Merged branches: %s", merged)
        coordinator.cleanup(results)
    except Exception as exc:
        logger.warning("Merge phase raised: %s", exc)
    return {}


# ---------------------------------------------------------------------------
# Node: save_memory
# ---------------------------------------------------------------------------

def save_memory(state: OrchestratorState) -> Dict[str, Any]:
    """Save a session summary to Engram for future reference.

    Args:
        state: Current orchestrator state.

    Returns:
        Empty dict (side-effect only).
    """
    results = state.get("results", [])
    project = state.get("project", "orchestrator")
    task_description = state.get("task_description", "")

    summaries = "\n".join(
        f"- [{r.task_id}] {r.status.value}: {r.summary}" for r in results
    )
    content = (
        f"## Goal\n{task_description}\n\n"
        f"## Accomplished\n{summaries}\n\n"
        f"## Next Steps\nReview merged branches and run full test suite."
    )

    memory = EngramClient()
    memory.save_observation(
        title=f"Session summary: {task_description[:60]}",
        type="session",
        content=content,
        topic_key=f"session/{task_description[:30].replace(' ', '-').lower()}",
        project=project,
    )
    logger.info("Session summary saved to Engram.")
    return {}
