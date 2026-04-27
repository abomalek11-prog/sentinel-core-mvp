"""
Sentinel Core API — Async pipeline runner.

Wraps the synchronous LangGraph pipeline in a thread executor so FastAPI
can stream partial results back to the client via Server-Sent Events without
blocking the event loop.

Architecture
------------
  1. run_analysis()  ← called by the /analyze route
       ├─ Runs each pipeline stage in asyncio.to_thread()
       └─ Yields SSEEvent objects as each stage completes

  2. run_pipeline_sync()  ← thin sync wrapper used in tests / CLI
"""
from __future__ import annotations

import asyncio
import sys
import traceback
import uuid
from typing import AsyncIterator

from sentinel_core import CPGBuilder, CodeParser
from sentinel_core.agents import run_pipeline
from sentinel_core.llm.config import get_llm
from sentinel_core.utils.logging import get_logger

from api.models import (
    AnalysisResponse,
    AnalysisStatus,
    ConfidenceBreakdownSchema,
    ContextInfoSchema,
    EventType,
    PatchReportSchema,
    PatchSuggestionSchema,
    SandboxVerificationSchema,
    SSEEvent,
    VulnerabilitySchema,
    VerificationSchema,
)

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers — convert internal dicts → Pydantic schemas
# ---------------------------------------------------------------------------

def _to_vuln(v: dict) -> VulnerabilitySchema:
    return VulnerabilitySchema(
        node_id=str(v.get("node_id", "")),
        kind=str(v.get("kind", "")),
        severity=str(v.get("severity", "")),
        description=str(v.get("description", "")),
        location=str(v.get("location", "")),
    )


def _to_patch(p: dict) -> PatchSuggestionSchema:
    return PatchSuggestionSchema(
        original=str(p.get("original", "")),
        patched=str(p.get("patched", "")),
        description=str(p.get("description", "")),
        target_location=str(p.get("target_location", "")),
    )


def _to_context_info(c: dict) -> ContextInfoSchema:
    return ContextInfoSchema(
        kind=str(c.get("kind", "")),
        cwe=str(c.get("cwe", "")),
        location=str(c.get("location", "")),
        function=str(c.get("function", "")),
        source_text=str(c.get("source_text", "")),
        cpg_trace=str(c.get("cpg_trace", "")),
        fix=str(c.get("fix", "")),
        llm_strategy=str(c.get("llm_strategy", "")),
        llm_rationale=str(c.get("llm_rationale", "")),
        llm_test_hint=str(c.get("llm_test_hint", "")),
    )


def _build_analysis_response(
    analysis_id: str,
    file_name: str,
    language: str,
    state: dict,
    status: AnalysisStatus = AnalysisStatus.completed,
    error: str | None = None,
) -> AnalysisResponse:
    """Convert raw AgentState dict → AnalysisResponse."""
    patch_report_raw: dict = state.get("patch_report", {})
    sandbox_raw: dict = state.get("sandbox_verification", {})
    breakdown_raw: dict = state.get("confidence_breakdown", {})
    verifications_raw: list = state.get("verification_results", [])

    patch_report = PatchReportSchema(
        patched_source=str(patch_report_raw.get("patched_source", "")),
        diff=str(patch_report_raw.get("diff", "")),
        changes=list(patch_report_raw.get("changes", [])),
        imports_added=list(patch_report_raw.get("imports_added", [])),
        context_info=[
            _to_context_info(c)
            for c in patch_report_raw.get("context_info", [])
        ],
        patch_complexity=float(patch_report_raw.get("patch_complexity", 0.0)),
    )

    is_sandbox_empty = not bool(sandbox_raw)
    sandbox = SandboxVerificationSchema(
        original_runs=bool(sandbox_raw.get("original_runs", is_sandbox_empty)),
        patched_runs=bool(sandbox_raw.get("patched_runs", is_sandbox_empty)),
        behaviour_match=bool(sandbox_raw.get("behaviour_match", is_sandbox_empty)),
        test_passed=bool(sandbox_raw.get("test_passed", is_sandbox_empty)),
        test_output=str(sandbox_raw.get("test_output", "No dynamic testing required.")),
        details=str(sandbox_raw.get("details", "No vulnerabilities detected. Sandbox bypassed.")),
        test_count=int(sandbox_raw.get("test_count", 0)),
        test_pass_count=int(sandbox_raw.get("test_pass_count", 0)),
    )

    breakdown = ConfidenceBreakdownSchema(
        static_safety=float(breakdown_raw.get("static_safety", 0.0)),
        behavioural_match=float(breakdown_raw.get("behavioural_match", 0.0)),
        patch_complexity=float(breakdown_raw.get("patch_complexity", 0.0)),
        cpg_coverage=float(breakdown_raw.get("cpg_coverage", 0.0)),
        overall=float(breakdown_raw.get("overall", 0.0)),
    )

    verification = VerificationSchema(
        static_checks=[
            {"passed": bool(v.get("passed")), "details": str(v.get("details", ""))}
            for v in verifications_raw
        ],
        sandbox=sandbox,
        confidence_score=float(state.get("confidence_score", 0.0)),
        confidence_breakdown=breakdown,
    )

    return AnalysisResponse(
        analysis_id=analysis_id,
        status=status,
        file_name=file_name,
        language=language,
        llm_model=str(state.get("llm_model", "rule-based")),
        source_code=str(state.get("source_code", "")),
        vulnerabilities=[_to_vuln(v) for v in state.get("vulnerabilities", [])],
        reasoning=list(state.get("reasoning", [])),
        patches=[_to_patch(p) for p in state.get("proposed_patches", [])],
        patch_report=patch_report,
        verification=verification,
        error=error or state.get("error"),
    )


