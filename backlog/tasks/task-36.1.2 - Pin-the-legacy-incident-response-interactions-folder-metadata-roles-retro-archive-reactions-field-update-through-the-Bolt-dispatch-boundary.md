---
id: TASK-36.1.2
title: >-
  Pin the legacy incident response interactions (roles, field update, archive,
  folder metadata) through the Bolt dispatch boundary
status: Done
assignee: []
created_date: 2026-10-15 20:49
updated_date: '2026-11-09T17:44:00Z'
labels:
  - migration
  - testing
milestone: m-5
dependencies:
  - TASK-36.1.1
references:
  - decisions/testing.md
  - decisions/migration.md
  - https://github.com/cds-snc/sre-bot/issues/1739
parent_task_id: TASK-36.1
priority: medium
ordinal: 396000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Second slice of TASK-36.1, reusing the harness from the first slice. Pins the 9 incident_helper.py interactions TASK-145.8 rebuilds or the incident contract retires: actions update_incident_field, archive_channel, add_folder_metadata, view_folder_metadata, delete_folder_metadata; views view_save_incident_roles, update_field_modal, view_folder_metadata_modal, add_metadata_view. The reaction and retro-scheduling rows moved to TASK-36.1.5 (2026-11-06, OQ3). The folder-metadata rows are retired, not rebuilt: the product's on-call schedule reference moves to the bot's own product list (TASK-165.1, TASK-146.3) and the Slack editor is deleted with modules/incident (TASK-145.13); they are pinned as legacy_only tests.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Each of the 9 interaction rows has a dispatch-driven test covering ack, Slack-visible calls and outcomes at the faked edges, following the pin contract (durable entry points; modal-internal ids read from the opened view; effects the rebuild ends in legacy_only tests)
- [x] #2 INVENTORY.md marks these rows pinned by this task and names the target and the owning ticket: TASK-145.8 for the rebuilt rows, TASK-165.1/TASK-146.3 with deletion by TASK-145.13 for the retired folder-metadata rows; the header's id rule is narrowed to ids on posted messages
- [x] #3 decisions/transport-slack.md and decisions/migration.md carry the interaction-id rule (modal-internal ids take the plugin prefix at rebuild; ids on posted messages keep a legacy alias until the contract task) and the pin contract, with dated Changes lines
- [x] #4 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Grounded at main 76f73bde (2026-11-06); revised the same day after a program-scope assessment (ADRs, doc-11, doc-15, prior pin tasks, web). 2026-11-06 (human): OQ1-OQ6 approved as recommended (OQ6: decisions/testing.md seams during the legacy migration; guard TASK-187). Scope is PR A (9 rows); steps 6-7 moved to TASK-36.1.5. Test-only: 0 production LOC. Touches app/tests/integration/legacy_surface/: conftest.py (additive), INVENTORY.md (rows 53-68 and the header), new test files. Reuses the TASK-36.1.1 harness (legacy_handler_harness, LegacyHandlerHarness.command/interaction/event, conftest.py:206-290) and its rule: fakes only at external edges, never inside modules/incident.

