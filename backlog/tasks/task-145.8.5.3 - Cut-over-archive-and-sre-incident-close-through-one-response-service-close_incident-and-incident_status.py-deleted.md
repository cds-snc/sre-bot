---
id: TASK-145.8.5.3
title: >-
  Cut over archive and /sre incident close through one response service;
  close_incident and incident_status.py deleted
status: Done
assignee: []
created_date: '2026-11-16T19:34:00Z'
updated_date: '2026-11-20T22:06:00Z'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.8.4
  - TASK-145.8.5.1
  - TASK-145.8.5.2
references:
  - decisions/incident-management.md
  - decisions/observability.md
  - decisions/migration.md
parent_task_id: TASK-145.8.5
priority: medium
type: feature
ordinal: 525000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L7a.3 (doc-11 row 18.L7a.3), stacked above L7a.1. Split from TASK-145.8.5 on 2026-11-16 (human, OQ1). response/service/archive.py archive_incident: find the incident (refusal decided by the record), join the channel, close through change_status (record first, report, list, channel notice), post the archived notice, archive, then one incident_channel_archived event with a minimal payload {incident_id, conversation_id, user_id, at} (OQ8). Serves the rebuilt `/sre incident close` and the stale notice's archive button (incident.response.archive with the archive_channel alias scoped to the archive value, TASK-145.8.5.2); ignore stays legacy until TASK-145.9.2, schedule_retro until TASK-145.10. Plan in full at pickup.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 archive_incident in incident.response: find (store down or not an incident: refusal, nothing written, no event), join, change_status(Closed) (a record failure stops it), archived notice, archive, then exactly one incident_channel_archived event with {incident_id, conversation_id, user_id, at} after a successful archive, sent through a response adapter tagged TODO(TASK-122)
- [x] #2 The archive button is incident.response.archive with the archive_channel alias scoped to the archive value; /sre incident close is registered by incident.response on the same service (pinned first); close_incident, handle_close, its dispatcher entry, incident_status.py and test_incident_status.py are deleted; ignore and schedule_retro stay on the legacy listener
- [x] #3 IncidentConversation gains async join (Slack conversations.join, already a member is success) on the adapter and the fake, held to the parity suite; incident-management.md (join is a write step, never the writability check) and observability.md (rebuilt surfaces send named events with minimal fields, never request bodies) carry dated Changes lines
- [x] #4 The archive pins pass with fixtures rewired; the refusal pin presses in a channel with no record, citing the ruling (kind b); the double event and the event on a refusal are pinned as test_legacy_only_* and deleted (kind a); new tests assert one event and none on refusal; update_incident_document_status's owner note names TASK-145.8.3
- [x] #5 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams, make check-settings-key-ownership and pytest tests --ignore=tests/smoke pass
- [x] #6 The PR body lists each named change with its kind (Sentinel once and none on refusal: a; refusal by record, record failure stops, minimal event payload: b), the revert target (one git revert; the L5r guard) and the merge order (after L6b)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PROPOSED 2026-11-17, revised the same day after the program-scope OQ assessment (task comment); APPROVED 2026-11-17 (human): OQ1 size exception; OQ2-OQ6 as recommended. Planned against origin/main 557b20ef (#1862 squashed, #1863 82155a96) plus L7b ddac794d; rulings TASK-145.8.5 OQ1-OQ8 (approved 2026-11-16), TASK-145.8.5.2 OQ7 (this task deletes the legacy archive branch).

