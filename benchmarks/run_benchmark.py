"""Reproducible Evaluation Benchmark for the Markdown Knowledge Retrieval System."""

from __future__ import annotations

import json
import math
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from knowledge_retrieval.api import KnowledgeEngine


# 1. Corpus Generator: 50 multi-domain technical documents
TOPICS = [
    ("raft_consensus", "Raft Distributed Consensus Algorithm", "consensus, distributed, fault-tolerance", [
        ("Leader Election", "In Raft, leader election is initiated when a follower's election timer expires. Candidates request votes via RequestVote RPC."),
        ("Log Replication", "The leader accepts log entries from clients and broadcasts AppendEntries RPCs to replicate them across the quorum."),
        ("Safety Invariants", "Raft ensures election safety, leader append-only, log matching, and state machine safety across split brains.")
    ]),
    ("lsm_trees", "Log-Structured Merge Trees Architecture", "storage, databases, lsm, sstable", [
        ("MemTable and WAL", "Writes are first appended to a Write-Ahead Log (WAL) and stored in an in-memory skip-list MemTable."),
        ("SSTable Compaction", "When the MemTable reaches size limits, it flushes immutable SSTables to disk. Leveled compaction merges overlapping key ranges."),
        ("Bloom Filters", "Bloom filters are placed on each SSTable to prevent expensive disk seeks for non-existent keys.")
    ]),
    ("b_trees", "B+ Tree Indexing in Relational Databases", "database, indexing, btree, sql", [
        ("Internal vs Leaf Nodes", "Internal nodes store routing keys while leaf nodes contain actual record pointers linked in a bidirectional chain."),
        ("Page Splitting", "When a node exceeds page capacity (typically 4KB or 8KB), it splits into two halves, propagating the median key upwards."),
        ("Concurrency and Latching", "Crabbing or lock-coupling protocols allow concurrent traversals down the tree while locking child nodes before releasing parents.")
    ]),
    ("vector_indexing", "HNSW Approximate Nearest Neighbor Search", "vectors, embeddings, hnsw, ai", [
        ("Hierarchical Graphs", "HNSW constructs multilayer skip-list graphs where upper layers have longer range links and layer 0 contains all points."),
        ("Greedy Routing", "Search begins at the top layer finding local minima before dropping to lower dense layers with beam search."),
        ("Distance Metrics", "Cosine distance and Euclidean L2 distance are commonly computed using SIMD instructions like AVX-512.")
    ]),
    ("token_bucket", "Token Bucket Rate Limiting Algorithm", "networking, traffic-shaping, security, api", [
        ("Capacity and Refill Rate", "Tokens are added to a bucket of capacity B at a constant refill rate R. Packets require T tokens to proceed."),
        ("Burst Handling", "Token buckets permit sudden traffic bursts up to the capacity limit, unlike leaky bucket algorithms."),
        ("Distributed Synchronization", "In distributed systems, Redis EVAL scripts with Lua provide atomic increment and time checks without race conditions.")
    ]),
    ("oauth2_pkce", "OAuth 2.0 PKCE Security Protocol", "security, auth, oauth, identity", [
        ("Code Verifier Generation", "The client generates a cryptographically random code_verifier between 43 and 128 characters long."),
        ("Code Challenge Calculation", "The client hashes the verifier with SHA-256 and base64url-encodes it as the code_challenge sent in the authorization request."),
        ("Token Exchange Verification", "During token exchange, the authorization server computes SHA256(code_verifier) and compares it with the stored challenge.")
    ]),
    ("cap_theorem", "CAP Theorem and PACELC Principles", "distributed-systems, theory, consistency, partition", [
        ("Consistency vs Availability", "Under a network partition (P), a distributed system must choose between consistency (C) or availability (A)."),
        ("PACELC Extension", "PACELC posits: if partition (P), choose A or C; else (E), choose Latency (L) or Consistency (C)."),
        ("Linearizability vs Eventual Consistency", "Linearizability guarantees real-time total order, whereas eventual consistency permits stale reads during replication.")
    ]),
    ("zero_trust", "Zero Trust Network Architecture Principles", "security, zero-trust, networking, iam", [
        ("Never Trust Always Verify", "Every network request is strictly authenticated, authorized, and encrypted before granting access, regardless of perimeter location."),
        ("Microsegmentation", "Workloads are partitioned into isolated network segments to prevent lateral movement of attackers."),
        ("Continuous Posture Assessment", "Device compliance and behavioral anomalies are evaluated dynamically during active sessions.")
    ]),
    ("event_sourcing", "Event Sourcing and CQRS Design Pattern", "architecture, patterns, events, cqrs", [
        ("Immutable Event Stream", "State changes are recorded as an append-only log of domain events rather than mutating records in-place."),
        ("Read Model Projections", "Projections asynchronously replay event streams into optimized query views (CQRS read side)."),
        ("Snapshotting Strategy", "To prevent replaying millions of historical events, snapshots are created periodically to establish baseline states.")
    ]),
    ("tls_handshake", "TLS 1.3 Cryptographic Handshake Protocol", "cryptography, security, tls, protocols", [
        ("1-RTT Key Exchange", "TLS 1.3 reduces the handshake to a single round-trip by combining client hello with Diffie-Hellman key shares."),
        ("0-RTT Early Data", "Clients resuming a previous session can transmit early application data, bearing replay risks."),
        ("Forward Secrecy", "Ephemeral Diffie-Hellman (ECDHE) keys ensure that compromise of the server private key does not decrypt past sessions.")
    ]),
]


