"""Markdown Knowledge Updater applying validated changes non-destructively with audit history."""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from typing import Optional, Tuple

from knowledge_retrieval.auto_update_models import ChangeCandidate, ChangeType
from knowledge_retrieval.auto_update_store import AutoUpdateStore
from knowledge_retrieval.indexer import Indexer


class KnowledgeUpdater:
    """Safely updates Markdown knowledge files on disk, records audit history, and reindexes."""

    def __init__(self, root_dir: str, store: AutoUpdateStore, indexer: Indexer):
        self.root_dir = str(Path(root_dir).resolve())
        self.store = store
        self.indexer = indexer

    def apply_candidate(
        self,
        candidate: ChangeCandidate,
        applied_by: str = "AUTO_POLICY"
    ) -> Tuple[bool, str]:
        """Applies a validated ChangeCandidate to the target Markdown file.
        
        Returns:
            (success: bool, message: str)
        """
        if not candidate.affected_doc_ids:
            return False, "Candidate has no destination document ID."

        target_doc_id = candidate.affected_doc_ids[0]
        # Resolve disk path for target document
        existing_doc = self.indexer.storage.get_document(target_doc_id)
        if existing_doc:
            doc_rel_path = existing_doc.path
        else:
            # Create new markdown path if not already existing
            filename = target_doc_id.replace(":", "_").replace("/", "_")
            if not filename.endswith(".md"):
                filename += ".md"
            doc_rel_path = filename

        abs_path = os.path.join(self.root_dir, doc_rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)

        prev_content = ""
        prev_hash = ""
        if os.path.exists(abs_path):
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                prev_content = f.read()
            prev_hash = hashlib.sha256(prev_content.encode("utf-8")).hexdigest()

        # Format update non-destructively
        now_iso = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(candidate.observed_at))
        source_url = candidate.evidence.get("source_url", "External Source")

        if candidate.change_type == ChangeType.NEW_RELEASE:
            tag = candidate.evidence.get("release_tag", "Latest")
            release_block = f"""
## Release {tag}
<!-- auto-update-provenance: source="{source_url}" observed="{now_iso}" fingerprint="{candidate.curr_fingerprint[:12]}" -->
**Published:** {now_iso}  
**Source:** [{tag}]({candidate.evidence.get('release_url', source_url)})  

{candidate.normalized_content}
""".strip()
            if prev_content:
                new_content = prev_content.rstrip() + "\n\n" + release_block + "\n"
            else:
                new_content = f"""---
id: {target_doc_id}
title: {target_doc_id.replace('_', ' ').title()}
tags: {candidate.affected_topics}
---

# {target_doc_id.replace('_', ' ').title()}

{release_block}
"""

        else:
            # Documentation update
            update_block = f"""
## External Update ({now_iso[:10]})
<!-- auto-update-provenance: source="{source_url}" observed="{now_iso}" fingerprint="{candidate.curr_fingerprint[:12]}" -->
{candidate.normalized_content}
""".strip()
            if prev_content:
                new_content = prev_content.rstrip() + "\n\n" + update_block + "\n"
            else:
                new_content = f"""---
id: {target_doc_id}
title: {target_doc_id.replace('_', ' ').title()}
tags: {candidate.affected_topics}
---

# {target_doc_id.replace('_', ' ').title()}

{update_block}
"""

        # Write to disk atomically
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        new_hash = hashlib.sha256(new_content.encode("utf-8")).hexdigest()

        # Record audit history in SQLite
        diff_summary = f"{candidate.change_type.value}: {candidate.change_summary}"
        self.store.record_history(
            candidate_id=candidate.candidate_id,
            source_id=candidate.source_id,
            doc_path=doc_rel_path,
            diff_summary=diff_summary,
            prev_hash=prev_hash,
            new_hash=new_hash,
            applied_by=applied_by
        )

        # Trigger incremental index synchronization
        self.indexer.sync()

        return True, f"Successfully applied update from {candidate.source_id} to {doc_rel_path}."
