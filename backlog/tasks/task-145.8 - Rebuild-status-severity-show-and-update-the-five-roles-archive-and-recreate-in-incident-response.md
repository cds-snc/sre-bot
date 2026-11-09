---
id: TASK-145.8
title: >-
  Rebuild status, severity, show and update, the five roles, archive and
  recreate in incident/response
status: To Do
assignee: []
created_date: 2026-10-09 16:43
updated_date: '2026-11-09T18:10:00Z'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-27.2
  - TASK-36.1.2
references:
  - https://github.com/cds-snc/sre-bot/issues/1699
parent_task_id: TASK-145
priority: medium
type: feature
ordinal: 358000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer C2 of TASK-145. Rebuilds the /sre incident subcommands and interactions that read and change an incident: status, the information display and update modals, roles, archive and the recreate-missing-resources path.

RULES
- Every command resolves its incident through find_incident_for_conversation; only operations that write to the conversation call conversation_is_writable. A status, severity, timing or report update on an incident whose channel is archived succeeds and reports that the channel message was skipped.
- Status change fans out from the record: atomic field update, then the report's status text, then the list projection (write-only), then the channel message when writable.
- Severity is set at declare and changed from the update modal (none and SEV0 to SEV4, SEV0 new); it is a record field, never read from a document.
- The five roles (incident commander, operations lead, communications lead, policy lead, postmortem owner) are stored on the record and shown in the show modal; the report's Drive properties are no longer written. The roles command offers all five; only IC and OL are required.
- The show modal renders every link from the record's references through the owning adapter, with the stored url as a hint only.
- IncidentStore.update_field maps to RecordStore.update (TASK-27.2) with a set change and the optional expected guard: a guard that does not hold is a distinct non-error result, and a missing incident is NOT_FOUND. Closed sets the status and removes open_bucket and opened_at in one update, so the sparse open index drops the incident atomically.
- A write to a Slack view or message that no longer exists (views.update not_found after the user closed the show modal) is an expected outcome, not a listener error, classified as TASK-151 does.
- The recreate path replaces a missing resource's reference map whole (never patched), guarded on the old channel_id scalar, so a concurrent change wins.
- Writers set record_version = RECORD_VERSION, imported from core/store.py (TASK-145.5.4), on every item they write in the end-state shape (recreate, reopen); reopen sets open_bucket = OPEN_BUCKET and opened_at through format_stored_time (core/adapters/incident_items.py). How an update treats an item still without record_version (before the TASK-145.5.7 job has run) is decided at planning; it never stamps record_version on a partly upgraded item.
- security_incident (bool) is editable by the coordinator from the update modal. Whether a flip triggers actions (true at declare invites the security group) is decided at planning.
- Parity rebuild: close keeps today's behaviour (closes all resources and archives the channel). The status lifecycle and close redesign is a separate task, TASK-154.
- Legacy registrations removed in the same PR; names, fields and replies unchanged apart from the three added role pickers, pinned by TASK-36.1.

