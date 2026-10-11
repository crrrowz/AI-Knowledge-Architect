# Research & Authoring Pipeline Architecture Specification

**System:** AI-Knowledge-Architect  
**Document ID:** RAD-001  
**Status:** Approved for Implementation  
**Date:** 2026-10-11  

---

## 1. Overview & Ten-Stage Lifecycle

This architecture upgrades `AI-Knowledge-Architect` with evidence-backed research, claim-to-evidence validation, substantive Markdown authoring, and post-authoring retrieval verification.

```
Goal
  ↓
1. Inspect (Library scan, inventory, missing required topics)
  ↓
2. Plan (Formulate research topics and document generation ops)
  ↓
3. Research (Gather facts from registered sources & local corpus)
  ↓
4. Verify Evidence (Validate authenticity, freshness, and detect conflicts)
  ↓
5. Author (Synthesize structured Markdown: What, How, Apps, Limits, Sources)
  ↓
6. Validate (Quality check: required sections, token density, no hollow placeholders)
  ↓
7. Policy Check (Permitted paths, overwrite protection, risk classification)
  ↓
8. Execute (Atomic write swap, provenance headers, index sync)
  ↓
9. Independently Verify (Filesystem proof + FTS5 retrieval validation)
  ↓
10. Report (Auditable completion report with factual citations)
```

---

## 2. Core Data Models

### A. `EvidenceFact`
```python
@dataclass
class EvidenceFact:
    fact_id: str
    source_id: str
    source_url: str
    observed_at: float
    excerpt: str
    fact_type: str  # 'VERIFIED_FACT', 'INTERPRETATION', 'LIMITATION', 'CONFLICT'
    topic: str
    fingerprint: str
```

### B. `ResearchDossier`
```python
@dataclass
class ResearchDossier:
    topic_id: str
    title: str
    facts: List[EvidenceFact]
    conflicts: List[str]
    unresolved_questions: List[str]
    sources_consulted: List[str]
```

### C. `AuthoredDocument`
```python
@dataclass
class AuthoredDocument:
    doc_id: str
    title: str
    target_path: str
    content: str
    sections_present: List[str]
    token_count: int
    citations: List[Dict[str, str]]
    unresolved_questions: List[str]
```

---

## 3. Required Section Standards

Every technology document authored by the agent must conform to the standard structure:

1. **YAML Frontmatter:** `id`, `title`, `tags`, `type: technology_reference`, `status: active`
2. **Top-Level H1 Title:** `# {Technology Name}`
3. **`## What It Is`:** Clear definition, architecture category, and primary function.
4. **`## How It Works`:** Technical mechanisms, protocols, data structures, and operational lifecycle.
5. **`## Practical Applications`:** Concrete production use-cases, enterprise deployments, and integration patterns.
6. **`## Limitations and Trade-offs`:** Known performance bottlenecks, failure modes, scalability limits, or security considerations.
7. **`## Authoritative Sources and Provenance`:** Traceable citations linking claims to canonical URLs, observation dates, and content fingerprints.
8. **`## Unresolved Questions` (Conditional):** If sufficient evidence is unavailable for any required aspect, it is explicitly flagged here rather than hallucinated.

---

## 4. Verification and Retrieval Quality Gate

The pipeline implements an independent post-authoring verification gate:
1. **Disk Verification:** Confirms file exists on disk with byte size > 100 bytes.
2. **Structural Validation:** Confirms all 5 required sections are present.
3. **Index Verification:** Confirms document is indexed in SQLite `documents` and `sections`.
4. **Retrieval Verification:** Queries the engine using specific questions derived from the authored facts (e.g. *"What is the consensus mechanism of {tech}?"*). Verifies that the retrieval engine returns the exact newly authored section with `is_sufficient: True`.
