"""
Sentinel Core API — /api/health endpoint.
"""
from __future__ import annotations

from fastapi import APIRouter

from sentinel_core.llm.config import get_llm
from api.models import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Health check")
async def health_check() -> HealthResponse:
    """Return API health status and LLM availability."""
    llm = get_llm()
    llm_ready = llm is not None
    llm_model = getattr(llm, "model", "none") if llm_ready else "none"

    return HealthResponse(
        status="ok",
        version="0.1.0",
        llm_ready=llm_ready,
        llm_model=str(llm_model),
    )
