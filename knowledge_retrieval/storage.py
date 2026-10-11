"""SQLite FTS5 Storage Engine for the Knowledge Retrieval System."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from knowledge_retrieval.models import (
    Document,
    DocumentLink,
    IndexStats,
    Section,
)


_CURRENT_SCHEMA_VERSION = 1

SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS documents (
    path TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL,
    title TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    mtime REAL NOT NULL,
    frontmatter_json TEXT NOT NULL,
    tags_json TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    status TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    indexed_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL REFERENCES documents(path) ON DELETE CASCADE,
    doc_id TEXT NOT NULL,
    section_id TEXT NOT NULL,
    heading TEXT NOT NULL,
    heading_level INTEGER NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    token_count INTEGER NOT NULL,
    content TEXT NOT NULL,
    UNIQUE(path, section_id)
);

CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_doc_id TEXT NOT NULL,
    source_path TEXT NOT NULL REFERENCES documents(path) ON DELETE CASCADE,
    target_ref TEXT NOT NULL,
    link_type TEXT NOT NULL,
    line_number INTEGER NOT NULL,
    text TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_documents_doc_id ON documents(doc_id);
CREATE INDEX IF NOT EXISTS idx_sections_path ON sections(path);
CREATE INDEX IF NOT EXISTS idx_sections_doc_id ON sections(doc_id);
CREATE INDEX IF NOT EXISTS idx_links_source_path ON links(source_path);
CREATE INDEX IF NOT EXISTS idx_links_source_id ON links(source_doc_id);
CREATE INDEX IF NOT EXISTS idx_links_target ON links(target_ref);

-- Full-Text Search on Sections using FTS5 with BM25
CREATE VIRTUAL TABLE IF NOT EXISTS sections_fts USING fts5(
    path UNINDEXED,
    doc_id UNINDEXED,
    section_id UNINDEXED,
    heading,
    content,
    tags,
    title,
    tokenize = 'porter unicode61'
);

-- Full-Text Search on Document overview
CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    path UNINDEXED,
    doc_id UNINDEXED,
    title,
    tags,
    content,
    tokenize = 'porter unicode61'
);

-- Auto-Update Pipeline Tables
CREATE TABLE IF NOT EXISTS monitored_sources (
    source_id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    display_name TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    topics_json TEXT NOT NULL,
    destination_doc_id TEXT NOT NULL,
    trust_tier TEXT NOT NULL,
    trust_rationale TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    polling_interval_seconds INTEGER NOT NULL DEFAULT 3600,
    last_checked_at REAL,
    last_observed_change_at REAL,
    last_fingerprint TEXT,
    last_etag TEXT,
    last_modified_header TEXT,
    last_error TEXT,
    retry_count INTEGER DEFAULT 0,
    config_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS change_candidates (
    candidate_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES monitored_sources(source_id) ON DELETE CASCADE,
    observed_at REAL NOT NULL,
    source_published_at REAL,
    prev_fingerprint TEXT,
    curr_fingerprint TEXT NOT NULL,
    change_type TEXT NOT NULL,
    change_summary TEXT NOT NULL,
    raw_content TEXT NOT NULL,
    normalized_content TEXT NOT NULL,
    affected_doc_ids_json TEXT NOT NULL,
    affected_topics_json TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    policy_decision TEXT NOT NULL,
    decision_rationale TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_update_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    doc_path TEXT NOT NULL,
    applied_at REAL NOT NULL,
    diff_summary TEXT NOT NULL,
    previous_content_hash TEXT NOT NULL,
    new_content_hash TEXT NOT NULL,
    applied_by TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_queue (
    queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id TEXT UNIQUE NOT NULL REFERENCES change_candidates(candidate_id) ON DELETE CASCADE,
    source_id TEXT NOT NULL,
    enqueued_at REAL NOT NULL,
    resolved_at REAL,
    resolution TEXT NOT NULL,
    reviewer_note TEXT
);
"""


