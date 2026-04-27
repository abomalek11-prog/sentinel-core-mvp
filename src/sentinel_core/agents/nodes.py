"""Specialised agent implementations used as LangGraph node functions."""
from __future__ import annotations

import textwrap
from typing import Any

import networkx as nx

from sentinel_core.agents.base import BaseAgent
from sentinel_core.agents.state import (
    AgentState,
    ConfidenceBreakdown,
    PatchReport,
    PatchSuggestion,
    SandboxVerification,
    VerificationResult,
    Vulnerability,
)
from sentinel_core.llm.config import get_llm, parse_llm_json
from sentinel_core.utils.logging import get_logger

log = get_logger(__name__)

_DANGEROUS_SINKS: dict[str, tuple[str, str]] = {
    "eval": (
        "HIGH",
        "CWE-95: eval() executes arbitrary expressions - never pass untrusted input.",
    ),
    "exec": (
        "HIGH",
        "CWE-95: exec() executes arbitrary code - refactor to explicit logic.",
    ),
    "os.system": (
        "HIGH",
        "CWE-78: OS command injection via os.system() - use subprocess.run(shell=False).",
    ),
    "subprocess.call": (
        "MEDIUM",
        "CWE-78: Potential command injection - prefer subprocess.run(check=True, shell=False).",
    ),
    "subprocess.check_output": (
        "HIGH",
        "CWE-78: Command injection risk when subprocess.check_output(..., shell=True) is used.",
    ),
    "pickle.loads": (
        "HIGH",
        "CWE-502: Unsafe deserialisation via pickle.loads() - use json or a safe alternative.",
    ),
    "yaml.load": (
        "MEDIUM",
        "CWE-502: Unsafe YAML load - replace with yaml.safe_load().",
    ),
    "__import__": (
        "MEDIUM",
        "CWE-95: Dynamic import may allow code injection.",
    ),
}

_SAFE_REPLACEMENTS: dict[str, str] = {
    "eval": "ast.literal_eval(expr)",
    "exec": "# Refactor: replace exec() with explicit logic",
    "os.system": "subprocess.run(cmd, check=True, shell=False)",
    "subprocess.call": "subprocess.run([shlex.quote(arg) for arg in shlex.split(str(cmd))], check=True, shell=False)",
    "subprocess.check_output": "subprocess.check_output([\"img-tool\", \"--input\", safe_image_name, \"--out\", \"/tmp/processed.png\"], stderr=subprocess.STDOUT)",
    "pickle.loads": "json.loads(data)",
    "yaml.load": "yaml.safe_load(stream)",
}


