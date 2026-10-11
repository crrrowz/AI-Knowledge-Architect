# Project Governance & Decision-Making Model

**AI-Knowledge-Architect** is an open-source project managed under a transparent, engineering-driven governance model.

---

## 1. Principles

1. **Engineering Grounding:** Architecture decisions must be supported by empirical evidence, benchmark metrics, and security analyses rather than speculative trends.
2. **Local-First & Non-Destructive:** We prioritize zero-remote local execution, non-destructive file operations, and strict data preservation.
3. **Open Collaboration:** All design changes, pull requests, and security disclosures follow documented, publicly auditable processes.

---

## 2. Roles and Responsibilities

### Contributors
Anyone who submits code, documentation, bug reports, or benchmark evaluations. Contributors must adhere to the [Code of Conduct](CODE_OF_CONDUCT.md) and [Contributing Guide](CONTRIBUTING.md).

### Maintainers
Individuals with write access to the repository and responsibility for guiding project architecture:
- Reviewing and approving pull requests.
- Enforcing architectural invariants and security boundaries.
- Releasing new versions following Semantic Versioning.
- Moderating community discussions and enforcing the Code of Conduct.

---

## 3. Decision-Making & Consensus Model

- **Routine Changes (Bug fixes, documentation improvements, test additions):** Require review and approval from at least one Maintainer.
- **Architectural Changes (Schema modifications, new pipeline stages, new dependencies):** Propose via an Architecture Decision Record (ADR) in `docs/` or a GitHub Discussion. Consensus is reached through lazy consensus among Maintainers with a minimum 72-hour review window.
- **Breaking Changes:** Require explicit approval from lead maintainers and must follow Semantic Versioning (major version bump).

---

## 4. Release Authority

Releases are published strictly by authorized Maintainers listed in [MAINTAINERS.md](MAINTAINERS.md). Each release requires:
1. All automated test suites passing with 100% pass rate (`pytest -v`).
2. Multi-scale benchmarks executed and verified clean.
3. Version increment in `pyproject.toml` and documentation.
4. Structured release notes documented in `CHANGELOG.md`.
