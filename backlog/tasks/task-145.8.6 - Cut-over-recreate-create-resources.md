---
id: TASK-145.8.6
title: Retire /sre incident create (create resources and the create new stub)
status: In Progress
assignee: []
created_date: '2026-11-09T19:06:00Z'
updated_date: '2026-11-17T16:29:00Z'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.8.1
  - TASK-145.7.5
  - TASK-145.7.6
  - TASK-145.8.2
references:
  - decisions/incident-management.md
parent_task_id: TASK-145.8
priority: medium
type: feature
ordinal: 511000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L7b. The production usage count (90 days: create resources 0, create new 1, bare create 3) retires the whole /sre incident create node as a kind (d) named change (migration.md step 4, :67). recreate_missing_resources, _create_database_record, handle_create, recreate_missing_incident_resources, their orphaned helpers and tests are deleted; the primary move is TASK-165.11's; the one-conversation loop is TASK-145.7.9's.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 /sre incident create is retired: bare create, create new and create resources answer the dispatcher's unknown-command reply and the help text no longer lists create (surface-pinned); handle_create, recreate_missing_incident_resources, the recreate functions of modules/incident/core.py, _create_database_record and their tests are deleted (checks parent ACs #1 and #5)
- [x] #2 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
- [x] #3 Every helper the retirement orphans is deleted with its tests (list_folder_files, find_document_by_channel_name), with rg evidence in the PR body; helpers the legacy declare, show or close still use are kept (channel_slug, incident_document functions, meet.create_space)
- [x] #4 The PR body states the revert target: one git revert restores the legacy surface, and the L5r rollback guard (TASK-145.8.2) keeps it reading and writing upgraded items correctly (decisions/incident-management.md Migration rule 1)
- [x] #5 The PR body lists two named changes of kind (d) with the usage count (create resources 0, create new 1, bare create 3, 90 days, Logs Insights on /ecs/sre-bot-app) and the revert target; code, README and ADR text no longer name recreate as a live surface (domain.py, google_meet.py, features/incident/README.md, decisions/incident-management.md :34, :36, :42, :50 and a Changes line)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLAN 2026-11-17, re-planned after the production usage count (comment #5 rule; comment #6 holds the AC proposal and the rest). Proposed, awaiting human approval. This replaces the earlier two-slice cutover plan: the task is a RETIREMENT of `/sre incident create`, one PR, mostly deletion.

0. Ruling that drives it
- Logs Insights on /ecs/sre-bot-app, 90 days, event sre_incident_command_received with args[0]=create: args[1]=resources 0, new 1, no args[1] 3 (human, 2026-11-17). Comment #5 ruled "unused -> retire create resources and the create new stub as kind (d)". migration.md step 4 kind (d) is "a surface retired with no target"; the feature parity trap is rejected (migration.md :67). The primary move went to TASK-165.11 (doc-15 row 8a); the I1-I5 loop is declare's (TASK-145.7.9), attach-later is TASK-165.5 AC #2.
- Legacy surface being deleted (survey at 8a7d6bf6): modules/incident/incident_helper.py `get_incident_actions` key "create" (:162), `handle_create` (:237-255, answers "Upcoming feature" for `new`, the create help for a bare `create`, recreate for `resources`), `recreate_missing_incident_resources` (:540-627); modules/incident/core.py:39-419 (_get_channel_info_and_topic, _get_existing_bookmarks, _find_product_folder, _create_meet_link_bookmark, _create_document_bookmark, _add_incident_to_sheet, _create_database_record, recreate_missing_resources). It never created a channel; the only legacy-item writer it holds is _create_database_record (core.py:316), which incident-management.md Migration rule 6 (:146) names as a writer to remove before the final backfill rerun.

