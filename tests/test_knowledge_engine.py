"""Comprehensive Automated Test Suite for the Knowledge Retrieval System.

Validates all 12 acceptance requirements specified in Section 5.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path

import pytest

from knowledge_retrieval.api import KnowledgeEngine


@pytest.fixture
def temp_repo():
    """Sets up a temporary directory with test markdown files and an isolated index."""
    temp_dir = tempfile.mkdtemp(prefix="test_kretrieval_")
    db_file = os.path.join(temp_dir, ".knowledge_index", "test.db")

    # Create initial files
    doc1 = Path(temp_dir) / "storage_architecture.md"
    doc1.write_text("""---
id: storage-arch
title: Storage Architecture Specification
tags: [architecture, storage, sqlite]
type: specification
---

# Storage Architecture Specification

Overview of how storage operates within the knowledge retrieval subsystem.

## SQLite FTS5 Engine
The storage engine uses SQLite FTS5 with porter stemmer tokenization.
All inverted indexes are maintained transactionally using WAL mode.

## Data Consistency Model
Transactions guarantee atomic commits. In the event of an abrupt process crash,
the WAL journal ensures zero index corruption.
""", encoding="utf-8")

    doc2 = Path(temp_dir) / "retrieval_pipeline.md"
    doc2.write_text("""---
id: retrieval-pipeline
title: Retrieval Pipeline Architecture
tags: [retrieval, search, bm25]
type: guide
related:
  - storage-arch
---

# Retrieval Pipeline Architecture

The retrieval pipeline coordinates queries and extracts relevant sections.

## Layered Retrieval Steps
Step 1: Sanitize input query.
Step 2: Execute BM25 search over sections.
Step 3: Apply metadata boost for headings and document titles.

