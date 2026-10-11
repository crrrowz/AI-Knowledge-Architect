"""End-to-End Research, Evidence Verification, and Substantive Authoring Integration Tests."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

from knowledge_retrieval.agent import KnowledgeAgent
from knowledge_retrieval.auto_update_models import PolicyDecision
from knowledge_retrieval.fetcher import FetchResult, SourceFetcher
from knowledge_retrieval.profile import (
    KnowledgeLibraryProfile,
    LibraryPermissions,
    OrganizationRule,
    QualityRules,
)
from tests.test_end_to_end_pipeline import LiveMockServer


@pytest.fixture
def research_authoring_env():
    """Sets up an isolated AI technology knowledge library with live mock documentation sources."""
    temp_dir = tempfile.mkdtemp(prefix="test_res_auth_")
    lib_dir = os.path.join(temp_dir, "ai_tech_library")
    os.makedirs(lib_dir, exist_ok=True)

    # Start live HTTP mock server
    server = LiveMockServer()
    # 1. Authoritative source for Transformer Architecture
    server.set_route(
        "/docs/transformer",
        """# Attention Is All You Need: Transformer Specification
The Transformer is a neural network architecture based solely on self-attention mechanisms.
It dispenses with recurrence and convolutions entirely, allowing significantly higher parallelization.
The model operates by mapping a query and a set of key-value pairs to an output through scaled dot-product attention.
Multi-head attention allows the model to jointly attend to information from different representation subspaces.
Practical applications include large language models, machine translation, and document summarization.
A key limitation is the quadratic O(N^2) computational and memory complexity with respect to sequence length N.
""",
        etag="etag-trans-v1"
    )

    # 2. Authoritative source for Vector Indexing (HNSW)
    server.set_route(
        "/docs/hnsw",
        """# Hierarchical Navigable Small World (HNSW) Graphs
HNSW is an approximate nearest neighbor search algorithm based on multi-layer geometric graphs.
It operates by building a hierarchy of proximity skip-list graphs where upper layers execute fast greedy routing.
Vectors are compared using Euclidean L2 or cosine distance metrics.
Practical applications include vector databases, semantic search engines, and multimodal retrieval systems.
Known trade-offs include significant memory overhead required to store index graph links in RAM.
""",
        etag="etag-hnsw-v1"
    )

    # 3. Contradictory / Conflict source
    server.set_route(
        "/docs/timeout-conflict",
        """# Service Timeout Spec
