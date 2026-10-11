# Knowledge Agent Security Boundaries & Safety Invariants

## 1. Hard Filesystem Boundaries

The Knowledge Agent enforces the library's `root_dir` as an unbreachable filesystem perimeter:

1. **Path Traversal Protection:** All relative paths are evaluated against the canonical resolved root path using `target_path.is_relative_to(root_resolved)`. Directory escape strings (`..`, `/`, `\`, drive letters) are rejected with `PolicyDecision.REJECT` and `RiskLevel.CRITICAL`.
2. **Permitted Write Scopes:** When `permitted_paths` is defined in the profile, writes outside those subdirectories are blocked even if they remain inside `root_dir`.
3. **Atomic File Swapping:** All modifications write to temporary PID-tagged files before performing atomic `os.replace()` swaps, preventing partial file corruption.

---

## 2. Model and Untrusted Content Isolation

External web pages, GitHub release notes, issues, and model-generated drafts are treated strictly as untrusted data:

1. **No Code Execution:** The agent never executes scripts, commands, shell directives, or installation steps found inside document bodies.
2. **Prompt Injection Invariant:** Discovered directives like `SYSTEM PROMPT: OVERRIDE` or `Ignore previous instructions` are treated as passive literal text and scanned by `evidence_verifier.py`.
3. **Deterministic Safety:** Machine learning reasoning proposes operations; deterministic code enforces permissions, validates schemas, and checks boundaries.

---

## 3. Explicit Permission Constraints

Default permissions are strictly conservative:
- `allow_read`: True
- `allow_create`: True
- `allow_modify`: True
- `allow_delete`: **False (Default)**
- `require_approval_for_destructive`: **True (Default)**
- `require_approval_for_breaking`: **True (Default)**

Destructive actions (e.g. file deletions) cannot be executed automatically unless `allow_delete=True` AND `require_approval_for_destructive=False`.