1. Stack base and merge order
- Recommend (a) above L7a.1 (branch stack-l/task-145.8.6-recreate; the task and PR may be renamed, see comment #6). Retirement removes every functional need from L6b and L7a.1 (no StageOutcome, no entrypoint, no core port), so a side PR from main is functionally possible. It is not conflict-free, though: L6b+L7a.1 edit the same files, `git diff -U0 main..8a7d6bf6 -- modules/incident/incident_helper.py` shows hunks at (main numbering) 27, 35, 63 and 108 (the two help texts), 146-155, 180-192, 203, 366, 577; this PR edits the help texts at the create bullet and the `/sre incident create` example (HEAD lines 58, 68, 103, 113), `get_incident_actions` (:162), `handle_create` (:237) and :540-627; the help-text hunks are within a few lines of L6b's. It also edits tests/modules/incident/test_incident_helper.py (L6b -190, L7a.1 -37 lines) and L7a.3 (TASK-145.8.5.3) deletes handle_close (:232-235) one blank line above handle_create (:237) and removes incident_status.py: adjacent hunks, likely a trivial textual conflict whichever of the two merges second. Stack above L7a.1 keeps the in-review PRs (#1859, #1862) untouched and puts the textual conflict in stack order (restack of L7a.3 over this PR is a `git rebase --onto`, no semantic overlap). A side PR from main buys independent merge and revert at the price of rebasing #1859/#1862 or this PR twice; not recommended while both are in review.
- Merge order L6b #1859 -> L7a.1 #1862 -> this PR. L7a.3 and L6a stack above it.

2. Steps (TDD order; all from app/)
2.1 Pin the post-retirement answers first (red before the delete). New app/tests/integration/legacy_surface/test_incident_create_retired_surface.py through the Bolt dispatch boundary with the existing harness (legacy_handler_harness, routed_slack_client; precedent test_incident_status_command_surface.py): bare `create`, `create new`, `create resources` each answer the dispatcher's existing unknown-subcommand reply "Unknown command: create. Type `/sre incident help` to see a list of commands." (incident_helper.py:228-229, ephemeral respond), with no Slack write, no Drive/Sheet/Meet call and no db_operations write (FakeIncidentTable asserts zero puts); `/sre incident help` and `aide` no longer list `create` (the bullet and the example), still list `create-folder`'s siblings unchanged. This is what a user sees: one line pointing at help, which no longer lists create. Add an INVENTORY.md row (deleted by TASK-145.13). No seam: fakes at external edges only; if the harness needs one it goes in a named legacy_surface/conftest.py fixture `Owning rebuild task: TASK-145.8.6` with its app/bin/baselines/test_seams_legacy.txt entry in this PR. Before editing, run the pin against the legacy code to see it fail for the right reason, and confirm there is no second `create` route (registrar-registered sre.incident subcommands in features/incident/response/entrypoints/slack.py do not define create): assumption, verified here.
2.2 Delete the legacy surface (production, about 520 lines):
  - modules/incident/core.py:39-419 (381 lines) and the imports ruff then finds unused: `incident_drive` (core.py:11, only user :185), `channel_slug` (core.py:22, only users :180 and :256; the declare path does not use it). Keep: channel_url (core.py:198 dies, but :265 dies and :434 declare keeps it), _security_answer_to_flag (declare, :523), initiate_resources_creation, incident_document, meet, on_call, db_operations, incident_folder, get_incident_response_settings.
  - modules/incident/incident_helper.py: the "create" key (:162), handle_create (:237-255), recreate_missing_incident_resources (:540-627), the `• create` bullet in help_text (:58) and help_text_fr (:103), the `/sre incident create` example lines (:68, :113), and imports ruff reports unused (slack_users, incident_drive, re and datetime stay: used at :335, :385, :451, :525-534). About 112 lines.
  - features/incident/core/adapters/google_docs.py: list_folder_files (:293-299, its only production caller was core.py:185) and find_document_by_channel_name (:346-361, no production caller at 8a7d6bf6: `rg find_document_by_channel_name app` finds the definition and tests only; a pre-existing orphan in the same file, deleted under the delete-dead-code rule). Keep get_metadata, add_metadata, delete_metadata (legacy_roles.py, google_docs.py:394, incident_folder.py), _list_all (list_child_folders). About 24 lines.
  - Kept with evidence (rg at the plan date): incident_folder.channel_slug (:382) is used by return_channel_name (:392), whose callers are information_update.py:315 and incident_status.py:57 (deleted by TASK-145.8.3 and TASK-145.8.5.3, not here); incident_document.create_incident_document and update_boilerplate_text are used by the legacy declare (core.py:492, :611); meet.create_space by declare (core.py:459); on_call.get_on_call_users_from_folder by declare (core.py:432); incident_folder.list_incident_folders/add_new_incident_to_list/get_incidents_from_sheet and db_operations.create_incident/get_incident_by_channel_id keep live callers (declare, dev incident commands, show, close). Re-run these rg checks at implementation and record the output in the PR body.
2.3 Delete the tests of the deleted code (about 540 lines): tests/modules/incident/test_recreate_missing_resources.py (430 lines, whole file); tests/modules/incident/test_incident_core.py:1053-1066 (test_recreate_database_record_leaves_security_incident_unset); tests/modules/incident/test_incident_helper.py:169-210 (the three handle_create tests; keep test_handle_help); the list_folder_files and find_document_by_channel_name cases in tests/unit/features/incident/core/test_incident_core_google_docs_drive.py (:64-70, :99-118 and their parametrised rows :128, :132, :155) and the two calls in test_incident_core_report_no_delegation.py:86,90 (adjust the `>= 8` count). Check test_legacy_handler_registration_surface.py and test_slack_command_registration_surface.py for an enumerated `create` action and edit the expectation.
2.4 Text that names recreate as a live surface (edits, not behaviour): features/incident/core/domain.py:316-318 (ReferenceKind docstring: "a recreated channel never moves the record's conversation" becomes "the conversation and the source alert are set only by create and attach_conversation") and :550 ("declare and recreate try" becomes "declare tries"); core/adapters/google_meet.py:8 and tests/unit/features/incident/core/test_incident_core_video_call_create_space.py:3 ("legacy declare and recreate" becomes "legacy declare"); tests/unit/features/incident/core/test_incident_core_incident_store_attach_conversation.py:103 (docstring "Moving the primary conversation is recreate's job" becomes "...is the rebind's, TASK-165.11"); features/incident/README.md:28 and :84-85 (recreate leaves the legacy-writer list: the writers left are the legacy declare, the dev add command and the sheet import) and its rerun rule; decisions/incident-management.md: Changes line plus the :34, :36 (incl. rule 5), :42, :50 edits listed in comment #6. These ride in this PR (no standalone docs PR).
2.5 Gates once at the end, sequential: ruff, mypy (baseline 40 errors in 13 files, no new), lint-imports, make check-package-shape, make check-test-seams, then pytest tests --ignore=tests/smoke.

3. AC traceability (proposed ACs in comment #6; #2 and #4 unchanged)
- New AC "retired surface": 2.1 pin, 2.2 deletions, 2.3 test deletions.
- New AC "orphans deleted, live helpers kept": 2.2 rg evidence in the PR body.
- New AC "named change and docs": 2.4 and the PR body.
- #2 -> 2.5. #4 -> section 5.

4. Named changes for the PR body (migration.md step 4)
- N-retire-1 (d): `/sre incident create resources` retired, 0 uses in 90 days (Logs Insights, /ecs/sre-bot-app, sre_incident_command_received, args[0]=create, args[1]=resources). The legacy record-creating branch (_create_database_record) goes with it; recreating resources has no target (declare owns resource creation; a retry is declare's idempotent replay).
- N-retire-2 (d): the `create new` stub ("Upcoming feature: create a new incident.") retired, 1 use in 90 days; /incident declares. Bare `create` (3 uses) answered the create help; it now answers the unknown-command reply.
No kind (a), (b) or (c) change, no addition, no fr-FR text. No pointer reply is added (OQ-A in the comment): counts of 0, 1 and 3 do not justify a surface to delete again in TASK-145.13.

5. Assumptions, blast radius, rollback
- Assumes the counts cover the retention window and the three "bare" calls are help lookups (the old reply was the create help). The pin tests what they now see.
- Assumes no other task calls the deleted functions: rg over backlog/tasks and doc-11 shows only the 145.8.6 and parent 145.8 texts; TASK-145.7.8 (L8) waits on this PR, which is satisfied by deleting the legacy recreate item writer.
- Revert target (AC #4, incident-management.md Migration rule 1): one git revert restores the legacy `create resources`, `create new` and the old help text. Its only item-writing path is `db_operations.create_incident` when `get_incident_by_channel_id` finds no item; for an item upgraded to marker 2 the channel_id lookup copy is still written (kept until TASK-145.13), and the L5r rollback guard (TASK-145.8.2, merged) keeps the legacy readers and writers correct on upgraded items. Nothing in this PR writes a new-shape item, so the revert does not strand data.
- Blast radius: one slash subcommand and two help texts; Slack users who typed `create` get the unknown-command line.

6. Size
Production code is deleted, not added: about 520 production lines deleted (core.py 381, incident_helper.py 112, google_docs.py 24) and 0 added apart from docstring and comment rewording (about 8 lines). Tests: about 540 lines deleted, about 70 added (the retirement pin). Docs: about 15 ADR/README lines. Files: about 18 touched, of which 6 production (core.py, incident_helper.py, google_docs.py, domain.py, google_meet.py, README) and the rest tests and docs. A delete-dominant PR is not bound by the single-PR size gate (CLAUDE.md: a PR that only deletes is not bound); this PR adds one pin test and wording, nothing behavioural, and mixes no refactor with a behaviour change. No decomposition needed.

7. Dropped from the earlier plan (why, in comment #6)
bookmarks() and find() ports, set_reference upgrade-on-write (OQ13), report title/placement, on-call boilerplate, the recreate service and Slack entrypoint, the list-row re-upsert, N1-N7, the fr-FR keys, the HTTP route and the two-slice split.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-10 (TASK-145.7.7): attach_conversation returns INCIDENT_RECORD_CONFLICT for a primary binding when the record names another conversation; moving the primary on recreate is this task's.

2026-11-17: production usage over 90 days (human, Logs Insights on sre_incident_command_received, args[0]=create): resources 0, new 1, bare 3. By the OQ1 follow-up rule: retire create resources and the create new stub as kind (d); re-plan as a retirement.

2026-11-17: implemented on the working tree above L7a.1 (8a7d6bf6); the branch stack-l/task-145.8.6-retire-create was not created yet (gh stack add did not run), so the human creates it before committing.
- Pin first: app/tests/integration/legacy_surface/test_incident_create_retired_surface.py (5 tests) red on legacy for the right reasons (create help, the Upcoming feature stub, the recreate run; both help texts listed create), green after the delete. It asserts the dispatcher's unknown-command line, the provider's locale read (users_info) as the only Slack call, and unchanged incidents table, Drive, Docs and Sheets fakes; help and aide no longer list create while create-folder and products create stay. INVENTORY.md row added (pin deleted by TASK-145.13).
- Deleted: modules/incident/core.py recreate functions (386 lines, imports incident_drive, channel_slug, Any), incident_helper.py handle_create, recreate_missing_incident_resources, the create key, both help bullets and examples, the core import (118 lines), google_docs.py list_folder_files and find_document_by_channel_name (24 lines); tests test_recreate_missing_resources.py, test_recreate_database_record_leaves_security_incident_unset, the three handle_create tests, the two Drive helpers' cases (the unclassified-error test now calls list_child_folders) and their no-delegation calls (count >= 6).
- rg evidence: no reference left to list_folder_files, find_document_by_channel_name, recreate_missing*, _create_database_record, handle_create; kept with live callers: channel_slug (incident_folder.py:392 return_channel_name), create_incident_document (core.py:106), update_boilerplate_text (core.py:225), meet.create_space (core.py:73), all legacy declare.
- Wording: domain.py ReferenceKind docstring and CONVERSATION_NAME_ATTEMPTS, google_meet.py, on_call.py, two test docstrings, features/incident/README.md (lifecycle row, legacy writers now three, create_space line); decisions/incident-management.md :34 (rebind TASK-165.11, bots cannot unarchive), :36 (declare owns the loop at response/service/conversation.py, 165.5 reuses it; rule 5), :42, :50, the :115 test line, and a 2026-11-17 Changes line. Migration rule 6 unchanged (recreate 'until TASK-145.8's' stays true).
- Diff: 22 insertions, 1068 deletions over 16 files plus the new pin (~75 lines). Production code: 0 lines added except wording.
- Gates: ruff check and format clean; import contracts 14 kept; settings key ownership OK; package shape OK (3 baselined); test seams OK (47/12 baselined); mypy 40 errors in 13 files (baseline, none new); pytest tests --ignore=tests/smoke 7555 passed.
- AC #4 and #5 are PR-body ACs: the body is prepared (session scratchpad pr-145.8.6.md) with the revert target and both kind (d) named changes.

2026-11-17: submitted as #1865 (stack-l/task-145.8.6-retire-create, ddac794d above L7a.1 a366d6de after #1859 merged; tree identical to the gated commit cea53e52). Top of Stack L: stays open until L7a.3 is added above it.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-10T20:12:00Z

---

2026-11-10 scope from TASK-145.7.5 (approved by the human): conversation creation follows incident-management.md one-channel-per-incident rules I1-I5 (TASK-145.7.5 plan 1.a4). Candidates from core/conversation_names.incident_conversation_names (legacy format, Slack-safe slug, bare name then -2..-5). I1 a record that names a conversation never creates one. I2 claim each candidate name for the incident through the IdempotencyStore (key incident:conversation_name:<tenant>:<name>); skip a name another incident claimed. I3 after any non-success create (name_taken, transient, unclassified exception or timeout) call IncidentConversation.find_own(name) first; the bots own channel bound to this incident, or unbound while this incident holds the claim, is bound and reused. I4 the same name may always be retried; the next suffix only when the channel is proven another incidents or not the bots. I5 an unknown outcome with nothing found reports the error (one warning, the pinned invoker message) without moving on; recreate retries the same name. CONVERSATION_NAME_TAKEN is an expected outcome logged at info. Plan this in full at pickup, with tests for each rule.

---

created: 2026-11-16T15:51:00Z

---

2026-11-16 (human, TASK-145.8.4 OQ4): decisions/migration.md step 4 amended (rides with L6b): a cutover changes behaviour only as a named change of kind (a) legacy bug no pin asserts, (b) behaviour an accepted end-state ADR replaces, (c) expired deprecated form after a usage check, (d) retired surface; additions only by an explicit plan ruling. At planning, classify each behaviour change of this task by kind, pin it (test_legacy_only_* or edited pin citing the ruling) and list it in the PR body.

---

created: 2026-11-17T14:58:00Z

---

2026-11-17 planning comment (TASK-145.8.6, L7b). Plan written; nothing else touched (no AC, status, other task, doc-11 or doc-16 edited). Open questions with ADR status, upcoming rows, practice and a recommendation each.

STACK BASE (decision 1). Recommend (a): new branch stack-l/task-145.8.6-recreate above L7a.1 (8a7d6bf6). Evidence: `git diff --stat main..7a07ac8e` (L6b) gives response/service/status.py, entrypoints/slack.py, providers.py, plugin.py, locales, incident_helper.py, INVENTORY.md and tests/factories/incident.py, all of which L7b edits or reuses (StageOutcome/StageResult, the register/_refusal/incident_scope pattern). `git diff --stat 7a07ac8e..8a7d6bf6` (L7a.1) adds service/roles.py, slack_roles.py, core api.py (+75, purpose), adapters/slack.py, in_memory.py, legacy_roles.py, the same locales/providers/slack.py/incident_helper.py and the same INVENTORY and legacy conftest. L7b needs from L6b: the stage types and entrypoint pattern (functional). From L7a.1: nothing functional (purpose, roles fields, legacy_roles_reader are unused), but it edits the same hunks in api.py, adapters/slack.py, in_memory.py, entrypoints/slack.py, locales, providers.py and incident_helper.py, so putting L7b below L7a.1 (b) would force rebasing #1862 for textual reasons only and dismiss its approvals again. Merge order L6b #1859 -> L7a.1 #1862 -> L7b slice 1 -> slice 2. L7a.3 and L6a can stack above L7b later (they touch incident_helper.py and the legacy update path; no overlap with recreate beyond the incident_helper.py import block and INVENTORY). Slice 1 is dark and could be a side PR from main, but api.py/in_memory.py/slack.py adjacency to L7a.1 makes a rebase conflict likely; stack it.

OQ1 Is recreate a channel recreation? ADR: CONFLICT/gap. incident-management.md:34 ("moving it is recreate's"), :36 ("Declare and recreate own the loop"; rule 1: an incident whose record names a conversation never creates one; rule 5: recreate retries the same name), :42 ("a replaced resource (a recreated channel) is a new map") assume recreate makes channels; the legacy never does (core.py:336-419 fills bookmarks, report, list row, DB record inside the invoking channel), and domain.py:316-318 says the opposite (a recreated channel never moves the conversation). Rule 1 conflicts with AC #3 whenever the record names a (dead) conversation. A slash command run inside a channel cannot recreate that channel. Upcoming row: 145.7.9 (L9a) builds the same loop, after L7b. Practice: no vendor documents replace-and-move. Rootly's create-channel step skips when the incident already has one ([Rootly workflows](https://docs.rootly.com/integrations/slack/workflows.md)); FireHydrant keeps one primary channel and creates a new one only for a channel it did not make ([FireHydrant](https://docs.firehydrant.com/docs/runbook-step-create-incident-channel)); incident.io unarchives instead ([incident.io](https://docs.incident.io/getting-started/channel-error)). Recommend: split. This task = parity (resources in the existing channel, slice 2); the loop and the primary move become a new task TASK-145.8.6.2 after 145.7.9, triggered from the API service, with I1 refined by ADR edit ("never creates one while the named conversation is usable; a conversation proven gone is replaced by the move"). Unarchive as an alternative to a new channel is unverified for bot tokens: check at slice 3. AC edits proposed: AC #3 moves to TASK-145.8.6.2 (text kept); AC #1 stays; comment #1's I1-I5 scope moves with it. The L8 gate is unaffected: parity removes the legacy item writer.

OQ2 Size gate. One PR would be ~480 prod LOC added, ~14 files, and mixes additive core ports with a behaviour cutover. Split (not created): TASK-145.8.6.1 dark core additions (IncidentConversation.bookmarks, IncidentReport.find; ~170 LOC, 7 files; one PR with an exception as no consumer, per the combine-dark-slices ruling); TASK-145.8.6 cutover (~330 LOC added, ~9 files, ~500 deleted); TASK-145.8.6.2 conversation recreate and move (~250 LOC, after 145.7.9). 145.8.6 becomes the coordinator like 145.8.5 if approved. New AC proposed for .1: "bookmarks and find exist on the Protocols with Slack, Google and in-memory implementations, classified failures, no consumer (tested)".

OQ3 set_reference guard. ADR: covered (incident-management.md:42, :188: guarded on record_version, INCIDENT_RECORD_CONFLICT); the parent text "guarded on the old channel_id scalar" and the task wording are stale: code is store.py:552-573 record_version only, two-pass re-read at 615-653. Recompute is not a retry (outbound-clients.md:32, 2026-11-17). Recommend: no store change; the service does not retry a conflict. Proposed parent rule edit (human): drop the old-scalar clause.

OQ4 Existing-resource detection and upgraded items. ADR: partial (incident-management.md:179 "not from the channel's bookmark"; rule on references :42). Legacy decides by channel bookmarks; the record likely lacks report/video_call for upgraded items (item_upgrade.py:43-44). Upcoming: TASK-145.7.12 (L7c) maps Drive roles only. Recommend: record reference first, then bookmark; report adopted via find(title); an existing "Meet link" bookmark with no reference is answered already-present, no reference written (a space id cannot be derived from a link without parsing, which the ADR forbids). Follow-up for the human: whether a job step should backfill video_call/report references (new task, not planned here). Named change N4.

OQ5 New core methods. ADR: gap (Protocol lists at incident-management.md:54 do not name them). Recommend: add `bookmarks` and `find` async on the existing Protocols; Changes line in the ADR rides with slice 1. Practice: Slack bookmarks.list needs bookmarks:read, Tier 3 (50+ per minute), 100 bookmarks per channel ([Slack docs](https://docs.slack.dev/reference/methods/bookmarks.list)); the legacy already calls it.

OQ6 On-call names in a recreated report's boilerplate. ADR: partial: oncall.md moves on-call to the capability; the ScheduleSource interim adapter is built by 145.7.9. Legacy reads the Drive folder's genie_schedule via on_call.get_on_call_users_from_folder (core.py:199). Options: A) build the lookup here (pulls 145.7.9's adapter forward, ~+120 LOC, trips the gate); B) keep the legacy call from the new service (imports modules/, forbidden); C) leave the on-call placeholder out until declare's `report_values` exists (a behaviour reduction needing an explicit ruling, pinned test_legacy_only_*, kind b by oncall.md). Recommend C, stated in the PR body; the report is still created and its placeholders filled.

OQ7 Report title and placement. ADR: gap (no ProductCatalog over Drive folders, 2026-11-04/05; record product is the bot product id once TASK-165.1 lands; today legacy name). Recommend: title = first candidate of incident_conversation_names (legacy doc title = channel slug, verified by pin 2.0); placement = list_placements() label equal to incident.product case-insensitively, else the legacy "product folder not found" error. Declare (145.7.9) should reuse both from response/service/; this slice defines them.

OQ8 Registration and wording. (i) Register `create resources` under sre.incident; the legacy `create new` ("Upcoming feature") stub is retired as kind (d) (surface with no target; /incident is the declare). Alternative: keep legacy handle_create for `new` and help until TASK-145.13 (smaller delete, dual registration risk). Recommend (d). (ii) The not-an-incident reply replaces "only in incident channels (starting with incident-)": new locale key incident_response.recreate.not_an_incident, same sentence shape as status/roles. (iii) fr-FR texts are an addition (legacy replies are English only); L6b and L7a.1 added them under the same rule; recommend the same, listed in the PR body as an addition by this ruling.

OQ9 No legacy pin exists. ADR: migration.md step 4 and the pin checklist require pins first. Recommend: slice 2 opens with the pin commit (plan 2.0) before any cutover code; a pin task is not needed.

OQ10 API first, HTTP route. ADR: covered in principle (incident-management.md:28, :188: HTTP always works an incident; the declare route rides with 145.7.9). Recommend: the service takes a resolved Incident and ports, no Slack types; Slack entrypoint thin. No HTTP route here (it is an addition: needs authorization.md permission, tag, error mapping). Name it for TASK-145.7.9's router or a new row after 18.L9a ("POST /incidents/{id}/resources", with slice 3); human to place the row.

OQ11 Non-idempotent creates. Meet spaces have no name to claim; outbound-clients.md:26 asks for a mechanism. Recommend: accept the legacy residual (a failed set_reference after a created space leaves one orphan; rerun creates another), log the space id; a report is protected by find(title). Practice: FireHydrant/Rootly dedupe by "resource already attached" check, the same as here.

OQ12 AC text. AC #5 says list "column E or B": the adapter upserts on the id in column F (incident-management.md:193; google_sheets.py:7). Proposed rewording: "...re-upserts the incident's list row (IncidentListProjection.append_row, keyed by the incident id)...". AC #4 unchanged.

PR body lists (for the cutover PR): revert target (AC #4) and named changes N1-N6 with kinds (plan section 4), additions (fr-FR, OQ8) and the OQ6 on-call ruling.

---

created: 2026-11-17T15:14:00Z

---

Program-scope OQ assessment (2026-11-17)

Scope: OQ1-OQ12 of comment #3 re-assessed against decisions/, prior rulings, the whole of doc-11, doc-15 and doc-16, the root Runbook and Handbook, and current practice. Plan revised via --plan (two slices, not three). Nothing else edited; every ADR, AC and task change below is a proposal.

WHAT CHANGED AND WHY
1. OQ1/OQ2 CHANGED: slice 3 (TASK-145.8.6.2, I1-I5 loop plus primary move) is dropped from Stack L. Evidence: (a) the Runbook and Handbook never describe recreating a lost channel, a second channel, unarchive or reopen (Incident Response Runbook.md:39,54,167-171 describe creation and the final archive step only; Handbook.md:107,111,200; no troubleshooting section); (b) TASK-145.7 scenarios 3-4 already ruled "Rebind to a new channel: not built in Stack L ... TASK-165.x adds it (new primary, old archived_at)" and "second channel bound: not built" (also TASK-145.7.3 line 69), which contradicts the 2026-11-10 AC #3 added to this row; (c) Slack: "Bot tokens (xoxb-...) cannot currently be used to unarchive conversations" (conversations.unarchive), so a bot cannot repair a lost or archived channel and incident.io's fix is a human unarchiving it; (d) the only legitimate create case under I1 is an incident whose record names no conversation (declare's failed step, or a channel-less child incident, TASK-165.5 AC #2), and declare's idempotent replay (TASK-145.7.9 AC #1: id derived from the idempotency key, steps retriable) plus 165.5's "conversation attached when the coordinator opens one" already own it; the loop is then built once, by 145.7.9. A move is redundant now and would be needed only by the rebind task, ideally after TASK-145.13 removes channel_id and by_channel so the move writes one copy, not two. My earlier "split into .2 after 145.7.9" is overturned: .2 as proposed has no consumer in Stack L.
2. OQ4 CHANGED (premise wrong): upgraded and not-yet-upgraded legacy items already carry report and video_call references: the read bridge maps report_url and meet_url (core/adapters/legacy_items.py:121-122, 256-274; read at store.py:737; the job persists them, TASK-145.7.4 D2/D3). Only items with no parsable URL (two open test incidents, ADR :175) lack them. N4 reworded; adopt-by-find applies only there.
3. OQ7 CHANGED: no product placement. ADR :175 (2026-11-05): a new report is filed in [incident_core] folder_id and placement returns only as configuration keyed by the bot's product id (TASK-165.1); ADR :177: the legacy `teams` folder name is not mapped to product. So the label match I proposed cannot work. New named change N7 (kind b, cites :175/:177): recreate files a new report in folder_id and stops parsing the channel topic. Title proposal kept.
4. NEW OQ13 (conflict): set_reference refuses any item not at record_version 2 (store.py:552-565, ADR :42 "a legacy item is refused with INCIDENT_RECORD_CONFLICT"). L7b deploys before the L8 apply (doc-11 row 18.L8 waits on L6a-L7b deployed), so on every not-yet-upgraded item the new recreate would create a document or Meet space and then fail to reference it, while the legacy recreate worked: a parity break. Recommend set_reference upgrades on write through _plan_write (store.py:655-689), as update_fields, set_roles and set_status already do (ADR Changes 2026-11-10 TASK-145.8.1). Goes in slice 1 (dark).
Other verdicts KEPT. The slices are now: .1 dark core additions (bookmarks, find, set_reference upgrade-on-write; ~220 LOC, 9 files) and the cutover (~330 LOC added). Stack base (a) unchanged.

TABLE (OQ / ADR status / prior ruling / upcoming owner / verdict / recommendation)
OQ1 recreate = channel recreation? | CONFLICT (ADR :34 "moving it is recreate's", :36 rule 1 vs :36 rule 5, :42; domain.py:316-318 says never moves) | 145.7 scenarios 3-4 defer rebind to TASK-165.x; 145.7.7 note 2026-11-10 and row 18.L7b assign the move here; comment #1 assigns I1-I5 here and in 145.7.9 | loop: 145.7.9; attach-to-none: 165.5 AC #2; rebind: TASK-165.x | CHANGED | recreate = parity only; move AC to the rebind task; reword ADR (below)
OQ2 size gate | covered (CLAUDE.md gate; combine-dark-slices ruling) | 145.8.5 three-slice precedent | - | CHANGED (two slices) | .1 dark + cutover; no .2
OQ3 set_reference guard | covered (ADR :42, :188; outbound-clients.md:32 2026-11-17) | 145.8.1 recompute rulings | - | KEPT | record_version only; fix the stale parent text
OQ4 existence detection | partial (ADR :179, :42) | 145.8.4 D6: no bookmark scan carried; 145.7.4 bridge | none planned (a backfill is unneeded) | CHANGED | record reference first, bookmark second, adopt-by-find only for URL-less items
OQ5 bookmarks(), find() ports | gap (ADR :54 lists add_bookmark only) | 145.6.2 C1-C3 (report from the record) | this task, slice 1 | KEPT | add; ADR :54 and Changes line
OQ6 on-call names in boilerplate | partial (oncall.md silent on the report; ADR :183 retires folder metadata) | 146.3 line 42: interim ScheduleSource reads genie_schedule, tolerated, owner 165.1; 146 note 2026-11-04 | 145.7.9 (ScheduleSource) | KEPT | option C: leave the placeholder out, pinned test_legacy_only_*, until declare supplies report values
OQ7 title and placement | covered for placement (ADR :175, :177), gap for title | 145.6.2 | 165.1 (placement by product id) | CHANGED | no placement; title = first incident_conversation_names candidate (shared with declare)
OQ8 registration, create new stub, fr-FR | covered (i18n.md:23,29,31; migration.md step 4) | 145.8.4 AC #6/#7 and D7; 145.8.5.1 S4/D5 (French added, named in PR body) | 145.13 deletes app/modules/incident | KEPT | retire stub as (d); fr-FR as ruled addition
OQ9 no legacy pin | covered (migration.md step 4; pin checklist) | 145.8.4 pins | - | KEPT | pin commit first
OQ10 HTTP route | covered in principle (ADR :28, :188) | 145.7.7 R6: declare route rides with 145.7.9 | none for recreate | KEPT, route deferred | no route now; an addition needing its own task with a row after 18.L9a only when an API caller needs it (Backstage is an API caller, ADR :28)
OQ11 non-idempotent Meet create | covered (outbound-clients.md:26, :71 names Meet create num_retries=0) | 145.7.6 (idempotency none offered) | - | KEPT | accept; log the space name
OQ12 AC wording | n/a | 145.12.1 (key column F, ADR :193) | - | KEPT | reword AC #5; AC #3 moves
OQ13 set_reference on legacy items | CONFLICT (ADR :42) | 145.8.1 upgrade-on-write for field writes | slice 1 | NEW | upgrade on write

DOMAIN-MODEL-EVOLUTION (OQ1/OQ4/OQ5; model: Incident, IncidentBinding, primary conversation, references)
Cardinalities (ADR :34, :42): incident to bindings 0..n, at most one active primary; conversation to active incident at most 1 (lookup fails closed on ambiguity); incident to each reference kind 0..1; the record's conversation and channel_id are the primary binding's copy.
Scenarios (doc-15 rows and 145.7 scenarios): S1 incident with zero bindings, API-declared or child (doc-15 row 8/E7, 165.5 AC #2): attach_conversation works today, no move. S2 primary channel archived by close, then reopen: same conversation, a human unarchives (Slack); no binding change. S3 primary deleted or lost: the record points at a dead channel; only a rebind (new primary, old archived_at, copy moved) repairs it; deferred by 145.7 scenario 3. S4 secondary conversation (war room): attach with primary=false, no move (145.7 scenario 4 "not built"). S5 one channel bound to two incidents (promote, attach, merge, 165.5 AC #3): lookup fails closed. S6 merge/split of incidents (165.5, D37): bindings and the root id re-pointed there; not this task. S7 legacy item before the L8 apply: set_reference must upgrade on write (OQ13). S8 legacy item with no report_url: adopt by find or leave unreferenced.
Edge evidence: Slack bots cannot unarchive; deleted channels are gone with their history (Slack docs); Drive name search is eventually consistent in practice, so find is best-effort; Meet spaces.create takes no request id, so only persisting the returned space name is idempotent.
Decision: the model needs no change in this task; IncidentBinding, ReferenceKind and the primary rule stay. Compatibility: slice 1 is additive (two port methods, set_reference widened to upgrade on write, in-memory fake in step); cascade: the rebind task must write conversation and channel_id until 145.13, only conversation after; I1 is refined, not weakened.

PROPOSED ADR EDITS (not made)
- decisions/incident-management.md, "One conversation per incident" (:36): replace "Declare and recreate own the loop, five rules" with "Declare owns the loop (`response/service/conversation.py`); attaching a conversation later to an incident that has none (TASK-165.5) reuses it; recreating missing resources never creates or moves a conversation", and in rule 5 replace "recreate retries the same name" with "a retried declare, or a later attach, retries the same name".
- same file, Bindings (:34): "moving it is recreate's" becomes "moving it is the rebind's (TASK-165.x)"; add the sentence "A bot cannot unarchive a Slack channel; an archived or deleted primary is repaired by a human unarchive or a rebind."
- same file, Stored form (:42): "(a recreated channel)" becomes "(a rebound conversation)"; "a legacy item is refused with INCIDENT_RECORD_CONFLICT" becomes "a legacy item is upgraded in the same update (upgrade on write), an unreadable one refused".
- same file, resource interface (:54): add `IncidentConversation.bookmarks` and `IncidentReport.find` (async, classified results; find is best-effort by exact name in the configured folder).
- same file, Changes: one 2026-11-17 line per PR (slice 1: ports and set_reference upgrade on write; cutover: recreate in response/, report filed in folder_id, named changes N1-N7, `create new` retired).
- core/domain.py:316-318 ReferenceKind docstring reworded with slice 1 (code, not an ADR).
- decisions/oncall.md: one line that a recreated report leaves the on-call placeholder blank until declare's report values exist (OQ6, option C).

PROPOSED TASK SCOPE CHANGES (not made)
- TASK-145.8.6: AC #3 removed here and moved; AC #5 reworded: "re-upserts the incident's list row (IncidentListProjection.append_row, keyed by the incident id, TASK-145.12.1 rulings)"; AC #1 gains "an item below record_version 2 is upgraded and referenced in the same update (tested)"; comment #1 (I1-I5) retired as scope here; description: add "the report is filed in [incident_core] folder_id, no product placement (N7)". Coordinator children: .1 dark core additions (AC: bookmarks and find on the Protocols with Slack, Google and in-memory implementations, classified failures; set_reference upgrades legacy items on write; no consumer; tested) and the cutover.
- TASK-145.8 (parent): rule "guarded on the old channel_id scalar" replaced by "set_reference guarded on record_version (ADR :42)"; parent AC #5 follows.
- TASK-145.7.9: state in its plan that the I1-I5 loop lives at response/service/conversation.py with one test per rule, and the report title / placeholder values (including on-call names) are the shared definition recreate reuses; confirm AC #1 "retriable" means an idempotent replay.
- TASK-165.5: AC #2 notes "opens a conversation through the I1-I5 loop (response/service/conversation.py)".
- TASK-165.x rebind task (the id named in TASK-145.7 scenarios 3-4; I could not find it by number, human to name): receives the old AC #3 text (archive the old primary binding, attach the new, move the record's conversation copy and channel_id in one update guarded on record_version; attach_conversation keeps refusing a primary move); depends on TASK-145.13; states that bots cannot unarchive.
- TASK-145.13: note that the rebind lands after channel_id and by_channel are retired, or writes both until then.
- doc-11 row 18.L7b (line 175): drop "2026-11-10: AC added: moving the primary conversation on recreate"; add "2026-11-17: parity only; move deferred to the rebind task; set_reference upgrades on write (slice 1, TASK-145.8.6.1)". doc-16 table row L7b: two PRs (dark slice, then cutover) on `stack-l/task-145.8.6-recreate`, plus the stack-base note (above L7a.1). doc-15: no change, but 165.5 should cite the shared loop.

SOURCES
- Slack unarchive (bot tokens cannot): https://docs.slack.dev/reference/methods/conversations.unarchive
- Slack create, name_taken, no idempotency key: https://docs.slack.dev/reference/methods/conversations.create
- Slack bookmarks: https://docs.slack.dev/reference/methods/bookmarks.list and https://docs.slack.dev/reference/methods/bookmarks.add (100 per channel, duplicates not documented, dedupe through list)
- Slack canvas: https://docs.slack.dev/reference/methods/conversations.canvases.create (channel_canvas_already_exists)
- Archived channels: https://docs.slack.dev/reference/methods/chat.postMessage (is_archived); https://docs.incident.io/getting-started/channel-error ("bots can't read archived channels", human unarchives); https://docs.incident.io/incidents/reopen-incidents
- FireHydrant one primary channel, ensure-style step, no duplicate: https://docs.firehydrant.com/docs/runbook-step-create-incident-channel; parent/child, each keeps its channel: https://docs.firehydrant.com/docs/related-incidents
- Rootly skips creation when a channel exists: https://docs.rootly.com/integrations/slack/workflows/create-slack-channel
- Dispatch create-if-missing resources and unarchive on reopen: https://github.com/Netflix/dispatch/blob/main/src/dispatch/incident/flows.py (archived read-only, 2025)
- PagerDuty Incident Workflows: https://support.pagerduty.com/actions/docs/create-a-slack-channel-for-an-incident (dedupe behaviour unverified)
- DynamoDB version attribute, conditional write, reload on mismatch: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBMapper.OptimisticLocking.html
- Expand/contract: https://www.prisma.io/docs/orm/prisma-migrate/workflows/expand-and-contract
- Transactional outbox (record as the commit point, idempotent consumers): https://microservices.io/patterns/data/transactional-outbox
- Drive search and consistency caveats: https://developers.google.com/workspace/drive/api/guides/search-files, https://issuetracker.google.com/issues/406305173
- Meet spaces.create (no request id) and spaces.get (store spaces/{id}, not the meeting code): https://developers.google.com/workspace/meet/api/reference/rest/v2/spaces/create, https://developers.google.com/workspace/meet/api/reference/rest/v2/spaces/get
Unverified: incident.io merge channel behaviour; PagerDuty create-channel dedupe; whether Slack lists bookmarks in archived channels.

---

created: 2026-11-17T15:33:00Z

---

2026-11-17 (human, OQ1 follow-up): the primary move (old AC #3) leaves this task for the new TASK-165.11 (rebind, depends on TASK-145.13; doc-15 row 8a). The human questioned whether parity is the right default here: migration.md step 4 keeps behaviour by default but :67 rejects the feature parity trap (replicating every legacy behaviour). Ruling: base what create resources keeps on production usage, as was done for the status form in TASK-145.8.4 OQ4. Human step: CloudWatch Logs Insights on /ecs/sre-bot-app, 90 days, event sre_incident_command_received with args[0] = create, split by args[1] (resources, new, other). Re-plan by the count: unused -> retire create resources and the create new stub as kind (d), the cutover is mostly deletion and the dark slice shrinks to set_reference upgrade-on-write (declare and status need it too); rare -> carry only the pieces used; used -> the current two-PR plan with N1-N7. Plan not approved until then.

---

created: 2026-11-17T15:43:00Z

---

Re-plan after usage count (2026-11-17)

Input: the human's Logs Insights count (90 days, /ecs/sre-bot-app, sre_incident_command_received, args[0]=create): resources 0, new 1, bare 3, and comment #5's rule (unused -> retire as kind (d)). The plan (--plan) is rewritten as a one-PR retirement of the whole `/sre incident create` node. Nothing else edited; everything below is a proposal.

BASE VERDICT: unchanged, (a) above L7a.1. Retirement removes the functional need for L6b/L7a.1 (no stage types, no entrypoint, no new core port), so a side PR from main would work functionally, but it is not conflict-free: the L6b+L7a.1 hunks in incident_helper.py (`git diff -U0 main..8a7d6bf6`: main lines 63 and 108 are the two help texts, 146-155, 180-192, 203, 366, 577) sit within a few lines of this PR's help-text, get_incident_actions and handle_create edits; test_incident_helper.py (L6b -190, L7a.1 -37) is edited by both; and L7a.3 deletes handle_close (:232-235) one blank line above handle_create (:237). A side PR would make #1859/#1862 or this PR rebase twice. Merge order L6b -> L7a.1 -> this PR; L7a.3 and L6a above it.

WHAT THE PR DELETES AND EDITS (about 520 production lines deleted, 0 added; tests about 540 deleted, 70 added; size gate does not bind a delete-dominant PR)
- modules/incident/core.py:39-419 (381): the recreate functions and _create_database_record; imports incident_drive (:11) and channel_slug (:22) go.
- modules/incident/incident_helper.py (about 112): the "create" key, handle_create, recreate_missing_incident_resources, the create bullet and example in both help texts.
- features/incident/core/adapters/google_docs.py (about 24): list_folder_files (orphaned by this PR; sole caller core.py:185) and find_document_by_channel_name (no production caller at 8a7d6bf6; pre-existing orphan, same file, delete-dead-code rule).
- Tests deleted: test_recreate_missing_resources.py (430), test_incident_core.py:1053-1066, test_incident_helper.py:169-210, the two helpers' cases in test_incident_core_google_docs_drive.py and the two calls in test_incident_core_report_no_delegation.py:86,90.
- Kept with rg evidence: incident_folder.channel_slug (used by return_channel_name :392; its callers information_update.py:315 and incident_status.py:57 die with TASK-145.8.3 and 145.8.5.3, not here); incident_document.create_incident_document/update_boilerplate_text (legacy declare, core.py:492, :611); meet.create_space (declare, :459); on_call and incident_folder helpers and db_operations (declare, dev commands, show, close).
- Text edits: domain.py:316-318 and :550, google_meet.py:8 and test_incident_core_video_call_create_space.py:3, test_incident_core_incident_store_attach_conversation.py:103 (docstring), features/incident/README.md:28 and :84-85, INVENTORY.md (new row for the pin), decisions/incident-management.md (below).

PIN BEFORE THE DELETE, and what a user sees: test_incident_create_retired_surface.py (legacy_surface, Bolt dispatch boundary; precedent test_incident_status_command_surface.py) asserts that bare `create`, `create new` and `create resources` each answer the dispatcher's existing "Unknown command: create. Type `/sre incident help` to see a list of commands." (incident_helper.py:228-229), with no Slack, Drive, Sheet, Meet or table write, and that `/sre incident help` and `aide` no longer list create. It is red against the legacy code first.
OQ-A pointer? Recommend NO. Counts 0, 1 and 3 do not justify a reply that TASK-145.13 would delete again (the `status <s>` pointer of 145.8.4 had a real bare-form population from OQ4); the unknown-command line already points to help, and help no longer lists create.

DROPPED, AND WHY (consumer check at 8a7d6bf6 and the whole map)
- OQ4-OQ7, OQ11, OQ12, N1-N7, the recreate service, Slack entrypoint, fr-FR keys, list-row re-upsert, report title/placement, on-call boilerplate: they only served a rebuilt `create resources`; nothing else in the map calls them (rg over backlog/tasks, doc-11, doc-15, doc-16, decisions: no other owner).
- Dark slice, bookmarks() and IncidentReport.find: no other consumer. Declare (145.7.9) needs add_bookmark, which exists (core/api.py:271); `rg "IncidentReport.find|.bookmarks("` over backlog finds only this task. Dropped; if declare or 165.5 later needs to know existing bookmarks they can add it with the consumer.
- OQ13, set_reference upgrade-on-write: DROPPED. Evidence: set_reference has no production caller today (rg over app/ outside core/ and tests: none). The only tasks that mention it are 145.7.7 (defined it), 145.7, 145.8, 145.8.1, 145.8.2, 145.8.7 (inventory or plan text) and this one; 145.8.1 line 55 listed L7b as a consumer, which retirement removes. Declare (145.7.9, 145.7.10) calls it on the record it just created through IncidentStore.create, which writes the end-state shape at record_version 2 (store.py create validates end-state only), and its id comes from the idempotency key so it never meets a legacy item; status uses set_status, which already upgrades on write (store.py:655-689). 145.8.3, 145.8.5.3, 145.9.x, 145.10, 145.12.x and 165.x do not mention set_reference. Comment #5 said declare and status need it too; the survey does not support that. Revisit only if a task adds a set_reference caller on a stored legacy item (165.5's child incidents and 165.11 start from end-state records). ADR :42 stays as written.
- Split into slices, OQ1-OQ3 (move, loop, guard text): the move is TASK-165.11; the loop is 145.7.9; the parent's guard-text clause belongs to the deleted surface and is removed rather than fixed.

REMAINING OPEN POINTS
- OQ-A (pointer): no (above).
- OQ-B: the legacy deprecation text for `create-folder` (test_incident_helper.py:25) tells users to use `/sre incident create folder <folder_name>`, a form handle_create never handled and the 2025-11-01 end date has passed; unchanged by this PR (unknown-command reply either way); TASK-145.13 deletes it. Recommend: no action here, noted so nobody reads the retirement as breaking it.
- OQ-C: the pin's expectation of the legacy dispatcher reply assumes no registrar-registered `create` exists (response/entrypoints/slack.py registers status and roles only); verified when the pin goes red. Recommend: if one exists, the pin asserts whatever the user sees and the PR body states it.
- OQ-D: task title and description: yes, change both (below).

PROPOSED AC SET (replaces #1, #3, #5; #2 and #4 unchanged; none applied)
#1 "/sre incident create is retired: bare create, create new and create resources answer the dispatcher's unknown-command reply and the help text no longer lists create (surface-pinned); handle_create, recreate_missing_incident_resources, the recreate functions of modules/incident/core.py, _create_database_record and their tests are deleted (checks parent AC #1 and #5)".
#3 "Every helper the retirement orphans is deleted with its tests (list_folder_files, find_document_by_channel_name), with rg evidence in the PR body; helpers the legacy declare, show or close still use are kept (channel_slug, incident_document functions, meet.create_space)".
#5 "The PR body lists two named changes of kind (d) with the usage count (create resources 0, create new 1, bare create 3, 90 days, Logs Insights on /ecs/sre-bot-app) and the revert target; code, README and ADR text no longer name recreate as a live surface (domain.py, google_meet.py, features/incident/README.md, incident-management.md)".
Title: "Retire /sre incident create: create resources and the create new stub, recreate_missing_resources and _create_database_record deleted". Description: replace with "Stack Stack L L7b. The production usage count (90 days: create resources 0, create new 1, bare 3) retires the whole /sre incident create node as a kind (d) named change (migration.md step 4, :67). recreate_missing_resources, _create_database_record, handle_create, recreate_missing_incident_resources, their orphaned helpers and tests are deleted; the primary move is TASK-165.11; the one-channel loop is TASK-145.7.9's." (CLI -t changes the title; the file name keeps the old title: human decides on renaming, memory feedback-backlog-cli-fallback.)

PROPOSED ADR EDITS (not made)
- decisions/incident-management.md :34: "moving it is recreate's" becomes "moving it is the rebind's (TASK-165.11)".
- :36: "Declare and recreate own the loop, five rules" becomes "Declare owns the loop, five rules (`response/service/conversation.py`, TASK-145.7.9); attaching a conversation later to an incident that has none (TASK-165.5) reuses it"; rule 5 "recreate retries the same name" becomes "a retried declare or attach retries the same name". The :115 Test line and the :190 Changes line keep "recreate" only as history; add the correction to the new Changes line.
- :42: "(a recreated channel)" becomes "(a rebound conversation, TASK-165.11)".
- :50 response row: drop "recreate resources" from the owned surfaces.
- :146 Migration rule 6: no text change; the new Changes line records that recreate, a legacy item writer, is removed (the rerun rule then waits only on legacy declare, TASK-145.7.10, and 145.12.2).
- Changes, one 2026-11-17 line: "TASK-145.8.6: `/sre incident create` retired (kind d; 0 uses of resources, 1 of new, 3 bare, 90 days); recreate is no surface; no new core port or store change".
- core/domain.py :316-318 and :550 and the other comments above ride in the PR (code, not ADR).

PROPOSED TASK SCOPE EDITS (not made)
- TASK-145.7.9: its plan states the I1-I5 loop lives at response/service/conversation.py with one test per rule (comment #1 there already holds the rules); nothing moves from here.
- TASK-165.5 AC #2: add "opens the conversation through the I1-I5 loop (response/service/conversation.py)".
- TASK-165.11: already holds the rebind and the old AC #3 text; add a line that the legacy tests' docstring (attach_conversation refusing a primary move) cites it.
- TASK-145.8 (parent): drop the rule "The recreate path replaces a missing resource's reference map whole... guarded on the old channel_id scalar" (the surface it described is retired; the guard text was stale anyway), reword the title/description wording "archive and recreate" to "archive" once 145.8.5.3 and this task land, and move parent AC #1 and #5's recreate mentions to "retired".
- doc-11 row 18.L7b (:175): replace with "TASK-145.8.6 retire /sre incident create (kind d, usage count); one delete-dominant PR; AC added 2026-11-10 (move the primary) moved to TASK-165.11"; row 18.L8's gate unchanged (the legacy item writer is removed). doc-16 table row L7b: one PR, delete-dominant, `stack-l/task-145.8.6-recreate` above L7a.1 (rename the branch only if the task is renamed). doc-15: row 8a already added.
- TASK-145.13: the pin test, INVENTORY row and the `create-folder` text join its deletion list.

SOURCES: no new web research needed (the change is a deletion). Earlier cited sources stand: https://docs.slack.dev/reference/methods/conversations.unarchive (bots cannot unarchive, why the move is not a bot repair), https://docs.rootly.com/integrations/slack/workflows/create-slack-channel, https://docs.firehydrant.com/docs/runbook-step-create-incident-channel (vendors do not offer a replace-channel operation).

---

created: 2026-11-17T15:47:00Z

---

2026-11-17 (human): plan APPROVED as re-planned after the usage count (comment 'Re-plan after usage count (2026-11-17)'): retire all of /sre incident create in one delete-dominant PR on stack-l/task-145.8.6-recreate above L7a.1; no pointer reply (OQ-A); OQ-B no action (145.13 deletes the create-folder text); OQ-C verified when the pin goes red; OQ-D title and description changed (file name unchanged). ACs replaced (#2 and #4 kept). Dropped: dark slice, recreate service, N1-N7, OQ13. ADR and code-text edits ride with the PR.

---
<!-- COMMENTS:END -->
