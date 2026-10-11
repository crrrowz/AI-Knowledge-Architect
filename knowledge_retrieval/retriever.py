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


_STOPWORDS = {
    'what', 'is', 'the', 'a', 'an', 'of', 'to', 'in', 'for', 'on', 'with', 'as', 
    'by', 'at', 'from', 'how', 'why', 'where', 'when', 'which', 'does', 'can', 'are', 'do'
}


def _extract_query_tokens(query: str) -> Tuple[List[str], List[str]]:
    """Extracts raw and content tokens from query, splitting on punctuation."""
    cleaned = re.sub(r'[^\w\s]', ' ', query)
    tokens = [t.strip() for t in cleaned.split() if t.strip()]
    if not tokens:
        return [], []
    content_tokens = [t for t in tokens if t.lower() not in _STOPWORDS]
    return tokens, content_tokens or tokens


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

        all_tokens, content_tokens = _extract_query_tokens(query)
        if not content_tokens:
            return []

        # 1. Primary query: AND of content tokens
        and_fts = " AND ".join(f'"{t}"*' for t in content_tokens)
        # 2. Secondary fallback query: OR of content tokens
        or_fts = " OR ".join(f'"{t}"*' for t in content_tokens)

        results_dict: Dict[Tuple[str, str], SearchResult] = {}

        def _execute_fts(fts_match_expr: str):
            with self.storage.get_connection() as conn:
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
                        s.content,
                        snippet(sections_fts, 4, '«', '»', '...', 25) AS matched_snippet,
                        bm25(sections_fts, 0.0, 0.0, 0.0, 5.0, 1.0, 2.0, 3.0) AS bm25_score
                    FROM sections_fts
                    JOIN sections s ON sections_fts.path = s.path AND sections_fts.section_id = s.section_id
                    JOIN documents d ON s.path = d.path
                    WHERE sections_fts MATCH ?
                """
                params: List[Any] = [fts_match_expr]

                if doc_type:
                    sql += " AND d.doc_type = ?"
                    params.append(doc_type)

                sql += " ORDER BY bm25_score ASC LIMIT ?"
                params.append(limit * 2)

                cursor = conn.execute(sql, params)
                for row in cursor.fetchall():
                    import json
                    doc_tags = json.loads(row["tags_json"])
                    if tags and not any(t.lower() in [dt.lower() for dt in doc_tags] for t in tags):
                        continue

                    # Verify query term coverage to prevent single-token false positives
                    sec_text_lower = (row["heading"] + " " + row["content"] + " " + row["doc_title"]).lower()
                    matched_terms_count = sum(1 for t in content_tokens if t.lower() in sec_text_lower)
                    
                    min_required = 1 if len(content_tokens) <= 1 else max(2, int(len(content_tokens) * 0.5))
                    if matched_terms_count < min_required:
                        continue

                    raw_score = -float(row["bm25_score"])

                    # Boost if query words appear in section heading or doc title
                    boost = 0.0
                    q_words = [t.lower() for t in content_tokens]
                    if any(w in row["heading"].lower() for w in q_words):
                        boost += 3.0
                    if any(w in row["doc_title"].lower() for w in q_words):
                        boost += 2.0

                    final_score = raw_score + boost
                    if final_score < min_score:
                        continue

                    key = (row["path"], row["section_id"])
                    if key not in results_dict or final_score > results_dict[key].score:
                        results_dict[key] = SearchResult(
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
                        )

        # First attempt: strict AND search
        _execute_fts(and_fts)

        # If strict search returned fewer results than limit, supplement with OR search
        if len(results_dict) < limit and or_fts != and_fts:
            _execute_fts(or_fts)

        results = list(results_dict.values())
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
