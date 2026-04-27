# Sandbox Module Documentation

## Overview

The **Sandbox Module** (`sentinel_core.sandbox`) provides safe, isolated execution of Python code with strict resource limits and timeout enforcement. It is the critical component that enables **Sentinel Core** to verify that auto-generated patches are functional and don't break existing code.

---

## Architecture

### Core Components

#### 1. **SandboxExecutor** (Main Class)

The primary interface for executing code in isolation.

```python
from sentinel_core.sandbox import SandboxExecutor

executor = SandboxExecutor(timeout_sec=15)  # Optional: override timeout
result = executor.execute("print('Hello')")
```

**Features:**
- Runs code in a subprocess (OS-level isolation)
- Enforces strict timeout limits (default: 15 seconds)
- Captures stdout/stderr for analysis
- Validates Python syntax before execution
- Sanitizes environment variables (removes API keys, tokens)
- Tracks execution duration and resource usage

#### 2. **ExecutionResult** (Result Object)

Structured result from code execution.

```python
@dataclass
class ExecutionResult:
    success: bool                    # True if exit code 0 and no timeout
    exit_code: Optional[int]         # Process exit code
    stdout: str                      # Captured standard output
    stderr: str                      # Captured standard error
    exception: Optional[Exception]   # Exception raised (if any)
    duration_sec: float              # Execution time in seconds
    peak_memory_mb: Optional[float]  # Memory usage (if tracked)
```

#### 3. **Exception Hierarchy**

- `SandboxError` — Base exception for all sandbox errors
- `ExecutionTimeout` — Code exceeded timeout limit
- `ExecutionFailure` — Code exited with non-zero status
- `MemoryLimitExceeded` — Reserved for future use

---

## Configuration

The Sandbox respects the **Sentinel Core configuration** system:

```python
from sentinel_core.config import settings

settings.sandbox_timeout = 30           # Max execution time (seconds)
settings.sandbox_max_memory_mb = 512    # Max memory limit (MB)
```

**Environment Variables (.env):**
```
SENTINEL_SANDBOX_TIMEOUT=30
SENTINEL_SANDBOX_MAX_MEMORY_MB=512
```

---

## Usage Examples

### Example 1: Basic Execution

```python
from sentinel_core.sandbox import SandboxExecutor

executor = SandboxExecutor()
result = executor.execute("print('Hello, World!')")

if result.success:
    print(f"Output: {result.stdout}")
    print(f"Execution time: {result.duration_sec:.3f}s")
else:
    print(f"Error: {result.exception}")
```

### Example 2: Code Validation

```python
executor = SandboxExecutor()

# Validate syntax without executing
is_valid, error_msg = executor.validate_code(user_code)
if not is_valid:
    print(f"Syntax error: {error_msg}")
else:
    result = executor.execute(user_code)
```

### Example 3: File Execution

```python
executor = SandboxExecutor()
result = executor.execute_file("path/to/script.py")

assert result.success, f"Script failed: {result.stderr}"
```

### Example 4: Patch Verification (Integration with Agents)

```python
from sentinel_core.sandbox import SandboxExecutor, ExecutionTimeout

# Original vulnerable code
original = "result = eval(user_input)"

# Patched code (proposed fix)
patch = "result = ast.literal_eval(user_input)"

# Verify the patch works
executor = SandboxExecutor(timeout_sec=5)
validation_code = f"""
import ast
user_input = "1 + 1"
{patch}
print(f"Result: {{result}}")
"""

result = executor.execute(validation_code)
if result.success:
    print("✓ Patch verified!")
else:
    print(f"✗ Patch failed: {result.exception}")
```

### Example 5: Convenience Function

```python
from sentinel_core.sandbox import execute_code

# Quick one-off execution
result = execute_code("x = 1 + 1; print(x)", timeout_sec=5)
assert result.success
```

---

## Security Features

### 1. **Subprocess Isolation**
Code runs in a completely separate process, isolated from the main Sentinel process.

### 2. **Timeout Enforcement**
Prevents infinite loops and resource exhaustion:
```python
# Code that times out
executor = SandboxExecutor(timeout_sec=1)
result = executor.execute("""
while True:
    pass
""")
assert not result.success
assert isinstance(result.exception, ExecutionTimeout)
```

### 3. **Environment Sanitization**
Strips sensitive environment variables before subprocess execution:
```python
# Sensitive keys removed: API_KEY, TOKEN, SECRET, AWS_*, GITHUB_*, etc.
# Safe keys preserved (PATH, HOME, etc.)
```

### 4. **Syntax Validation**
Catches syntax errors before execution:
```python
is_valid, error = executor.validate_code("x = 1 +")  # Invalid
assert not is_valid
```

---

## Integration with Agent Pipeline

The Sandbox Module is designed to integrate seamlessly with the **Multi-Agent Pipeline**:

### 1. **VerifyAgent** Uses Sandbox
The `VerifyAgent` (in `agents/nodes.py`) uses the Sandbox to test patches:

