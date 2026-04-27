"""
Sentinel Core — Sandbox Module
Safe, isolated execution of Python code with timeout and memory limits.

Public API:
    - SandboxExecutor: Main executor class for safe code execution.
    - ExecutionResult: Result object from sandbox execution.
    - execute_code: Convenience function for one-off execution.
    - SandboxError: Base exception for all sandbox errors.
    - ExecutionTimeout: Raised when code exceeds timeout.
    - ExecutionFailure: Raised when code exits non-zero.
"""

from __future__ import annotations

from sentinel_core.sandbox.executor import (
    ExecutionFailure,
    ExecutionResult,
    ExecutionTimeout,
    SandboxError,
    SandboxExecutor,
    execute_code,
)

__all__ = [
    "SandboxExecutor",
    "ExecutionResult",
    "execute_code",
    "SandboxError",
    "ExecutionTimeout",
    "ExecutionFailure",
]
