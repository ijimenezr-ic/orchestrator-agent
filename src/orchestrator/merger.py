"""Merge Coordinator.

Coordinates the merge of all completed sub-agent worktrees back into the main
branch after all subtasks are done.
"""

from __future__ import annotations

import logging
from typing import List

from orchestrator.models import AgentResult, TaskStatus
from orchestrator.worktree import WorktreeManager

logger = logging.getLogger(__name__)


class MergeCoordinator:
    """Merges sub-agent worktree branches into the target branch."""

    def __init__(self, repo_path: str = ".", target_branch: str = "main") -> None:
        self._worktree_mgr = WorktreeManager(repo_path=repo_path)
        self._target = target_branch

    def merge_all(self, results: List[AgentResult]) -> List[str]:
        """Merge branches from all completed results into the target branch.

        Args:
            results: Agent results produced by the DAG executor.

        Returns:
            List of branch names that were successfully merged.
        """
        merged: List[str] = []
        for result in results:
            if result.status != TaskStatus.COMPLETED:
                logger.warning("Skipping merge for %s (status=%s)", result.task_id, result.status)
                continue
            if not result.branch:
                logger.warning("No branch recorded for task %s, skipping merge.", result.task_id)
                continue
            try:
                self._worktree_mgr.merge_branch(result.branch, target=self._target)
                merged.append(result.branch)
                logger.info("Merged %s → %s", result.branch, self._target)
            except Exception as exc:
                logger.error("Failed to merge %s: %s", result.branch, exc)
        return merged

    def cleanup(self, results: List[AgentResult]) -> None:
        """Remove worktrees for all provided results.

        Args:
            results: Agent results whose worktrees should be cleaned up.
        """
        for result in results:
            try:
                self._worktree_mgr.remove_worktree(result.task_id)
            except Exception as exc:
                logger.warning("Could not remove worktree for %s: %s", result.task_id, exc)
