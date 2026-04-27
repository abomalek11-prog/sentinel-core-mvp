"""
Sentinel Core — Patching Module
Code patch generation and application engine.

Public API:
    - PatchEngine:       Main engine for generating and applying patches.
    - PatchResult:       Result of a patch operation.
    - PatchRule:         A single deterministic rewrite rule.
    - LLMPatchPlanner:   LLM-powered patch planning (GitHub Models / Anthropic).
    - PatchPlan:         Structured plan produced by LLMPatchPlanner.
    - PatchDecision:     Single patching decision within a plan.
    - PatchStrategy:     Enum of allowed transformation strategies.
"""

from __future__ import annotations

from sentinel_core.patching.llm_planner import LLMPatchPlanner
from sentinel_core.patching.models import PatchDecision, PatchPlan, PatchStrategy
from sentinel_core.patching.patch_generator import (
    PatchEngine,
    PatchResult,
    PatchRule,
    _CPGContext,
)

__all__ = [
    "LLMPatchPlanner",
    "PatchDecision",
    "PatchEngine",
    "PatchPlan",
    "PatchResult",
    "PatchRule",
    "PatchStrategy",
]

