"""Search and retrieval pipeline supporting section-level BM25 search, outline generation, and cross-reference traversal."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

from knowledge_retrieval.models import (
    Document,
    DocumentOutline,
    DocumentOutlineNode,
    SearchResult,
    Section,
)
from knowledge_retrieval.storage import StorageEngine


def _sanitize_fts_query(query: str) -> str:
    """Prepares user query for safe FTS5 syntax, avoiding syntax errors from special chars."""
    # Remove FTS5 operators like NOT, AND, OR if naked, and punctuation quotes
    cleaned = re.sub(r'[^\w\s-]', ' ', query)
    tokens = [t.strip() for t in cleaned.split() if t.strip()]
    if not tokens:
        return ""
    # Treat each word as prefix match token or exact token: "tok"*
    fts_tokens = [f'"{t}"*' for t in tokens]
    return " AND ".join(fts_tokens)


class Retriever:
    """Layered retrieval engine operating over the SQLite FTS5 store."""

    def __init__(self, storage: StorageEngine):
        self.storage = storage

    def search(
        self,
        query: str,
        tags: Optional[List[str]] = None,
        doc_type: Optional[str] = None,
        limit: int = 10,
        min_score: float = -100.0
    ) -> List[SearchResult]:
        """Performs section-level BM25 full-text search with metadata ranking boost."""
        query = query.strip()
        if not query:
            return []

        fts_query = _sanitize_fts_query(query)
        if not fts_query:
            return []

        results: List[SearchResult] = []
        with self.storage.get_connection() as conn:
            # Query sections_fts using bm25() ranking function.
            # bm25 weights: (heading=5.0, content=1.0, tags=2.0, title=3.0)
            # In SQLite FTS5 bm25(table, w0, w1, ...): lower values mean better match (more negative/closer to 0).
            # We invert to positive score for clarity: score = -bm25_val.
            sql = """
                SELECT 
                    s.doc_id,
                    d.path,
                    d.title AS doc_title,
                    d.tags_json,
                    d.doc_type,
                    s.section_id,
                    s.heading,
                    s.heading_level,
                    s.start_line,
                    s.end_line,
                    s.token_count,
                    snippet(sections_fts, 1, '«', '»', '...', 25) AS matched_snippet,
                    bm25(sections_fts, 5.0, 1.0, 2.0, 3.0) AS bm25_score
                FROM sections_fts
                JOIN sections s ON sections_fts.doc_id = s.doc_id AND sections_fts.section_id = s.section_id
                JOIN documents d ON s.doc_id = d.doc_id
                WHERE sections_fts MATCH ?
            """
            params: List[Any] = [fts_query]

            if doc_type:
                sql += " AND d.doc_type = ?"
                params.append(doc_type)

            sql += " ORDER BY bm25_score ASC LIMIT ?"
            params.append(limit * 2)

            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()

            for row in rows:
                import json
                doc_tags = json.loads(row["tags_json"])
                if tags and not any(t.lower() in [dt.lower() for dt in doc_tags] for t in tags):
                    continue

                # Invert SQLite bm25 score (which is negative) to positive
                # Lower bm25 value = better rank in SQLite FTS5
                raw_score = -float(row["bm25_score"])

                # Boost if query words appear in section heading or doc title
                boost = 0.0
                q_words = query.lower().split()
                if any(w in row["heading"].lower() for w in q_words):
                    boost += 2.0
                if any(w in row["doc_title"].lower() for w in q_words):
                    boost += 1.5

                final_score = raw_score + boost

                if final_score < min_score:
                    continue

                results.append(SearchResult(
                    doc_id=row["doc_id"],
                    path=row["path"],
                    section_id=row["section_id"],
                    heading=row["heading"],
                    heading_level=row["heading_level"],
                    start_line=row["start_line"],
                    end_line=row["end_line"],
                    snippet=row["matched_snippet"],
                    score=round(final_score, 4),
                    match_source="fts_bm25",
                    token_count=row["token_count"],
                    tags=doc_tags,
                    doc_title=row["doc_title"]
                ))

        # Re-sort by final boosted score descending and clamp to limit
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]

    def get_document_outline(self, doc_id_or_path: str) -> Optional[DocumentOutline]:
        """Returns the high-level structural outline of a document without loading the full body text."""
        doc = self.storage.get_document(doc_id_or_path)
        if not doc:
            return None

        nodes = [
            DocumentOutlineNode(
                section_id=sec.section_id,
                heading=sec.heading,
                level=sec.heading_level,
                start_line=sec.start_line,
                end_line=sec.end_line,
                token_count=sec.token_count
            )
            for sec in doc.sections
        ]

        return DocumentOutline(
            doc_id=doc.doc_id,
            path=doc.path,
            title=doc.title,
            total_tokens=doc.token_count,
            sections=nodes
        )

    def read_section(self, doc_id_or_path: str, section_id: str) -> Optional[Section]:
        """Retrieves exactly one targeted section by ID from a document."""
        doc = self.storage.get_document(doc_id_or_path)
        if not doc:
            return None
        for sec in doc.sections:
            if sec.section_id.lower() == section_id.lower():
                return sec
        return None

    def get_related_documents(self, doc_id_or_path: str) -> List[Dict[str, Any]]:
        """Finds all forward and backward linked documents for a given document."""
        doc = self.storage.get_document(doc_id_or_path)
        if not doc:
            return []

        related: List[Dict[str, Any]] = []
        with self.storage.get_connection() as conn:
            # 1. Forward links (links from this doc to others)
            f_cur = conn.execute(
                """
                SELECT target_ref, link_type, line_number, text 
                FROM links WHERE source_doc_id = ?
                """,
                (doc.doc_id,)
            )
            for row in f_cur.fetchall():
                target = row["target_ref"]
                # Resolve target doc if indexed
                resolved = conn.execute(
                    "SELECT doc_id, path, title FROM documents WHERE doc_id = ? OR path = ?",
                    (target, target)
                ).fetchone()

                related.append({
                    "direction": "outgoing",
                    "target_ref": target,
                    "resolved_doc_id": resolved["doc_id"] if resolved else None,
                    "resolved_path": resolved["path"] if resolved else None,
                    "resolved_title": resolved["title"] if resolved else None,
                    "link_type": row["link_type"],
                    "line_number": row["line_number"],
                    "text": row["text"]
                })

            # 2. Backlinks (links pointing to this doc)
            b_cur = conn.execute(
                """
                SELECT l.source_doc_id, d.path, d.title, l.link_type, l.line_number, l.text
                FROM links l
                JOIN documents d ON l.source_doc_id = d.doc_id
                WHERE l.target_ref = ? OR l.target_ref = ?
                """,
                (doc.doc_id, doc.path)
            )
            for row in b_cur.fetchall():
                related.append({
                    "direction": "incoming",
                    "target_ref": doc.doc_id,
                    "resolved_doc_id": row["source_doc_id"],
                    "resolved_path": row["path"],
                    "resolved_title": row["title"],
                    "link_type": row["link_type"],
                    "line_number": row["line_number"],
                    "text": row["text"]
                })

        return related