def generate_benchmark_corpus(target_dir: str, target_count: int = 50) -> List[Dict[str, Any]]:
    """Generates synthetic multi-section markdown files and returns known benchmark query specs."""
    Path(target_dir).mkdir(parents=True, exist_ok=True)
    benchmark_queries: List[Dict[str, Any]] = []

    doc_index = 0
    while doc_index < target_count:
        base_topic = TOPICS[doc_index % len(TOPICS)]
        suffix = f"_{doc_index // len(TOPICS) + 1}" if doc_index >= len(TOPICS) else ""
        doc_id = f"{base_topic[0]}{suffix}"
        filename = f"{doc_id}.md"
        title = f"{base_topic[1]}{' Part ' + suffix.replace('_', '') if suffix else ''}"
        tags = base_topic[2]

        content = [
            "---",
            f"id: {doc_id}",
            f"title: \"{title}\"",
            f"tags: [{tags}]",
            "type: specification",
            "status: active",
            "---",
            "",
            f"# {title}",
            "",
            f"Official technical reference and architecture details for {title}.",
            ""
        ]

        for sec_heading, sec_body in base_topic[3]:
            content.append(f"## {sec_heading}")
            content.append(sec_body)
            content.append("")

        filepath = Path(target_dir) / filename
        filepath.write_text("\n".join(content), encoding="utf-8")

        # Create known-answer query for this document
        if doc_index < 20:
            target_sec = base_topic[3][0]
            query_text = f"{base_topic[1]} {target_sec[0]}"
            benchmark_queries.append({
                "query": query_text,
                "expected_doc_id": doc_id,
                "expected_section_heading": target_sec[0]
            })

        doc_index += 1

    return benchmark_queries


