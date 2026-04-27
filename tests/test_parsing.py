"""Tests for the Tree-sitter code parser and AST models."""

from __future__ import annotations

from pathlib import Path

import pytest

from sentinel_core.parsing.models import ASTNode, ParsedFile, Position
from sentinel_core.parsing.parser import CodeParser


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def parser() -> CodeParser:
    return CodeParser()


SIMPLE_SOURCE = "def hello(): return 42"

CLASS_SOURCE = """\
class Greeter:
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"
"""

IMPORT_SOURCE = """\
import os
import sys
from pathlib import Path

x = 1
"""


# ---------------------------------------------------------------------------
# CodeParser.parse_source
# ---------------------------------------------------------------------------

class TestParseSource:
    def test_returns_parsed_file(self, parser: CodeParser) -> None:
        result = parser.parse_source(SIMPLE_SOURCE)
        assert isinstance(result, ParsedFile)

    def test_language_stored(self, parser: CodeParser) -> None:
        result = parser.parse_source(SIMPLE_SOURCE, language="python")
        assert result.language == "python"

    def test_source_stored(self, parser: CodeParser) -> None:
        result = parser.parse_source(SIMPLE_SOURCE)
        assert result.source == SIMPLE_SOURCE

    def test_no_syntax_errors_on_valid_code(self, parser: CodeParser) -> None:
        result = parser.parse_source(SIMPLE_SOURCE)
        assert result.has_errors is False

    def test_detects_syntax_errors(self, parser: CodeParser) -> None:
        broken = "def (: pass"
        result = parser.parse_source(broken)
        assert result.has_errors is True

    def test_root_is_ast_node(self, parser: CodeParser) -> None:
        result = parser.parse_source(SIMPLE_SOURCE)
        assert isinstance(result.root, ASTNode)
        assert result.root.node_type == "module"

    def test_unsupported_language_raises(self, parser: CodeParser) -> None:
        with pytest.raises(ValueError, match="Unsupported language"):
            parser.parse_source("code", language="cobol")

    def test_line_count(self, parser: CodeParser) -> None:
        result = parser.parse_source(CLASS_SOURCE)
        assert result.line_count == CLASS_SOURCE.count("\n") + 1

    def test_empty_source(self, parser: CodeParser) -> None:
        result = parser.parse_source("")
        assert result.has_errors is False
        assert result.root.node_type == "module"


# ---------------------------------------------------------------------------
# ASTNode traversal
# ---------------------------------------------------------------------------

class TestASTNodeTraversal:
    def test_find_all_function_definitions(self, parser: CodeParser) -> None:
        result = parser.parse_source(CLASS_SOURCE)
        funcs = result.find_all("function_definition")
        assert len(funcs) >= 1
        names = [f.text[:20] for f in funcs]
        assert any("greet" in n for n in names)

    def test_find_all_imports(self, parser: CodeParser) -> None:
        result = parser.parse_source(IMPORT_SOURCE)
        imports = result.find_all("import_statement")
        assert len(imports) >= 2

    def test_named_children(self, parser: CodeParser) -> None:
        result = parser.parse_source(SIMPLE_SOURCE)
        named = result.root.named_children()
        assert all(c.is_named for c in named)

    def test_is_leaf_on_leaf_node(self, parser: CodeParser) -> None:
        result = parser.parse_source("x = 1")
        # Walk to a leaf
        def find_leaf(node: ASTNode) -> ASTNode:
            if node.is_leaf:
                return node
            return find_leaf(node.children[0])
        leaf = find_leaf(result.root)
        assert leaf.is_leaf is True

    def test_position_row_col(self, parser: CodeParser) -> None:
        result = parser.parse_source(CLASS_SOURCE)
        assert isinstance(result.root.start, Position)
        assert result.root.start.row == 0
        assert result.root.start.column == 0

    def test_line_count_on_node(self, parser: CodeParser) -> None:
        result = parser.parse_source(CLASS_SOURCE)
        assert result.root.line_count >= 3


# ---------------------------------------------------------------------------
# CodeParser.parse_file
# ---------------------------------------------------------------------------

class TestParseFile:
    def test_parse_real_file(self, parser: CodeParser, tmp_path: Path) -> None:
        src_file = tmp_path / "sample.py"
        src_file.write_text("x = 42\ny = x + 1\n", encoding="utf-8")
        result = parser.parse_file(src_file)
        assert isinstance(result, ParsedFile)
        assert result.path == src_file
        assert result.has_errors is False

    def test_missing_file_raises(self, parser: CodeParser, tmp_path: Path) -> None:
        from sentinel_core.parsing.models import ParseError
        with pytest.raises(ParseError, match="File not found"):
            parser.parse_file(tmp_path / "nonexistent.py")

    def test_file_too_large_raises(
        self, parser: CodeParser, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from sentinel_core.parsing.models import ParseError
        from sentinel_core.parsing import parser as parser_module
        monkeypatch.setattr(parser_module.settings, "max_file_size_kb", 0)
        src_file = tmp_path / "big.py"
        src_file.write_text("x = 1\n", encoding="utf-8")
        with pytest.raises(ParseError, match="too large"):
            parser.parse_file(src_file)


# ---------------------------------------------------------------------------
# Supported languages
# ---------------------------------------------------------------------------

class TestSupportedLanguages:
    def test_python_is_supported(self, parser: CodeParser) -> None:
        assert "python" in parser.supported_languages()
