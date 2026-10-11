# Knowledge Retrieval System Architecture

## 1. System Overview

The Knowledge Retrieval System is a high-efficiency, local-first retrieval infrastructure designed for AI coding agents and knowledge platforms. It treats Markdown files as the canonical source of truth while maintaining an embedded, incremental SQLite FTS5 search index.

```
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
|                      SQLite Storage Engine (WAL)                        |
|  - documents (metadata, tokens)                                         |
|  - sections (headings, 1-indexed line spans, tokens)                    |
|  - links (source, target, line numbers)                                 |
|  - sections_fts (FTS5 BM25 inverted index)                              |
+------------------------------------+------------------------------------+
                                     |
                             [Retriever Core]
                     (BM25 + Heading / Metadata Boost)
                                     |
                                     v
+------------------------------------+------------------------------------+
|                         Context Assembler                               |
|       - Token budgeting (tiktoken cl100k_base / fallback)               |
|       - Section-level excerpt extraction                                |
|       - Sufficiency evaluation & missing evidence flags                 |
+------------------------------------+------------------------------------+
                                     |
                         [Agent Interfaces & CLI]
        (search_knowledge, get_outline, read_section, context, audit)
```

## 2. Core Invariants

1. **Markdown is Canonical:** The SQLite database stored in `.knowledge_index/index.db` is an ephemeral, disposable cache. Deleting it and executing `knowledge-cli sync --rebuild` reconstitutes the entire index without information loss.
2. **Sub-Document Precision:** AI agents never need to load whole files. The system indexes down to section boundaries (`start_line`, `end_line`) and section slugs.
3. **Deterministic Token Control:** Evidence packages are bounded by an explicit token budget. If available evidence does not meet relevance thresholds, the system flags `is_sufficient: false` with explicit missing information diagnostics.
4. **Untrusted Content:** All retrieved document text is treated strictly as passive data, never as system instructions.

## 3. Data Flow & Components

### A. Document Parser (`knowledge_retrieval.parser`)
- Extracts YAML frontmatter without external preprocessors.
- Scans headings (`#` to `######`) to segment the document into discrete sections.
- Computes exact 1-indexed source line spans (`start_line`, `end_line`).
- Extracts Markdown links `[text](target)` and Obsidian Wikilinks `[[target#section|label]]`.

### B. Incremental Indexer (`knowledge_retrieval.indexer`)
- Maintains a path-to-hash catalog in SQLite.
- On sync, checks file modification timestamps (`mtime`) and SHA-256 hashes.
- Skips unchanged files in under 10 microseconds per file.
- Automatically handles added, modified, renamed, and deleted files transactionally.

### C. Search & Retrieval Pipeline (`knowledge_retrieval.retriever`)
- Leverages SQLite FTS5 with Porter Stemming and Unicode 61 tokenization.
- Applies weighted BM25 ranking across heading (weight 5.0), title (3.0), tags (2.0), and body content (1.0).
- Applies heuristic boosts for exact query token matches in titles and headings.

### D. Context Assembler (`knowledge_retrieval.context`)
- Filters candidates based on minimum relevance thresholds.
- Packages section headers with exact source coordinates (`path:start_line-end_line`).
- Bounds cumulative token count using `tiktoken` (cl100k_base) or fallback heuristics.
- Explicitly flags when available knowledge is insufficient or missing.

### E. Integrity Auditor (`knowledge_retrieval.integrity`)
- Verifies all outgoing references against known document IDs and relative paths.
- Detects orphaned documents with no links.
- Flags duplicate document IDs and malformed frontmatter.
