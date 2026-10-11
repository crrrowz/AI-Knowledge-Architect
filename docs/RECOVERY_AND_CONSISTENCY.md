# Failure Recovery, Concurrency, and Data Consistency Guide

**System:** AI-Knowledge-Architect  
**Auditor:** Senior Software Reliability Engineer  
**Date:** 2026-10-11  

---

## 1. Storage & Concurrency Architecture

The system uses an embedded SQLite database (`.knowledge_index/index.db`) operating in **Write-Ahead Logging (WAL)** mode.

### Invariants:
- `PRAGMA journal_mode = WAL;`
- `PRAGMA synchronous = NORMAL;`
- `PRAGMA foreign_keys = ON;`
- `timeout = 30.0;`

### Concurrency Characteristics:
- **Readers do not block Writers:** Multiple processes or agent threads can execute BM25 searches simultaneously while an incremental sync is writing to disk.
- **Writers do not block Readers:** Read transactions access the consistent snapshot in the database and WAL file.
- **Single Writer Serialized:** Write transactions are serialized with a 30-second busy timeout.

---

## 2. Failure Scenarios and Recovery Mechanisms

### A. Process Interruption During File Write
- **Mechanism:** `KnowledgeUpdater` writes new Markdown content to an isolated temporary file (`abs_path + ".tmp.<pid>.<time>"`), flushes buffers, and executes an atomic file replacement via `os.replace()`.
- **Outcome:** If a process crashes or power is lost before `os.replace()`, the original Markdown file remains completely intact. No partial or corrupted files can overwrite canonical knowledge.

### B. Interruption Between Markdown Write and SQLite Sync
- **Scenario:** The Markdown file is updated on disk, but the process crashes before SQLite `sync()` completes.
- **Outcome:** On the subsequent invocation of `knowledge-cli sync` or `engine.sync_index()`, the incremental indexer compares the disk file's SHA-256 hash and `mtime` against the SQLite catalog. The modified file is detected immediately and reindexed in under 20ms without manual intervention.

### C. Network Outages and Unreachable Sources
- **Scenario:** Monitored external websites or GitHub APIs experience HTTP 500, 502, 504, 404, or network timeouts.
- **Outcome:** `SourceFetcher` catches network errors, records the error string in `monitored_sources.last_error`, and increments `retry_count`. **Existing knowledge is never deleted, truncated, or modified on fetch failures.**

### D. Duplicate Change Discovery (Idempotency)
- **Scenario:** Running `check-updates` repeatedly when the source has not changed.
- **Outcome:** HTTP requests transmit `If-None-Match: <etag>` and `If-Modified-Since: <header>`. The server returns HTTP 304 Not Modified. If the server does not support 304, the client computes the SHA-256 content fingerprint and compares it to `last_fingerprint`. If unchanged, the event is classified as `NO_CHANGE`, preventing duplicate history records or duplicate candidates.

### E. Total Database Corruption Recovery
- **Disaster Recovery:** Because the SQLite database is strictly a derived cache of the canonical Markdown files:
  ```bash
  # 1. Delete corrupted SQLite index
  rm -rf .knowledge_index/
  
  # 2. Rebuild cleanly from canonical Markdown
  knowledge-cli sync --rebuild
  ```
  The entire database, full-text indexes, sections, and links are reconstituted deterministically from Markdown source files.
