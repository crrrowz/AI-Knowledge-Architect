# Remaining Risks and Production Boundaries

**System:** AI-Knowledge-Architect  
**Auditor:** Senior Software Reliability Engineer  
**Date:** 2026-10-11  

---

## 1. Operational Boundaries and Documented Limitations

### A. SQLite Concurrency Ceiling
- **Condition:** SQLite supports infinite concurrent readers but serializes writers using a database-level lock.
- **Risk:** If hundreds of automated agent worker processes simultaneously attempt to run `check_updates` or write to SQLite, transactions will queue and could hit the 30-second busy timeout.
- **Operational Rule:** Keep update discovery runs serialized on a single coordinator thread or process.

### B. External Network Latency and Rate Limits
- **Condition:** Web scraping and GitHub API calls are subject to network round-trips and IP rate limits (e.g., GitHub unauthenticated 60 requests/hour; authenticated 5,000 requests/hour).
- **Risk:** Without `GITHUB_TOKEN` configured, monitoring multiple active GitHub repositories could trigger HTTP 429 / 403 Rate Limit errors.
- **Operational Rule:** Configure `GITHUB_TOKEN` in the execution environment for any high-frequency monitoring setup.

### C. Heuristic Prompt Injection Defense
- **Condition:** Prompt injection detection uses regex-based pattern matching (`INJECTION_PATTERNS`).
- **Risk:** Novel, heavily obfuscated, or multilingual jailbreak prompts might not match the specific regex signatures.
- **Operational Rule:** Retrieved knowledge excerpts should continue to be treated strictly as passive context data by downstream agent prompts, rather than as administrative directives.

### D. File System Case Sensitivity (Cross-Platform)
- **Condition:** Windows filesystems (NTFS) are case-insensitive; Linux filesystems (ext4) are case-sensitive.
- **Risk:** A document link `[[Net-Spec]]` resolves to `net-spec.md` on Windows, but may fail on Linux without lowercase normalization.
- **Operational Rule:** Always use lowercase slugified document IDs (`doc_id`) across cross-platform repositories.
