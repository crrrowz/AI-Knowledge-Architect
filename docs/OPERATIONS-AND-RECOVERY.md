# Operations, CLI Usage, and Disaster Recovery Guide

## 1. Quickstart

### Installation
Ensure Python 3.10+ is installed. In the repository directory:
```bash
pip install -e .
```

### Initial Indexing
To index all Markdown files in the current directory:
```bash
knowledge-cli sync
```

### Inspect Repository Status
```bash
knowledge-cli status
```

---

## 2. CLI Command Reference

### `sync`
Synchronizes the index with Markdown files on disk incrementally:
```bash
knowledge-cli sync [--rebuild] [--root <dir>] [--db <path>]
```
- `--rebuild`: Forces a clean wipe and re-index of all files.

### `search`
Performs section-level BM25 search:
```bash
knowledge-cli search "storage architecture" --limit 5
knowledge-cli search "consensus" --tags "distributed,consensus" --json
```

### `outline`
Displays the structural heading tree and line spans of a document:
```bash
knowledge-cli outline storage_architecture.md
```

### `section`
Retrieves exact section text:
```bash
knowledge-cli section storage-arch sqlite-fts5-engine
```

### `context`
Assembles a token-bounded evidence package for an agent:
```bash
knowledge-cli context "How does SQLite FTS5 handle indexing?" --budget 1000
```

### `related`
Traverses forward links and backlinks:
```bash
knowledge-cli related retrieval-pipeline
```

### `audit`
Scans for broken links, duplicate IDs, and orphaned documents:
```bash
knowledge-cli audit [--json]
```

### Auto-Update Pipeline Commands

#### `source-add`
Register a monitored documentation website or GitHub repository:
```bash
knowledge-cli source-add src-sqlite-repo --type github_repo --name "SQLite Mirror" --url "https://github.com/sqlite/sqlite" --doc dist-storage --topics "sqlite,storage" --trust official
```

#### `source-list`
List all registered sources:
```bash
knowledge-cli source-list
```

#### `check-updates`
Poll monitored sources, detect changes, verify evidence, and auto-apply or queue:
```bash
knowledge-cli check-updates [--source <source_id>] [--json]
```

#### `review-list`
List changes requiring human review and approval:
```bash
knowledge-cli review-list
```

#### `review-approve` & `review-reject`
Approve or reject a queued candidate:
```bash
knowledge-cli review-approve <candidate_id> --note "Approved by team lead"
knowledge-cli review-reject <candidate_id> --note "Rejected: incompatible architecture"
```

#### `update-history`
View audit history of applied updates:
```bash
knowledge-cli update-history [--limit 20]
```

---

## 3. Python Agent API Usage

AI agents and automated tools can interact with the system directly via Python:

```python
from knowledge_retrieval.api import KnowledgeEngine

# Initialize engine
engine = KnowledgeEngine(root_dir=".")

# 1. Sync & Search
engine.sync_index()
results = engine.search_knowledge("SQLite FTS5 storage", limit=3)

# 2. Register external source for autonomous updates
engine.register_source(
    source_id="src-sqlite-docs",
    source_type="website",
    display_name="SQLite Official Documentation",
    canonical_url="https://www.sqlite.org/fts5.html",
    destination_doc_id="dist-storage",
    topics=["sqlite", "fts5"],
    trust_tier="official"
)

# 3. Check for external updates (auto-applies safe updates, queues risky changes)
update_results = engine.check_updates()

# 4. Inspect human review queue
queue_items = engine.list_review_queue()
for item in queue_items:
    print(f"Pending review: {item['candidate_id']} - {item['change_summary']}")
    # Approve if verified
    # engine.approve_update(item['candidate_id'], note="Verified manually")
```

---

## 4. Maintenance and Recovery Procedures

### Index Corruption or Interrupted Sync
Because the SQLite database is strictly a derived cache and uses WAL mode:
1. Delete the `.knowledge_index` folder:
   ```bash
   rmdir /s /q .knowledge_index   # Windows
   rm -rf .knowledge_index        # Linux/macOS
   ```
2. Run a clean rebuild:
   ```bash
   knowledge-cli sync --rebuild
   ```
3. Verify integrity:
   ```bash
   knowledge-cli audit
   ```

### Stale File Cleanup
The index automatically detects deleted files on each `sync` invocation and removes their document, section, and link entries atomically.
