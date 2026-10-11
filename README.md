# AI-Knowledge-Architect

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-44%20passed-brightgreen.svg)](tests/)
[![Status](https://img.shields.io/badge/status-ready%20for%20controlled%20local%20use-success.svg)](docs/END_TO_END_AUDIT.md)

**A high-efficiency, local-first Markdown knowledge retrieval and autonomous agent system for AI coding assistants and developer tooling.**

AI-Knowledge-Architect treats human-readable Markdown files as the canonical source of truth while maintaining an embedded, incremental SQLite FTS5 search index for sub-document precision retrieval, token-bounded context assembly, autonomous source monitoring, and evidence-grounded research and authoring.

---

## 1. Problem Solved & Core Value

AI agents operating over large software repositories face severe context-window limits, token costs, hallucinated citations, and stale documentation:
1. **Context Window Waste:** Loading whole documents dilutes model attention and inflates inference costs. AI-Knowledge-Architect indexes down to exact section headings and 1-indexed line ranges (`start_line`, `end_line`), assembling only relevant excerpts within strict token budgets (yielding **96.35% context window reduction**).
2. **Loss of Local Truth:** Traditional RAG stacks rely on remote cloud vector stores and black-box embeddings. AI-Knowledge-Architect is **100% local-first**, running on embedded SQLite FTS5 with BM25 ranking, zero external network dependencies, and complete disaster recovery from Markdown.
3. **Stale Documentation:** Software architectures evolve constantly. AI-Knowledge-Architect provides an **Autonomous Update Pipeline** that monitors official documentation and GitHub releases with conditional HTTP (ETags), verifies evidence, detects conflicts, and updates Markdown files non-destructively.
4. **General-Purpose Agent Orchestration:** Customized through declarative **Library Profiles**, the agent executes an auditable six-stage lifecycle: `INSPECT -> PLAN -> POLICY CHECK -> EXECUTE -> VERIFY -> REPORT` to organize, research, author, and independently verify knowledge libraries without cross-library contamination.

---

## 2. Project Status

- **Maturity:** Production-Ready for Controlled Local Use (Beta v0.1.0).
- **Test Coverage:** 44/44 automated tests passing (100% pass rate in <8s).
- **Scalability Verified:** Benchmark verified up to 5,000 documents (20,000 sections, 813,990 tokens) with p50 search latency of 20.26ms.

---

## 3. Key Capabilities

- **Sub-Document Section Precision:** Chunks documents by Markdown headings, extracting exact line numbers and slugified section IDs.
- **Microsecond Incremental Indexing:** SHA-256 and `mtime` change detection skips unchanged files in <2ms, indexing cold-start repositories at >150 documents/sec.
- **Token-Budgeted Context Assembler:** Packages section-level evidence strictly within configured token caps using `tiktoken` (cl100k_base) and explicit sufficiency checks.
- **Integrity Auditor:** Detects broken internal links (`[[wikilinks]]` and `[links](path)`), anchor mismatches, duplicate IDs, and orphaned files.
- **Autonomous Source Monitoring:** Monitors official documentation and GitHub releases with conditional GET (ETags / Last-Modified), rate-limit backoff, and human review routing for breaking changes.
- **Hardened Security Boundaries:** Full SSRF defense blocking loopback/private/cloud metadata subnets, redirect chain enforcement, path traversal guards, and prompt injection defense.
- **Evidence-Grounded Research & Authoring:** Researches topics, tracks claims to source URLs, authors substantive Markdown (*What*, *How*, *Applications*, *Limitations*, *Sources*), and verifies retrievability via post-authoring queries.
- **Multi-Library Isolation:** Complete physical separation of root directories, SQLite databases, review queues, and update histories across libraries.

---

## 4. Architecture Overview

```text
+-------------------------------------------------------------------------+
|                        Canonical Markdown Corpus                        |
|   (Frontmatter, Headings, Sections, Wikilinks, Line-level content)      |
+------------------------------------+------------------------------------+
                                     |
                          [Incremental Indexer]
                         (SHA-256 / mtime caches)
                                     |
                                     v
+------------------------------------+------------------------------------+
|                    SQLite Storage Engine (WAL Mode)                     |
|  - documents (path, doc_id, metadata, tokens, content_hash)             |
|  - sections (path, heading, 1-indexed line spans, tokens)               |
|  - links (source, target, line numbers)                                 |
|  - sections_fts (FTS5 BM25 inverted index)                              |
|  - monitored_sources, change_candidates, review_queue, audit_history    |
+------------------------------------+------------------------------------+
                                     |
                       [Retriever & Context Assembler]
                       (BM25 Ranking + Heading Boost)
                                     |
                                     v
+------------------------------------+------------------------------------+
|                    General-Purpose Knowledge Agent                      |
|       INSPECT -> PLAN -> POLICY CHECK -> EXECUTE -> VERIFY -> REPORT    |
+------------------------------------+------------------------------------+
                                     |
                   [CLI (`knowledge-cli`) & Python API]
```

---

## 5. Installation

### Requirements
- **Python:** 3.10, 3.11, or 3.12.
- **SQLite:** 3.35+ with FTS5 enabled (standard in official Python binaries).
- **Operating Systems:** Windows 10/11, macOS, Linux.

### Install from Source
```bash
git clone https://github.com/your-org/AI-Knowledge-Architect.git
cd AI-Knowledge-Architect

# Install package in editable development mode
pip install -e .

# Or install with testing dependencies
pip install -e ".[dev]"
```

---

## 6. Quick Start

### A. Index & Search Existing Markdown Files
```bash
# 1. Incrementally index current directory
knowledge-cli sync

# 2. View repository index statistics
knowledge-cli status

# 3. Search sections with BM25 ranking
knowledge-cli search "storage architecture" --limit 3

# 4. Assemble token-bounded evidence package for an LLM prompt
knowledge-cli context "How does the storage engine handle WAL?" --budget 1000

# 5. Audit knowledge base integrity (broken links, duplicates)
knowledge-cli audit
```

### B. Autonomous Source Monitoring & Updates
```bash
# 1. Register a monitored GitHub repository
knowledge-cli source-add src-sqlite-repo --type github_repo \
  --name "SQLite Mirror" --url "https://github.com/sqlite/sqlite" \
  --doc dist-storage --topics "sqlite,storage"

# 2. Poll registered sources for updates (auto-applies safe updates)
knowledge-cli check-updates

# 3. View changes requiring human review (breaking changes or conflicts)
knowledge-cli review-list

# 4. View permanent audit history of applied updates
knowledge-cli update-history
```

### C. General-Purpose Knowledge Agent
```bash
# 1. Create a library profile
knowledge-cli profile-create ./ai_profile.yaml \
  --id "ai-tech-core" --root "./knowledge/ai" \
  --goal "Build a concise, well-structured knowledge base about AI technologies."

# 2. Inspect library inventory without modifying files
knowledge-cli agent-inspect ./ai_profile.yaml

# 3. Preview planned operations (Dry-Run mode)
knowledge-cli agent-run ./ai_profile.yaml --dry-run

# 4. Execute live research, authoring, indexing, and independent verification
knowledge-cli agent-run ./ai_profile.yaml
```

---

## 7. Python API Integration

AI agents and developer tools can interface directly via the unified Python API:

```python
from knowledge_retrieval.api import KnowledgeEngine
from knowledge_retrieval.agent import KnowledgeAgent
from knowledge_retrieval.profile import KnowledgeLibraryProfile

# Initialize engine on a Markdown directory
engine = KnowledgeEngine(root_dir="./knowledge")

# 1. Synchronize index and search
engine.sync_index()
results = engine.search_knowledge("consensus algorithm", limit=5)

# 2. Assemble bounded context for LLM prompt injection
context = engine.get_source_context("How do nodes elect a leader?", token_budget=800)
if context["is_sufficient"]:
    for excerpt in context["excerpts"]:
        print(f"[{excerpt['path']}:{excerpt['start_line']}-{excerpt['end_line']}]")
        print(excerpt["content"])

# 3. Orchestrate Knowledge Agent using a Library Profile
profile = KnowledgeLibraryProfile.load("ai_profile.yaml")
agent = KnowledgeAgent(profile)
report = agent.run(dry_run=False)
print(f"Verified {report.verification_evidence['verified_operations_count']} operations.")
```

---

## 8. Running Tests & Benchmarks

The project maintains deterministic, isolated automated test suites requiring zero live internet access:

```bash
# Run all 44 automated tests across 5 test suites
pytest -v

# Run reproducible multi-scale benchmark (50, 500, and 5,000 documents)
python benchmarks/rigorous_benchmark.py
```

---

## 9. Documentation System

A comprehensive documentation architecture is maintained in [`docs/INDEX.md`](docs/INDEX.md):

- **Architecture & Design:**
  - [Core Architecture Specification](docs/ARCHITECTURE.md)
  - [Knowledge Agent Architecture](docs/KNOWLEDGE_AGENT_ARCHITECTURE.md)
  - [Library Profiles Schema](docs/KNOWLEDGE_LIBRARY_PROFILES.md)
  - [Autonomous Update Pipeline Design](docs/AUTO_UPDATE_DESIGN.md)
  - [Research & Authoring Design](docs/RESEARCH_AUTHORING_DESIGN.md)
  - [ADR 001: Technology Selection](docs/ADR-001-technology-selection.md)
- **Operations & Security:**
  - [Operations & Recovery Guide](docs/OPERATIONS-AND-RECOVERY.md)
  - [Failure Recovery & Consistency](docs/RECOVERY_AND_CONSISTENCY.md)
  - [Security Audit Report](docs/SECURITY_AUDIT.md)
  - [Agent Security Boundaries](docs/AGENT_SECURITY_BOUNDARIES.md)
  - [Operational Remaining Risks](docs/REMAINING_RISKS.md)
- **Audits & Benchmarks:**
  - [End-to-End Reliability Audit](docs/END_TO_END_AUDIT.md)
  - [Independent Reliability Audit](docs/AUDIT_REPORT.md)
  - [Benchmark Methodology & Scalability](docs/BENCHMARK_METHODOLOGY.md)
  - [Research & Authoring Test Report](docs/RESEARCH_AUTHORING_TEST_REPORT.md)

---

## 10. Community & Governance

- **[Contributing Guide](CONTRIBUTING.md)**: Development setup, PR process, and commit rules.
- **[Security Policy](SECURITY.md)**: Private vulnerability disclosure and threat model.
- **[Code of Conduct](CODE_OF_CONDUCT.md)**: Contributor Covenant standards and enforcement.
- **[Governance Model](GOVERNANCE.md)**: Consensus model and release authority.
- **[Maintainers](MAINTAINERS.md)**: Active maintainers and contact mechanisms.
- **[Changelog](CHANGELOG.md)**: Release history and version migration notes.
- **[Support](SUPPORT.md)**: Where to ask questions and report problems.

---

## 11. License

Licensed under the **Apache License, Version 2.0**. See [`LICENSE`](LICENSE) for terms and conditions.
