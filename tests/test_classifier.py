"""Tests for the AgentClassifier."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from orchestrator.classifier import AgentClassifier
from orchestrator.models import AgentType


@pytest.fixture()
def classifier_no_llm():
    """Classifier with LLM fallback disabled."""
    return AgentClassifier(use_llm_fallback=False)


@pytest.fixture()
def classifier_with_mock_llm():
    """Classifier whose LLM always returns 'code-generic'."""
    c = AgentClassifier(use_llm_fallback=True)
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="code-generic")]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message
    c._client = mock_client
    return c


class TestKeywordClassification:
    def test_react_keyword_returns_frontend(self, classifier_no_llm):
        assert classifier_no_llm.classify("Create React component") == AgentType.CODE_FRONTEND

    def test_tsx_keyword_returns_frontend(self, classifier_no_llm):
        assert classifier_no_llm.classify("Add TSX form") == AgentType.CODE_FRONTEND

    def test_api_keyword_returns_backend(self, classifier_no_llm):
        assert classifier_no_llm.classify("Implement REST API endpoint") == AgentType.CODE_BACKEND

    def test_fastapi_keyword_returns_backend(self, classifier_no_llm):
        assert classifier_no_llm.classify("Add FastAPI route") == AgentType.CODE_BACKEND

    def test_test_keyword_returns_test(self, classifier_no_llm):
        assert classifier_no_llm.classify("Write unit tests for auth") == AgentType.TEST

    def test_pytest_keyword_returns_test(self, classifier_no_llm):
        assert classifier_no_llm.classify("pytest coverage for service") == AgentType.TEST

    def test_readme_keyword_returns_docs(self, classifier_no_llm):
        assert classifier_no_llm.classify("Update README") == AgentType.DOCS

    def test_documentation_keyword_returns_docs(self, classifier_no_llm):
        assert classifier_no_llm.classify("Write documentation", "Add docstrings") == AgentType.DOCS

    def test_review_keyword_returns_review(self, classifier_no_llm):
        assert classifier_no_llm.classify("Code review for PR") == AgentType.REVIEW

    def test_debug_keyword_returns_debug(self, classifier_no_llm):
        assert classifier_no_llm.classify("Debug login failure") == AgentType.DEBUG

    def test_merge_keyword_returns_merge(self, classifier_no_llm):
        assert classifier_no_llm.classify("Merge feature branch") == AgentType.MERGE

    def test_no_match_returns_generic(self, classifier_no_llm):
        assert classifier_no_llm.classify("Obscure random task") == AgentType.CODE_GENERIC

    def test_description_is_also_checked(self, classifier_no_llm):
        # Title has no keyword but description does
        result = classifier_no_llm.classify("Do the thing", "Write pytest tests here")
        assert result == AgentType.TEST

    def test_case_insensitive_matching(self, classifier_no_llm):
        assert classifier_no_llm.classify("CREATE REACT COMPONENT") == AgentType.CODE_FRONTEND


class TestLLMFallback:
    def test_llm_fallback_called_when_no_keyword_match(self, classifier_with_mock_llm):
        result = classifier_with_mock_llm.classify("Obscure random task with no keywords")
        assert result == AgentType.CODE_GENERIC
        classifier_with_mock_llm._client.messages.create.assert_called_once()

    def test_llm_fallback_not_called_when_keyword_matches(self, classifier_with_mock_llm):
        classifier_with_mock_llm.classify("Write pytest tests")
        classifier_with_mock_llm._client.messages.create.assert_not_called()

    def test_llm_fallback_returns_generic_on_exception(self):
        c = AgentClassifier(use_llm_fallback=True)
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API error")
        c._client = mock_client
        result = c.classify("Obscure task")
        assert result == AgentType.CODE_GENERIC
