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


if __name__ == "__main__":
    main()
