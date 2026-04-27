"""Vercel Python function entrypoint.

Vercel reliably detects `api/index.py` as the default Python serverless function.
We re-export the FastAPI ASGI app from `api.main`.
"""
from __future__ import annotations

from api.main import app