def run_benchmark():
    print("=" * 60)
    print("  Markdown Knowledge Retrieval System - Evaluation Benchmark")
    print("=" * 60)

    temp_dir = tempfile.mkdtemp(prefix="benchmark_kretrieval_")
    db_file = os.path.join(temp_dir, ".knowledge_index", "bench.db")

    try:
        # Step 1: Generate 50 representative markdown documents
        queries = generate_benchmark_corpus(temp_dir, target_count=50)
        print(f"[OK] Generated 50 benchmark documents in {temp_dir}")
        print(f"[OK] Formulated {len(queries)} known-answer evaluation queries\n")

        engine = KnowledgeEngine(root_dir=temp_dir, db_path=db_file)

        # Step 2: Measure Initial Indexing
        t0 = time.perf_counter()
        init_rep = engine.sync_index()
        t_init = time.perf_counter() - t0
        stats = engine.check_index_status()
        docs_per_sec = stats.total_documents / max(t_init, 0.0001)

        print(f"[BENCHMARK] Initial Indexing:")
        print(f"  - Total Documents:   {stats.total_documents}")
        print(f"  - Total Sections:    {stats.total_sections}")
        print(f"  - Total Tokens:      {stats.total_tokens:,}")
        print(f"  - Elapsed Time:      {t_init * 1000:.2f} ms ({docs_per_sec:.1f} docs/sec)")
        print(f"  - DB File Size:      {stats.index_db_size_bytes / 1024:.1f} KB\n")

        # Step 3: Measure Incremental Indexing (Modify 1 file)
        test_file = Path(temp_dir) / "raft_consensus.md"
        test_file.write_text(test_file.read_text(encoding="utf-8") + "\n\n## Leader Lease\nLeader leases provide local linearizable reads.", encoding="utf-8")
        
        t0 = time.perf_counter()
        inc_rep = engine.sync_index()
        t_inc = time.perf_counter() - t0

        print(f"[BENCHMARK] Incremental Indexing (1 file modified, 49 unchanged):")
        print(f"  - Added:     {len(inc_rep.added_files)}")
        print(f"  - Modified:  {len(inc_rep.modified_files)}")
        print(f"  - Unchanged: {len(inc_rep.unchanged_files)}")
        print(f"  - Elapsed:   {t_inc * 1000:.2f} ms\n")

        # Step 4: Search Quality & Latency Benchmark
        latencies_ms: List[float] = []
        reciprocal_ranks: List[float] = []
        hits_at_1 = 0
        hits_at_3 = 0
        total_context_tokens_list: List[int] = []

        for q in queries:
            t_start = time.perf_counter()
            results = engine.search_knowledge(q["query"], limit=5)
            lat_ms = (time.perf_counter() - t_start) * 1000.0
            latencies_ms.append(lat_ms)

            # Evaluate context assembly tokens
            ctx = engine.get_source_context(q["query"], token_budget=1000)
            total_context_tokens_list.append(ctx["total_tokens"])

            # Check ground truth match
            found_rank = 0
            for rank_idx, r in enumerate(results, start=1):
                if r["doc_id"] == q["expected_doc_id"]:
                    found_rank = rank_idx
                    break

            if found_rank == 1:
                hits_at_1 += 1
            if 1 <= found_rank <= 3:
                hits_at_3 += 1

            if found_rank > 0:
                reciprocal_ranks.append(1.0 / found_rank)
            else:
                reciprocal_ranks.append(0.0)

        latencies_ms.sort()
        p50 = latencies_ms[len(latencies_ms) // 2]
        p95 = latencies_ms[int(len(latencies_ms) * 0.95)]
        p99 = latencies_ms[int(len(latencies_ms) * 0.99)]
        mrr = sum(reciprocal_ranks) / len(reciprocal_ranks)
        p_at_1 = hits_at_1 / len(queries)
        p_at_3 = hits_at_3 / len(queries)
        avg_context_tokens = sum(total_context_tokens_list) / len(total_context_tokens_list)
        corpus_tokens = stats.total_tokens
        token_savings_ratio = (1.0 - (avg_context_tokens / corpus_tokens)) * 100.0

        print(f"[BENCHMARK] Retrieval Accuracy & Ranking:")
        print(f"  - Precision@1:          {p_at_1 * 100:.1f}%")
        print(f"  - Precision@3:          {p_at_3 * 100:.1f}%")
        print(f"  - Mean Reciprocal Rank: {mrr:.3f}")
        print(f"  - Query Latency p50:    {p50:.2f} ms")
        print(f"  - Query Latency p95:    {p95:.2f} ms")
        print(f"  - Query Latency p99:    {p99:.2f} ms\n")

        print(f"[BENCHMARK] Token Economy:")
        print(f"  - Total Corpus Tokens:      {corpus_tokens:,} tokens")
        print(f"  - Avg Retrieved Context:    {avg_context_tokens:.1f} tokens")
        print(f"  - Context Window Reduction: {token_savings_ratio:.2f}% (measured on 50 docs)\n")

        # Save Benchmark Results JSON
        results_data = {
            "corpus": {
                "total_documents": stats.total_documents,
                "total_sections": stats.total_sections,
                "total_tokens": corpus_tokens,
                "db_size_bytes": stats.index_db_size_bytes
            },
            "indexing": {
                "initial_indexing_ms": round(t_init * 1000, 2),
                "initial_docs_per_sec": round(docs_per_sec, 2),
                "incremental_indexing_ms": round(t_inc * 1000, 2)
            },
            "retrieval": {
                "queries_evaluated": len(queries),
                "precision_at_1": round(p_at_1, 4),
                "precision_at_3": round(p_at_3, 4),
                "mrr": round(mrr, 4),
                "latency_p50_ms": round(p50, 3),
                "latency_p95_ms": round(p95, 3),
                "latency_p99_ms": round(p99, 3)
            },
            "token_budgeting": {
                "avg_context_tokens": round(avg_context_tokens, 1),
                "corpus_tokens": corpus_tokens,
                "context_reduction_percent": round(token_savings_ratio, 2)
            }
        }

        output_file = Path("benchmarks") / "benchmark_results.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(results_data, indent=2), encoding="utf-8")
        print(f"[OK] Benchmark metrics successfully saved to {output_file}")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    run_benchmark()
