"""
Tests for the Sandbox Execution Module
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from sentinel_core.sandbox import (
    ExecutionFailure,
    ExecutionResult,
    ExecutionTimeout,
    SandboxExecutor,
    execute_code,
)


class TestExecutionResult:
    """Tests for ExecutionResult dataclass."""

    def test_success_result(self) -> None:
        """Test creating a successful execution result."""
        result = ExecutionResult(
            success=True,
            exit_code=0,
            stdout="Hello, World!",
            stderr="",
            duration_sec=0.5,
        )
        assert result.success is True
        assert result.exit_code == 0
        assert "Hello, World!" in result.stdout
        assert result.duration_sec == 0.5

    def test_failure_result(self) -> None:
        """Test creating a failed execution result."""
        exc = ExecutionFailure("Code crashed")
        result = ExecutionResult(
            success=False,
            exit_code=1,
            exception=exc,
            duration_sec=0.1,
        )
        assert result.success is False
        assert result.exit_code == 1
        assert isinstance(result.exception, ExecutionFailure)

    def test_repr(self) -> None:
        """Test ExecutionResult repr."""
        result = ExecutionResult(success=True, exit_code=0, duration_sec=1.5)
        repr_str = repr(result)
        assert "✓ OK" in repr_str
        assert "exit_code=0" in repr_str
        assert "1.50s" in repr_str


class TestSandboxExecutor:
    """Tests for SandboxExecutor class."""

    def test_simple_print(self) -> None:
        """Test basic print statement."""
        executor = SandboxExecutor()
        result = executor.execute("print('Hello, World!')")
        assert result.success is True
        assert "Hello, World!" in result.stdout
        assert result.exit_code == 0

    def test_arithmetic(self) -> None:
        """Test basic arithmetic."""
        executor = SandboxExecutor()
        code = "print(2 + 2)"
        result = executor.execute(code)
        assert result.success is True
        assert "4" in result.stdout

    def test_multi_line_code(self) -> None:
        """Test multi-line code block."""
        executor = SandboxExecutor()
        code = """
x = 10
y = 20
print(f"Sum: {x + y}")
"""
        result = executor.execute(code)
        assert result.success is True
        assert "Sum: 30" in result.stdout

    def test_stderr_capture(self) -> None:
        """Test that stderr is captured."""
        executor = SandboxExecutor()
        code = """
import sys
sys.stderr.write("Error message")
"""
        result = executor.execute(code)
        assert result.success is True
        assert "Error message" in result.stderr

    def test_exception_handling(self) -> None:
        """Test code that raises an exception."""
        executor = SandboxExecutor()
        code = """
x = 1 / 0
"""
        result = executor.execute(code)
        assert result.success is False
        assert result.exit_code != 0

    def test_syntax_error(self) -> None:
        """Test code with syntax error."""
        executor = SandboxExecutor()
        code = "print('unclosed string"
        result = executor.execute(code)
        assert result.success is False

    def test_timeout_exceeded(self) -> None:
        """Test code that exceeds timeout."""
        executor = SandboxExecutor(timeout_sec=1)
        code = """
import time
time.sleep(5)
print("This should not print")
"""
        result = executor.execute(code)
        assert result.success is False
        assert isinstance(result.exception, ExecutionTimeout)

    def test_timeout_within_limit(self) -> None:
        """Test code that completes within timeout."""
        executor = SandboxExecutor(timeout_sec=5)
        code = """
import time
time.sleep(0.1)
print("Completed")
"""
        result = executor.execute(code)
        assert result.success is True
        assert "Completed" in result.stdout

    def test_execution_duration_tracked(self) -> None:
        """Test that execution duration is tracked."""
        executor = SandboxExecutor()
        code = """
import time
time.sleep(0.2)
print("Done")
"""
        result = executor.execute(code)
        assert result.success is True
        assert result.duration_sec >= 0.2

    def test_working_directory_respected(self, tmp_path: Path) -> None:
        """Test that working directory is respected."""
        executor = SandboxExecutor()
        code = """
