---
id: TASK-25.6
title: >-
  Bring Opsgenie onto the outbound-client contract: factory with explicit
  timeout, classify_opsgenie_error, business calls moved to their adapters
status: To Do
assignee: []
created_date: 2026-09-18 16:51
updated_date: '2026-10-23T18:48:00Z'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies: []
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/opsgenie/client.py
  - app/packages/oncall_sync/adapters/opsgenie.py
  - decisions/plugin-architecture.md
  - https://github.com/cds-snc/sre-bot/issues/1602
parent_task_id: TASK-25
priority: high
ordinal: 239000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Every vendor in app/integrations/ conforms to decisions/outbound-clients.md; nothing is tolerated silently.

TODAY. app/integrations/opsgenie/client.py (132 lines):
request, all re-exported from __init__.py.
- It has no factory and no classify_opsgenie_error.
- Its urlopen() calls (lines 121 and 131) pass NO timeout, so a hung Opsgenie blocks the caller indefinitely. outbound-clients.md requires every client to set a per-attempt timeout.
- Several broad 'except Exception' blocks log and swallow, so programmer errors become data.
- OPSGENIE_KEY is read into a module constant at import time (client.py:10), an import-time side effect.
- Settings live in integrations/opsgenie/settings.py; TASK-111.12 moves that slice onto the configuration files.

CONSUMERS (re-grep before planning):
- packages/oncall_sync/adapters/opsgenie.py, a real Path B adapter that already maps OpsGenieAPIError to OnCallSyncError (TASK-146.1 builds the on-call capability over this client, and TASK-146.2 makes oncall_sync a feature over it);
- modules/incident/on_call.py (get_on_call_users), which TASK-145.7 replaces;
- jobs/scheduled_tasks.py:141 (the integration healthcheck); TASK-127 decides whether that probe survives, so only its call path migrates here.
py).

TARGET. The vendor package exports an authenticated HTTP client factory with an explicit timeout and a retry policy set once at construction (the planner picks the HTTP library; the codebase already uses httpx and requests), classify_opsgenie_error, and nothing else. The on-call operations move into the adapters that need them: the oncall_sync adapter, and an adapter for the legacy incident and healthcheck call sites (a legacy caller may keep a thin module-local helper until TASK-145.7 rebuilds declare).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/opsgenie/ exports only a client factory (explicit per-attempt timeout, retry configured once at construction) and classify_opsgenie_error; no business operation and no import-time settings read remain in the vendor package
- [ ] #2 Each consumer calls the client inside try/except + classify_opsgenie_error at its adapter boundary; unexpected exceptions propagate instead of being logged and swallowed
- [ ] #3 No non-idempotent Opsgenie write remains without named replay protection
- [ ] #4 Classification tests cover each mapped failure family plus one unmapped exception propagating; factory tests assert the timeout and retry settings
- [ ] #5 ruff, mypy, pytest tests --ignore=tests/smoke and make check-vendor-package-contract pass, with output recorded in notes
<!-- AC:END -->
