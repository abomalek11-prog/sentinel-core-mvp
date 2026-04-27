"""
Sentinel Core — LLM Patch Planner

Calls GitHub Models (or any configured LLM) to produce a structured PatchPlan.
The plan contains one PatchDecision per vulnerability.

Design contract
---------------
* The planner ONLY produces data (JSON).  It NEVER writes or executes code.
* PatchEngine is the sole authority that applies transformations.
* If the LLM is unavailable or returns invalid JSON, the planner produces a
  fallback plan that instructs PatchEngine to use its built-in rules.
"""

from __future__ import annotations

import json
import textwrap
from typing import Any

from sentinel_core.llm.config import get_llm as _get_llm_cached
from sentinel_core.llm.config import strip_json_markdown
from sentinel_core.patching.models import PatchDecision, PatchPlan, PatchStrategy
from sentinel_core.utils.logging import get_logger

log = get_logger(__name__)


def _get_llm() -> Any:
    """Thin wrapper around the cached get_llm — exists so tests can patch it."""
    return _get_llm_cached()

# ---------------------------------------------------------------------------
# Allowed strategy strings the LLM may return
# ---------------------------------------------------------------------------
_VALID_STRATEGIES: frozenset[str] = frozenset(s.value for s in PatchStrategy)

# Minimum confidence threshold — decisions below this are auto-rejected
_MIN_CONFIDENCE: float = 0.40

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT: str = textwrap.dedent("""\
You are a senior application-security engineer specialising in automated code repair.

Given a list of vulnerabilities found in Python source code, produce a JSON object
with these top-level keys:

  "planning_notes" : string — one short paragraph describing your overall strategy
  "decisions"      : array  — one object per vulnerability with exactly these keys:
      "kind"        : string — vulnerability kind exactly as provided (e.g. "eval")
      "location"    : string — location exactly as provided (e.g. "line 6")
      "strategy"    : one of: "safe_replace" | "wrap_try_except" |
                              "add_input_validation" | "comment_out" | "rule_based"
      "safe_api"    : string — the safe replacement API to use
      "rationale"   : string — 1-2 sentences explaining WHY this fix is correct
      "test_hint"   : string — one-line test to verify the fix
      "confidence"  : float between 0.0 and 1.0

Rules:
- Choose "rule_based" only when you cannot determine a better strategy.
- Prefer "safe_replace" for well-known sinks (eval, os.system, pickle.loads, yaml.load).
- Prefer "wrap_try_except" when the safe API may throw on bad input.
- confidence must be > 0.40 for the fix to be applied; otherwise it will be skipped.
- Return ONLY valid JSON — no markdown fences, no comments, no prose.
""")


# ---------------------------------------------------------------------------
# LLMPatchPlanner
# ---------------------------------------------------------------------------

