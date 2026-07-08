---
id: TASK-2
title: 'Fix production CORS: explicit origin allow-list with boot-time validator'
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
labels:
  - security
  - phase-0
milestone: m-0
dependencies:
  - TASK-1
references:
  - decisions/security.md
priority: high
ordinal: 2000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/security.md (CORS). Today app/server/server.py:21-28 sets allow_origins=["*"] when not bool(app_settings.PREFIX), combined with allow_credentials=True at line 32 - i.e. production gets wildcard origins WITH credentials (SEC-1, OWASP API8:2023).

Steps:
1. Add a CORS_ALLOWED_ORIGINS list field to settings (the SecuritySettings slice if task-24 has landed, otherwise app settings).
2. In app/server/server.py, pass the configured list to CORSMiddleware. Never compute origins from environment shape.
3. Add a boot-time validator (settings model validator or lifespan phase-1 check) that raises if "*" appears in the origins list while allow_credentials is true - in EVERY environment.
4. Populate real origins per environment in deployment config.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 CORSMiddleware receives an explicit origin list from settings; no wildcard logic remains in app/server/server.py
- [ ] #2 Boot fails with a clear error when config contains "*" origins together with credentials (test exists)
- [ ] #3 grep: allow_origins is never computed from ENVIRONMENT/PREFIX conditionals
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Tests pass; new boot-validator test included
- [ ] #2 Per-environment origin lists set in deployment config
- [ ] #3 PR references SEC-1 and decisions/security.md
<!-- DOD:END -->