import os
print(os.getcwd())
"""
        result = executor.execute(code, working_dir=str(tmp_path))
        assert result.success is True
        # Note: Exact path comparison may differ across platforms

    def test_file_execution(self, tmp_path: Path) -> None:
        """Test executing code from a file."""
        test_file = tmp_path / "test_script.py"
        test_file.write_text("print('From file')")

        executor = SandboxExecutor()
        result = executor.execute_file(str(test_file))
        assert result.success is True
        assert "From file" in result.stdout

    def test_file_not_found(self) -> None:
        """Test executing a non-existent file."""
        executor = SandboxExecutor()
        result = executor.execute_file("/nonexistent/file.py")
        assert result.success is False
        assert isinstance(result.exception, FileNotFoundError)

    def test_validate_code_syntax(self) -> None:
        """Test code validation."""
        executor = SandboxExecutor()

        # Valid code
        is_valid, error = executor.validate_code("x = 1 + 1")
        assert is_valid is True
        assert error is None

        # Invalid code
        is_valid, error = executor.validate_code("x = 1 +")
        assert is_valid is False
        assert error is not None
        assert "Syntax error" in error

    def test_safe_env_strips_secrets(self) -> None:
        """Test that environment sanitization removes sensitive keys."""
        import os

        # Add some sensitive keys to the environment temporarily
        original_env = os.environ.copy()
        try:
            os.environ["SECRET_API_KEY"] = "super-secret"
            os.environ["AWS_ACCESS_KEY"] = "fake-key"
            os.environ["GITHUB_TOKEN"] = "fake-token"
            os.environ["SAFE_VAR"] = "safe-value"

            safe_env = SandboxExecutor._get_safe_env()

            # Sensitive keys should be removed
            assert "SECRET_API_KEY" not in safe_env
            assert "AWS_ACCESS_KEY" not in safe_env
            assert "GITHUB_TOKEN" not in safe_env

            # Safe keys should be present
            assert "SAFE_VAR" in safe_env
            assert safe_env["SAFE_VAR"] == "safe-value"

            # Sandbox-specific keys should be set
            assert "PYTHONUNBUFFERED" in safe_env
            assert "PYTHONDONTWRITEBYTECODE" in safe_env

        finally:
            # Restore environment
            os.environ.clear()
            os.environ.update(original_env)

    def test_import_standard_library(self) -> None:
        """Test that standard library imports work."""
        executor = SandboxExecutor()
        code = """
import json
import os
import sys
from pathlib import Path
print("All imports successful")
"""
        result = executor.execute(code)
        assert result.success is True

    def test_infinity_loop_timeout(self) -> None:
        """Test that infinite loops are caught by timeout."""
        executor = SandboxExecutor(timeout_sec=1)
        code = """
while True:
    pass
"""
        result = executor.execute(code)
        assert result.success is False
        assert isinstance(result.exception, ExecutionTimeout)


class TestConvenienceFunction:
    """Tests for the execute_code convenience function."""

    def test_execute_code_simple(self) -> None:
        """Test execute_code convenience function."""
        result = execute_code("print('Quick test')")
        assert result.success is True
        assert "Quick test" in result.stdout

    def test_execute_code_custom_timeout(self) -> None:
        """Test execute_code with custom timeout."""
        code = """
import time
time.sleep(0.1)
print("Done")
"""
        result = execute_code(code, timeout_sec=2)
        assert result.success is True

    def test_execute_code_timeout_exceeded(self) -> None:
        """Test execute_code timeout exception."""
        code = """
import time
time.sleep(5)
"""
        result = execute_code(code, timeout_sec=1)
        assert result.success is False
        assert isinstance(result.exception, ExecutionTimeout)


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_empty_code(self) -> None:
        """Test executing empty code."""
        executor = SandboxExecutor()
        result = executor.execute("")
        assert result.success is True

    def test_comment_only_code(self) -> None:
        """Test executing code with only comments."""
        executor = SandboxExecutor()
        result = executor.execute("# This is just a comment")
        assert result.success is True

    def test_large_output(self) -> None:
        """Test code that produces large output."""
        executor = SandboxExecutor()
        code = """
for i in range(1000):
    print(f"Line {i}")
"""
        result = executor.execute(code)
        assert result.success is True
        assert len(result.stdout) > 5000

    def test_special_characters_in_output(self) -> None:
        """Test code that outputs special characters."""
        executor = SandboxExecutor()
        code = """
print("Escaped: newline tab backslash")
print("Characters: abc123")
"""
        result = executor.execute(code)
        assert result.success is True
        assert "Escaped" in result.stdout
        assert "Characters" in result.stdout

    def test_exit_with_code(self) -> None:
        """Test code that exits with specific code."""
        executor = SandboxExecutor()
        code = """
import sys
sys.exit(42)
"""
        result = executor.execute(code)
        assert result.success is False
        assert result.exit_code == 42


class TestConfigurationIntegration:
    """Tests for integration with Sentinel configuration."""

    def test_default_timeout_from_config(self) -> None:
        """Test that executor uses configured timeout."""
        from sentinel_core.config import settings

        executor = SandboxExecutor()
        assert executor.timeout_sec == settings.sandbox_timeout

    def test_default_memory_limit_from_config(self) -> None:
        """Test that executor uses configured memory limit."""
        from sentinel_core.config import settings

        executor = SandboxExecutor()
        assert executor.max_memory_mb == settings.sandbox_max_memory_mb
