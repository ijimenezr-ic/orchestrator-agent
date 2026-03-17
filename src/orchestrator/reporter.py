"""Compact Reporter.

Formats sub-agent results into compact summaries suitable for the orchestrator
context window and for saving to Engram.
"""

from __future__ import annotations

from orchestrator.models import AgentResult, TaskStatus


class CompactReporter:
    """Converts :class:`~orchestrator.models.AgentResult` objects into compact text."""

    def format_summary(self, result: AgentResult) -> str:
        """Return a one-paragraph plain-text summary of the result.

        Args:
            result: The agent result to format.

        Returns:
            A compact, human-readable summary string.
        """
        status_emoji = {
            TaskStatus.COMPLETED: "✅",
            TaskStatus.FAILED: "❌",
            TaskStatus.SKIPPED: "⏭️",
        }.get(result.status, "⏳")

        files_info = ""
        if result.files_changed:
            files_list = ", ".join(result.files_changed[:5])
            if len(result.files_changed) > 5:
                files_list += f" (+{len(result.files_changed) - 5} more)"
            files_info = f" | Files: {files_list}"

        error_info = f" | Error: {result.errors}" if result.errors else ""

        return (
            f"{status_emoji} [{result.task_id}] {result.summary}"
            f"{files_info}"
            f"{error_info}"
        )

    def format_engram_content(self, result: AgentResult) -> str:
        """Format result as structured Engram observation content (Markdown).

        Args:
            result: The agent result to format.

        Returns:
            Markdown string suitable for saving to Engram.
        """
        lines = [
            f"## Status\n{result.status.value.upper()}",
            f"## Summary\n{result.summary}",
        ]
        if result.files_changed:
            files = "\n".join(f"- `{f}`" for f in result.files_changed)
            lines.append(f"## Files Changed\n{files}")
        if result.branch:
            lines.append(f"## Branch\n`{result.branch}`")
        if result.errors:
            lines.append(f"## Errors\n{result.errors}")
        return "\n\n".join(lines)
