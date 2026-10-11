"""Data models for the Knowledge Retrieval System."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Section:
    """Represents an individual structural section within a Markdown document."""
    section_id: str
    heading: str
    heading_level: int
    content: str
    start_line: int
    end_line: int
    token_count: int = 0
    parent_heading: Optional[str] = None


@dataclass
class DocumentLink:
    """Represents a cross-reference link within a document."""
    source_doc_id: str
    target_ref: str
    link_type: str  # 'wikilink' or 'markdown'
    line_number: int
    text: str = ""


@dataclass
class Document:
    """Represents a canonical Markdown document."""
    doc_id: str
    path: str
    title: str
    content_hash: str
    size_bytes: int
    mtime: float
    frontmatter: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    doc_type: str = "general"
    status: str = "active"
    sections: List[Section] = field(default_factory=list)
    links: List[DocumentLink] = field(default_factory=list)
    raw_content: str = ""
    token_count: int = 0


@dataclass
class SearchResult:
    """Represents a single scored retrieval result at the section or document level."""
    doc_id: str
    path: str
    section_id: str
    heading: str
    heading_level: int
    start_line: int
    end_line: int
    snippet: str
    score: float
    match_source: str  # 'fts_bm25', 'title_match', 'tag_match', 'heading_match'
    token_count: int = 0
    tags: List[str] = field(default_factory=list)
    doc_title: str = ""


@dataclass
class ContextExcerpt:
    """An excerpt packaged into the final evidence package."""
    doc_id: str
    path: str
    section_id: str
    heading: str
    start_line: int
    end_line: int
    content: str
    relevance_score: float
    token_count: int
    cross_references: List[str] = field(default_factory=list)


@dataclass
class ContextPackage:
    """Evidence package assembled for an AI agent with token budgeting."""
    query: str
    excerpts: List[ContextExcerpt]
    total_tokens: int
    token_budget: int
    is_sufficient: bool
    unresolved_questions: List[str] = field(default_factory=list)
    missing_evidence_notice: Optional[str] = None
    insufficient_reason: Optional[str] = None


@dataclass
class DocumentOutlineNode:
    """A node in a document's structural outline."""
    section_id: str
    heading: str
    level: int
    start_line: int
    end_line: int
    token_count: int


@dataclass
class DocumentOutline:
    """Full outline of a document."""
    doc_id: str
    path: str
    title: str
    total_tokens: int
    sections: List[DocumentOutlineNode]


@dataclass
class IndexStats:
    """Statistical summary of the index."""
    total_documents: int
    total_sections: int
    total_tokens: int
    total_links: int
    last_indexed_at: float
    index_db_size_bytes: int
    index_version: int = 1


@dataclass
class IntegrityIssue:
    """Diagnostic issue discovered during an integrity audit."""
    severity: str  # 'ERROR', 'WARNING', 'INFO'
    issue_type: str  # 'broken_link', 'duplicate_id', 'orphaned_doc', 'malformed_frontmatter', 'missing_heading'
    doc_id: str
    path: str
    message: str
    line_number: Optional[int] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IntegrityReport:
    """Overall report from an integrity audit."""
    is_healthy: bool
    issues: List[IntegrityIssue] = field(default_factory=list)
    total_checked_docs: int = 0
    broken_link_count: int = 0
    duplicate_count: int = 0
    orphaned_count: int = 0
