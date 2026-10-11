"""Independent Functional Audit Test Suite for AI-Knowledge-Architect.

Designed to independently stress-test realistic failure modes, natural language queries,
punctuation/technical terms, multilingual/Arabic support, broken section anchors,
token budget precision, and multi-document / conflicting evidence.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

from knowledge_retrieval.api import KnowledgeEngine


@pytest.fixture
def audit_repo():
    """Isolated temporary repository for independent audit tests."""
    temp_dir = tempfile.mkdtemp(prefix="audit_independent_")
    db_file = os.path.join(temp_dir, ".knowledge_index", "audit.db")

    # Document 1: English consensus and networking
    (Path(temp_dir) / "network_spec.md").write_text("""---
id: net-spec
title: Network Configuration Specification
tags: [networking, timeout, zero-trust]
---

# Network Configuration Specification

## Timeout Settings
The client connection timeout is strictly set to 30 seconds.
Retries are attempted with exponential backoff up to 3 times.

## Zero-Trust Architecture
All ingress traffic must pass through the zero-trust gateway.
Mutual TLS with ECDHE is mandatory.
""", encoding="utf-8")

    # Document 2: Conflicting network config in a legacy document
    (Path(temp_dir) / "legacy_net.md").write_text("""---
id: legacy-net
title: Legacy Network Guidelines
tags: [networking, legacy, timeout]
---

# Legacy Network Guidelines

## Timeout Settings
The client connection timeout is configured to 60 seconds for legacy services.
Do not decrease this timeout without consulting the infrastructure team.
""", encoding="utf-8")

    # Document 3: Multilingual (Arabic) document
    (Path(temp_dir) / "arabic_architecture.md").write_text("""---
id: ar-arch
title: بنية النظام السحابي
tags: [معمارية, سحابية, تخزين]
---

# بنية النظام السحابي

## محرك التخزين الموزع
يعتمد محرك التخزين الموزع على هيكلية الحزام الناقل لتسريع معالجة البيانات الضخمة.
زمن الاستجابة المستهدف هو أقل من 5 ميلي ثانية.

## الأمان والتشفير
يتم تشفير كافة البيانات المخزنة باستخدام معيار AES-256 بشكل افتراضي.
""", encoding="utf-8")

    # Document 4: Document with valid and invalid section anchors
    (Path(temp_dir) / "linking_hub.md").write_text("""---
id: link-hub
title: System Linking Hub
tags: [links, hub]
---

# System Linking Hub

