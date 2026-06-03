"""Shared OpenAI client for offline knowledge-base work.

Kept separate from the chat agent: the KB analyzer makes single structured
calls (no tool loop), so it talks to the OpenAI SDK directly. This is the only
KB module that performs network calls.
"""

from __future__ import annotations

from functools import lru_cache

from ..config import MODEL_API_KEY, MODEL_NAME


class KBConfigError(RuntimeError):
    """Raised when the model API key is missing."""


@lru_cache(maxsize=1)
def get_openai_client():
    """Return a cached OpenAI client, or raise if no API key is configured."""
    if not MODEL_API_KEY:
        raise KBConfigError(
            "MODEL_API_KEY is not set. Add it to .env to run knowledge-base analysis."
        )
    from openai import OpenAI

    return OpenAI(api_key=MODEL_API_KEY)


def get_model_name() -> str:
    return MODEL_NAME
