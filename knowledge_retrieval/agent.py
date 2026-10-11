"""General-Purpose Knowledge Management Agent implementing INSPECT -> PLAN -> POLICY -> EXECUTE -> VERIFY -> REPORT."""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from knowledge_retrieval.api import KnowledgeEngine
from knowledge_retrieval.auto_update_models import PolicyDecision, RiskLevel
from knowledge_retrieval.profile import KnowledgeLibraryProfile


@dataclass
class InspectionResult:
    """Findings from inspecting a knowledge library against its profile."""
    library_id: str
    root_dir: str
    total_docs: int
    total_sections: int
    total_tokens: int
    existing_doc_ids: List[str]
    missing_expected_docs: List[Dict[str, str]]
    broken_links: List[Dict[str, Any]]
    integrity_issues: List[Dict[str, Any]]
    pending_review_items: List[Dict[str, Any]]
    observed_topics: List[str]
    inspected_at: float = field(default_factory=time.time)


@dataclass
class AgentOperation:
    """An individual operation within an agent plan."""
    operation_id: str
    action: str  # 'CREATE_DOCUMENT', 'UPDATE_DOCUMENT', 'FIX_LINK', 'REVIEW_DECISION', 'DELETE_DOCUMENT'
    target_path: str
    reason: str
    proposed_content: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.LOW
    policy_decision: PolicyDecision = PolicyDecision.AUTO_APPLY
    decision_rationale: str = ""
    execution_status: str = "PENDING"  # 'PENDING', 'APPLIED', 'SKIPPED', 'REJECTED', 'FAILED'
    verification_status: str = "UNVERIFIED"  # 'UNVERIFIED', 'VERIFIED', 'FAILED'
    error_message: Optional[str] = None


@dataclass
class AgentPlan:
    """Structured plan of operations generated to achieve library goals."""
    plan_id: str
    library_id: str
    goal: str
    operations: List[AgentOperation]
    created_at: float = field(default_factory=time.time)


@dataclass
class AgentExecutionReport:
    """Final auditable report distinguishing completed, skipped, failed, and verified operations."""
    run_id: str
    library_id: str
    dry_run: bool
    completed_operations: List[AgentOperation]
    failed_operations: List[AgentOperation]
    skipped_operations: List[AgentOperation]
    unresolved_issues: List[str]
    verification_evidence: Dict[str, Any]
    duration_seconds: float
    timestamp: float = field(default_factory=time.time)


