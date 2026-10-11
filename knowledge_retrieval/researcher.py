"""Research collector and claim-to-evidence tracker for knowledge authoring."""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from knowledge_retrieval.auto_update_store import AutoUpdateStore
from knowledge_retrieval.fetcher import SourceFetcher
from knowledge_retrieval.retriever import Retriever


@dataclass
class EvidenceFact:
    """An individual verified fact extracted from an external source or existing corpus."""
    fact_id: str
    source_id: str
    source_url: str
    observed_at: float
    excerpt: str
    fact_type: str  # 'DEFINITION', 'MECHANISM', 'APPLICATION', 'LIMITATION', 'CONFLICT'
    topic: str
    fingerprint: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResearchDossier:
    """Consolidated evidence dossier gathered for a specific document topic."""
    topic_id: str
    title: str
    facts: List[EvidenceFact] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    unresolved_questions: List[str] = field(default_factory=list)
    sources_consulted: List[str] = field(default_factory=list)


class ResearchCollector:
    """Collects traceable evidence facts from registered sources and existing knowledge."""

    def __init__(
        self,
        store: AutoUpdateStore,
        retriever: Retriever,
        fetcher: Optional[SourceFetcher] = None
    ):
        self.store = store
        self.retriever = retriever
        self.fetcher = fetcher or SourceFetcher()

    def research_topic(
        self,
        topic_id: str,
        title: str,
        topic_keywords: Optional[List[str]] = None
    ) -> ResearchDossier:
        """Gathers evidence facts from registered sources and local corpus for a topic."""
        now = time.time()
        dossier = ResearchDossier(
            topic_id=topic_id,
            title=title,
            facts=[],
            conflicts=[],
            unresolved_questions=[],
            sources_consulted=[]
        )

        keywords = topic_keywords or [topic_id, title]
        all_sources = self.store.list_sources(enabled_only=True)

        # 1. Gather from registered sources matching topic or destination_doc_id
        matching_sources = [
            s for s in all_sources
            if s.destination_doc_id == topic_id or
               any(k.lower() in [t.lower() for t in s.topics] for k in keywords) or
               any(k.lower() in s.display_name.lower() for k in keywords)
        ]

        for src in matching_sources:
            dossier.sources_consulted.append(src.canonical_url)
            fetch_res = self.fetcher.fetch_url(src.canonical_url, etag=src.last_etag)
            if fetch_res.status_code == 200 and fetch_res.content:
                self._extract_facts_from_content(
                    content=fetch_res.content,
                    source_id=src.source_id,
                    source_url=src.canonical_url,
                    fingerprint=fetch_res.fingerprint,
                    observed_at=now,
                    topic=topic_id,
                    dossier=dossier
                )
            elif fetch_res.error:
                dossier.unresolved_questions.append(
                    f"External source '{src.display_name}' could not be reached: {fetch_res.error}"
                )

        # 2. Gather cross-references from existing local knowledge base
        local_results = self.retriever.search(f"{topic_id} {title}", limit=3)
        for r in local_results:
            sec = self.retriever.read_section(r.doc_id, r.section_id)
            if sec and sec.content:
                dossier.facts.append(EvidenceFact(
                    fact_id=f"fact-local-{uuid.uuid4().hex[:6]}",
                    source_id=f"local:{r.doc_id}",
                    source_url=r.path,
                    observed_at=now,
                    excerpt=sec.content[:400],
                    fact_type="LOCAL_CROSS_REFERENCE",
                    topic=topic_id,
                    fingerprint="local-verified"
                ))

        # 3. Detect conflicts among gathered facts
        self._detect_conflicts(dossier)

        # 4. Check evidence completeness for required aspects
        fact_types = {f.fact_type for f in dossier.facts}
        if "DEFINITION" not in fact_types and not any("is" in f.excerpt.lower() for f in dossier.facts):
            dossier.unresolved_questions.append("Lacking clear architectural definition or functional category.")
        if "LIMITATION" not in fact_types and not any("limit" in f.excerpt.lower() or "bottleneck" in f.excerpt.lower() for f in dossier.facts):
            dossier.unresolved_questions.append("Lacking documented limitations, trade-offs, or scalability constraints.")

        return dossier

    def _extract_facts_from_content(
        self,
        content: str,
        source_id: str,
        source_url: str,
        fingerprint: str,
        observed_at: float,
        topic: str,
        dossier: ResearchDossier
    ) -> None:
        """Parses source text into categorized, traceable evidence facts."""
        lines = [line.strip() for line in content.split("\n") if line.strip()]
        current_heading = "General"

        for line in lines:
            if line.startswith("#"):
                current_heading = line.lstrip("#").strip()
                continue

            # Classify statement by technical cues
            line_lower = line.lower()
            fact_type = "GENERAL_FACT"

            if any(cue in line_lower for cue in ["is an", "is a", "defined as", "designed to", "provides a"]):
                fact_type = "DEFINITION"
            elif any(cue in line_lower for cue in ["operates by", "works by", "algorithm", "protocol", "architecture", "mechanism", "lifecycle"]):
                fact_type = "MECHANISM"
            elif any(cue in line_lower for cue in ["used for", "application", "deployment", "production", "use case", "scenarios"]):
                fact_type = "APPLICATION"
            elif any(cue in line_lower for cue in ["limit", "bottleneck", "disadvantage", "trade-off", "overhead", "restriction", "vulnerability"]):
                fact_type = "LIMITATION"

            dossier.facts.append(EvidenceFact(
                fact_id=f"fact-{uuid.uuid4().hex[:6]}",
                source_id=source_id,
                source_url=source_url,
                observed_at=observed_at,
                excerpt=line,
                fact_type=fact_type,
                topic=topic,
                fingerprint=fingerprint,
                metadata={"section_heading": current_heading}
            ))

    def _detect_conflicts(self, dossier: ResearchDossier) -> None:
        """Surfaces conflicting numerical or behavioral statements across facts."""
        timeout_facts = []
        for f in dossier.facts:
            match = re.search(r"timeout\s+(?:is\s+)?(?:set\s+to\s+)?(\d+)\s*(?:seconds?|s)", f.excerpt, re.IGNORECASE)
            if match:
                timeout_facts.append((match.group(1), f))

        if len(timeout_facts) > 1:
            vals = {t[0] for t in timeout_facts}
            if len(vals) > 1:
                conflict_desc = f"Conflicting timeout specifications detected: " + ", ".join(
                    f"{t[0]}s in {t[1].source_url}" for t in timeout_facts
                )
                dossier.conflicts.append(conflict_desc)
