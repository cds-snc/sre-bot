---
id: TASK-37.5
title: >-
  Webhooks slice 5: contract, delete legacy processing and enforce passthrough
  hardening
status: To Do
assignee: []
created_date: 2026-07-28 18:40
updated_date: '2026-11-25T20:51:00Z'
labels:
  - migration
  - webhooks
  - phase-4
milestone: m-4
dependencies:
  - TASK-37.4.3
references:
  - decisions/webhooks.md
  - decisions/reliability.md
  - decisions/feature-packages.md
  - https://github.com/cds-snc/sre-bot/issues/1380
  - decisions/plugin-architecture.md
  - decisions/plugins.md
parent_task_id: TASK-37
priority: high
ordinal: 100000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The contract step (decisions/migration.md; TASK-168 research packet section 5, row 37.5, Q4 item 12 and OQ7, OQ23). A single PR from main, after TASK-37.4.3 has every instance on the pipeline for the agreed soak (proposed: 7 days with no webhook_render_failed or unmatched spike).

Scope:
- Delete the legacy processing: app/modules/webhooks/ (the per-sender patterns and their import-time filesystem walk, the guessers select_best_model and validate_payload, the legacy route), validate_string_payload_type and has_parameters_in_model, the payload models in app/models/webhooks.py that no live module still imports, the test_legacy_only_ pins and the cutover flag; remove webhooks from _register_legacy_handlers(). Grep every importer first and repoint or delete it in the same PR.
- Enforce passthrough hardening on slack.passthrough, per the shadow fingerprints (TASK-37.4.2), with per-instance allowances only where the fingerprints show legitimate use: drop callback_id, action_id and block_id values that match ids registered by any feature; drop interactive elements without a url; drop parse and link_names; drop username, icon_*, thread_ts and reply_broadcast unless the instance allows them; add a "via webhook <instance name>" context line.
- bin/deploy-checks.zsh: the Non-JSON webhook pattern exclusion is removed (moved from TASK-168 AC #5).
- The legacy admin (modules/slack/webhooks*.py, modules/sre/webhook_helper.py) stays until TASK-37.6.2.

Size: delete-only plus ~60 production LOC of enforcement.
Production: prod.
Revert / blast radius: one revert restores the legacy path; every passthrough sender is affected by the enforcement.
Change notice: developer notice, action needed by a date: the dropped passthrough fields (bot button ids, username, icon_*, thread_ts, parse), sent at least two weeks before this merges and naming the senders the shadow found. User announcement: webhook messages show "via webhook <name>" (packet section 7.4).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/modules/webhooks/ is deleted and webhooks is removed from _register_legacy_handlers(); no payload guessing (select_best_model, validate_payload, validate_string_payload_type, has_parameters_in_model) and no filesystem-walk handler registration remain (grep)
- [ ] #2 The legacy route, the payload models in app/models/webhooks.py that no live module imports, the test_legacy_only_ pins and the cutover flag are deleted, and every importer was repointed or deleted (grep + test)
- [ ] #3 Passthrough hardening is enforced on slack.passthrough: registered callback_id, action_id and block_id values, interactive elements without a url, parse and link_names are dropped, and username, icon_*, thread_ts and reply_broadcast are dropped unless the instance allows them (test)
- [ ] #4 Webhook messages carry a "via webhook <instance name>" context line (test)
- [ ] #5 bin/deploy-checks.zsh post: the Non-JSON section's webhook pattern exclusion (added by TASK-28.2) is removed and any non-JSON line FAILs once import-time pattern discovery is gone
- [ ] #6 TASK-36 smoke tests pass; deprecated-import and import-linter baselines shrank or held (test + check)
- [ ] #7 The developer change notice (action needed by a date) went out at least two weeks before merge, and the PR body carries it and the user announcement (review)
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-25T20:51:00Z

---

2026-11-25 re-cut (TASK-168, human-approved; TASK-37.1 plan corrections C6-C10). Old title "Webhooks slice 5: multi-sink dispatch fan-out (registered-handler and durable-enqueue targets)". This id now carries the contract step; the old fan-out text moves to TASK-37.7. Old ACs, verbatim (short), and where each intent now lives:
- #1 "Dispatch supports multiple declared targets per webhook, each of exactly one kind: transport render, registered handler or durable enqueue" -> instance destinations and event consumers by type (TASK-37.2.1 AC #2 and #9); handlers by id (TASK-37.3 AC #5); the durable path is the inbox (TASK-37.2.2), on QueueService in TASK-37.7 AC #1.
- #2 "A feature registers a handler through the webhooks hookspecs extension point, collected once at startup; the capability never imports the feature, and no pluggy hook is called per request" -> TASK-37.2.1 AC #9 and TASK-37.7 AC #4.
- #3 "The durable-enqueue target uses the queue contract, or fails validation clearly until TASK-34 lands; no bespoke queue is introduced" -> TASK-37.7 AC #1 and #3.
- #4 "No in-process event dispatcher is used or introduced (grep: no dispatch_background, register_handler or blinker in the capability)" -> TASK-37.7 AC #3 (verbatim grep).
- #5 "TASK-36 smoke tests pass; existing Slack-render webhooks are unaffected" -> TASK-37.7 AC #5 (verbatim) and this task's new AC #6.
Old dependencies: TASK-37.4 (now the coordinator; this task waits on its last child TASK-37.4.3), TASK-34 and TASK-113 move to TASK-37.7. TASK-168 AC #5 (deploy-checks Non-JSON) is moved onto this task verbatim (AC #5, human-approved, correction C8). Nothing is archived.

---
<!-- COMMENTS:END -->
