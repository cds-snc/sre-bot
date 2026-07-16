---
id: TASK-8
title: Install the recursive redaction processor in the structlog pipeline
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-08 16:56'
labels:
  - security
  - phase-0
  - observability
milestone: m-0
dependencies: []
references:
  - decisions/observability.md
  - 'https://github.com/cds-snc/sre-bot/issues/1262'
priority: high
ordinal: 8000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/observability.md (Redaction). Today mask_sensitive_data exists at app/infrastructure/logging/formatters.py:64 but is NOT in the structlog processor chain (the processor list at app/infrastructure/logging/setup.py:168-204 omits it), and it does not recurse into nested dicts/lists (SEC-7, CWE-532).

Steps:
1. Make the redaction processor recursive: walk nested dicts and lists, replacing values whose keys match the deny-list (token, secret, password/passwd/pwd, authorization, api_key, credentials, signature, session*, *_token, ...) with ***REDACTED***.
2. Install it in the processor chain in app/infrastructure/logging/setup.py, positioned before the JSON renderer so it cannot be skipped per-call.
3. Add a redaction_extra_keys setting for extension.
4. Scope note: the full pipeline rework (foreign chain, UTC timestamps, logger names) is task-28; only redaction lands here.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A log event containing {"config": {"api_token": "x"}} renders with ***REDACTED*** in place of the token value (pipeline test, not a unit test of the function alone)
- [ ] #2 Deny-list keys are matched case-insensitively and in nested lists of dicts
- [ ] #3 redaction_extra_keys extends the deny-list from settings (test)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Tests pass
- [ ] #2 PR references SEC-7 and decisions/observability.md
<!-- DOD:END -->
