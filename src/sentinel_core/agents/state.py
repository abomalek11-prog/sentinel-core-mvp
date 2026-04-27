"""Shared state definition for the Sentinel agent pipeline."""
from __future__ import annotations

from typing import Any, TypedDict


class Vulnerability(TypedDict, total=False):
    """A detected vulnerability or logic flaw."""

    node_id: str
    kind: str
    severity: str
    description: str
    location: str


class PatchSuggestion(TypedDict, total=False):
    """A proposed code patch for a vulnerability."""

    original: str
    patched: str
    description: str
    target_location: str


class VerificationResult(TypedDict, total=False):
    """Result of patch verification."""

    passed: bool
    test_code: str
    details: str


class PatchReport(TypedDict, total=False):
    """A complete patch report with diff and patched source."""

    patched_source: str
    diff: str
    changes: list[str]
    imports_added: list[str]
    context_info: list[dict[str, str]]
    patch_complexity: float


class SandboxVerification(TypedDict, total=False):
    """Result of dynamic verification via sandbox execution."""

    original_runs: bool
    patched_runs: bool
    original_stdout: str
    patched_stdout: str
    original_stderr: str
    patched_stderr: str
    behaviour_match: bool
    test_passed: bool
    test_output: str
    details: str
    test_count: int
    test_pass_count: int


class ConfidenceBreakdown(TypedDict, total=False):
    """Detailed breakdown of the confidence score."""

    static_safety: float
    behavioural_match: float
    patch_complexity: float
    cpg_coverage: float
    overall: float


class AgentState(TypedDict, total=False):
    """Full pipeline state flowing through every agent node."""

    source_code: str
    file_path: str
    language: str
    parsed_file: dict[str, Any]
    cpg: dict[str, Any]
    vulnerabilities: list[Vulnerability]
    reasoning: list[str]
    proposed_patches: list[PatchSuggestion]
    patch_report: PatchReport
    verification_results: list[VerificationResult]
    sandbox_verification: SandboxVerification
    confidence_score: float
    confidence_breakdown: ConfidenceBreakdown
    llm_model: str
    error: str | None
