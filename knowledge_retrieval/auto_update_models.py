"""Data models for the Autonomous Knowledge Update Pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SourceType(str, Enum):
    WEBSITE = "website"
    GITHUB_REPO = "github_repo"


class TrustTier(str, Enum):
    OFFICIAL = "official"
    TRUSTED_PARTNER = "trusted_partner"
    COMMUNITY = "community"


class ChangeType(str, Enum):
    NO_CHANGE = "NO_CHANGE"
    NEW_RELEASE = "NEW_RELEASE"
    NEW_TAG = "NEW_TAG"
    DOC_UPDATED = "DOC_UPDATED"
    UNREACHABLE = "UNREACHABLE"
    FORMAT_ERROR = "FORMAT_ERROR"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class PolicyDecision(str, Enum):
    AUTO_APPLY = "AUTO_APPLY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REJECT = "REJECT"


class CandidateStatus(str, Enum):
    PENDING = "PENDING"
    APPLIED = "APPLIED"
    QUEUED_FOR_REVIEW = "QUEUED_FOR_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass
class MonitoredSource:
    """Represents an explicitly registered documentation site or GitHub repo."""
    source_id: str
    source_type: SourceType
    display_name: str
    canonical_url: str
    topics: List[str]
    destination_doc_id: str
    trust_tier: TrustTier = TrustTier.OFFICIAL
    trust_rationale: str = "Authoritative official repository"
    enabled: bool = True
    polling_interval_seconds: int = 3600
    last_checked_at: Optional[float] = None
    last_observed_change_at: Optional[float] = None
    last_fingerprint: Optional[str] = None
    last_etag: Optional[str] = None
    last_modified_header: Optional[str] = None
    last_error: Optional[str] = None
    retry_count: int = 0
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChangeCandidate:
    """Represents a detected, structured change with evidence and verification flags."""
    candidate_id: str
    source_id: str
    observed_at: float
    source_published_at: Optional[float]
    prev_fingerprint: Optional[str]
    curr_fingerprint: str
    change_type: ChangeType
    change_summary: str
    raw_content: str
    normalized_content: str
    affected_doc_ids: List[str]
    affected_topics: List[str]
    evidence: Dict[str, Any]
    risk_level: RiskLevel
    policy_decision: PolicyDecision
    decision_rationale: str
    status: CandidateStatus = CandidateStatus.PENDING
    created_at: float = field(default_factory=lambda: 0.0)


@dataclass
class KnowledgeUpdateRecord:
    """Audit entry documenting an applied update to a Markdown file."""
    history_id: int
    candidate_id: str
    source_id: str
    doc_path: str
    applied_at: float
    diff_summary: str
    previous_content_hash: str
    new_content_hash: str
    applied_by: str  # 'AUTO_POLICY' or 'HUMAN_REVIEWER'


@dataclass
class ReviewQueueItem:
    """Item queued for human inspection before application."""
    queue_id: int
    candidate_id: str
    source_id: str
    enqueued_at: float
    resolved_at: Optional[float]
    resolution: str  # 'PENDING', 'APPROVED', 'REJECTED'
    reviewer_note: Optional[str]
    candidate: Optional[ChangeCandidate] = None
