"""
Sentinel Core — Code Parser (Tree-sitter backend)
Converts raw source code into a structured ASTNode tree.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

import tree_sitter_python as tspython
from tree_sitter import Language, Node, Parser

from sentinel_core.config import settings
from sentinel_core.parsing.models import ASTNode, ParseError, ParsedFile, Position
from sentinel_core.utils.logging import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Language registry — extend here to add more languages (JS, Go, Rust …)
# ---------------------------------------------------------------------------
_LANGUAGE_MAP: dict[str, Language] = {
    "python": Language(tspython.language()),
}


class CodeParser:
    """
    Thin wrapper around Tree-sitter for parsing source code.

    Supports Python out-of-the-box.  Additional languages can be registered
    by extending ``_LANGUAGE_MAP`` above.

    Usage::

        parser = CodeParser()

        # From a file path
        result = parser.parse_file(Path("main.py"))

        # From a raw string
        result = parser.parse_source("def hello(): return 42")
    """

    def __init__(self) -> None:
        self._parsers: dict[str, Parser] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse_file(self, path: Union[str, Path]) -> ParsedFile:
        """
        Read *path* from disk and parse it.

        Args:
            path: Path to the source file.

        Returns:
            A :class:`~sentinel_core.parsing.models.ParsedFile` instance.

        Raises:
            ParseError: If the file cannot be read or exceeds the size limit.
        """
        path = Path(path).resolve()
        log.debug("parsing_file", path=str(path))

        if not path.exists():
            raise ParseError(message=f"File not found: {path}", path=path)

        size_kb = path.stat().st_size / 1024
        if size_kb > settings.max_file_size_kb:
            raise ParseError(
                message=(
                    f"File too large: {size_kb:.1f} KB "
                    f"(limit: {settings.max_file_size_kb} KB)"
                ),
                path=path,
            )

        source = path.read_text(encoding="utf-8", errors="replace")
        language = _detect_language(path)

        parsed = self.parse_source(source, language=language)
        parsed.path = path
        return parsed

    def parse_source(
        self,
        source: str,
        language: str = "python",
    ) -> ParsedFile:
        """
        Parse *source* code string directly (no file I/O).

        Args:
            source:   Raw source code string.
            language: Language identifier (default: ``"python"``).

        Returns:
            A :class:`~sentinel_core.parsing.models.ParsedFile` instance.

        Raises:
            ValueError: If the language is not supported.
            ParseError: If tree-sitter encounters an unrecoverable error.
        """
        if language not in _LANGUAGE_MAP:
            supported = ", ".join(_LANGUAGE_MAP)
            raise ValueError(
                f"Unsupported language {language!r}. Supported: {supported}"
            )

        ts_parser = self._get_parser(language)
        source_bytes = source.encode("utf-8")
        tree = ts_parser.parse(source_bytes)

        has_errors = tree.root_node.has_error
        if has_errors:
            log.warning("syntax_errors_detected", language=language)

        root_ast = _convert_node(
            tree.root_node,
            source_bytes=source_bytes,
            depth=0,
            max_depth=settings.max_ast_depth,
        )

        log.info(
            "parse_complete",
            language=language,
            lines=source.count("\n") + 1,
            has_errors=has_errors,
        )

        return ParsedFile(
            source=source,
            language=language,
            root=root_ast,
            has_errors=has_errors,
        )

    def supported_languages(self) -> list[str]:
        """Return list of supported language identifiers."""
        return list(_LANGUAGE_MAP.keys())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_parser(self, language: str) -> Parser:
        """Return (and cache) a Tree-sitter Parser for the given language."""
        if language not in self._parsers:
            ts_lang = _LANGUAGE_MAP[language]
            p = Parser(ts_lang)
            self._parsers[language] = p
        return self._parsers[language]


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _detect_language(path: Path) -> str:
    """Infer language from file extension."""
    ext_map: dict[str, str] = {
        ".py": "python",
    }
    return ext_map.get(path.suffix.lower(), settings.default_language)


def _convert_node(
    node: Node,
    source_bytes: bytes,
    depth: int,
    max_depth: int,
    parent_type: str | None = None,
) -> ASTNode:
    """
    Recursively convert a Tree-sitter ``Node`` into an :class:`ASTNode`.

    Args:
        node:        The Tree-sitter node to convert.
        source_bytes: Full source encoded as bytes (for text extraction).
        depth:       Current recursion depth.
        max_depth:   Recursion limit to prevent stack overflow on huge files.
        parent_type: Type of the parent node (for context).

    Returns:
        Populated :class:`ASTNode` tree.
    """
    text = source_bytes[node.start_byte: node.end_byte].decode("utf-8", errors="replace")

    ast_node = ASTNode(
        node_type=node.type,
        text=text,
        start=Position(row=node.start_point[0], column=node.start_point[1]),
        end=Position(row=node.end_point[0], column=node.end_point[1]),
        is_named=node.is_named,
        parent_type=parent_type,
    )

    if depth < max_depth:
        for child in node.children:
            child_ast = _convert_node(
                child,
                source_bytes=source_bytes,
                depth=depth + 1,
                max_depth=max_depth,
                parent_type=node.type,
            )
            ast_node.children.append(child_ast)
    else:
        log.warning("max_ast_depth_reached", depth=depth, node_type=node.type)

    return ast_node
