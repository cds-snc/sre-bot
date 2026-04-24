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
