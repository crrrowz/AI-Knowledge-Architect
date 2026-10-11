"""Knowledge Base Integrity Auditor for detecting broken links, duplicates, and structural issues."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Set

from knowledge_retrieval.models import IntegrityIssue, IntegrityReport
from knowledge_retrieval.storage import StorageEngine


class IntegrityAuditor:
    """Performs deep audits on link integrity, ID uniqueness, and structural hygiene."""

    def __init__(self, root_dir: str, storage: StorageEngine):
        self.root_dir = str(Path(root_dir).resolve())
        self.storage = storage

    def audit(self) -> IntegrityReport:
        """Runs comprehensive validation checks across all indexed documents."""
        issues: List[IntegrityIssue] = []
        docs = self.storage.get_all_documents()
        total_docs = len(docs)

        doc_id_to_paths: Dict[str, List[str]] = {}
        indexed_ids: Set[str] = set()
        indexed_paths: Set[str] = set()

        # 1. Check ID uniqueness & document hygiene
        for doc in docs:
            indexed_ids.add(doc.doc_id)
            indexed_paths.add(doc.path)
            doc_id_to_paths.setdefault(doc.doc_id, []).append(doc.path)

            # Check if file exists on disk
            abs_p = os.path.join(self.root_dir, doc.path)
            if not os.path.exists(abs_p):
                issues.append(IntegrityIssue(
                    severity="ERROR",
                    issue_type="stale_index",
                    doc_id=doc.doc_id,
                    path=doc.path,
                    message=f"Indexed document file does not exist on disk: {doc.path}"
                ))

            # Missing title or empty document
            if not doc.title or doc.title.lower() == "overview" and doc.size_bytes == 0:
                issues.append(IntegrityIssue(
                    severity="WARNING",
                    issue_type="missing_heading",
                    doc_id=doc.doc_id,
                    path=doc.path,
                    message=f"Document has no distinct title or content: {doc.path}"
                ))

            # Malformed frontmatter indicator
            if doc.frontmatter.get("_frontmatter_error"):
                issues.append(IntegrityIssue(
                    severity="ERROR",
                    issue_type="malformed_frontmatter",
                    doc_id=doc.doc_id,
                    path=doc.path,
                    message=f"YAML frontmatter could not be parsed: {doc.path}"
                ))

        # Check duplicates
        duplicate_count = 0
        for doc_id, paths in doc_id_to_paths.items():
            if len(paths) > 1:
                duplicate_count += 1
                issues.append(IntegrityIssue(
                    severity="ERROR",
                    issue_type="duplicate_id",
                    doc_id=doc_id,
                    path=", ".join(paths),
                    message=f"Duplicate document id '{doc_id}' shared across files: {paths}"
                ))

        # 2. Check broken links
        links = self.storage.get_all_links()
        broken_link_count = 0
        outgoing_docs: Set[str] = set()
        incoming_docs: Set[str] = set()

        for link in links:
            outgoing_docs.add(link.source_doc_id)
            target = link.target_ref.split("#")[0].strip()  # strip anchor
            if not target:
                continue

            # Target could be doc_id, path, or path without .md
            is_resolved = (
                target in indexed_ids or
                target in indexed_paths or
                (target + ".md") in indexed_paths or
                (target.replace(":", "/") + ".md") in indexed_paths
            )

            if is_resolved:
                incoming_docs.add(target)
            else:
                broken_link_count += 1
                issues.append(IntegrityIssue(
                    severity="ERROR",
                    issue_type="broken_link",
                    doc_id=link.source_doc_id,
                    path=link.source_doc_id,
                    line_number=link.line_number,
                    message=f"Broken {link.link_type} reference to '{link.target_ref}' from line {link.line_number}",
                    details={"target_ref": link.target_ref, "link_type": link.link_type}
                ))

        # 3. Check orphaned documents (zero links in or out, excluding tiny repos)
        orphaned_count = 0
        if total_docs > 3:
            for doc in docs:
                has_links = (doc.doc_id in outgoing_docs) or (doc.doc_id in incoming_docs) or (doc.path in incoming_docs)
                if not has_links:
                    orphaned_count += 1
                    issues.append(IntegrityIssue(
                        severity="INFO",
                        issue_type="orphaned_doc",
                        doc_id=doc.doc_id,
                        path=doc.path,
                        message=f"Document is isolated with no incoming or outgoing links: {doc.path}"
                    ))

        is_healthy = not any(i.severity == "ERROR" for i in issues)

        return IntegrityReport(
            is_healthy=is_healthy,
            issues=issues,
            total_checked_docs=total_docs,
            broken_link_count=broken_link_count,
            duplicate_count=duplicate_count,
            orphaned_count=orphaned_count
        )
