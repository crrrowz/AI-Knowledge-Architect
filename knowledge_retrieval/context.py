"""Evidence Context Assembler enforcing token budgeting and sufficiency validation."""

from __future__ import annotations

from typing import List, Optional

from knowledge_retrieval.models import ContextExcerpt, ContextPackage, SearchResult
from knowledge_retrieval.retriever import Retriever
from knowledge_retrieval.tokenizer import estimate_tokens


class ContextAssembler:
    """Constructs token-bounded, section-traceable evidence packages for AI models."""

    def __init__(self, retriever: Retriever, default_token_budget: int = 1500):
        self.retriever = retriever
        self.default_token_budget = default_token_budget

    def assemble(
        self,
        query: str,
        token_budget: Optional[int] = None,
        min_relevance_score: float = -10.0,
        include_related_refs: bool = True,
        max_sections: int = 5
    ) -> ContextPackage:
        """Searches and compiles relevant section excerpts strictly within the allocated token budget."""
        budget = token_budget if token_budget is not None else self.default_token_budget
        search_results = self.retriever.search(query, limit=max_sections * 2)

        if not search_results:
            return ContextPackage(
                query=query,
                excerpts=[],
                total_tokens=0,
                token_budget=budget,
                is_sufficient=False,
                unresolved_questions=[f"No matching documents or sections found for query: '{query}'"],
                insufficient_reason="No relevant sections found in the knowledge repository.",
                missing_evidence_notice="The repository lacks indexed documents addressing this query."
            )

        excerpts: List[ContextExcerpt] = []
        current_token_count = 0
        seen_section_keys = set()

        for res in search_results:
            sec_key = (res.doc_id, res.section_id)
            if sec_key in seen_section_keys:
                continue

            sec = self.retriever.read_section(res.doc_id, res.section_id)
            if not sec:
                continue

            content = sec.content
            # Estimate tokens of the formatted excerpt
            excerpt_header = f"### [{res.doc_title}] {sec.heading} ({res.path}:{sec.start_line}-{sec.end_line})\n"
            excerpt_tokens = estimate_tokens(excerpt_header + content)

            # Check if this excerpt fits in remaining budget
            if current_token_count + excerpt_tokens > budget:
                # If budget is tight and we have zero excerpts yet, truncate the section cleanly
                if not excerpts and budget > 50:
                    truncated_content = content[: max(100, budget * 3)] + "\n... [Truncated due to token budget]"
                    trunc_tokens = estimate_tokens(excerpt_header + truncated_content)
                    excerpts.append(ContextExcerpt(
                        doc_id=res.doc_id,
                        path=res.path,
                        section_id=res.section_id,
                        heading=sec.heading,
                        start_line=sec.start_line,
                        end_line=sec.end_line,
                        content=truncated_content,
                        relevance_score=res.score,
                        token_count=trunc_tokens
                    ))
                    current_token_count += trunc_tokens
                break

            # Collect cross references if requested
            cross_refs = []
            if include_related_refs:
                related = self.retriever.get_related_documents(res.doc_id)
                for r in related[:3]:
                    target = r.get("resolved_title") or r.get("target_ref")
                    if target:
                        cross_refs.append(f"{r['direction']} -> {target}")

            excerpts.append(ContextExcerpt(
                doc_id=res.doc_id,
                path=res.path,
                section_id=res.section_id,
                heading=sec.heading,
                start_line=sec.start_line,
                end_line=sec.end_line,
                content=content,
                relevance_score=res.score,
                token_count=excerpt_tokens,
                cross_references=cross_refs
            ))
            current_token_count += excerpt_tokens
            seen_section_keys.add(sec_key)

            if len(excerpts) >= max_sections:
                break

        # Assess sufficiency
        is_sufficient = len(excerpts) > 0 and search_results[0].score >= min_relevance_score
        unresolved = []
        insufficient_reason = None

        if not is_sufficient:
            insufficient_reason = f"Top result score ({search_results[0].score if search_results else 0}) below relevance threshold ({min_relevance_score})."
            unresolved.append("The retrieved excerpts may only partially address the topic.")

        return ContextPackage(
            query=query,
            excerpts=excerpts,
            total_tokens=current_token_count,
            token_budget=budget,
            is_sufficient=is_sufficient,
            unresolved_questions=unresolved,
            insufficient_reason=insufficient_reason
        )
