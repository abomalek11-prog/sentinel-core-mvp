"""
LLM configuration for Sentinel Core.

Wraps ChatAnthropic with sane defaults, auto-loads ANTHROPIC_API_KEY from
the project .env file, and returns None gracefully when the key is absent
so every caller can fall back to rule-based logic without crashing.
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from typing import Any

from dotenv import find_dotenv, load_dotenv

from sentinel_core.utils.logging import get_logger

log = get_logger(__name__)

# ── Public constants ──────────────────────────────────────────────────────────
DEFAULT_MODEL: str = "anthropic/claude-4-sonnet-2026"
FALLBACK_MODEL: str = "openai/gpt-4o"

# ── Load .env as early as possible ───────────────────────────────────────────
_dotenv_path = find_dotenv(usecwd=True)
if _dotenv_path:
    load_dotenv(_dotenv_path, override=False)
    log.debug("dotenv_loaded", path=_dotenv_path)
else:
    log.debug("dotenv_not_found", note="Relying on existing environment variables")


# ── Core factory ─────────────────────────────────────────────────────────────

@lru_cache(maxsize=8)
def get_llm(
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    timeout: int = 60,
) -> Any | None:
    from sentinel_core.config import settings
    target_model = model or settings.llm_model

    if target_model == "gpt-4o":  # Handle previous default if still in settings
        target_model = DEFAULT_MODEL

    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not openrouter_key:
        openrouter_key = getattr(settings, "openrouter_api_key", "")

    if not openrouter_key:
        log.error(
            "missing_api_key", 
            detail="OPENROUTER_API_KEY not found in environment or .env.",
            note="Agents will fall back to rule-based analysis."
        )
        return None

    try:
        from langchain_openai import ChatOpenAI
        
        main_llm = ChatOpenAI(
            model=target_model,
            api_key=openrouter_key,
            base_url="https://openrouter.ai/api/v1",
            temperature=temperature,
            max_tokens=max_tokens,
            request_timeout=timeout,
        )
        
        fallback_llm = ChatOpenAI(
            model=FALLBACK_MODEL,
            api_key=openrouter_key,
            base_url="https://openrouter.ai/api/v1",
            temperature=temperature,
            max_tokens=max_tokens,
            request_timeout=timeout,
        )

        llm_with_fallback = main_llm.with_fallbacks([fallback_llm])
        
        log.info(
            "llm_initialised", 
            provider="openrouter", 
            model=target_model,
            fallback=FALLBACK_MODEL
        )
        return llm_with_fallback

    except ImportError:
        log.error("langchain_openai_missing", fix="Run: uv pip install langchain-openai")
        return None
    except Exception as exc:
        log.error("openrouter_llm_init_failed", error=str(exc), exc_info=True)
        return None


def strip_json_markdown(text: str) -> str:
    """Strip markdown code fences from an LLM response before JSON parsing.

    Some models wrap JSON output in triple-backtick fences even when instructed
    not to.  This helper removes the fences so ``json.loads`` can parse cleanly.

    Args:
        text: Raw LLM response text.

    Returns:
        The inner JSON text, or *text* unchanged if no fences are found.
    """
    text = text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        return m.group(1).strip()
    return text


def parse_llm_json(text: str, fallback: Any = None) -> Any:
    """Parse JSON from an LLM response, tolerating markdown fences.

    Args:
        text:     Raw LLM response text.
        fallback: Value to return if parsing fails.

    Returns:
        The parsed Python object, or *fallback* on failure.
    """
    cleaned = strip_json_markdown(text)
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError) as exc:
        log.warning("llm_json_parse_failed", exc=str(exc), preview=cleaned[:120])
        return fallback
