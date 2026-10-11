"""AI Knowledge Architect - High-Efficiency Local Markdown Knowledge Retrieval System."""

from knowledge_retrieval.api import KnowledgeEngine
from knowledge_retrieval.models import (
    ContextExcerpt,
    ContextPackage,
    Document,
    DocumentLink,
    DocumentOutline,
    DocumentOutlineNode,
    IndexStats,
    IntegrityIssue,
    IntegrityReport,
    SearchResult,
    Section,
)

__all__ = [
    "KnowledgeEngine",
    "Document",
    "Section",
    "DocumentLink",
    "SearchResult",
    "ContextExcerpt",
    "ContextPackage",
    "DocumentOutline",
    "DocumentOutlineNode",
    "IndexStats",
    "IntegrityIssue",
    "IntegrityReport",
]

__version__ = "0.1.0"
