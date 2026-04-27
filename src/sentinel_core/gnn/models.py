"""
Sentinel Core — GNN / Code Property Graph Data Models
Typed representations of graph nodes, edges, and the full CPG.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Node & Edge type enumerations
# ---------------------------------------------------------------------------

class NodeType(str, Enum):
    """Semantic categories of code entities in the graph."""
    MODULE = "MODULE"
    CLASS = "CLASS"
    FUNCTION = "FUNCTION"
    METHOD = "METHOD"
    PARAMETER = "PARAMETER"
    VARIABLE = "VARIABLE"
    ATTRIBUTE = "ATTRIBUTE"
    CALL = "CALL"
    IMPORT = "IMPORT"
    RETURN = "RETURN"
    LITERAL = "LITERAL"
    OPERATOR = "OPERATOR"
    BLOCK = "BLOCK"
    UNKNOWN = "UNKNOWN"


class EdgeType(str, Enum):
    """Directed relationships between code entities."""
    # Structural
    CONTAINS = "CONTAINS"       # parent → child scope
    DEFINES = "DEFINES"         # module/class → function/class
    # Data flow
    CALLS = "CALLS"             # call-site → callee
    USES = "USES"               # expression → variable/attribute
    ASSIGNS = "ASSIGNS"         # statement → variable
    RETURNS = "RETURNS"         # function → return value node
    # Control flow
    NEXT = "NEXT"               # cfg: statement → next statement
    # Import
    IMPORTS = "IMPORTS"         # module → imported name
    # Inheritance
    INHERITS = "INHERITS"       # class → base class


# ---------------------------------------------------------------------------
# Core graph primitives
# ---------------------------------------------------------------------------

@dataclass
class GraphNode:
    """
    A vertex in the Code Property Graph.

    Attributes:
        node_id:    Unique integer identifier within its CPG.
        node_type:  Semantic category.
        name:       Human-readable name (function name, variable name, …).
        start_line: First source line (0-indexed).
        end_line:   Last source line (0-indexed).
        source_text: The raw source snippet this node represents.
        metadata:   Arbitrary extra key-value pairs (e.g. ``{"is_async": True}``).
    """
    node_id: int
    node_type: NodeType
    name: str
    start_line: int = 0
    end_line: int = 0
    source_text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __hash__(self) -> int:
        return hash(self.node_id)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, GraphNode):
            return self.node_id == other.node_id
        return NotImplemented

    def __repr__(self) -> str:
        return f"GraphNode({self.node_id}, {self.node_type.value}, {self.name!r})"


@dataclass
class GraphEdge:
    """
    A directed edge in the Code Property Graph.

    Attributes:
        source_id: ``node_id`` of the origin node.
        target_id: ``node_id`` of the destination node.
        edge_type: Semantic relationship type.
        metadata:  Arbitrary extra key-value pairs.
    """
    source_id: int
    target_id: int
    edge_type: EdgeType
    metadata: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return (
            f"GraphEdge({self.source_id} "
            f"--[{self.edge_type.value}]--> "
            f"{self.target_id})"
        )


# ---------------------------------------------------------------------------
# The full Code Property Graph
# ---------------------------------------------------------------------------

@dataclass
class CodePropertyGraph:
    """
    A complete Code Property Graph for a single parsed file.

    Internally stores nodes and edges in plain Python dicts/lists for
    easy serialisation.  The corresponding ``networkx.DiGraph`` is built
    by :class:`~sentinel_core.gnn.graph_builder.CPGBuilder`.

    Attributes:
        source_path:  Path/label of the analysed file (may be ``None``).
        language:     Language of the source (e.g. ``"python"``).
        nodes:        All nodes keyed by ``node_id``.
        edges:        Ordered list of directed edges.
    """
    language: str
    nodes: dict[int, GraphNode] = field(default_factory=dict)
    edges: list[GraphEdge] = field(default_factory=list)
    source_path: Optional[str] = None

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def nodes_of_type(self, node_type: NodeType) -> list[GraphNode]:
        """Return all nodes matching a given :class:`NodeType`."""
        return [n for n in self.nodes.values() if n.node_type == node_type]

    def edges_of_type(self, edge_type: EdgeType) -> list[GraphEdge]:
        """Return all edges matching a given :class:`EdgeType`."""
        return [e for e in self.edges if e.edge_type == edge_type]

    def get_node(self, node_id: int) -> Optional[GraphNode]:
        return self.nodes.get(node_id)

    def add_node(self, node: GraphNode) -> None:
        self.nodes[node.node_id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        self.edges.append(edge)

    def __repr__(self) -> str:
        label = self.source_path or "<in-memory>"
        return (
            f"CodePropertyGraph({label!r}, "
            f"nodes={self.node_count}, edges={self.edge_count})"
        )
