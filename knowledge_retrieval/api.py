"""High-level agent-facing interface for knowledge retrieval operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from knowledge_retrieval.auto_update_store import AutoUpdateStore
from knowledge_retrieval.auto_updater import AutoUpdater
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
        self.auto_update_store = AutoUpdateStore(self.storage)
        self.auto_updater = AutoUpdater(self.root_dir, self.auto_update_store, self.indexer)

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

    # =========================================================================
    # Autonomous Knowledge Update Pipeline Methods
    # =========================================================================

    def register_source(
        self,
        source_id: str,
        source_type: str,
        display_name: str,
        canonical_url: str,
        destination_doc_id: str,
        topics: Optional[List[str]] = None,
        trust_tier: str = "official",
        trust_rationale: str = "Authoritative official repository",
        polling_interval: int = 3600,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Registers an official documentation website or GitHub repository for monitoring."""
        src = self.auto_updater.register_source(
            source_id=source_id,
            source_type=source_type,
            display_name=display_name,
            canonical_url=canonical_url,
            destination_doc_id=destination_doc_id,
            topics=topics,
            trust_tier=trust_tier,
            trust_rationale=trust_rationale,
            polling_interval=polling_interval,
            config=config
        )
        return {
            "source_id": src.source_id,
            "display_name": src.display_name,
            "canonical_url": src.canonical_url,
            "destination_doc_id": src.destination_doc_id,
            "trust_tier": src.trust_tier.value,
            "status": "registered"
        }

    def list_sources(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """Lists all registered knowledge sources."""
        return self.auto_updater.list_sources(enabled_only=enabled_only)

    def remove_source(self, source_id: str) -> bool:
        """Removes a source from monitoring."""
        return self.auto_updater.remove_source(source_id)

    def check_updates(self, source_id: Optional[str] = None) -> Any:
        """Polls sources, verifies changes, and applies safe updates or enqueues for review."""
        if source_id:
            return self.auto_updater.check_source(source_id)
        return self.auto_updater.check_all_sources()

    def list_review_queue(self, status: str = "PENDING") -> List[Dict[str, Any]]:
        """Lists changes requiring human review and approval."""
        return self.auto_updater.list_review_queue(status=status)

    def approve_update(self, candidate_id: str, note: Optional[str] = None) -> Dict[str, Any]:
        """Approves and applies a candidate queued for review."""
        return self.auto_updater.approve_review_item(candidate_id, note=note)

    def reject_update(self, candidate_id: str, note: Optional[str] = None) -> Dict[str, Any]:
        """Rejects a candidate queued for review."""
        return self.auto_updater.reject_review_item(candidate_id, note=note)

    def list_update_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Returns the audit trail of applied knowledge updates."""
        return self.auto_updater.list_history(limit=limit)
