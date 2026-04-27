"""
Sentinel Core — Patch Planning Models

Structured data models representing an LLM-generated patch plan.
The plan is produced by LLMPatchPlanner and consumed by PatchEngine.
The engine only ever applies transformations from the whitelisted registry;
raw LLM text is never executed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PatchStrategy(str, Enum):
    """Allowed transformation strategies the engine understands."""

    SAFE_REPLACE = "safe_replace"          # swap dangerous API for a safe one
    WRAP_TRY_EXCEPT = "wrap_try_except"    # add try/except around dangerous call
    ADD_INPUT_VALIDATION = "add_input_validation"  # add guard before dangerous call
    COMMENT_OUT = "comment_out"            # comment out irremediably unsafe code
    RULE_BASED = "rule_based"              # fall back to built-in rule (engine decides)


@dataclass
class PatchDecision:
    """A single patching decision for one vulnerability.

    Produced by the LLM Planner and validated before being passed to
    PatchEngine.  The engine only acts on ``strategy`` + ``kind``; it never
    evaluates the free-text ``rationale`` or ``test_hint`` as code.

    Attributes:
        kind:        Vulnerability kind matching a key in ``_PATCH_RULES``
                     (e.g. ``"eval"``, ``"os.system"``).
        location:    Original location string (e.g. ``"line 6"``).
        strategy:    Transformation to apply (must be a valid PatchStrategy).
        safe_api:    The safe replacement API suggested by the LLM (informational;
                     the engine maps this to its own whitelist).
        rationale:   LLM explanation — stored for the report, never executed.
        test_hint:   One-line test suggestion — stored for the report only.
        confidence:  LLM confidence float 0.0-1.0.
        accepted:    Set by the engine: True if the decision was applied.
        rejection_reason: Set by the engine when ``accepted=False``.
    """

    kind: str
    location: str
    strategy: PatchStrategy = PatchStrategy.RULE_BASED
    safe_api: str = ""
    rationale: str = ""
    test_hint: str = ""
    confidence: float = 1.0
    accepted: bool = False
    rejection_reason: str = ""

    # ── Validation ────────────────────────────────────────────────────────────

    def is_valid(self) -> bool:
        """Return True when this decision has enough information to act on."""
        return bool(self.kind) and bool(self.location) and 0.0 <= self.confidence <= 1.0

    def __repr__(self) -> str:  # pragma: no cover
        status = "ACCEPTED" if self.accepted else f"REJECTED({self.rejection_reason})"
        return (
            f"PatchDecision(kind={self.kind!r}, location={self.location!r}, "
            f"strategy={self.strategy.value!r}, confidence={self.confidence:.2f}, "
            f"status={status})"
        )


@dataclass
class PatchPlan:
    """An ordered list of decisions produced by the LLM Planner.

    Attributes:
        decisions:       Ordered list of PatchDecision objects (one per vuln).
        llm_model:       Model that produced this plan (for reporting).
        planning_notes:  High-level LLM notes about the overall patch strategy.
        used_fallback:   True when the planner fell back to rule-based planning
                         (LLM unavailable or returned invalid JSON).
    """

    decisions: list[PatchDecision] = field(default_factory=list)
    llm_model: str = "rule-based"
    planning_notes: str = ""
    used_fallback: bool = False

    # ── Convenience ───────────────────────────────────────────────────────────

    @property
    def accepted_count(self) -> int:
        return sum(1 for d in self.decisions if d.accepted)

    @property
    def rejected_count(self) -> int:
        return sum(1 for d in self.decisions if not d.accepted and d.kind)

    def by_kind(self, kind: str) -> PatchDecision | None:
        """Return the first decision matching *kind*, or None."""
        return next((d for d in self.decisions if d.kind == kind), None)

    def summary(self) -> str:
        """One-line human-readable summary of the plan."""
        total = len(self.decisions)
        return (
            f"PatchPlan: {total} decision(s), model={self.llm_model!r}, "
            f"fallback={self.used_fallback}"
        )
