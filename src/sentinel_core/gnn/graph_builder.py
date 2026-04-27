"""
Sentinel Core — Code Property Graph Builder
Converts a ParsedFile (AST) into a NetworkX-backed CodePropertyGraph.
"""

from __future__ import annotations

from itertools import count
from typing import Optional

import networkx as nx

from sentinel_core.gnn.models import (
    CodePropertyGraph,
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeType,
)
from sentinel_core.parsing.models import ASTNode, ParsedFile
from sentinel_core.utils.logging import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# AST node-type → CPG NodeType mapping  (Python-specific)
# ---------------------------------------------------------------------------
_NODE_TYPE_MAP: dict[str, NodeType] = {
    "module": NodeType.MODULE,
    "class_definition": NodeType.CLASS,
    "function_definition": NodeType.FUNCTION,
    "decorated_definition": NodeType.FUNCTION,
    "parameters": NodeType.PARAMETER,
    "identifier": NodeType.VARIABLE,
    "attribute": NodeType.ATTRIBUTE,
    "call": NodeType.CALL,
    "import_statement": NodeType.IMPORT,
    "import_from_statement": NodeType.IMPORT,
    "return_statement": NodeType.RETURN,
    "string": NodeType.LITERAL,
    "integer": NodeType.LITERAL,
    "float": NodeType.LITERAL,
    "boolean": NodeType.LITERAL,
    "binary_operator": NodeType.OPERATOR,
    "comparison_operator": NodeType.OPERATOR,
    "assignment": NodeType.VARIABLE,
    "augmented_assignment": NodeType.VARIABLE,
    "block": NodeType.BLOCK,
}

# AST node types we skip from the graph (low-value punctuation / whitespace)
_SKIP_TYPES: frozenset[str] = frozenset(
    {
        "comment",
        "(",
        ")",
        "[",
        "]",
        "{",
        "}",
        ":",
        ",",
        ".",
        ";",
        "newline",
        "indent",
        "dedent",
    }
)


