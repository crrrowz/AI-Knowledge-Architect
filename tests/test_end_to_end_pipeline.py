"""End-to-End Reliability and Security Integration Test Suite for AI-Knowledge-Architect."""

from __future__ import annotations

import http.server
import os
import shutil
import tempfile
import threading
import time
from pathlib import Path

import pytest

from knowledge_retrieval.api import KnowledgeEngine
from knowledge_retrieval.auto_update_models import (
    CandidateStatus,
    ChangeCandidate,
    ChangeType,
    PolicyDecision,
    RiskLevel,
    SourceType,
    TrustTier,
)
from knowledge_retrieval.fetcher import FetchResult, SourceFetcher, validate_url_safety


class LiveMockServer:
    """Threaded HTTP server providing realistic HTTP endpoints, ETags, and 304s."""

    def __init__(self):
        self.host = "127.0.0.1"
        self.port = 0
        self.server = None
        self.thread = None
        self.routes = {}

    def set_route(self, path: str, content: str, etag: str = "etag-v1", status_code: int = 200):
        self.routes[path] = {"content": content, "etag": etag, "status_code": status_code}

    def start(self):
        routes = self.routes

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                # Check route
                clean_path = self.path.split("?")[0]
                if clean_path in routes:
                    route_info = routes[clean_path]
                    client_etag = self.headers.get("If-None-Match")
                    if client_etag and client_etag == route_info["etag"]:
                        self.send_response(304)
                        self.end_headers()
                        return

                    body_bytes = route_info["content"].encode("utf-8")
                    self.send_response(route_info["status_code"])
                    self.send_header("Content-Type", "text/markdown; charset=utf-8")
                    self.send_header("ETag", route_info["etag"])
                    self.send_header("Content-Length", str(len(body_bytes)))
                    self.end_headers()
                    self.wfile.write(body_bytes)
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, format, *args):
                pass  # Silence server logs during tests

        self.server = http.server.HTTPServer((self.host, 0), Handler)
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()


@pytest.fixture
def e2e_env():
    """Sets up an end-to-end integration environment with a live mock HTTP server."""
    temp_dir = tempfile.mkdtemp(prefix="test_e2e_")
    db_file = os.path.join(temp_dir, ".knowledge_index", "e2e.db")

    server = LiveMockServer()
    server.set_route(
        "/docs/fts5",
        "# SQLite FTS5 Specification\n\n## Overview\nSQLite FTS5 provides fast full-text indexing.\nConnection timeout is strictly set to 30 seconds.\n",
        etag="etag-init"
    )
    server.start()

    # Initial target document
    init_doc = Path(temp_dir) / "sqlite_guide.md"
    init_doc.write_text("""---
id: sqlite-guide
title: SQLite Guide
tags: [database, sqlite]
---

# SQLite Guide

## Core Concepts
SQLite is an embedded relational database engine.
Connection timeout is strictly set to 30 seconds.
""", encoding="utf-8")

    engine = KnowledgeEngine(root_dir=temp_dir, db_path=db_file)
    # Enable private IPs specifically for the controlled local test server
    engine.auto_updater.fetcher.allow_private_ips = True
    engine.sync_index()

    yield {
        "dir": temp_dir,
        "engine": engine,
        "server": server,
        "doc_path": str(init_doc),
        "db": db_file
    }

    server.stop()
    shutil.rmtree(temp_dir, ignore_errors=True)


# ==============================================================================
# SECTION 1: Complete 10-Step Update Lifecycle & Review Lifecycle
# ==============================================================================

