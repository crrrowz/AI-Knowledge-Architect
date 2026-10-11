# Security Policy

The **AI-Knowledge-Architect** project treats security as a foundational engineering requirement. Because this system ingests external web pages and documentation feeds while managing local files, we maintain strict defensive boundaries.

---

## 1. Supported Versions

| Version | Supported | Notes |
| :--- | :--- | :--- |
| `0.1.x` | :white_check_mark: | Current active release branch. Receives security patches. |
| `< 0.1.0` | :x: | Development prototypes. Not supported. |

---

## 2. Reporting a Vulnerability

If you discover a security vulnerability or bypass in `AI-Knowledge-Architect`, please report it responsibly.

### How to Report Privately
- **GitHub Security Advisory:** Please submit a report through GitHub's Private Vulnerability Reporting interface (Security tab -> "Report a vulnerability").
- **Email:** If private vulnerability reporting is unavailable, email `security@ai-knowledge-architect.local` with the subject `[SECURITY VULNERABILITY] <Component Name>`.

**Please DO NOT open a public GitHub issue for security vulnerabilities.**

### Information to Include in Your Report
To help us triage and remediate quickly, please include:
1. **Component affected:** (e.g. `fetcher.py`, `knowledge_updater.py`, `profile.py`).
2. **Vulnerability type:** (e.g. SSRF bypass, Path Traversal, Injection Bypass, Logic Error).
3. **Reproduction steps:** Minimal Python script or command sequence demonstrating the vulnerability.
4. **Impact assessment:** What files or system capabilities can be accessed or altered.
5. **Proposed fix / mitigation:** (if known).

---

## 3. Response Process & Timeline

- **Initial Acknowledgment:** Within **48 hours** of receiving the report.
- **Triage & Reproduction:** Within **5 business days**.
- **Fix & Patch Release:** We aim to release a patch and publish a security advisory within **14 days** of confirmation, depending on complexity.
- **Public Disclosure:** Coordinated disclosure after the patch has been released.

---

## 4. Threat Model & Security Scope

### In-Scope Security Boundaries
- **Server-Side Request Forgery (SSRF):** `validate_url_safety()` and `SafeRedirectHandler` in `fetcher.py` must prohibit connections to loopback (`127.0.0.1`), private RFC-1918 subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local metadata addresses (`169.254.169.254`), and non-HTTP schemes.
- **Path Traversal Protection:** Target paths in `knowledge_updater.py` and `profile.py` must be strictly validated to prevent writes escaping the configured library `root_dir`.
- **Credential Protection:** Tokens (e.g. `GITHUB_TOKEN`) must never be leaked into SQLite indices, audit logs, or generated Markdown files.
- **Untrusted External Content:** Discovered web pages, issues, and release notes must be treated strictly as passive data, sanitized of `<script>` and `<style>` tags, and scanned for prompt injection directives.

### Out-of-Scope / Non-Vulnerabilities
- Downstream Language Model behavior: The engine retrieves text passages as passive context. If a downstream LLM chooses to execute text found within an excerpt, that is an agent harness configuration issue, not a vulnerability in the retrieval engine.
- Intentional local administrator access: Access granted to local users who already possess local shell write privileges on the host machine.
