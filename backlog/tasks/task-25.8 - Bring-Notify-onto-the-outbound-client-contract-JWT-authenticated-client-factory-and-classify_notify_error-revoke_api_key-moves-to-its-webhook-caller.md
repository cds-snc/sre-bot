---
id: TASK-25.8
title: >-
  Bring Notify onto the outbound-client contract: JWT-authenticated client
  factory and classify_notify_error; revoke_api_key moves to its webhook caller
status: To Do
assignee: []
created_date: '2026-09-18 16:51'
updated_date: '2026-09-24 20:11'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies: []
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/notify/client.py
  - app/modules/webhooks/patterns/aws_sns_notification/api_key_detected.py
  - decisions/plugin-architecture.md
parent_task_id: TASK-25
priority: medium
ordinal: 241000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Created 2026-09-18 (human decision: every vendor conforms to decisions/outbound-clients.md).

TODAY (verified 2026-09-18). app/integrations/notify/client.py (167 lines) holds:
- JWT creation (create_jwt_token, create_authorization_header);
- a raw requests.post helper (post_event, timeout=60, no retry policy);
- a business operation, revoke_api_key(api_key, api_type, github_repo, source).
It reads settings at import time (notify_settings = get_notify_settings()) and also imports infrastructure.configuration.app. It has no classify_notify_error.

CONSUMER (re-grep): modules/webhooks/patterns/aws_sns_notification/api_key_detected.py, the only one. TASK-37 (webhooks rearchitecture) later rewrites that caller, so keep its change minimal.

TARGET. The vendor package exports a factory for an authenticated HTTP client (JWT auth, explicit timeout, retry configured once) and classify_notify_error. revoke_api_key moves next to its caller as an adapter-shaped function that does try/except + classify. Revoking a key is idempotent at the provider (verify and record this); if it is not, name the replay protection.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/notify/ exports only the client factory (JWT auth, explicit timeout, retry configured once) and classify_notify_error; no business operation and no import-time settings read remain
- [ ] #2 revoke_api_key lives with its caller, calls the client inside try/except + classify_notify_error, and its replay behaviour is recorded
- [ ] #3 Classification tests cover each mapped failure family plus one unmapped exception propagating; JWT header construction keeps its test coverage
- [ ] #4 ruff, mypy, pytest tests --ignore=tests/smoke and make check-vendor-package-contract pass, with output recorded in notes
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-24 20:11
---
2026-09-24 citation fix: decisions/layers.md, capability-packages.md and events.md were deleted and replaced by decisions/plugin-architecture.md (six layers: server, features, capabilities, infrastructure, integrations, contracts). Read those references in this task as plugin-architecture.md. Path A infrastructure capabilities are now split: hosting contracts (storage, coordination, queue, secrets) live in app/contracts/ with implementations in app/infrastructure/; workplace systems and shared business engines live in app/capabilities/. Path B adapters are unchanged (outbound-clients.md). revoke_api_key moves to its caller. Today that is the modules/webhooks SNS pattern. When TASK-37 rebuilds webhooks as a capability, the key-revocation reaction belongs to the feature that registers a handler through the webhooks extension point (TASK-37.5), not the capability core.
---
<!-- COMMENTS:END -->
