"""Task Decomposer.

Uses Claude Opus to break a high-level task description into a directed
acyclic graph (DAG) of smaller subtasks, each with an assigned agent type
and explicit dependency relationships.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List

import anthropic

from orchestrator.config import ANTHROPIC_API_KEY, ORCHESTRATOR_MODEL
from orchestrator.models import AgentType, SubTask, TaskDAG

logger = logging.getLogger(__name__)

_DECOMPOSE_SYSTEM = """You are an expert software project manager and architect.
Your job is to break down a development task into a set of well-defined subtasks
that can be executed by specialized AI sub-agents.

Each subtask must have:
- A unique short ID (kebab-case, e.g. "task-1-auth-code")
- A clear title
- A detailed description
- An agent type: one of code-frontend, code-backend, code-generic, test-agent, docs-agent, review-agent
- A list of IDs of subtasks this one depends on (empty list if none)

Return ONLY a valid JSON object with the structure:
{
  "subtasks": [
    {
      "id": "<string>",
      "title": "<string>",
      "description": "<string>",
      "type": "<agent-type>",
      "depends_on": ["<id>", ...]
    }
  ]
}

Rules:
1. Decompose into 2-6 subtasks for the MVP scope.
2. Code subtasks come first, test subtasks depend on code subtasks.
3. Docs subtasks depend on code subtasks.
4. Review subtask (if any) must come last, depending on tests and docs.
5. Return ONLY the JSON — no prose, no markdown fences.
"""


class TaskDecomposer:
    """Decomposes a user task description into a :class:`~orchestrator.models.TaskDAG`."""

    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    def decompose(self, task_description: str) -> TaskDAG:
        """Send *task_description* to the LLM and parse the structured response.

        Args:
            task_description: Free-text description of the user's goal.

        Returns:
            A :class:`~orchestrator.models.TaskDAG` containing the subtasks.

        Raises:
            ValueError: If the LLM response cannot be parsed as a valid DAG.
        """
        logger.info("Decomposing task: %s", task_description)
        message = self._client.messages.create(
            model=ORCHESTRATOR_MODEL,
            max_tokens=2048,
            system=_DECOMPOSE_SYSTEM,
            messages=[{"role": "user", "content": task_description}],
        )

        raw_text: str = message.content[0].text.strip()
        data = self._parse_json(raw_text)
        subtasks = self._build_subtasks(data.get("subtasks", []))

        logger.info("Decomposed into %d subtasks.", len(subtasks))
        return TaskDAG(original_task=task_description, subtasks=subtasks)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_json(text: str) -> Dict[str, Any]:
        """Extract and parse JSON from the LLM response text."""
        # Strip markdown fences if present
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM returned invalid JSON: {exc}\n---\n{text}") from exc

    @staticmethod
    def _build_subtasks(raw: List[Dict[str, Any]]) -> List[SubTask]:
        """Convert raw dicts to :class:`~orchestrator.models.SubTask` objects."""
        subtasks = []
        for item in raw:
            agent_type_str: str = item.get("type", "code-generic")
            try:
                agent_type = AgentType(agent_type_str)
            except ValueError:
                logger.warning("Unknown agent type '%s', defaulting to CODE_GENERIC.", agent_type_str)
                agent_type = AgentType.CODE_GENERIC

            task_id: str = item["id"]
            branch_name = f"feature/{task_id}"

            subtasks.append(
                SubTask(
                    id=task_id,
                    title=item.get("title", task_id),
                    description=item.get("description", ""),
                    type=agent_type,
                    depends_on=item.get("depends_on", []),
                    branch_name=branch_name,
                )
            )
        return subtasks
