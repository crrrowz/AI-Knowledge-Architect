# AI-Knowledge-Architect Documentation System

Welcome to the **AI-Knowledge-Architect** documentation system. This documentation is organized as an engineering system structured by persona and task.

---

## 1. Documentation Map by Persona

```text
                               AI-Knowledge-Architect
                                         │
        ┌───────────────────┬────────────┴───────┬────────────────────┐
        ▼                   ▼                    ▼                    ▼
   [For Users]      [For Integrators]    [For Contributors]   [Audits & ADRs]
   • README.md      • ARCHITECTURE.md    • CONTRIBUTING.md    • ADR-001
   • OPERATIONS     • AGENT_ARCH         • SECURITY.md        • AUDIT_REPORT
   • CLI Commands   • PROFILES           • CODE_OF_CONDUCT    • SECURITY_AUDIT
                    • RESEARCH_DESIGN    • MAINTAINERS.md     • E2E_AUDIT
```

---

## 2. Document Catalog

### A. Getting Started & Operations (Users & Operators)
- **[README.md](../README.md)**: Project front door, purpose, quick start, and feature summary.
- **[Operations & Recovery Guide](OPERATIONS-AND-RECOVERY.md)**: CLI command reference, operational maintenance, and disaster recovery.
- **[Failure Recovery & Concurrency Guide](RECOVERY_AND_CONSISTENCY.md)**: SQLite WAL mode, atomic file swapping, and crash recovery.
- **[Operational Remaining Risks](REMAINING_RISKS.md)**: Documented operational constraints, network limits, and production boundaries.

### B. Architecture & APIs (AI Integrators & Developers)
- **[Core Architecture Specification](ARCHITECTURE.md)**: Component breakdown, SQLite FTS5 schemas, and BM25 ranking pipeline.
- **[Document Schema Specification](DOCUMENT-SCHEMA.md)**: Canonical Markdown frontmatter schema (KDS-v1), section addressing, and link formats.
- **[Knowledge Agent Architecture](KNOWLEDGE_AGENT_ARCHITECTURE.md)**: Six-stage agent lifecycle: `INSPECT -> PLAN -> POLICY -> EXECUTE -> VERIFY -> REPORT`.
- **[Knowledge Library Profiles](KNOWLEDGE_LIBRARY_PROFILES.md)**: Declarative profile schema, permission boundaries, and YAML examples.
- **[Knowledge Agent Operations](AGENT_OPERATIONS.md)**: Practical workflows, Python API patterns, and agent CLI commands.
- **[Autonomous Update Pipeline Design](AUTO_UPDATE_DESIGN.md)**: Source registry, conditional polling, change detection, and human review queue.
- **[Research & Authoring Architecture](RESEARCH_AUTHORING_DESIGN.md)**: Evidence collection, claim-to-evidence tracking, and post-authoring verification.

### C. Governance & Contribution (Contributors & Maintainers)
- **[Contributing Guide](../CONTRIBUTING.md)**: Development bootstrap, code invariants, and PR guidelines.
- **[Security Policy](../SECURITY.md)**: Vulnerability disclosure, response SLAs, and threat model.
- **[Code of Conduct](../CODE_OF_CONDUCT.md)**: Contributor Covenant standards and enforcement.
- **[Project Governance](../GOVERNANCE.md)**: Decision-making model, consensus, and release authority.
- **[Maintainers](../MAINTAINERS.md)**: Active maintainers and contact mechanisms.
- **[Changelog](../CHANGELOG.md)**: Semantic versioning history and release notes.
- **[Support Resources](../SUPPORT.md)**: Help channels, issue reporting, and discussion forums.

### D. Architectural Decision Records & Audits (Auditors & Architects)
- **[ADR 001: Technology Selection](ADR-001-technology-selection.md)**: Rationale for Python 3.12, SQLite FTS5, and local-first architecture.
- **[Independent Reliability Audit](AUDIT_REPORT.md)**: Initial reliability audit, identified defects, and confirmed fixes.
- **[End-to-End Reliability & Integration Audit](END_TO_END_AUDIT.md)**: Full lifecycle testing, live mock HTTP fixtures, and policy verification.
- **[Comprehensive Security Audit](SECURITY_AUDIT.md)**: SSRF defenses, path traversal protection, and prompt injection defense.
- **[Benchmark Methodology](BENCHMARK_METHODOLOGY.md)**: Metric definitions, multi-scale evaluation (50, 500, 5000 docs), and nDCG formulas.
- **[Research & Authoring Gap Analysis](RESEARCH_AND_AUTHORING_GAP_ANALYSIS.md)**: Baseline capability evaluation against autonomous research goals.
- **[Research & Authoring Test Report](RESEARCH_AUTHORING_TEST_REPORT.md)**: Verification report for evidence-backed authoring and retrieval quality.
- **[Test Coverage Gaps](TEST_COVERAGE_GAPS.md)**: Boundary analysis and concurrency risk documentation.
