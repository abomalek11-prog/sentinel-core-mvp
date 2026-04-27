"""
Sentinel Core API — /api/demo endpoint.

Returns the built-in vulnerable Python snippet that the CLI uses for its demo
run.  The frontend can call this to pre-populate the code editor.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["demo"])

# Same snippet used in main.py _DEMO_SOURCE
_DEMO_SOURCE = '''\
"""
UserDataService — internal data processing pipeline.
Handles image processing, formula evaluation, config loading, and session management.
"""
import os
import subprocess
import pickle
import yaml
from pathlib import Path


class UserDataService:
    """Core service for processing user-submitted data."""

    def resize_image(self, filename: str, width: int, height: int) -> bytes:
        """Resize an uploaded image using ImageMagick."""
        cmd = f"convert {filename} -resize {width}x{height} /tmp/output.png"
        result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
        return result

    def evaluate_formula(self, expression: str) -> float:
        """Evaluate a user-supplied math formula from the request."""
        return eval(expression)

    def load_user_config(self, config_path: str) -> dict:
        """Load YAML configuration file supplied by the user."""
        with open(config_path) as f:
            return yaml.load(f)

    def restore_session(self, session_data: bytes) -> dict:
        """Restore a user session from serialised bytes."""
        return pickle.loads(session_data)

    def run_report(self, report_name: str) -> str:
        """Generate a named report and return its output."""
        os.system(f"python reports/{report_name}.py > /tmp/report.txt")
        return Path("/tmp/report.txt").read_text()
'''


class DemoResponse(BaseModel):
    source_code: str
    file_name:   str
    description: str


@router.get(
    "/demo",
    response_model=DemoResponse,
    summary="Return the built-in demo source code",
)
async def get_demo() -> DemoResponse:
    """Return the built-in vulnerable Python snippet for the demo."""
    return DemoResponse(
        source_code=_DEMO_SOURCE,
        file_name="demo_vulnerable.py",
        description=(
            "Production-style service class with 5 vulnerabilities: "
            "subprocess.check_output(shell=True), eval(), yaml.load(), "
            "pickle.loads(), and os.system() — all patched automatically."
        ),
    )