## References
Valid document link: [[net-spec]].
Valid section link: [[net-spec#timeout-settings]].
Broken section link: [[net-spec#non-existent-anchor-xyz]].
Broken doc link: [[completely-missing-doc]].
""", encoding="utf-8")

    engine = KnowledgeEngine(root_dir=temp_dir, db_path=db_file)
    engine.sync_index()

    yield {
        "dir": temp_dir,
        "engine": engine,
        "db": db_file
    }

    shutil.rmtree(temp_dir, ignore_errors=True)


# ==============================================================================
# AUDIT CASE 1: Natural Language Queries with Conversational & Stop Words
# ==============================================================================

def test_audit_natural_language_query_with_stop_words(audit_repo):
    """Verifies retrieval when user queries include natural conversational words (what, is, the, for)."""
    engine: KnowledgeEngine = audit_repo["engine"]
    # Query contains 'What', 'is', 'the', 'for' which may not appear in the text
    results = engine.search_knowledge("What is the client connection timeout for services?")
    assert len(results) > 0, "Query with conversational stop words failed to return any results"
    headings = [r["heading"] for r in results]
    assert "Timeout Settings" in headings


def test_audit_hyphenated_and_technical_terms(audit_repo):
    """Verifies retrieval for technical punctuation like 'zero-trust', 'AES-256', 'ECDHE'."""
    engine: KnowledgeEngine = audit_repo["engine"]
    results = engine.search_knowledge("zero-trust gateway mutual TLS")
    assert len(results) > 0, "Failed to retrieve document with hyphenated technical term 'zero-trust'"
    assert results[0]["heading"] == "Zero-Trust Architecture"


# ==============================================================================
# AUDIT CASE 2: Multi-Document Retrieval and Conflicting Evidence
# ==============================================================================

def test_audit_conflicting_evidence_exposure(audit_repo):
    """Verifies that queries over conflicting topics return evidence from BOTH documents."""
    engine: KnowledgeEngine = audit_repo["engine"]
    results = engine.search_knowledge("connection timeout settings", limit=5)
    matched_doc_ids = {r["doc_id"] for r in results}
    # Both net-spec (30s) and legacy-net (60s) must be surfaced so the agent can see both
    assert "net-spec" in matched_doc_ids, "Failed to retrieve primary network spec"
    assert "legacy-net" in matched_doc_ids, "Failed to retrieve conflicting legacy spec"


def test_audit_context_assembly_surfaces_conflicting_excerpts(audit_repo):
    """Verifies that the context package includes both conflicting viewpoints."""
    engine: KnowledgeEngine = audit_repo["engine"]
    pkg = engine.get_source_context("connection timeout settings", token_budget=1000)
    assert pkg["is_sufficient"] is True
    doc_paths = [e["path"] for e in pkg["excerpts"]]
    assert any("network_spec.md" in p for p in doc_paths)
    assert any("legacy_net.md" in p for p in doc_paths)


# ==============================================================================
# AUDIT CASE 3: Multilingual & Arabic Query Support
# ==============================================================================

def test_audit_arabic_search_and_outline(audit_repo):
    """Verifies that Arabic documents can be searched and their outlines extracted."""
    engine: KnowledgeEngine = audit_repo["engine"]
    results = engine.search_knowledge("محرك التخزين الموزع")
    assert len(results) > 0, "Failed to retrieve Arabic document by heading"
    assert results[0]["doc_id"] == "ar-arch"

    outline = engine.get_document_outline("ar-arch")
    assert outline is not None
    assert len(outline["sections"]) >= 2


# ==============================================================================
# AUDIT CASE 4: Broken Section Anchor Detection in Integrity Audit
# ==============================================================================

def test_audit_detects_broken_section_anchors(audit_repo):
    """Verifies that [[doc#invalid-anchor]] is flagged as a broken link."""
    engine: KnowledgeEngine = audit_repo["engine"]
    report = engine.audit_integrity()

    # Must detect both broken doc and broken section anchor
    broken_targets = [i["details"].get("target_ref", "") for i in report["issues"] if i["issue_type"] == "broken_link"]
    assert any("completely-missing-doc" in t for t in broken_targets), "Failed to detect missing doc link"
    assert any("net-spec#non-existent-anchor-xyz" in t for t in broken_targets), "Failed to detect broken section anchor"


# ==============================================================================
# AUDIT CASE 5: Duplicate Document ID Collision Detection
# ==============================================================================

def test_audit_duplicate_doc_id_collision_handling(audit_repo):
    """Verifies that two different files claiming the same frontmatter ID trigger an error."""
    engine: KnowledgeEngine = audit_repo["engine"]
    temp_dir = audit_repo["dir"]

    # Add duplicate doc with id 'net-spec'
    (Path(temp_dir) / "duplicate_spec.md").write_text("""---
id: net-spec
title: Duplicate Network Specification
---

# Duplicate Network Specification
Some conflicting content.
""", encoding="utf-8")

    engine.sync_index()
    report = engine.audit_integrity()
    assert report["duplicate_count"] >= 1, "Auditor failed to detect duplicate document ID"


# ==============================================================================
# AUDIT CASE 6: Strict Token Budgeting (No Silent Budget Overflow)
# ==============================================================================

def test_audit_strict_token_budget_enforcement(audit_repo):
    """Verifies that context assembler never exceeds the allocated token budget."""
    engine: KnowledgeEngine = audit_repo["engine"]
    budget = 120
    pkg = engine.get_source_context("connection timeout settings", token_budget=budget)
    assert pkg["total_tokens"] <= budget, f"Token count {pkg['total_tokens']} exceeded budget {budget}"


# ==============================================================================
# AUDIT CASE 7: Missing Information Reporting (No Hallucination)
# ==============================================================================

def test_audit_missing_information_abstention(audit_repo):
    """Verifies that unindexed concepts clearly flag insufficient evidence."""
    engine: KnowledgeEngine = audit_repo["engine"]
    pkg = engine.get_source_context("quantum entanglement teleportation bus protocol")
    assert pkg["is_sufficient"] is False
    assert pkg["total_tokens"] == 0
    assert len(pkg["excerpts"]) == 0
    assert pkg["insufficient_reason"] is not None