2026-11-06 (TASK-36.1.2 OQ1/OQ2, human-approved): the folder-metadata interactions and the products subcommand are not rebuilt: incident-management.md (2026-11-04, 2026-11-05) builds no ProductCatalog over Drive folders; the product's on-call schedule reference moves to the bot's own product list (TASK-165.1 import, TASK-146.3) and the legacy editor is deleted by TASK-145.13. confirm_click is the retro modal's button and belongs to TASK-145.10. Rebuilt modal-internal ids take the incident.response prefix; archive_channel, on stale-channel nudges already posted, keeps a registered legacy alias until TASK-145.13 (decisions/transport-slack.md).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every rebuilt command and interaction resolves its incident through find_incident_for_conversation; a write to an archived channel is skipped and reported, not failed
- [ ] #2 Severity and the five roles are read from and written to the record; no code path writes Drive properties for roles
- [ ] #3 Status change updates the record, the report text, the projection and the channel in that order, each failure logged and the rest continuing
- [ ] #4 The pinned behaviour of status, show, update, roles and archive passes unchanged
- [ ] #5 Recreate replaces a reference map whole, guarded on the old channel_id scalar; show renders links through the owning adapter with the stored url as a hint
- [ ] #6 security_incident is editable from the update modal; the flip-action decision is recorded in the plan
- [ ] #7 Writes in the end-state shape set record_version = RECORD_VERSION from core/store.py; reopen sets open_bucket and opened_at and Closed removes them in one update; an item without record_version is never stamped by a partial update (tested)
- [ ] #8 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
- [ ] #9 IncidentReport gains set_status_text(ReportReference, status) in core/api.py with its Google Docs adapter and fake (parity test); the legacy status mapping in modules/incident/incident_document.py (lines 55-80 at main 5deb8406) moves into core/adapters/google_docs.py and the legacy caller is repointed or deleted
- [ ] #10 Cutover per decisions/migration.md step 4 and decisions/testing.md seams: the pins pass with assertions unchanged, their fixtures rewired to the target Protocol fakes with the matching seam-baseline entries removed; legacy_only_* tests for behaviour this task ends are deleted; modal-internal ids take the incident.<subdomain> prefix and ids on posted messages stay registered as legacy aliases; new tests pass make check-test-seams
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PROPOSED, AWAITING APPROVAL. Stack L program re-plan of 2026-11-09 against main 3075170b; cross-task order and rules in TASK-145.7's plan (sections 0 and 2) and doc-11 row 18. Supersedes the 2026-10-09 outline (145.8.1/145.8.2, "after TASK-145.7"). Planning only: no subtasks until approved. This task's slices: L3 (core update operations), L6a, L6b, L7a, L7b (reader cutovers, before the declare cutover L9b).

## 1. Re-grounded state (legacy paths are frozen; not references)
- Dispatcher: modules/sre/platforms/slack.py:49 handle_incident_command (registered ~205, legacy_mode); incident_helper.py:196-240; registrations incident_helper.py:144-166.
- show: incident_helper.py:276 -> information_display.py:14 (get_incident_by_channel_id :18, Incident(**item) :29, severity rendered :50).
- update modal: button update_incident_field (incident_helper.py:164) -> information_update.py:50; view update_field_modal (:165) -> :264; reads Incident (:329); writes db_operations.update_incident_field (:322) for detection_time, start_impact_time, end_impact_time, retrospective_url, severity (none, sev-1..sev-4: FIELD_SCHEMA 25-34), status; posts to the channel (323-327) and appends a logs line (log_activity, db_operations.py:159-160). Write order today: report, sheet, record, channel (306-327).
- status: `status update <s>` incident_helper.py:366 -> :577 (reads :592) -> incident_status.update_status at :603 WITHOUT incident_id, so the slash path never writes the record (incident_status.py:56-59 skips it); it writes the report status text (incident_document, lines 55-80 mapping) and the sheet (incident_folder.py:311). `status show` is a stub (382-383).
- roles: `roles manage` incident_helper.py:388 -> incident_roles.py:57 (Drive appProperties ic_id/ol_id); view view_save_incident_roles (:155) -> incident_roles.py:13 (Drive metadata 20-21, purpose 54). Two pickers (IC, OL); the record has five roles.
- archive: button archive_channel (incident_helper.py:159) on the stale-nudge message -> incident_conversation.py:430 -> close_incident (incident_helper.py:435: read :443, refuse non-incident 459-470, status Closed written through update_status with incident_id :475, post, conversations_archive :501, Sentinel :508), then Sentinel again (incident_conversation.py:452).
- recreate: `create resources` incident_helper.py:254 -> :631 -> modules/incident/core.py:336 (read :377; no record -> _create_database_record :406/:316).
- Pins: tests/integration/legacy_surface/test_incident_field_update_surface.py (show, update, status: 12), test_incident_roles_surface.py (13, 2 legacy_only), test_incident_channel_archive_surface.py (8); fixture legacy_sre_web_client_seam conftest.py:788-794 (owner TASK-145.8), used by the incident_surface fixture :803; baseline app/bin/baselines/test_seams_legacy.txt:20. No pin for slash status update, status show, roles show or recreate (recreate: tests/modules/incident/test_recreate_missing_resources.py). Inline baseline lines 10-12 (test_incident_updates_command_surface.py) carry no owner: assigned to TASK-145.9 (summary) at its plan.
- Core on main: IncidentStore has no write; StatusUpdateStore.transition (store.py:360-379) is the guarded-update model; RecordStore.update(table, key, changes, *, expected) with Set/Remove/Increment (contracts/records/store.py:131-150, 288); an unmet guard returns success with data=None. upgrade_legacy_item (core/adapters/legacy_items.py:99) is pure; the job's per-item plan (_plan_item, legacy_upgrade.py:230) is private until L2b.

