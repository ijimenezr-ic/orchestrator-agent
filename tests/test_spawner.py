"""Tests for SubAgentSpawner file-writing and committing behaviour."""

from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock, patch

import git
import pytest

from orchestrator.models import AgentType, SubTask, TaskStatus
from orchestrator.spawner import SubAgentSpawner


@pytest.fixture()
def task(tmp_path):
    """Return a minimal SubTask with a worktree_path pointing to tmp_path."""
    return SubTask(
        id="task-1-test",
        title="Create LoginForm component",
        description="Implement the React login form",
        type=AgentType.CODE_FRONTEND,
        branch_name="feature/task-1-test",
        worktree_path=str(tmp_path),
    )


@pytest.fixture()
def spawner():
    """Return a SubAgentSpawner with mocked LLM client and memory."""
    memory = MagicMock()
    memory.search.return_value = []
    memory.save_observation.return_value = {}
    with patch("orchestrator.spawner.create_client", return_value=MagicMock()):
        s = SubAgentSpawner(memory=memory)
    return s


# ---------------------------------------------------------------------------
# _parse_result tests
# ---------------------------------------------------------------------------

class TestParseResult:
    def test_parses_new_files_format(self, spawner, task):
        payload = {
            "summary": "Created LoginForm",
            "files": [
                {"path": "src/LoginForm.tsx", "content": "export const LoginForm = () => null;"},
            ],
            "status": "completed",
            "errors": None,
        }
        result, files_data = spawner._parse_result(task, json.dumps(payload))

        assert result.status == TaskStatus.COMPLETED
        assert result.summary == "Created LoginForm"
        assert result.files_changed == ["src/LoginForm.tsx"]
        assert len(files_data) == 1
        assert files_data[0]["path"] == "src/LoginForm.tsx"
        assert "LoginForm" in files_data[0]["content"]

    def test_falls_back_to_old_files_changed_format(self, spawner, task):
        payload = {
            "summary": "Created LoginForm",
            "files_changed": ["src/LoginForm.tsx"],
            "status": "completed",
            "errors": None,
        }
        result, files_data = spawner._parse_result(task, json.dumps(payload))

        assert result.files_changed == ["src/LoginForm.tsx"]
        assert files_data == []

    def test_handles_missing_json(self, spawner, task):
        result, files_data = spawner._parse_result(task, "No JSON here at all")

        assert result.status == TaskStatus.COMPLETED
        assert files_data == []

    def test_handles_invalid_json(self, spawner, task):
        result, files_data = spawner._parse_result(task, "{not valid json}")

        assert result.status == TaskStatus.COMPLETED
        assert files_data == []

    def test_strips_markdown_fences(self, spawner, task):
        payload = json.dumps({
            "summary": "Done",
            "files": [],
            "status": "completed",
            "errors": None,
        })
        text = f"```json\n{payload}\n```"
        result, files_data = spawner._parse_result(task, text)

        assert result.status == TaskStatus.COMPLETED

    def test_failed_status_is_propagated(self, spawner, task):
        payload = {
            "summary": "Could not build",
            "files": [],
            "status": "failed",
            "errors": "Build error",
        }
        result, _ = spawner._parse_result(task, json.dumps(payload))

        assert result.status == TaskStatus.FAILED
        assert result.errors == "Build error"

    def test_ignores_file_entries_without_content(self, spawner, task):
        payload = {
            "summary": "Partial",
            "files": [
                {"path": "src/Foo.tsx"},  # missing "content"
                {"path": "src/Bar.tsx", "content": "export {}"},
            ],
            "status": "completed",
            "errors": None,
        }
        result, files_data = spawner._parse_result(task, json.dumps(payload))

        assert len(files_data) == 1
        assert files_data[0]["path"] == "src/Bar.tsx"


# ---------------------------------------------------------------------------
# _write_and_commit_files tests
# ---------------------------------------------------------------------------