## Pin contract (approved OQ1; amendments in decisions/transport-slack.md and decisions/migration.md, 2026-11-06, ride with this PR)
A pin couples only to what survives the rebuild into the target feature packages, so the rebuild PR keeps its assertions and only rewires fixtures:
- In: durable entry points only: slash command names, ids on messages already posted to channels (archive_channel on the stale-channel nudge), and event types (reaction_added/removed). Modal-internal ids (view callback ids, actions inside a modal the bot opened) are never hard-coded: the pin opens the modal from its durable entry point and reads the ids from the recorded views_open/views_push/views_update payload. The 16 rows' registrations still exist exactly (incident_helper.py:149-165); only archive_channel and the 4 reaction rows are durable, the other 11 are modal-internal (incident_folder.py:63/155/160/209, incident_roles.py:144, information_display.py:30, schedule_retro.py:91/241).
- Out: Slack-visible calls and their user-facing content, and outcomes at external edges stated in domain terms: the incident's field now reads V (read back through the next /sre incident show, which renders it), one timeline entry with this text in the report, one calendar event with these attendees, one Sentinel event. No UpdateExpression, item shape, open_bucket, record_version or Docs request bodies.
- Fakes (OQ6): external edges wherever reachable; an internal legacy seam only through a named legacy_surface fixture recorded in the seam baseline: the DynamoDB adapter (packages.aws_platform.adapters.dynamodb.build_dynamodb_adapter, in-memory table), the incident Google adapter module (features.incident.core.adapters.google_docs: Drive appProperties, child folders, Docs timeline and status text over an in-memory document), the calendar adapter (features.incident.scheduling.adapters.google_calendar get_freebusy/insert_event), the spreadsheets provider, integrations.sentinel. No patch of db_operations, incident_document, or names imported into schedule_retro (the earlier draft did; dropped). At cutover the owning task rewires the fixture to the target port fake (IncidentStore over the records fake, IncidentReport fake, the incident scheduling port fake); assertions do not change.
- Effects the rebuild deliberately ends get a test named legacy_only_* in its own class, deleted by the owning task: the roles report-property writes ic_id/ol_id (TASK-145.8 AC #2), and the folder-metadata rows (OQ2).

## Rebuild owner per row (OQ1)
- TASK-145.8 (incident.response): view_save_incident_roles, update_incident_field, update_field_modal, archive_channel (ignore and archive branches).
- TASK-145.9 (incident.response): reaction_added/removed floppy-disk matcher and ack-only fallback (4 rows).
- TASK-145.10 (incident.postmortem): view_save_event, confirm_click (schedule_retro.py:346), user_select_action (364), and archive_channel's schedule_retro branch (rendered by response, handled by postmortem, incident-management.md common/ vocabulary rule).
- Retired, not rebuilt (OQ2): add_folder_metadata, view_folder_metadata, delete_folder_metadata, view_folder_metadata_modal, add_metadata_view. Target: the product's on-call ScheduleReference in the bot's own product list (TASK-165.1, TASK-146.3); the Slack editor is deleted with modules/incident (TASK-145.13).

## Steps (this task = PR A; steps 6-7 are TASK-36.1.5's plan)
1. conftest.py (additive; registration-surface tests unchanged): edge fakes above as fixtures (in-memory incidents table, Google document/folder fake generalising the INCIDENT_FOLDERS lambda, calendar fake, sheet fake); a helper that returns the last opened/pushed/updated view and builds the block_actions or view_submission payload from that view's own ids and state.
2. PR A test_incident_roles_surface.py (1 row): /sre incident roles opens the modal; submit through the read callback id; changed IC/OL post one message each, unchanged none; purpose text replaced or appended, capped at 250. legacy_only test: ic_id/ol_id written as report properties.
3. PR A test_incident_field_update_surface.py (2 rows): /sre incident show -> click an update button (ids read from the view) -> views_push field view -> submit; per type the channel message, the information view refreshed, and the new value rendered by a following show; status also moves the report status text and the sheet row, and posts the sheet-miss message; datetime converts the user's tz to UTC.
4. PR A test_incident_channel_archive_surface.py (1 row): interactive_message callback archive_channel (durable id, hard-coded): ignore clears the nudge attachments and sends one Sentinel event; archive closes the incident (status rendered Closed by show, sheet row, "has archived this channel", conversations_archive, Sentinel); non-incident channel refused; store unavailable gives the bilingual message. schedule_retro branch: the retro modal opens (PR B owns the flow after it).
5. PR A test_incident_folder_metadata_surface.py (5 rows, thin, legacy_only class): /sre incident products (or the command that opens it, verified at pickup) lists folders by name (25 cap); add, view and delete through ids read from the views; the appProperties change at the Drive edge. Documents the genie_schedule data contract the TASK-165.1 import reads.
6. (moved to TASK-36.1.5) reactions.
7. (moved to TASK-36.1.5) retro scheduling.
8. INVENTORY.md: each owned row gets Pinned by, the real Defined at line, Target (incident.response / incident.postmortem / retired -> product catalogue) and Rebuild ticket (145.8, 145.9, 145.10, or 165.1/146.3 + deleted by 145.13), replacing "TASK-38 (after TASK-97)"; the header's "every rebuild must keep ids working" is narrowed to durable ids per the pin contract.
9. Mutation-check each file once (invert one expected value, see it fail, revert), as TASK-36.3 did.

## AC traceability
AC1: steps 2-5 (every row pinned; the 5 folder rows as legacy_only with their owning tickets). AC2: step 8. AC3: the ADR amendments (transport-slack, migration, testing, incident-management; written 2026-11-06, committed with this PR). AC4: verification below.

## Open questions (OQ1-OQ6 ruled 2026-11-06 as recommended)
OQ1 Interaction ids across the rebuild (ADR conflict). transport-slack.md: rebuilt ids carry the plugin's entry-point name and open modals across a deploy are accepted as broken; migration.md recipe step 4 and INVENTORY.md: names and behaviour unchanged, smoke tests stay green; TASK-145.7 keeps legacy names, TASK-145.10's plan renames to incident.postmortem.*. Gap: no rule separates ids on posted messages from modal-internal ids. Slack routes block_actions by the action_id carried in the posted element, so a renamed id breaks every button already posted (Bolt action listeners). Recommend: amend transport-slack.md and migration.md: modal-internal ids take the plugin prefix at rebuild; ids on posted messages keep a registered legacy alias owned by the rebuilt plugin until the legacy contract task removes it (parallel change); pins follow the pin contract above. AC #2 reads "TASK-145.8, TASK-145.9 or TASK-145.10, or the retiring task". TASK-145.10 depends on TASK-36.1 (whole parent, incl. the aws and webhook pins 36.1.3/36.1.4): repoint to the pin task that holds the retro rows. TASK-145.8's entrypoint list drops confirm_click and the folder-metadata interactions.
OQ2 Folder metadata. incident-management.md (2026-11-04, 2026-11-05): ProductCatalog is never built over Drive folders; the bot owns the product list (TASK-165.1). TASK-145.8 still says "folder-metadata interactions over ProductCatalog" and "Folder metadata stays a ProductCatalog concern through the Drive adapter" (conflict). The only contractual key is genie_schedule (on_call.py:32), the Opsgenie schedule TASK-146.3 turns into a ScheduleReference. Recommend: pin thin as legacy_only; correct 145.8; the carry-over is OQ5.
OQ3 Size: PR A 9 rows (~700 test LOC incl. conftest, 5 files), PR B 7 rows (~550, 3 files incl. INVENTORY). Recommend two PRs; PR B is new sibling TASK-36.1.5 gating 145.9 and 145.10; doc-11 row 17 gates 145.8 only.
OQ4 Stack L reshape: covered by the pin contract (field read back through show, not the item).
OQ5 (program scope, not this PR) No task carries each product folder's genie_schedule into the bot's product list, and TASK-145.13 deletes on_call.py and incident_folder.py while TASK-165.1 depends on all of TASK-145, so the delete can land before the list exists. Recommend: TASK-165.1 gains an import step (folder -> product mapping confirmed by a human, genie_schedule -> ScheduleReference, every other appProperties key listed for a ruling, never dropped silently); 165.1 depends on 145.6 instead of 145; 145.13 depends on 165.1 and 146.3. Scenario evidence for 165.1's plan: product with one schedule; none; unknown keys; self-managed rotation or after the Opsgenie end of service (2027-04-05); coordinated incident engaging many products; one schedule shared by several products; a folder that is report placement only, not a product. Open cardinality for 165.1: schedules per product, legacy 0..1.

OQ6 (approved) Test seams while legacy modules are mid-reshape. Two zones, both on the freeze-baseline ratchet (migration.md rule 3, app/bin/freeze_guard.py): (a) target code and its tests are strict: testing.md already says Protocol fakes at the seam, and production shape is guarded (import contracts, package shape, fake coverage, key ownership), but nothing guards app/tests; a new guard flags tests of features/ and capabilities/ that patch a module path inside features/, capabilities/ or modules/ instead of registering a Protocol fake, baseline seeded once. (b) legacy pins keep strict assertions (pin contract) and best-available seams: an external edge where reachable, otherwise an internal legacy function patched only through a named fixture in legacy_surface/conftest.py naming its owning rebuild task, counted in a seam baseline that only shrinks; the rebuild PR rewires that fixture to the target fake and removes the entry. Each rebuild task carries the same cutover ACs; a tangle that blocks a seam is resolved by migration.md rule 5 (move pure logic early), not a deeper patch. This PR expects no internal seam (every edge in step 1 is reachable). Guard as its own task before Stack L's first rebuild.

## Assumptions and doubts (verify at pickup)
- Bolt routes interactive_message by callback_id to app.action("archive_channel") (verified for handle_incident_action_buttons in 36.1.1).
- Bolt runs only the first matching event listener (first reaction test proves it).
- Every edge close_incident touches is faked before the first archive dispatch.
- The command that opens the folder-metadata modal and the retro modal still exists in handle_incident_command (incident_helper.py 198-437).
- schedule_event reads datetime.utcnow: assert invariants, do not freeze time.

## Blast radius and rollback
Tests, conftest and one markdown file; no runtime effect; one git revert.

## Verification (from app/)
During work: uv run ruff check . and uv run pytest tests/integration/legacy_surface/<file>. At the end, once each, sequentially: uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' (no new errors in touched files), then uv run pytest tests --ignore=tests/smoke. Also make check-import-contracts, make check-settings-key-ownership, make check-package-shape.

## Size estimate
Production 0. This task: 4 new test files + conftest + INVENTORY + 3 ADRs (9 files, ~700 test LOC). TASK-36.1.5: 2 new test files + conftest + INVENTORY (4 files, ~550 LOC).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-06 implemented (tests and docs only, from main 76f73bde): conftest.py additive (incident_surface fixture: in-memory DynamoDB client under the incidents adapter, Google client factory for Drive/Docs/Sheets, view helpers reading modal ids from recorded views; one internal legacy seam, legacy_sre_web_client_seam, owner TASK-145.8); test_incident_roles_surface.py (13, 2 legacy_only), test_incident_field_update_surface.py (12), test_incident_channel_archive_surface.py (8), test_incident_folder_metadata_surface.py (5, all legacy_only); INVENTORY.md 9 rows and the id sentence. Pytest collects only test_*, so the ADR names test_legacy_only_*. Mutation-checked each file. Legacy behaviour pinned as is, for TASK-145.8 to rule: /sre incident products answers Unknown command (the key is product, help says products); archive sends incident_channel_archived to Sentinel twice; a refused archive in a non-incident channel still sends it (not pinned); re-saving roles with no roles line in the purpose leaves a doubled newline. Gates: ruff clean; contracts 13 kept; key ownership OK; package shape OK (10 baselined); mypy 41 pre-existing in 14 files (none in touched files); pytest 6475 passed.
<!-- SECTION:NOTES:END -->
