---
name: Tests Python Rules
description: Use for tests under app/tests; enforces location, naming, and focused assertions.
applyTo: app/tests/**/*.py
---

- Keep all tests inside app/tests.
- Use feature-prefix file names and avoid generic names.
- Cover both success and failure mapping paths for API tests.
- Use dependency overrides and fakes where possible for deterministic tests.
- Prefer minimal, behavior-focused assertions over implementation-detail assertions.
- Do not run `app/tests/smoke/*` by default; run smoke tests only when explicitly requested and required env vars are configured.
- Docstrings in test files must describe observable behavior, stub strategy, and assertion rationale only. Never reference external documents, task/ticket identifiers, sprint labels, plan step numbers, implementation phases, or transitory states (e.g. "before implementation", "AC#2 of TASK-X"). Docstrings must remain accurate regardless of project state.
