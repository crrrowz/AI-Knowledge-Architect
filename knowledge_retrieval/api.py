"""High-level agent-facing interface for knowledge retrieval operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from knowledge_retrieval.context import ContextAssembler
from knowledge_retrieval.indexer import Indexer, IndexingReport
from knowledge_retrieval.integrity import IntegrityAuditor
from knowledge_retrieval.models import (
    ContextPackage,
    DocumentOutline,
    IndexStats,
    IntegrityReport,
    SearchResult,
    Section,
)
from knowledge_retrieval.retriever import Retriever


class KnowledgeEngine:
    """Canonical Agent-Facing facade for searching, reading, inspecting, and maintaining Markdown knowledge bases."""

    def __init__(self, root_dir: str = ".", db_path: Optional[str] = None):
        self.root_dir = str(Path(root_dir).resolve())
        self.indexer = Indexer(self.root_dir, db_path=db_path)
        self.storage = self.indexer.storage
        self.retriever = Retriever(self.storage)
        self.assembler = ContextAssembler(self.retriever)
        self.auditor = IntegrityAuditor(self.root_dir, self.storage)

    def sync_index(self) -> IndexingReport:
        """Incrementally indexes new or modified markdown documents."""
        return self.indexer.sync()

    def rebuild_index(self, scope: str = "all") -> IndexingReport:
        """Completely rebuilds the search index from canonical Markdown files."""
        return self.indexer.rebuild()

    def check_index_status(self) -> IndexStats:
        """Returns statistics on indexed documents, sections, tokens, and database size."""
        return self.indexer.get_stats()

    def search_knowledge(
        self,
        query: str,
        tags: Optional[List[str]] = None,
        doc_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Searches document sections and headings using FTS5 BM25 with metadata boosts.
        
        Returns clean JSON-serializable dictionaries for AI agent tools.
        """
        results: List[SearchResult] = self.retriever.search(
            query=query,
            tags=tags,
            doc_type=doc_type,
            limit=limit
        )
        return [
            {
                "doc_id": r.doc_id,
                "doc_title": r.doc_title,
                "path": r.path,
                "section_id": r.section_id,
                "heading": r.heading,
                "heading_level": r.heading_level,
                "start_line": r.start_line,
                "end_line": r.end_line,
                "score": r.score,
                "matched_snippet": r.snippet,
                "token_count": r.token_count,
                "tags": r.tags
            }
            for r in results
        ]

    def get_document_outline(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Returns structural outline of a document (headings, sections, line numbers) without loading body text."""
        outline: Optional[DocumentOutline] = self.retriever.get_document_outline(document_id)
        if not outline:
            return None
        return {
            "doc_id": outline.doc_id,
            "title": outline.title,
            "path": outline.path,
            "total_tokens": outline.total_tokens,
            "sections": [
                {
                    "section_id": s.section_id,
                    "heading": s.heading,
                    "level": s.level,
                    "start_line": s.start_line,
                    "end_line": s.end_line,
                    "token_count": s.token_count
                }
                for s in outline.sections
            ]
        }

    def read_section(self, document_id: str, section_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves exact section contents and line numbers from a specific document."""
        sec: Optional[Section] = self.retriever.read_section(document_id, section_id)
        if not sec:
            return None
        return {
            "section_id": sec.section_id,
            "heading": sec.heading,
            "heading_level": sec.heading_level,
            "start_line": sec.start_line,
            "end_line": sec.end_line,
            "content": sec.content,
            "token_count": sec.token_count
        }

    def get_related_documents(self, document_id: str) -> List[Dict[str, Any]]:
        """Traverses outgoing and incoming cross-references for a document."""
        return self.retriever.get_related_documents(document_id)

    def get_source_context(
        self,
        query: str,
        token_budget: int = 1500,
        max_sections: int = 5
    ) -> Dict[str, Any]:
        """Assembles a compact, token-bounded evidence package for an AI model."""
        pkg: ContextPackage = self.assembler.assemble(
            query=query,
            token_budget=token_budget,
            max_sections=max_sections
        )
        return {
            "query": pkg.query,
            "total_tokens": pkg.total_tokens,
            "token_budget": pkg.token_budget,
            "is_sufficient": pkg.is_sufficient,
            "unresolved_questions": pkg.unresolved_questions,
            "missing_evidence_notice": pkg.missing_evidence_notice,
            "insufficient_reason": pkg.insufficient_reason,
            "excerpts": [
                {
                    "doc_id": e.doc_id,
                    "path": e.path,
                    "section_id": e.section_id,
                    "heading": e.heading,
                    "start_line": e.start_line,
                    "end_line": e.end_line,
                    "relevance_score": e.relevance_score,
                    "token_count": e.token_count,
                    "content": e.content,
                    "cross_references": e.cross_references
                }
                for e in pkg.excerpts
            ]
        }

    def audit_integrity(self) -> Dict[str, Any]:
        """Validates internal link integrity, detects duplicates, and checks structural hygiene."""
        rep: IntegrityReport = self.auditor.audit()
        return {
            "is_healthy": rep.is_healthy,
            "total_checked_docs": rep.total_checked_docs,
            "broken_link_count": rep.broken_link_count,
            "duplicate_count": rep.duplicate_count,
            "orphaned_count": rep.orphaned_count,
            "issues": [
                {
                    "severity": i.severity,
                    "issue_type": i.issue_type,
                    "doc_id": i.doc_id,
                    "path": i.path,
                    "line_number": i.line_number,
                    "message": i.message,
                    "details": i.details
                }
                for i in rep.issues
            ]
        }
