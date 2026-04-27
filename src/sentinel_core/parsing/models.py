"""
Sentinel Core — Parsing Data Models
Pydantic models representing parsed source code artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(slots=True)
class Position:
    """A zero-indexed (row, column) position inside a source file."""
    row: int
    column: int

    def __repr__(self) -> str:
        return f"{self.row}:{self.column}"


@dataclass
class ASTNode:
    """
    A single node in the Abstract Syntax Tree produced by Tree-sitter.

    Attributes:
        node_type:   Tree-sitter node type string (e.g. ``"function_definition"``).
        text:        Source text that this node spans (decoded UTF-8).
        start:       Start position in the source.
        end:         End position in the source.
        is_named:    Whether this is a *named* node (vs. anonymous punctuation).
        children:    Ordered list of child AST nodes.
        parent_type: Type string of the parent node (``None`` for root).
    """

    node_type: str
    text: str
    start: Position
    end: Position
    is_named: bool = True
    children: list[ASTNode] = field(default_factory=list)
    parent_type: Optional[str] = None

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def line_count(self) -> int:
        """Number of source lines this node spans."""
        return self.end.row - self.start.row + 1

    @property
    def is_leaf(self) -> bool:
        """True when this node has no children."""
        return len(self.children) == 0

    def named_children(self) -> list[ASTNode]:
        """Return only the named (non-anonymous) child nodes."""
        return [c for c in self.children if c.is_named]

    def find_all(self, node_type: str) -> list[ASTNode]:
        """
        Depth-first search for all descendant nodes of a given type.

        Args:
            node_type: The Tree-sitter type string to search for.

        Returns:
            A flat list of matching nodes in DFS order.
        """
        results: list[ASTNode] = []
        stack = list(self.children)
        while stack:
            node = stack.pop()
            if node.node_type == node_type:
                results.append(node)
            stack.extend(reversed(node.children))
        return results

    def __repr__(self) -> str:
        snippet = self.text[:40].replace("\n", "\\n")
        return f"ASTNode({self.node_type!r}, {self.start!r}, text={snippet!r})"


@dataclass
class ParsedFile:
    """
    The complete result of parsing a single source file.

    Attributes:
        path:       Absolute path to the source file (``None`` for in-memory snippets).
        source:     Original source code as a string.
        language:   Language identifier used for parsing (e.g. ``"python"``).
        root:       Root node of the AST.
        has_errors: True when Tree-sitter detected syntax errors in the source.
    """

    source: str
    language: str
    root: ASTNode
    path: Optional[Path] = None
    has_errors: bool = False

    @property
    def line_count(self) -> int:
        return self.source.count("\n") + 1

    @property
    def byte_size(self) -> int:
        return len(self.source.encode())

    def find_all(self, node_type: str) -> list[ASTNode]:
        """Convenience proxy to root.find_all()."""
        return self.root.find_all(node_type)

    def __repr__(self) -> str:
        name = self.path.name if self.path else "<snippet>"
        return (
            f"ParsedFile({name!r}, lang={self.language!r}, "
            f"lines={self.line_count}, errors={self.has_errors})"
        )


@dataclass
class ParseError(Exception):
    """Represents a failure to parse a source file."""

    message: str
    path: Optional[Path] = None
    source_snippet: Optional[str] = None

    def __str__(self) -> str:
        loc = str(self.path) if self.path else "<snippet>"
        return f"ParseError in {loc}: {self.message}"

    def __post_init__(self) -> None:
        super().__init__(self.message)
