"""Pydantic data models for the orchestrator agent system."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    """Supported sub-agent specializations."""

    CODE_FRONTEND = "code-frontend"
    CODE_BACKEND = "code-backend"
    CODE_GENERIC = "code-generic"
    TEST = "test-agent"
    DOCS = "docs-agent"
    REVIEW = "review-agent"
    DEBUG = "debug-agent"
    MERGE = "merge-agent"


class TaskStatus(str, Enum):
    """Lifecycle states for a subtask."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class SubTask(BaseModel):
    """A single unit of work within a larger task DAG."""

    id: str = Field(..., description="Unique identifier, e.g. 'task-1-auth-code'")
    title: str = Field(..., description="Short human-readable title")
    description: str = Field(..., description="Detailed description of the work")
    type: AgentType = Field(..., description="Agent type that should handle this task")
    depends_on: List[str] = Field(
        default_factory=list,
        description="IDs of subtasks that must complete before this one starts",
    )
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    branch_name: Optional[str] = Field(
        default=None, description="Git branch for the worktree, e.g. 'feature/task-1-auth-code'"
    )
    worktree_path: Optional[str] = Field(
        default=None, description="Absolute path to the git worktree directory"
    )
    retry_count: int = Field(default=0, description="Number of execution attempts so far")


class TaskDAG(BaseModel):
    """Complete task decomposition as a directed acyclic graph."""

    original_task: str = Field(..., description="The raw task description from the user")
    subtasks: List[SubTask] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def get_ready_tasks(self, completed_ids: set[str]) -> List[SubTask]:
        """Return subtasks whose dependencies are all satisfied."""
        return [
            t
            for t in self.subtasks
            if t.status == TaskStatus.PENDING
            and t.id not in completed_ids
            and all(dep in completed_ids for dep in t.depends_on)
        ]

    def is_complete(self) -> bool:
        """True when every subtask is in a terminal state."""
        return all(
            t.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED, TaskStatus.FAILED)
            for t in self.subtasks
        )


class AgentResult(BaseModel):
    """Compact result returned by a sub-agent after finishing its subtask."""

    task_id: str = Field(..., description="ID of the subtask that was executed")
    status: TaskStatus
    summary: str = Field(..., description="One-paragraph human-readable summary")
    files_changed: List[str] = Field(
        default_factory=list, description="Relative paths of files created/modified"
    )
    branch: Optional[str] = Field(default=None, description="Git branch with the changes")
    errors: Optional[str] = Field(default=None, description="Error description if status=FAILED")
