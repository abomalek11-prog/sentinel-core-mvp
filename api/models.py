"""
Sentinel Core API — Pydantic request / response schemas.

All models are strict-by-default so the API never silently drops fields.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Language(str, Enum):
    python = "python"


class Severity(str, Enum):
    HIGH   = "HIGH"
    MEDIUM = "MEDIUM"
    LOW    = "LOW"


class AnalysisStatus(str, Enum):
    queued    = "queued"
    running   = "running"
    completed = "completed"
    failed    = "failed"


# ---------------------------------------------------------------------------
# SSE event types  (sent over the streaming endpoint)
# ---------------------------------------------------------------------------

class EventType(str, Enum):
    status          = "status"          # pipeline stage change
    vulnerabilities = "vulnerabilities" # list of detected vulns
    reasoning       = "reasoning"       # LLM root-cause analysis
    patch           = "patch"           # diff + patched source
    verification    = "verification"    # sandbox + confidence results
    error           = "error"           # unrecoverable error
    done            = "done"            # pipeline finished


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    """POST /api/analyze — analyse source code."""

    source_code: str = Field(
        ...,
        min_length=1,
        max_length=500_000,
        description="Source code to analyse (max 500 KB).",
    )
    file_name: str = Field(
        default="<source>",
        max_length=260,
        description="Display file name (used in diff headers).",
    )
    language: Language = Field(
        default=Language.python,
        description="Programming language of the source code.",
    )

    @field_validator("source_code")
    @classmethod
    def no_null_bytes(cls, v: str) -> str:
        if "\x00" in v:
            raise ValueError("Source code must not contain null bytes.")
        return v


# ---------------------------------------------------------------------------
# Sub-models (returned inside responses)
# ---------------------------------------------------------------------------

class VulnerabilitySchema(BaseModel):
    node_id:     str = ""
    kind:        str = ""
    severity:    str = ""
    description: str = ""
    location:    str = ""


class PatchSuggestionSchema(BaseModel):
    original:        str = ""
    patched:         str = ""
    description:     str = ""
    target_location: str = ""


class ContextInfoSchema(BaseModel):
    kind:          str = ""
    cwe:           str = ""
    location:      str = ""
    function:      str = ""
    source_text:   str = ""
    cpg_trace:     str = ""
    fix:           str = ""
    llm_strategy:  str = ""
    llm_rationale: str = ""
    llm_test_hint: str = ""


class PatchReportSchema(BaseModel):
    patched_source:   str                   = ""
    diff:             str                   = ""
    changes:          list[str]             = Field(default_factory=list)
    imports_added:    list[str]             = Field(default_factory=list)
    context_info:     list[ContextInfoSchema] = Field(default_factory=list)
    patch_complexity: float                 = 0.0


class SandboxVerificationSchema(BaseModel):
    original_runs:   bool  = False
    patched_runs:    bool  = False
    behaviour_match: bool  = False
    test_passed:     bool  = False
    test_output:     str   = ""
    details:         str   = ""
    test_count:      int   = 0
    test_pass_count: int   = 0


class ConfidenceBreakdownSchema(BaseModel):
    static_safety:     float = 0.0
    behavioural_match: float = 0.0
    patch_complexity:  float = 0.0
    cpg_coverage:      float = 0.0
    overall:           float = 0.0


class VerificationSchema(BaseModel):
    static_checks:       list[dict[str, Any]] = Field(default_factory=list)
    sandbox:             SandboxVerificationSchema = Field(
                             default_factory=SandboxVerificationSchema)
    confidence_score:    float                = 0.0
    confidence_breakdown: ConfidenceBreakdownSchema = Field(
                             default_factory=ConfidenceBreakdownSchema)


# ---------------------------------------------------------------------------
# Full analysis response (returned by GET /api/results/{id})
# ---------------------------------------------------------------------------

class AnalysisResponse(BaseModel):
    """Complete analysis result."""

    analysis_id:     str
    status:          AnalysisStatus
    file_name:       str
    language:        str
    llm_model:       str                       = "rule-based"
    source_code:     str                       = ""
    vulnerabilities: list[VulnerabilitySchema] = Field(default_factory=list)
    reasoning:       list[str]                 = Field(default_factory=list)
    patches:         list[PatchSuggestionSchema] = Field(default_factory=list)
    patch_report:    PatchReportSchema         = Field(
                         default_factory=PatchReportSchema)
    verification:    VerificationSchema        = Field(
                         default_factory=VerificationSchema)
    error:           str | None                = None

    # Computed convenience fields
    @property
    def vuln_count(self) -> int:
        return len(self.vulnerabilities)

    @property
    def patch_count(self) -> int:
        return len(self.patches)


# ---------------------------------------------------------------------------
# SSE event envelope
# ---------------------------------------------------------------------------

class SSEEvent(BaseModel):
    """Single Server-Sent Event payload."""

    event:   EventType
    data:    Any
    message: str = ""


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status:    str  = "ok"
    version:   str  = "0.1.0"
    llm_ready: bool = False
    llm_model: str  = "none"
