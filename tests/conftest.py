"""pytest configuration and shared fixtures."""

from __future__ import annotations

import pytest

from sentinel_core.utils.logging import configure_logging


def pytest_configure(config: pytest.Config) -> None:
    """Configure logging once for the whole test session."""
    configure_logging(level="WARNING", json_output=False)
