"""Error handling utilities for the orchestrator.

Provides retry logic, timeout handling, and failure escalation strategies.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, TypeVar

from orchestrator.config import MAX_RETRIES, TASK_TIMEOUT
from orchestrator.models import AgentResult, SubTask, TaskStatus

logger = logging.getLogger(__name__)

T = TypeVar("T")


class OrchestratorError(Exception):
    """Base exception for orchestrator errors."""


class TaskTimeoutError(OrchestratorError):
    """Raised when a subtask exceeds its time budget."""


class MaxRetriesExceededError(OrchestratorError):
    """Raised when a subtask fails more than :data:`~orchestrator.config.MAX_RETRIES` times."""


def with_retry(
    fn: Callable[[], AgentResult],
    task: SubTask,
    max_retries: int = MAX_RETRIES,
) -> AgentResult:
    """Execute *fn* up to *max_retries* + 1 times.

    Args:
        fn: Callable that returns an :class:`~orchestrator.models.AgentResult`.
        task: The subtask being executed (used for logging and result construction).
        max_retries: Maximum number of retry attempts after the first failure.

    Returns:
        The first successful :class:`~orchestrator.models.AgentResult`.

    Raises:
        MaxRetriesExceededError: If all attempts fail.
    """
    last_result: AgentResult | None = None
    for attempt in range(max_retries + 1):
        if attempt > 0:
            wait = 2 ** attempt  # exponential back-off: 2s, 4s, …
            logger.info("Retry %d/%d for task %s in %ds…", attempt, max_retries, task.id, wait)
            time.sleep(wait)

        result = fn()
        task.retry_count = attempt

        if result.status == TaskStatus.COMPLETED:
            return result

        last_result = result
        logger.warning(
            "Task %s failed on attempt %d: %s", task.id, attempt + 1, result.errors
        )

    # All attempts exhausted
    raise MaxRetriesExceededError(
        f"Task {task.id} failed after {max_retries + 1} attempt(s). "
        f"Last error: {last_result.errors if last_result else 'unknown'}"
    )


def make_failed_result(task: SubTask, error: str) -> AgentResult:
    """Create a synthetic failed :class:`~orchestrator.models.AgentResult`.

    Useful when a task is skipped due to a dependency failure or timeout.

    Args:
        task: The subtask that failed.
        error: Human-readable error description.

    Returns:
        A :class:`~orchestrator.models.AgentResult` with status FAILED.
    """
    return AgentResult(
        task_id=task.id,
        status=TaskStatus.FAILED,
        summary=f"Task {task.id} failed: {error}",
        branch=task.branch_name,
        errors=error,
    )
