"""Command Line Interface for the Knowledge Retrieval System."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from knowledge_retrieval.api import KnowledgeEngine


def main():
    parser = argparse.ArgumentParser(
        prog="knowledge-cli",
        description="High-Efficiency Local Markdown Knowledge Retrieval System"
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Root directory of Markdown knowledge base (default: current directory)"
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Path to SQLite index file (default: <root>/.knowledge_index/index.db)"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # sync / index
    sync_p = subparsers.add_parser("sync", help="Incrementally index markdown files")
    sync_p.add_argument("--rebuild", action="store_true", help="Force clean rebuild from scratch")

    # status
    subparsers.add_parser("status", help="Display index statistics")

    # search
    search_p = subparsers.add_parser("search", help="Perform section-level BM25 search")
    search_p.add_argument("query", help="Search query string")
    search_p.add_argument("--limit", type=int, default=5, help="Maximum number of results")
    search_p.add_argument("--tags", default=None, help="Comma-separated tags to filter by")
    search_p.add_argument("--json", action="store_true", help="Output raw JSON results")

    # outline
    outline_p = subparsers.add_parser("outline", help="Get structural outline of a document")
    outline_p.add_argument("document_id", help="Document ID or relative path")
    outline_p.add_argument("--json", action="store_true", help="Output raw JSON")

    # section
    sec_p = subparsers.add_parser("section", help="Read exact content of a section")
    sec_p.add_argument("document_id", help="Document ID or relative path")
    sec_p.add_argument("section_id", help="Section ID or slug")
    sec_p.add_argument("--json", action="store_true", help="Output raw JSON")

    # context
    ctx_p = subparsers.add_parser("context", help="Assemble token-budgeted evidence context package")
    ctx_p.add_argument("query", help="User question or query")
    ctx_p.add_argument("--budget", type=int, default=1500, help="Maximum token budget")
    ctx_p.add_argument("--json", action="store_true", help="Output raw JSON")

    # related
    rel_p = subparsers.add_parser("related", help="List related documents and cross-references")
    rel_p.add_argument("document_id", help="Document ID or relative path")
    rel_p.add_argument("--json", action="store_true", help="Output raw JSON")

    # integrity / audit
    audit_p = subparsers.add_parser("audit", help="Audit knowledge base integrity (broken links, duplicates)")
    audit_p.add_argument("--json", action="store_true", help="Output raw JSON")

    # source-add
    src_add_p = subparsers.add_parser("source-add", help="Register a monitored documentation site or GitHub repo")
    src_add_p.add_argument("source_id", help="Unique source identifier")
    src_add_p.add_argument("--type", choices=["website", "github_repo"], default="website", help="Source type")
    src_add_p.add_argument("--name", required=True, help="Display name")
    src_add_p.add_argument("--url", required=True, help="Canonical URL")
    src_add_p.add_argument("--doc", required=True, help="Destination document ID")
    src_add_p.add_argument("--topics", default="", help="Comma-separated topics")
    src_add_p.add_argument("--trust", choices=["official", "trusted_partner", "community"], default="official", help="Trust tier")

    # source-list
    subparsers.add_parser("source-list", help="List all registered monitored sources")

    # source-remove
    src_rm_p = subparsers.add_parser("source-remove", help="Remove a monitored source")
    src_rm_p.add_argument("source_id", help="Source identifier")

    # check-updates
    chk_p = subparsers.add_parser("check-updates", help="Check sources for updates and apply or queue")
    chk_p.add_argument("--source", default=None, help="Specific source ID to check (default: all)")
    chk_p.add_argument("--json", action="store_true", help="Output raw JSON")

    # review-list
    subparsers.add_parser("review-list", help="List changes pending human review")

    # review-approve
    appr_p = subparsers.add_parser("review-approve", help="Approve and apply a candidate from the review queue")
    appr_p.add_argument("candidate_id", help="Candidate ID")
    appr_p.add_argument("--note", default=None, help="Approval note")

    # review-reject
    rej_p = subparsers.add_parser("review-reject", help="Reject a candidate from the review queue")
    rej_p.add_argument("candidate_id", help="Candidate ID")
    rej_p.add_argument("--note", default=None, help="Rejection note")

    # update-history
    hist_p = subparsers.add_parser("update-history", help="View audit trail of applied knowledge updates")
    hist_p.add_argument("--limit", type=int, default=20, help="Maximum entries to show")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    engine = KnowledgeEngine(root_dir=args.root, db_path=args.db)

    if args.command == "sync":
        if args.rebuild:
            print("[INFO] Rebuilding index from scratch...")
            rep = engine.rebuild_index()
        else:
            print("[INFO] Synchronizing index incrementally...")
            rep = engine.sync_index()
        print(f"Indexed in {rep.duration_seconds:.3f}s: Added={len(rep.added_files)}, "
              f"Modified={len(rep.modified_files)}, Deleted={len(rep.deleted_files)}, "
              f"Unchanged={len(rep.unchanged_files)}")

    elif args.command == "status":
        stats = engine.check_index_status()
        print("=== Knowledge Index Status ===")
        print(f"Total Documents: {stats.total_documents}")
        print(f"Total Sections:  {stats.total_sections}")
        print(f"Total Tokens:    {stats.total_tokens:,}")
        print(f"Total Links:     {stats.total_links}")
        print(f"Database Size:   {stats.index_db_size_bytes / 1024:.1f} KB")

    elif args.command == "search":
        tags = [t.strip() for t in args.tags.split(",")] if args.tags else None
        results = engine.search_knowledge(args.query, tags=tags, limit=args.limit)
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print(f"Found {len(results)} matching section(s) for query: '{args.query}'\n")
            for idx, r in enumerate(results, 1):
                print(f"{idx}. [{r['score']:.2f}] {r['heading']} (Doc: {r['doc_title']}, {r['path']}:{r['start_line']}-{r['end_line']})")
                print(f"   Snippet: {r['matched_snippet']}")
                print(f"   Tokens:  {r['token_count']}")
                print()

    elif args.command == "outline":
        outline = engine.get_document_outline(args.document_id)
        if not outline:
            print(f"Document not found: {args.document_id}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(outline, indent=2))
        else:
            print(f"=== Document Outline: {outline['title']} ({outline['path']}) ===")
            print(f"Total Tokens: {outline['total_tokens']:,}")
            for sec in outline["sections"]:
                indent = "  " * (sec["level"] - 1)
                print(f"{indent}- [{sec['section_id']}] {sec['heading']} (lines {sec['start_line']}-{sec['end_line']}, ~{sec['token_count']} tokens)")

    elif args.command == "section":
        sec = engine.read_section(args.document_id, args.section_id)
        if not sec:
            print(f"Section '{args.section_id}' not found in document '{args.document_id}'", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(sec, indent=2))
        else:
            print(f"### {sec['heading']} (lines {sec['start_line']}-{sec['end_line']}, {sec['token_count']} tokens)")
            print(sec["content"])

    elif args.command == "context":
        pkg = engine.get_source_context(args.query, token_budget=args.budget)
        if args.json:
            print(json.dumps(pkg, indent=2))
        else:
            print(f"=== Evidence Package (Tokens: {pkg['total_tokens']}/{pkg['token_budget']} | Sufficient: {pkg['is_sufficient']}) ===")
            if not pkg["is_sufficient"]:
                print(f"[WARNING] {pkg['insufficient_reason']}")
            for idx, exc in enumerate(pkg["excerpts"], 1):
                print(f"\n--- Excerpt {idx} from {exc['path']} (lines {exc['start_line']}-{exc['end_line']}) ---")
                print(f"Section: {exc['heading']} | Relevance: {exc['relevance_score']:.2f}")
                print(exc["content"])

    elif args.command == "related":
        related = engine.get_related_documents(args.document_id)
        if args.json:
            print(json.dumps(related, indent=2))
        else:
            print(f"=== Cross References for '{args.document_id}' ===")
            for r in related:
                print(f"- {r['direction'].upper()}: {r['target_ref']} -> {r.get('resolved_title') or 'Unresolved'} ({r['link_type']} line {r['line_number']})")

    elif args.command == "audit":
        rep = engine.audit_integrity()
        if args.json:
            print(json.dumps(rep, indent=2))
        else:
            print(f"=== Knowledge Base Audit (Status: {'HEALTHY' if rep['is_healthy'] else 'DEGRADED'}) ===")
            print(f"Checked Documents: {rep['total_checked_docs']}")
            print(f"Broken Links:      {rep['broken_link_count']}")
            print(f"Duplicate IDs:     {rep['duplicate_count']}")
            print(f"Orphaned Docs:     {rep['orphaned_count']}")
            if rep["issues"]:
                print("\nIssues:")
                for i in rep["issues"]:
                    loc = f"{i['path']}:{i['line_number']}" if i['line_number'] else i['path']
                    print(f"  [{i['severity']}] {i['issue_type'].upper()} @ {loc}: {i['message']}")

    elif args.command == "source-add":
        topics = [t.strip() for t in args.topics.split(",") if t.strip()]
        res = engine.register_source(
            source_id=args.source_id,
            source_type=args.type,
            display_name=args.name,
            canonical_url=args.url,
            destination_doc_id=args.doc,
            topics=topics,
            trust_tier=args.trust
        )
        print(f"[OK] Source '{res['source_id']}' registered successfully.")

    elif args.command == "source-list":
        sources = engine.list_sources()
        print(f"=== Registered Monitored Sources ({len(sources)}) ===")
        for s in sources:
            status = "ENABLED" if s['enabled'] else "DISABLED"
            print(f"- [{s['source_id']}] {s['display_name']} ({s['source_type']}) [{status}]")
            print(f"  URL:         {s['canonical_url']}")
            print(f"  Destination: {s['destination_doc_id']}")
            print(f"  Trust:       {s['trust_tier']}")
            if s['last_error']:
                print(f"  Last Error:  {s['last_error']}")
            print()

    elif args.command == "source-remove":
        ok = engine.remove_source(args.source_id)
        if ok:
            print(f"[OK] Source '{args.source_id}' removed.")
        else:
            print(f"[ERROR] Source '{args.source_id}' not found.", file=sys.stderr)
            sys.exit(1)

    elif args.command == "check-updates":
        res = engine.check_updates(source_id=args.source)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print("=== Source Update Check Results ===")
            items = res if isinstance(res, list) else [res]
            for it in items:
                print(f"- Source: {it.get('source_id')}")
                print(f"  Change: {it.get('change_type')}")
                if it.get('action_taken'):
                    print(f"  Action: {it.get('action_taken')} ({it.get('policy_decision')})")
                print(f"  Message:{it.get('message') or it.get('error') or it.get('rationale')}")
                print()

    elif args.command == "review-list":
        queue = engine.list_review_queue()
        print(f"=== Changes Awaiting Human Review ({len(queue)}) ===")
        for q in queue:
            print(f"- [Queue ID {q['queue_id']}] Candidate: {q['candidate_id']}")
            print(f"  Source:    {q['source_id']}")
            print(f"  Risk:      {q['risk_level']}")
            print(f"  Summary:   {q['change_summary']}")
            print(f"  Rationale: {q['rationale']}")
            print("  Preview:")
            print("  " + q['content_preview'].replace("\n", "\n  "))
            print()

    elif args.command == "review-approve":
        res = engine.approve_update(args.candidate_id, note=args.note)
        print(f"[{res.get('status')}] {res.get('message')}")

    elif args.command == "review-reject":
        res = engine.reject_update(args.candidate_id, note=args.note)
        print(f"[{res.get('status')}] {res.get('message')}")

    elif args.command == "update-history":
        hist = engine.list_update_history(limit=args.limit)
        print(f"=== Knowledge Update Audit History ({len(hist)}) ===")
        for h in hist:
            t_iso = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(h['applied_at']))
            print(f"- [{t_iso}] {h['doc_path']} by {h['applied_by']}")
            print(f"  Candidate: {h['candidate_id']} (Source: {h['source_id']})")
            print(f"  Summary:   {h['diff_summary']}")
            print()


if __name__ == "__main__":
    main()
