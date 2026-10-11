# Knowledge Agent Operations & Workflow Guide

## 1. Quickstart CLI Guide

### A. Creating a Starter Profile
```bash
knowledge-cli profile-create ./my_library_profile.yaml \
  --id "platform-knowledge" \
  --root "./knowledge/platform" \
  --goal "Maintain core architectural and operational specifications"
```

### B. Validating a Profile File
```bash
knowledge-cli profile-validate ./my_library_profile.yaml
```

### C. Inspecting a Knowledge Library
Gathers inventory, identifies missing topics, and audits integrity without modifying any files:
```bash
knowledge-cli agent-inspect ./my_library_profile.yaml
knowledge-cli agent-inspect ./my_library_profile.yaml --json
```

### D. Planning Operations
Generates a structured plan of operations satisfying profile goals:
```bash
knowledge-cli agent-plan ./my_library_profile.yaml
```

### E. Dry-Run (Previewing Changes)
Simulates execution and validates policies without writing any changes to disk:
```bash
knowledge-cli agent-run ./my_library_profile.yaml --dry-run
```

### F. Live Agent Execution & Verification
Executes approved operations, updates Markdown files with provenance, reindexes SQLite FTS5, and verifies results:
```bash
knowledge-cli agent-run ./my_library_profile.yaml
```

---

## 2. Python Agent API Usage

```python
from knowledge_retrieval.agent import KnowledgeAgent
from knowledge_retrieval.profile import KnowledgeLibraryProfile

# 1. Load Profile
profile = KnowledgeLibraryProfile.load("my_library_profile.yaml")

# 2. Instantiate Agent
agent = KnowledgeAgent(profile)

# 3. Inspect (Read-Only)
inspection = agent.inspect()
print(f"Total documents: {inspection.total_docs}")
print(f"Missing expected: {len(inspection.missing_expected_docs)}")

# 4. Plan & Policy Check
plan = agent.plan(inspection)
agent.policy_check(plan)

# 5. Preview via Dry Run
preview_report = agent.execute(plan, dry_run=True)
print(f"Previewed operations: {len(preview_report.completed_operations)}")

# 6. Live Execution and Independent Verification
live_report = agent.execute(plan, dry_run=False)
print(f"Verified operations: {live_report.verification_evidence['verified_operations_count']}")
```