class StorageEngine:
    """Manages the local SQLite database and FTS5 search indexes."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self):
        with self.get_connection() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)",
                (str(_CURRENT_SCHEMA_VERSION),)
            )

    def get_indexed_documents_map(self) -> Dict[str, Tuple[str, float]]:
        """Returns a map of {rel_path: (content_hash, mtime)} for incremental check."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT path, content_hash, mtime FROM documents")
            return {row["path"]: (row["content_hash"], row["mtime"]) for row in cursor.fetchall()}

    def get_document(self, doc_id: str) -> Optional[Document]:
        """Loads a document and its sections from storage by doc_id or path."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM documents WHERE doc_id = ? OR path = ?",
                (doc_id, doc_id)
            )
            row = cursor.fetchone()
            if not row:
                return None

            # Load sections
            s_cur = conn.execute(
                "SELECT * FROM sections WHERE doc_id = ? ORDER BY start_line ASC",
                (row["doc_id"],)
            )
            sections = [
                Section(
                    section_id=s["section_id"],
                    heading=s["heading"],
                    heading_level=s["heading_level"],
                    content=s["content"],
                    start_line=s["start_line"],
                    end_line=s["end_line"],
                    token_count=s["token_count"]
                )
                for s in s_cur.fetchall()
            ]

            # Load links
            l_cur = conn.execute(
                "SELECT * FROM links WHERE source_doc_id = ?",
                (row["doc_id"],)
            )
            links = [
                DocumentLink(
                    source_doc_id=l["source_doc_id"],
                    target_ref=l["target_ref"],
                    link_type=l["link_type"],
                    line_number=l["line_number"],
                    text=l["text"]
                )
                for l in l_cur.fetchall()
            ]

            tags = json.loads(row["tags_json"])
            fm = json.loads(row["frontmatter_json"])

            return Document(
                doc_id=row["doc_id"],
                path=row["path"],
                title=row["title"],
                content_hash=row["content_hash"],
                size_bytes=row["size_bytes"],
                mtime=row["mtime"],
                frontmatter=fm,
                tags=tags,
                doc_type=row["doc_type"],
                status=row["status"],
                sections=sections,
                links=links,
                token_count=row["token_count"]
            )

    def insert_or_replace_document(self, doc: Document):
        """Transactionally writes or updates a document, its sections, links, and FTS tables."""
        tags_str = " ".join(doc.tags)
        now = time.time()
        with self.get_connection() as conn:
            with conn:
                # 1. Clean up existing FTS entries for this path
                conn.execute("DELETE FROM sections_fts WHERE path = ?", (doc.path,))
                conn.execute("DELETE FROM documents_fts WHERE path = ?", (doc.path,))

                # 2. Insert/replace document record
                conn.execute(
                    """
                    INSERT OR REPLACE INTO documents (
                        path, doc_id, title, content_hash, size_bytes, mtime,
                        frontmatter_json, tags_json, doc_type, status, token_count, indexed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        doc.path,
                        doc.doc_id,
                        doc.title,
                        doc.content_hash,
                        doc.size_bytes,
                        doc.mtime,
                        json.dumps(doc.frontmatter),
                        json.dumps(doc.tags),
                        doc.doc_type,
                        doc.status,
                        doc.token_count,
                        now
                    )
                )

                # 3. Delete old sections and links for this path
                conn.execute("DELETE FROM sections WHERE path = ?", (doc.path,))
                conn.execute("DELETE FROM links WHERE source_path = ?", (doc.path,))

                # 4. Insert sections
                for sec in doc.sections:
                    conn.execute(
                        """
                        INSERT INTO sections (
                            path, doc_id, section_id, heading, heading_level,
                            start_line, end_line, token_count, content
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            doc.path,
                            doc.doc_id,
                            sec.section_id,
                            sec.heading,
                            sec.heading_level,
                            sec.start_line,
                            sec.end_line,
                            sec.token_count,
                            sec.content
                        )
                    )
                    # Insert into FTS
                    conn.execute(
                        """
                        INSERT INTO sections_fts (
                            path, doc_id, section_id, heading, content, tags, title
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            doc.path,
                            doc.doc_id,
                            sec.section_id,
                            sec.heading,
                            sec.content,
                            tags_str,
                            doc.title
                        )
                    )

                # 5. Insert links
                for link in doc.links:
                    conn.execute(
                        """
                        INSERT INTO links (
                            source_doc_id, source_path, target_ref, link_type, line_number, text
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            doc.doc_id,
                            doc.path,
                            link.target_ref,
                            link.link_type,
                            link.line_number,
                            link.text
                        )
                    )

                # 6. Insert full document into documents_fts
                conn.execute(
                    """
                    INSERT INTO documents_fts (
                        path, doc_id, title, tags, content
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        doc.path,
                        doc.doc_id,
                        doc.title,
                        tags_str,
                        doc.raw_content
                    )
                )

                conn.execute(
                    "INSERT OR REPLACE INTO meta (key, value) VALUES ('last_indexed_at', ?)",
                    (str(now),)
                )

    def delete_document(self, path_or_doc_id: str):
        """Removes a document and cleans all related indexes."""
        with self.get_connection() as conn:
            with conn:
                row = conn.execute(
                    "SELECT path, doc_id FROM documents WHERE path = ? OR doc_id = ?",
                    (path_or_doc_id, path_or_doc_id)
                ).fetchone()
                if row:
                    p = row["path"]
                    conn.execute("DELETE FROM sections_fts WHERE path = ?", (p,))
                    conn.execute("DELETE FROM documents_fts WHERE path = ?", (p,))
                    conn.execute("DELETE FROM documents WHERE path = ?", (p,))

    def get_all_documents(self) -> List[Document]:
        """Loads all documents (lightweight overview without full sections)."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM documents ORDER BY path ASC")
            docs = []
            for row in cursor.fetchall():
                docs.append(Document(
                    doc_id=row["doc_id"],
                    path=row["path"],
                    title=row["title"],
                    content_hash=row["content_hash"],
                    size_bytes=row["size_bytes"],
                    mtime=row["mtime"],
                    frontmatter=json.loads(row["frontmatter_json"]),
                    tags=json.loads(row["tags_json"]),
                    doc_type=row["doc_type"],
                    status=row["status"],
                    token_count=row["token_count"]
                ))
            return docs

    def get_all_links(self) -> List[DocumentLink]:
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM links")
            return [
                DocumentLink(
                    source_doc_id=l["source_doc_id"],
                    target_ref=l["target_ref"],
                    link_type=l["link_type"],
                    line_number=l["line_number"],
                    text=l["text"]
                )
                for l in cursor.fetchall()
            ]

    def get_stats(self) -> IndexStats:
        """Calculates current repository statistics from the index."""
        with self.get_connection() as conn:
            doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            sec_count = conn.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
            link_count = conn.execute("SELECT COUNT(*) FROM links").fetchone()[0]
            tokens = conn.execute("SELECT COALESCE(SUM(token_count), 0) FROM documents").fetchone()[0]
            meta_time = conn.execute("SELECT value FROM meta WHERE key = 'last_indexed_at'").fetchone()
            last_indexed = float(meta_time[0]) if meta_time and meta_time[0] else 0.0

        db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0

        return IndexStats(
            total_documents=doc_count,
            total_sections=sec_count,
            total_tokens=tokens,
            total_links=link_count,
            last_indexed_at=last_indexed,
            index_db_size_bytes=db_size
        )

    def clear(self):
        """Drops all indexed records for a complete clean rebuild."""
        with self.get_connection() as conn:
            with conn:
                conn.execute("DELETE FROM sections_fts")
                conn.execute("DELETE FROM documents_fts")
                conn.execute("DELETE FROM links")
                conn.execute("DELETE FROM sections")
                conn.execute("DELETE FROM documents")
                conn.execute("DELETE FROM meta WHERE key = 'last_indexed_at'")