## 2. Dependency reversal (verified)
Readers and update operations need only IncidentStore.get/find_by_conversation, the bridge, RECORD_VERSION/OPEN_BUCKET, format_stored_time and RecordStore.update: none of declare. Recreate needs 145.7's inert core slices L4a (conversation additions) and L4b (VideoCall), not the declare cutover. So TASK-145.8 no longer depends on TASK-145.7; TASK-145.7 depends on TASK-145.8 (its cutover L9b waits on L6a-L7b). Per-slice dependencies (L7b on L4a/L4b, L3 on L2b) are wired when the subtasks are created.

## 3. AC #7: writes onto items the job has not upgraded (recommendation: upgrade-on-write)
Legacy declare keeps creating legacy items until L9b, and the sheet import and dev add-incident until L11, so items without the marker keep appearing after the job's first run (L8). "Refuse until the job has run" would therefore refuse status, severity and role changes on every incident declared between L8 and L9b: rejected. Upgrade-on-write: a core write that reads an item without record_version calls the shared plan_item_upgrade (L2b), puts the binding (idempotent), then applies ONE guarded update holding the upgraded attributes, the requested change and record_version 2, guarded on record_version absent plus every read attribute (the job's guard). A lost guard re-reads and retries once, then returns a classified conflict. An unreadable legacy item (Migration rule 7) refuses the write with the field named, exactly as the job lists it. This keeps AC #7 ("an item without record_version is never stamped by a partial update") and makes writer and job one rule.

