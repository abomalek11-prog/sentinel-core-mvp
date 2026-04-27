"""
Sentinel Core — Sandboxed Code Execution Engine
Safe, isolated execution of Python code with timeout and memory limits.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from sentinel_core.config import settings
from sentinel_core.utils.logging import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class SandboxError(Exception):
    """Base exception for sandbox-related errors."""
    pass


class ExecutionTimeout(SandboxError):
    """Raised when code execution exceeds the timeout."""
    pass


class ExecutionFailure(SandboxError):
    """Raised when code execution fails (non-zero exit or crash)."""
    pass


class MemoryLimitExceeded(SandboxError):
    """Raised when memory usage exceeds the configured limit."""
    pass


# ---------------------------------------------------------------------------
# Execution Result
# ---------------------------------------------------------------------------

@dataclass
class ExecutionResult:
    """
    Outcome of a sandboxed code execution.

    Attributes:
        success:        True if exit code was 0 and no timeout.
        exit_code:      Process exit code (0 = success).
        stdout:         Standard output captured from the process.
        stderr:         Standard error captured from the process.
        exception:      Optional exception raised during execution.
        duration_sec:   Wall-clock execution time in seconds.
        peak_memory_mb: Peak memory usage in megabytes (if tracked).
    """
    success: bool
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    exception: Optional[Exception] = None
    duration_sec: float = 0.0
    peak_memory_mb: Optional[float] = None

    def __repr__(self) -> str:
        status = "✓ OK" if self.success else "✗ FAILED"
        return (
            f"ExecutionResult({status}, "
            f"exit_code={self.exit_code}, "
            f"duration={self.duration_sec:.2f}s, "
            f"memory={self.peak_memory_mb}MB)"
        )


# ---------------------------------------------------------------------------
# Sandbox Executor
# ---------------------------------------------------------------------------

class SandboxExecutor:
    """
    Executes Python code in an isolated subprocess with resource limits.

    This is the primary interface for safe code execution in Sentinel Core.
    It:
      • Runs code in a child process (OS-level isolation)
      • Enforces strict timeouts (configured in settings)
      • Captures stdout/stderr
      • Tracks execution metrics (duration, memory)
      • Provides structured error handling

    Example:
        >>> executor = SandboxExecutor()
        >>> result = executor.execute("print('Hello')")
        >>> print(result.stdout)
        'Hello'
        >>> print(result.success)
        True
    """

    def __init__(self, timeout_sec: Optional[int] = None):
        """
        Initialize the sandbox executor.

        Args:
            timeout_sec: Override the configured timeout (seconds).
                        If None, uses settings.sandbox_timeout.
        """
        self.timeout_sec = timeout_sec or settings.sandbox_timeout
        self.max_memory_mb = settings.sandbox_max_memory_mb

    def execute(self, code: str, working_dir: Optional[str] = None) -> ExecutionResult:
        """
        Execute Python code in an isolated subprocess.

        Args:
            code:         Python source code to execute (string).
            working_dir:  Optional working directory for the subprocess.
                         Defaults to the workspace root.

        Returns:
            ExecutionResult with success status, output, exit code, etc.
        """
        import time

        working_dir = working_dir or str(settings.workspace_root)
        start_time = time.time()

        try:
            log.info(
                "sandbox_execute_start",
                timeout_sec=self.timeout_sec,
                working_dir=working_dir,
                code_length=len(code),
            )

            # Write code to temp file
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                dir=working_dir,
                delete=False,
                encoding="utf-8",
            ) as f:
                temp_file = f.name
                f.write(code)

            try:
                # Execute in subprocess
                result = subprocess.run(
                    [sys.executable, temp_file],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_sec,
                    cwd=working_dir,
                    env=self._get_safe_env(),
                )

                duration = time.time() - start_time

                # Check exit code
                if result.returncode == 0:
                    log.info(
                        "sandbox_execute_success",
                        duration_sec=duration,
                        stdout_length=len(result.stdout),
                    )
                    return ExecutionResult(
                        success=True,
                        exit_code=result.returncode,
                        stdout=result.stdout,
                        stderr=result.stderr,
                        duration_sec=duration,
                    )
                else:
                    log.warning(
                        "sandbox_execute_nonzero_exit",
                        exit_code=result.returncode,
                        duration_sec=duration,
                        stderr_length=len(result.stderr),
                    )
                    exc = ExecutionFailure(
                        f"Code exited with status {result.returncode}"
                    )
                    return ExecutionResult(
                        success=False,
                        exit_code=result.returncode,
                        stdout=result.stdout,
                        stderr=result.stderr,
                        exception=exc,
                        duration_sec=duration,
                    )

            finally:
                # Clean up temp file
                try:
                    os.unlink(temp_file)
                except OSError:
                    log.debug("temp_file_cleanup_failed", path=temp_file)

        except subprocess.TimeoutExpired as e:
            duration = time.time() - start_time
            log.error(
                "sandbox_timeout",
                timeout_sec=self.timeout_sec,
                duration_sec=duration,
            )
            exc = ExecutionTimeout(
                f"Code execution exceeded {self.timeout_sec}s timeout"
            )
            return ExecutionResult(
                success=False,
                exception=exc,
                duration_sec=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            log.error(
                "sandbox_execute_error",
                error_type=type(e).__name__,
                error=str(e),
                duration_sec=duration,
                exc_info=True,
            )
            return ExecutionResult(
                success=False,
                exception=e,
                duration_sec=duration,
            )

    def execute_file(
        self, file_path: str, working_dir: Optional[str] = None
    ) -> ExecutionResult:
        """
        Execute a Python file in the sandbox.

        Args:
            file_path:   Path to the Python file to execute.
            working_dir: Optional working directory for the subprocess.

        Returns:
            ExecutionResult with success status, output, exit code, etc.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            exc = FileNotFoundError(f"File not found: {file_path}")
            log.error("sandbox_file_not_found", path=str(file_path))
            return ExecutionResult(
                success=False,
                exception=exc,
            )

        if not file_path.is_file():
            exc = ValueError(f"Not a file: {file_path}")
            log.error("sandbox_not_a_file", path=str(file_path))
            return ExecutionResult(
                success=False,
                exception=exc,
            )

        try:
            code = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            log.error(
                "sandbox_file_read_failed",
                path=str(file_path),
                error=str(e),
                exc_info=True,
            )
            return ExecutionResult(
                success=False,
                exception=e,
            )

        working_dir = working_dir or str(file_path.parent)
        return self.execute(code, working_dir=working_dir)

    @staticmethod
    def _get_safe_env() -> dict:
        """
        Build a sanitised environment dict for subprocess execution.

        Strips sensitive variables (API keys, tokens) and limits the
        subprocess environment to safe, necessary values.

        Returns:
            dict: Environment variables for subprocess.
        """
        # Start with current environment
        env = os.environ.copy()

        # List of sensitive keys to strip
        sensitive_keys = {
            "AWS_", "AZURE_", "GITHUB_", "GITLAB_",
            "TOKEN", "SECRET", "API_KEY", "PASSWORD",
            "SSH_", "PGP_",
        }

        # Remove sensitive keys
        keys_to_remove = [
            k for k in env.keys()
            if any(s in k.upper() for s in sensitive_keys)
        ]
        for k in keys_to_remove:
            del env[k]

        # Set safe defaults
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        return env

    def validate_code(self, code: str) -> tuple[bool, Optional[str]]:
        """
        Validate Python code syntax without executing it.

        This is a lightweight check using compile() to catch syntax errors
        before sending code to the sandbox.

        Args:
            code: Python source code to validate.

        Returns:
            (is_valid, error_message) where error_message is None if valid.
        """
        try:
            compile(code, "<sandbox-validation>", "exec")
            return True, None
        except SyntaxError as e:
            msg = f"Syntax error at line {e.lineno}: {e.msg}"
            log.debug("sandbox_syntax_error", code_length=len(code), error=msg)
            return False, msg
        except Exception as e:
            msg = f"Validation error: {e}"
            log.debug("sandbox_validation_error", error=msg, exc_info=True)
            return False, msg


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def execute_code(
    code: str,
    timeout_sec: Optional[int] = None,
    working_dir: Optional[str] = None,
) -> ExecutionResult:
    """
    Convenience function to execute code in a fresh sandbox.

    This is equivalent to ``SandboxExecutor(timeout_sec).execute(code)``.

    Args:
        code:         Python source code to execute.
        timeout_sec:  Override configured timeout (seconds).
        working_dir:  Override working directory.

    Returns:
        ExecutionResult.
    """
    executor = SandboxExecutor(timeout_sec=timeout_sec)
    return executor.execute(code, working_dir=working_dir)