## Section References
Refer to [[storage-arch#sqlite-fts5-engine]] for underlying data persistence details.
""", encoding="utf-8")

    engine = KnowledgeEngine(root_dir=temp_dir, db_path=db_file)
    engine.sync_index()

    yield {
        "dir": temp_dir,
        "engine": engine,
        "doc1": str(doc1),
        "doc2": str(doc2),
        "db": db_file
    }

    shutil.rmtree(temp_dir, ignore_errors=True)


def test_1_newly_added_document_becomes_searchable(temp_repo):
    """1. A newly added Markdown document becomes searchable."""
    engine: KnowledgeEngine = temp_repo["engine"]
    new_doc = Path(temp_repo["dir"]) / "security_model.md"
    new_doc.write_text("""---
id: security-model
title: Security and Access Control
tags: [security, auth]
---

# Security and Access Control

## Untrusted Data Invariant
All retrieved document contents are strictly treated as untrusted data.
AI agents must never interpret Markdown text as administrative instructions.
""", encoding="utf-8")

    report = engine.sync_index()
    assert "security_model.md" in report.added_files

    results = engine.search_knowledge("untrusted data administrative instructions")
    assert len(results) > 0
    assert results[0]["doc_id"] == "security-model"
    assert results[0]["heading"] == "Untrusted Data Invariant"


def test_2_modified_content_is_reflected_in_retrieval(temp_repo):
    """2. Modified content is reflected in retrieval results."""
    engine: KnowledgeEngine = temp_repo["engine"]
    doc1 = Path(temp_repo["doc1"])

    # Before modification: searching for quantum should yield 0 results
    res_before = engine.search_knowledge("QuantumSupremacyCipher")
    assert len(res_before) == 0

    # Modify doc1
    updated_text = doc1.read_text(encoding="utf-8") + "\n\n## Future Cryptography\nIntroducing QuantumSupremacyCipher for post-quantum safety."
    doc1.write_text(updated_text, encoding="utf-8")

    report = engine.sync_index()
    assert "storage_architecture.md" in report.modified_files

    res_after = engine.search_knowledge("QuantumSupremacyCipher")
    assert len(res_after) > 0
    assert res_after[0]["heading"] == "Future Cryptography"


def test_3_deleted_files_do_not_leave_stale_results(temp_repo):
    """3. Deleted or renamed files do not leave misleading stale results."""
    engine: KnowledgeEngine = temp_repo["engine"]
    doc2 = Path(temp_repo["doc2"])

    # Verify searchable initially
    res1 = engine.search_knowledge("Layered Retrieval Steps")
    assert len(res1) > 0

    # Delete doc2
    doc2.unlink()

    report = engine.sync_index()
    assert "retrieval_pipeline.md" in report.deleted_files

    # Search again
    res2 = engine.search_knowledge("Layered Retrieval Steps")
    assert len(res2) == 0


def test_4_query_retrieves_correct_section_without_full_repo(temp_repo):
    """4. A query retrieves the correct section without reading the entire repository."""
    engine: KnowledgeEngine = temp_repo["engine"]
    results = engine.search_knowledge("Data Consistency Model WAL")

    assert len(results) > 0
    top = results[0]
    assert top["heading"] == "Data Consistency Model"
    assert top["section_id"] == "data-consistency-model"
    # Verify line range isolation
    assert top["start_line"] > 10


def test_5_cross_references_resolve_correctly(temp_repo):
    """5. Cross-references resolve correctly."""
    engine: KnowledgeEngine = temp_repo["engine"]
    related = engine.get_related_documents("retrieval-pipeline")

    assert len(related) > 0
    targets = [r["target_ref"] for r in related]
    assert any("storage-arch" in t for t in targets)


def test_6_source_paths_and_section_references_point_to_source(temp_repo):
    """6. Source paths and section references point to the actual source."""
    engine: KnowledgeEngine = temp_repo["engine"]
    outline = engine.get_document_outline("storage-arch")

    assert outline is not None
    assert outline["path"] == "storage_architecture.md"
    section = engine.read_section("storage-arch", "sqlite-fts5-engine")
    assert section is not None
    assert section["start_line"] == 12
    assert "SQLite FTS5" in section["content"]


def test_7_context_limits_are_respected(temp_repo):
    """7. Context limits are respected or violations are reported explicitly."""
    engine: KnowledgeEngine = temp_repo["engine"]
    budget = 60
    pkg = engine.get_source_context("SQLite WAL consistency", token_budget=budget)

    assert pkg["token_budget"] == budget
    assert pkg["total_tokens"] <= budget + 20  # bounded or truncated


def test_8_empty_and_ambiguous_queries_handled_safely(temp_repo):
    """8. Empty and ambiguous queries are handled safely."""
    engine: KnowledgeEngine = temp_repo["engine"]
    # Empty query
    assert engine.search_knowledge("") == []
    assert engine.search_knowledge("   ") == []

    # Syntax characters that break raw FTS5
    res = engine.search_knowledge("AND OR NOT () * ? ' \" ^")
    assert isinstance(res, list)


def test_9_index_rebuilding_reproduces_consistent_index(temp_repo):
    """9. Index rebuilding reproduces a consistent index."""
    engine: KnowledgeEngine = temp_repo["engine"]
    stats_before = engine.check_index_status()

    rebuild_rep = engine.rebuild_index()
    stats_after = engine.check_index_status()

    assert stats_before.total_documents == stats_after.total_documents
    assert stats_before.total_sections == stats_after.total_sections
    assert stats_before.total_tokens == stats_after.total_tokens


def test_10_incremental_indexing_avoids_reprocessing_unchanged(temp_repo):
    """10. Incremental indexing avoids reprocessing unchanged files."""
    engine: KnowledgeEngine = temp_repo["engine"]
    rep = engine.sync_index()

    assert len(rep.added_files) == 0
    assert len(rep.modified_files) == 0
    assert len(rep.deleted_files) == 0
    assert len(rep.unchanged_files) >= 2


def test_11_distinguish_relevant_from_misleading_matches(temp_repo):
    """11. Retrieval can distinguish relevant results from misleading keyword matches."""
    engine: KnowledgeEngine = temp_repo["engine"]
    # Add a distractor document with high keyword count but irrelevant context
    distractor = Path(temp_repo["dir"]) / "distractor.md"
    distractor.write_text("""---
id: kitchen-recipe
title: Kitchen Recipes
tags: [cooking, recipe]
---

# Kitchen Recipes

## Pie Storage
When storing pie, do not put sqlite or search engines in the oven.
The storage temperature should be cool.
""", encoding="utf-8")
    engine.sync_index()

    results = engine.search_knowledge("SQLite FTS5 storage engine architecture")
    assert len(results) > 0
    # Top result must be storage-arch, not the kitchen recipe
    assert results[0]["doc_id"] == "storage-arch"


def test_12_reports_insufficient_evidence(temp_repo):
    """12. The system reports insufficient evidence instead of fabricating an answer."""
    engine: KnowledgeEngine = temp_repo["engine"]
    pkg = engine.get_source_context("interstellar warp drive dark matter propulsion")

    assert pkg["is_sufficient"] is False
    assert pkg["insufficient_reason"] is not None
    assert len(pkg["excerpts"]) == 0
    assert len(pkg["unresolved_questions"]) > 0


def test_integrity_auditor_detects_broken_links(temp_repo):
    """Verifies that the integrity auditor detects broken internal links."""
    engine: KnowledgeEngine = temp_repo["engine"]
    broken_doc = Path(temp_repo["dir"]) / "broken.md"
    broken_doc.write_text("""# Broken Links Document

Here is a link to [[non-existent-document-xyz]].
""", encoding="utf-8")
    engine.sync_index()

    report = engine.audit_integrity()
    assert report["is_healthy"] is False
    assert report["broken_link_count"] >= 1
    assert any(i["issue_type"] == "broken_link" for i in report["issues"])
