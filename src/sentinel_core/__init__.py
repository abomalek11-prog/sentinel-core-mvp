"""
sentinel_core — AI-powered code analysis and automated bug repair.

Public surface::

    from sentinel_core import CodeParser, CPGBuilder, settings
"""

from sentinel_core.config import settings
from sentinel_core.gnn import CPGBuilder, CodePropertyGraph
from sentinel_core.parsing import CodeParser, ParsedFile
from sentinel_core.utils import configure_logging, get_logger

__all__ = [
    "settings",
    "CodeParser",
    "ParsedFile",
    "CPGBuilder",
    "CodePropertyGraph",
    "configure_logging",
    "get_logger",
]

__version__ = "0.1.0"