class LLMPatchPlanner:
    """Produces a PatchPlan by asking the configured LLM for a patch strategy.

    Usage::

        planner = LLMPatchPlanner()
        plan = planner.plan(vulnerabilities, source_code)

        for decision in plan.decisions:
            print(decision)

    The planner always returns a valid PatchPlan.  On LLM failure it falls back
    to a rule-based plan (each vulnerability gets a RULE_BASED decision) so the
    PatchEngine can still apply its deterministic rules.
    """

    def plan(
        self,
        vulnerabilities: list[dict[str, Any]],
        source_code: str,
        *,
        file_path: str = "<source>",
    ) -> PatchPlan:
        """Generate a PatchPlan for the given vulnerabilities.

        Args:
            vulnerabilities: List of vulnerability dicts from AgentState.
            source_code:     Full source code being analysed.
            file_path:       Display path (used in logs only).

        Returns:
            A :class:`PatchPlan` — never raises.
        """
        if not vulnerabilities:
            return PatchPlan(decisions=[], used_fallback=False)

        llm = _get_llm()
        if llm is None:
            log.info("llm_planner_no_llm", fallback="rule_based")
            return self._fallback_plan(vulnerabilities)

        return self._llm_plan(llm, vulnerabilities, source_code, file_path)

    # ------------------------------------------------------------------
    # LLM path
    # ------------------------------------------------------------------

    def _llm_plan(
        self,
        llm: Any,
        vulnerabilities: list[dict[str, Any]],
        source_code: str,
        file_path: str,
    ) -> PatchPlan:
        """Call the LLM and parse the JSON response into a PatchPlan."""
        from langchain_core.messages import HumanMessage, SystemMessage

        vuln_summary = json.dumps(
            [{"kind": v.get("kind"), "location": v.get("location"),
              "severity": v.get("severity"), "description": v.get("description")}
             for v in vulnerabilities],
            indent=2,
        )
        # Show source with 0-based line numbers so the LLM reports the correct index
        numbered_lines = "\n".join(
            f"{i}: {line}" for i, line in enumerate(source_code.splitlines())
        )
        source_preview = numbered_lines[:3_000]  # cap to avoid large token usage

        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=(
                f"File: {file_path}\n\n"
                f"Source code (lines are 0-indexed):\n```python\n{source_preview}\n```\n\n"
                f"Vulnerabilities to patch:\n{vuln_summary}"
            )),
        ]

        try:
            response = llm.invoke(messages)
            raw = response.content if hasattr(response, "content") else str(response)
            model_name: str = getattr(llm, "model_name", None) or getattr(llm, "model", "llm")

            log.debug("llm_planner_raw_response", length=len(raw), model=model_name)
            return self._parse_response(raw, model_name, vulnerabilities)

        except Exception:
            log.warning("llm_planner_call_failed", fallback="rule_based", exc_info=True)
            return self._fallback_plan(vulnerabilities)

    def _parse_response(
        self,
        raw: str,
        model_name: str,
        vulnerabilities: list[dict[str, Any]],
    ) -> PatchPlan:
        """Parse the raw LLM text into a PatchPlan, validating every field."""
        cleaned = strip_json_markdown(raw)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            log.warning("llm_planner_json_error", exc=str(exc), preview=cleaned[:120])
            return self._fallback_plan(vulnerabilities, model_name=model_name)

        if not isinstance(data, dict):
            log.warning("llm_planner_unexpected_shape", got=type(data).__name__)
            return self._fallback_plan(vulnerabilities, model_name=model_name)

        planning_notes: str = str(data.get("planning_notes", ""))
        raw_decisions: list[Any] = data.get("decisions", [])
        if not isinstance(raw_decisions, list):
            log.warning("llm_planner_no_decisions_array")
            return self._fallback_plan(vulnerabilities, model_name=model_name)

        # Build a lookup so we can fill in missing decisions with fallbacks
        known_kinds = {v.get("kind", ""): v.get("location", "") for v in vulnerabilities}
        seen_kinds: set[str] = set()
        decisions: list[PatchDecision] = []

        for item in raw_decisions:
            if not isinstance(item, dict):
                continue

            kind = str(item.get("kind", "")).strip()
            location = str(item.get("location", "")).strip()
            raw_strategy = str(item.get("strategy", "rule_based")).strip()
            confidence = float(item.get("confidence", 1.0))

            # Validate strategy — default to RULE_BASED on unknown values
            if raw_strategy not in _VALID_STRATEGIES:
                log.debug(
                    "llm_planner_unknown_strategy",
                    strategy=raw_strategy,
                    defaulting="rule_based",
                )
                raw_strategy = PatchStrategy.RULE_BASED.value

            strategy = PatchStrategy(raw_strategy)

            decision = PatchDecision(
                kind=kind,
                location=location or known_kinds.get(kind, ""),
                strategy=strategy,
                safe_api=str(item.get("safe_api", "")),
                rationale=str(item.get("rationale", "")),
                test_hint=str(item.get("test_hint", "")),
                confidence=max(0.0, min(confidence, 1.0)),
            )

            # Reject decisions below confidence threshold
            if decision.confidence < _MIN_CONFIDENCE:
                decision.accepted = False
                decision.rejection_reason = (
                    f"confidence {decision.confidence:.2f} < threshold {_MIN_CONFIDENCE}"
                )
                log.debug(
                    "llm_planner_low_confidence",
                    kind=kind,
                    confidence=decision.confidence,
                )

            decisions.append(decision)
            seen_kinds.add(kind)

        # Fill in fallback decisions for any vuln the LLM missed
        for kind, location in known_kinds.items():
            if kind not in seen_kinds:
                log.debug("llm_planner_filling_missing", kind=kind)
                decisions.append(PatchDecision(
                    kind=kind,
                    location=location,
                    strategy=PatchStrategy.RULE_BASED,
                    rationale="LLM did not address this vulnerability; using rule-based fix.",
                    confidence=1.0,
                ))

        log.info(
            "llm_planner_plan_ready",
            model=model_name,
            total=len(decisions),
            fallback_filled=len([d for d in decisions if d.strategy == PatchStrategy.RULE_BASED]),
        )
        return PatchPlan(
            decisions=decisions,
            llm_model=model_name,
            planning_notes=planning_notes,
            used_fallback=False,
        )

    # ------------------------------------------------------------------
    # Fallback (rule-based) plan
    # ------------------------------------------------------------------

    @staticmethod
    def _fallback_plan(
        vulnerabilities: list[dict[str, Any]],
        model_name: str = "rule-based",
    ) -> PatchPlan:
        """Build a plan that tells PatchEngine to use its built-in rules."""
        decisions = [
            PatchDecision(
                kind=v.get("kind", ""),
                location=v.get("location", ""),
                strategy=PatchStrategy.RULE_BASED,
                rationale="LLM unavailable — using deterministic rule-based fix.",
                confidence=1.0,
            )
            for v in vulnerabilities
            if v.get("kind")
        ]
        return PatchPlan(
            decisions=decisions,
            llm_model=model_name,
            planning_notes="Fallback: deterministic rule-based patching applied.",
            used_fallback=True,
        )
