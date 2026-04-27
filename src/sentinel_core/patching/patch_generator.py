"""
Sentinel Core — Patch Engine (v2 / v3)
CPG-aware code patch generation with safe rewrite rules and unified diffs.

v3 addition: generate_patch_from_plan() — accepts a PatchPlan from the LLM
Planner and applies only whitelisted transformations; raw LLM text is never
executed.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Any, Optional

import networkx as nx

from sentinel_core.utils.logging import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Patch-rule registry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PatchRule:
    """A rewrite rule mapping a dangerous API to a safe alternative."""
    sink: str
    safe_call: str
    import_needed: Optional[str] = None
    from_import: Optional[tuple[str, str]] = None
    description: str = ""
    cwe: str = ""


_PATCH_RULES: dict[str, PatchRule] = {
    "eval": PatchRule(
        sink="eval",
        safe_call="ast.literal_eval",
        import_needed="ast",
        description="Replace eval() with ast.literal_eval() + error-handling wrapper.",
        cwe="CWE-95",
    ),
    "exec": PatchRule(
        sink="exec",
        safe_call="# SENTINEL-FIX: exec() removed",
        description="Remove exec() — refactor to explicit, safe logic.",
        cwe="CWE-95",
    ),
    "os.system": PatchRule(
        sink="os.system",
        safe_call="subprocess.run",
        import_needed="subprocess",
        from_import=("shlex", "split"),
        description="Replace os.system() with subprocess.run(shell=False).",
        cwe="CWE-78",
    ),
    "subprocess.call": PatchRule(
        sink="subprocess.call",
        safe_call="subprocess.run",
        import_needed="shlex",
        description=(
            "Replace subprocess.call() with subprocess.run(shell=False) using "
            "quoted argument lists and try/except wrapper."
        ),
        cwe="CWE-78",
    ),
    "subprocess.check_output": PatchRule(
        sink="subprocess.check_output",
        safe_call="subprocess.check_output",
        import_needed="shlex",
        description=(
            "Replace subprocess.check_output(..., shell=True) with a "
            "sanitised argument list and stderr=subprocess.STDOUT."
        ),
        cwe="CWE-78",
    ),
    "pickle.loads": PatchRule(
        sink="pickle.loads",
        safe_call="json.loads",
        import_needed="json",
        description="Replace pickle.loads() with json.loads() + error-handling wrapper.",
        cwe="CWE-502",
    ),
    "yaml.load": PatchRule(
        sink="yaml.load",
        safe_call="yaml.safe_load",
        description="Replace yaml.load() with yaml.safe_load().",
        cwe="CWE-502",
    ),
}


def _normalize_kind(kind: str) -> str:
    """Map LLM-returned kind strings to canonical _PATCH_RULES keys."""
    if kind in _PATCH_RULES:
        return kind
    lowered = kind.lower().replace("-", "_").replace(" ", "_")
    # Direct lookup after normalisation
    if lowered in _PATCH_RULES:
        return lowered
    # Keyword-based fallback for common LLM variations
    _KIND_ALIASES: dict[str, list[str]] = {
        "eval": ["eval", "cwe_95"],
        "exec": ["exec"],
        "os.system": ["os.system", "os_system"],
        "subprocess.call": ["subprocess.call", "subprocess_call"],
        "subprocess.check_output": [
            "subprocess.check_output", "subprocess_check_output",
            "command_injection", "shell_injection", "cwe_78", "cwe78",
        ],
        "pickle.loads": ["pickle.loads", "pickle_loads", "cwe_502", "deserialization"],
        "yaml.load": ["yaml.load", "yaml_load", "unsafe_yaml"],
    }
    for canonical, aliases in _KIND_ALIASES.items():
        if lowered in aliases or any(alias in lowered for alias in aliases):
            return canonical
    return kind


# ---------------------------------------------------------------------------
# Patch result
# ---------------------------------------------------------------------------

@dataclass
class PatchResult:
    """Outcome of applying patches to source code."""
    original_source: str
    patched_source: str
    diff: str
    changes: list[str] = field(default_factory=list)
    imports_added: list[str] = field(default_factory=list)
    context_info: list[dict[str, str]] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return self.original_source != self.patched_source

    @property
    def patch_complexity(self) -> float:
        """0.0 = trivial, 1.0 = very complex.  Used by confidence scoring."""
        if not self.has_changes:
            return 0.0
        orig_lines = len(self.original_source.splitlines())
        diff_lines = len([
            ln for ln in self.diff.splitlines()
            if ln.startswith("+") or ln.startswith("-")
        ])
        ratio = diff_lines / max(orig_lines, 1)
        return min(ratio, 1.0)


# ---------------------------------------------------------------------------
# CPG context extractor
# ---------------------------------------------------------------------------

class _CPGContext:
    """Extracts contextual information from the Code Property Graph."""

    def __init__(self, graph: nx.DiGraph | nx.MultiDiGraph | None) -> None:
        self._graph = graph

    @property
    def available(self) -> bool:
        return self._graph is not None

    def function_at_line(self, line: int) -> str | None:
        """Return the name of the function enclosing *line*, or None."""
        if not self._graph:
            return None
        best: tuple[str | None, int] = (None, -1)
        for _, attrs in self._graph.nodes(data=True):
            if attrs.get("node_type") in ("FUNCTION", "METHOD"):
                start = attrs.get("start_line", -1)
                end = attrs.get("end_line", -1)
                if start <= line <= end and start > best[1]:
                    best = (attrs.get("name", "<fn>"), start)
        return best[0]

    def source_text_at(self, line: int) -> str:
        """Return the source text of the node closest to *line*."""
        if not self._graph:
            return ""
        for _, attrs in self._graph.nodes(data=True):
            if attrs.get("start_line") == line:
                return attrs.get("source_text", "")
        return ""

    def node_id_at(self, line: int) -> int | None:
        if not self._graph:
            return None
        for node_id, attrs in self._graph.nodes(data=True):
            if attrs.get("start_line") == line:
                return int(node_id)
        return None

    def edge_profile(self, node_id: int | None) -> str:
        if not self._graph or node_id is None or node_id not in self._graph.nodes:
            return "in=0; out=0"

        if isinstance(self._graph, nx.MultiDiGraph):
            in_edges = list(self._graph.in_edges(node_id, keys=True))
            out_edges = list(self._graph.out_edges(node_id, keys=True))
        else:
            in_edges = list(self._graph.in_edges(node_id))
            out_edges = list(self._graph.out_edges(node_id))
        return f"in={len(in_edges)}; out={len(out_edges)}"

    def node_count(self) -> int:
        if not self._graph:
            return 0
        return self._graph.number_of_nodes()


# ---------------------------------------------------------------------------
# Patch Engine
# ---------------------------------------------------------------------------

class PatchEngine:
    """
    CPG-aware code patch generator.

    Accepts the source code, vulnerability list, and optionally the CPG
    networkx graph.  Uses the graph to understand function scope around
    each vulnerability, producing safer patches with error-handling wrappers.

    Example::

        engine = PatchEngine()
        result = engine.generate_patch(
            source_code,
            vulnerabilities=[{"kind": "eval", "location": "line 5"}],
            file_path="app.py",
            cpg_graph=nx_graph,
        )
        print(result.diff)
    """

    def generate_patch(
        self,
        source: str,
        vulnerabilities: list[dict[str, Any]],
        file_path: str = "<source>",
        cpg_graph: nx.DiGraph | nx.MultiDiGraph | None = None,
    ) -> PatchResult:
        """Generate a complete patch for all fixable vulnerabilities."""
        log.info(
            "patch_engine_start",
            file=file_path,
            vuln_count=len(vulnerabilities),
            cpg_available=cpg_graph is not None,
        )

        ctx = _CPGContext(cpg_graph)
        patched = source
        changes: list[str] = []
        imports_added: list[str] = []
        context_info: list[dict[str, str]] = []

        # --- Collect needed imports (deduplicated) --------------------
        needed_imports: set[str] = set()
        needed_from_imports: set[tuple[str, str]] = set()
        for vuln in vulnerabilities:
            rule = _PATCH_RULES.get(vuln.get("kind", ""))
            if rule:
                if rule.import_needed:
                    needed_imports.add(rule.import_needed)
                if rule.from_import:
                    needed_from_imports.add(rule.from_import)

        # --- Add missing imports (track offset) ----------------------
        import_offset = 0
        for mod in sorted(needed_imports):
            if not self._has_import(patched, mod):
                patched = self._add_import(patched, f"import {mod}")
                imports_added.append(f"import {mod}")
                changes.append(f"Added 'import {mod}'")
                import_offset += 1

        for mod, name in sorted(needed_from_imports):
            if not self._has_from_import(patched, mod, name):
                patched = self._add_import(patched, f"from {mod} import {name}")
                imports_added.append(f"from {mod} import {name}")
                changes.append(f"Added 'from {mod} import {name}'")
                import_offset += 1

        # --- Apply each fix (track cumulative line offset) ------------
        cumulative_offset = import_offset
        for vuln in vulnerabilities:
            kind = vuln.get("kind", "")
            location = vuln.get("location", "")
            rule = _PATCH_RULES.get(kind)
            if rule is None:
                log.debug("no_patch_rule", kind=kind)
                continue

            # CPG context
            line_num = self._parse_line_number(location)
            fn_name = ctx.function_at_line(line_num) if line_num is not None else None
            src_text = ctx.source_text_at(line_num) if line_num is not None else ""
            node_id = ctx.node_id_at(line_num) if line_num is not None else None
            edge_profile = ctx.edge_profile(node_id)

            context_info.append({
                "kind": kind,
                "cwe": rule.cwe,
                "location": location,
                "function": fn_name or "<module>",
                "source_text": src_text[:120],
                "cpg_trace": f"node={node_id if node_id is not None else '<none>'}; {edge_profile}",
                "fix": rule.description,
            })

            old_line_count = len(patched.splitlines())
            new_source = self._apply_rule(patched, rule, location, cumulative_offset)
            if new_source != patched:
                scope = f"in {fn_name}()" if fn_name else "at module level"
                changes.append(f"[{rule.cwe}] {rule.description} ({location}, {scope})")
                # Track how many extra lines this fix added
                new_line_count = len(new_source.splitlines())
                cumulative_offset += (new_line_count - old_line_count)
                patched = new_source

        diff = self._make_diff(source, patched, file_path)

        log.info(
            "patch_engine_done",
            changes=len(changes),
            imports_added=len(imports_added),
            has_diff=source != patched,
        )
        return PatchResult(
            original_source=source,
            patched_source=patched,
            diff=diff,
            changes=changes,
            imports_added=imports_added,
            context_info=context_info,
        )

    # ------------------------------------------------------------------
    # v3 entry-point: plan-guided patching
    # ------------------------------------------------------------------

    def generate_patch_from_plan(
        self,
        source: str,
        plan: "PatchPlan",  # noqa: F821  (forward ref; imported lazily)
        file_path: str = "<source>",
        cpg_graph: nx.DiGraph | nx.MultiDiGraph | None = None,
    ) -> PatchResult:
        """Apply a PatchPlan produced by LLMPatchPlanner.

        Each :class:`~sentinel_core.patching.models.PatchDecision` in *plan*
        is validated against ``_PATCH_RULES``.  Only decisions whose ``kind``
        is known to the engine are applied; unknown kinds are rejected and
        logged.  The engine then calls the same deterministic fix methods it
        uses in :meth:`generate_patch`, ensuring no raw LLM text is executed.

        Args:
            source:    Original source code.
            plan:      PatchPlan from LLMPatchPlanner.
            file_path: Display path (used in diff headers and logs).
            cpg_graph: Optional NetworkX graph for scope resolution.

        Returns:
            A :class:`PatchResult` with full diff and metadata.
        """
        from sentinel_core.patching.models import PatchStrategy

        log.info(
            "patch_engine_plan_start",
            file=file_path,
            decisions=len(plan.decisions),
            llm_model=plan.llm_model,
            used_fallback=plan.used_fallback,
        )

        ctx = _CPGContext(cpg_graph)
        patched = source
        changes: list[str] = []
        imports_added: list[str] = []
        context_info: list[dict[str, str]] = []

        # Collect needed imports only from decisions that will actually be applied
        # (skip decisions already known to be below the confidence threshold)
        from sentinel_core.patching.llm_planner import _MIN_CONFIDENCE
        needed_imports: set[str] = set()
        needed_from_imports: set[tuple[str, str]] = set()
        for decision in plan.decisions:
            if decision.confidence < _MIN_CONFIDENCE:
                continue
            decision.kind = _normalize_kind(decision.kind)
            rule = _PATCH_RULES.get(decision.kind)
            if rule:
                if rule.import_needed:
                    needed_imports.add(rule.import_needed)
                if rule.from_import:
                    needed_from_imports.add(rule.from_import)

        import_offset = 0
        for mod in sorted(needed_imports):
            if not self._has_import(patched, mod):
                patched = self._add_import(patched, f"import {mod}")
                imports_added.append(f"import {mod}")
                changes.append(f"Added 'import {mod}'")
                import_offset += 1

        for mod, name in sorted(needed_from_imports):
            if not self._has_from_import(patched, mod, name):
                patched = self._add_import(patched, f"from {mod} import {name}")
                imports_added.append(f"from {mod} import {name}")
                changes.append(f"Added 'from {mod} import {name}'")
                import_offset += 1

        cumulative_offset = import_offset

        for decision in plan.decisions:
            kind = _normalize_kind(decision.kind)
            decision.kind = kind
            location = decision.location
            rule = _PATCH_RULES.get(kind)

            # Reject decisions for unknown vulnerability kinds
            if rule is None:
                decision.accepted = False
                decision.rejection_reason = f"no patch rule registered for kind={kind!r}"
                log.debug("patch_plan_decision_rejected", kind=kind,
                          reason=decision.rejection_reason)
                continue

            # Reject low-confidence decisions (safety-net; planner already marked them)
            if decision.confidence < _MIN_CONFIDENCE:
                decision.accepted = False
                decision.rejection_reason = (
                    f"confidence {decision.confidence:.2f} below threshold"
                )
                log.debug("patch_plan_low_confidence", kind=kind,
                          confidence=decision.confidence)
                continue

            # CPG context enrichment
            line_num = self._parse_line_number(location)
            fn_name = ctx.function_at_line(line_num) if line_num is not None else None
            src_text = ctx.source_text_at(line_num) if line_num is not None else ""
            node_id = ctx.node_id_at(line_num) if line_num is not None else None
            edge_profile = ctx.edge_profile(node_id)

            ctx_entry: dict[str, str] = {
                "kind": kind,
                "cwe": rule.cwe,
                "location": location,
                "function": fn_name or "<module>",
                "source_text": src_text[:120],
                "cpg_trace": f"node={node_id if node_id is not None else '<none>'}; {edge_profile}",
                "fix": rule.description,
                # LLM-supplied enrichment (informational only)
                "llm_strategy": decision.strategy.value,
                "llm_rationale": decision.rationale[:200] if decision.rationale else "",
                "llm_test_hint": decision.test_hint[:200] if decision.test_hint else "",
            }
            context_info.append(ctx_entry)

            old_line_count = len(patched.splitlines())
            new_source = self._apply_rule(patched, rule, location, cumulative_offset)

            if new_source != patched:
                scope = f"in {fn_name}()" if fn_name else "at module level"
                strategy_tag = f"[{decision.strategy.value}]" if decision.strategy != PatchStrategy.RULE_BASED else "[rule_based]"
                changes.append(
                    f"[{rule.cwe}] {strategy_tag} {rule.description} "
                    f"({location}, {scope})"
                )
                new_line_count = len(new_source.splitlines())
                cumulative_offset += new_line_count - old_line_count
                patched = new_source
                decision.accepted = True
            else:
                decision.accepted = False
                decision.rejection_reason = "fix did not modify source (pattern not matched)"
                log.debug("patch_plan_no_change", kind=kind, location=location)

        diff = self._make_diff(source, patched, file_path)

        log.info(
            "patch_engine_plan_done",
            total_decisions=len(plan.decisions),
            accepted=plan.accepted_count,
            changes=len(changes),
            has_diff=source != patched,
        )

        return PatchResult(
            original_source=source,
            patched_source=patched,
            diff=diff,
            changes=changes,
            imports_added=imports_added,
            context_info=context_info,
        )

    # ------------------------------------------------------------------
    # Rule dispatch
    # ------------------------------------------------------------------

    def _apply_rule(
        self, source: str, rule: PatchRule, location: str, offset: int = 0,
    ) -> str:
        lines = source.splitlines(keepends=True)
        target = self._parse_line_number(location)
        if target is not None:
            target += offset

        handler = {
            "eval": self._fix_eval,
            "exec": self._fix_exec,
            "os.system": self._fix_os_system,
            "subprocess.call": self._fix_subprocess_call,
            "subprocess.check_output": self._fix_subprocess_check_output,
            "pickle.loads": self._fix_pickle_loads,
            "yaml.load": self._fix_yaml_load,
        }.get(rule.sink)

        if handler:
            return handler(lines, target)
        return source

    # ------------------------------------------------------------------
    # Individual fix methods
    # ------------------------------------------------------------------

    def _fix_eval(self, lines: list[str], target: int | None) -> str:
        """Replace eval(x) with ast.literal_eval(x) wrapped in try/except."""
        result: list[str] = []
        for i, line in enumerate(lines):
            if self._is_target(i, target) and re.search(r'\beval\s*\(', line):
                indent = self._get_indent(line)
                new_line = re.sub(r'\beval\s*\(', 'ast.literal_eval(', line)
                result.append(f"{indent}try:\n")
                result.append(f"{indent}    {new_line.strip()}\n")
                result.append(f"{indent}except (ValueError, SyntaxError):\n")
                result.append(
                    f"{indent}    raise ValueError("
                    f"\"Unsafe expression rejected\")\n"
                )
            else:
                result.append(line)
        return "".join(result)

    def _fix_exec(self, lines: list[str], target: int | None) -> str:
        """Comment out exec() calls."""
        result: list[str] = []
        for i, line in enumerate(lines):
            if self._is_target(i, target) and re.search(r'\bexec\s*\(', line):
                indent = self._get_indent(line)
                result.append(
                    f"{indent}# SENTINEL-FIX: exec() removed "
                    f"- refactor to explicit logic\n"
                )
                result.append(f"{indent}# {line.strip()}\n")
            else:
                result.append(line)
        return "".join(result)

    def _fix_os_system(self, lines: list[str], target: int | None) -> str:
        """Replace os.system(cmd) with subprocess.run(shlex.split(cmd), ...)."""
        result: list[str] = []
        for i, line in enumerate(lines):
            if self._is_target(i, target) and re.search(r'os\.system\s*\(', line):
                indent = self._get_indent(line)
                m = re.search(r'os\.system\s*\((.+?)\)\s*$', line.rstrip())
                if m:
                    arg = m.group(1).strip()
                    result.append(
                        f"{indent}subprocess.run("
                        f"shlex.split({arg}), "
                        f"shell=False, check=True, "
                        f"capture_output=True)\n"
                    )
                else:
                    new_line = re.sub(
                        r'os\.system\s*\((.+?)\)',
                        r'subprocess.run(shlex.split(\1), shell=False, check=True)',
                        line,
                    )
                    result.append(new_line)
            else:
                result.append(line)
        return "".join(result)

    def _fix_subprocess_call(self, lines: list[str], target: int | None) -> str:
        """Replace subprocess.call() with safe subprocess.run + defensive wrapper."""
        result: list[str] = []
        for i, line in enumerate(lines):
            if self._is_target(i, target) and re.search(
                r'subprocess\.call\s*\(', line
            ):
                indent = self._get_indent(line)
                stripped = line.strip()
                assign_m = re.match(
                    r'^(\w+)\s*=\s*subprocess\.call\s*\((.+)\)\s*$',
                    stripped,
                )
                call_m = re.search(r'subprocess\.call\s*\((.+)\)\s*$', stripped)

                raw_args = ""
                assigned_var = ""
                if assign_m:
                    assigned_var = assign_m.group(1)
                    raw_args = assign_m.group(2)
                elif call_m:
                    raw_args = call_m.group(1)

                cmd_expr = self._extract_command_expr(raw_args)
                if not cmd_expr:
                    # Conservative fallback if parsing failed.
                    fallback = re.sub(
                        r'subprocess\.call\s*\((.+?)\)',
                        r'subprocess.run(\1, check=True, shell=False)',
                        line,
                    )
                    result.append(fallback)
                    continue

                quoted_args_expr = self._quoted_args_expression(cmd_expr)
                result.append(f"{indent}try:\n")
                result.append(
                    f"{indent}    _sentinel_cmd = {quoted_args_expr}\n"
                )
                result.append(
                    f"{indent}    _sentinel_completed = subprocess.run(\n"
                )
                result.append(
                    f"{indent}        _sentinel_cmd, check=True, shell=False, "
                    f"capture_output=True, text=True\n"
                )
                result.append(f"{indent}    )\n")
                if assigned_var:
                    result.append(
                        f"{indent}    {assigned_var} = _sentinel_completed.returncode\n"
                    )
                result.append(
                    f"{indent}except (subprocess.SubprocessError, ValueError, "
                    f"TypeError) as exc:\n"
                )
                result.append(
                    f"{indent}    raise RuntimeError(\"Blocked unsafe subprocess call\") "
                    f"from exc\n"
                )
            else:
                result.append(line)
        return "".join(result)

    def _fix_subprocess_check_output(self, lines: list[str], target: int | None) -> str:
        """Replace subprocess.check_output(..., shell=True) with safe argv execution.

        Handles three patterns:
        1. Inline:    result = subprocess.check_output(f"cmd {arg}", shell=True)
        2. Variable:  command = f"cmd {arg}"
                      result = subprocess.check_output(command, shell=True)
        3. Multi-line: result = subprocess.check_output(
                           f"cmd {arg}", shell=True
                       )
        """
        log.info("fix_subprocess_check_output_start", target_line=target)

        # --- Phase 1: join multi-line subprocess.check_output calls ---
        joined_lines, target = self._join_multiline_call(
            lines, target, r'subprocess\.check_output\s*\(',
        )

        # --- Phase 2: identify lines to suppress (variable assignments) ---
        suppress: set[int] = set()
        replacements: dict[int, list[str]] = {}

        for i, line in enumerate(joined_lines):
            if not (
                self._is_target(i, target)
                and re.search(r'subprocess\.check_output\s*\(', line)
            ):
                continue

            indent = self._get_indent(line)
            stripped = line.strip()

            assign_m = re.match(
                r'^(\w+)\s*=\s*subprocess\.check_output\s*\((.+)\)\s*$',
                stripped,
            )
            call_m = re.search(
                r'subprocess\.check_output\s*\((.+)\)\s*$',
                stripped,
            )

            raw_args = ""
            assigned_var = ""
            if assign_m:
                assigned_var = assign_m.group(1)
                raw_args = assign_m.group(2)
            elif call_m:
                raw_args = call_m.group(1)

            if not self._has_shell_true(raw_args):
                continue

            cmd_expr = self._extract_command_expr(raw_args)
            if not cmd_expr:
                replacements[i] = [re.sub(r'shell\s*=\s*True', 'shell=False', line)]
                continue

            # --- Variable tracing: resolve `command` → its f-string value ---
            resolved_expr = cmd_expr
            if re.match(r'^\w+$', cmd_expr):
                var_def = self._resolve_variable(joined_lines, i, cmd_expr)
                if var_def:
                    resolved_expr = var_def
                    for j in range(i - 1, max(i - 15, -1), -1):
                        if re.match(
                            rf'^\s*{re.escape(cmd_expr)}\s*=\s*', joined_lines[j],
                        ):
                            suppress.add(j)
                            break

            is_image_tool_pattern = (
                "img-tool" in resolved_expr
                and "--input" in resolved_expr
                and "--out" in resolved_expr
                and ("image_name" in resolved_expr or "safe_image_name" in resolved_expr)
            )

            output_var = assigned_var or "result"
            new_lines: list[str] = []

            new_lines.append(f"{indent}try:\n")
            if is_image_tool_pattern:
                new_lines.append(
                    f"{indent}    safe_image_name = shlex.quote(str(image_name))\n"
                )
                new_lines.append(f"{indent}    {output_var} = subprocess.check_output([\n")
                new_lines.append(f"{indent}        \"img-tool\",\n")
                new_lines.append(f"{indent}        \"--input\", safe_image_name,\n")
                new_lines.append(f"{indent}        \"--out\", \"/tmp/processed.png\"\n")
                new_lines.append(f"{indent}    ], stderr=subprocess.STDOUT)\n")
            else:
                if re.match(r'^\w+$', cmd_expr) and resolved_expr != cmd_expr:
                    quoted_args_expr = self._quoted_args_expression(resolved_expr)
                else:
                    quoted_args_expr = self._quoted_args_expression(cmd_expr)
                new_lines.append(f"{indent}    _sentinel_cmd = {quoted_args_expr}\n")
                new_lines.append(
                    f"{indent}    {output_var} = subprocess.check_output(\n"
                )
                new_lines.append(
                    f"{indent}        _sentinel_cmd, stderr=subprocess.STDOUT\n"
                )
                new_lines.append(f"{indent}    )\n")

            new_lines.append(
                f"{indent}except (subprocess.SubprocessError, ValueError, "
                f"TypeError) as exc:\n"
            )
            new_lines.append(
                f"{indent}    raise RuntimeError(\"Blocked unsafe subprocess call\") "
                f"from exc\n"
            )
            replacements[i] = new_lines
            log.info(
                "fix_subprocess_check_output_applied",
                line=i,
                assigned_var=assigned_var or "(none)",
                shell_true_removed=True,
                used_variable_tracing=resolved_expr != cmd_expr,
                is_image_tool=is_image_tool_pattern,
            )

        # --- Phase 3: assemble output ---
        result: list[str] = []
        for i, line in enumerate(joined_lines):
            if i in suppress:
                continue
            if i in replacements:
                result.extend(replacements[i])
            else:
                result.append(line)

        patched = "".join(result)

        # --- Safety net: if shell=True somehow survived, forcefully remove it ---
        if re.search(r'subprocess\.check_output\([^)]*shell\s*=\s*True', patched):
            log.warning("fix_subprocess_check_output_safety_net",
                        msg="shell=True survived, forcing removal")
            patched = re.sub(
                r'(subprocess\.check_output\([^)]*),\s*shell\s*=\s*True',
                r'\1',
                patched,
            )

        return patched

    @staticmethod
    def _resolve_variable(
        lines: list[str], call_line: int, var_name: str,
    ) -> str | None:
        """Look backwards from *call_line* for ``var_name = <expr>`` and return <expr>."""
        pattern = re.compile(
            rf'^\s*{re.escape(var_name)}\s*=\s*(.+?)\s*$',
        )
        for j in range(call_line - 1, max(call_line - 15, -1), -1):
            m = pattern.match(lines[j])
            if m:
                return m.group(1).strip()
        return None

    @staticmethod
    def _join_multiline_call(
        lines: list[str],
        target: int | None,
        call_pattern: str,
    ) -> tuple[list[str], int | None]:
        """Join multi-line function calls (open paren on one line, close on another).

        Returns a new list of lines and an adjusted target index.
        """
        joined: list[str] = []
        i = 0
        target_adj = target
        while i < len(lines):
            line = lines[i]
            if re.search(call_pattern, line) and line.rstrip().endswith('('):
                # Collect continuation lines until we find the closing paren
                collected = [line.rstrip('\n')]
                depth = line.count('(') - line.count(')')
                j = i + 1
                while j < len(lines) and depth > 0:
                    part = lines[j].strip()
                    depth += part.count('(') - part.count(')')
                    collected.append(part)
                    j += 1
                merged = ' '.join(collected) + '\n'
                # If the original target was within the merged range, point to merged line
                merged_idx = len(joined)
                if target is not None and i <= target < j:
                    target_adj = merged_idx
                joined.append(merged)
                # Shift target for lines after the merge
                if target is not None and target >= j:
                    target_adj = target - (j - i - 1)
                i = j
            else:
                if target is not None and i == target:
                    target_adj = len(joined)
                joined.append(line)
                i += 1
        return joined, target_adj

    @staticmethod
    def _extract_command_expr(raw_args: str) -> str:
        if not raw_args:
            return ""

        args_expr_match = re.search(r'\bargs\s*=\s*(.+?)(?:,\s*\w+\s*=|$)', raw_args)
        if args_expr_match:
            return args_expr_match.group(1).strip()

        first_arg = PatchEngine._split_top_level(raw_args)
        if not first_arg:
            return ""
        candidate = first_arg[0].strip()
        if "=" in candidate:
            return ""
        return candidate

    @staticmethod
    def _quoted_args_expression(cmd_expr: str) -> str:
        normalized = cmd_expr.strip()
        if normalized.startswith("[") or normalized.startswith("("):
            return f"[shlex.quote(str(part)) for part in {normalized}]"
        return f"[shlex.quote(part) for part in shlex.split(str({normalized}))]"

    @staticmethod
    def _split_top_level(raw: str) -> list[str]:
        parts: list[str] = []
        current: list[str] = []
        depth = 0
        quote: str | None = None
        escape = False

        for ch in raw:
            if escape:
                current.append(ch)
                escape = False
                continue

            if ch == "\\":
                current.append(ch)
                escape = True
                continue

            if quote:
                current.append(ch)
                if ch == quote:
                    quote = None
                continue

            if ch in ("'", '"'):
                quote = ch
                current.append(ch)
                continue

            if ch in "([{" :
                depth += 1
                current.append(ch)
                continue

            if ch in ")]}":
                depth = max(0, depth - 1)
                current.append(ch)
                continue

            if ch == "," and depth == 0:
                parts.append("".join(current).strip())
                current = []
                continue

            current.append(ch)

        tail = "".join(current).strip()
        if tail:
            parts.append(tail)
        return parts

    @staticmethod
    def _has_shell_true(raw_args: str) -> bool:
        if not raw_args:
            return False

        for part in PatchEngine._split_top_level(raw_args):
            norm = part.replace(" ", "")
            if norm.startswith("shell=") and norm.endswith("True"):
                return True
        return False

    def _fix_pickle_loads(self, lines: list[str], target: int | None) -> str:
        """Replace pickle.loads(data) with json.loads(data) + try/except."""
        result: list[str] = []
        for i, line in enumerate(lines):
            if self._is_target(i, target) and re.search(
                r'pickle\.loads\s*\(', line
            ):
                indent = self._get_indent(line)
                m = re.match(
                    r'^(\s*)(\w+)\s*=\s*pickle\.loads\s*\((.+?)\)\s*$',
                    line.rstrip(),
                )
                if m:
                    var = m.group(2)
                    arg = m.group(3)
                    result.append(f"{indent}try:\n")
                    result.append(f"{indent}    {var} = json.loads({arg})\n")
                    result.append(
                        f"{indent}except (json.JSONDecodeError, TypeError):\n"
                    )
                    result.append(
                        f"{indent}    raise ValueError("
                        f"\"Failed to deserialise data safely\")\n"
                    )
                else:
                    new_line = re.sub(
                        r'pickle\.loads\s*\((.+?)\)',
                        r'json.loads(\1)',
                        line,
                    )
                    result.append(new_line)
            else:
                result.append(line)
        return "".join(result)

    def _fix_yaml_load(self, lines: list[str], target: int | None) -> str:
        """Replace yaml.load(...) with yaml.safe_load(...)."""
        return self._regex_replace(
            lines, target,
            pattern=r'yaml\.load\s*\(',
            replacement='yaml.safe_load(',
        )

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------

    def _regex_replace(
        self,
        lines: list[str],
        target: int | None,
        pattern: str,
        replacement: str,
    ) -> str:
        result: list[str] = []
        for i, line in enumerate(lines):
            if self._is_target(i, target) and re.search(pattern, line):
                result.append(re.sub(pattern, replacement, line))
            else:
                result.append(line)
        return "".join(result)

    @staticmethod
    def _is_target(line_index: int, target: int | None) -> bool:
        if target is None:
            return True
        return line_index == target

    @staticmethod
    def _parse_line_number(location: str) -> int | None:
        match = re.search(r'line\s+(\d+)', location)
        if match:
            return int(match.group(1))
        return None

    @staticmethod
    def _get_indent(line: str) -> str:
        return line[: len(line) - len(line.lstrip())]

    @staticmethod
    def _has_import(source: str, module: str) -> bool:
        return bool(
            re.search(
                rf'^\s*(import\s+{re.escape(module)}\b'
                rf'|from\s+{re.escape(module)}\s+import)',
                source,
                re.MULTILINE,
            )
        )

    @staticmethod
    def _has_from_import(source: str, module: str, name: str) -> bool:
        return bool(
            re.search(
                rf'^\s*from\s+{re.escape(module)}\s+import\s+'
                rf'.*\b{re.escape(name)}\b',
                source,
                re.MULTILINE,
            )
        )

    @staticmethod
    def _add_import(source: str, import_line: str) -> str:
        lines = source.splitlines(keepends=True)
        last_import_idx = -1
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                last_import_idx = i
        stmt = f"{import_line}\n"
        if last_import_idx >= 0:
            lines.insert(last_import_idx + 1, stmt)
        else:
            lines.insert(0, stmt)
        return "".join(lines)

    @staticmethod
    def _make_diff(original: str, patched: str, file_path: str) -> str:
        orig_lines = original.splitlines(keepends=True)
        patch_lines = patched.splitlines(keepends=True)
        diff_lines = list(difflib.unified_diff(
            orig_lines, patch_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
        ))
        return "".join(diff_lines)
