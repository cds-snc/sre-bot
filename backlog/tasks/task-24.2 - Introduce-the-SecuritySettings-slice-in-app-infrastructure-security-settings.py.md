---
id: TASK-24.2
title: >-
  Introduce the SecuritySettings slice in
  app/infrastructure/security/settings.py
status: To Do
assignee: []
created_date: '2026-10-19 17:18'
labels:
  - clients
  - phase-3
  - configuration
milestone: m-3
dependencies: []
references:
  - decisions/configuration.md
  - decisions/plugins.md
parent_task_id: TASK-24
priority: medium
ordinal: 400000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2 of TASK-24 (decisions/configuration.md: the security domain owns a SecuritySettings slice). Security config is split today: DEV_BYPASS_ENABLED and CORS_ALLOWED_ORIGINS/METHODS/HEADERS with the wildcard validator on AppSettings (app/infrastructure/configuration/app.py), ISSUER_CONFIG and DEV_BYPASS_TOKEN with their validators on ServerSettings (app/infrastructure/configuration/infrastructure/server.py). The slice is built where security lives today; TASK-116 carries it to app/server/security/.

Consumers: server/server.py CORSMiddleware, infrastructure/security/current_user.py (dev bypass), infrastructure/security/jwks.py and server/lifespan.py (issuers). The slice validates in the lifespan configuration phase with the other host slices.

No rate-limit backend field: the limiter is in-process with one backend (human, 2026-10-19); the field arrives with a second backend. Env names unchanged (renames in TASK-111). Independent of Stack K.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 SecuritySettings in app/infrastructure/security/settings.py owns ISSUER_CONFIG, CORS_ALLOWED_ORIGINS/METHODS/HEADERS (with the wildcard-with-credentials validator), DEV_BYPASS_ENABLED and DEV_BYPASS_TOKEN; AppSettings and ServerSettings no longer define them
- [ ] #2 The CORS middleware, the dev bypass, JWKS and lifespan read SecuritySettings; the slice validates in the lifespan configuration phase
- [ ] #3 Env var names and defaults are unchanged
- [ ] #4 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
