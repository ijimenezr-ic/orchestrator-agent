"""Tests for the EngramClient (memory module)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from orchestrator.memory import EngramClient


@pytest.fixture()
def client():
    return EngramClient(base_url="http://localhost:7437")


@pytest.fixture()
def mock_httpx_client():
    """Return a context-manager-compatible mock for httpx.Client."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()

    mock_http = MagicMock()
    mock_http.__enter__ = MagicMock(return_value=mock_http)
    mock_http.__exit__ = MagicMock(return_value=False)
    mock_http.get.return_value = mock_resp
    mock_http.post.return_value = mock_resp
    return mock_http, mock_resp


class TestSearch:
    def test_returns_list_on_success(self, client, mock_httpx_client):
        mock_http, mock_resp = mock_httpx_client
        mock_resp.json.return_value = [{"id": "1", "content": "JWT auth implemented"}]

        with patch("orchestrator.memory.httpx.Client", return_value=mock_http):
            results = client.search("JWT auth")

        assert isinstance(results, list)
        assert results[0]["content"] == "JWT auth implemented"

    def test_returns_empty_list_on_connection_error(self, client):
        with patch("orchestrator.memory.httpx.Client") as mock_cls:
            mock_cls.return_value.__enter__.side_effect = Exception("connection refused")
            results = client.search("anything")
        assert results == []

    def test_passes_query_and_limit_as_params(self, client, mock_httpx_client):
        mock_http, mock_resp = mock_httpx_client
        mock_resp.json.return_value = []

        with patch("orchestrator.memory.httpx.Client", return_value=mock_http):
            client.search("test query", limit=5)

        call_kwargs = mock_http.get.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs.args[1] if len(call_kwargs.args) > 1 else {}
        assert params.get("q") == "test query" or "test query" in str(call_kwargs)

    def test_handles_dict_response_with_results_key(self, client, mock_httpx_client):
        mock_http, mock_resp = mock_httpx_client
        mock_resp.json.return_value = {"results": [{"id": "2"}], "total": 1}

        with patch("orchestrator.memory.httpx.Client", return_value=mock_http):
            results = client.search("query")

        assert len(results) == 1


class TestSaveObservation:
    def test_returns_dict_on_success(self, client, mock_httpx_client):
        mock_http, mock_resp = mock_httpx_client
        mock_resp.json.return_value = {"id": "obs-1", "title": "Test obs"}

        with patch("orchestrator.memory.httpx.Client", return_value=mock_http):
            result = client.save_observation(
                title="Test obs",
                type="progress",
                content="Did something",
                topic_key="task/1",
                project="my-project",
            )

        assert result["id"] == "obs-1"

    def test_posts_to_observations_endpoint(self, client, mock_httpx_client):
        mock_http, mock_resp = mock_httpx_client
        mock_resp.json.return_value = {}

        with patch("orchestrator.memory.httpx.Client", return_value=mock_http):
            client.save_observation("T", "progress", "C", "key", "proj")

        url = mock_http.post.call_args.args[0]
        assert url.endswith("/observations")

    def test_returns_empty_dict_on_error(self, client):
        with patch("orchestrator.memory.httpx.Client") as mock_cls:
            mock_cls.return_value.__enter__.side_effect = Exception("error")
            result = client.save_observation("T", "t", "C", "k", "p")
        assert result == {}


class TestSessionManagement:
    def test_session_start_posts_to_sessions(self, client, mock_httpx_client):
        mock_http, mock_resp = mock_httpx_client
        mock_resp.json.return_value = {"session_id": "s1"}

        with patch("orchestrator.memory.httpx.Client", return_value=mock_http):
            result = client.session_start("s1", "proj", "/home/user/project")

        url = mock_http.post.call_args.args[0]
        assert url.endswith("/sessions")
        assert result["session_id"] == "s1"

    def test_session_end_posts_to_sessions_id_end(self, client, mock_httpx_client):
        mock_http, mock_resp = mock_httpx_client
        mock_resp.json.return_value = {}

        with patch("orchestrator.memory.httpx.Client", return_value=mock_http):
            client.session_end("s1", "## Goal\nDone")

        url = mock_http.post.call_args.args[0]
        assert "s1/end" in url


class TestGetStats:
    def test_returns_stats_dict(self, client, mock_httpx_client):
        mock_http, mock_resp = mock_httpx_client
        mock_resp.json.return_value = {"observations": 42, "sessions": 5}

        with patch("orchestrator.memory.httpx.Client", return_value=mock_http):
            stats = client.get_stats()

        assert stats["observations"] == 42

    def test_returns_empty_dict_on_error(self, client):
        with patch("orchestrator.memory.httpx.Client") as mock_cls:
            mock_cls.return_value.__enter__.side_effect = Exception("down")
            stats = client.get_stats()
        assert stats == {}
