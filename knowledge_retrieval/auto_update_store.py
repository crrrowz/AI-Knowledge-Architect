"""SQLite storage repository for monitored sources, change candidates, review queue, and audit history."""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any, Dict, List, Optional

from knowledge_retrieval.auto_update_models import (
    CandidateStatus,
    ChangeCandidate,
    ChangeType,
    KnowledgeUpdateRecord,
    MonitoredSource,
    PolicyDecision,
    ReviewQueueItem,
    RiskLevel,
    SourceType,
    TrustTier,
)
from knowledge_retrieval.storage import StorageEngine


class AutoUpdateStore:
    """Provides transactional persistence for the Autonomous Knowledge Update Pipeline."""

    def __init__(self, storage: StorageEngine):
        self.storage = storage

    def get_connection(self) -> sqlite3.Connection:
        return self.storage.get_connection()

    # =========================================================================
    # Source Registry
    # =========================================================================

    def register_source(self, source: MonitoredSource) -> None:
        """Registers or updates a monitored documentation website or GitHub repository."""
        with self.get_connection() as conn:
            with conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO monitored_sources (
                        source_id, source_type, display_name, canonical_url,
                        topics_json, destination_doc_id, trust_tier, trust_rationale,
                        enabled, polling_interval_seconds, last_checked_at,
                        last_observed_change_at, last_fingerprint, last_etag,
                        last_modified_header, last_error, retry_count, config_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source.source_id,
                        source.source_type.value,
                        source.display_name,
                        source.canonical_url,
                        json.dumps(source.topics),
                        source.destination_doc_id,
                        source.trust_tier.value,
                        source.trust_rationale,
                        1 if source.enabled else 0,
                        source.polling_interval_seconds,
                        source.last_checked_at,
                        source.last_observed_change_at,
                        source.last_fingerprint,
                        source.last_etag,
                        source.last_modified_header,
                        source.last_error,
                        source.retry_count,
                        json.dumps(source.config)
                    )
                )

    def get_source(self, source_id: str) -> Optional[MonitoredSource]:
        """Retrieves a monitored source by ID."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM monitored_sources WHERE source_id = ?",
                (source_id,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_source(row)

    def list_sources(self, enabled_only: bool = False) -> List[MonitoredSource]:
        """Lists all registered sources."""
        with self.get_connection() as conn:
            query = "SELECT * FROM monitored_sources"
            if enabled_only:
                query += " WHERE enabled = 1"
            query += " ORDER BY source_id ASC"
            rows = conn.execute(query).fetchall()
            return [self._row_to_source(r) for r in rows]

    def remove_source(self, source_id: str) -> bool:
        """Deletes a source from the registry."""
        with self.get_connection() as conn:
            with conn:
                res = conn.execute(
                    "DELETE FROM monitored_sources WHERE source_id = ?",
                    (source_id,)
                )
                return res.rowcount > 0

    def update_source_checkpoint(
        self,
        source_id: str,
        fingerprint: Optional[str] = None,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None,
        error: Optional[str] = None,
        observed_change: bool = False
    ) -> None:
        """Updates checkpoints, timestamps, and error states for a monitored source."""
        now = time.time()
        with self.get_connection() as conn:
            with conn:
                sql = """
                    UPDATE monitored_sources SET
                        last_checked_at = ?,
                        last_error = ?,
                        retry_count = CASE WHEN ? IS NULL THEN 0 ELSE retry_count + 1 END
                """
                params = [now, error, error]

                if fingerprint is not None:
                    sql += ", last_fingerprint = ?"
                    params.append(fingerprint)
                if etag is not None:
                    sql += ", last_etag = ?"
                    params.append(etag)
                if last_modified is not None:
                    sql += ", last_modified_header = ?"
                    params.append(last_modified)
                if observed_change:
                    sql += ", last_observed_change_at = ?"
                    params.append(now)

                sql += " WHERE source_id = ?"
                params.append(source_id)
                conn.execute(sql, params)

    def _row_to_source(self, row: sqlite3.Row) -> MonitoredSource:
        return MonitoredSource(
            source_id=row["source_id"],
            source_type=SourceType(row["source_type"]),
            display_name=row["display_name"],
            canonical_url=row["canonical_url"],
            topics=json.loads(row["topics_json"]),
            destination_doc_id=row["destination_doc_id"],
            trust_tier=TrustTier(row["trust_tier"]),
            trust_rationale=row["trust_rationale"],
            enabled=bool(row["enabled"]),
            polling_interval_seconds=row["polling_interval_seconds"],
            last_checked_at=row["last_checked_at"],
            last_observed_change_at=row["last_observed_change_at"],
            last_fingerprint=row["last_fingerprint"],
            last_etag=row["last_etag"],
            last_modified_header=row["last_modified_header"],
            last_error=row["last_error"],
            retry_count=row["retry_count"],
            config=json.loads(row["config_json"])
        )

    # =========================================================================
    # Change Candidates & Evidence
    # =========================================================================

    def save_candidate(self, candidate: ChangeCandidate) -> None:
        """Saves a change candidate to the database."""
        now = time.time()
        created = candidate.created_at or now
        with self.get_connection() as conn:
            with conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO change_candidates (
                        candidate_id, source_id, observed_at, source_published_at,
                        prev_fingerprint, curr_fingerprint, change_type, change_summary,
                        raw_content, normalized_content, affected_doc_ids_json,
                        affected_topics_json, evidence_json, risk_level,
                        policy_decision, decision_rationale, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        candidate.candidate_id,
                        candidate.source_id,
                        candidate.observed_at,
                        candidate.source_published_at,
                        candidate.prev_fingerprint,
                        candidate.curr_fingerprint,
                        candidate.change_type.value,
                        candidate.change_summary,
                        candidate.raw_content,
                        candidate.normalized_content,
                        json.dumps(candidate.affected_doc_ids),
                        json.dumps(candidate.affected_topics),
                        json.dumps(candidate.evidence),
                        candidate.risk_level.value,
                        candidate.policy_decision.value,
                        candidate.decision_rationale,
                        candidate.status.value,
                        created
                    )
                )

    def get_candidate(self, candidate_id: str) -> Optional[ChangeCandidate]:
        """Loads a change candidate by ID."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM change_candidates WHERE candidate_id = ?",
                (candidate_id,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_candidate(row)

    def update_candidate_status(self, candidate_id: str, status: CandidateStatus) -> None:
        """Updates candidate status."""
        with self.get_connection() as conn:
            with conn:
                conn.execute(
                    "UPDATE change_candidates SET status = ? WHERE candidate_id = ?",
                    (status.value, candidate_id)
                )

    def _row_to_candidate(self, row: sqlite3.Row) -> ChangeCandidate:
        return ChangeCandidate(
            candidate_id=row["candidate_id"],
            source_id=row["source_id"],
            observed_at=row["observed_at"],
            source_published_at=row["source_published_at"],
            prev_fingerprint=row["prev_fingerprint"],
            curr_fingerprint=row["curr_fingerprint"],
            change_type=ChangeType(row["change_type"]),
            change_summary=row["change_summary"],
            raw_content=row["raw_content"],
            normalized_content=row["normalized_content"],
            affected_doc_ids=json.loads(row["affected_doc_ids_json"]),
            affected_topics=json.loads(row["affected_topics_json"]),
            evidence=json.loads(row["evidence_json"]),
            risk_level=RiskLevel(row["risk_level"]),
            policy_decision=PolicyDecision(row["policy_decision"]),
            decision_rationale=row["decision_rationale"],
            status=CandidateStatus(row["status"]),
            created_at=row["created_at"]
        )

    # =========================================================================
    # Review Queue
    # =========================================================================

    def enqueue_for_review(self, candidate_id: str, source_id: str) -> int:
        """Places a change candidate into the human review queue."""
        now = time.time()
        with self.get_connection() as conn:
            with conn:
                cursor = conn.execute(
                    """
                    INSERT OR REPLACE INTO review_queue (
                        candidate_id, source_id, enqueued_at, resolution
                    ) VALUES (?, ?, ?, 'PENDING')
                    """,
                    (candidate_id, source_id, now)
                )
                conn.execute(
                    "UPDATE change_candidates SET status = ? WHERE candidate_id = ?",
                    (CandidateStatus.QUEUED_FOR_REVIEW.value, candidate_id)
                )
                return cursor.lastrowid

    def list_review_queue(self, status: str = "PENDING") -> List[ReviewQueueItem]:
        """Lists items currently in the review queue."""
        with self.get_connection() as conn:
            query = "SELECT * FROM review_queue"
            params = []
            if status:
                query += " WHERE resolution = ?"
                params.append(status)
            query += " ORDER BY enqueued_at ASC"
            rows = conn.execute(query, params).fetchall()

            items = []
            for r in rows:
                c_row = conn.execute(
                    "SELECT * FROM change_candidates WHERE candidate_id = ?",
                    (r["candidate_id"],)
                ).fetchone()
                cand = self._row_to_candidate(c_row) if c_row else None
                items.append(ReviewQueueItem(
                    queue_id=r["queue_id"],
                    candidate_id=r["candidate_id"],
                    source_id=r["source_id"],
                    enqueued_at=r["enqueued_at"],
                    resolved_at=r["resolved_at"],
                    resolution=r["resolution"],
                    reviewer_note=r["reviewer_note"],
                    candidate=cand
                ))
            return items

    def resolve_review_item(self, candidate_id: str, resolution: str, note: Optional[str] = None) -> bool:
        """Resolves a review item as APPROVED or REJECTED."""
        now = time.time()
        with self.get_connection() as conn:
            with conn:
                res = conn.execute(
                    """
                    UPDATE review_queue SET
                        resolution = ?,
                        resolved_at = ?,
                        reviewer_note = ?
                    WHERE candidate_id = ?
                    """,
                    (resolution, now, note, candidate_id)
                )
                cand_status = CandidateStatus.APPROVED if resolution == "APPROVED" else CandidateStatus.REJECTED
                conn.execute(
                    "UPDATE change_candidates SET status = ? WHERE candidate_id = ?",
                    (cand_status.value, candidate_id)
                )
                return res.rowcount > 0

    # =========================================================================
    # Knowledge Update Audit History
    # =========================================================================

    def record_history(
        self,
        candidate_id: str,
        source_id: str,
        doc_path: str,
        diff_summary: str,
        prev_hash: str,
        new_hash: str,
        applied_by: str = "AUTO_POLICY"
    ) -> int:
        """Records an applied update in the permanent audit history table."""
        now = time.time()
        with self.get_connection() as conn:
            with conn:
                cursor = conn.execute(
                    """
                    INSERT INTO knowledge_update_history (
                        candidate_id, source_id, doc_path, applied_at,
                        diff_summary, previous_content_hash, new_content_hash, applied_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        candidate_id,
                        source_id,
                        doc_path,
                        now,
                        diff_summary,
                        prev_hash,
                        new_hash,
                        applied_by
                    )
                )
                conn.execute(
                    "UPDATE change_candidates SET status = ? WHERE candidate_id = ?",
                    (CandidateStatus.APPLIED.value, candidate_id)
                )
                return cursor.lastrowid

    def list_history(self, limit: int = 20) -> List[KnowledgeUpdateRecord]:
        """Retrieves historical updates with audit provenance."""
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM knowledge_update_history
                ORDER BY applied_at DESC LIMIT ?
                """,
                (limit,)
            ).fetchall()
            return [
                KnowledgeUpdateRecord(
                    history_id=r["history_id"],
                    candidate_id=r["candidate_id"],
                    source_id=r["source_id"],
                    doc_path=r["doc_path"],
                    applied_at=r["applied_at"],
                    diff_summary=r["diff_summary"],
                    previous_content_hash=r["previous_content_hash"],
                    new_content_hash=r["new_content_hash"],
                    applied_by=r["applied_by"]
                )
                for r in rows
            ]