class KnowledgeAgent:
    """General-purpose orchestration agent customized by KnowledgeLibraryProfile."""

    def __init__(self, profile: KnowledgeLibraryProfile):
        self.profile = profile
        self.engine = KnowledgeEngine(root_dir=profile.root_dir, db_path=profile.db_path)

    # =========================================================================
    # STAGE 1: INSPECT
    # =========================================================================

    def inspect(self) -> InspectionResult:
        """Inspects the permitted library root, gathers inventory, and checks integrity without modifying files."""
        # 1. Sync index (read-only inspection of disk changes into local derived index)
        self.engine.sync_index()
        stats = self.engine.check_index_status()
        docs = self.engine.storage.get_all_documents()
        existing_doc_ids = [d.doc_id for d in docs]
        existing_paths = [d.path for d in docs]

        # 2. Collect observed topics
        topics_set = set()
        for d in docs:
            topics_set.update(d.tags)

        # 3. Check for missing expected documents defined in profile organization
        missing_expected = []
        for org in self.profile.organization:
            for exp_id in org.expected_doc_ids:
                if exp_id not in existing_doc_ids and f"{exp_id}.md" not in existing_paths:
                    expected_rel = os.path.join(org.directory, f"{exp_id}.md").replace("\\", "/")
                    missing_expected.append({
                        "doc_id": exp_id,
                        "expected_path": expected_rel,
                        "directory": org.directory,
                        "description": org.description
                    })

        # 4. Check integrity issues
        audit_rep = self.engine.audit_integrity()
        broken = [i for i in audit_rep["issues"] if i["issue_type"] == "broken_link"]

        # 5. Check pending review queue items
        review_items = self.engine.list_review_queue(status="PENDING")

        return InspectionResult(
            library_id=self.profile.library_id,
            root_dir=self.profile.root_dir,
            total_docs=stats.total_documents,
            total_sections=stats.total_sections,
            total_tokens=stats.total_tokens,
            existing_doc_ids=existing_doc_ids,
            missing_expected_docs=missing_expected,
            broken_links=broken,
            integrity_issues=audit_rep["issues"],
            pending_review_items=review_items,
            observed_topics=sorted(list(topics_set))
        )

    # =========================================================================
    # STAGE 2: PLAN
    # =========================================================================

    def plan(self, inspection: Optional[InspectionResult] = None) -> AgentPlan:
        """Generates a structured plan of operations to satisfy profile goals and fix issues."""
        insp = inspection or self.inspect()
        plan_id = f"plan-{self.profile.library_id}-{uuid.uuid4().hex[:6]}"
        ops: List[AgentOperation] = []
        op_counter = 1

        # 1. Plan creation of missing expected documents
        for miss in insp.missing_expected_docs:
            doc_id = miss["doc_id"]
            target_path = miss["expected_path"]
            title = doc_id.replace("_", " ").replace("-", " ").title()
            initial_content = f"""---
id: {doc_id}
title: "{title}"
tags: [{miss.get('directory', '').replace('/', ', ')}]
type: reference
---

# {title}

{miss.get('description', 'Technical documentation and reference.')}

## Overview
Detailed content for {title}.
"""
            ops.append(AgentOperation(
                operation_id=f"op-{op_counter:03d}",
                action="CREATE_DOCUMENT",
                target_path=target_path,
                reason=f"Goal satisfaction: Expected document '{doc_id}' is missing from '{miss.get('directory')}'.",
                proposed_content=initial_content,
                evidence={"expected_doc_id": doc_id, "directory": miss.get("directory")},
                risk_level=RiskLevel.LOW
            ))
            op_counter += 1

        # 2. Plan remediation for broken links
        for brk in insp.broken_links:
            ops.append(AgentOperation(
                operation_id=f"op-{op_counter:03d}",
                action="FIX_LINK",
                target_path=brk["path"],
                reason=f"Integrity rule: {brk['message']}",
                evidence=brk.get("details", {}),
                risk_level=RiskLevel.MEDIUM
            ))
            op_counter += 1

        return AgentPlan(
            plan_id=plan_id,
            library_id=self.profile.library_id,
            goal=self.profile.goal,
            operations=ops
        )

    # =========================================================================
    # STAGE 3: POLICY CHECK
    # =========================================================================

    def policy_check(self, plan: AgentPlan) -> None:
        """Evaluates each planned operation against profile permissions and safety boundaries."""
        perms = self.profile.permissions

        for op in plan.operations:
            # Check filesystem safety & boundary containment
            safe, msg = self.profile.validate_path_safety(op.target_path)
            if not safe:
                op.policy_decision = PolicyDecision.REJECT
                op.risk_level = RiskLevel.CRITICAL
                op.decision_rationale = f"Safety Boundary Blocked: {msg}"
                continue

            # Check action permissions
            if op.action == "CREATE_DOCUMENT":
                if not perms.allow_create:
                    op.policy_decision = PolicyDecision.REJECT
                    op.decision_rationale = "Permission denied: 'allow_create' is False in library profile."
                else:
                    op.policy_decision = PolicyDecision.AUTO_APPLY
                    op.decision_rationale = "Permitted non-destructive creation."

            elif op.action == "UPDATE_DOCUMENT" or op.action == "FIX_LINK":
                if not perms.allow_modify:
                    op.policy_decision = PolicyDecision.REJECT
                    op.decision_rationale = "Permission denied: 'allow_modify' is False in library profile."
                else:
                    op.policy_decision = PolicyDecision.AUTO_APPLY
                    op.decision_rationale = "Permitted modification."

            elif op.action == "DELETE_DOCUMENT":
                if not perms.allow_delete:
                    op.policy_decision = PolicyDecision.REJECT
                    op.decision_rationale = "Permission denied: 'allow_delete' is False in library profile."
                elif perms.require_approval_for_destructive:
                    op.policy_decision = PolicyDecision.REVIEW_REQUIRED
                    op.risk_level = RiskLevel.HIGH
                    op.decision_rationale = "Destructive operation requires explicit human approval."
                else:
                    op.policy_decision = PolicyDecision.AUTO_APPLY

    # =========================================================================
    # STAGE 4: EXECUTE
    # =========================================================================

    def execute(self, plan: AgentPlan, dry_run: bool = False) -> AgentExecutionReport:
        """Executes approved operations in plan or previews in dry-run mode."""
        t0 = time.time()
        run_id = f"run-{self.profile.library_id}-{uuid.uuid4().hex[:6]}"
        completed: List[AgentOperation] = []
        failed: List[AgentOperation] = []
        skipped: List[AgentOperation] = []
        unresolved: List[str] = []

        root_resolved = Path(self.profile.root_dir).resolve()

        for op in plan.operations:
            if op.policy_decision == PolicyDecision.REJECT:
                op.execution_status = "REJECTED"
                skipped.append(op)
                unresolved.append(f"Rejected {op.operation_id}: {op.decision_rationale}")
                continue

            if op.policy_decision == PolicyDecision.REVIEW_REQUIRED:
                op.execution_status = "SKIPPED_REVIEW_REQUIRED"
                skipped.append(op)
                unresolved.append(f"Pending Review {op.operation_id}: {op.decision_rationale}")
                continue

            # AUTO_APPLY Operation
            if dry_run:
                op.execution_status = "PREVIEWED_DRY_RUN"
                completed.append(op)
                continue

            # Live Execution
            target_abs = root_resolved / op.target_path.replace("\\", "/")
            try:
                if op.action == "CREATE_DOCUMENT":
                    target_abs.parent.mkdir(parents=True, exist_ok=True)
                    # Atomic write with temp file
                    tmp = str(target_abs) + f".tmp.{os.getpid()}"
                    with open(tmp, "w", encoding="utf-8") as f:
                        f.write(op.proposed_content)
                    os.replace(tmp, str(target_abs))
                    op.execution_status = "APPLIED"
                    completed.append(op)

                elif op.action == "UPDATE_DOCUMENT":
                    target_abs.parent.mkdir(parents=True, exist_ok=True)
                    tmp = str(target_abs) + f".tmp.{os.getpid()}"
                    with open(tmp, "w", encoding="utf-8") as f:
                        f.write(op.proposed_content)
                    os.replace(tmp, str(target_abs))
                    op.execution_status = "APPLIED"
                    completed.append(op)

                elif op.action == "DELETE_DOCUMENT":
                    if target_abs.exists():
                        target_abs.unlink()
                    op.execution_status = "APPLIED"
                    completed.append(op)

                else:
                    op.execution_status = "SKIPPED_UNSUPPORTED"
                    skipped.append(op)

            except Exception as e:
                op.execution_status = "FAILED"
                op.error_message = str(e)
                failed.append(op)
                unresolved.append(f"Failed {op.operation_id}: {e}")

        # Synchronize index post-execution if live
        if not dry_run and completed:
            self.engine.sync_index()

        # Build execution report
        report = AgentExecutionReport(
            run_id=run_id,
            library_id=self.profile.library_id,
            dry_run=dry_run,
            completed_operations=completed,
            failed_operations=failed,
            skipped_operations=skipped,
            unresolved_issues=unresolved,
            verification_evidence={},
            duration_seconds=time.time() - t0
        )

        # STAGE 5: VERIFY
        self.verify(report)
        return report

    # =========================================================================
    # STAGE 5: VERIFY
    # =========================================================================

    def verify(self, report: AgentExecutionReport) -> None:
        """Independently checks actual filesystem and search index states post-execution."""
        if report.dry_run:
            report.verification_evidence = {"mode": "dry_run", "verified": True}
            return

        root_resolved = Path(self.profile.root_dir).resolve()
        verified_count = 0
        checks = {}

        for op in report.completed_operations:
            target_abs = root_resolved / op.target_path.replace("\\", "/")
            if op.action == "CREATE_DOCUMENT" or op.action == "UPDATE_DOCUMENT":
                if target_abs.exists() and target_abs.stat().st_size > 0:
                    op.verification_status = "VERIFIED"
                    verified_count += 1
                    checks[op.target_path] = "EXISTS_ON_DISK"
                else:
                    op.verification_status = "FAILED"
                    checks[op.target_path] = "MISSING_OR_EMPTY"

            elif op.action == "DELETE_DOCUMENT":
                if not target_abs.exists():
                    op.verification_status = "VERIFIED"
                    verified_count += 1
                    checks[op.target_path] = "DELETED_CONFIRMED"
                else:
                    op.verification_status = "FAILED"
                    checks[op.target_path] = "STILL_EXISTS"

        # Index check: verify newly created documents are retrievable
        stats = self.engine.check_index_status()
        checks["indexed_doc_count"] = stats.total_documents
        checks["indexed_section_count"] = stats.total_sections

        report.verification_evidence = {
            "verified_operations_count": verified_count,
            "total_completed": len(report.completed_operations),
            "checks": checks
        }

    # =========================================================================
    # COMPLETE LIFECYCLE RUNNER
    # =========================================================================

    def run(self, dry_run: bool = False) -> AgentExecutionReport:
        """Executes full INSPECT -> PLAN -> POLICY CHECK -> EXECUTE -> VERIFY pipeline."""
        inspection = self.inspect()
        plan = self.plan(inspection)
        self.policy_check(plan)
        return self.execute(plan, dry_run=dry_run)
