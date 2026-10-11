# Changelog

All notable changes to **AI-Knowledge-Architect** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] - 2026-10-11

### Added
- **Core Knowledge Retrieval Engine:**
  - Embedded SQLite FTS5 search engine with BM25 ranking, Porter stemming, and Unicode 61 tokenization.
  - Heading-level Markdown chunking with exact 1-indexed source line spans (`start_line`, `end_line`).
  - Incremental indexer tracking file mtime and SHA-256 hashes to skip unchanged files in microseconds.
  - Token-budgeted context assembler integrating `tiktoken` (cl100k_base) and resilient fallback.
  - Structural integrity auditor detecting broken internal links, anchor mismatches, duplicate document IDs, and orphaned files.
- **Autonomous Knowledge Update Pipeline:**
  - Source registry supporting official documentation sites and GitHub repositories.
  - HTTP conditional request fetcher (ETag, If-Modified-Since) with HTTP 304 idempotency.
  - GitHub REST API release monitoring with unauthenticated and authenticated modes.
  - Evidence verification engine supporting prompt injection pattern detection and material conflict surfacing.
  - Deterministic policy engine: `AUTO_APPLY`, `REVIEW_REQUIRED`, and `REJECT`.
  - Human review queue manager and auditable historical update logs.
- **Security & Reliability Hardening:**
  - Pre-flight SSRF protection prohibiting loopback, private RFC-1918 networks, and cloud link-local metadata addresses (`169.254.169.254`).
  - Custom `SafeRedirectHandler` preventing SSRF redirect bypasses.
  - Path traversal defense verifying destination paths remain strictly within library root directories.
  - Stale approval revalidation preventing outdated review decisions from overwriting newer knowledge.
  - Atomic Markdown file replacement via temporary file swap (`os.replace`).
- **General-Purpose Knowledge Management Agent:**
  - Declarative, versioned Knowledge Library Profiles (`KnowledgeLibraryProfile`) with granular permission boundaries.
  - Six-stage agent lifecycle: `INSPECT -> PLAN -> POLICY CHECK -> EXECUTE -> VERIFY -> REPORT`.
  - Dry-run preview mode executing full planning with zero filesystem writes.
  - Evidence research collector and claim-to-evidence tracking (`researcher.py`).
  - Substantive document authoring engine with required section validation (*What It Is*, *How It Works*, *Applications*, *Limitations*, *Sources*).
  - Post-authoring retrieval verification confirming newly authored facts are retrievable.
- **Terminal & API Interfaces:**
  - Comprehensive `knowledge-cli` CLI supporting retrieval, sources, updates, reviews, profiles, and agent execution.
  - Python agent API facade in `knowledge_retrieval.api.KnowledgeEngine` and `knowledge_retrieval.agent.KnowledgeAgent`.
- **Testing & Benchmarking:**
  - 44 automated tests across 5 test suites with 100% pass rate.
  - Reproducible multi-scale benchmark evaluating 50, 500, and 5,000 synthetic documents.
