# Contributing to AI-Knowledge-Architect

Thank you for your interest in contributing to **AI-Knowledge-Architect**! This project is an open-source, local-first knowledge retrieval and autonomous agent system.

We treat contributions with engineering rigor: clear rationale, reproducible evidence, deterministic tests, and non-breaking architecture.

---

## 1. Code of Conduct

All contributors, maintainers, and community participants are expected to adhere to our [Code of Conduct](CODE_OF_CONDUCT.md). Please treat everyone with respect and professionalism.

---

## 2. Development Setup

### Prerequisites
- **Python:** 3.10, 3.11, or 3.12 (Python 3.12 recommended).
- **SQLite:** 3.35+ with FTS5 module enabled (built into official Python distributions).
- **Git:** Version 2.30+.

### Step-by-Step Environment Bootstrap
```bash
# 1. Clone repository
git clone https://github.com/your-org/AI-Knowledge-Architect.git
cd AI-Knowledge-Architect

# 2. (Optional) Create virtual environment
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# 3. Install in editable development mode with dev dependencies
pip install -e ".[dev]"

# 4. Verify installation and run test suite
pytest -v
```

---

## 3. Project Architecture & Codebase Layout

```text
AI-Knowledge-Architect/
├── knowledge_retrieval/       # Core python package
│   ├── api.py                 # KnowledgeEngine unified facade
│   ├── agent.py               # KnowledgeAgent 6-stage lifecycle
│   ├── author.py              # DocumentAuthor & RetrievalVerifier
│   ├── researcher.py          # ResearchCollector & claim tracking
│   ├── profile.py             # KnowledgeLibraryProfile schema & validation
│   ├── retriever.py           # SQLite FTS5 BM25 search engine
│   ├── storage.py             # SQLite WAL schemas and transactions
│   ├── indexer.py             # Incremental indexer (SHA-256 + mtime)
│   ├── parser.py              # Markdown heading & frontmatter scanner
│   ├── integrity.py           # IntegrityAuditor (links & anchors)
│   ├── context.py             # ContextAssembler (token budgeting)
│   ├── auto_updater.py        # Autonomous update coordinator
│   ├── auto_update_store.py   # Sources, candidates, review queue
│   ├── change_detector.py     # Content fingerprint change detection
│   ├── evidence_verifier.py   # Authenticity, injection & conflict verification
│   ├── fetcher.py             # Safe HTTP/GitHub fetcher with SSRF defense
│   └── cli.py                 # knowledge-cli terminal interface
├── tests/                     # Automated pytest test suites
├── benchmarks/                # Multi-scale benchmarks (50, 500, 5000 docs)
├── docs/                      # Architectural specifications & audits
└── pyproject.toml             # Build and dependency configuration
```

---

## 4. Invariants and Architectural Rules

When proposing code changes, you must preserve our core invariants:

1. **Markdown is the Canonical Source of Truth:** Never store unique knowledge solely in SQLite. Deleting `.knowledge_index/` and running `knowledge-cli sync --rebuild` must reconstitute all search indices without loss.
2. **Untrusted Data Isolation:** All external content (web pages, GitHub releases, issues) is untrusted data. Never execute scripts or shell commands found in document bodies.
3. **Hard Filesystem Boundaries:** The knowledge root directory (`root_dir`) is unbreachable. Directory traversal attempts (`..`, leading slashes) must fail closed.
4. **Deterministic Testing:** Tests must use temporary directories, isolated databases, and local mock HTTP fixtures (`LiveMockServer`). Never depend on live internet connections in automated tests.
5. **Atomic File Swaps:** Never overwrite Markdown files directly. Write to a temporary file (`.tmp.<pid>.<time>`) and perform atomic replacement via `os.replace()`.

---

## 5. Development Workflow & Pull Request Process

### A. Branch Strategy
- Main development branch: `master` (or `main`).
- Create feature or bugfix branches:
  ```bash
  git checkout -b feat/your-feature-name
  # or
  git checkout -b fix/issue-description
  ```

### B. Commit Conventions
We follow Conventional Commits:
- `feat(component): add new capability`
- `fix(component): resolve identified defect`
- `test(component): add regression test cases`
- `docs(component): update architectural documentation`
- `refactor(component): code cleanup without behavior change`

### C. Pre-PR Checklist
Before opening a pull request, ensure:
```bash
# 1. All tests pass with zero regressions
pytest -v

# 2. Test multi-scale benchmark runs clean
python benchmarks/rigorous_benchmark.py

# 3. CLI help operates properly
knowledge-cli --help
```

### D. Pull Request Expectations
Each pull request description must include:
1. **Summary:** Problem being solved and proposed solution.
2. **Architecture Impact:** Files touched and invariant verification.
3. **Evidence:** Output of test run showing newly added and existing passing tests.
4. **Security Consideration:** Explanation of input validation or permission boundaries.

---

## 6. Reporting Issues & Vulnerabilities

- **Bug Reports & Feature Requests:** Please open an issue on GitHub with reproduction steps and sample Markdown content.
- **Security Vulnerabilities:** Do **NOT** open public issues for security vulnerabilities. See our [Security Policy](SECURITY.md) for private reporting instructions.
