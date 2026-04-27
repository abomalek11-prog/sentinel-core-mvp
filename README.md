# Sentinel Core MVP

> **AI-powered code analysis and automated bug detection/repair system**

🌐 **[Live Demo](https://sentinel-core-frontend-ruddy.vercel.app)** — Try the interactive UI now!

Sentinel Core is a multi-agent system that reads source code, builds a rich
**Code Property Graph (CPG)**, and uses that graph to locate bugs and
generate verified patches — automatically.

---

## Architecture

```
Source Code
    │
    ▼
┌─────────────┐
│  CodeParser  │  Tree-sitter → AST
└──────┬──────┘
       │ ParsedFile
       ▼
┌──────────────┐
│  CPGBuilder  │  AST → NetworkX DiGraph (CPG)
└──────┬───────┘
       │ CodePropertyGraph
       ▼
┌──────────────┐
│ Bug Detector │  Agent: analyses CPG for defect patterns
└──────┬───────┘
       │ Bug reports
       ▼
┌─────────────────┐
│ Patch Generator │  Agent: generates candidate fixes
└──────┬──────────┘
       │ Patches
       ▼
┌───────────┐
│  Sandbox  │  Executes & validates patches safely
└───────────┘
```

## Project Layout

```
sentinel-core-mvp/
├── src/sentinel_core/
│   ├── config.py          ← Pydantic settings (env-driven)
│   ├── parsing/           ← Tree-sitter parser + AST models
│   ├── gnn/               ← Code Property Graph + NetworkX
│   ├── agents/            ← Bug detector & patch generator agents
│   ├── patching/          ← Patch application engine
│   ├── sandbox/           ← Safe code execution
│   └── utils/             ← Logging (structlog)
├── tests/                 ← pytest test suite
├── docs/                  ← Extended documentation
├── examples/              ← Usage examples
├── main.py                ← Demo pipeline entry point
└── pyproject.toml
```

## Quick Start

```bash
# 1. Clone and enter the project
git clone <repo-url>
cd sentinel-core-mvp

# 2. Install dependencies (uses uv)
uv sync

# 3. Copy environment config
cp .env.example .env

# 4. Run the demo pipeline
uv run python main.py
```

## Development

```bash
# Run tests
uv run pytest -v

# Lint
uv run ruff check src/

# Type-check
uv run mypy src/

# Format
uv run black src/ tests/
```

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| 1 — Foundation | ✅ | Parser, CPG, logging, config |
| 2 — Agents | 🔜 | Bug detector & patch generator |
| 3 — Sandbox | 🔜 | Safe patch execution & verification |
| 4 — CLI | 🔜 | Command-line interface |
| 5 — API | 🔜 | REST API / IDE plugin |

## License

MIT — see `LICENSE` for details.
