# Knowledge Agent Architecture Specification

**System:** AI-Knowledge-Architect  
**Role:** General-Purpose Knowledge Management Agent  
**Version:** 1.0  
**Date:** 2026-10-11  

---

## 1. Architectural Philosophy & Invariants

The `KnowledgeAgent` transforms AI-Knowledge-Architect from a passive retrieval search engine into an active, domain-independent knowledge management agent.

### Core Invariants:
1. **Configurable Independence:** The agent contains no hardcoded domain logic. Every behavior—target outcomes, permissions, organization, sources, quality rules—is driven by an explicit `KnowledgeLibraryProfile`.
2. **Canonical Markdown:** All knowledge resides in standard Markdown documents with YAML frontmatter. Database tables serve exclusively as operational indices, review queues, and audit trails.
3. **Deterministic Separation of Stages:** The agent strictly separates planning from execution:
   ```
   INSPECT -> PLAN -> POLICY CHECK -> EXECUTE -> VERIFY -> REPORT
   ```
4. **Independent Verification:** The agent never relies on language model assertions or write return codes alone. Post-execution, the agent scans actual filesystem bytes, directory structures, and search index availability to independently prove outcome satisfaction.
5. **Multi-Library Isolation:** Multiple libraries can operate concurrently on the same machine without mixing documents, databases, caches, or review queues.

---

## 2. Six-Stage Pipeline Detail

```
+---------------------------------------------------------------------------------+
|                       1. INSPECT (Read-only Assessment)                         |
|  - Scans permitted library directory root                                       |
|  - Collects active documents, sections, tokens, and observed topics             |
|  - Audits integrity (broken links, missing headings, duplicate IDs)             |
|  - Gathers pending review queue candidates                                      |
+---------------------------------------+-----------------------------------------+
                                        |
                                        v
+---------------------------------------------------------------------------------+
|                         2. PLAN (Goal-Driven Reasoning)                         |
|  - Compares observed inventory against Profile expected organization            |
|  - Identifies missing required topics or structural gaps                        |
|  - Proposes atomic operations (CREATE_DOCUMENT, UPDATE, FIX_LINK, DELETE)       |
+---------------------------------------+-----------------------------------------+
                                        |
                                        v
+---------------------------------------------------------------------------------+
|                     3. POLICY CHECK (Deterministic Safety)                      |
|  - Validates hard filesystem boundaries and permitted sub-paths                 |
|  - Enforces permissions (allow_create, allow_modify, allow_delete)               |
|  - Assigns PolicyDecision: AUTO_APPLY, REVIEW_REQUIRED, REJECT                  |
+---------------------------------------+-----------------------------------------+
                                        |
                                        v
+---------------------------------------------------------------------------------+
|                   4. EXECUTE (Atomic Implementation / Dry-Run)                  |
|  - Dry-Run Mode: Previews operations with zero filesystem modifications        |
|  - Live Mode: Atomic file replacement (temp file -> os.replace)                 |
|  - Provenance headers and audit history logging                                 |
|  - Immediate incremental SQLite FTS5 reindexing                                 |
+---------------------------------------+-----------------------------------------+
                                        |
                                        v
+---------------------------------------------------------------------------------+
|                    5. VERIFY (Independent State Confirmation)                   |
|  - Proves files exist on disk with positive byte sizes                          |
|  - Validates full-text retrievability via FTS5                                  |
|  - Confirms zero residual broken links                                          |
+---------------------------------------+-----------------------------------------+
                                        |
                                        v
+---------------------------------------------------------------------------------+
|                       6. REPORT (Auditable Final Summary)                       |
|  - Lists completed, skipped, and failed operations                              |
|  - Provides execution duration, run IDs, and unresolved blockers                |
+---------------------------------------------------------------------------------+
```
