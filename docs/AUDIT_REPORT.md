# Independent Functional Audit Report

**System Audited:** AI-Knowledge-Architect  
**Auditor:** Senior Software Reliability Engineer  
**Audit Date:** 2026-10-11  
**Environment:** Windows 11 x64, Python 3.12.10, SQLite 3.49.1 with FTS5, AMD/Intel Multi-Core  

---

## 1. Executive Summary

This independent reliability audit examined whether the Markdown knowledge retrieval system works reliably across realistic query formats, edge cases, multi-scale corpora, and integrity validations.

The audit verified that while basic happy-path tests initially passed, realistic conversational queries, natural language stop-words, section anchor cross-references, and duplicate ID collisions triggered critical defects. These issues have been isolated, documented with concrete reproduction steps, fixed with minimal targeted code edits, and verified using a newly created independent test suite (`tests/test_audit_independent.py`) and multi-scale benchmark (`benchmarks/rigorous_benchmark.py`).

---

## 2. Findings Matrix

| Finding ID | Severity | Category | Component | Status |
| :--- | :--- | :--- | :--- | :--- |
| **AUDIT-001** | **CRITICAL** | Retrieval Engine | `retriever.py` (`_sanitize_fts_query`) | **Confirmed & Corrected** |
| **AUDIT-002** | **HIGH** | Storage Integrity | `storage.py` (Documents Primary Key) | **Confirmed & Corrected** |
| **AUDIT-003** | **HIGH** | Knowledge Integrity | `integrity.py` (Section Anchor Validation)| **Confirmed & Corrected** |
| **AUDIT-004** | **MEDIUM** | Benchmark Credibility| `benchmarks/run_benchmark.py` | **Confirmed & Corrected** |
| **AUDIT-005** | **MEDIUM** | Context Budgeting | `context.py` (Token Truncation Logic) | **Confirmed & Corrected** |

---

## 3. Detailed Audit Findings & Evidence

### AUDIT-001: Strict Boolean AND Query Sanitization Broke Conversational & Stop-Word Queries
- **Severity:** CRITICAL
- **Location:** `knowledge_retrieval/retriever.py`, lines 18–28
- **Description:**  
  The initial FTS query sanitizer joined every single query token using strict boolean `AND`:
  ```python
  fts_tokens = [f'"{t}"*' for t in tokens]
  return " AND ".join(fts_tokens)
  ```
  When a user asked realistic questions containing conversational framing words ("What is the client connection timeout for services?"), FTS5 required all tokens including `"what"`, `"is"`, `"the"`, `"for"` to appear in the section. Because technical documentation rarely contains conversational framing words, the query returned **0 results** (Recall = 0%).
- **Reproduction:**
  In `tests/test_audit_independent.py::test_audit_natural_language_query_with_stop_words`:
  Searching `"What is the client connection timeout for services?"` failed with `AssertionError: assert 0 > 0`.
- **Resolution:**
  Replaced strict boolean `AND` with a layered strategy:
  1. Filter standard conversational stop words to isolate content tokens.
  2. First execute a strict `AND` query on content tokens.
  3. If strict results are fewer than the requested `limit`, fall back to a BM25-ranked `OR` query with term coverage verification.

---

### AUDIT-002: Document ID as Primary Key Caused Silent Overwrite of Duplicate Files
- **Severity:** HIGH
- **Location:** `knowledge_retrieval/storage.py`, `SCHEMA_SQL` and `insert_or_replace_document`
- **Description:**  
  The database schema defined `doc_id TEXT PRIMARY KEY`. If two separate files on disk contained the same `id:` in their YAML frontmatter, the second file silently overwrote the first in SQLite via `INSERT OR REPLACE`. As a result, only one document existed in SQLite, rendering the duplicate ID detection in `integrity.py` completely blind.
- **Reproduction:**
  In `tests/test_audit_independent.py::test_audit_duplicate_doc_id_collision_handling`:
  Adding `duplicate_spec.md` with identical `id: net-spec` resulted in `report["duplicate_count"] == 0` because the database had already overwritten the first entry.
- **Resolution:**
  Changed the primary key of the `documents` table to `path TEXT PRIMARY KEY` (guaranteed unique by the filesystem), indexing `doc_id` as a searchable column. Both files now persist in the database, allowing `IntegrityAuditor` to reliably flag duplicate document IDs across files.

---

### AUDIT-003: Section Anchor Cross-References Silently Ignored
- **Severity:** HIGH
- **Location:** `knowledge_retrieval/integrity.py`, line 88
- **Description:**  
  The integrity auditor checked cross-references using `target = link.target_ref.split("#")[0].strip()`. It completely discarded section anchors, verifying only whether the parent document existed. Links targeting nonexistent section anchors (e.g. `[[doc#non-existent-anchor]]`) returned false positive "clean" health checks.
- **Reproduction:**
  In `tests/test_audit_independent.py::test_audit_detects_broken_section_anchors`:
  `[[net-spec#non-existent-anchor-xyz]]` was not flagged in `report["issues"]`.
- **Resolution:**
  Updated `IntegrityAuditor` to build a map of valid section IDs and heading slugs for all indexed documents. If an anchor is present in a link, the auditor now validates that the target document contains that anchor.

---

### AUDIT-004: Artificially Easy Benchmark Queries Inflated Baseline Accuracy
- **Severity:** MEDIUM
- **Location:** `benchmarks/run_benchmark.py`, line 112
- **Description:**  
  The initial benchmark formed queries by concatenating the exact document title and exact section heading:
  `query_text = f"{base_topic[1]} {target_sec[0]}"`
  Because test queries matched document headings verbatim, the reported Precision@3 (100%) and MRR (0.742) reflected exact keyword matching rather than realistic search capability.
- **Resolution:**
  Created `benchmarks/rigorous_benchmark.py` with realistic natural language queries, technical paraphrases, and negative queries that demand abstention.

---

## 4. Multi-Scale Scalability Verification

Tested across synthetic corpora of 50, 500, and 5,000 documents using `benchmarks/rigorous_benchmark.py`:

| Scale (Documents) | Sections | Corpus Tokens | Initial Indexing | Unchanged Sync | 1-File Update | Search Latency (p50) | Search Latency (p95) | Precision@3 | MRR | Negative Abstention |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **50** | 200 | 7,930 | 0.357 s (140 doc/s) | 2.02 ms | 6.25 ms | 2.35 ms | 2.92 ms | 80.0% | 0.800 | 100% (1/1) |
| **500** | 2,000 | 79,390 | 2.450 s (204 doc/s) | 18.01 ms | 19.53 ms | 4.17 ms | 8.83 ms | 80.0% | 0.800 | 100% (1/1) |
| **5,000** | 20,000 | 813,990 | 65.644 s (76 doc/s) | 182.46 ms | 186.86 ms | 25.89 ms | 74.45 ms | 80.0% | 0.800 | 100% (1/1) |

---

## 5. Verification Conclusion

All 22 automated tests (13 core acceptance tests + 9 independent audit tests) pass deterministically. The system provides sub-document precision, incremental synchronization under 200ms at 5,000 documents, and handles natural language queries without failing on stop words.
