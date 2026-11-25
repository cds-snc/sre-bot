---
id: TASK-37.4
title: >-
  Webhooks slice 4: backfill, shadow and cutover (coordinator of 37.4.1, 37.4.2,
  37.4.3)
status: To Do
assignee: []
created_date: 2026-07-28 18:40
updated_date: '2026-11-25T20:50:00Z'
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
  - https://github.com/cds-snc/sre-bot/issues/1379
  - decisions/plugin-architecture.md
parent_task_id: TASK-37
priority: high
ordinal: 99000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Coordinator only. Do not write production code against this task; pick up a child.

Expand, migrate, contract, per instance (decisions/migration.md; decisions/webhooks.md Migration; TASK-168 research packet Q8). URLs never change: the bare /hook/{id} is a durable contract.

Children, each a single PR from main after Stack W:
- TASK-37.4.1 Instance backfill (expand; prod data, inert): instance_ref, protocol, sender kinds, destinations, topic_arns and owner from the TASK-46 evidence, through a GitHub Actions workflow.
- TASK-37.4.2 Shadow (prod, inert): the new route behind a per-instance legacy | shadow | pipeline flag; the pipeline renders without posting and reports structural digests.
- TASK-37.4.3 Cutover (prod): instances move to pipeline after shadow parity, one SNS canary then all; acknowledge after persist; the /api/v1/hook decision; the pin-harness rewire; the TASK-190 padding AC; the alert button value moves to instance_ref plus the inbox item id (waits on Stack L's TASK-145.7.11).

The legacy processing is deleted after the soak in TASK-37.5, and the legacy admin in TASK-37.6.2.

Dependencies: the coordinator carries its first child's dependencies (TASK-145.5 and 145.10 precedent).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 TASK-37.4.1, TASK-37.4.2 and TASK-37.4.3 are Done
- [ ] #2 Every webhook instance serves on the pipeline path, or stays on legacy by a recorded decision (review)
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

created: 2026-11-25T20:50:00Z

---

2026-11-25 re-cut (TASK-168, human-approved; TASK-37.1 plan corrections C6-C10). Old title "Webhooks slice 4: cutover and delete modules/webhooks". This task becomes the coordinator of TASK-37.4.1 (backfill), TASK-37.4.2 (shadow) and TASK-37.4.3 (cutover). Old ACs, verbatim (short), and where each intent now lives:
- #1 "POST /hook/{webhook_id} and the admin surface are served by app/capabilities/webhooks via hookspec registration at both existing mount points; URLs unchanged" -> the route: TASK-37.4.2 AC #1 and TASK-37.4.3 AC #4 (mount decision); the admin surface: TASK-37.6.1 and TASK-37.6.2 AC #1.
- #2 "app/modules/webhooks/ is deleted and webhooks is removed from _register_legacy_handlers(); the legacy CRUD in modules/slack/webhooks.py is gone or relocated" -> TASK-37.5 AC #1 (processing) and TASK-37.6.2 AC #3 (CRUD).
- #3 "The capability declares its pyproject entry point and enablement key and loads via pm.load_setuptools_entrypoints; boot fails loudly if it does not" -> TASK-37.2.1 AC #1.
- #4 "TASK-36 smoke tests pass before and after cutover; deprecated-import and import-linter baselines shrank or held" -> TASK-37.4.3 AC #8, TASK-37.5 AC #6, TASK-37.6.2 AC #5.
- #5 "TASK-46 fingerprint emission and TASK-7 hardening are preserved on the new route" -> TASK-37.4.3 AC #7.
- #6 "The WAF Common Rule Set scope-down and the body cap cover both webhook mount points ..." -> TASK-37.4.3 AC #4 (verbatim).
- #7 "The TASK-36.2 pin harness is rewired at its named steps ..." -> TASK-37.4.3 AC #5 (verbatim); comment #2 (F-G) is carried in TASK-37.4.3's description.
The TASK-190 padding AC (delivery map row 21, "at pickup, add TASK-37.4 AC ...") is placed on TASK-37.4.3 (AC #3), where the cutover now happens. Comment #1 (the /api/v1/hook access-log check) applies to TASK-37.4.3 AC #4.
Old dependencies: TASK-110 and TASK-112 (Done) dropped; TASK-36.1.4 (admin pins) moves to TASK-37.6.2. Nothing is archived.

---
<!-- COMMENTS:END -->
