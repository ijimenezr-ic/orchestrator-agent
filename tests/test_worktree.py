"""Tests for the WorktreeManager."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from orchestrator.worktree import WorktreeManager


@pytest.fixture()
def mock_repo(tmp_path):
    """Return a mock git.Repo object rooted at tmp_path."""
    repo = MagicMock()
    repo.working_dir = str(tmp_path)
    repo.active_branch.name = "main"
    return repo


@pytest.fixture()
def manager(mock_repo, tmp_path):
    """Return a WorktreeManager with a mocked repo and temp base dir."""
    with patch("orchestrator.worktree.git.Repo", return_value=mock_repo):
        mgr = WorktreeManager(repo_path=str(tmp_path), base_dir=".worktrees-test")
    # Ensure the base_dir exists so tests can interact with it
    mgr.base_dir.mkdir(parents=True, exist_ok=True)
    return mgr


class TestCreateWorktree:
    def test_creates_directory_via_git(self, manager, mock_repo):
        worktree_path = manager.create_worktree("task-1", "feature/task-1")
        mock_repo.git.worktree.assert_called_once()
        assert "task-1" in worktree_path

    def test_returns_path_string(self, manager):
        result = manager.create_worktree("task-2", "feature/task-2")
        assert isinstance(result, str)

    def test_reuses_existing_worktree_without_error(self, manager, mock_repo):
        # Simulate worktree directory already existing
        existing = manager.base_dir / "task-3"
        existing.mkdir(parents=True, exist_ok=True)

        result = manager.create_worktree("task-3", "feature/task-3")
        # Should not call git worktree add again
        mock_repo.git.worktree.assert_not_called()
        assert "task-3" in result


class TestRemoveWorktree:
    def test_calls_git_worktree_remove(self, manager, mock_repo, tmp_path):
        # Create the worktree directory so remove doesn't bail out early
        wt_dir = manager.base_dir / "task-rm"
        wt_dir.mkdir(parents=True, exist_ok=True)

        manager.remove_worktree("task-rm")
        mock_repo.git.worktree.assert_called_once()

    def test_logs_warning_if_worktree_not_found(self, manager, caplog):
        import logging
        with caplog.at_level(logging.WARNING, logger="orchestrator.worktree"):
            manager.remove_worktree("nonexistent-task")
        assert "does not exist" in caplog.text

    def test_prunes_on_git_command_error(self, manager, mock_repo, tmp_path):
        import git as gitmodule
        wt_dir = manager.base_dir / "task-fail"
        wt_dir.mkdir(parents=True, exist_ok=True)

        # First worktree call raises, prune should be called afterwards
        mock_repo.git.worktree.side_effect = [gitmodule.GitCommandError("worktree", "remove"), None]

        manager.remove_worktree("task-fail", force=True)

        # Second call is the prune
        assert mock_repo.git.worktree.call_count == 2


class TestListWorktrees:
    def test_parses_porcelain_output(self, manager, mock_repo):
        porcelain = (
            "worktree /home/user/project\n"
            "HEAD abc123\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /home/user/.worktrees/task-1\n"
            "HEAD def456\n"
            "branch refs/heads/feature/task-1\n"
        )
        mock_repo.git.worktree.return_value = porcelain

        result = manager.list_worktrees()
        assert len(result) == 2
        assert result[0]["path"] == "/home/user/project"
        assert result[1]["branch"] == "refs/heads/feature/task-1"

    def test_returns_empty_list_for_empty_output(self, manager, mock_repo):
        mock_repo.git.worktree.return_value = ""
        result = manager.list_worktrees()
        assert result == []


class TestMergeBranch:
    def test_checks_out_target_and_merges(self, manager, mock_repo):
        manager.merge_branch("feature/task-1", target="main")
        mock_repo.git.checkout.assert_called_with("main")
        mock_repo.git.merge.assert_called_once()

    def test_restores_original_branch_after_merge(self, manager, mock_repo):
        mock_repo.active_branch.name = "develop"
        manager.merge_branch("feature/task-1", target="main")
        # Last checkout should be back to original branch
        calls = [c.args[0] for c in mock_repo.git.checkout.call_args_list]
        assert "develop" in calls
