"""Orchestrator for the Autonomous Knowledge Update Pipeline."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from knowledge_retrieval.auto_update_models import (
    CandidateStatus,
    ChangeCandidate,
    ChangeType,
    MonitoredSource,
    PolicyDecision,
    RiskLevel,
    SourceType,
    TrustTier,
)
from knowledge_retrieval.auto_update_store import AutoUpdateStore
from knowledge_retrieval.change_detector import ChangeDetector
from knowledge_retrieval.evidence_verifier import EvidenceVerifier
from knowledge_retrieval.fetcher import SourceFetcher
from knowledge_retrieval.indexer import Indexer
from knowledge_retrieval.knowledge_updater import KnowledgeUpdater


class AutoUpdater:
    """Orchestrates source monitoring, change detection, verification, and knowledge updates."""

    def __init__(
        self,
        root_dir: str,
        store: AutoUpdateStore,
        indexer: Indexer,
        fetcher: Optional[SourceFetcher] = None
    ):
        self.root_dir = root_dir
        self.store = store
        self.indexer = indexer
        self.fetcher = fetcher or SourceFetcher()
        self.detector = ChangeDetector(self.fetcher)
        self.verifier = EvidenceVerifier(indexer.storage)
        self.updater = KnowledgeUpdater(self.root_dir, self.store, self.indexer)

    # =========================================================================
    # Source Registry Operations
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
    ) -> MonitoredSource:
        """Registers a new monitored source."""
        source = MonitoredSource(
            source_id=source_id,
            source_type=SourceType(source_type),
            display_name=display_name,
            canonical_url=canonical_url,
            topics=topics or [],
            destination_doc_id=destination_doc_id,
            trust_tier=TrustTier(trust_tier),
            trust_rationale=trust_rationale,
            enabled=True,
            polling_interval_seconds=polling_interval,
            config=config or {}
        )
        self.store.register_source(source)
        return source

    def list_sources(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        sources = self.store.list_sources(enabled_only=enabled_only)
        return [
            {
                "source_id": s.source_id,
                "source_type": s.source_type.value,
                "display_name": s.display_name,
                "canonical_url": s.canonical_url,
                "destination_doc_id": s.destination_doc_id,
                "topics": s.topics,
                "trust_tier": s.trust_tier.value,
                "enabled": s.enabled,
                "last_checked_at": s.last_checked_at,
                "last_error": s.last_error,
                "retry_count": s.retry_count
            }
            for s in sources
        ]

    def remove_source(self, source_id: str) -> bool:
        return self.store.remove_source(source_id)

    # =========================================================================
    # Polling & Check Pipeline
    # =========================================================================

    def check_source(self, source_id: str) -> Dict[str, Any]:
        """Polls a specific registered source and executes the verification and update pipeline."""
        source = self.store.get_source(source_id)
        if not source:
            return {"error": f"Source '{source_id}' not found."}

        change_type, candidate, fetch_res = self.detector.check_source(source)

        if change_type == ChangeType.NO_CHANGE:
            self.store.update_source_checkpoint(source_id, error=None)
            return {
                "source_id": source_id,
                "change_type": "NO_CHANGE",
                "message": "Source content is up to date."
            }

        if change_type == ChangeType.UNREACHABLE:
            self.store.update_source_checkpoint(source_id, error=fetch_res.error)
            return {
                "source_id": source_id,
                "change_type": "UNREACHABLE",
                "error": fetch_res.error
            }

        # Candidate generated: Run evidence verification & policy decision
        policy_decision, risk_level, rationale = self.verifier.verify_candidate(candidate, source)
        candidate.policy_decision = policy_decision
        candidate.risk_level = risk_level
        candidate.decision_rationale = rationale

        # Save candidate in SQLite
        self.store.save_candidate(candidate)

        # Update source checkpoint
        self.store.update_source_checkpoint(
            source_id=source_id,
            fingerprint=fetch_res.fingerprint,
            etag=fetch_res.etag,
            last_modified=fetch_res.last_modified,
            error=None,
            observed_change=True
        )

        outcome_result = {
            "source_id": source_id,
            "candidate_id": candidate.candidate_id,
            "change_type": change_type.value,
            "policy_decision": policy_decision.value,
            "risk_level": risk_level.value,
            "rationale": rationale
        }

        # Apply Policy
        if policy_decision == PolicyDecision.AUTO_APPLY:
            ok, msg = self.updater.apply_candidate(candidate, applied_by="AUTO_POLICY")
            outcome_result["action_taken"] = "AUTO_APPLIED" if ok else "APPLY_FAILED"
            outcome_result["message"] = msg

        elif policy_decision == PolicyDecision.REVIEW_REQUIRED:
            q_id = self.store.enqueue_for_review(candidate.candidate_id, source_id)
            outcome_result["action_taken"] = "QUEUED_FOR_REVIEW"
            outcome_result["queue_id"] = q_id
            outcome_result["message"] = f"Candidate queued for human review (Queue ID: {q_id})."

        else:  # REJECT
            self.store.update_candidate_status(candidate.candidate_id, CandidateStatus.REJECTED)
            outcome_result["action_taken"] = "REJECTED"
            outcome_result["message"] = f"Candidate rejected: {rationale}"

        return outcome_result

    def check_all_sources(self) -> List[Dict[str, Any]]:
        """Polls all enabled sources sequentially."""
        sources = self.store.list_sources(enabled_only=True)
        results = []
        for s in sources:
            results.append(self.check_source(s.source_id))
        return results

    # =========================================================================
    # Review Queue & History
    # =========================================================================

    def list_review_queue(self, status: str = "PENDING") -> List[Dict[str, Any]]:
        items = self.store.list_review_queue(status=status)
        out = []
        for it in items:
            c = it.candidate
            out.append({
                "queue_id": it.queue_id,
                "candidate_id": it.candidate_id,
                "source_id": it.source_id,
                "enqueued_at": it.enqueued_at,
                "resolution": it.resolution,
                "reviewer_note": it.reviewer_note,
                "change_summary": c.change_summary if c else "",
                "risk_level": c.risk_level.value if c else "",
                "rationale": c.decision_rationale if c else "",
                "content_preview": c.normalized_content[:300] if c else ""
            })
        return out

    def approve_review_item(self, candidate_id: str, note: Optional[str] = None) -> Dict[str, Any]:
        """Revalidates and applies a human-approved candidate, preventing stale overwrites."""
        cand = self.store.get_candidate(candidate_id)
        if not cand:
            return {"error": f"Candidate '{candidate_id}' not found."}

        # Verify candidate is currently pending in review queue
        pending_items = self.store.list_review_queue(status="PENDING")
        if not any(it.candidate_id == candidate_id for it in pending_items):
            return {
                "status": "ERROR",
                "error": f"Candidate '{candidate_id}' is not in PENDING review state."
            }

        source = self.store.get_source(cand.source_id)
        if not source:
            return {"error": f"Source '{cand.source_id}' is no longer registered."}

        # 1. Stale Check against Source: Verify source fingerprint has not moved past this candidate
        if source.last_fingerprint and source.last_fingerprint != cand.curr_fingerprint:
            return {
                "status": "STALE_REJECTED",
                "error": f"Stale Approval Blocked: Source '{cand.source_id}' has updated to a newer fingerprint ({source.last_fingerprint[:12]}) than this candidate ({cand.curr_fingerprint[:12]})."
            }

        # 2. Stale Check against Destination Document
        if cand.affected_doc_ids:
            target_doc_id = cand.affected_doc_ids[0]
            existing_doc = self.indexer.storage.get_document(target_doc_id)
            if existing_doc and existing_doc.mtime > cand.observed_at:
                # Document was modified on disk after candidate observation
                # Re-verify material conflicts with current content
                conflict = self.verifier._detect_material_conflict(cand.normalized_content, existing_doc)
                if conflict:
                    return {
                        "status": "STALE_REJECTED",
                        "error": f"Stale Approval Blocked: Target document was modified and now conflicts: {conflict}"
                    }

        # 3. Security & Policy Revalidation
        policy_decision, risk_level, rationale = self.verifier.verify_candidate(cand, source)
        if policy_decision == PolicyDecision.REJECT:
            return {
                "status": "SECURITY_REJECTED",
                "error": f"Revalidation Failed: Candidate rejected under current security policy: {rationale}"
            }

        # 4. Safe Apply
        ok, msg = self.updater.apply_candidate(cand, applied_by="HUMAN_REVIEWER")
        if ok:
            self.store.resolve_review_item(candidate_id, "APPROVED", note=note)
            return {"status": "APPROVED", "message": msg}
        return {"status": "ERROR", "message": f"Failed to apply: {msg}"}

    def reject_review_item(self, candidate_id: str, note: Optional[str] = None) -> Dict[str, Any]:
        cand = self.store.get_candidate(candidate_id)
        if not cand:
            return {"error": f"Candidate '{candidate_id}' not found."}

        self.store.resolve_review_item(candidate_id, "REJECTED", note=note)
        return {"status": "REJECTED", "message": f"Candidate {candidate_id} rejected."}

    def list_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        records = self.store.list_history(limit=limit)
        return [
            {
                "history_id": r.history_id,
                "candidate_id": r.candidate_id,
                "source_id": r.source_id,
                "doc_path": r.doc_path,
                "applied_at": r.applied_at,
                "diff_summary": r.diff_summary,
                "applied_by": r.applied_by
            }
            for r in records
        ]
