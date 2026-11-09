---
id: TASK-145.9
title: >-
  Rebuild timeline capture and the stale-channel nudge in incident/response;
  summarize moves in; incident leaves aws_platform
status: To Do
assignee: []
created_date: 2026-10-09 16:43
updated_date: '2026-11-09T19:06:00Z'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.8
  - TASK-36.3
  - TASK-25.10
  - TASK-145.5.7
  - TASK-36.1.5
references:
  - https://github.com/cds-snc/sre-bot/issues/1700
parent_task_id: TASK-145
priority: medium
type: feature
ordinal: 359000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer C3 of TASK-145. Rebuilds the floppy-disk reaction handlers (message captured into the report's timeline and the record's timeline entries; removal deletes both), the ack-only reaction fallbacks and the stale-channel nudge job, moves /sre incident summarize from scribe into response, and deletes modules/incident/db_operations.py.

THIS SLICE
- Timeline capture through IncidentReport and IncidentStore; entries are their own records.
- Timeline layout in core/store.py: timeline_table(name), partition incident_id and sort entry_key, with the table name from the incident core settings; an entry_key helper building <posted_at>#<entry_id> with posted_at as fixed-width ISO-8601 UTC (isoformat(timespec="microseconds"), +00:00, format_stored_time in core/adapters/incident_items.py); captured_entry_id, a uuid5 over system, tenant, conversation and message id, so a re-capture writes the same key and put_if_not_exists dedupes; a uuid4 id for manual entries. The vendor message id stays in the entry's source_message reference.
- The nudge job is registered by response through the background-job hookimpl with its schedule and lease from the response settings slice; the hand import in app/jobs/scheduled_tasks.py is deleted. Stale detection reads the store, not a channel-name pattern; it queries the sparse open index through IncidentStore.list_open (open_bucket = OPEN, sort opened_at), never a scan, so a closed incident drops out; the nudge carries the archive action id and the schedule-postmortem action id from common/vocabulary.
- summarize: scribe/service.py's summary path becomes response/service/summary.py (prompt text in response/service/prompt.py; layout table of 2026-11-06, feature-packages.md) with its settings slice, catalogue (incident_summary) and tests renamed test_incident_response_summary_*; the command registers under incident.response. It calls the text-generation capability (TASK-25.10).
- After this slice no module under app/modules/incident imports db_operations or packages.aws_platform; the incident seam baseline entries are removed, which is what TASK-88 needs.
- Legacy registrations and the job hand import removed in the same PR; pinned by TASK-36.1 (reactions) and TASK-36.3 (job).
- Security guard (incident-management.md 2026-11-06): comms' _security_gate (comms/service/draft.py) moves into core as one guard exported by core/api.py; comms and summarize call it before the model call, keeping their log events and the SECURITY_CONFIRMATION_REQUIRED code; summarize gains the responder's confirmation, so a security incident's transcript reaches the model only after it.
- Transcript text: comms' build_transcript (comms/service/prompt.py) and scribe's _transcript_line render the same messages twice; the shared rendering moves into core (feature-packages.md rule 3, two consumers) and both callers use it, with output unchanged for each.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Floppy-disk capture and removal write and delete timeline records and report entries through core; the legacy handlers are gone
- [ ] #2 The stale-channel job is registered by response through the hookimpl and reads the store; app/jobs/scheduled_tasks.py no longer imports it
- [ ] #3 /sre incident summarize is handled by response/summary.py and scribe no longer holds a summary path, catalogue or test
- [ ] #4 No module this task rebuilds imports modules.incident.db_operations or packages.aws_platform for incident data, and the incident seam baseline entries it owns are removed (the repository-wide check is TASK-145.12's)
- [ ] #5 Timeline capture writes through the timeline store TASK-145.8 adds to core/store.py; captured_entry_id is a uuid5 over system, tenant, conversation and message id, so a re-capture yields the same key (tested)
- [ ] #6 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
- [ ] #7 IncidentReport gains append_timeline_entry(ReportReference, entry) in core/api.py with its Google Docs adapter and fake (parity test); the legacy timeline rewrite in modules/incident/incident_document.py (lines 82-302 at main 5deb8406, build_timeline_replacement included) moves into core/adapters/google_docs.py, and incident_document.py is deleted with its legacy test once 145.8 has moved the status mapping and no caller remains
- [ ] #8 Cutover per decisions/migration.md step 4 and decisions/testing.md seams: the pins pass with assertions unchanged, their fixtures rewired to the target Protocol fakes with the matching seam-baseline entries removed; legacy_only_* tests for behaviour this task ends are deleted; modal-internal ids take the incident.<subdomain> prefix and ids on posted messages stay registered as legacy aliases; new tests pass make check-test-seams
- [ ] #9 /sre incident summarize is refused for a security incident, or one whose flag cannot be read, until the responder confirms, through the core security guard; comms drafting uses the same guard with its behaviour and log events unchanged
- [ ] #10 Transcript text for the model is rendered by one core function used by comms and summarize, each prompt's transcript text unchanged
- [ ] #11 summarize lives in response/service/summary.py (prompt in response/service/prompt.py); make check-package-shape passes with no new baseline entry
- [ ] #12 /sre incident summarize resolves its incident through find_incident_for_conversation (a channel that is not an incident gets the not-an-incident reply) and reads the incident's conversation (the primary IncidentBinding); a behaviour change, so not in the mechanical summarize move
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
APPROVED 2026-11-09 (human): the program breakdown and the revised recommendations of the second OQ assessment comment on TASK-145.7 (OQ1-OQ20), including the L5r rollback guard, the on-call capability path (25.6 -> 146.1, 146.3 in L9a), L9c and the IncidentBinding rename. Subtasks created 2026-11-09. Stack L program re-plan of 2026-11-09 against main 3075170b; cross-task order and rules in TASK-145.7's plan (sections 0 and 2) and doc-11 row 18. Supersedes the 2026-10-09 outline (145.9.1/145.9.2).  Outline; each slice is planned in full at pickup.

