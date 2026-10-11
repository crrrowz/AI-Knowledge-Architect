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

---

## 3. Python Agent API Usage

AI agents and automated tools can interact with the system directly via Python:

```python
from knowledge_retrieval.api import KnowledgeEngine

# Initialize engine
engine = KnowledgeEngine(root_dir=".")

# 1. Sync
engine.sync_index()

# 2. Search
results = engine.search_knowledge("SQLite FTS5 storage", limit=3)

# 3. Read specific section
section = engine.read_section("storage-arch", "sqlite-fts5-engine")
print(section["content"])

# 4. Assemble bounded context
evidence = engine.get_source_context("How are logs replicated?", token_budget=800)
if evidence["is_sufficient"]:
    for excerpt in evidence["excerpts"]:
        print(f"[{excerpt['path']}:{excerpt['start_line']}-{excerpt['end_line']}]")
        print(excerpt["content"])
else:
    print("Insufficient evidence:", evidence["insufficient_reason"])
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
