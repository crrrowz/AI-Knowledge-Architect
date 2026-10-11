"""Incremental indexing engine that keeps SQLite FTS5 in sync with Markdown files."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from knowledge_retrieval.models import Document, IndexStats
from knowledge_retrieval.parser import parse_markdown_document
from knowledge_retrieval.storage import StorageEngine


IGNORED_DIRS = {
    ".git",
    ".knowledge_index",
    ".cache",
    ".pytest_cache",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build"
}


class IndexingReport:
    """Detailed results of an indexing execution."""
    def __init__(self):
        self.added_files: List[str] = []
        self.modified_files: List[str] = []
        self.deleted_files: List[str] = []
        self.unchanged_files: List[str] = []
        self.duration_seconds: float = 0.0

    @property
    def total_changes(self) -> int:
        return len(self.added_files) + len(self.modified_files) + len(self.deleted_files)


class Indexer:
    """Orchestrates incremental synchronization between the Markdown corpus and SQLite index."""

    def __init__(self, root_dir: str, db_path: Optional[str] = None):
        self.root_dir = str(Path(root_dir).resolve())
        if db_path is None:
            db_path = str(Path(self.root_dir) / ".knowledge_index" / "index.db")
        self.db_path = str(Path(db_path).resolve())
        self.storage = StorageEngine(self.db_path)

    def scan_markdown_files(self) -> Dict[str, str]:
        """Scans the root directory for all Markdown files.
        
        Returns:
            Dict mapping relative_path (forward slashes) -> absolute_path
        """
        md_files: Dict[str, str] = {}
        root_path = Path(self.root_dir)

        if not root_path.exists():
            return md_files

        for dirpath, dirnames, filenames in os.walk(self.root_dir):
            # Prune ignored directories in-place
            dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS and not d.startswith(".")]

            for fname in filenames:
                if fname.lower().endswith((".md", ".markdown")):
                    abs_path = os.path.join(dirpath, fname)
                    rel_path = os.path.relpath(abs_path, self.root_dir).replace("\\", "/")
                    md_files[rel_path] = abs_path

        return md_files

    def sync(self, force_rebuild: bool = False) -> IndexingReport:
        """Executes an incremental synchronization pass or full rebuild.
        
        Only parses and writes files whose mtime or SHA-256 content hash has changed.
        """
        start_time = time.time()
        report = IndexingReport()

        if force_rebuild:
            self.storage.clear()

        # Existing indexed state: {rel_path: (content_hash, mtime)}
        indexed_map = self.storage.get_indexed_documents_map()
        disk_files = self.scan_markdown_files()

        # 1. Detect deleted files
        for indexed_path in list(indexed_map.keys()):
            if indexed_path not in disk_files:
                self.storage.delete_document(indexed_path)
                report.deleted_files.append(indexed_path)

        # 2. Process current files on disk
        for rel_path, abs_path in disk_files.items():
            try:
                stat = os.stat(abs_path)
                mtime = stat.st_mtime
            except OSError:
                continue

            # Quick mtime check against cache
            if rel_path in indexed_map and not force_rebuild:
                cached_hash, cached_mtime = indexed_map[rel_path]
                if abs(mtime - cached_mtime) < 1e-4:
                    report.unchanged_files.append(rel_path)
                    continue

            # Read content and compute hash to prevent unnecessary reindexing
            try:
                with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except Exception:
                continue

            import hashlib
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

            if rel_path in indexed_map and not force_rebuild:
                cached_hash, _ = indexed_map[rel_path]
                if cached_hash == content_hash:
                    report.unchanged_files.append(rel_path)
                    continue
                # Hash differs -> modified
                doc = parse_markdown_document(abs_path, self.root_dir, raw_content=content)
                self.storage.insert_or_replace_document(doc)
                report.modified_files.append(rel_path)
            else:
                # Newly added
                doc = parse_markdown_document(abs_path, self.root_dir, raw_content=content)
                self.storage.insert_or_replace_document(doc)
                report.added_files.append(rel_path)

        report.duration_seconds = time.time() - start_time
        return report

    def rebuild(self) -> IndexingReport:
        """Forces a clean rebuild of the entire index from scratch."""
        return self.sync(force_rebuild=True)

    def get_stats(self) -> IndexStats:
        return self.storage.get_stats()
