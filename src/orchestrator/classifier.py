"""Agent Classifier.

Determines the most appropriate :class:`~orchestrator.models.AgentType` for a
given subtask using keyword heuristics and an LLM fallback.
"""

from __future__ import annotations

import logging
import re

import openai

from orchestrator.config import ORCHESTRATOR_MODEL
from orchestrator.llm import chat, create_client
from orchestrator.models import AgentType

logger = logging.getLogger(__name__)

# Ordered heuristic rules: (compiled_pattern, AgentType)
_KEYWORD_RULES: list[tuple[re.Pattern[str], AgentType]] = [
    (re.compile(r"\b(react|tsx?|frontend|ui|component|css|html|vue|svelte)\b", re.I), AgentType.CODE_FRONTEND),
    (re.compile(r"\b(api|backend|server|django|fastapi|flask|express|node|database|sql|orm)\b", re.I), AgentType.CODE_BACKEND),
    (re.compile(r"\b(test|spec|pytest|jest|coverage|unit|integration|e2e|end.to.end)\b", re.I), AgentType.TEST),
    (re.compile(r"\b(doc|readme|documentation|docstring|comment|wiki|mkdocs)\b", re.I), AgentType.DOCS),
    (re.compile(r"\b(review|audit|quality|lint|sonar|code.review)\b", re.I), AgentType.REVIEW),
    (re.compile(r"\b(debug|fix|bug|error|traceback|issue|investigate)\b", re.I), AgentType.DEBUG),
    (re.compile(r"\b(merge|integrate|combine|conflict)\b", re.I), AgentType.MERGE),
]

_CLASSIFY_SYSTEM = """You are a software project manager. Given a subtask description,
return exactly one agent type from this list:
code-frontend, code-backend, code-generic, test-agent, docs-agent, review-agent, debug-agent, merge-agent

Return ONLY the agent type string with no other text."""


class AgentClassifier:
    """Classifies a subtask into an :class:`~orchestrator.models.AgentType`."""

    def __init__(self, use_llm_fallback: bool = True) -> None:
        self._use_llm_fallback = use_llm_fallback
        if use_llm_fallback:
            self._client = create_client()

    def classify(self, title: str, description: str = "") -> AgentType:
        """Determine the agent type for the given subtask.

        First applies fast keyword heuristics; falls back to the LLM when
        no keyword rule matches.

        Args:
            title: Short title of the subtask.
            description: Detailed description of the subtask.

        Returns:
            The most appropriate :class:`~orchestrator.models.AgentType`.
        """
        combined = f"{title} {description}"
        agent_type = self._keyword_classify(combined)
        if agent_type is not None:
            logger.debug("Keyword-classified '%s' → %s", title, agent_type)
            return agent_type

        if self._use_llm_fallback:
            return self._llm_classify(combined)

        logger.debug("No match for '%s', defaulting to CODE_GENERIC.", title)
        return AgentType.CODE_GENERIC

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _keyword_classify(text: str) -> AgentType | None:
        for pattern, agent_type in _KEYWORD_RULES:
            if pattern.search(text):
                return agent_type
        return None

    def _llm_classify(self, text: str) -> AgentType:
        try:
            raw = chat(
                self._client,
                model=ORCHESTRATOR_MODEL,
                system=_CLASSIFY_SYSTEM,
                user_message=text,
                max_tokens=20,
            ).strip().lower()
            return AgentType(raw)
        except (ValueError, Exception) as exc:
            logger.warning("LLM classification failed: %s — defaulting to CODE_GENERIC", exc)
            return AgentType.CODE_GENERIC
