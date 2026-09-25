---
id: TASK-25.6
title: >-
  Bring Opsgenie onto the outbound-client contract: factory with explicit
  timeout, classify_opsgenie_error, business calls moved to their adapters
status: To Do
assignee: []
created_date: '2026-09-18 16:51'
updated_date: '2026-09-25 15:00'
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
parent_task_id: TASK-25
priority: high
ordinal: 239000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Created 2026-09-18 (human decision: every vendor in app/integrations/ conforms to decisions/outbound-clients.md; nothing is tolerated silently).

TODAY (verified 2026-09-18). app/integrations/opsgenie/client.py (153 lines):
- It holds business operations: get_on_call_users, get_on_call_user_for_rotation, create_alert and healthcheck, plus api_get_request/api_post_request on urllib.request.
- It has no factory and no classify_opsgenie_error.
- Its urlopen() calls (lines 121 and 131) pass NO timeout, so a hung Opsgenie blocks the caller indefinitely. outbound-clients.md requires every client to set a per-attempt timeout.
- Several broad 'except Exception' blocks log and swallow, so programmer errors become data.
- OPSGENIE_KEY is read into a module constant at import time, which is an import-time side effect.
- Settings live in infrastructure/configuration/integrations/opsgenie.py (TASK-24 owns that move).

CONSUMERS (re-grep before planning):
- packages/oncall_sync/adapters/opsgenie.py, a real Path B adapter that already maps OpsGenieAPIError to OnCallSyncError;
- modules/incident/on_call.py (get_on_call_users);
- jobs/scheduled_tasks.py (the healthcheck).

TARGET. The vendor package exports an authenticated HTTP client factory with an explicit timeout and a retry policy set once at construction (the planner picks the HTTP library; the codebase already uses httpx and requests), classify_opsgenie_error, and nothing else. The on-call and alert operations move into the adapters that need them: the oncall_sync adapter, and an adapter for the legacy incident and healthcheck call sites (a legacy caller may keep a thin module-local helper until TASK-38 migrates incident). create_alert is a non-idempotent write: name its idempotency mechanism (Opsgenie alias dedup) or send it with retries disabled.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/opsgenie/ exports only a client factory (explicit per-attempt timeout, retry configured once at construction) and classify_opsgenie_error; no business operation and no import-time settings read remain in the vendor package
- [ ] #2 Each consumer calls the client inside try/except + classify_opsgenie_error at its adapter boundary; unexpected exceptions propagate instead of being logged and swallowed
- [ ] #3 create_alert names its replay protection (alias dedup or retries disabled)
- [ ] #4 Classification tests cover each mapped failure family plus one unmapped exception propagating; factory tests assert the timeout and retry settings
- [ ] #5 ruff, mypy, pytest tests --ignore=tests/smoke and make check-vendor-package-contract pass, with output recorded in notes
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-24 20:11
---
2026-09-24 citation fix: decisions/layers.md, capability-packages.md and events.md were deleted and replaced by decisions/plugin-architecture.md (six layers: server, features, capabilities, infrastructure, integrations, contracts). Read those references in this task as plugin-architecture.md. Path A infrastructure capabilities are now split: hosting contracts (storage, coordination, queue, secrets) live in app/contracts/ with implementations in app/infrastructure/; workplace systems and shared business engines live in app/capabilities/. Path B adapters are unchanged (outbound-clients.md). Opsgenie business operations move to the adapters/ of their consumers: packages/oncall_sync (moving to features/oncall_sync in TASK-124.2) and the incident surfaces.
---

created: 2026-09-25 15:00
---
2026-09-25: whether the scheduled integration_healthchecks probe for this vendor survives is decided by TASK-127 (split from TASK-92). Migrate the probe's call path only; do not add or redesign a vendor probe here.
---
<!-- COMMENTS:END -->