def test_complete_10_step_update_lifecycle(e2e_env):
    """Executes the complete 10-step lifecycle from registration to retrieval and idempotency."""
    engine: KnowledgeEngine = e2e_env["engine"]
    server: LiveMockServer = e2e_env["server"]
    doc_path = Path(e2e_env["doc_path"])

    url = f"http://127.0.0.1:{server.port}/docs/fts5"

    # Step 1: Register official documentation source
    reg = engine.register_source(
        source_id="src-sqlite-official",
        source_type="website",
        display_name="Official SQLite Documentation",
        canonical_url=url,
        destination_doc_id="sqlite-guide",
        topics=["sqlite", "fts5"],
        trust_tier="official"
    )
    assert reg["status"] == "registered"

    # Step 2: Fetch and index initial content
    res_init = engine.check_updates("src-sqlite-official")
    assert res_init["action_taken"] == "AUTO_APPLIED"

    # Step 3: Modify source content on the live server
    server.set_route(
        "/docs/fts5",
        "## BM25 Enhancements\nNew BM25 ranking algorithm introduced in version 3.50 with SIMD acceleration.",
        etag="etag-v2"
    )

    # Step 4: Run update discovery
    # Step 5: Verify source evidence and policy decision
    # Step 6: Apply safe, low-risk update
    res_update = engine.check_updates("src-sqlite-official")
    assert res_update["change_type"] == "DOC_UPDATED"
    assert res_update["policy_decision"] == "AUTO_APPLY"
    assert res_update["action_taken"] == "AUTO_APPLIED"

    # Step 7: Confirm Markdown file contains correct change and provenance
    doc_text = doc_path.read_text(encoding="utf-8")
    assert "BM25 Enhancements" in doc_text
    assert "auto-update-provenance" in doc_text

    # Step 8: Confirm search index is synchronized
    stats = engine.check_index_status()
    assert stats.total_documents >= 1

    # Step 9: Search for newly introduced fact and verify source evidence retrievability
    search_results = engine.search_knowledge("SIMD acceleration BM25 ranking")
    assert len(search_results) > 0
    assert "BM25 Enhancements" in search_results[0]["heading"]

    # Step 10: Run updater again and verify idempotency (304 Not Modified)
    res_idempotent = engine.check_updates("src-sqlite-official")
    assert res_idempotent["change_type"] == "NO_CHANGE"
    # Ensure no duplicate history records created
    history = engine.list_update_history()
    assert len(history) == 2  # initial + 1 update


def test_review_lifecycle_conflict_rejection_and_stale_approval(e2e_env):
    """Verifies review lifecycle: conflict queueing, reviewer rejection, and stale approval blocking."""
    engine: KnowledgeEngine = e2e_env["engine"]
    server: LiveMockServer = e2e_env["server"]
    doc_path = Path(e2e_env["doc_path"])

    url = f"http://127.0.0.1:{server.port}/docs/fts5"
    engine.register_source(
        source_id="src-sqlite-conflict",
        source_type="website",
        display_name="Conflict Source",
        canonical_url=url,
        destination_doc_id="sqlite-guide",
        topics=["sqlite"]
    )

    # 1. Conflicting update: timeout set to 999 seconds (conflicts with 30s)
    server.set_route(
        "/docs/fts5",
        "## Timeout Update\nConnection timeout is strictly set to 999 seconds.",
        etag="etag-conflict-1"
    )

    chk = engine.check_updates("src-sqlite-conflict")
    assert chk["action_taken"] == "QUEUED_FOR_REVIEW"
    assert chk["policy_decision"] == "REVIEW_REQUIRED"

    # Canonical markdown file must remain UNCHANGED
    doc_before = doc_path.read_text(encoding="utf-8")
    assert "999 seconds" not in doc_before

    # 2. Reviewer rejects the candidate
    cid = chk["candidate_id"]
    rej_res = engine.reject_update(cid, note="Rejected due to invalid timeout parameter")
    assert rej_res["status"] == "REJECTED"
    assert "999 seconds" not in doc_path.read_text(encoding="utf-8")

    # 3. Test Stale Approval Protection
    # Create candidate A, but source changes to version B before reviewer approves A
    server.set_route("/docs/fts5", "## Breaking API\nWARNING: breaking changes in API.", etag="etag-break")
    chk2 = engine.check_updates("src-sqlite-conflict")
    cid2 = chk2["candidate_id"]
    assert chk2["action_taken"] == "QUEUED_FOR_REVIEW"

    # Now source advances to a newer version on server
    server.set_route("/docs/fts5", "## Newer Stable\nStable release v4.0.", etag="etag-newer")
    engine.check_updates("src-sqlite-conflict")

    # Now attempt to approve candidate A (cid2)
    stale_appr = engine.approve_update(cid2, note="Belated approval attempt")
    assert stale_appr["status"] == "STALE_REJECTED"
    assert "Stale Approval Blocked" in stale_appr["error"]