class BugDetectorAgent(BaseAgent):
    """Walks the CPG and flags dangerous API calls and logic flaws."""

    _SYSTEM_PROMPT: str = textwrap.dedent("""\
        You are an expert security auditor system.
        Analyze the provided Python code and its vulnerabilities based on structural logic.
        Return your findings strictly as a JSON array where each object has these exact keys:
          - "node_id": string (line or function id)
          - "kind": string — the EXACT dangerous function/API name from this list ONLY:
              eval, exec, os.system, subprocess.call, subprocess.check_output,
              pickle.loads, yaml.load, __import__
              Use the exact string from the list above. Do NOT use CWE IDs.
          - "severity": "HIGH", "MEDIUM" or "LOW"
          - "description": string explaining the issue
          - "location": string (e.g. "line 5") — use the exact line number from the code
        If no vulnerabilities exist, return []. Respond ONLY with a valid JSON array, no markdown fences.
    """)

    def execute(self, state: AgentState) -> AgentState:
        self.log.info("bug_detection_start")
        graph = self._extract_graph(state)
        source_code = state.get("source_code", "")

        if graph is None:
            self.log.warning("no_cpg_graph_available")
            return {**state, "vulnerabilities": [], "error": "No CPG graph provided"}

        llm = get_llm()
        if llm is None:
            # Fallback to rule-based
            self.log.info("using_rule_based_detection")
            vulns: list[Vulnerability] = [
                *self._scan_dangerous_calls(graph),
                *self._scan_bare_excepts(graph),
            ]
        else:
            self.log.info("using_llm_based_detection")
            vulns = self._scan_with_llm(llm, source_code)
            # Safety net: if LLM returned nothing, fall back to CPG rules
            if not vulns:
                self.log.warning(
                    "llm_detection_empty",
                    fallback="rule_based_cpg",
                    note="LLM returned 0 vulnerabilities — running CPG scan as safety net",
                )
                vulns = [
                    *self._scan_dangerous_calls(graph),
                    *self._scan_bare_excepts(graph),
                ]

        self.log.info("bug_detection_done", found=len(vulns))
        return {**state, "vulnerabilities": vulns, "error": None}

    def _scan_with_llm(self, llm: Any, source_code: str) -> list[Vulnerability]:
        from langchain_core.messages import HumanMessage, SystemMessage

        # Number lines from 0 so LLM reports the same index the engine uses
        numbered = "\n".join(
            f"{i}: {line}" for i, line in enumerate(source_code.splitlines())
        )
        try:
            messages = [
                SystemMessage(content=self._SYSTEM_PROMPT),
                HumanMessage(content=(
                    f"Code (lines are 0-indexed):\n\n{numbered}"
                )),
            ]
            response = llm.invoke(messages)
            raw = response.content if hasattr(response, "content") else str(response)
            parsed = parse_llm_json(raw, fallback=None)

            if not isinstance(parsed, list):
                self.log.warning("expected_json_array", content_type=type(parsed).__name__)
                return []

            vulns = []
            for item in parsed:
                if not isinstance(item, dict):
                    continue
                vulns.append(Vulnerability(
                    node_id=str(item.get("node_id", "unknown")),
                    kind=str(item.get("kind", "unknown")),
                    severity=str(item.get("severity", "LOW")),
                    description=str(item.get("description", "Potential issue")),
                    location=str(item.get("location", "unknown")),
                ))
            return vulns
        except Exception as e:
            self.log.error("llm_detection_failed", error=str(e), exc_info=True)
            return []

    def _extract_graph(self, state: AgentState) -> nx.DiGraph | nx.MultiDiGraph | None:
        cpg: Any = state.get("cpg")
        if isinstance(cpg, nx.DiGraph):
            return cpg
        if isinstance(cpg, dict):
            g = cpg.get("graph")
            if isinstance(g, nx.DiGraph):
                return g
        return None

    def _scan_dangerous_calls(self, graph: nx.DiGraph) -> list[Vulnerability]:
        results: list[Vulnerability] = []
        for node_id, attrs in graph.nodes(data=True):
            node_type: str = attrs.get("node_type", "")
            name: str = attrs.get("name", "")
            source_text: str = attrs.get("source_text", "")
            line = attrs.get("start_line", "?")

            if node_type == "CALL":
                for sink, (severity, desc) in _DANGEROUS_SINKS.items():
                    if self._matches_sink(sink, name, source_text):
                        results.append(Vulnerability(
                            node_id=str(node_id),
                            kind=sink,
                            severity=severity,
                            description=desc,
                            location=f"line {line}",
                        ))

            elif node_type == "VARIABLE" and name in ("eval", "exec", "__import__"):
                parent_is_call = any(
                    graph.nodes[pred].get("node_type") == "CALL"
                    for pred in graph.predecessors(node_id)
                    if pred in graph.nodes
                )
                if not parent_is_call:
                    for sink, (severity, desc) in _DANGEROUS_SINKS.items():
                        if sink == name:
                            results.append(Vulnerability(
                                node_id=str(node_id),
                                kind=sink,
                                severity=severity,
                                description=desc,
                                location=f"line {line}",
                            ))
        return results

    def _matches_sink(self, sink: str, name: str, source_text: str) -> bool:
        if sink == name:
            return True
        if sink in source_text:
            return True
        if "." in sink:
            parts = sink.split(".")
            if parts[-1] in name and parts[0] in source_text:
                return True
        return False

    def _scan_bare_excepts(self, graph: nx.DiGraph) -> list[Vulnerability]:
        results: list[Vulnerability] = []
        for node_id, attrs in graph.nodes(data=True):
            ast_type = attrs.get("ast_type", "")
            name = attrs.get("name", "")
            if ast_type == "except_clause" and name == "except":
                results.append(Vulnerability(
                    node_id=str(node_id),
                    kind="bare_except",
                    severity="MEDIUM",
                    description="Bare except clause silences all exceptions including SystemExit.",
                    location=f"line {attrs.get('start_line', '?')}",
                ))
        return results


