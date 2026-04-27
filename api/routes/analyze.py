"""
Sentinel Core API — /api/analyze endpoints.

Routes
------
POST /api/analyze/stream   Stream SSE events as the pipeline runs.
POST /api/analyze          Run full pipeline; return complete result as JSON.
GET  /api/results          List all stored analysis results.
GET  /api/results/{id}     Retrieve a single stored result.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from sentinel_core.utils.logging import get_logger

from api.models import AnalyzeRequest, AnalysisResponse, AnalysisStatus
from api.pipeline import get_result, list_results, run_analysis

log = get_logger(__name__)

router = APIRouter(tags=["analyze"])


# ---------------------------------------------------------------------------
# SSE streaming endpoint  (primary endpoint used by the UI)
# ---------------------------------------------------------------------------

@router.post(
    "/analyze/stream",
    summary="Analyse source code (Server-Sent Events)",
    response_class=StreamingResponse,
)
async def analyze_stream(request: AnalyzeRequest) -> StreamingResponse:
    """
    Run the full Sentinel pipeline and stream progress events in SSE format.

    Each event has the form:
    ```
    event: <event_type>
    data: <json_payload>

    ```

    Event types: `status`, `vulnerabilities`, `reasoning`, `patch`,
    `verification`, `error`, `done`.
    """
    log.info(
        "analyze_stream_start",
        file=request.file_name,
        lang=request.language,
        chars=len(request.source_code),
    )

    async def _event_generator():
        async for sse_event in run_analysis(
            source_code=request.source_code,
            file_name=request.file_name,
            language=request.language,
        ):
            payload = json.dumps(sse_event.data, default=str)
            # SSE wire format: "event: <type>\ndata: <json>\n\n"
            yield f"event: {sse_event.event.value}\ndata: {payload}\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
        },
    )


# ---------------------------------------------------------------------------
# Blocking JSON endpoint  (useful for CLI / testing)
# ---------------------------------------------------------------------------

@router.post(
    "/analyze",
    response_model=AnalysisResponse,
    summary="Analyse source code (JSON, blocking)",
)
async def analyze_json(request: AnalyzeRequest) -> AnalysisResponse:
    """
    Run the full Sentinel pipeline synchronously and return the complete
    analysis result as JSON.  For streaming progress updates use
    `POST /api/analyze/stream` instead.
    """
    log.info(
        "analyze_json_start",
        file=request.file_name,
        lang=request.language,
        chars=len(request.source_code),
    )

    analysis_id: str | None = None
    async for sse_event in run_analysis(
        source_code=request.source_code,
        file_name=request.file_name,
        language=request.language,
    ):
        # Capture the analysis_id from the first status event
        if analysis_id is None and isinstance(sse_event.data, dict):
            analysis_id = sse_event.data.get("analysis_id")

        # If we hit an error event, raise immediately
        if sse_event.event.value == "error":
            raise HTTPException(
                status_code=500,
                detail=str(sse_event.data.get("error", "Pipeline error")),
            )

    if analysis_id is None:
        raise HTTPException(status_code=500, detail="Pipeline returned no result.")

    result = get_result(analysis_id)
    if result is None:
        raise HTTPException(status_code=500, detail="Result not found after pipeline.")

    return result


# ---------------------------------------------------------------------------
# Result retrieval
# ---------------------------------------------------------------------------

@router.get(
    "/results",
    response_model=list[AnalysisResponse],
    summary="List all analysis results",
)
async def get_all_results() -> list[AnalysisResponse]:
    """Return a list of all stored analysis results (newest last)."""
    return list_results()


@router.get(
    "/results/{analysis_id}",
    response_model=AnalysisResponse,
    summary="Get a single analysis result",
)
async def get_single_result(analysis_id: str) -> AnalysisResponse:
    """Retrieve a previously completed analysis result by ID."""
    result = get_result(analysis_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Analysis {analysis_id!r} not found.",
        )
    return result
