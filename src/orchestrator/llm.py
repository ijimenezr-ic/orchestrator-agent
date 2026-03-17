"""LLM client factory using GitHub Copilot's model access.

All LLM calls in this project go through the GitHub Models API, which is
OpenAI-compatible and available to any developer with a GitHub Copilot
subscription.  Authentication uses a GitHub token — in Copilot environments
this is the ``GITHUB_TOKEN`` environment variable that is already present; in
local development it must be a fine-grained PAT with *Models: read* permission.

References:
    https://docs.github.com/en/github-models
    https://github.com/marketplace/models
"""

from __future__ import annotations

import logging

import openai

from orchestrator.config import GITHUB_MODELS_URL, GITHUB_TOKEN

logger = logging.getLogger(__name__)


def create_client() -> openai.OpenAI:
    """Create an OpenAI-compatible client pointing at the GitHub Models API.

    Returns:
        A configured :class:`openai.OpenAI` instance ready to use.
    """
    return openai.OpenAI(
        base_url=GITHUB_MODELS_URL,
        api_key=GITHUB_TOKEN,
    )


def chat(
    client: openai.OpenAI,
    model: str,
    system: str,
    user_message: str,
    max_tokens: int = 2048,
) -> str:
    """Send a system + user message pair and return the assistant's reply.

    This is a thin wrapper around ``client.chat.completions.create`` that
    normalises the Anthropic-style ``system`` parameter into the OpenAI
    messages list expected by the GitHub Models API.

    Args:
        client: An :class:`openai.OpenAI` instance (from :func:`create_client`).
        model: GitHub Models catalog ID, e.g. ``"claude-opus-4-5"``.
        system: The system prompt string.
        user_message: The user turn message.
        max_tokens: Maximum tokens in the response.

    Returns:
        The assistant's reply as a plain string.

    Raises:
        openai.OpenAIError: On API errors (rate limit, auth, etc.).
    """
    completion = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
    )
    return completion.choices[0].message.content or ""