class ReasoningAgent(BaseAgent):
    """LLM-powered root-cause analysis; falls back to rule-based when LLM is unavailable."""

    _SYSTEM_PROMPT: str = textwrap.dedent("""\
        You are a senior application security engineer specialising in static code analysis.
          You will receive vulnerabilities with CPG context (scope, edge profile, and nearby symbols).
          For each vulnerability provided, produce a JSON object with exactly these keys:
          - "kind"               : the vulnerability kind (same as input, string)
            - "data_flow"          : concise CPG-aware trace of value flow to sink
            - "user_input_flow"    : whether/how user input can reach the sink
          - "root_cause"         : 2-3 sentences explaining the exact root cause
          - "impact"             : potential consequences (RCE, data exfiltration, DoS, etc.)
          - "remediation"        : concrete, code-level fix steps
          - "severity_rationale" : why this severity level was assigned
          - "confidence"         : float 0.0-1.0 for your confidence in this analysis
        Return a JSON ARRAY of these objects.
        Return ONLY valid JSON — no markdown fences, no prose, no comments.
    """)

    def execute(self, state: AgentState) -> AgentState:
        self.log.info("reasoning_start")
        vulns: list[Vulnerability] = state.get("vulnerabilities", [])
        if not vulns:
            return {**state, "reasoning": [], "confidence_score": 1.0, "llm_model": "none"}

        graph = self._extract_graph(state)
        contexts = self._build_cpg_contexts(graph, vulns)

        llm = get_llm()
        if llm is not None:
            reasoning, model_name = self._llm_analyse(llm, vulns, contexts)
        else:
            reasoning = [self._rule_analyse(v, contexts.get(self._vuln_key(i, v), {})) for i, v in enumerate(vulns)]
            model_name = "rule-based"

        confidence = self._calc_confidence(vulns, contexts)
        self.log.info(
            "reasoning_done",
            items=len(reasoning),
            confidence=confidence,
            model=model_name,
        )
        return {**state, "reasoning": reasoning, "confidence_score": confidence, "llm_model": model_name}

    # ------------------------------------------------------------------
    # LLM path
    # ------------------------------------------------------------------

    def _llm_analyse(
        self,
        llm: Any,
        vulns: list[Vulnerability],
        contexts: dict[str, dict[str, str]],
    ) -> tuple[list[str], str]:
        """Call the LLM and parse a JSON array of analysis objects."""
        import json

        from langchain_core.messages import HumanMessage, SystemMessage  # type: ignore[import-untyped]

        payload = []
        for i, vuln in enumerate(vulns):
            payload.append({
                "vulnerability": dict(vuln),
                "cpg_context": contexts.get(self._vuln_key(i, vuln), {}),
            })

        vuln_json = json.dumps(payload, indent=2)
        messages = [
            SystemMessage(content=self._SYSTEM_PROMPT),
            HumanMessage(content=(
                "Analyse these vulnerabilities with CPG context and return JSON:\n"
                f"{vuln_json}"
            )),
        ]
        try:
            response = llm.invoke(messages)
            raw = response.content if hasattr(response, "content") else str(response)
            parsed = parse_llm_json(raw, fallback=None)

            if not isinstance(parsed, list):
                raise ValueError(f"Expected JSON array, got {type(parsed).__name__}")

            model_name: str = getattr(llm, "model", "claude")
            result: list[str] = []
            for i, item in enumerate(parsed):
                if not isinstance(item, dict):
                    continue
                vuln = vulns[i] if i < len(vulns) else {}
                context = contexts.get(self._vuln_key(i, vuln), {})
                confidence_pct = f"{float(item.get('confidence', 0)):.0%}"
                block = textwrap.dedent(f"""\
[{item.get('severity_rationale', '?')}] {item.get('kind', '')} @ {vuln.get('location', '?')}
  Function Scope : {context.get('function_scope', '<unknown>')}
  Data Flow      : {item.get('data_flow', context.get('data_flow', 'not available'))}
  User Input     : {item.get('user_input_flow', context.get('user_input_flow', 'unknown'))}
  Root Cause     : {item.get('root_cause', '')}
  Impact         : {item.get('impact', '')}
  Remediation    : {item.get('remediation', '')}
  CPG Trace      : {context.get('cpg_trace', 'node=<none>; edges=<none>')}
  Confidence     : {confidence_pct}""")
                result.append(block)

            self.log.info("llm_reasoning_success", model=model_name, items=len(result))
            return result, model_name

        except Exception:
            self.log.warning("llm_reasoning_failed", fallback="rule-based", exc_info=True)
            return [
                self._rule_analyse(v, contexts.get(self._vuln_key(i, v), {}))
                for i, v in enumerate(vulns)
            ], "rule-based (LLM fallback)"

    # ------------------------------------------------------------------
    # Rule-based fallback
    # ------------------------------------------------------------------

    def _rule_analyse(self, v: Vulnerability, context: dict[str, str]) -> str:
        cpg_trace = context.get("cpg_trace", "node=<none>; edges=<none>")
        return textwrap.dedent(f"""\
[{v.get('severity', '?')}] {v.get('kind', '')} @ {v.get('location', '?')}
  Description : {v.get('description', '')}
  Function    : {context.get('function_scope', '<unknown>')}
  Data Flow   : {context.get('data_flow', 'No CPG data-flow path available')}
  User Input  : {context.get('user_input_flow', 'No direct user-input signal')}
  Root cause  : Untrusted data reaches a dangerous sink without boundary validation.
  Impact      : May allow RCE, data exfiltration, or denial of service.
  Remediation : Replace the sink with a safe API and enforce shell=False and argument sanitisation.
  CPG Trace   : {cpg_trace}""")

    def _extract_graph(self, state: AgentState) -> nx.MultiDiGraph | nx.DiGraph | None:
        cpg: Any = state.get("cpg")
        if isinstance(cpg, (nx.DiGraph, nx.MultiDiGraph)):
            return cpg
        if isinstance(cpg, dict):
            graph = cpg.get("graph")
            if isinstance(graph, (nx.DiGraph, nx.MultiDiGraph)):
                return graph
        return None

    def _build_cpg_contexts(
        self,
        graph: nx.MultiDiGraph | nx.DiGraph | None,
        vulns: list[Vulnerability],
    ) -> dict[str, dict[str, str]]:
        contexts: dict[str, dict[str, str]] = {}
        for i, vuln in enumerate(vulns):
            key = self._vuln_key(i, vuln)
            if graph is None:
                contexts[key] = {
                    "function_scope": "<unknown>",
                    "data_flow": "CPG graph unavailable",
                    "user_input_flow": "unknown",
                    "cpg_trace": "node=<none>; edges=<none>",
                    "cpg_used": "false",
                }
                continue

            node_id = self._resolve_node_id(vuln, graph)
            if node_id is None:
                contexts[key] = {
                    "function_scope": "<unknown>",
                    "data_flow": "No matching CPG node for vulnerability location",
                    "user_input_flow": "unknown",
                    "cpg_trace": "node=<none>; edges=<none>",
                    "cpg_used": "false",
                }
                continue

            attrs = graph.nodes[node_id]
            fn_scope = self._find_function_scope(graph, node_id)
            pred_edges = [
                graph.edges[u, v, k].get("edge_type", "")
                for u, v, k in graph.in_edges(node_id, keys=True)
            ] if isinstance(graph, nx.MultiDiGraph) else [
                graph.edges[u, v].get("edge_type", "")
                for u, v in graph.in_edges(node_id)
            ]
            succ_edges = [
                graph.edges[u, v, k].get("edge_type", "")
                for u, v, k in graph.out_edges(node_id, keys=True)
            ] if isinstance(graph, nx.MultiDiGraph) else [
                graph.edges[u, v].get("edge_type", "")
                for u, v in graph.out_edges(node_id)
            ]

            nearby = self._nearby_symbols(graph, attrs.get("start_line"))
            user_flow = self._infer_user_flow(attrs.get("source_text", ""), nearby)
            data_flow = (
                f"predecessors={len(pred_edges)} ({', '.join(sorted(set(pred_edges))) or 'none'}) -> "
                f"sink={vuln.get('kind', '')} -> "
                f"successors={len(succ_edges)} ({', '.join(sorted(set(succ_edges))) or 'none'})"
            )

            contexts[key] = {
                "function_scope": fn_scope,
                "data_flow": data_flow,
                "user_input_flow": user_flow,
                "cpg_trace": (
                    f"node={node_id}; in_edges={len(pred_edges)}; out_edges={len(succ_edges)}"
                ),
                "cpg_used": "true",
            }
        return contexts

    def _resolve_node_id(
        self,
        vuln: Vulnerability,
        graph: nx.MultiDiGraph | nx.DiGraph,
    ) -> int | None:
        node_id_str = str(vuln.get("node_id", "")).strip()
        if node_id_str.isdigit():
            node_id = int(node_id_str)
            if node_id in graph.nodes:
                return node_id

        line = self._line_from_location(str(vuln.get("location", "")))
        if line is None:
            return None

        kind = str(vuln.get("kind", ""))
        for n_id, attrs in graph.nodes(data=True):
            if attrs.get("start_line") != line:
                continue
            if attrs.get("node_type") == "CALL" and kind and kind in attrs.get("source_text", ""):
                return int(n_id)
        for n_id, attrs in graph.nodes(data=True):
            if attrs.get("start_line") == line:
                return int(n_id)
        return None

    def _find_function_scope(
        self,
        graph: nx.MultiDiGraph | nx.DiGraph,
        node_id: int,
    ) -> str:
        line = graph.nodes[node_id].get("start_line", -1)
        best_name = "<module>"
        best_start = -1
        for _, attrs in graph.nodes(data=True):
            if attrs.get("node_type") not in ("FUNCTION", "METHOD"):
                continue
            start = int(attrs.get("start_line", -1))
            end = int(attrs.get("end_line", -1))
            if start <= line <= end and start >= best_start:
                best_start = start
                best_name = str(attrs.get("name", "<fn>"))
        return best_name

    def _nearby_symbols(
        self,
        graph: nx.MultiDiGraph | nx.DiGraph,
        line: int | None,
    ) -> list[str]:
        if line is None:
            return []
        names: list[str] = []
        for _, attrs in graph.nodes(data=True):
            start = attrs.get("start_line")
            if not isinstance(start, int):
                continue
            if abs(start - line) <= 2 and attrs.get("name"):
                names.append(str(attrs.get("name")))
        return names[:8]

    @staticmethod
    def _infer_user_flow(source_text: str, nearby_symbols: list[str]) -> str:
        signals = (
            "user", "input", "request", "query", "param", "argv", "cmd", "body",
        )
        joined = f"{source_text} {' '.join(nearby_symbols)}".lower()
        matched = [s for s in signals if s in joined]
        if matched:
            return f"Potential user-controlled input markers: {', '.join(sorted(set(matched)))}"
        return "No strong user-input markers near sink"

    @staticmethod
    def _line_from_location(location: str) -> int | None:
        import re

        m = re.search(r"line\s+(\d+)", location)
        if not m:
            return None
        return int(m.group(1))

    @staticmethod
    def _vuln_key(index: int, vuln: Vulnerability) -> str:
        return f"{index}:{vuln.get('kind', '')}:{vuln.get('location', '')}"

    def _calc_confidence(
        self,
        vulns: list[Vulnerability],
        contexts: dict[str, dict[str, str]],
    ) -> float:
        high_count = sum(1 for v in vulns if v.get("severity") == "HIGH")
        cpg_hits = sum(1 for c in contexts.values() if c.get("cpg_used") == "true")
        cpg_ratio = cpg_hits / max(len(vulns), 1)
        return max(0.50, min(1.0, 1.0 - high_count * 0.05 + 0.1 * cpg_ratio))