# ==============================================================================
# SECTION 2: Failure Recovery and Data Integrity
# ==============================================================================

def test_failure_recovery_source_timeout_and_unreachable(e2e_env):
    """Verifies that network timeout or 404 does not delete or corrupt existing knowledge."""
    engine: KnowledgeEngine = e2e_env["engine"]
    doc_path = Path(e2e_env["doc_path"])
    content_before = doc_path.read_text(encoding="utf-8")

    # Point to an inaccessible port
    engine.register_source(
        source_id="src-unreachable",
        source_type="website",
        display_name="Dead Server",
        canonical_url="http://127.0.0.1:59999/nonexistent",
        destination_doc_id="sqlite-guide"
    )

    res = engine.check_updates("src-unreachable")
    assert res["change_type"] == "UNREACHABLE"
    assert res["error"] is not None

    # Knowledge must not be deleted or modified
    content_after = doc_path.read_text(encoding="utf-8")
    assert content_before == content_after


def test_failure_recovery_malformed_and_empty_content(e2e_env):
    """Verifies that an empty web page is rejected rather than overwriting documents."""
    engine: KnowledgeEngine = e2e_env["engine"]
    server: LiveMockServer = e2e_env["server"]

    server.set_route("/docs/empty", "    \n   \n   ", etag="etag-empty")
    engine.register_source(
        source_id="src-empty",
        source_type="website",
        display_name="Empty Page",
        canonical_url=f"http://127.0.0.1:{server.port}/docs/empty",
        destination_doc_id="sqlite-guide"
    )

    res = engine.check_updates("src-empty")
    assert res["action_taken"] == "REJECTED"
    assert "empty or malformed" in res["rationale"].lower()


# ==============================================================================
# SECTION 3: Security & SSRF Audit Tests
# ==============================================================================

def test_security_ssrf_protection_loopback_and_private_ips():
    """Verifies that validate_url_safety blocks SSRF attempts."""
    # Loopback targets
    safe, msg = validate_url_safety("http://127.0.0.1/admin")
    assert safe is False
    assert "loopback" in msg.lower()

    safe, msg = validate_url_safety("http://localhost:8080/secret")
    assert safe is False

    # Link-local cloud metadata service (AWS/GCP/Azure: 169.254.169.254)
    safe, msg = validate_url_safety("http://169.254.169.254/latest/meta-data/")
    assert safe is False

    # Private network ranges (10.0.0.1, 192.168.1.1)
    safe, msg = validate_url_safety("http://192.168.1.1/router")
    assert safe is False

    # Prohibited scheme (file://, ftp://, gopher://)
    safe, msg = validate_url_safety("file:///etc/passwd")
    assert safe is False
    assert "prohibited url scheme" in msg.lower()


def test_security_path_traversal_prevention(e2e_env):
    """Verifies that candidate destination IDs with path traversal (../../) are blocked."""
    engine: KnowledgeEngine = e2e_env["engine"]
    cand = ChangeCandidate(
        candidate_id="cand-traversal",
        source_id="src-fake",
        observed_at=time.time(),
        source_published_at=None,
        prev_fingerprint=None,
        curr_fingerprint="fp-traversal",
        change_type=ChangeType.DOC_UPDATED,
        change_summary="Exploit attempt",
        raw_content="Malicious payload",
        normalized_content="Malicious payload",
        affected_doc_ids=["../../escaped_target"],
        affected_topics=["security"],
        evidence={},
        risk_level=RiskLevel.LOW,
        policy_decision=PolicyDecision.AUTO_APPLY,
        decision_rationale="Test"
    )

    ok, msg = engine.auto_updater.updater.apply_candidate(cand)
    assert ok is False
    assert "Security Violation" in msg or "escapes" in msg
