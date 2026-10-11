"""Knowledge Library Profile specification, schema, and validation."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class LibraryPermissions:
    """Explicit permission flags governing agent write scope and operations."""
    allow_read: bool = True
    allow_create: bool = True
    allow_modify: bool = True
    allow_delete: bool = False
    allow_external_fetch: bool = True
    require_approval_for_destructive: bool = True
    require_approval_for_breaking: bool = True


@dataclass
class QualityRules:
    """Structural hygiene and validation requirements for Markdown documents."""
    require_frontmatter: bool = True
    required_frontmatter_keys: List[str] = field(default_factory=lambda: ["id", "title"])
    require_title_h1: bool = True
    enforce_link_integrity: bool = True
    disallow_orphaned_docs: bool = False
    max_section_tokens: int = 1500


@dataclass
class OrganizationRule:
    """Defines target directory structure and expected topics."""
    directory: str
    expected_doc_ids: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class KnowledgeLibraryProfile:
    """Versioned configuration governing an individual, isolated knowledge repository."""
    library_id: str
    name: str
    root_dir: str
    goal: str
    version: str = "1.0"
    outcomes: List[str] = field(default_factory=list)
    permitted_paths: List[str] = field(default_factory=list)  # Relative sub-paths within root_dir
    organization: List[OrganizationRule] = field(default_factory=list)
    permissions: LibraryPermissions = field(default_factory=LibraryPermissions)
    quality_rules: QualityRules = field(default_factory=QualityRules)
    db_path: Optional[str] = None  # Defaults to <root_dir>/.knowledge_index/index.db
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], base_dir: Optional[str] = None) -> KnowledgeLibraryProfile:
        """Parses a dictionary into a validated KnowledgeLibraryProfile."""
        library_id = str(data.get("library_id", "")).strip()
        if not library_id:
            raise ValueError("Profile error: 'library_id' must be specified and non-empty.")

        name = str(data.get("name", library_id)).strip()
        raw_root = str(data.get("root_dir", ".")).strip()

        if base_dir:
            root_path = Path(base_dir) / raw_root
        else:
            root_path = Path(raw_root)
        resolved_root = str(root_path.resolve())

        goal = str(data.get("goal", "Maintain comprehensive and accurate knowledge.")).strip()

        # Parse Permissions
        perm_data = data.get("permissions", {})
        perms = LibraryPermissions(
            allow_read=bool(perm_data.get("allow_read", True)),
            allow_create=bool(perm_data.get("allow_create", True)),
            allow_modify=bool(perm_data.get("allow_modify", True)),
            allow_delete=bool(perm_data.get("allow_delete", False)),
            allow_external_fetch=bool(perm_data.get("allow_external_fetch", True)),
            require_approval_for_destructive=bool(perm_data.get("require_approval_for_destructive", True)),
            require_approval_for_breaking=bool(perm_data.get("require_approval_for_breaking", True))
        )

        # Parse Quality Rules
        q_data = data.get("quality_rules", {})
        q_rules = QualityRules(
            require_frontmatter=bool(q_data.get("require_frontmatter", True)),
            required_frontmatter_keys=list(q_data.get("required_frontmatter_keys", ["id", "title"])),
            require_title_h1=bool(q_data.get("require_title_h1", True)),
            enforce_link_integrity=bool(q_data.get("enforce_link_integrity", True)),
            disallow_orphaned_docs=bool(q_data.get("disallow_orphaned_docs", False)),
            max_section_tokens=int(q_data.get("max_section_tokens", 1500))
        )

        # Parse Organization Rules
        org_rules = []
        for org in data.get("organization", []):
            org_rules.append(OrganizationRule(
                directory=str(org.get("directory", "")).strip(),
                expected_doc_ids=list(org.get("expected_doc_ids", [])),
                description=str(org.get("description", ""))
            ))

        db_path = data.get("db_path")
        if db_path:
            if base_dir and not os.path.isabs(db_path):
                db_path = str((Path(base_dir) / db_path).resolve())
            else:
                db_path = str(Path(db_path).resolve())

        return cls(
            library_id=library_id,
            name=name,
            root_dir=resolved_root,
            goal=goal,
            version=str(data.get("version", "1.0")),
            outcomes=list(data.get("outcomes", [])),
            permitted_paths=list(data.get("permitted_paths", [])),
            organization=org_rules,
            permissions=perms,
            quality_rules=q_rules,
            db_path=db_path,
            metadata=dict(data.get("metadata", {}))
        )

    @classmethod
    def load(cls, file_path: str) -> KnowledgeLibraryProfile:
        """Loads and parses a profile from YAML or JSON file."""
        p = Path(file_path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Knowledge profile not found: {file_path}")

        content = p.read_text(encoding="utf-8")
        if p.suffix.lower() in (".yaml", ".yml"):
            data = yaml.safe_load(content) or {}
        else:
            data = json.loads(content)

        return cls.from_dict(data, base_dir=str(p.parent))

    def save(self, file_path: str) -> None:
        """Saves profile to YAML file."""
        data = {
            "library_id": self.library_id,
            "name": self.name,
            "root_dir": self.root_dir,
            "goal": self.goal,
            "version": self.version,
            "outcomes": self.outcomes,
            "permitted_paths": self.permitted_paths,
            "organization": [
                {
                    "directory": o.directory,
                    "expected_doc_ids": o.expected_doc_ids,
                    "description": o.description
                }
                for o in self.organization
            ],
            "permissions": asdict(self.permissions),
            "quality_rules": asdict(self.quality_rules),
            "db_path": self.db_path,
            "metadata": self.metadata
        }
        p = Path(file_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            yaml.dump(data, f, sort_keys=False)

    def validate_path_safety(self, relative_path: str) -> Tuple[bool, str]:
        """Ensures a path is strictly inside the library root and matches permitted sub-paths."""
        clean_rel = relative_path.replace("\\", "/").strip()
        if ".." in clean_rel or clean_rel.startswith("/"):
            return False, f"Path traversal attempt blocked: '{relative_path}'."

        root_resolved = Path(self.root_dir).resolve()
        target_abs = (root_resolved / clean_rel).resolve()

        if not target_abs.is_relative_to(root_resolved):
            return False, f"Target path '{relative_path}' escapes library root '{self.root_dir}'."

        # If permitted_paths is specified, target must fall within at least one permitted sub-path
        if self.permitted_paths:
            allowed = False
            for allowed_sub in self.permitted_paths:
                allowed_abs = (root_resolved / allowed_sub.replace("\\", "/")).resolve()
                if target_abs == allowed_abs or target_abs.is_relative_to(allowed_abs):
                    allowed = True
                    break
            if not allowed:
                return False, f"Target path '{relative_path}' is outside permitted scopes: {self.permitted_paths}."

        return True, "OK"
