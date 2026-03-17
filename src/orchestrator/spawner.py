"""Sub-Agent Spawner.

Creates and runs a sub-agent in its assigned git worktree using a specialized
system prompt.  The sub-agent uses Claude Sonnet for implementation and returns
only a compact :class:`~orchestrator.models.AgentResult`.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List

import git
import openai

from orchestrator.config import SUBAGENT_MODEL, TASK_TIMEOUT
from orchestrator.llm import chat, create_client
from orchestrator.memory import EngramClient
from orchestrator.models import AgentResult, AgentType, SubTask, TaskStatus
from orchestrator.reporter import CompactReporter

logger = logging.getLogger(__name__)

# Import agent-specific system prompts
from orchestrator.prompts.agents.code_frontend import SYSTEM_PROMPT as _FRONTEND_PROMPT
from orchestrator.prompts.agents.code_backend import SYSTEM_PROMPT as _BACKEND_PROMPT
from orchestrator.prompts.agents.test_agent import SYSTEM_PROMPT as _TEST_PROMPT
from orchestrator.prompts.agents.docs_agent import SYSTEM_PROMPT as _DOCS_PROMPT
from orchestrator.prompts.agents.review_agent import SYSTEM_PROMPT as _REVIEW_PROMPT
from orchestrator.prompts.orchestrator import SYSTEM_PROMPT as _GENERIC_PROMPT

_PROMPT_MAP: dict[AgentType, str] = {
    AgentType.CODE_FRONTEND: _FRONTEND_PROMPT,
    AgentType.CODE_BACKEND: _BACKEND_PROMPT,
    AgentType.CODE_GENERIC: _GENERIC_PROMPT,
    AgentType.TEST: _TEST_PROMPT,
    AgentType.DOCS: _DOCS_PROMPT,
    AgentType.REVIEW: _REVIEW_PROMPT,
}


class SubAgentSpawner:
    """Creates and executes sub-agents for individual subtasks."""

    def __init__(self, memory: EngramClient | None = None, project: str = "orchestrator") -> None:
        self._client = create_client()
        self._memory = memory or EngramClient()
        self._reporter = CompactReporter()
        self._project = project

    def run(self, task: SubTask, prior_context: str = "") -> AgentResult:
        """Execute the subtask inside its worktree and return a compact result.

        Args:
            task: The subtask to execute.
            prior_context: Optional summary of relevant prior work from Engram.

        Returns:
            A compact :class:`~orchestrator.models.AgentResult`.
        """
        system_prompt = _PROMPT_MAP.get(task.type, _GENERIC_PROMPT)
        worktree_info = (
            f"\n\nYou are working in git worktree: {task.worktree_path}"
            if task.worktree_path
            else ""
        )
        if prior_context:
            worktree_info += f"\n\nPrior context from memory:\n{prior_context}"

        user_message = (
            f"Task ID: {task.id}\n"
            f"Title: {task.title}\n"
            f"Description: {task.description}\n"
            f"{worktree_info}\n\n"
            "Complete the task by writing all necessary files. "
            "Respond with a JSON object:\n"
            "{\n"
            '  "summary": "<one paragraph summary of what was done>",\n'
            '  "files": [\n'
            '    {"path": "<relative path>", "content": "<complete file content>"}\n'
            "  ],\n"
            '  "status": "completed" | "failed",\n'
            '  "errors": "<error message or null>"\n'
            "}"
        )

        logger.info("Spawning sub-agent for task %s (type=%s)", task.id, task.type)
        try:
            response_text = chat(
                self._client,
                model=SUBAGENT_MODEL,
                system=system_prompt,
                user_message=user_message,
                max_tokens=16384,
            )
            result, files_data = self._parse_result(task, response_text)
            if task.worktree_path and files_data:
                self._write_and_commit_files(task, files_data)
        except Exception as exc:
            logger.error("Sub-agent for task %s raised: %s", task.id, exc)
            result = AgentResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                summary=f"Sub-agent raised an exception: {exc}",
                branch=task.branch_name,
                errors=str(exc),
            )

        self._save_to_memory(task, result)
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_result(self, task: SubTask, text: str) -> tuple[AgentResult, list[dict]]:
        """Parse the LLM response into an AgentResult and a list of file dicts.

        Returns:
            A tuple of (AgentResult, files_data) where files_data is a list of
            dicts with ``path`` and ``content`` keys.
        """
        import json
        import re

        text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
        text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)

        # Find first JSON object in the response
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return AgentResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                summary=text[:500],
                branch=task.branch_name,
            ), []

        try:
            data = json.loads(match.group())
            status_str = data.get("status", "completed").lower()
            status = TaskStatus.COMPLETED if status_str == "completed" else TaskStatus.FAILED

            # Support new format: files=[{path, content}] or old format: files_changed=[path]
            files_data: list[dict] = [
                f for f in data.get("files", [])
                if isinstance(f, dict) and "path" in f and "content" in f
            ]
            files_changed = [f["path"] for f in files_data] or data.get("files_changed", [])

            return AgentResult(
                task_id=task.id,
                status=status,
                summary=data.get("summary", "Task completed."),
                files_changed=files_changed,
                branch=task.branch_name,
                errors=data.get("errors"),
            ), files_data
        except json.JSONDecodeError:
            return AgentResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                summary=text[:500],
                branch=task.branch_name,
            ), []

    def _write_and_commit_files(self, task: SubTask, files_data: list[dict]) -> None:
        """Write files to the worktree directory and commit them.

        Args:
            task: The subtask whose worktree will receive the files.
            files_data: List of dicts with ``path`` and ``content`` keys.
        """
        worktree = Path(task.worktree_path)
        written: list[str] = []
        for file_info in files_data:
            rel_path = file_info.get("path", "").lstrip("/")
            content = file_info.get("content", "")
            if not rel_path:
                continue
            full_path = worktree / rel_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")
            written.append(rel_path)
            logger.info("Wrote %s to worktree %s", rel_path, worktree)

        if not written:
            return

        try:
            repo = git.Repo(str(worktree))
            repo.git.add(".")
            repo.git.commit("-m", f"feat({task.id}): {task.title}")
            logger.info("Committed %d files for task %s", len(written), task.id)
        except git.GitCommandError as exc:
            logger.warning("Could not commit files for task %s: %s", task.id, exc)

    def _save_to_memory(self, task: SubTask, result: AgentResult) -> None:
        """Persist the result to Engram."""
        content = self._reporter.format_engram_content(result)
        self._memory.save_observation(
            title=f"[{task.id}] {task.title}",
            type="progress",
            content=content,
            topic_key=f"task/{task.id}",
            project=self._project,
        )
