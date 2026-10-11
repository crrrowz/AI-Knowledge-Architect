# Knowledge Library Profiles Guide & Schema

## 1. Profile Format Specification

A Knowledge Library Profile is a declarative YAML or JSON specification that customizes a knowledge management agent for an individual repository.

### Fields Reference

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `library_id` | string | Yes | Unique identifier for the knowledge library. |
| `name` | string | Yes | Human-readable display name. |
| `root_dir` | string | Yes | Path to the root directory containing Markdown files. |
| `goal` | string | Yes | High-level objective guiding agent planning and organization. |
| `outcomes` | list[string] | No | Specific deliverables and completeness criteria. |
| `permitted_paths` | list[string] | No | Allowed write sub-paths within `root_dir` (default: entire root). |
| `organization` | list[object] | No | Target directory structure and expected document IDs. |
| `permissions` | object | No | Permission boundaries (allow_create, allow_modify, allow_delete). |
| `quality_rules` | object | No | Validation criteria (frontmatter, title H1, link integrity). |
| `db_path` | string | No | Custom SQLite index path (default: `<root_dir>/.knowledge_index/index.db`). |

---

## 2. Example 1: AI Knowledge Library Profile

```yaml
library_id: ai-knowledge-hub
name: "AI Systems Knowledge Base"
root_dir: "./knowledge/ai"
goal: "Maintain comprehensive specifications for AI models, retrieval systems, and prompt engineering."
version: "1.0"
outcomes:
  - "Complete architectural references for transformer and diffusion models"
  - "Standardized retrieval evaluation benchmarks and metric definitions"
permitted_paths:
  - "models"
  - "retrieval"
  - "benchmarks"
organization:
  - directory: "models"
    expected_doc_ids:
      - "transformer-architecture"
      - "attention-mechanisms"
    description: "Core neural architecture specifications."
  - directory: "retrieval"
    expected_doc_ids:
      - "bm25-indexing"
      - "vector-embeddings"
    description: "Retrieval pipeline and vector indexing references."
permissions:
  allow_read: true
  allow_create: true
  allow_modify: true
  allow_delete: false
  allow_external_fetch: true
  require_approval_for_destructive: true
quality_rules:
  require_frontmatter: true
  required_frontmatter_keys: ["id", "title", "tags"]
  require_title_h1: true
  enforce_link_integrity: true
  max_section_tokens: 1200
```

---

## 3. Example 2: Software Project Documentation Library Profile

```yaml
library_id: core-software-docs
name: "Platform Engineering Docs"
root_dir: "./docs/platform"
goal: "Maintain production runbooks, API contracts, and disaster recovery procedures."
version: "1.0"
outcomes:
  - "Complete operational runbooks for Tier-1 services"
  - "Zero broken cross-references across architectural specifications"
permitted_paths:
  - "api"
  - "runbooks"
  - "architecture"
organization:
  - directory: "api"
    expected_doc_ids:
      - "authentication-v2"
      - "rate-limiting"
    description: "External API contract specifications."
  - directory: "runbooks"
    expected_doc_ids:
      - "incident-triage"
      - "database-failover"
    description: "Emergency incident response protocols."
permissions:
  allow_read: true
  allow_create: true
  allow_modify: true
  allow_delete: false
  allow_external_fetch: false
  require_approval_for_destructive: true
quality_rules:
  require_frontmatter: true
  required_frontmatter_keys: ["id", "title"]
  require_title_h1: true
  enforce_link_integrity: true
  max_section_tokens: 1500
```
