"""sentinel_core.gnn — Code Property Graph subsystem."""

from sentinel_core.gnn.graph_builder import CPGBuilder
from sentinel_core.gnn.models import (
    CodePropertyGraph,
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeType,
)

__all__ = [
    "CPGBuilder",
    "CodePropertyGraph",
    "EdgeType",
    "GraphEdge",
    "GraphNode",
    "NodeType",
]