0. Base and order
- Stack L layer above L7b (#1865, top). The local stack predates #1862's squash and lacks #1863's legacy_callback_values, so the human first syncs the stack onto main (gh stack sync; L7b then sits on main 557b20ef), then gh stack add stack-l/task-145.8.5.3-archive-close. Implementation starts only on that branch.
- Merge order: after #1865 (L7b); L6a (145.8.3) stacks above. Once this layer is submitted, #1865 may merge.

1. Core: IncidentConversation.join (AC #3)
- features/incident/core/api.py: Protocol gains async join(conversation) -> OperationResult[None]; docstring: a write step for a write that needs membership; never part of the writability check.
- core/adapters/slack.py SlackIncidentConversation.join: conversations.info (read client); is_member -> success with no call; else conversations.join (write handle); already_in_channel counts as done (_JOIN_DONE); any other Slack error (private channel the bot left: method_not_supported_for_channel_type; is_archived) -> the mapped failure. The info read avoids join's refusal on a private channel the bot is already in (legacy reads info first too, incident_helper.py:368-371).
- core/adapters/in_memory.py InMemoryIncidentConversation.join: member set; unknown conversation not found; archived refused; failure injection like the other writes.
- Parity suite: tests/unit/features/incident/core/test_incident_core_conversation_protocol_parity.py and _operations.py gain join (joins once; joining twice is success; archived refused; other system unsupported). New tests/unit/features/incident/core/test_incident_core_conversation_join.py for the Slack branches (member: no join call; not a member: one join; already_in_channel; private refusal).

2. Response: Sentinel adapter (AC #1, OQ8)
- New features/incident/response/adapters/sentinel.py (TODO(TASK-122): moves to the audit capability's sink): async send_channel_archived(ArchivedEvent) over integrations.sentinel.client.send_event in asyncio.to_thread; legacy envelope kept, {event: incident_channel_archived, message: {incident_id, conversation_id, user_id, at (ISO 8601 UTC)}}, so queries keyed on event keep working (moves onto AuditEvent with TASK-122); a send failure is logged (incident_sentinel_event_failed) and never fails the archive. ArchivedEvent is a frozen dataclass. A Protocol ArchiveEventSink in service/archive.py so the service takes a fake; providers.archive_event_sink() builds the adapter.
- Verify at step 1 of implementation: make check-package-shape accepts response/adapters/ and lint-imports lets features.incident.response.adapters import integrations.sentinel (core/adapters already import integrations). If shape refuses it, the adapter goes under core/adapters/ instead (fallback, noted on the task).

3. Response: archive_incident service (AC #1)
- New features/incident/response/service/archive.py: async archive_incident(incidents, reports, projection, conversations, events, conversation, *, user_id, at, status_notice, archived_notice) -> OperationResult[Archive].
  1. find_incident_for_conversation: refusal (not an incident, ambiguous, store down, unreadable) returns it; nothing written, no event.
  2. conversations.join(the command's conversation): the outcome is kept as the join stage, never a gate (incident-management.md:54/:56/:101; OQ4).
  3. change_status(..., IncidentStatus.CLOSED, notice=status_notice): a refusal or record failure stops (the commit point); its notice posts only when the channel is writable; follower failures are carried and do not stop the archive.
  4. conversations.post(archived_notice) only when the join succeeded, else SKIPPED (not_joined); a failure is logged and carried, the archive still runs.
  5. conversations.archive only when the join succeeded, else SKIPPED (not_joined); a failure is the archive stage FAILED; no event without an archive.
  6. events.send_channel_archived once, after a successful archive.
  Archive (frozen dataclass): the StatusChange and the join, notice and archive StageResults. Reuses StageOutcome/StageResult/_stage from service/status.py (moved to a small service/stages.py if a private helper is needed across modules; no copy).
- Repeating on an already Closed incident reruns the followers and archives (decisions/incident-management.md, writes that fan out).

4. Response: Slack entrypoints (AC #2)
- New features/incident/response/entrypoints/slack_archive.py, register_archive(registrar, scopes), called from entrypoints/slack.py register:
  - registrar.register_command(command="close", parent="sre.incident", handler=dispatch to handle_close_command): asyncio.run(archive_incident(...)) inside incident_scope, invoker's locale; replies like status: the outcome line plus one line per skipped or failed stage (status lines reused; join, notice and archive lines added) (OQ3).
  - registrar.register_attachment_action("incident.response.archive", _press, legacy_callback_values={"archive_channel": ("archive",)}): acks first, channel from body.channel.id, user from body.user.id; refusals answered as the legacy path does (chat_postEphemeral for not an incident; respond for the store down); a reply only on a refusal or a skipped or failed stage; the payload names no locale, so every text it renders (refusals and both channel notices) is English then French from the catalogues (OQ2, i18n.md line); asyncio.run at the sync Bolt edge.
- Locales features/incident/response/locales/incident_response.{en-US,fr-FR}.yml: archive.description, archive.notice ("{user} has archived this channel 👋"), archive.not_an_incident, archive.unavailable, archive.ambiguous, archive.unreadable, archive.conflict, archive.join_failed, archive.archive_failed; the status notice reuses status.notice.

5. Legacy deletions (AC #2, AC #4)
- modules/incident/incident_helper.py: close_incident (:352-434), handle_close (:227-228), the "close" dispatcher entry (:157), the incident_status import, help bullets/examples (:57, :67, :100, :110) move to the rebuilt help (the registrar lists close under /sre incident).
- modules/incident/incident_status.py deleted; tests/modules/incident/test_incident_status.py deleted.
- modules/incident/incident_conversation.py archive_channel_action: the archive branch (:446-450) deleted (unreachable once the value is claimed, TASK-145.8.5.2 OQ7); ignore and schedule_retro stay; bot.action("archive_channel") stays registered (legacy fall-through).
- modules/incident/core.py:211 help line: kept pointing at the rebuilt command (text unchanged).
- modules/incident/incident_document.py:74 owner note: "TASK-145.8.3 deletes this function" (its last caller information_update.py:313).
- tests/modules/incident/test_incident_helper.py: the close tests (:50, :155, :421-:813 close_incident set) deleted; test_incident_conversation.py:1242 archive branch test deleted (pinned by the surface file instead).
- READMEs: features/incident/README.md:91-92, response/README.md:18; INVENTORY.md row for archive_channel (stale line number fixed, owner incident.response for the archive value).

6. Pins (AC #4), written first, red on legacy where they assert new behaviour
- tests/integration/legacy_surface/test_incident_channel_archive_surface.py: fixtures rewired to the target's fakes (incident store fake or the surface's table, the core conversation over the faked Slack client); assertions unchanged for: closes the incident in report, sheet and record; announces then archives (both texts identical); joins first when not a member; store down leaves channel and report alone; ignore and schedule_retro unchanged.
  - Edited pins citing the ruling (kind b): the refusal pin presses in a channel with no record (not a non-incident-* name); reply text per OQ2.
  - test_legacy_only_archive_records_two_sentinel_events and test_legacy_only_archive_records_an_event_on_a_refusal: pinned now against legacy (red-green on legacy), deleted by the cutover (kind a).
  - Sentinel assertion: the fake sink receives exactly one incident_channel_archived with {incident_id, conversation_id, user_id, at} (kind b: minimal payload).
- New tests/integration/legacy_surface/test_incident_close_command_surface.py: /sre incident close in an incident channel closes and archives (same order and texts as the button); in a channel with no record refuses and writes nothing; store down refuses.
- New unit tests: tests/unit/features/incident/response/test_incident_response_archive_service.py (order of calls; refusal writes nothing and sends no event; join failure still closes the record and skips notice and archive (no event); record failure stops before posts; follower failure still archives; notice failure still archives; archive failure sends no event; exactly one event after success; repeat on Closed reruns); test_incident_response_archive_entrypoint.py (registration: command close under sre.incident, attachment action with the archive_channel/archive scoped alias; press acks first; asyncio.run edge; reply lines); test_incident_response_archive_sentinel.py (payload shape; send failure logged, not raised).
- test_legacy_handler_registration_surface.py / test_slack_command_registration_surface.py: close appears under the rebuilt tree; archive_channel stays legacy-registered.

7. ADR lines (AC #3)
- decisions/incident-management.md: Decision line on joining (an explicit, idempotent step of a write that needs membership, such as archive; never part of the writability check; a private channel the bot left is refused, not joined); Changes 2026-11-17: TASK-145.8.5.3 archive and /sre incident close rebuilt in response (archive_incident, change_status(Closed) as the commit point, then notice, archive, one event), IncidentConversation gains join, close_incident and incident_status.py deleted.
- decisions/incident-management.md join line also says: a failed join skips the conversation writes that need it and never blocks the record write (OQ4).
- decisions/i18n.md Locale resolution + Changes 2026-11-17: a request whose payload names no locale is answered in English and French, each from its catalogue; a per-user lookup (users.info include_locale) only through a contract when a surface needs one language (OQ2; transport-slack.md:31 and #1858 precedents; TBS Directive on Official Languages for Communications and Services; Slack localizing guide).
- decisions/observability.md :20 sentence plus Changes 2026-11-17: rebuilt surfaces send named events with minimal fields, never request bodies, until the audit capability (TASK-122) owns the sink; incident_channel_archived is the first.

Named changes (AC #6)
- (a) Sentinel incident_channel_archived once per archive (legacy sent it twice: incident_helper.py:425 and incident_conversation.py:450) and none on a refusal (legacy :450 fires after the early returns at :374/:390).
- (b) Refusal decided by the record (legacy: channel name incident-*; the refusal no longer names the channel); a failed record write stops (legacy update_status swallowed failures and archived anyway); minimal event payload instead of the raw Slack body (verification token, response_url; OWASP Logging Cheat Sheet); an incident whose channel the bot cannot join is still closed, archive and notice reported skipped (legacy closed nothing; incident-management.md :56/:101); the button's channel notices are English and French (legacy English only; i18n.md line).
- Pin edits citing these rulings: the refusal pin (record, bilingual text), the announce pin (bilingual notices); a new pin for the join-refused path.

Size: production ~+420 / -200 over ~13 files (core api, slack adapter, in_memory, response service/archive.py, adapters/sentinel.py, entrypoints/slack_archive.py, slack.py, providers.py, two locales, incident_helper.py, incident_conversation.py, incident_status.py deleted, incident_document.py note) plus ADRs/READMEs. Over the ~10 files gate by file count; the coordinator split (OQ1) already set this slice; see OQ1 below.

Blast radius: the stale notice's archive button and /sre incident close in production. Wrong ship: an incident closed but not archived (follower or archive failure is reported to the presser) or a refusal where legacy archived (a channel with no record: those are not incidents by the ADR). Rollback: one git revert of the squash commit restores the legacy close and branch (the alias goes with it; the L5r guard keeps reads of records this path wrote with version-2 shape working). Ignore and schedule_retro unaffected (value fall-through pinned).

Gates: ruff, targeted tests during TDD; at the end once each: mypy (baseline 40/13), pytest tests --ignore=tests/smoke; make check-import-contracts, check-settings-key-ownership, check-package-shape, check-test-seams.

AC traceability: #1 -> steps 2, 3; tests archive_service, archive_sentinel, surface Sentinel pin. #2 -> steps 4, 5; tests archive_entrypoint, close_command_surface, registration surfaces. #3 -> steps 1, 7; parity suite, conversation_join. #4 -> step 6. #5 -> gates. #6 -> PR body.

Open questions (assessed at program scope 2026-11-17, task comment; recommendation first):
OQ1 Size exception: APPROVED (human, 2026-11-17).
OQ2 No-locale replies: i18n.md gap; add the line (both languages when the payload names no locale), apply it to every text the archive button renders; close keeps the invoker's locale. Note on TASK-145.9.2.
OQ3 Close replies like status (outcome plus skipped or failed stage lines; ADR :56 "reported"); the button replies only on a refusal or a skipped or failed stage.
OQ4 Join is not a gate: close the record even when the join fails, skip notice and archive (ADR conflict with legacy parity resolved by :56/:101; join line extended).
OQ5 Keep the OQ8 adapter and the {event, message} envelope with the minimal message (audit path needs user_email and renames event); human confirms no Sentinel query reads other message fields before merge.
OQ6 No change here; scope note on TASK-145.9.2: repoint or delete /sre dev stale's copy of the notice before TASK-145.13 removes the aliases.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-17: implemented (TDD) on stack-l/task-145.8.5.3-archive-close above L7b (d9dbf3b7, stack synced onto main 557b20ef; TASK-176 asked at session start: unchanged).
- Pins first: test_legacy_only_archive_records_two_sentinel_events and test_legacy_only_archive_records_an_event_on_a_refusal passed on the legacy archive (10 passed), deleted with the cutover. The /sre incident close pin (close closes, announces, archives; table down archives nothing with the bilingual reply) passed on the pre-cutover tree (2 passed), then rewired to the target's fakes (3 passed with the record-refusal pin).
- Core: IncidentConversation.join (api.py, Slack adapter reads conversations.info first, joins only a non-member, archived and method_not_supported_for_channel_type refused as CONVERSATION_NOT_WRITABLE; fake with private_non_member_ids and joined), held to the parity suite (100 passed) plus test_incident_core_conversation_join.py.
- Response: interfaces.py (ArchivedEvent, ArchiveEventSink), adapters/sentinel.py (TODO(TASK-122); log_to_sentinel envelope {event, message} with the four fields, off the loop), service/archive.py archive_incident (find, join as a stage, change_status Closed, notice and archive only after a join, one event after a successful archive), entrypoints/slack_archive.py (/sre incident close in the invoker's locale; incident.response.archive with legacy_callback_values archive_channel: archive; button texts English then French; replies only on a refusal or a skipped/failed stage), providers.archive_event_sink, archive.* keys in both catalogues. status.py's _stage became public stage_result; roles.py's duplicate deleted.
- Legacy deleted: close_incident, handle_close, the close dispatcher entry, incident_status.py, test_incident_status.py, the archive branch of archive_channel_action (ignore and schedule_retro stay), the close tests in test_incident_helper.py and test_archive_channel_action_archive. Help bullets for close stay (the help text is unchanged, as status kept its bullet). update_incident_document_status owner note -> TASK-145.8.3.
- Finding: db_operations.update_incident_field has no production caller after this change; kept as part of the L5r rollback guard (TASK-145.8.2) so reverting an earlier cutover alone still works; TASK-145.13 deletes it with db_operations.
- Harness: legacy_surface conftest attach_rebuilt_listeners_first (the plugin's listeners ahead of the legacy handlers, as server/lifespan.py orders them); the ignore and schedule_retro pins pass through the value fall-through. The access discovery test's fake provider gained register_attachment_action (first feature to register one).
- ADRs: incident-management.md (join line in the command check; Changes), observability.md :20 (minimal named Sentinel events; Changes), i18n.md (no-locale requests answered in English and French; Changes).
- Gates: ruff clean, format clean; make check-import-contracts (14 kept), check-settings-key-ownership, check-package-shape (3 baselined), check-test-seams (47/12), check-fake-coverage, check-runtime-imports, check-sdk-typing, check-vendor-package-contract, check-aws-platform-seam OK; mypy 40 errors in 13 files (baseline, none in touched files); pytest tests --ignore=tests/smoke 7664 passed.
- Size: production ~+530 / -215 over 19 files incl. READMEs and locales (over the ~420 estimate; size exception approved 2026-11-17). Tests +263/-777 in modified files, ~760 lines in new test files.
- Human before merge: confirm no Sentinel query or workbook reads message fields of incident_channel_archived other than incident_id, conversation_id, user_id, at.

2026-11-17 (human): Sentinel check done: nothing in the Sentinel code reads incident_channel_archived, so the minimal message breaks no query or workbook (TASK-145.8.5 OQ8 condition met).

2026-11-20: closed by the agent: PR #1866 merged 2026-11-17 (94553f9b); all ACs checked.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-17T18:32:00Z

---

Program-scope OQ assessment (2026-11-17), against decisions/ at stack top ddac794d + origin/main 557b20ef, doc-11, doc-15, doc-16, prior and upcoming tasks.

OQ1 Size exception. APPROVED 2026-11-17 (human): one PR (~13 prod files, ~+420/-200).

OQ2 Reply language when the payload names no locale. ADR: i18n.md:31 resolves the locale per request from the platform signal and says nothing for a request without one; transport-slack.md:31 (2026-11-03, tenant guard) already rules for its own notice: the user's locale when the payload names one, otherwise English and French. Prior: TASK-145.8.4 (status) and 145.8.5.1 (roles) reply in the invoker's locale (payload.user_locale; roles carries it in private_metadata); #1858 posts a bilingual failure notice from a reaction (no locale). Facts: interactive_message payloads carry no locale; Slack exposes a user's locale only through users.info with include_locale=true (https://api.slack.com/start/localizing, https://docs.slack.dev/changelog/2017/09/01/locale-locale-locale); the provider already has get_user_locale (integrations/slack/provider.py:863) but no contract exposes it to features. Federal practice: communications to employees in bilingual regions go out in both official languages (TBS Directive on Official Languages for Communications and Services, https://www.tbs-sct.canada.ca/pol/doc-eng.aspx?id=26164). Upcoming: TASK-145.9.2 rebuilds the stale notice in Block Kit (block_actions also carry no locale); TASK-145.7.10 alert buttons. GAP: i18n.md has no rule for a request without a locale, and two precedents (tenant guard, #1858) already answer it with both languages. Proposed i18n.md line (Locale resolution): a request whose payload names no locale (a legacy attachment button, a block action, an event) is answered in English and French, each from its catalogue (no second copy of a string, the :47 check holds); a per-user lookup (users.info include_locale) is added only when a surface needs one reply language, through a contract, never from a feature to the provider. Scope here: every text rendered for the archive button (ephemeral refusals and the two channel notices) is English then French; /sre incident close keeps the invoker's locale like status. Named change kind (b) by that ADR line: the button's channel notices become bilingual (legacy English only) and the not-an-incident refusal no longer names the channel (refusal by record); the store-down text stays bilingual (pin unchanged). Note on TASK-145.9.2: its Block Kit notice and ignore reply follow the same line.

OQ3 Close reply on success. ADR: incident-management.md:56 (writes that fan out): a follower failure is logged and reported, so reporting failed followers is ADR-backed, not an addition or a named change. Prior: TASK-145.8.4 status replies one ephemeral outcome line plus one line per skipped or failed follower (_STAGE_LINES). Upcoming: none. No gap. Recommendation: /sre incident close replies like status (the outcome line plus a line per skipped or failed follower, the join and archive stages included), so the two commands answer alike; the button replies only on a refusal or a failed or skipped stage (the channel notices already announce success; legacy posted nothing to the presser on success, pin unchanged).

OQ4 Join failure. ADR: incident-management.md:54 and :101 (an archived channel never blocks a record update; an incident stays editable after its channel is gone), :56 (only a refused command check or a failed record write stops); TASK-145.8.5 OQ5 ruling (join is a write step, never the writability check; a private channel the bot left is refused, not joined). CONFLICT with my first recommendation (stop before the record, legacy parity): a join failure is a conversation failure, so by :56 it must not stop the record write. Revised: find, join (outcome kept, not a gate), change_status(Closed) (commit point; its notice posts only when the channel is writable), then the archived notice and the archive only when the join succeeded, else both reported as skipped (not_joined); no event without an archive. Named change kind (b): an incident whose channel the bot cannot join is still closed (legacy closed nothing). ADR fix: the join line approved in OQ5 gains "a failed join skips the conversation writes that need it and never blocks the record write". Upcoming: TASK-165.11 (rebind) and 145.7.9 (attach loop) reuse join the same way.

OQ5 Sentinel. ADR: observability.md:20 (Sentinel receives only audit events, through the audit sink); TASK-145.8.5 OQ8 ruling (response adapter, TODO(TASK-122), one event, minimal payload; ADR line on minimal named events). Prior: TASK-171 notes: sends through the HTTP Data Collector API still succeed (41604 in 30 days to 2026-10-28) and the rebuild on the Logs Ingestion API is decided, not scheduled; TASK-171 comment of 2026-11-16 already lists this event. Finding: an audit path exists (integrations/sentinel/client.py log_audit_event over infrastructure/audit/models.py AuditEvent) with no production caller; it requires user_email (no Slack-id-to-email lookup exists until the people capability, TASK-83.4) and moves the name from event to action, breaking any query on event. Recommendation: keep the OQ8 ruling, and keep the legacy envelope {event, message} with the minimal message so queries keyed on event keep working; the adapter moves onto AuditEvent with TASK-122. No new gap. Carried human step (OQ8 condition, before merge): confirm no Sentinel query or workbook reads message fields of incident_channel_archived other than the four kept.

OQ6 /sre dev stale (modules/dev/platforms/slack.py:153) posts a copy of the stale notice with archive_channel. This task: no change (the scoped alias answers its archive button). GAP: no task owns that copy; once TASK-145.9.2 posts the Block Kit notice and TASK-145.13 (AC #10) removes the aliases, the dev copy's buttons reach no listener. Proposed scope: TASK-145.9.2 repoints /sre dev stale to the rebuilt notice's renderer or deletes it (note added); TASK-145.13 AC #10 assumes it.

---

created: 2026-11-17T19:03:00Z

---

APPROVED 2026-11-17 (human): plan approved; OQ1 size exception; OQ2-OQ6 as recommended in the program-scope assessment above (i18n.md no-locale line, both languages for the archive button's texts; close replies like status; join is a stage, never a gate, and the join ADR line is extended; OQ8 Sentinel adapter with the {event, message} envelope and the minimal message, human Sentinel query check before merge; /sre dev stale scope note on TASK-145.9.2). TASK-176 unchanged.

---
<!-- COMMENTS:END -->
