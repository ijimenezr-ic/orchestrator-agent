"""Configuration constants for the orchestrator agent."""

import os
from dotenv import load_dotenv

load_dotenv()

# LLM Models
ORCHESTRATOR_MODEL: str = os.getenv("ORCHESTRATOR_MODEL", "claude-opus-4-20250514")
SUBAGENT_MODEL: str = os.getenv("SUBAGENT_MODEL", "claude-sonnet-4-20250514")

# Engram memory service
ENGRAM_URL: str = os.getenv("ENGRAM_URL", "http://localhost:7437")

# Execution limits
MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "1"))
MAX_SUBAGENTS: int = int(os.getenv("MAX_SUBAGENTS", "2"))
TASK_TIMEOUT: int = int(os.getenv("TASK_TIMEOUT", "300"))  # seconds

# Git worktrees
WORKTREE_BASE_DIR: str = os.getenv("WORKTREE_BASE_DIR", "../.worktrees")

# Anthropic API key
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