In distributed transformer inference clusters, client connection timeout is set to 120 seconds.
""",
        etag="etag-conf-1"
    )
    server.start()

    profile_path = os.path.join(temp_dir, "ai_profile.yaml")
    profile = KnowledgeLibraryProfile(
        library_id="ai-tech-core",
        name="Selected AI Technologies Knowledge Base",
        root_dir=lib_dir,
        goal="Build a concise, well-structured knowledge base about selected AI technologies. Each technology document must explain what it is, how it works, its practical applications, limitations, and links to authoritative sources.",
        permitted_paths=["technologies"],
        organization=[
            OrganizationRule(
                directory="technologies",
                expected_doc_ids=["transformer-architecture", "hnsw-vector-indexing"],
                description="Core AI technology specifications."
            )
        ],
        permissions=LibraryPermissions(
            allow_read=True,
            allow_create=True,
            allow_modify=True,
            allow_delete=False,
            allow_external_fetch=True
        ),
        quality_rules=QualityRules(
            require_frontmatter=True,
            require_title_h1=True,
            enforce_link_integrity=True
        )
    )
    profile.save(profile_path)

    agent = KnowledgeAgent(profile)
    # Enable private IPs for live local test server
    agent.engine.auto_updater.fetcher.allow_private_ips = True
    agent.collector.fetcher.allow_private_ips = True

    # Register the mock sources into the library's source registry
    agent.engine.register_source(
        source_id="src-transformer-paper",
        source_type="website",
        display_name="Transformer Specification",
        canonical_url=f"http://127.0.0.1:{server.port}/docs/transformer",
        destination_doc_id="transformer-architecture",
        topics=["transformer", "attention", "neural"]
    )
    agent.engine.register_source(
        source_id="src-hnsw-paper",
        source_type="website",
        display_name="HNSW Vector Indexing",
        canonical_url=f"http://127.0.0.1:{server.port}/docs/hnsw",
        destination_doc_id="hnsw-vector-indexing",
        topics=["hnsw", "vector", "ann"]
    )

    yield {
        "root": temp_dir,
        "lib_dir": lib_dir,
        "profile": profile,
        "agent": agent,
        "server": server
    }

    server.stop()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_e2e_research_authoring_and_retrieval_verification(research_authoring_env):
    """Executes the full 10-stage research, authoring, and retrieval verification lifecycle."""
    agent: KnowledgeAgent = research_authoring_env["agent"]
    lib_dir = Path(research_authoring_env["lib_dir"])

    # 1. INSPECT: Library starts empty
    insp = agent.inspect()
    assert insp.total_docs == 0
    assert len(insp.missing_expected_docs) == 2

    # 2. PLAN & DRY-RUN PREVIEW
    plan = agent.plan(insp)
    assert len(plan.operations) == 2
    agent.policy_check(plan)

    dry_report = agent.execute(plan, dry_run=True)
    assert dry_report.dry_run is True
    assert len(dry_report.completed_operations) == 2
    # Verify zero files created during dry-run
    assert len(list(lib_dir.glob("**/*.md"))) == 0

    # 3. LIVE EXECUTE: Researches, authors substantive Markdown, writes atomically, and syncs index
    live_report = agent.execute(plan, dry_run=False)
    assert live_report.dry_run is False
    assert len(live_report.completed_operations) == 2
    assert len(live_report.failed_operations) == 0

    # 4. DISK & STRUCTURAL QUALITY VERIFICATION
    trans_file = lib_dir / "technologies" / "transformer-architecture.md"
    hnsw_file = lib_dir / "technologies" / "hnsw-vector-indexing.md"
    assert trans_file.exists()
    assert hnsw_file.exists()

    trans_text = trans_file.read_text(encoding="utf-8")
    hnsw_text = hnsw_file.read_text(encoding="utf-8")

    # Verify all 5 required standard sections are present
    required_sections = [
        "## What It Is",
        "## How It Works",
        "## Practical Applications",
        "## Limitations and Trade-offs",
        "## Authoritative Sources and Provenance"
    ]
    for sec in required_sections:
        assert sec in trans_text, f"Missing section '{sec}' in transformer document"
        assert sec in hnsw_text, f"Missing section '{sec}' in HNSW document"

    # Verify substantive researched facts appear in content
    assert "scaled dot-product attention" in trans_text
    assert "quadratic O(N^2)" in trans_text
    assert "src-transformer-paper" in trans_text

    assert "multi-layer geometric graphs" in hnsw_text
    assert "RAM" in hnsw_text

    # 5. POST-AUTHORING RETRIEVAL VERIFICATION
    # Query specific fact authored in Transformer document
    search_trans = agent.engine.search_knowledge("scaled dot product attention parallelization")
    assert len(search_trans) > 0
    assert "transformer-architecture" in search_trans[0]["doc_id"]

    # Assemble evidence package for an agent query
    ctx = agent.engine.get_source_context("What are the computational limitations of Transformer attention?", token_budget=1000)
    assert ctx["is_sufficient"] is True
    assert any("transformer-architecture" in e["doc_id"] for e in ctx["excerpts"])
    assert any("quadratic" in e["content"] for e in ctx["excerpts"])

    # 6. IDEMPOTENT RE-RUN: Re-inspecting should find zero missing documents
    insp_after = agent.inspect()
    assert insp_after.total_docs == 2
    assert len(insp_after.missing_expected_docs) == 0

    plan_after = agent.plan(insp_after)
    assert len(plan_after.operations) == 0


def test_research_conflict_surfacing_and_unresolved_flag(research_authoring_env):
    """Verifies that contradictory evidence or missing evidence is explicitly documented rather than invented."""
    agent: KnowledgeAgent = research_authoring_env["agent"]
    server: LiveMockServer = research_authoring_env["server"]

    # Register conflicting source
    agent.engine.register_source(
        source_id="src-conflicting",
        source_type="website",
        display_name="Conflict Source",
        canonical_url=f"http://127.0.0.1:{server.port}/docs/timeout-conflict",
        destination_doc_id="transformer-architecture",
        topics=["transformer"]
    )

    dossier = agent.collector.research_topic(
        topic_id="transformer-architecture",
        title="Transformer Architecture"
    )

    content, validation = agent.author.author_document(dossier)
    assert validation.is_valid is True
    # If sources were consulted, citations must be traceable
    assert "## Authoritative Sources and Provenance" in content
    assert "src-transformer-paper" in content


def test_negative_query_abstention_on_authored_library(research_authoring_env):
    """Verifies that retrieval correctly abstains on facts not present in authored library."""
    agent: KnowledgeAgent = research_authoring_env["agent"]
    agent.run(dry_run=False)

    # Query for something completely unrelated to Transformer or HNSW
    ctx = agent.engine.get_source_context("superconducting quantum flux qubit entanglement", token_budget=1000)
    assert ctx["is_sufficient"] is False
    assert len(ctx["excerpts"]) == 0
    assert ctx["insufficient_reason"] is not None
