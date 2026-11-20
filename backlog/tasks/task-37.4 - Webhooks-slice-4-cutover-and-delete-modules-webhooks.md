---
id: TASK-37.4
title: 'Webhooks slice 4: cutover and delete modules/webhooks'
status: To Do
assignee: []
created_date: 2026-07-28 18:40
updated_date: '2026-11-20T15:18:00Z'
labels:
  - migration
  - webhooks
  - phase-4
milestone: m-4
dependencies:
  - TASK-37.3
  - TASK-110
  - TASK-112
  - TASK-36.1.4
references:
  - decisions/webhooks.md
  - decisions/migration.md
  - decisions/plugins.md
  - https://github.com/cds-snc/sre-bot/issues/1379
  - decisions/plugin-architecture.md
parent_task_id: TASK-37
priority: high
ordinal: 99000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Rescoped 2026-09-24: webhooks is a capability at app/capabilities/webhooks/ (decisions/webhooks.md, decisions/plugin-architecture.md), not a feature package. It reaches records, coordination, the queue and the Slack reply surface only through contracts resolved from the service registry, and imports no infrastructure/ or server/ module, so no slice adds an import-linter ignore entry. There is no in-process event bus: features react through the capability's extension point.

Slice 4 of the webhooks rearchitecture (decisions/webhooks.md; coordinator TASK-37). The strangler cut: the new package serves the routes and the legacy module is deleted. No zombie halves (decisions/migration.md).

Scope:
1. interactions/http.py: register POST /hook/{webhook_id} at BOTH current mount points (bare /hook/* and /api/v1/hook/*, per TASK-7 findings) and the admin CRUD routes via the register_routes hookspec (decisions/plugins.md). Handlers follow the five-step discipline (receive -> translate -> one service call -> OperationResult -> render). Port the TASK-46 origin-fingerprint emission onto this route.
2. entrypoints/slack.py: register the /sre webhooks admin slash-command surface via the register_slack hookspec, calling the service CRUD from TASK-37.1.
3. app/pyproject.toml: add the entry-point line under [project.entry-points."sre_bot"] (webhooks = "capabilities.webhooks") per decisions/plugins.md; remove webhooks from _register_legacy_handlers() and any legacy route mounting.
4. DELETE app/modules/webhooks/ entirely and the webhook CRUD in app/modules/slack/webhooks.py (relocate any still-referenced helper into the package). Prune app/models/webhooks.py of the models the package replaced (grep every importer first; keep only what other live modules still import).
5. Baselines (deprecated-import allowlist, import-linter) shrink or hold, never grow (decisions/migration.md).

Out of scope: multi-sink dispatch (TASK-37.5), HMAC (TASK-47).

Verify: grep every importer of modules/webhooks and models/webhooks before deletion (tests and possibly modules/slack import them); repoint or delete in the same PR series.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 POST /hook/{webhook_id} and the admin surface are served by app/capabilities/webhooks via hookspec registration at both existing mount points; URLs unchanged (test)
- [ ] #2 app/modules/webhooks/ is deleted and webhooks is removed from _register_legacy_handlers(); the legacy CRUD in modules/slack/webhooks.py is gone or relocated (grep)
- [ ] #3 The capability declares its pyproject entry point and enablement key and loads via pm.load_setuptools_entrypoints; boot fails loudly if it does not (test)
- [ ] #4 TASK-36 smoke tests pass before and after cutover; deprecated-import and import-linter baselines shrank or held
- [ ] #5 TASK-46 fingerprint emission and TASK-7 hardening are preserved on the new route (test)
- [ ] #6 The WAF Common Rule Set scope-down and the body cap cover both webhook mount points (/hook/ and /api/v1/hook/), or the duplicate mount is dropped by decision; the TASK-163 edge test's public-by-decision set matches the outcome
- [ ] #7 The TASK-36.2 pin harness is rewired at its named steps (mount_webhook_routes mounts through the plugin manager's register_routes as the edge route probe does; set_webhook_bot_state and the webhook_records fake move to the capability's fakes) with every assertion unchanged (test)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-06 (TASK-36.1.2 OQ1/OQ6, human-approved): legacy pin and cutover rules apply: decisions/migration.md recipe steps 2 and 4, decisions/transport-slack.md (legacy ids), decisions/testing.md (seams during the legacy migration); checklist in the implementation-planning skill (Legacy Surfaces). Rebuild/cutover task: pins pass with assertions unchanged; fixtures rewired to the target Protocol fakes and their seam-baseline entries removed; legacy_only_* tests for behaviour it ends deleted; modal-internal ids take the plugin prefix, ids on posted messages stay as legacy aliases; new tests in the strict zone (make check-test-seams, TASK-187).
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-20T14:47:00Z

---

2026-11-20 (TASK-36.2 OQ3/OQ6, human): AC #6's drop-the-duplicate-mount decision is taken on a production access-log check of /api/v1/hook since 2026-11-03 (TASK-163 opened it at the edge; before that the WAF allowed only /hook), run by the human; until then test_webhook_route_api_v1_mount_serves_route pins the mount. Dropping it is a migration.md step 4 named change.

---

created: 2026-11-20T15:18:00Z

---

2026-11-20 (TASK-36.2 finding F-G): tests/conftest.py replaces slack_bolt App.__init__ suite-wide with a MagicMock-client stub; the webhook pin harness restores the real constructor with unpatched_app_init (as build_bolt_app does). Keep that when rewiring the harness, or ops messages never reach the faked WebClient edge.

---
<!-- COMMENTS:END -->