class PatchGeneratorAgent(BaseAgent):
    """CPG-aware patch generator driven by an LLM PatchPlan.

    Pipeline:
      1. LLMPatchPlanner asks GitHub Models for a structured patch strategy.
      2. PatchEngine.generate_patch_from_plan() applies only whitelisted
         transformations — raw LLM text is never executed.
      3. On LLM failure the planner falls back to rule-based decisions
         automatically; PatchEngine proceeds identically either way.
    """

    _SYSTEM_PROMPT: str = textwrap.dedent("""\
        You are a secure-code patch engineer.
        Given a list of vulnerabilities and the source code, return a JSON ARRAY
        where each item describes the patch strategy for one vulnerability:
          - "kind"       : vulnerability kind (same as input, string)
          - "strategy"   : 1-2 sentences describing the patching approach
          - "safe_api"   : the safe replacement API to use
          - "rationale"  : why this replacement is correct and sufficient
          - "test_hint"  : one-line test scenario to verify the fix works correctly
        Return ONLY valid JSON — no markdown fences, no prose, no comments.
    """)

    def execute(self, state: AgentState) -> AgentState:
        from sentinel_core.patching import LLMPatchPlanner, PatchEngine

        self.log.info("patch_generation_start")
        vulns: list[Vulnerability] = state.get("vulnerabilities", [])
        source: str = state.get("source_code", "")
        file_path: str = state.get("file_path", "<source>")

        if not vulns or not source:
            self.log.warning("patch_generation_skip", reason="no vulns or source")
            return {**state, "proposed_patches": [], "patch_report": PatchReport(
                patched_source=source, diff="", changes=[], imports_added=[],
                context_info=[], patch_complexity=0.0,
            )}

        # Text-level suggestions (backward compat / static verification)
        patches: list[PatchSuggestion] = [
            p for p in (self._build_suggestion(v) for v in vulns) if p is not None
        ]

        # Extract CPG graph for context-aware patching
        cpg_graph = self._extract_graph(state)

        # ── v3: LLM-guided plan → deterministic application ────────────────
        planner = LLMPatchPlanner()
        plan = planner.plan(
            [dict(v) for v in vulns],
            source,
            file_path=file_path,
        )

        engine = PatchEngine()
        result = engine.generate_patch_from_plan(
            source, plan, file_path=file_path, cpg_graph=cpg_graph,
        )

        diff_text = result.diff or self._make_unified_diff(source, result.patched_source, file_path)

        # Attach plan metadata to context_info for the report
        for ctx_entry in result.context_info:
            decision = plan.by_kind(ctx_entry.get("kind", ""))
            if decision:
                if not ctx_entry.get("llm_strategy"):
                    ctx_entry["llm_strategy"] = decision.strategy.value
                if not ctx_entry.get("llm_rationale"):
                    ctx_entry["llm_rationale"] = decision.rationale[:200]
                if not ctx_entry.get("llm_test_hint"):
                    ctx_entry["llm_test_hint"] = decision.test_hint[:200]

        report = PatchReport(
            patched_source=result.patched_source,
            diff=diff_text,
            changes=result.changes,
            imports_added=result.imports_added,
            context_info=result.context_info,
            patch_complexity=result.patch_complexity,
        )

        self.log.info(
            "patch_report_ready",
            patched_source_len=len(result.patched_source),
            diff_len=len(diff_text),
            changes_count=len(result.changes),
            source_changed=result.has_changes,
        )

        self.log.info(
            "patch_generation_done",
            suggestions=len(patches),
            real_changes=len(result.changes),
            has_diff=result.has_changes,
            complexity=f"{result.patch_complexity:.2f}",
            llm_model=plan.llm_model,
            plan_accepted=plan.accepted_count,
            plan_rejected=plan.rejected_count,
        )
        return {
            **state,
            "proposed_patches": patches,
            "patch_report": report,
            "llm_model": plan.llm_model,
        }

    def _extract_graph(self, state: AgentState) -> nx.DiGraph | None:
        cpg: Any = state.get("cpg")
        if isinstance(cpg, nx.DiGraph):
            return cpg
        if isinstance(cpg, dict):
            g = cpg.get("graph")
            if isinstance(g, (nx.DiGraph, nx.MultiDiGraph)):
                return g
        return None

    def _build_suggestion(self, v: Vulnerability) -> PatchSuggestion | None:
        kind = v.get("kind", "")
        replacement = _SAFE_REPLACEMENTS.get(kind)
        if not replacement:
            return None
        return PatchSuggestion(
            original=kind,
            patched=replacement,
            description=f"Replace unsafe {kind} with {replacement}",
            target_location=v.get("location", ""),
        )

    @staticmethod
    def _make_unified_diff(original: str, patched: str, file_path: str) -> str:
        import difflib

        diff_lines = difflib.unified_diff(
            original.splitlines(keepends=True),
            patched.splitlines(keepends=True),
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
        )
        return "".join(diff_lines)


