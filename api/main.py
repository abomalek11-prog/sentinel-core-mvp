"""
Sentinel Core — FastAPI application entry point.

Run in development:
    $env:PYTHONPATH = "src"
    uvicorn api.main:app --reload --port 8000

Or via the helper script:
    python -m api.main
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

# Add 'src' to PYTHONPATH so sentinel_core can be imported in Vercel functions
src_path = str(Path(__file__).parent.parent / "src")
if src_path not in sys.path:
    sys.path.append(src_path)

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from sentinel_core.utils.logging import configure_logging, get_logger

from api.routes.analyze import router as analyze_router
from api.routes.demo import router as demo_router
from api.routes.health import router as health_router

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

configure_logging()
log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Lifespan  (startup / shutdown hooks)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    log.info("sentinel_api_startup", version="0.1.0")

    # Warm up the LLM client so first request is fast
    try:
        from sentinel_core.llm.config import get_llm
        llm = get_llm()
        if llm:
            log.info("llm_ready", model=getattr(llm, "model", "unknown"))
        else:
            log.info("llm_unavailable", note="Rule-based mode active")
    except Exception as exc:
        log.warning("llm_warmup_failed", exc=str(exc))

    yield

    log.info("sentinel_api_shutdown")


# ---------------------------------------------------------------------------
# App instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Sentinel Core API",
    description=(
        "Static-analysis + multi-agent bug-repair system. "
        "Upload Python source code, detect vulnerabilities, and receive "
        "AI-powered patches — all streamed in real time via SSE."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS  (allow all origins in development; tighten in production)
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.error("unhandled_exception", path=str(request.url), exc=str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check server logs for details."},
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

# Include routers both with and without /api prefix to be safe on Vercel
app.include_router(health_router, prefix="/api")
app.include_router(analyze_router, prefix="/api")
app.include_router(demo_router, prefix="/api")

# Fallback for direct function calls
app.include_router(health_router)
app.include_router(analyze_router)
app.include_router(demo_router)


# ---------------------------------------------------------------------------
# Root redirect → docs
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def root() -> JSONResponse:
    return JSONResponse(
        {"message": "Sentinel Core API", "docs": "/docs", "health": "/api/health"}
    )


# ---------------------------------------------------------------------------
# Dev entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
