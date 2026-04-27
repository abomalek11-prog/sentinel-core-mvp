"""Tests for the CPG graph builder."""

from __future__ import annotations

import pytest

from sentinel_core.gnn.graph_builder import CPGBuilder
from sentinel_core.gnn.models import (
    CodePropertyGraph,
    EdgeType,
    NodeType,
)
from sentinel_core.parsing.parser import CodeParser


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def parser() -> CodeParser:
    return CodeParser()


@pytest.fixture
def builder() -> CPGBuilder:
    return CPGBuilder()


def build_cpg(source: str) -> CodePropertyGraph:
    p = CodeParser()
    b = CPGBuilder()
    return b.build(p.parse_source(source))


# ---------------------------------------------------------------------------
# Basic graph properties
# ---------------------------------------------------------------------------

class TestCPGBasics:
    def test_returns_cpg_instance(self) -> None:
        cpg = build_cpg("x = 1")
        assert isinstance(cpg, CodePropertyGraph)

    def test_has_nodes(self) -> None:
        cpg = build_cpg("x = 1")
        assert cpg.node_count > 0

    def test_has_edges(self) -> None:
        cpg = build_cpg("x = 1\ny = x + 2")
        assert cpg.edge_count > 0

    def test_language_stored(self) -> None:
        cpg = build_cpg("pass")
        assert cpg.language == "python"

    def test_empty_source(self) -> None:
        cpg = build_cpg("")
        assert isinstance(cpg, CodePropertyGraph)

    def test_node_ids_unique(self) -> None:
        cpg = build_cpg("def f(): pass\ndef g(): return 1")
        ids = list(cpg.nodes.keys())
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Node types
# ---------------------------------------------------------------------------

class TestNodeTypes:
    def test_has_module_node(self) -> None:
        cpg = build_cpg("x = 1")
        modules = cpg.nodes_of_type(NodeType.MODULE)
        assert len(modules) >= 1

    def test_detects_function(self) -> None:
        cpg = build_cpg("def add(a, b): return a + b")
        funcs = cpg.nodes_of_type(NodeType.FUNCTION)
        assert len(funcs) >= 1

    def test_detects_class(self) -> None:
        cpg = build_cpg("class Foo:\n    pass")
        classes = cpg.nodes_of_type(NodeType.CLASS)
        assert len(classes) >= 1

    def test_detects_import(self) -> None:
        cpg = build_cpg("import os\nimport sys")
        imports = cpg.nodes_of_type(NodeType.IMPORT)
        assert len(imports) >= 2

    def test_detects_return(self) -> None:
        cpg = build_cpg("def f():\n    return 42")
        returns = cpg.nodes_of_type(NodeType.RETURN)
        assert len(returns) >= 1

    def test_multiple_functions(self) -> None:
        src = "def a(): pass\ndef b(): pass\ndef c(): pass"
        cpg = build_cpg(src)
        funcs = cpg.nodes_of_type(NodeType.FUNCTION)
        assert len(funcs) >= 3


# ---------------------------------------------------------------------------
# Edge types
# ---------------------------------------------------------------------------

class TestEdgeTypes:
    def test_contains_edges_exist(self) -> None:
        cpg = build_cpg("def f():\n    x = 1")
        contains = cpg.edges_of_type(EdgeType.CONTAINS)
        assert len(contains) > 0

    def test_defines_edges_for_function(self) -> None:
        cpg = build_cpg("def hello(): pass")
        defines = cpg.edges_of_type(EdgeType.DEFINES)
        assert len(defines) >= 1

    def test_imports_edges_exist(self) -> None:
        cpg = build_cpg("import os")
        imports = cpg.edges_of_type(EdgeType.IMPORTS)
        assert len(imports) >= 1

    def test_returns_edge_linked_to_function(self) -> None:
        cpg = build_cpg("def f():\n    return 99")
        returns = cpg.edges_of_type(EdgeType.RETURNS)
        assert len(returns) >= 1
        # source must be a FUNCTION node
        for edge in returns:
            src_node = cpg.get_node(edge.source_id)
            assert src_node is not None
            assert src_node.node_type == NodeType.FUNCTION

    def test_edge_source_target_exist(self) -> None:
        cpg = build_cpg("def f(): pass")
        for edge in cpg.edges:
            assert cpg.get_node(edge.source_id) is not None
            assert cpg.get_node(edge.target_id) is not None


# ---------------------------------------------------------------------------
# NetworkX conversion
# ---------------------------------------------------------------------------

class TestNetworkXConversion:
    def test_to_networkx_returns_digraph(self) -> None:
        import networkx as nx
        cpg = build_cpg("def f(): return 1")
        b = CPGBuilder()
        G = b.to_networkx(cpg)
        assert isinstance(G, nx.MultiDiGraph)

    def test_node_count_matches(self) -> None:
        cpg = build_cpg("class A:\n    def m(self): pass")
        b = CPGBuilder()
        G = b.to_networkx(cpg)
        assert G.number_of_nodes() == cpg.node_count

    def test_edge_count_matches(self) -> None:
        cpg = build_cpg("def f():\n    return 1")
        b = CPGBuilder()
        G = b.to_networkx(cpg)
        assert G.number_of_edges() == cpg.edge_count

    def test_node_has_type_attribute(self) -> None:
        cpg = build_cpg("x = 1")
        b = CPGBuilder()
        G = b.to_networkx(cpg)
        for _, data in G.nodes(data=True):
            assert "node_type" in data


# ---------------------------------------------------------------------------
# Source path propagation
# ---------------------------------------------------------------------------

class TestSourcePath:
    def test_no_path_for_snippet(self) -> None:
        cpg = build_cpg("x = 1")
        assert cpg.source_path is None

    def test_path_stored_from_file(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        src = tmp_path / "demo.py"
        src.write_text("y = 2\n", encoding="utf-8")
        p = CodeParser()
        b = CPGBuilder()
        parsed = p.parse_file(src)
        cpg = b.build(parsed)
        assert cpg.source_path is not None
        assert "demo.py" in cpg.source_path
