# Markdown Knowledge Document Schema Specification (KDS-v1)

## 1. Overview
This specification defines the structural conventions, frontmatter schemas, cross-referencing syntax, and validation rules for Markdown files managed by the Knowledge Retrieval System.

## 2. Document Structure

A valid knowledge document consists of:
1. **Optional YAML Frontmatter:** Delimited by `---` at the beginning of the file.
2. **Top-Level Heading (`# Title`):** The primary title of the document.
3. **Structured Sub-Headings (`##`, `###`, etc.):** Logical divisions forming addressable sections.

```markdown
---
id: doc-arch-overview
title: Architecture Overview
tags: [architecture, core, indexing]
type: specification
status: active
related:
  - doc-storage-engine
  - doc-retrieval-pipeline
---

# Architecture Overview

General introduction and system overview.

## Storage Engine
Details on the storage engine and data structures.

### SQLite FTS5 Schema
Schema definitions and indexing details.

## Retrieval Pipeline
Step-by-step query execution lifecycle.
```

## 3. Metadata Fields (YAML Frontmatter)

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `id` | string | Optional | Stable identifier (defaults to slugified relative path without extension). |
| `title` | string | Optional | Human-readable title (defaults to the first `# Heading` or file name). |
| `tags` | list of strings | Optional | Keywords and thematic labels for categorization. |
| `type` | string | Optional | e.g. `concept`, `guide`, `specification`, `reference`, `decision`. |
| `status` | string | Optional | e.g. `draft`, `active`, `deprecated`. |
| `related` | list of strings | Optional | Document IDs or relative paths to related documents. |

## 4. Cross-Referencing Syntax

The system supports two link formats:
1. **Standard Markdown Links:** `[Link Text](path/to/target.md)` or `[Link Text](path/to/target.md#section-heading)`.
2. **Obsidian-Style Wikilinks:** `[[target-document]]` or `[[target-document#section-heading|Label]]`.

## 5. Section Identification & Addressing
Sections are addressed deterministically via:
- `document_id`: The document identifier (or relative path).
- `section_id`: Slugified heading path (e.g., `architecture-overview#storage-engine#sqlite-fts5-schema`).
- Line Span: Exact `start_line` to `end_line` (1-indexed).

## 6. Integrity Rules & Diagnostics
The system audits:
- **Broken Links:** Target documents or section anchors that do not exist.
- **Duplicate Document IDs:** Multiple documents claiming identical explicit `id`s.
- **Orphaned Documents:** Documents with zero incoming and zero outgoing links.
- **Missing Headings:** Files lacking any Markdown headings.
- **Malformed Frontmatter:** Invalid YAML syntax.
