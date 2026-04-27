"""
Sentinel Core — Application Configuration
Loads settings from environment variables / .env file using Pydantic.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    """
    Central configuration model for Sentinel Core.

    All values can be overridden via environment variables or a .env file.
    Environment variable names are uppercased versions of the field names,
    prefixed with ``SENTINEL_``.

    Example .env::

        SENTINEL_LOG_LEVEL=DEBUG
        SENTINEL_JSON_LOGS=false
        SENTINEL_SANDBOX_TIMEOUT=30
    """

    model_config = SettingsConfigDict(
        env_prefix="SENTINEL_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM Configuration ─────────────────────────────────────────────────────
    github_token: str | None = Field(
        default=None,
        description="GitHub PAT for accessing GitHub Models API.",
    )
    openrouter_api_key: str | None = Field(
        default=None,
        description="OpenRouter API key for using LLMs via OpenRouter.",
    )
    llm_model: str = Field(
        default="gpt-4o",
        description="LLM model name to use via OpenRouter or GitHub Models.",
    )

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Log verbosity level.",
    )
    json_logs: bool = Field(
        default=False,
        description="Emit JSON-formatted logs (enable in production/CI).",
    )

    # ── Parsing ───────────────────────────────────────────────────────────────
    default_language: Literal["python"] = Field(
        default="python",
        description="Default programming language for parsing (extensible in future).",
    )
    max_file_size_kb: int = Field(
        default=512,
        ge=1,
        le=10_240,
        description="Maximum source file size to parse, in kilobytes.",
    )
    max_ast_depth: int = Field(
        default=200,
        ge=10,
        le=2_000,
        description="Maximum AST traversal depth to prevent stack overflows.",
    )

    # ── Graph Builder ─────────────────────────────────────────────────────────
    max_graph_nodes: int = Field(
        default=50_000,
        ge=100,
        description="Hard cap on nodes in a single Code Property Graph.",
    )

    # ── Sandbox ───────────────────────────────────────────────────────────────
    sandbox_timeout: int = Field(
        default=15,
        ge=1,
        le=300,
        description="Maximum seconds a sandboxed execution may run.",
    )
    sandbox_max_memory_mb: int = Field(
        default=256,
        ge=32,
        le=4_096,
        description="Memory limit (MB) for sandboxed processes.",
    )

    # ── Paths ─────────────────────────────────────────────────────────────────
    workspace_root: Path = Field(
        default=Path("."),
        description="Root directory Sentinel operates on.",
    )

    @field_validator("workspace_root", mode="before")
    @classmethod
    def resolve_workspace(cls, v: object) -> Path:
        return Path(str(v)).resolve()


# ---------------------------------------------------------------------------
# Module-level singleton — import this everywhere instead of re-instantiating
# ---------------------------------------------------------------------------
settings = Settings()
