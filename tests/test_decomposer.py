"""Tests for the TaskDecomposer."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from orchestrator.decomposer import TaskDecomposer
from orchestrator.models import AgentType, TaskDAG


MOCK_LLM_RESPONSE = """{
  "subtasks": [
    {
      "id": "task-1-login-code",
      "title": "Implement login page",
      "description": "Create a React login form component with email and password fields.",
      "type": "code-frontend",
      "depends_on": []
    },
    {
      "id": "task-2-login-test",
      "title": "Tests for login page",
      "description": "Write pytest tests for the login component.",
      "type": "test-agent",
      "depends_on": ["task-1-login-code"]
    }
  ]
}"""


@pytest.fixture()
def mock_llm_client():
    """Return a mock OpenAI client (GitHub Models) that returns a fixed JSON response."""
    mock_choice = MagicMock()
    mock_choice.message.content = MOCK_LLM_RESPONSE

    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_completion
    return mock_client


@pytest.fixture()
def decomposer(mock_llm_client):
    """Return a TaskDecomposer with a mocked LLM client."""
    d = TaskDecomposer.__new__(TaskDecomposer)
    d._client = mock_llm_client
    return d


class TestTaskDecomposer:
    def test_decompose_returns_task_dag(self, decomposer):
        dag = decomposer.decompose("Add login page with tests")
        assert isinstance(dag, TaskDAG)

    def test_dag_contains_expected_number_of_subtasks(self, decomposer):
        dag = decomposer.decompose("Add login page with tests")
        assert len(dag.subtasks) == 2

    def test_subtask_ids_are_correct(self, decomposer):
        dag = decomposer.decompose("Add login page with tests")
        ids = [t.id for t in dag.subtasks]
        assert "task-1-login-code" in ids
        assert "task-2-login-test" in ids

    def test_subtask_types_are_assigned(self, decomposer):
        dag = decomposer.decompose("Add login page with tests")
        types = {t.id: t.type for t in dag.subtasks}
        assert types["task-1-login-code"] == AgentType.CODE_FRONTEND
        assert types["task-2-login-test"] == AgentType.TEST

    def test_dependency_order_is_preserved(self, decomposer):
        dag = decomposer.decompose("Add login page with tests")
        test_task = next(t for t in dag.subtasks if t.id == "task-2-login-test")
        assert "task-1-login-code" in test_task.depends_on

    def test_original_task_is_stored(self, decomposer):
        description = "Add login page with tests"
        dag = decomposer.decompose(description)
        assert dag.original_task == description

    def test_branch_name_is_auto_set(self, decomposer):
        dag = decomposer.decompose("Add login page with tests")
        for task in dag.subtasks:
            assert task.branch_name == f"feature/{task.id}"

    def test_parse_json_strips_markdown_fences(self):
        raw = "```json\n{\"subtasks\": []}\n```"
        result = TaskDecomposer._parse_json(raw)
        assert result == {"subtasks": []}

    def test_parse_json_raises_on_invalid_json(self):
        with pytest.raises(ValueError, match="invalid JSON"):
            TaskDecomposer._parse_json("not json at all")

    def test_unknown_agent_type_defaults_to_code_generic(self, decomposer, mock_llm_client):
        response_with_unknown_type = """{
          "subtasks": [
            {
              "id": "task-1",
              "title": "Some task",
              "description": "Do something",
              "type": "unknown-agent-xyz",
              "depends_on": []
            }
          ]
        }"""
        mock_llm_client.chat.completions.create.return_value.choices[0].message.content = (
            response_with_unknown_type
        )
        dag = decomposer.decompose("Some task")
        assert dag.subtasks[0].type == AgentType.CODE_GENERIC

    def test_get_ready_tasks_returns_tasks_with_no_dependencies(self, decomposer):
        dag = decomposer.decompose("Add login page with tests")
        ready = dag.get_ready_tasks(completed_ids=set())
        assert len(ready) == 1
        assert ready[0].id == "task-1-login-code"

    def test_get_ready_tasks_unlocks_dependent_after_dependency_completes(self, decomposer):
        dag = decomposer.decompose("Add login page with tests")
        ready = dag.get_ready_tasks(completed_ids={"task-1-login-code"})
        assert len(ready) == 1
        assert ready[0].id == "task-2-login-test"
