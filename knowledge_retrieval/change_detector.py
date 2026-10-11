"""Change detection engine that observes sources and generates structured change candidates."""

from __future__ import annotations

import time
import uuid
from typing import Optional, Tuple

from knowledge_retrieval.auto_update_models import (
    CandidateStatus,
    ChangeCandidate,
    ChangeType,
    MonitoredSource,
    PolicyDecision,
    RiskLevel,
    SourceType,
)
from knowledge_retrieval.fetcher import FetchResult, SourceFetcher, compute_content_fingerprint


class ChangeDetector:
    """Detects meaningful updates, new releases, and content modifications across monitored sources."""

    def __init__(self, fetcher: Optional[SourceFetcher] = None):
        self.fetcher = fetcher or SourceFetcher()

    def check_source(self, source: MonitoredSource) -> Tuple[ChangeType, Optional[ChangeCandidate], FetchResult]:
        """Polls a single monitored source and detects whether a change occurred.
        
        Returns:
            (ChangeType, Optional[ChangeCandidate], FetchResult)
        """
        now = time.time()

        if source.source_type == SourceType.GITHUB_REPO:
            # Extract owner and repo from config or canonical_url
            owner = source.config.get("owner")
            repo = source.config.get("repo")
            if not owner or not repo:
                # Parse from canonical_url (e.g. https://github.com/owner/repo)
                parts = source.canonical_url.rstrip("/").split("/")
                if len(parts) >= 2:
                    owner, repo = parts[-2], parts[-1]

            fetch_res = self.fetcher.fetch_github_release(owner=owner, repo=repo, etag=source.last_etag)

            if fetch_res.status_code == 304 or (fetch_res.fingerprint and fetch_res.fingerprint == source.last_fingerprint):
                return ChangeType.NO_CHANGE, None, fetch_res

            if fetch_res.error:
                return ChangeType.UNREACHABLE, None, fetch_res

            meta = fetch_res.metadata or {}
            tag_name = meta.get("tag_name", "latest")
            cid = f"cand-{source.source_id}-{tag_name}-{int(now * 1000)}-{uuid.uuid4().hex[:6]}"
            summary = f"New GitHub release {tag_name} detected for {source.display_name}."

            candidate = ChangeCandidate(
                candidate_id=cid,
                source_id=source.source_id,
                observed_at=now,
                source_published_at=fetch_res.published_at,
                prev_fingerprint=source.last_fingerprint,
                curr_fingerprint=fetch_res.fingerprint,
                change_type=ChangeType.NEW_RELEASE,
                change_summary=summary,
                raw_content=fetch_res.content,
                normalized_content=fetch_res.content,
                affected_doc_ids=[source.destination_doc_id],
                affected_topics=source.topics,
                evidence={
                    "source_url": source.canonical_url,
                    "release_tag": tag_name,
                    "release_url": meta.get("html_url", source.canonical_url),
                    "etag": fetch_res.etag
                },
                risk_level=RiskLevel.LOW,
                policy_decision=PolicyDecision.AUTO_APPLY,
                decision_rationale="Official GitHub release note from authoritative repository.",
                status=CandidateStatus.PENDING,
                created_at=now
            )
            return ChangeType.NEW_RELEASE, candidate, fetch_res

        else:
            # Website or doc URL
            fetch_res = self.fetcher.fetch_url(
                url=source.canonical_url,
                etag=source.last_etag,
                last_modified=source.last_modified_header
            )

            if fetch_res.status_code == 304 or (fetch_res.fingerprint and fetch_res.fingerprint == source.last_fingerprint):
                return ChangeType.NO_CHANGE, None, fetch_res

            if fetch_res.error:
                return ChangeType.UNREACHABLE, None, fetch_res

            meta = fetch_res.metadata or {}
            cid = f"cand-{source.source_id}-{int(now * 1000)}-{uuid.uuid4().hex[:6]}"
            summary = f"Documentation content update observed for {source.display_name}."

            candidate = ChangeCandidate(
                candidate_id=cid,
                source_id=source.source_id,
                observed_at=now,
                source_published_at=fetch_res.published_at,
                prev_fingerprint=source.last_fingerprint,
                curr_fingerprint=fetch_res.fingerprint,
                change_type=ChangeType.DOC_UPDATED,
                change_summary=summary,
                raw_content=fetch_res.content,
                normalized_content=fetch_res.content,
                affected_doc_ids=[source.destination_doc_id],
                affected_topics=source.topics,
                evidence={
                    "source_url": source.canonical_url,
                    "etag": fetch_res.etag,
                    "last_modified": fetch_res.last_modified
                },
                risk_level=RiskLevel.LOW,
                policy_decision=PolicyDecision.AUTO_APPLY,
                decision_rationale="Documentation update from registered authoritative source.",
                status=CandidateStatus.PENDING,
                created_at=now
            )
            return ChangeType.DOC_UPDATED, candidate, fetch_res