class CPGBuilder:
    """
    Builds a :class:`~sentinel_core.gnn.models.CodePropertyGraph` from a
    :class:`~sentinel_core.parsing.models.ParsedFile`.

    The builder performs two passes:
    1. **Node pass** — walk the AST, create a ``GraphNode`` for every
       meaningful AST node and add it to an internal ``networkx.DiGraph``.
    2. **Edge pass** — walk the graph and infer semantic edges
       (DEFINES, CALLS, IMPORTS, CONTAINS …).

    Usage::

        from sentinel_core.parsing.parser import CodeParser
        from sentinel_core.gnn.graph_builder import CPGBuilder

        parsed = CodeParser().parse_source("def greet(name): return name")
        cpg    = CPGBuilder().build(parsed)
        print(cpg)
    """

    def __init__(self) -> None:
        self._id_gen = count(0)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(self, parsed_file: ParsedFile) -> CodePropertyGraph:
        """
        Convert *parsed_file* into a ``CodePropertyGraph``.

        Args:
            parsed_file: Output of :class:`~sentinel_core.parsing.parser.CodeParser`.

        Returns:
            A populated :class:`~sentinel_core.gnn.models.CodePropertyGraph`.
        """
        log.info(
            "cpg_build_start",
            language=parsed_file.language,
            path=str(parsed_file.path) if parsed_file.path else "<snippet>",
        )

        cpg = CodePropertyGraph(
            language=parsed_file.language,
            source_path=str(parsed_file.path) if parsed_file.path else None,
        )

        # Reset ID generator for each new graph
        self._id_gen = count(0)

        # Pass 1: AST → nodes + CONTAINS edges
        self._walk(parsed_file.root, cpg, parent_graph_id=None)

        # Pass 2: semantic edge inference
        self._add_semantic_edges(cpg)

        log.info(
            "cpg_build_complete",
            nodes=cpg.node_count,
            edges=cpg.edge_count,
        )
        return cpg

    def to_networkx(self, cpg: CodePropertyGraph) -> nx.MultiDiGraph:
        """
        Convert a :class:`CodePropertyGraph` to a :class:`networkx.MultiDiGraph`.

        Nodes carry all :class:`GraphNode` attributes; edges carry
        ``edge_type``.

        Args:
            cpg: A built Code Property Graph.

        Returns:
            A ``networkx.MultiDiGraph`` ready for GNN analysis.
        """
        G: nx.MultiDiGraph = nx.MultiDiGraph()

        for node_id, gnode in cpg.nodes.items():
            G.add_node(
                node_id,
                node_type=gnode.node_type.value,
                name=gnode.name,
                start_line=gnode.start_line,
                end_line=gnode.end_line,
                source_text=gnode.source_text[:200],  # truncate for safety
                **gnode.metadata,
            )

        for edge in cpg.edges:
            G.add_edge(
                edge.source_id,
                edge.target_id,
                edge_type=edge.edge_type.value,
                **edge.metadata,
            )

        return G

    # ------------------------------------------------------------------
    # Internal: Pass 1 — AST walk
    # ------------------------------------------------------------------

    def _walk(
        self,
        ast_node: ASTNode,
        cpg: CodePropertyGraph,
        parent_graph_id: Optional[int],
    ) -> Optional[int]:
        """
        Recursively walk *ast_node* and populate *cpg* with nodes/edges.

        Returns the ``node_id`` assigned to *ast_node* (or ``None`` if the
        node was skipped).
        """
        if ast_node.node_type in _SKIP_TYPES:
            # Still recurse into skipped nodes' children
            for child in ast_node.children:
                self._walk(child, cpg, parent_graph_id)
            return None

        node_type = _NODE_TYPE_MAP.get(ast_node.node_type, NodeType.UNKNOWN)
        name = _extract_name(ast_node)

        graph_node = GraphNode(
            node_id=next(self._id_gen),
            node_type=node_type,
            name=name,
            start_line=ast_node.start.row,
            end_line=ast_node.end.row,
            source_text=ast_node.text[:300],
            metadata={"ast_type": ast_node.node_type},
        )
        cpg.add_node(graph_node)

        # CONTAINS edge from parent
        if parent_graph_id is not None:
            cpg.add_edge(GraphEdge(
                source_id=parent_graph_id,
                target_id=graph_node.node_id,
                edge_type=EdgeType.CONTAINS,
            ))

        for child in ast_node.children:
            self._walk(child, cpg, parent_graph_id=graph_node.node_id)

        return graph_node.node_id

    # ------------------------------------------------------------------
    # Internal: Pass 2 — Semantic edge inference
    # ------------------------------------------------------------------

    def _add_semantic_edges(self, cpg: CodePropertyGraph) -> None:
        """
        Scan existing nodes and add higher-level semantic edges.
        Currently infers: DEFINES, IMPORTS, CALLS, RETURNS.
        """
        # Build a lookup: name → list of node_ids (for CALLS resolution)
        name_index: dict[str, list[int]] = {}
        for nid, node in cpg.nodes.items():
            if node.name and node.name != "<unnamed>":
                name_index.setdefault(node.name, []).append(nid)

        # Walk nodes and emit semantic edges
        for node_id, node in list(cpg.nodes.items()):
            parent_ids = self._parents_of(node_id, cpg)

            # DEFINES: class/module DEFINES function or nested class
            if node.node_type in (NodeType.FUNCTION, NodeType.CLASS):
                for pid in parent_ids:
                    p = cpg.get_node(pid)
                    if p and p.node_type in (
                        NodeType.MODULE, NodeType.CLASS, NodeType.FUNCTION
                    ):
                        cpg.add_edge(GraphEdge(
                            source_id=pid,
                            target_id=node_id,
                            edge_type=EdgeType.DEFINES,
                        ))
                        break

            # IMPORTS: module IMPORTS name
            elif node.node_type == NodeType.IMPORT:
                for pid in parent_ids:
                    p = cpg.get_node(pid)
                    if p and p.node_type == NodeType.MODULE:
                        cpg.add_edge(GraphEdge(
                            source_id=pid,
                            target_id=node_id,
                            edge_type=EdgeType.IMPORTS,
                        ))
                        break

            # CALLS: call node → callee function (by name)
            elif node.node_type == NodeType.CALL:
                callee_name = _extract_call_name(node)
                if callee_name and callee_name in name_index:
                    for target_id in name_index[callee_name]:
                        if target_id != node_id:
                            cpg.add_edge(GraphEdge(
                                source_id=node_id,
                                target_id=target_id,
                                edge_type=EdgeType.CALLS,
                            ))

            # RETURNS: return statement linked to enclosing function
            elif node.node_type == NodeType.RETURN:
                enclosing_fn = self._find_ancestor_of_types(
                    node_id, cpg, [NodeType.FUNCTION, NodeType.METHOD]
                )
                if enclosing_fn is not None:
                    cpg.add_edge(GraphEdge(
                        source_id=enclosing_fn,
                        target_id=node_id,
                        edge_type=EdgeType.RETURNS,
                    ))

    def _find_ancestor_of_types(
        self, node_id: int, cpg: CodePropertyGraph, target_types: list[NodeType]
    ) -> Optional[int]:
        """
        Recursively search upwards through CONTAINS edges to find the
        nearest ancestor of a given type.
        """
        visited: set[int] = {node_id}
        queue = self._parents_of(node_id, cpg)

        while queue:
            pid = queue.pop(0)
            if pid in visited:
                continue
            visited.add(pid)

            p = cpg.get_node(pid)
            if p and p.node_type in target_types:
                return pid

            # Keep searching up
            queue.extend(self._parents_of(pid, cpg))

        return None

    def _parents_of(self, node_id: int, cpg: CodePropertyGraph) -> list[int]:
        """Return list of parent node IDs via CONTAINS edges."""
        return [
            e.source_id
            for e in cpg.edges_of_type(EdgeType.CONTAINS)
            if e.target_id == node_id
        ]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _extract_name(node: ASTNode) -> str:
    """
    Best-effort extraction of a human-readable name from an AST node.
    Looks for an ``identifier`` child first, then falls back to a
    truncated text snippet.
    """
    # Direct identifier child
    for child in node.children:
        if child.node_type == "identifier" and child.is_named:
            return child.text.strip()

    # Named node with short text
    text = node.text.strip()
    if len(text) <= 80 and "\n" not in text:
        return text or "<unnamed>"

    return "<unnamed>"


def _extract_call_name(call_node: GraphNode) -> Optional[str]:
    """
    Extract the callee name from a CALL GraphNode's source text.
    Handles simple ``func()`` and ``obj.method()`` patterns.
    """
    src = call_node.source_text.strip()
    # e.g. "foo(..." → "foo"
    paren_idx = src.find("(")
    if paren_idx == -1:
        return None
    callee = src[:paren_idx].strip()
    # obj.method → take last segment
    if "." in callee:
        callee = callee.split(".")[-1]
    return callee if callee.isidentifier() else None