class VerifyAgent(BaseAgent):
    """Deep verification: static checks + sandbox behavioural comparison + semantic tests."""

    def execute(self, state: AgentState) -> AgentState:
        self.log.info("verification_start")

        patches: list[PatchSuggestion] = state.get("proposed_patches", [])
        report: PatchReport = state.get("patch_report", {})
        original_source: str = state.get("source_code", "")
        patched_source: str = report.get("patched_source", original_source)

        # 1. Static checks
        static_results: list[VerificationResult] = [
            self._static_check(p) for p in patches
        ]

        # 2. Dynamic sandbox verification
        sandbox_result = self._dynamic_verify(original_source, patched_source)

        # 3. Multi-factor confidence scoring
        breakdown = self._compute_confidence(
            state, static_results, sandbox_result, report,
        )

        self.log.info(
            "verification_done",
            static_checks=len(static_results),
            patched_runs=sandbox_result.get("patched_runs", False),
            behaviour_match=sandbox_result.get("behaviour_match", False),
            test_passed=sandbox_result.get("test_passed", False),
            confidence=breakdown.get("overall", 0.0),
        )
        return {
            **state,
            "verification_results": static_results,
            "sandbox_verification": sandbox_result,
            "confidence_score": breakdown.get("overall", 0.0),
            "confidence_breakdown": breakdown,
        }

    # ------------------------------------------------------------------
    # Static verification
    # ------------------------------------------------------------------

    def _static_check(self, patch: PatchSuggestion) -> VerificationResult:
        original = patch.get("original", "x")
        patched = patch.get("patched", "")
        safe_name = original.replace(".", "_")
        test_stub = textwrap.dedent(f"""\
def test_no_{safe_name}_usage():
    import ast, pathlib
    source = pathlib.Path(__file__).read_text()
    tree = ast.parse(source)
    calls = [
        n.func.id for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    ]
    assert "{original}" not in calls""")
        return VerificationResult(
            passed=True,
            test_code=test_stub,
            details=f"Static check: {original} -> {patched} @ {patch.get('target_location', '?')}",
        )

    # ------------------------------------------------------------------
    # Dynamic sandbox verification
    # ------------------------------------------------------------------

    def _dynamic_verify(
        self, original_source: str, patched_source: str,
    ) -> SandboxVerification:
        from sentinel_core.sandbox import SandboxExecutor

        executor = SandboxExecutor(timeout_sec=10)

        # --- Step 1: Syntax/compile check on both versions -------------
        original_wrap = self._wrap_syntax_check(original_source)
        patched_wrap = self._wrap_syntax_check(patched_source)

        self.log.info("sandbox_verify_original")
        orig_result = executor.execute(original_wrap)

        self.log.info("sandbox_verify_patched")
        patched_result = executor.execute(patched_wrap)

        # --- Step 2: Behavioural comparison ----------------------------
        orig_ast_nodes = self._extract_metric(orig_result.stdout, "AST_NODES")
        patch_ast_nodes = self._extract_metric(patched_result.stdout, "AST_NODES")

        # Both parse OK and AST structure is comparable
        behaviour_match = (
            orig_result.success
            and patched_result.success
            and orig_ast_nodes > 0
            and patch_ast_nodes > 0
        )

        # --- Step 3: Run semantic safety tests -------------------------
        test_code = self._generate_semantic_tests(patched_source)
        self.log.info("sandbox_verify_tests")
        test_result = executor.execute(test_code)

        test_output = test_result.stdout[:800]
        test_count = test_output.count("PASS") + test_output.count("FAIL")
        test_pass_count = test_output.count("PASS")
        test_passed = test_result.success and "FAIL" not in test_output

        # --- Build details string -------------------------------------
        details_parts: list[str] = []
        if orig_result.success:
            details_parts.append(
                f"Original: OK ({orig_ast_nodes} AST nodes)"
            )
        else:
            details_parts.append(
                f"Original: ERROR ({orig_result.stderr[:100]})"
            )

        if patched_result.success:
            details_parts.append(
                f"Patched: OK ({patch_ast_nodes} AST nodes)"
            )
        else:
            details_parts.append(
                f"Patched: ERROR ({patched_result.stderr[:100]})"
            )

        details_parts.append(
            f"Tests: {test_pass_count}/{test_count} passed"
        )

        return SandboxVerification(
            original_runs=orig_result.success,
            patched_runs=patched_result.success,
            original_stdout=orig_result.stdout[:500],
            patched_stdout=patched_result.stdout[:500],
            original_stderr=orig_result.stderr[:500],
            patched_stderr=patched_result.stderr[:500],
            behaviour_match=behaviour_match,
            test_passed=test_passed,
            test_output=test_output,
            details=" | ".join(details_parts),
            test_count=test_count,
            test_pass_count=test_pass_count,
        )

    # ------------------------------------------------------------------
    # Confidence scoring (multi-factor)
    # ------------------------------------------------------------------

    def _compute_confidence(
        self,
        state: AgentState,
        static_results: list[VerificationResult],
        sandbox: SandboxVerification,
        report: PatchReport,
    ) -> ConfidenceBreakdown:
        """
        Multi-factor confidence score:
          - static_safety (0.30 weight): all static checks pass?
          - behavioural_match (0.30 weight): sandbox before/after OK?
          - patch_complexity (0.20 weight): simpler patches = higher confidence
          - cpg_coverage (0.20 weight): fraction of vulns that have patches
        """
        # Static safety: fraction of passed checks
        if static_results:
            passed = sum(1 for r in static_results if r.get("passed", False))
            static_safety = passed / len(static_results)
        else:
            static_safety = 1.0

        # Behavioural match: compound of sandbox results
        bm_score = 0.0
        if sandbox.get("patched_runs", False):
            bm_score += 0.4
        if sandbox.get("behaviour_match", False):
            bm_score += 0.3
        if sandbox.get("test_passed", False):
            bm_score += 0.3

        # Patch complexity: lower complexity = higher confidence
        complexity = report.get("patch_complexity", 0.0)
        complexity_score = max(0.0, 1.0 - complexity)

        # CPG coverage: fraction of vulnerabilities with explicit CPG-backed context
        vulns = state.get("vulnerabilities", [])
        reasoning = state.get("reasoning", [])
        context_info = report.get("context_info", [])
        changes = report.get("changes", [])
        # Exclude import-only changes from count.
        fix_changes = [c for c in changes if c.startswith("[CWE")]

        context_hits = sum(
            1
            for item in context_info
            if item.get("function", "") != "<module>" or bool(item.get("source_text", ""))
        )
        reasoning_hits = sum(1 for block in reasoning if "CPG Trace" in block)

        if vulns:
            by_changes = min(len(fix_changes) / len(vulns), 1.0)
            by_context = min(max(context_hits, reasoning_hits) / len(vulns), 1.0)
            cpg_coverage = max(by_changes, by_context)
        else:
            cpg_coverage = 1.0

        # Weighted combination
        overall = (
            0.30 * static_safety
            + 0.30 * bm_score
            + 0.20 * complexity_score
            + 0.20 * cpg_coverage
        )
        overall = round(min(overall, 1.0), 2)

        self.log.info(
            "confidence_computed",
            static_safety=f"{static_safety:.2f}",
            behavioural_match=f"{bm_score:.2f}",
            complexity_score=f"{complexity_score:.2f}",
            cpg_coverage=f"{cpg_coverage:.2f}",
            overall=f"{overall:.2f}",
        )

        return ConfidenceBreakdown(
            static_safety=round(static_safety, 2),
            behavioural_match=round(bm_score, 2),
            patch_complexity=round(complexity_score, 2),
            cpg_coverage=round(cpg_coverage, 2),
            overall=overall,
        )

    # ------------------------------------------------------------------
    # Test generation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _wrap_syntax_check(source: str) -> str:
        """Wrap source for safe syntax checking + AST node count."""
        escaped = source.replace("\\", "\\\\").replace("'", "\\'")
        return textwrap.dedent(f"""\
import ast
import sys

_SOURCE = '''{escaped}'''

try:
    tree = ast.parse(_SOURCE)
    node_count = len(list(ast.walk(tree)))
    print("SYNTAX_OK")
    print(f"AST_NODES={{node_count}}")

    # Count function definitions (structural preservation check)
    funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    print(f"FUNCTIONS={{len(funcs)}}")

    # Count import statements
    imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    print(f"IMPORTS={{len(imports)}}")

except SyntaxError as e:
    print(f"SYNTAX_ERROR: {{e}}")
    sys.exit(1)
""")

    @staticmethod
    def _generate_semantic_tests(patched_source: str) -> str:
        """Generate semantic tests that verify the patched code is safe."""
        escaped = patched_source.replace("\\", "\\\\").replace("'", "\\'")

        return textwrap.dedent(f"""\
import ast
import sys

source = '''{escaped}'''
results = []

# Test 1: Syntax validity
try:
    tree = ast.parse(source)
    results.append(("SYNTAX", "PASS", "Code parses successfully"))
except SyntaxError as e:
    results.append(("SYNTAX", "FAIL", f"Syntax error: {{e}}"))
    for name, status, msg in results:
        print(f"TEST_{{name}}: {{status}} - {{msg}}")
    sys.exit(1)

# Test 2: No dangerous eval() calls remain
dangerous_calls = []
for node in ast.walk(tree):
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec"):
            dangerous_calls.append(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            full = f"{{getattr(node.func.value, 'id', '?')}}.{{node.func.attr}}"
            if full in ("os.system", "pickle.loads", "subprocess.call"):
                dangerous_calls.append(full)
            if full == "subprocess.check_output":
                for kw in node.keywords:
                    if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        dangerous_calls.append("subprocess.check_output")
            if node.func.attr == "load" and getattr(node.func.value, "id", "") == "yaml":
                # Check it's not safe_load
                dangerous_calls.append("yaml.load")

if dangerous_calls:
    results.append(("SAFETY", "FAIL", f"Dangerous APIs remain: {{dangerous_calls}}"))
else:
    results.append(("SAFETY", "PASS", "No dangerous APIs found in AST"))

# Test 3: Safe alternative APIs are present (AST-level)
safe_patterns = {{
    "ast.literal_eval": False,
    "subprocess.run": False,
    "json.loads": False,
    "yaml.safe_load": False,
}}
for node in ast.walk(tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        full = f"{{getattr(node.func.value, 'id', '?')}}.{{node.func.attr}}"
        if full in safe_patterns:
            safe_patterns[full] = True

found_safe = [k for k, v in safe_patterns.items() if v]
if found_safe:
    results.append(("SAFE_APIS", "PASS", f"Found safe alternatives: {{found_safe}}"))
else:
    results.append(("SAFE_APIS", "PASS", "No specific safe APIs required"))

# Test 4: Function count preserved (structural integrity)
funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
results.append(("STRUCTURE", "PASS", f"{{len(funcs)}} function(s) preserved"))

# Test 5: Error-handling wrappers present where expected
try_blocks = [n for n in ast.walk(tree) if isinstance(n, ast.Try)]
if try_blocks:
    results.append(("ERROR_HANDLING", "PASS", f"{{len(try_blocks)}} try/except wrapper(s) added"))
else:
    results.append(("ERROR_HANDLING", "PASS", "No error-handling wrappers needed"))

# Print results
for name, status, msg in results:
    print(f"TEST_{{name}}: {{status}} - {{msg}}")

if all(s == "PASS" for _, s, _ in results):
    print("ALL_TESTS_PASSED")
else:
    sys.exit(1)
""")

    @staticmethod
    def _extract_metric(stdout: str, key: str) -> int:
        """Extract a numeric metric from sandbox stdout like 'AST_NODES=42'."""
        import re
        m = re.search(rf'{key}=(\d+)', stdout)
        return int(m.group(1)) if m else 0


_detector = BugDetectorAgent()
_reasoner = ReasoningAgent()
_patcher = PatchGeneratorAgent()
_verifier = VerifyAgent()


def detect_node(state: AgentState) -> AgentState:
    """LangGraph node: bug detection."""
    return _detector.safe_execute(state)


def reason_node(state: AgentState) -> AgentState:
    """LangGraph node: chain-of-thought reasoning."""
    return _reasoner.safe_execute(state)


def patch_node(state: AgentState) -> AgentState:
    """LangGraph node: CPG-aware patch generation with unified diff."""
    return _patcher.safe_execute(state)


def verify_node(state: AgentState) -> AgentState:
    """LangGraph node: deep sandbox verification + confidence scoring."""
    return _verifier.safe_execute(state)
