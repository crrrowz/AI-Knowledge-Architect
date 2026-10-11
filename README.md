# AI-Knowledge-Architect

A high-efficiency, local-first Markdown knowledge retrieval system for AI agents and developer tools.

Treats Markdown files as the canonical source of truth while maintaining an embedded, incremental SQLite FTS5 index for sub-document precision search and token-bounded context assembly.

## Key Features

- **Local-First & Zero-Remote:** Runs entirely on embedded SQLite FTS5. No remote database, Docker daemon, or vector cloud required.
- **Sub-Document Precision:** Chunks documents by Markdown headings, extracting exact 1-indexed line spans (`start_line`, `end_line`) and section IDs.
- **Incremental Indexing:** SHA-256 and `mtime` change detection skips unchanged files in microseconds.
- **Token-Budgeted Context Assembler:** Packages relevant excerpts strictly within configured token limits (using `tiktoken` with resilient fallback) and flags insufficient evidence.
- **Knowledge Integrity Auditor:** Automatically detects broken internal links (`[[wikilinks]]` and `[links](path)`), duplicate IDs, and orphaned documents.
- **Agent-Ready Python API & CLI:** Simple functions and CLI commands designed for agent tool integrations.

## Installation

```bash
git clone <repo-url>
cd AI-Knowledge-Architect
pip install -e .
```

## Quick Start

```bash
# 1. Index current repository
knowledge-cli sync

# 2. Check statistics
knowledge-cli status

# 3. Search for sections
knowledge-cli search "storage architecture" --limit 3

# 4. Assemble bounded evidence package for an LLM
knowledge-cli context "How does the storage engine handle WAL?" --budget 1000

# 5. Check repository health
knowledge-cli audit

# 6. Autonomous updates: register source & poll
knowledge-cli source-add src-sqlite-repo --type github_repo --name "SQLite Mirror" --url "https://github.com/sqlite/sqlite" --doc dist-storage --topics "sqlite"
knowledge-cli check-updates
knowledge-cli review-list

# 7. General-Purpose Agent: inspect, plan, dry-run, and run
knowledge-cli profile-create ./my_profile.yaml --id "my-lib" --root "./docs" --goal "Maintain system docs"
knowledge-cli agent-inspect ./my_profile.yaml
knowledge-cli agent-plan ./my_profile.yaml
knowledge-cli agent-run ./my_profile.yaml --dry-run
knowledge-cli agent-run ./my_profile.yaml
```

## Running Tests and Benchmarks

```bash
# Run complete test suite (41 tests across retrieval, audit, auto-update, and agent)
pytest tests/ -v

# Run multi-scale benchmark (50, 500, 5000 documents)
python benchmarks/rigorous_benchmark.py
```

## Documentation

- [Knowledge Agent Architecture Specification](docs/KNOWLEDGE_AGENT_ARCHITECTURE.md)
- [Knowledge Library Profiles Guide & Schema](docs/KNOWLEDGE_LIBRARY_PROFILES.md)
- [Knowledge Agent Operations Guide](docs/AGENT_OPERATIONS.md)
- [Agent Security Boundaries & Safety Invariants](docs/AGENT_SECURITY_BOUNDARIES.md)
- [Agent Verification & Test Report](docs/AGENT_TEST_REPORT.md)
- [Autonomous Knowledge Update Pipeline Design](docs/AUTO_UPDATE_DESIGN.md)
- [Architecture Specification](docs/ARCHITECTURE.md)
- [Architecture Decision Record (ADR 001)](docs/ADR-001-technology-selection.md)
- [Document Schema Specification](docs/DOCUMENT-SCHEMA.md)
- [Operations & Recovery Guide](docs/OPERATIONS-AND-RECOVERY.md)
- [Independent Reliability Audit Report](docs/AUDIT_REPORT.md)
- [End-to-End Reliability & Integration Audit](docs/END_TO_END_AUDIT.md)