# ---------------------------------------------------------------------------
# In-memory result store  (sufficient for MVP; replace with Redis/DB later)
# ---------------------------------------------------------------------------

_results: dict[str, AnalysisResponse] = {}


def get_result(analysis_id: str) -> AnalysisResponse | None:
    return _results.get(analysis_id)


def list_results() -> list[AnalysisResponse]:
    return list(_results.values())


# ---------------------------------------------------------------------------
# Async streaming pipeline
# ---------------------------------------------------------------------------

async def run_analysis(
    source_code: str,
    file_name: str = "<source>",
    language: str = "python",
) -> AsyncIterator[SSEEvent]:
    """Run the full Sentinel pipeline and yield SSE events as stages complete.

    Stages emitted:
        status(running)  →  status(parsing)  →  vulnerabilities  →
        status(reasoning) →  reasoning  →  status(patching)  →
        patch  →  status(verifying)  →  verification  →  done
    """
    analysis_id = str(uuid.uuid4())

    # ── Stage 0: initialise ───────────────────────────────────────────
    yield SSEEvent(
        event=EventType.status,
        data={"stage": "started", "analysis_id": analysis_id},
        message="Analysis started",
    )

    try:
        # ── Stage 1: Parse + CPG (sync in thread) ────────────────────
        yield SSEEvent(
            event=EventType.status,
            data={"stage": "parsing"},
            message="Parsing source code and building CPG…",
        )

        def _parse_and_build() -> dict:
            parser = CodeParser()
            parsed = parser.parse_source(source_code)
            builder = CPGBuilder()
            cpg = builder.build(parsed)
            nx_graph = builder.to_networkx(cpg)
            return {
                "parsed": parsed,
                "cpg": cpg,
                "nx_graph": nx_graph,
            }

        build_result = await asyncio.to_thread(_parse_and_build)
        cpg = build_result["cpg"]
        nx_graph = build_result["nx_graph"]

        yield SSEEvent(
            event=EventType.status,
            data={
                "stage": "parsed",
                "cpg_nodes": cpg.node_count,
                "cpg_edges": cpg.edge_count,
            },
            message=f"CPG built: {cpg.node_count} nodes, {cpg.edge_count} edges",
        )

        # ── Stage 2: Run detection (sync in thread) ───────────────────
        yield SSEEvent(
            event=EventType.status,
            data={"stage": "detecting"},
            message="Detecting vulnerabilities…",
        )

        def _run_full_pipeline() -> dict:
            return run_pipeline(
                source_code=source_code,
                file_path=file_name,
                language=language,
                cpg_graph=nx_graph,
            )

        state: dict = await asyncio.to_thread(_run_full_pipeline)

        log.info(
            "pipeline_state_debug",
            state_keys=list(state.keys()),
            confidence_score=state.get("confidence_score"),
            breakdown=state.get("confidence_breakdown"),
            sandbox=state.get("sandbox_verification"),
            vuln_count=len(state.get("vulnerabilities", [])),
        )

        # ── Emit vulnerabilities ──────────────────────────────────────
        vulns = [_to_vuln(v).model_dump() for v in state.get("vulnerabilities", [])]
        yield SSEEvent(
            event=EventType.vulnerabilities,
            data={"vulnerabilities": vulns, "count": len(vulns)},
            message=f"{len(vulns)} vulnerability/vulnerabilities detected",
        )

        # ── Emit reasoning ────────────────────────────────────────────
        reasoning = state.get("reasoning", [])
        if reasoning:
            yield SSEEvent(
                event=EventType.reasoning,
                data={"reasoning": reasoning},
                message="Root-cause analysis complete",
            )

        # ── Emit patch ────────────────────────────────────────────────
        patch_report_raw = state.get("patch_report", {})
        patches = [_to_patch(p).model_dump() for p in state.get("proposed_patches", [])]
        patched_src = patch_report_raw.get("patched_source", "")
        log.info(
            "patch_event_emit",
            patches_count=len(patches),
            patched_source_len=len(patched_src),
            has_diff=bool(patch_report_raw.get("diff")),
            source_changed=patched_src != source_code,
        )
        yield SSEEvent(
            event=EventType.patch,
            data={
                "patches": patches,
                "diff": patch_report_raw.get("diff", ""),
                "changes": patch_report_raw.get("changes", []),
                "patched_source": patched_src,
                "context_info": [
                    _to_context_info(c).model_dump()
                    for c in patch_report_raw.get("context_info", [])
                ],
            },
            message=f"{len(patches)} patch(es) generated",
        )

        # ── Emit verification ─────────────────────────────────────────
        breakdown_raw = state.get("confidence_breakdown", {})
        sandbox_raw = state.get("sandbox_verification", {})
        log.info("verification_payload_prepared", sandbox_raw=sandbox_raw)
        is_sandbox_empty = not bool(sandbox_raw)
        yield SSEEvent(
            event=EventType.verification,
            data={
                "confidence_score": state.get("confidence_score", 0.0),
                "confidence_breakdown": breakdown_raw,
                "sandbox": {
                    "original_runs":   sandbox_raw.get("original_runs", is_sandbox_empty),
                    "patched_runs":    sandbox_raw.get("patched_runs", is_sandbox_empty),
                    "behaviour_match": sandbox_raw.get("behaviour_match", is_sandbox_empty),
                    "test_passed":     sandbox_raw.get("test_passed", is_sandbox_empty),
                    "test_output":     sandbox_raw.get("test_output", "No dynamic testing required."),
                    "test_count":      sandbox_raw.get("test_count", 0),
                    "test_pass_count": sandbox_raw.get("test_pass_count", 0),
                    "details":         sandbox_raw.get("details", "No vulnerabilities detected. Sandbox bypassed."),
                },
                "static_checks": [
                    {"passed": bool(v.get("passed")), "details": str(v.get("details", ""))}
                    for v in state.get("verification_results", [])
                ],
            },
            message="Verification complete",
        )

        # ── Build + store full result ──────────────────────────────────
        response = _build_analysis_response(
            analysis_id=analysis_id,
            file_name=file_name,
            language=language,
            state=state,
        )
        _results[analysis_id] = response

        # ── Done ──────────────────────────────────────────────────────
        yield SSEEvent(
            event=EventType.done,
            data={
                "analysis_id": analysis_id,
                "vuln_count":  len(vulns),
                "patch_count": len(patches),
                "confidence":  state.get("confidence_score", 0.0),
                "llm_model":   state.get("llm_model", "rule-based"),
            },
            message="Analysis complete",
        )

    except Exception as exc:
        log.error("pipeline_exception", exc=str(exc), exc_info=True)
        err_msg = str(exc)

        # Store failed result so GET /results/{id} still responds
        failed = AnalysisResponse(
            analysis_id=analysis_id,
            status=AnalysisStatus.failed,
            file_name=file_name,
            language=language,
            error=err_msg,
        )
        _results[analysis_id] = failed

        yield SSEEvent(
            event=EventType.error,
            data={"error": err_msg, "analysis_id": analysis_id},
            message="Pipeline failed",
        )
