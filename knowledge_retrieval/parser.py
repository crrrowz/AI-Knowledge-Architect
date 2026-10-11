"""Markdown parser that extracts frontmatter, structural sections, line ranges, and links."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from knowledge_retrieval.models import Document, DocumentLink, Section
from knowledge_retrieval.tokenizer import estimate_tokens


_HEADING_REGEX = re.compile(r"^(#{1,6})\s+(.+)$")
_WIKILINK_REGEX = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
_MD_LINK_REGEX = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def slugify(text: str) -> str:
    """Converts a heading string into a URL/anchor-friendly slug."""
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text.strip("-") or "section"


def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str, int]:
    """Parses optional YAML frontmatter at the beginning of a document.
    
    Returns:
        (metadata_dict, body_text, frontmatter_line_count)
    """
    lines = content.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, content, 0

    end_idx = -1
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break

    if end_idx == -1:
        # Malformed frontmatter (opening --- with no closing ---)
        return {}, content, 0

    yaml_block = "".join(lines[1:end_idx])
    try:
        metadata = yaml.safe_load(yaml_block) or {}
        if not isinstance(metadata, dict):
            metadata = {}
    except Exception:
        metadata = {"_frontmatter_error": "Malformed YAML"}

    # Body starts immediately after end_idx line
    body = "".join(lines[end_idx + 1:])
    return metadata, body, end_idx + 1


def extract_links(lines: List[str], doc_id: str, line_offset: int) -> List[DocumentLink]:
    """Extracts all Markdown links and Wikilinks with their exact source lines."""
    links: List[DocumentLink] = []
    for line_idx, line in enumerate(lines):
        actual_line_no = line_offset + line_idx + 1

        # Check Wikilinks: [[target]] or [[target#heading|Label]]
        for match in _WIKILINK_REGEX.finditer(line):
            target_raw = match.group(1).strip()
            label = match.group(2) or target_raw
            links.append(DocumentLink(
                source_doc_id=doc_id,
                target_ref=target_raw,
                link_type="wikilink",
                line_number=actual_line_no,
                text=label.strip()
            ))

        # Check Standard Markdown links: [Text](target)
        for match in _MD_LINK_REGEX.finditer(line):
            link_text = match.group(1).strip()
            link_url = match.group(2).strip()
            # Ignore external web links (http://, https://, mailto:)
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", link_url) or link_url.startswith("mailto:"):
                continue
            links.append(DocumentLink(
                source_doc_id=doc_id,
                target_ref=link_url,
                link_type="markdown",
                line_number=actual_line_no,
                text=link_text
            ))

    return links


def parse_markdown_document(
    file_path: str,
    root_dir: str,
    raw_content: Optional[str] = None
) -> Document:
    """Parses a Markdown file into a canonical Document model with structured sections and links."""
    p = Path(file_path)
    if raw_content is None:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            raw_content = f.read()

    stat = p.stat() if p.exists() else None
    mtime = stat.st_mtime if stat else 0.0
    size_bytes = stat.st_size if stat else len(raw_content.encode("utf-8"))

    # Relative path from root
    try:
        rel_path = str(p.relative_to(Path(root_dir))).replace("\\", "/")
    except ValueError:
        rel_path = p.name

    # Compute default doc_id (slugified rel_path without .md)
    default_id = rel_path
    if default_id.lower().endswith(".md"):
        default_id = default_id[:-3]
    default_id = default_id.replace("/", ":")

    metadata, body, fm_lines_count = parse_frontmatter(raw_content)

    doc_id = str(metadata.get("id", default_id)).strip()
    title_from_fm = metadata.get("title")
    tags = metadata.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    elif not isinstance(tags, list):
        tags = []
    tags = [str(t) for t in tags]

    doc_type = str(metadata.get("type", "general"))
    status = str(metadata.get("status", "active"))

    # Parse sections and headings
    body_lines = body.splitlines(keepends=True)
    sections: List[Section] = []
    first_h1_title: Optional[str] = None

    current_heading = "Overview"
    current_level = 1
    current_start_line = fm_lines_count + 1
    current_section_lines: List[str] = []
    seen_section_ids: Dict[str, int] = {}

    for idx, line in enumerate(body_lines):
        line_num = fm_lines_count + idx + 1
        heading_match = _HEADING_REGEX.match(line)
        if heading_match:
            hashes = heading_match.group(1)
            level = len(hashes)
            heading_text = heading_match.group(2).strip()

            if level == 1 and first_h1_title is None:
                first_h1_title = heading_text

            # If we had accumulated content in a prior section, flush it
            if current_section_lines:
                sec_content = "".join(current_section_lines).strip()
                if sec_content:
                    base_slug = slugify(current_heading)
                    count = seen_section_ids.get(base_slug, 0)
                    seen_section_ids[base_slug] = count + 1
                    sec_id = base_slug if count == 0 else f"{base_slug}-{count}"
                    
                    end_line = line_num - 1
                    sections.append(Section(
                        section_id=sec_id,
                        heading=current_heading,
                        heading_level=current_level,
                        content=sec_content,
                        start_line=current_start_line,
                        end_line=end_line,
                        token_count=estimate_tokens(sec_content)
                    ))

            # Start new section
            current_heading = heading_text
            current_level = level
            current_start_line = line_num
            current_section_lines = [line]
        else:
            current_section_lines.append(line)

    # Flush final section
    if current_section_lines:
        sec_content = "".join(current_section_lines).strip()
        if sec_content:
            base_slug = slugify(current_heading)
            count = seen_section_ids.get(base_slug, 0)
            seen_section_ids[base_slug] = count + 1
            sec_id = base_slug if count == 0 else f"{base_slug}-{count}"
            end_line = fm_lines_count + len(body_lines)
            sections.append(Section(
                section_id=sec_id,
                heading=current_heading,
                heading_level=current_level,
                content=sec_content,
                start_line=current_start_line,
                end_line=end_line,
                token_count=estimate_tokens(sec_content)
            ))

    # If no sections were created (e.g. empty body), create a dummy empty overview section
    if not sections:
        sections.append(Section(
            section_id="overview",
            heading="Overview",
            heading_level=1,
            content="",
            start_line=1,
            end_line=max(1, len(raw_content.splitlines())),
            token_count=0
        ))

    # Final title determination
    doc_title = str(title_from_fm or first_h1_title or p.stem).strip()

    # Extract all links across entire raw content
    all_lines = raw_content.splitlines()
    links = extract_links(all_lines, doc_id, line_offset=0)

    # Cross-references in frontmatter 'related' field
    related_list = metadata.get("related", [])
    if isinstance(related_list, list):
        for ref in related_list:
            if ref and isinstance(ref, str):
                links.append(DocumentLink(
                    source_doc_id=doc_id,
                    target_ref=ref.strip(),
                    link_type="frontmatter_related",
                    line_number=1,
                    text=f"Related: {ref}"
                ))

    import hashlib
    content_hash = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()
    doc_tokens = estimate_tokens(raw_content)

    return Document(
        doc_id=doc_id,
        path=rel_path,
        title=doc_title,
        content_hash=content_hash,
        size_bytes=size_bytes,
        mtime=mtime,
        frontmatter=metadata,
        tags=tags,
        doc_type=doc_type,
        status=status,
        sections=sections,
        links=links,
        raw_content=raw_content,
        token_count=doc_tokens
    )