class TestWriteAndCommitFiles:
    def test_writes_files_to_worktree(self, spawner, task, tmp_path):
        files_data = [
            {"path": "src/LoginForm.tsx", "content": "export const LoginForm = () => null;"},
            {"path": "src/LoginForm.test.tsx", "content": "import { LoginForm } from './LoginForm';"},
        ]
        mock_repo = MagicMock()
        with patch("orchestrator.spawner.git.Repo", return_value=mock_repo):
            spawner._write_and_commit_files(task, files_data)

        assert (tmp_path / "src" / "LoginForm.tsx").exists()
        assert (tmp_path / "src" / "LoginForm.test.tsx").exists()
        assert "LoginForm" in (tmp_path / "src" / "LoginForm.tsx").read_text()

    def test_creates_nested_directories(self, spawner, task, tmp_path):
        files_data = [
            {"path": "src/components/auth/LoginForm.tsx", "content": "export {}"},
        ]
        mock_repo = MagicMock()
        with patch("orchestrator.spawner.git.Repo", return_value=mock_repo):
            spawner._write_and_commit_files(task, files_data)

        assert (tmp_path / "src" / "components" / "auth" / "LoginForm.tsx").exists()

    def test_commits_files_via_git(self, spawner, task, tmp_path):
        files_data = [{"path": "src/LoginForm.tsx", "content": "export {}"}]
        mock_repo = MagicMock()
        with patch("orchestrator.spawner.git.Repo", return_value=mock_repo):
            spawner._write_and_commit_files(task, files_data)

        mock_repo.git.add.assert_called_once_with(".")
        mock_repo.git.commit.assert_called_once()
        commit_msg = mock_repo.git.commit.call_args[0][1]
        assert task.id in commit_msg

    def test_skips_commit_on_empty_files(self, spawner, task, tmp_path):
        mock_repo = MagicMock()
        with patch("orchestrator.spawner.git.Repo", return_value=mock_repo):
            spawner._write_and_commit_files(task, [])

        mock_repo.git.add.assert_not_called()
        mock_repo.git.commit.assert_not_called()

    def test_skips_files_with_empty_path(self, spawner, task, tmp_path):
        files_data = [{"path": "", "content": "export {}"}]
        mock_repo = MagicMock()
        with patch("orchestrator.spawner.git.Repo", return_value=mock_repo):
            spawner._write_and_commit_files(task, files_data)

        mock_repo.git.add.assert_not_called()

    def test_strips_leading_slash_from_path(self, spawner, task, tmp_path):
        files_data = [{"path": "/src/LoginForm.tsx", "content": "export {}"}]
        mock_repo = MagicMock()
        with patch("orchestrator.spawner.git.Repo", return_value=mock_repo):
            spawner._write_and_commit_files(task, files_data)

        assert (tmp_path / "src" / "LoginForm.tsx").exists()

    def test_logs_warning_on_git_error(self, spawner, task, tmp_path, caplog):
        files_data = [{"path": "src/LoginForm.tsx", "content": "export {}"}]
        mock_repo = MagicMock()
        mock_repo.git.commit.side_effect = git.GitCommandError("commit", "nothing to commit")

        with patch("orchestrator.spawner.git.Repo", return_value=mock_repo):
            with caplog.at_level(logging.WARNING, logger="orchestrator.spawner"):
                spawner._write_and_commit_files(task, files_data)

        assert "Could not commit" in caplog.text


# ---------------------------------------------------------------------------
# Integration: run() writes files when LLM returns them
# ---------------------------------------------------------------------------

class TestRunWritesFiles:
    def test_run_writes_files_to_worktree(self, task, tmp_path):
        llm_response = json.dumps({
            "summary": "Created LoginForm component",
            "files": [
                {"path": "src/LoginForm.tsx", "content": "export const LoginForm = () => null;"},
            ],
            "status": "completed",
            "errors": None,
        })

        memory = MagicMock()
        memory.search.return_value = []
        memory.save_observation.return_value = {}

        mock_repo = MagicMock()

        with patch("orchestrator.spawner.create_client", return_value=MagicMock()), \
             patch("orchestrator.spawner.chat", return_value=llm_response), \
             patch("orchestrator.spawner.git.Repo", return_value=mock_repo):
            spawner = SubAgentSpawner(memory=memory)
            result = spawner.run(task)

        assert result.status == TaskStatus.COMPLETED
        assert (tmp_path / "src" / "LoginForm.tsx").exists()
        assert result.files_changed == ["src/LoginForm.tsx"]
        mock_repo.git.commit.assert_called_once()

    def test_run_returns_failed_result_on_exception(self, task):
        memory = MagicMock()
        memory.search.return_value = []
        memory.save_observation.return_value = {}

        with patch("orchestrator.spawner.create_client", return_value=MagicMock()), \
             patch("orchestrator.spawner.chat", side_effect=RuntimeError("API down")):
            spawner = SubAgentSpawner(memory=memory)
            result = spawner.run(task)

        assert result.status == TaskStatus.FAILED
        assert "API down" in result.errors
