"""LangGraph StateGraph orchestrating the Sentinel agent pipeline."""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from sentinel_core.agents.nodes import (
    detect_node,
    patch_node,
    reason_node,
    verify_node,
)
from sentinel_core.agents.state import AgentState
from sentinel_core.utils.logging import get_logger

log = get_logger(__name__)


def _route_after_detect(state: AgentState) -> str:
    """Route: skip pipeline when nothing found or error occurred."""
    if state.get("error"):
        log.warning("pipeline_short_circuit", reason=state["error"])
        return "end"
    if not state.get("vulnerabilities"):
        log.info("pipeline_short_circuit", reason="no vulnerabilities detected")
        return "end"
    return "reason"


def build_graph() -> Any:
    """Build and compile the Sentinel LangGraph pipeline.

    Topology:
        detect -(vulns found)-> reason -> patch -> verify -> END
               -(none/error)-----------------------------> END
    """
    workflow: StateGraph = StateGraph(AgentState)

    workflow.add_node("detect", detect_node)
    workflow.add_node("reason", reason_node)
    workflow.add_node("patch", patch_node)
    workflow.add_node("verify", verify_node)

    workflow.set_entry_point("detect")
    workflow.add_conditional_edges(
        "detect",
        _route_after_detect,
        {"reason": "reason", "end": END},
    )
    workflow.add_edge("reason", "patch")
    workflow.add_edge("patch", "verify")
    workflow.add_edge("verify", END)

    return workflow.compile()


def run_pipeline(
    source_code: str,
    file_path: str = "<unknown>",
    language: str = "python",
    cpg_graph: Any = None,
) -> AgentState:
    """Execute the full agent pipeline synchronously.

    Args:
        source_code: Raw source code to analyse.
        file_path: Display path of the source file.
        language: Programming language identifier.
        cpg_graph: NetworkX DiGraph from Phase 1 GraphBuilder.

    Returns:
        Final AgentState with all fields populated.
    """
    log.info("pipeline_start", file=file_path, language=language)

    initial: AgentState = {
        "source_code": source_code,
        "file_path": file_path,
        "language": language,
        "parsed_file": {},
        "cpg": {"graph": cpg_graph},
        "vulnerabilities": [],
        "reasoning": [],
        "proposed_patches": [],
        "patch_report": {},
        "verification_results": [],
        "sandbox_verification": {},
        "confidence_score": 1.0,
        "confidence_breakdown": {
            "static_safety": 1.0,
            "behavioural_match": 1.0,
            "patch_complexity": 1.0,
            "cpg_coverage": 1.0,
            "overall": 1.0,
        },
        "llm_model": "none",
        "error": None,
    }

    compiled = build_graph()
    result: AgentState = compiled.invoke(initial)

    log.info(
        "pipeline_done",
        vulns=len(result.get("vulnerabilities", [])),
        patches=len(result.get("proposed_patches", [])),
    )
    return result
