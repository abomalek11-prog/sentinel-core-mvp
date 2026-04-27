#!/usr/bin/env python
"""
Sandbox Module Demo
Demonstrates safe code execution with Sentinel Core's Sandbox.
"""

from __future__ import annotations

from sentinel_core.sandbox import SandboxExecutor, ExecutionTimeout, execute_code
from sentinel_core.utils.logging import get_logger

log = get_logger(__name__)


def demo_basic_execution() -> None:
    """Demo 1: Basic code execution."""
    print("\n" + "=" * 70)
    print("DEMO 1: Basic Code Execution")
    print("=" * 70)

    executor = SandboxExecutor()
    code = """
print("Hello from Sandbox!")
x = [1, 2, 3, 4, 5]
print(f"Sum: {sum(x)}")
"""
    result = executor.execute(code)
    print(f"Success: {result.success}")
    print(f"Exit Code: {result.exit_code}")
    print(f"Duration: {result.duration_sec:.3f}s")
    print(f"Output:\n{result.stdout}")


def demo_error_handling() -> None:
    """Demo 2: Error handling."""
    print("\n" + "=" * 70)
    print("DEMO 2: Error Handling")
    print("=" * 70)

    executor = SandboxExecutor()
    code = """
x = 1
y = 0
try:
    result = x / y
except ZeroDivisionError as e:
    print(f"Caught error: {e}")
"""
    result = executor.execute(code)
    print(f"Success: {result.success}")
    print(f"Output:\n{result.stdout}")


def demo_timeout() -> None:
    """Demo 3: Timeout enforcement."""
    print("\n" + "=" * 70)
    print("DEMO 3: Timeout Enforcement")
    print("=" * 70)

    executor = SandboxExecutor(timeout_sec=2)
    code = """
import time
print("Starting long operation...")
time.sleep(5)
print("This will not print")
"""
    result = executor.execute(code)
    print(f"Success: {result.success}")
    print(f"Exception: {type(result.exception).__name__}")
    print(f"Message: {result.exception}")
    print(f"Duration: {result.duration_sec:.3f}s")


def demo_code_validation() -> None:
    """Demo 4: Code validation."""
    print("\n" + "=" * 70)
    print("DEMO 4: Code Validation (Syntax Check)")
    print("=" * 70)

    executor = SandboxExecutor()

    # Valid code
    print("\nValidating good code...")
    is_valid, error = executor.validate_code("x = 1 + 1")
    print(f"Valid: {is_valid}, Error: {error}")

    # Invalid code
    print("\nValidating bad code...")
    is_valid, error = executor.validate_code("x = 1 +")
    print(f"Valid: {is_valid}, Error: {error}")


def demo_convenience_function() -> None:
    """Demo 5: Convenience function."""
    print("\n" + "=" * 70)
    print("DEMO 5: Convenience Function")
    print("=" * 70)

    code = """
import json
data = {"name": "Sentinel", "version": "0.1"}
print(json.dumps(data, indent=2))
"""
    result = execute_code(code, timeout_sec=5)
    print(f"Success: {result.success}")
    print(f"Output:\n{result.stdout}")


def demo_patch_verification() -> None:
    """Demo 6: Using Sandbox to verify patches."""
    print("\n" + "=" * 70)
    print("DEMO 6: Patch Verification Use Case")
    print("=" * 70)

    print("\nOriginal code (with eval - UNSAFE):")
    original_code = """
user_input = "1 + 2"
result = eval(user_input)
print(f"Result: {result}")
"""
    print(original_code)

    print("\nPatched code (with ast.literal_eval - SAFE):")
    patched_code = """
import ast
user_input = "1 + 2"
result = ast.literal_eval(user_input)
print(f"Result: {result}")
"""
    print(patched_code)

    print("\nExecuting patched code in sandbox...")
    executor = SandboxExecutor()
    result = executor.execute(patched_code)

    print(f"Patch verification success: {result.success}")
    if result.success:
        print(f"Output: {result.stdout.strip()}")
        print("✓ Patch verified safe!")
    else:
        print(f"Error: {result.exception}")


def main() -> None:
    """Run all demos."""
    print("\n" + "#" * 70)
    print("# SENTINEL CORE — SANDBOX MODULE DEMO")
    print("#" * 70)

    demo_basic_execution()
    demo_error_handling()
    demo_timeout()
    demo_code_validation()
    demo_convenience_function()
    demo_patch_verification()

    print("\n" + "#" * 70)
    print("# DEMO COMPLETE")
    print("#" * 70 + "\n")


if __name__ == "__main__":
    main()