## 4. Slices
L3 core update operations (~350 / 5, incident core; waits L2b): IncidentStore gains update_fields(incident_id, changes: IncidentChanges, *, expected_version) for title, impact times, retrospective link, severity, security_incident; set_roles(incident_id, roles); close(incident_id) (status Closed, open_bucket and opened_at removed in one update); reopen(incident_id) (status, open_bucket, opened_at = format_stored_time(now) in one update); each through upgrade-on-write (section 3); in-memory fake with the same guard rules. Severity changes are recorded: append_timeline_entry of a system entry (kind severity_changed, from, to, by) on sre_bot_incident_timeline; this pulls 145.9 AC #5 (timeline_table, entry_key, ids) into L3 (proposed in a comment on 145.9; OQ13). Tests: tests/unit/features/incident/core/test_incident_core_store_update_*.py: guarded update happy, lost guard, upgrade-on-write in one pass (binding + marker 2), unreadable legacy item refused, close/reopen bucket rules, severity change appends one timeline entry, replay of the same change.
L6a cutover show + update modal (~380 / 9, response; waits L3): response/entrypoints/slack.py registers `incident show` and the modal (ids incident.response.show / incident.response.update_field; modal-internal, prefixed; the show view's update buttons are inside the modal); views render links through the owning adapter with the stored url as hint (AC #5 part); update writes through L3 in today's order with each failure logged and the rest continuing; severity options none, SEV0-SEV4 decided at OQ14 (recommend: keep none, sev-1..sev-4 until L9b adds SEV0 to both pickers together, so the pin is unchanged here); security_incident editable (AC #6: the flip is a field of the update modal, no separate action). Deletes information_display.py, information_update.py and their registrations. Pins: field-update pins rewired to fakes.
L6b cutover status (~300 / 7, response + core adapter; waits L3, L4c): `incident status update` writes record, report text, projection, channel in that order (AC #3). Named behaviour change: the legacy slash path never wrote the record. IncidentReport.set_status_text with the mapping moved from incident_document.py 55-80 into core/adapters/google_docs.py (AC #9); projection update through L4c. Deletes incident_status.py.
L7a cutover roles + archive (~350 / 8, response; waits L1, L3): five roles on the record (set_roles); no Drive property writes for roles (AC #2); purpose rewritten from the record; archive button incident.response.archive with legacy alias archive_channel (posted by the legacy stale nudge until L10b); close through L3, archive, one Sentinel event. 36.1.2 rulings (OQ15): Sentinel event sent once (the pin asserts a set, unchanged); a refused archive logs nothing; roles purpose output kept exactly as pinned (the note's "doubled newline" does not match the pin: append path gives "Checkout outage \nIC:"; a wording fix belongs to a UX task); products vs product is not this task's (ADR 2026-11-06 retires /sre incident products; 145.13 deletes it). Deletes legacy_sre_web_client_seam (conftest.py:788-794) and baseline line 20 once the roles, archive and field-update pins no longer request it.
L7b cutover recreate (~250 / 6, response; waits L3, L4a, L4b): `incident create resources` fills each missing reference (report, video call, bookmarks) through core and set_reference; replaces a map whole guarded on the old value (AC #5). A channel with no record: OQ16 (recommend: answers not-an-incident, every command resolves through find_incident_for_conversation (AC #1); the legacy record-creating branch is not carried). Deletes recreate_missing_resources, _create_database_record and their test.

## 5. AC traceability
#1 L6a-L7b. #2 L3 + L7a. #3 L6b. #4 L6a, L6b, L7a. #5 L6a (links) + L7b. #6 L6a. #7 L3 (section 3). #8 every PR. #9 L6b. #10 L6a-L7b.
Proposed new AC (comment): each person-chosen severity change is recorded as a timeline entry (Revision 1; TASK-154 owns lifecycle only, its description has no severity scope).

## 6. Blast radius and rollback
Each cutover changes one group of commands; one revert restores the legacy registration (legacy code deleted in the same PR returns with the revert). Items written by the rebuilt writers are end-state (marker 2): a reverted legacy reader would fail on them (Incident(**item), extra=forbid). Mitigation: L6a-L7b ship and soak before L8; a revert after upgrades must be paired with a forward fix, not the legacy reader; state it in each PR body. L8 waits on all four deployed.

## 7. Assumptions
1 The bridge maps every field the modal writes (verify at L3 against legacy_items.py). 2 The archive_channel action carries only the archive branch (verify incident_conversation.py:430 at L7a; another branch would move with it). 3 Pins need only fixture rewiring (assertions unchanged).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-04 (TASK-145.5.7 planning, human approved): the TASK-145.5.7 upgrade job writes each legacy item in one update guarded on record_version absent plus every scalar attribute the bridge read, at its read value (status, name, user_id, created_at, security_incident, channel_id, report_url, meet_url, severity, the legacy times, incident_commander, operations_lead) and each end-state attribute it sets as read. Whatever this task decides for a partial update of an item without record_version must keep that guard meaningful: a write here that changes one of those attributes makes the job's write lose (guard_lost), never be overwritten by it.

2026-11-05 (human, TASK-145.6.2 C1): IncidentReport ships in 145.6.2 without set_status_text; this task adds it when it rebuilds the status surface (rule: status fans out to the report's status text) and moves the legacy status mapping from incident_document.py then. The ADR's end surface (decisions/incident-management.md) is unchanged.

2026-11-06 (TASK-36.1.2 pins): legacy bugs pinned as is, to rule in this plan: /sre incident products answers Unknown command (dispatcher key product, help text products); archive sends incident_channel_archived to Sentinel twice (close_incident and archive_channel_action); a refused archive in a non-incident channel still sends it; re-saving roles with no roles line in the purpose leaves a doubled newline. The pins' one internal seam, legacy_sre_web_client_seam, is deleted here.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-03T19:00:00Z

---

Coordinated incidents ADR note (doc-11 A1/E1): re-plan the chosen change-severity surface to record each person-chosen severity change. Do not derive severity from the count or breadth of engagements. Choose one owning task during planning to avoid duplicate behavior.

---

created: 2026-11-09T18:10:00Z

---

Stack L re-plan 2026-11-09: dependency on TASK-145.7 reversed (verified: readers and updates need none of declare; recreate needs only 145.7's inert core slices L4a/L4b). Proposed new AC: each person-chosen severity change is recorded as a timeline entry (OQ13). AC #7 resolved by upgrade-on-write (plan section 3). Open questions OQ13-OQ16 and OQ18 are on TASK-145.7's comment.

---
<!-- COMMENTS:END -->
