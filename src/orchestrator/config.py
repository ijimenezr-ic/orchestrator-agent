"""Configuration constants for the orchestrator agent."""

import os
from dotenv import load_dotenv

load_dotenv()

# LLM Models — names must match GitHub Models catalog IDs
# https://github.com/marketplace/models
ORCHESTRATOR_MODEL: str = os.getenv("ORCHESTRATOR_MODEL", "claude-opus-4-5")
SUBAGENT_MODEL: str = os.getenv("SUBAGENT_MODEL", "claude-sonnet-4-5")

# GitHub Models API (OpenAI-compatible endpoint used by GitHub Copilot)
GITHUB_MODELS_URL: str = os.getenv("GITHUB_MODELS_URL", "https://models.inference.ai.azure.com")

# GitHub token — provided automatically in Copilot environments via GITHUB_TOKEN,
# or set manually via a fine-grained PAT with "Models: read" permission.
GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")

# Engram memory service
ENGRAM_URL: str = os.getenv("ENGRAM_URL", "http://localhost:7437")

# Execution limits
MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "1"))
MAX_SUBAGENTS: int = int(os.getenv("MAX_SUBAGENTS", "2"))
TASK_TIMEOUT: int = int(os.getenv("TASK_TIMEOUT", "300"))  # seconds

# Git worktrees
WORKTREE_BASE_DIR: str = os.getenv("WORKTREE_BASE_DIR", "../.worktrees")
