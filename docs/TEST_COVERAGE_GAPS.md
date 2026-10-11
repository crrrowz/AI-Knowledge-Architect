# Test Coverage Gaps & Risk Analysis

## 1. Overview
This document outlines uncovered failure modes, boundary risks, and edge conditions identified during the functional audit of `AI-Knowledge-Architect`.

---

## 2. Identified Coverage Gaps & Associated Risks

### Gap 1: High-Volume Concurrent Writes
- **Scenario:** Multiple background worker processes attempting simultaneous writes/syncs to SQLite database.
- **Current Behavior:** SQLite WAL mode handles concurrent readers and a single serialized writer with `timeout=30.0`.
- **Residual Risk:** If multiple independent indexing processes trigger `sync()` concurrently, SQLite raises `sqlite3.OperationalError: database is locked` if transactions exceed the 30-second timeout window.
- **Mitigation:** Recommended single-writer orchestration lock in process manager when running in distributed agent harnesses.

### Gap 2: Deeply Nested Headings and Heading Gaps
- **Scenario:** Markdown files with non-sequential heading levels (e.g. jumping from `# Title` directly to `#### Deep Subsection`).
- **Observed Behavior:** Current parser tracks `heading_level` literally. Section hierarchy is preserved linearly by line number.
- **Residual Risk:** Outline visualization reflects literal levels without hierarchical normalization.

### Gap 3: Extremely Large Sections Exceeding Context Budget
- **Scenario:** A single Markdown section with >10,000 words (exceeding typical context budget).
- **Observed Behavior:** `ContextAssembler` detects if the section exceeds budget and cleanly truncates with a notice (`... [Truncated due to token budget]`).
- **Residual Risk:** Truncation at a character boundary rather than a paragraph/sentence boundary.

### Gap 4: Case-Insensitive vs Case-Preserving Cross-References
- **Scenario:** Wikilinks pointing to `[[Architecture-Overview]]` while file is named `architecture-overview.md`.
- **Observed Behavior:** File system checks on Windows (case-insensitive) pass, but on Linux/macOS case-sensitive filesystems, exact case mismatches may occur.
- **Mitigation:** Added normalized lowercase comparisons in `integrity.py`.
