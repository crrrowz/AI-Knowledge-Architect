# Architecture Decision Record (ADR 001): Technology Selection & Engine Design

**Status:** Accepted  
**Date:** 2026-10-11  
**Author:** AI Knowledge Infrastructure Architect  

---

## 1. Context and Problem Statement

AI agents operating over large, growing codebases and Markdown knowledge repositories face severe context-window and token-cost constraints. Passing entire documents or full repositories into context windows causes attention dilution, hallucination, latency spikes, and high operational costs.

We require a local-first system that treats Markdown files as the canonical source of truth, indexes document hierarchy and section boundaries without central cloud dependencies, and provides sub-document precision retrieval (exact section citations and line ranges) within bounded token budgets.

## 2. Decision Drivers

- **Zero-Remote Infrastructure:** Must operate purely locally on developer machines and isolated environments without requiring external servers, Docker containers, or cloud vector databases.
- **Incremental Efficiency:** Thousands of Markdown documents must be indexed rapidly; modifications to a single file must reindex only that file in milliseconds.
- **Section-Level Retrieval:** Retrieve exact subsections, line numbers, and headings rather than whole documents.
- **Measurable Precision:** High lexical and structural relevance with deterministic scoring (BM25 + heading/metadata boost).
- **Graceful Token Budgeting:** Assemble evidence packages strictly respecting token limits with explicit sufficiency warnings.
- **Simplicity & Maintainability:** Standard, stable libraries without fragile native compilation layers.

## 3. Technology Evaluation

| Component | Considered Alternatives | Selected Technology | Rationale |
| :--- | :--- | :--- | :--- |
| **Language Runtime** | Node.js / TypeScript vs. Python 3.12 | **Python 3.12** | Universal data science, AI agent tooling, native SQLite FTS5 binding in standard library, rich ecosystem (`tiktoken`, `python-frontmatter`, `pytest`). |
| **Search Engine** | Tantivy, DuckDB, ChromaDB, SQLite FTS5 | **SQLite FTS5 (BM25)** | Built-in to Python's `sqlite3`, zero external binaries or services, robust BM25 ranking, ACID transactions, transactional crash recovery, fast queries (<5ms for thousands of records). |
| **Document Parsing** | AST Regex vs `markdown-it-py` vs CommonMark | **Heading-Aware Line Scanner with Frontmatter Parser** | Preserves exact 1-indexed source line numbers (`start_line`, `end_line`), isolates YAML frontmatter, extracts `[[wikilinks]]` and Markdown links, resilient to malformed syntax. |
| **Token Estimation** | Character heuristic (char/4) vs `tiktoken` (cl100k_base) | **Dual Strategy: `tiktoken` (cl100k_base) with fallback to character heuristic** | Precise OpenAI/Claude-aligned token budgeting when available, fallback ensures zero hard-crash risk. |
| **Semantic Search** | Mandatory dense vector embeddings vs. Layered/Optional | **Layered Architecture (Lexical BM25 baseline + pluggable vector hook)** | Lexical BM25 provides immediate, reproducible, zero-model-dependency search. Semantic search is pluggable and optional rather than an unconditional runtime dependency. |

## 4. Consequences and Invariants

1. **Markdown is Canonical:** The SQLite database is purely a derived cache stored in `.knowledge_index/index.db`. Deleting it and rebuilding guarantees zero data loss.
2. **Deterministic Citations:** Every retrieved chunk must cite `path`, `heading`, `section_id`, `start_line`, and `end_line`.
3. **No Unbounded Retrieval:** Search and context assembly mandate explicit limits (`limit`, `token_budget`).
