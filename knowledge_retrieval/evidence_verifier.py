"""Evidence Verification Engine enforcing authenticity, security sanitization, and risk classification."""

from __future__ import annotations

import re
import urllib.parse
from typing import Dict, List, Optional, Tuple

from knowledge_retrieval.auto_update_models import (
    ChangeCandidate,
    MonitoredSource,
    PolicyDecision,
    RiskLevel,
    TrustTier,
)
from knowledge_retrieval.storage import StorageEngine


# Security patterns indicative of prompt injection attempts in external untrusted data
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(an?\s+)?unrestricted", re.IGNORECASE),
    re.compile(r"system\s*prompt\s*:\s*override", re.IGNORECASE),
    re.compile(r"administrative\s+directive\s*:\s*bypass", re.IGNORECASE),
    re.compile(r"<\s*script\s*>\s*alert\(", re.IGNORECASE),
    re.compile(r"rm\s+-rf\s+[/~]", re.IGNORECASE),
]

# Patterns indicative of breaking changes or deprecations
BREAKING_PATTERNS = [
    re.compile(r"\bbreaking\s+changes?\b", re.IGNORECASE),
    re.compile(r"\bdeprecated\b", re.IGNORECASE),
    re.compile(r"\bremoved\s+support\b", re.IGNORECASE),
    re.compile(r"\bincompatible\s+with\b", re.IGNORECASE),
]


class EvidenceVerifier:
    """Evaluates source authenticity, scans for security injections, and deterministically assigns policy decisions."""

    def __init__(self, storage: Optional[StorageEngine] = None):
        self.storage = storage

    def verify_candidate(
        self,
        candidate: ChangeCandidate,
        source: MonitoredSource
    ) -> Tuple[PolicyDecision, RiskLevel, str]:
        """Runs multi-stage verification on a candidate.
        
        Returns:
            (PolicyDecision, RiskLevel, rationale_string)
        """
        # 1. Source Authenticity & Domain Validation
        source_parsed = urllib.parse.urlparse(source.canonical_url)
        evidence_url = candidate.evidence.get("source_url") or ""
        evidence_parsed = urllib.parse.urlparse(evidence_url)

        if evidence_parsed.netloc and source_parsed.netloc:
            # Domains must match
            if evidence_parsed.netloc.lower() != source_parsed.netloc.lower():
                return (
                    PolicyDecision.REJECT,
                    RiskLevel.CRITICAL,
                    f"Security Reject: Evidence domain '{evidence_parsed.netloc}' does not match registered source domain '{source_parsed.netloc}'."
                )

        # 2. Prompt Injection Defense (Untrusted Data Invariant)
        content_to_scan = candidate.raw_content + " " + candidate.change_summary
        for pattern in INJECTION_PATTERNS:
            if pattern.search(content_to_scan):
                return (
                    PolicyDecision.REJECT,
                    RiskLevel.CRITICAL,
                    "Security Reject: Potential prompt injection or malicious instruction detected in untrusted external source content."
                )

        # 3. Content Completeness & Destructive Check
        if not candidate.normalized_content.strip():
            return (
                PolicyDecision.REJECT,
                RiskLevel.HIGH,
                "Reject: Source content is empty or malformed."
            )

        # 4. Breaking Changes & Deprecation Detection
        for b_pat in BREAKING_PATTERNS:
            if b_pat.search(content_to_scan):
                return (
                    PolicyDecision.REVIEW_REQUIRED,
                    RiskLevel.HIGH,
                    "Review Required: Detected breaking changes, deprecation notices, or removed functionality."
                )

        # 5. Contradiction & Conflict Detection against existing canonical document
        if self.storage and candidate.affected_doc_ids:
            target_doc_id = candidate.affected_doc_ids[0]
            existing_doc = self.storage.get_document(target_doc_id)
            if existing_doc:
                conflict_reason = self._detect_material_conflict(candidate.normalized_content, existing_doc)
                if conflict_reason:
                    return (
                        PolicyDecision.REVIEW_REQUIRED,
                        RiskLevel.HIGH,
                        f"Review Required: Contradiction detected with existing knowledge: {conflict_reason}"
                    )

        # 6. Trust Tier Calibration
        if source.trust_tier == TrustTier.COMMUNITY:
            return (
                PolicyDecision.REVIEW_REQUIRED,
                RiskLevel.MEDIUM,
                "Review Required: Updates from Community tier sources require human approval before application."
            )

        # 7. Safe Auto-Apply
        return (
            PolicyDecision.AUTO_APPLY,
            RiskLevel.LOW,
            "Auto-Apply Approved: Verified authoritative source, traceable evidence, non-breaking update."
        )

    def _detect_material_conflict(self, new_content: str, existing_doc) -> Optional[str]:
        """Detects conflicting parameters, such as conflicting timeouts or port numbers."""
        # Check timeout patterns (e.g. timeout: 30s vs timeout: 60s)
        new_timeout = re.search(r"timeout\s+(?:is\s+)?(?:strictly\s+)?(?:set\s+to\s+)?(\d+)\s*(?:seconds?|s)", new_content, re.IGNORECASE)
        if new_timeout:
            new_val = new_timeout.group(1)
            for sec in existing_doc.sections:
                old_timeout = re.search(r"timeout\s+(?:is\s+)?(?:strictly\s+)?(?:set\s+to\s+)?(\d+)\s*(?:seconds?|s)", sec.content, re.IGNORECASE)
                if old_timeout and old_timeout.group(1) != new_val:
                    return f"New timeout ({new_val}s) conflicts with existing statement in [{sec.heading}] ({old_timeout.group(1)}s)"

        return None
