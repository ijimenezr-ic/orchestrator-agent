"""Engram HTTP API client for persistent memory across agent sessions.

Engram exposes a REST API on localhost:7437.  This module provides a thin
async/sync wrapper so orchestrator components can save, search, and retrieve
structured memory without coupling to any specific HTTP library internals.

References:
    https://github.com/Gentleman-Programming/engram
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from orchestrator.config import ENGRAM_URL

logger = logging.getLogger(__name__)


class EngramClient:
    """Synchronous HTTP client for the Engram memory service."""

    def __init__(self, base_url: str = ENGRAM_URL, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Full-text search over stored observations.

        Args:
            query: Free-text search query.
            limit: Maximum number of results to return.

        Returns:
            List of matching observation objects.
        """
        try:
            result = self._get("/search", params={"q": query, "limit": limit})
            return result if isinstance(result, list) else result.get("results", [])
        except Exception as exc:
            logger.warning("Engram search failed: %s", exc)
            return []

    def save_observation(
        self,
        title: str,
        type: str,  # noqa: A002
        content: str,
        topic_key: str,
        project: str,
    ) -> Dict[str, Any]:
        """Persist a structured observation in Engram.

        Args:
            title: Short title/label for the observation.
            type: Category string, e.g. "decision", "bugfix", "progress".
            content: Markdown body of the observation.
            topic_key: Hierarchical key, e.g. "task/42-auth-middleware".
            project: Project name for grouping.

        Returns:
            Created observation object returned by Engram.
        """
        payload = {
            "title": title,
            "type": type,
            "content": content,
            "topic_key": topic_key,
            "project": project,
        }
        try:
            return self._post("/observations", payload)
        except Exception as exc:
            logger.warning("Engram save_observation failed: %s", exc)
            return {}

    def get_context(self, project: str) -> Dict[str, Any]:
        """Retrieve the latest memory context for a project.

        Args:
            project: Project name to filter by.

        Returns:
            Context object with recent observations.
        """
        try:
            return self._get("/context", params={"project": project})
        except Exception as exc:
            logger.warning("Engram get_context failed: %s", exc)
            return {}

    def session_start(
        self, session_id: str, project: str, directory: str
    ) -> Dict[str, Any]:
        """Register the start of an agent session.

        Args:
            session_id: Unique session identifier.
            project: Project name.
            directory: Working directory for this session.

        Returns:
            Session object returned by Engram.
        """
        payload = {
            "session_id": session_id,
            "project": project,
            "directory": directory,
        }
        try:
            return self._post("/sessions", payload)
        except Exception as exc:
            logger.warning("Engram session_start failed: %s", exc)
            return {}

    def session_end(self, session_id: str, summary: str) -> Dict[str, Any]:
        """Mark a session as finished and store its summary.

        Args:
            session_id: The session identifier previously used in session_start.
            summary: Markdown summary (Goal / Accomplished / Next Steps).

        Returns:
            Updated session object.
        """
        payload = {"summary": summary}
        try:
            return self._post(f"/sessions/{session_id}/end", payload)
        except Exception as exc:
            logger.warning("Engram session_end failed: %s", exc)
            return {}

    def get_stats(self) -> Dict[str, Any]:
        """Return Engram server statistics.

        Returns:
            Stats dict with counts of observations, sessions, etc.
        """
        try:
            return self._get("/stats")
        except Exception as exc:
            logger.warning("Engram get_stats failed: %s", exc)
            return {}