## 1. Re-grounded state
- Reaction capture: registered incident_helper.py:160-163; handlers incident_conversation.py:261 (added) and :322 (removed), matcher :74; they read Slack (channel name, bookmarks: get_incident_document_id :230) and rewrite the report timeline (incident_document.py:82 update_timeline_section). CORRECTION: they do not call db_operations.log_activity (the outline's Discovered state is wrong) and read no incident item.
- Stale nudge: app/jobs/scheduled_tasks.py:150-153 and :165-167 -> modules/incident/notify_stale_incident_channels.py:10 (Slack channels only); it posts the archive_channel button that TASK-145.8 L7a re-registers with that id as a legacy alias.
- Summarize: features/incident/scribe/entrypoints/slack.py:211 -> scribe/service.py:906; builds a ConversationReference from payload.channel_id with no store lookup (AC #12 changes that).
- Core security guard: comms/service/draft.py:410 _security_gate (called :352, refusal :429-439, SECURITY_CONFIRMATION_REQUIRED). Shared transcript rendering: comms/service/prompt.py:68 build_transcript and scribe/service.py:511, :515 _transcript_line (also :1003).
- None of these surfaces reads incident items, so 145.9 does not gate the declare cutover: it follows L9b only to keep one cutover in flight at a time.
## 2. Size gate: trips (~1,100 production LOC with the moves, >10 files, core + response + scribe + comms + jobs, moves mixed with behaviour). Split:
- L10a core report timeline (~250 / 4, incident core; mechanical move + Protocol): IncidentReport.append_timeline_entry (and removal) in core/api.py, the legacy rewrite incident_document.py 82-302 (build_timeline_replacement included) moved verbatim into core/adapters/google_docs.py, fake + parity test (AC #7). The legacy handlers call the moved function. Waits: -.
- L10b cutover capture + nudge (~350 / 8, response; waits L10a, L3 (timeline store, if OQ13 moves AC #5 there), L7a (archive alias)): reaction handlers registered by response, writing timeline records (captured_entry_id uuid5, re-capture same key) and report entries through core (AC #1, #5); the nudge registered by response's background-job hookimpl reading the store, posting the prefixed archive id (AC #2); jobs/scheduled_tasks.py no longer imports it; incident_document.py and its legacy test deleted when no caller remains (AC #7 end). Pins (36.1.5) rewired.
- L10c summarize move (~450 moved / ~8, response + scribe; mechanical; waits TASK-25.10.3): summary.py and prompt.py into response/service/ (AC #3, #11); scribe loses its summary path, catalogue and test; behaviour unchanged; optional text-generation use with no requirement in response (2026-11-09 ruling). Size exception requested for a pure move (same basis as 25.10.2's).
- L10d guard, rendering, command check (~200 / 6, core + response + comms; behaviour; waits L10c): one core security guard used by comms and summarize (AC #9, comms behaviour and log events unchanged), one core transcript renderer (AC #10, each prompt's text unchanged), summarize resolves through find_incident_for_conversation and reads the primary binding's conversation (AC #12).
Only L10c and L10d wait on TASK-25.10 (all three slices); L10a and L10b do not.
## 3. AC changes proposed (comment): AC #4 (no module imports modules.incident.db_operations for incident data) cannot hold at L10: modules/dev/incident.py and incident_folder.py create_missing_incidents import it until TASK-145.12 (L11). Move the check to 145.12 AC #2 or narrow #4 to the surfaces this task rebuilds. AC #5 (timeline_table, entry_key, ids) moves to TASK-145.8 L3 if OQ13 is approved (severity changes are the first timeline writer).
## 4. Blast radius: L10b changes reaction capture and the nightly nudge (one revert each); L10c none (move); L10d the comms security refusal path (tested unchanged). The inline baseline lines 10-12 (test_incident_updates_command_surface.py) are this task's to remove at L10d.

## Subtasks (created 2026-11-09)
L0 TASK-145.7.1; L1 TASK-145.7.2; L2a TASK-145.7.3; L2b TASK-145.7.4; L3 TASK-145.8.1; L4a TASK-145.7.5; L4b TASK-145.7.6; L4c TASK-145.12.1; L5 TASK-145.7.7; L5r TASK-145.8.2; L6a TASK-145.8.3; L6b TASK-145.8.4; L7a TASK-145.8.5; L7b TASK-145.8.6; L8 TASK-145.7.8; L9a TASK-145.7.9; L9b TASK-145.7.10; L9c TASK-145.7.11; L10a TASK-145.9.1; L10b TASK-145.9.2; L10c TASK-145.9.3; L10d TASK-145.9.4; L11 TASK-145.12.2; side: TASK-25.6 -> TASK-146.1 (before L9a); TASK-146.3 delivered by TASK-145.7.9; L12 (job rerun) is TASK-145.12.2's notes. Other slices are planned in full at pickup.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-13 re-ground: with the TASK-147 postmortem-records flag off, capture and removal behave exactly as today, including the report's timeline section and who may react. The timeline records are written regardless of the flag, but nothing user-facing reads them until it is on. The capture-permission rule is decided by TASK-147.1 and announced by TASK-147.8; this slice does not change it.

2026-10-14 (TASK-145.5 split): precondition before this task merges: the TASK-145.5.7 incident legacy upgrade job (which also fills the open index) has run (dry run, then apply) in each environment after TASK-145.8 deployed and reported pending=0; TASK-145.13 removes the job (updated 2026-10-15). Timeline key format supersedes 'ts#entry_id': partition incident_id, sort entry_key '<posted_at ISO-8601 UTC, microseconds, +00:00>#<entry_id>', where entry_id is a uuid5 over system, tenant, conversation and message id for captured messages (a re-capture writes the same key, so put_if_not_exists dedupes) and a uuid4 for manual entries; the Slack ts stays in the source_message reference. The GSIs use projection ALL. IAM index access comes from TASK-152.

2026-11-04 (TASK-145.5.7 planning, human approved): the nudge job registers with the lease_ttl keyword on register_interval/register_daily added by TASK-145.5.7.1, its TTL from the response settings slice (reliability.md 2026-11-04). Precondition unchanged: the TASK-145.5.7 job has run (dry run then apply) after TASK-145.8 deploys.

2026-11-05 (human, TASK-145.6.2 C1): IncidentReport ships in 145.6.2 without append_timeline_entry; this task adds it with timeline capture and moves the legacy timeline rewrite (~220 lines) from incident_document.py then. Size gate: count this move in the 145.9 plan; it may split the slice.

2026-11-06: depends on TASK-36.1.5 (reaction pins split from TASK-36.1.2). Reaction events carry no ids; the pins assert one timeline entry in the report and rewire to the IncidentReport fake at rebuild.

2026-11-06 (human, TASK-186 review): scope gains the core security guard (comms' gate moves into core/api.py; summarize calls it), the shared transcript rendering into core, and the layout-table paths response/service/summary.py and service/prompt.py (description and ACs updated). Re-check the size gate at Stack L's re-plan; split the guard and transcript moves into their own layer if it trips.

2026-11-06 (TASK-36.1.5 pins): test_incident_conversation_reaction_surface.py pins timeline capture: one linked, attributed entry per floppy disk, chronological order, re-add no-op, removal deletes only that entry, a stale-revision write retried from a fresh read, ack-only for other emoji and non-incident channels. Legacy behaviour to rule on: every failure is logged and swallowed (the reacting user is never told). Rewire the pins to the rebuilt append_timeline_entry.

2026-11-09 (TASK-25.10 plan, open for this task's re-plan): incident.scribe declares Requirement('openai.tenant') (TASK-172; TASK-25.10.3 adds 'text_generation.model'), so scribe aborts boot without a model gateway. When this task moves scribe's summarize path into incident.response, the requirement must not move with it unchanged. Requiring text generation in response would abort the whole response plugin, declare included, in any environment without a gateway, and ci.toml would switch it off, dropping its CI boot coverage (plugins.md). Recommendation: the moved use becomes optional, like comms' drafting. It asks the capability's is_available() (TASK-25.10.2) and answers with an unavailable message otherwise, and the plugin declares no text-generation requirement. This narrows TASK-172's 'scribe requires it' to the dissolved package. It needs a human ruling at this re-plan, recorded in plugin-architecture.md and plugins.md.

2026-11-09 (human): ruled. The moved text-generation use is optional: it asks is_available() (TASK-25.10.2) and answers with an unavailable message otherwise. The plugin it moves into declares no text-generation requirement. TASK-172's 'scribe requires it' holds only while scribe exists. Record it in plugin-architecture.md and plugins.md with this task's PR.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-26T15:06:00Z

---

2026-10-26: TASK-112.4 first moves notify_stale_incident_channels off the Bolt app: it takes the integrations/slack Web API client per run and is scheduled only when [slack.tenant] is configured. The rebuilt nudge keeps both properties (decisions/reliability.md).

---

created: 2026-11-05T15:54:00Z

---

2026-11-05: _SRE_BOT_GENERATED_TIMELINE in core/adapters/google_docs.py (the section writer) and START_HEADING in modules/incident/incident_document.py are the same template marker. When the timeline is rebuilt here, keep one definition, with the report's timeline in the adapter. TASK-145.11 leaves it in the adapter.

---

created: 2026-11-05T20:31:00Z

---

2026-11-05 (TASK-145.6.3 approval, OQ6): AC #8 added. incident-management.md Checks require every incident command to resolve its incident through find_incident_for_conversation; summarize skips it today and 145.6.3 keeps that behaviour. The layer that carries it is chosen at this task's split approval (not 145.9.2, the mechanical move). 145.6.3 also makes the transcript reader take a ConversationReference and return OperationResult (synchronous on WebClient, tolerated in transport-slack.md until its last caller moves).

---

created: 2026-11-09T18:10:00Z

---

Stack L re-plan 2026-11-09: proposed AC changes (not applied): AC #4 moves to TASK-145.12 (OQ20); AC #5 moves to TASK-145.8 L3 if OQ13 is approved. Correction: reaction capture does not call db_operations.log_activity.

---
<!-- COMMENTS:END -->