```python
# In VerifyAgent.run()
from sentinel_core.sandbox import execute_code

test_code = generate_test_for_patch(patch)
result = execute_code(test_code, timeout_sec=settings.sandbox_timeout)

if result.success:
    verification_results.append({
        "patch_id": patch.id,
        "verified": True,
        "test_output": result.stdout,
    })
```

### 2. **Patch Testing Workflow**
```
PatchGeneratorAgent
        ↓
    (generates patch)
        ↓
VerifyAgent + Sandbox
        ↓
    (tests in isolation)
        ↓
    Confidence Score
```

---

## Testing

**Test File:** `tests/test_sandbox.py`

**Coverage:** 29 comprehensive tests covering:
- Basic execution (print, arithmetic, multi-line code)
- Error handling (syntax errors, exceptions, non-zero exit)
- Timeouts (exceeded, within limit)
- Output capture (stdout, stderr)
- File execution and validation
- Environment sanitization
- Edge cases (empty code, large output, special characters)
- Configuration integration

**Run Tests:**
```bash
pytest tests/test_sandbox.py -v
```

**Current Status:** ✅ **All 71 tests pass** (29 sandbox + 42 existing)

---

## Performance Characteristics

| Operation | Typical Duration |
|-----------|------------------|
| Simple print | 0.01 - 0.05s |
| Arithmetic/logic | 0.02 - 0.1s |
| Module import | 0.1 - 0.3s |
| File I/O | 0.05 - 0.5s |
| Timeout detection | Up to timeout configured |

---

## Limitations & Future Enhancements

### Current Limitations:
1. ⚠️ Memory limits are configured but not enforced via `resource` module (planned)
2. ⚠️ No Windows job object support yet (uses subprocess timeout instead)
3. ⚠️ CPU limits not enforced (can add with `psutil`)

### Future Enhancements:
1. 📝 Add memory enforcement via `resource` module (Unix-like systems)
2. 📝 Add CPU/thread limits
3. 📝 Add Windows job object support for resource limits
4. 📝 Add output size limits (prevent OOM on large outputs)
5. 📝 Add network blocking (prevent network access from sandbox)
6. 📝 Integration with container-based sandboxing (Docker)

---

## Best Practices

### ✅ Do:
- ✓ Validate code syntax before execution
- ✓ Set appropriate timeout limits
- ✓ Handle `ExecutionTimeout` exceptions
- ✓ Use the convenience function for one-off executions
- ✓ Log execution results for debugging

### ❌ Don't:
- ✗ Trust untrusted code without sandbox
- ✗ Assume memory limits are enforced (future work)
- ✗ Run network requests in production without networking control
- ✗ Ignore timeout exceptions

---

## Example: Complete Workflow

```python
from sentinel_core.sandbox import SandboxExecutor, ExecutionTimeout
from sentinel_core.parsing import CodeParser
from sentinel_core.gnn import CPGBuilder
from sentinel_core.agents.graph import build_graph, run_pipeline

# Step 1: Parse vulnerable code
parser = CodeParser()
parsed = parser.parse_file("vulnerable_script.py")

# Step 2: Build CPG
cpg_builder = CPGBuilder()
cpg = cpg_builder.build(parsed)

# Step 3: Run agent pipeline
graph = build_graph()
final_state = run_pipeline(
    code=parsed.source,
    file_path="vulnerable_script.py",
    language="python",
)

# Step 4: Verify patches in sandbox
executor = SandboxExecutor(timeout_sec=10)
for patch in final_state.proposed_patches:
    patched_code = apply_patch(parsed.source, patch)
    result = executor.execute(patched_code)
    
    if result.success:
        print(f"✓ Patch {patch.id} verified!")
    else:
        print(f"✗ Patch {patch.id} failed: {result.exception}")
```

---

## FAQ

**Q: Can I run arbitrary code safely?**
A: The Sandbox provides OS-level process isolation and timeout enforcement, making it reasonably safe for code analysis. However, do not trust untrusted code completely — the sandbox is a safety layer, not a complete guarantee.

**Q: What languages are supported?**
A: Currently, **Python only**. Other languages can be added in future phases.

**Q: How do I set custom timeout per execution?**
A: Pass `timeout_sec` to `SandboxExecutor()`:
```python
executor = SandboxExecutor(timeout_sec=5)  # 5 second timeout
```

**Q: How are environment variables handled?**
A: The Sandbox sanitizes the environment, removing sensitive keys (API keys, tokens) while preserving safe values.

**Q: Can I access files in the sandbox?**
A: Yes, the sandbox has access to the filesystem (working directory). This is intentional for patch testing.

---

## References

- **Configuration:** `src/sentinel_core/config.py`
- **Main Module:** `src/sentinel_core/sandbox/executor.py`
- **Public API:** `src/sentinel_core/sandbox/__init__.py`
- **Tests:** `tests/test_sandbox.py`
- **Integration:** `src/sentinel_core/agents/nodes.py` (VerifyAgent)
