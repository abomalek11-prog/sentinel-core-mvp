# AGENTS.md — Sentinel Core Guide for AI Agents

This file provides structured guidance for AI coding agents (Claude, Gemini,
GPT-4, etc.) working inside this repository.  Read it **before** making any
changes.

---

## Project Purpose

Sentinel Core is a **static-analysis + multi-agent bug-repair** system.
It ingests Python source code, builds a Code Property Graph (CPG), and uses
specialised agents to detect bugs and generate verified patches.

---

## Repository Map

| Path | Role |
|------|------|
| `src/sentinel_core/config.py` | Central settings — edit to add new config knobs |
| `src/sentinel_core/parsing/` | Tree-sitter parsing; extend here for new languages |
| `src/sentinel_core/gnn/` | CPG construction; extend `_NODE_TYPE_MAP` for new AST types |
| `src/sentinel_core/agents/` | Agent interfaces — **next phase to implement** |
| `src/sentinel_core/patching/` | Patch application engine — **next phase** |
| `src/sentinel_core/sandbox/` | Sandboxed execution — **next phase** |
| `src/sentinel_core/utils/` | Shared utilities (logging is the only one so far) |
| `tests/` | pytest test suite — always add tests for new modules |
| `main.py` | CLI/demo entry point |

---

## Coding Conventions

### Style
- **Python ≥ 3.11**, type-annotated, `from __future__ import annotations`
- Line length: **100 characters** (`ruff` enforces this)
- Use `dataclasses` for internal data models; `pydantic` only for
  config/settings and models that need validation.
- Imports: stdlib → third-party → local (enforced by `ruff I`)

### Logging
Always use the project logger — **never** `print()` in library code:

```python
from sentinel_core.utils.logging import get_logger
log = get_logger(__name__)
log.info("event_name", key=value)   # structured key=value pairs
```

### Configuration
Read settings from the singleton — **never** hardcode values:

```python
from sentinel_core.config import settings
timeout = settings.sandbox_timeout
```

### Error Handling
- Raise domain-specific exceptions (e.g. `ParseError`) instead of bare `Exception`.
- Log errors with context before re-raising: `log.error("msg", exc_info=True)`.

---

## Adding a New Language

1. Install the `tree-sitter-<lang>` package and add it to `pyproject.toml`.
2. Register it in `src/sentinel_core/parsing/parser.py`:
   ```python
   import tree_sitter_javascript as tsjs
   _LANGUAGE_MAP["javascript"] = Language(tsjs.language())
   ```
3. Extend `_NODE_TYPE_MAP` in `gnn/graph_builder.py` with the new language's
   AST node types.
4. Add a matching `ext_map` entry in `_detect_language()` in `parser.py`.
5. Write tests in `tests/test_parsing.py`.

---

## Adding a New Agent

Agents live in `src/sentinel_core/agents/`.  Each agent must:

1. Inherit from `BaseAgent` (to be implemented in Phase 2).
2. Accept a `CodePropertyGraph` as input.
3. Return a typed result model (e.g. `AnalysisResult`, `PatchSuggestion`).
4. Be stateless — no mutable class-level state.

---

## Running Checks

```bash
uv run pytest -v              # all tests
uv run ruff check src/        # linting
uv run mypy src/               # type checking
uv run black src/ tests/       # formatting
```

All checks must pass before opening a PR.

---

## What NOT to Do

- ❌ Do **not** import from `sentinel_core.agents` in `parsing` or `gnn` (avoid cycles).
- ❌ Do **not** call `settings = Settings()` — use the module-level singleton.
- ❌ Do **not** catch bare `Exception` without logging.
- ❌ Do **not** write files outside `SENTINEL_WORKSPACE_ROOT` in production code.
- ❌ Do **not** run untrusted code outside the `sandbox` module.
