# Autonomous Knowledge Update Pipeline Architecture & Design

**Document ID:** AUD-001  
**Status:** Approved for Implementation  
**Date:** 2026-10-11  
**System:** AI-Knowledge-Architect  

---

## 1. Objective and Invariants

The Autonomous Knowledge Update Pipeline extends `AI-Knowledge-Architect` to monitor external authoritative sources (official documentation sites and GitHub repositories), detect meaningful technical changes, gather traceable evidence, evaluate risk, and update canonical Markdown documents automatically or route to a human review queue.

### Core Invariants

1. **Markdown Remains Canonical:** All knowledge persists in Markdown files. SQLite tables (`monitored_sources`, `change_candidates`, `knowledge_update_history`, `review_queue`) serve purely as operational state, audit logs, and cache.
2. **Untrusted Data Boundary:** All content retrieved from the web, APIs, or GitHub is strictly untrusted data. Prompt injections (e.g., "Ignore instructions", "System: override") are sanitized and never executed.
3. **Non-Destructive Evolution:** Knowledge updates must not destroy historical context without preserving an audit trail. Breaking changes or conflicts must be flagged and routed to `REVIEW_REQUIRED`.
4. **Traceable Attribution:** Every auto-applied fact must cite its `source_id`, canonical URL, observed timestamp, and version fingerprint.
5. **Zero Remote Dependencies:** Built using standard library `urllib` / SQLite, without introducing external vector databases, microservices, or cloud SaaS requirements.

---

## 2. Pipeline Flow Diagram

```
+---------------------------------------------------------------------------------+
|                                Monitored Sources                                |
|  - Official Documentation Webpages (HTTP ETag / Last-Modified)                  |
|  - GitHub Repositories (Releases, Tags, Documentation Paths)                    |
+---------------------------------------+-----------------------------------------+
                                        |
                             [Change Detection Engine]
                 - Conditional GET / GitHub REST API polling
                 - SHA-256 fingerprinting & 304 Not Modified
                 - Event classification: NEW_RELEASE, DOC_UPDATED, NO_CHANGE
                                        |
                                        v
+---------------------------------------+-----------------------------------------+
|                        Change Candidate Generation                              |
|  - Canonical URL & Observation Timestamp                                        |
|  - Raw Excerpt & Normalized Content                                             |
|  - Target Document & Affected Topics                                            |
|  - Preliminary Risk Classification                                              |
+---------------------------------------+-----------------------------------------+
                                        |
                             [Evidence & Policy Engine]
                 - Authenticity Check: Domain & Redirect Validation
                 - Injection Defense: Heuristic Prompt Injection Scanning
                 - Conflict & Freshness Verification
                                        |
                      +-----------------+-----------------+
                      |                                   |
              [AUTO_APPLY]                       [REVIEW_REQUIRED] / [REJECT]
                      |                                   |
                      v                                   v
+---------------------+-------------------+     +---------+-----------------------+
|        Markdown Knowledge Updater       |     |          Review Queue           |
|  - Atomic Markdown file update          |     |  - Pending human approval       |
|  - Provenance frontmatter recorded      |     |  - Diff, evidence, & rationale  |
|  - History logged in SQLite audit trail |     |  - CLI: approve / reject        |
|  - Incremental Index Sync (`sync_index`)|     +---------------------------------+
|  - Integrity Audit (`audit_integrity`)  |
+-----------------------------------------+
```

---

## 3. Data Model & Storage Schema

Extensions to `index.db` in `.knowledge_index/`:

### Table: `monitored_sources`
- `source_id` TEXT PRIMARY KEY
- `source_type` TEXT NOT NULL ('website', 'github_repo')
- `display_name` TEXT NOT NULL
- `canonical_url` TEXT NOT NULL
- `topics_json` TEXT NOT NULL
- `destination_doc_id` TEXT NOT NULL
- `trust_tier` TEXT NOT NULL ('official', 'trusted_partner', 'community')
- `trust_rationale` TEXT NOT NULL
- `enabled` INTEGER NOT NULL DEFAULT 1
- `polling_interval_seconds` INTEGER NOT NULL DEFAULT 3600
- `last_checked_at` REAL
- `last_observed_change_at` REAL
- `last_fingerprint` TEXT
- `last_etag` TEXT
- `last_modified_header` TEXT
- `last_error` TEXT
- `retry_count` INTEGER DEFAULT 0
- `config_json` TEXT NOT NULL

### Table: `change_candidates`
- `candidate_id` TEXT PRIMARY KEY
- `source_id` TEXT NOT NULL
- `observed_at` REAL NOT NULL
- `source_published_at` REAL
- `prev_fingerprint` TEXT
- `curr_fingerprint` TEXT NOT NULL
- `change_type` TEXT NOT NULL ('NEW_RELEASE', 'NEW_TAG', 'DOC_UPDATED')
- `change_summary` TEXT NOT NULL
- `raw_content` TEXT NOT NULL
- `normalized_content` TEXT NOT NULL
- `affected_doc_ids_json` TEXT NOT NULL
- `affected_topics_json` TEXT NOT NULL
- `evidence_json` TEXT NOT NULL
- `risk_level` TEXT NOT NULL ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')
- `policy_decision` TEXT NOT NULL ('AUTO_APPLY', 'REVIEW_REQUIRED', 'REJECT')
- `decision_rationale` TEXT NOT NULL
- `status` TEXT NOT NULL ('PENDING', 'APPLIED', 'QUEUED_FOR_REVIEW', 'APPROVED', 'REJECTED')
- `created_at` REAL NOT NULL

### Table: `knowledge_update_history`
- `history_id` INTEGER PRIMARY KEY AUTOINCREMENT
- `candidate_id` TEXT NOT NULL
- `source_id` TEXT NOT NULL
- `doc_path` TEXT NOT NULL
- `applied_at` REAL NOT NULL
- `diff_summary` TEXT NOT NULL
- `previous_content_hash` TEXT NOT NULL
- `new_content_hash` TEXT NOT NULL
- `applied_by` TEXT NOT NULL ('AUTO_POLICY', 'HUMAN_REVIEWER')

### Table: `review_queue`
- `queue_id` INTEGER PRIMARY KEY AUTOINCREMENT
- `candidate_id` TEXT UNIQUE NOT NULL
- `source_id` TEXT NOT NULL
- `enqueued_at` REAL NOT NULL
- `resolved_at` REAL
- `resolution` TEXT ('PENDING', 'APPROVED', 'REJECTED')
- `reviewer_note` TEXT

---

## 4. Policy Rules & Decision Matrix

| Condition | Risk Level | Policy Decision | Action |
| :--- | :--- | :--- | :--- |
| Official source, non-breaking version release note, clean parse, no injection | **LOW** | **AUTO_APPLY** | Append/update release section in destination doc, record history, sync index |
| Official source, documentation section edit with no conflict | **LOW** | **AUTO_APPLY** | Update doc section with audit provenance, sync index |
| Contradicts existing active statement in destination document | **HIGH** | **REVIEW_REQUIRED** | Enqueue in `review_queue` with highlighted conflicting excerpts |
| Breaking API changes or major version deprecation | **HIGH** | **REVIEW_REQUIRED** | Enqueue in `review_queue` with migration rationale |
| Untrusted domain redirect, unverified origin, or potential prompt injection | **CRITICAL** | **REJECT** | Log security rejection, record error in source metadata |
| Source unreachable (HTTP 5xx, 4xx, network timeout) | N/A | **RETRY** | Incremental backoff, maintain existing knowledge intact |
