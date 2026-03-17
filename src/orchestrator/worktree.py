"""Git Worktree Manager.

Provides helpers to create, list, remove, and merge git worktrees so that
each sub-agent works in a fully isolated branch without touching the main
working directory.

Requires GitPython (``pip install gitpython``).
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

import git

from orchestrator.config import WORKTREE_BASE_DIR

logger = logging.getLogger(__name__)


class WorktreeManager:
    """Manages git worktrees for sub-agent task isolation."""

    def __init__(self, repo_path: str = ".", base_dir: str = WORKTREE_BASE_DIR) -> None:
        """Initialise the manager.

        Args:
            repo_path: Path to the main git repository root.
            base_dir: Directory where worktrees will be created (relative to repo_path).
        """
        self.repo = git.Repo(repo_path, search_parent_directories=True)
        self.repo_root = Path(self.repo.working_dir)
        self.base_dir = (self.repo_root / base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Worktree lifecycle
    # ------------------------------------------------------------------

    def create_worktree(self, task_id: str, branch_name: str) -> str:
        """Create a new git worktree for the given task.

        Args:
            task_id: Unique task identifier used to name the worktree directory.
            branch_name: Name of the new (or existing) branch, e.g. ``feature/task-1-code``.

        Returns:
            Absolute path to the created worktree directory.

        Raises:
            git.GitCommandError: If the worktree could not be created.
        """
        worktree_path = self.base_dir / task_id
        if worktree_path.exists():
            logger.warning("Worktree %s already exists, reusing.", worktree_path)
            return str(worktree_path)

        logger.info("Creating worktree %s → branch %s", worktree_path, branch_name)
        self.repo.git.worktree("add", "-b", branch_name, str(worktree_path))
        return str(worktree_path)

    def remove_worktree(self, task_id: str, force: bool = True) -> None:
        """Remove the worktree for the given task.

        Args:
            task_id: Task identifier matching the directory created by :meth:`create_worktree`.
            force: Pass ``--force`` to ``git worktree remove`` (default ``True``).
        """
        worktree_path = self.base_dir / task_id
        if not worktree_path.exists():
            logger.warning("Worktree %s does not exist, nothing to remove.", worktree_path)
            return

        args = ["remove"]
        if force:
            args.append("--force")
        args.append(str(worktree_path))

        logger.info("Removing worktree %s", worktree_path)
        try:
            self.repo.git.worktree(*args)
        except git.GitCommandError as exc:
            logger.error("git worktree remove failed: %s — trying manual cleanup", exc)
            shutil.rmtree(worktree_path, ignore_errors=True)
            self.repo.git.worktree("prune")

    def list_worktrees(self) -> List[Dict[str, str]]:
        """Return a list of active worktrees.

        Returns:
            List of dicts with keys ``path``, ``branch``, and ``commit``.
        """
        raw: str = self.repo.git.worktree("list", "--porcelain")
        worktrees: List[Dict[str, str]] = []
        current: Dict[str, str] = {}
        for line in raw.splitlines():
            if line.startswith("worktree "):
                if current:
                    worktrees.append(current)
                current = {"path": line.split(" ", 1)[1]}
            elif line.startswith("HEAD "):
                current["commit"] = line.split(" ", 1)[1]
            elif line.startswith("branch "):
                current["branch"] = line.split(" ", 1)[1]
        if current:
            worktrees.append(current)
        return worktrees

    # ------------------------------------------------------------------
    # Merge helpers
    # ------------------------------------------------------------------

    def merge_branch(self, source_branch: str, target: str = "main") -> None:
        """Merge *source_branch* into *target* using a fast-forward or merge commit.

        Args:
            source_branch: Branch to merge from (e.g. ``feature/task-1-code``).
            target: Branch to merge into (default ``main``).

        Raises:
            git.GitCommandError: On merge conflict or other git errors.
        """
        logger.info("Merging %s → %s", source_branch, target)
        original_branch = self.repo.active_branch.name
        try:
            self.repo.git.checkout(target)
            self.repo.git.merge(source_branch, "--no-ff", "-m", f"Merge {source_branch} into {target}")
        finally:
            self.repo.git.checkout(original_branch)

    def cleanup_all(self) -> None:
        """Remove every worktree created under :attr:`base_dir`."""
        for item in self.base_dir.iterdir():
            if item.is_dir():
                task_id = item.name
                logger.info("Cleanup: removing worktree %s", task_id)
                self.remove_worktree(task_id)
