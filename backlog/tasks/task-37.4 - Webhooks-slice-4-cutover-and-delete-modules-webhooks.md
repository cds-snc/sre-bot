---
id: TASK-37.4
title: 'Webhooks slice 4: cutover and delete modules/webhooks'
status: To Do
assignee: []
created_date: '2026-07-28 18:40'
updated_date: '2026-07-28 19:16'
labels:
  - migration
  - webhooks
  - phase-4
milestone: m-4
dependencies:
  - TASK-37.3
references:
  - decisions/webhooks.md
  - decisions/migration.md
  - decisions/plugins.md
  - 'https://github.com/cds-snc/sre-bot/issues/1379'
parent_task_id: TASK-37
priority: high
ordinal: 99000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 4 of the webhooks rearchitecture (decisions/webhooks.md; coordinator TASK-37). The strangler cut: the new package serves the routes and the legacy module is deleted. No zombie halves (decisions/migration.md).

Scope:
1. interactions/http.py: register POST /hook/{webhook_id} at BOTH current mount points (bare /hook/* and /api/v1/hook/*, per TASK-7 findings) and the admin CRUD routes via the register_routes hookspec (decisions/plugins.md). Handlers follow the five-step discipline (receive -> translate -> one service call -> OperationResult -> render). Port the TASK-46 origin-fingerprint emission onto this route.
2. interactions/slack.py: register the /sre webhooks admin slash-command surface via the register_slack hookspec, calling the service CRUD from TASK-37.1.
3. app/pyproject.toml: add the entry-point line under [project.entry-points."sre_bot"] (webhooks = "packages.webhooks") per decisions/plugins.md; remove webhooks from _register_legacy_handlers() and any legacy route mounting.
4. DELETE app/modules/webhooks/ entirely and the webhook CRUD in app/modules/slack/webhooks.py (relocate any still-referenced helper into the package). Prune app/models/webhooks.py of the models the package replaced (grep every importer first; keep only what other live modules still import).
5. Baselines (deprecated-import allowlist, import-linter) shrink or hold, never grow (decisions/migration.md).

Out of scope: multi-sink dispatch (TASK-37.5), HMAC (TASK-47).

Verify: grep every importer of modules/webhooks and models/webhooks before deletion (tests and possibly modules/slack import them); repoint or delete in the same PR series.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 POST /hook/{webhook_id} and the admin surface are served by app/packages/webhooks via hookspec registration at both existing mount points; URLs unchanged (test)
- [ ] #2 app/modules/webhooks/ is deleted and webhooks is removed from _register_legacy_handlers(); the legacy CRUD in modules/slack/webhooks.py is gone or relocated (grep)
- [ ] #3 The package declares its pyproject entry-point and loads via pm.load_setuptools_entrypoints; boot fails loudly if it does not (test)
- [ ] #4 TASK-36 smoke tests pass before and after cutover; deprecated-import and import-linter baselines shrank or held
- [ ] #5 TASK-46 fingerprint emission and TASK-7 hardening are preserved on the new route (test)
<!-- AC:END -->
