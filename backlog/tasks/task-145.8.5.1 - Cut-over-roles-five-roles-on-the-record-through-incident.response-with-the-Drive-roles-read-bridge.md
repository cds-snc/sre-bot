---
id: TASK-145.8.5.1
title: >-
  Cut over roles: five roles on the record through incident.response, with the
  Drive roles read bridge
status: In Progress
assignee: []
created_date: '2026-11-16T19:33:00Z'
updated_date: '2026-11-16T23:09:00Z'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.8.1
  - TASK-145.8.4
references:
  - decisions/incident-management.md
  - decisions/migration.md
  - decisions/transport-slack.md
parent_task_id: TASK-145.8.5
priority: medium
type: feature
ordinal: 523000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L7a.1 (doc-11 row 18.L7a.1), stacked above L6b (TASK-145.8.4, #1859). Split from TASK-145.8.5 on 2026-11-16 (human, OQ1). `/sre incident roles manage` and its modal move to incident.response: the modal shows the five roles (IC and OL required as today, communications lead, policy lead and postmortem owner optional), the submission writes them with IncidentStore.set_roles (the commit point), announces each changed role in the channel and rewrites the purpose's `IC: ... / OL: ...` line exactly as pinned. Roles are read from the record; an incident with no role on the record reads the report's Drive properties ic_id/ol_id through a legacy-only core read bridge (OQ7, Migration rule 1: existing roles live only in Drive), which never writes Drive and is deleted by TASK-145.13 after TASK-145.7.12's backfill reports nothing pending.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 /sre incident roles manage and its modal submission are registered by incident.response (modal callback and ids prefixed incident.response.roles): five pickers from the record (IC and OL required, the other three optional), set_roles is the commit point, each changed role is announced, the purpose's IC/OL line is rewritten as pinned; the legacy roles registration, handle_roles, incident_roles.py and its tests are deleted
- [x] #2 core/api.py reads an incident's roles from the record, else from the report's Drive properties ic_id/ol_id through one legacy-only core adapter tagged TODO(TASK-145.13); nothing writes Drive role properties; incident-management.md Migration amended (a legacy side store as an upgrade input; the 2026-11-04 roles line corrected) with a dated Changes line
- [x] #3 IncidentConversation gains async purpose(conversation) on the Slack adapter and the in-memory fake, held to the parity suite
- [x] #4 The roles pins pass with fixtures rewired to the target fakes; edited assertions cite their rulings (five pickers by the TASK-145.8 ruling; the not-an-incident reply, kind b); the Drive-properties legacy_only tests are deleted; the roles show stub is pinned as test_legacy_only_* and retired (kind d); legacy_sre_web_client_seam names TASK-145.13 as its owner in the fixture and the baseline
- [x] #5 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams, make check-settings-key-ownership and pytest tests --ignore=tests/smoke pass
- [x] #6 The PR body lists each named change with its kind and the revert target: one git revert restores the legacy roles surface; the L5r guard keeps it correct on marker-2 items; after a revert the legacy modal reads Drive again, so roles saved through the rebuilt modal are not preselected
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
APPROVED 2026-11-16 (human: TASK-145.8.5 OQ1-OQ8 as recommended; program plan and rulings in TASK-145.8.5's comments). Layer L7a.1 of Stack L (doc-11 row 18.L7a.1, doc-16), branch stack-l/task-145.8.5.1-roles above L6b (#1859, 73681647 on main ac3b8f8d). Line numbers from that base.

## 0. Scope
`/sre incident roles manage` and its modal move from modules/incident into incident.response. The modal opens on the incident's five roles (record first; an incident with no role on the record shows the report's Drive properties ic_id/ol_id through a legacy-only core read bridge, OQ7). The submission writes all five with IncidentStore.set_roles (the commit point: a failure stops it and the modal is answered with an error), then announces each role whose holder changed against what the modal showed (only when the channel is writable), then rewrites the purpose's IC/OL line exactly as the legacy did. Nothing reads or writes Drive role properties except the bridge's read. Not in scope: archive and close (145.8.5.3), the show modal's roles (145.8.3), the job backfill (145.7.12).

## 1. Call sites
Legacy (deleted): modules/incident/incident_helper.py:148 bot.view("view_save_incident_roles"); "roles": handle_roles in get_incident_actions (:183) and handle_roles (:352-365, its help text lines stay: the command keeps its name); modules/incident/incident_roles.py (145 lines); tests/modules/incident/test_incident_roles.py; incident_helper tests of handle_roles. Help text naming roles: incident_helper.py:55, modules/incident/core.py:595 (unchanged).
Core: core/api.py IncidentConversation :189 (set_purpose :252, post :228, is_writable :272), find_incident_for_conversation :506, conversation_is_writable :517; core/store.py set_roles :302 (Mapping[IncidentRole, str | None]; None unassigns); common/vocabulary.py:34 IncidentRole; core/domain.py Incident :280-300 (five role fields, report: ReportReference | None); core/adapters/google_docs.py get_metadata :375 (Drive files.get, sync); core/adapters/slack.py SlackIncidentConversation (async writes handle; conversations.info used by is_writable); core/adapters/in_memory.py InMemoryIncidentConversation (set_purpose :627).
Response: entrypoints/slack.py register :58 (status), _incident_scope; plugin.py register_slack_commands, register_i18n_resources; providers.py :18-30; locales incident_response.{en-US,fr-FR}.yml. Precedent for a command that opens a modal and a view submission: comms/entrypoints/slack.py :140-163 (registrar.reply.open_view with platform_metadata["trigger_id"], register_view_submission with _with_scopes).
Pins: tests/integration/legacy_surface/test_incident_roles_surface.py (10 + 2 legacy_only) on incident_surface; rewire precedent test_incident_status_command_surface.py:99-122 (in-memory record store via incident_scopes, providers monkeypatched to core in-memory fakes, plugin.register_slack_commands on incident_surface.provider, load_plugin_catalogues). Seam: conftest.py:807-818 legacy_sre_web_client_seam (owner text TASK-145.8 -> TASK-145.13), app/bin/baselines/test_seams_legacy.txt:20 (comment -> TASK-145.13).

## 2. Decisions
D1 Core read bridge (legacy, TODO(TASK-145.13)): core/api.py `LegacyRolesReader` Protocol, `async def read(report: ReportReference) -> OperationResult[Mapping[IncidentRole, str]]`, `get_legacy_roles_reader()`, and `async def read_incident_roles(incident, legacy) -> Mapping[IncidentRole, str | None]`: the record's five roles when any is set; otherwise, for a Google report, IC and OL from the reader (others None); a failed read is logged (incident_legacy_roles_read_failed, error_code) and yields the record's (empty) roles. Adapter core/adapters/legacy_roles.py GoogleDriveLegacyRolesReader: one asyncio.to_thread around google_docs.get_metadata(vendor_id, fields="appProperties"), ic_id -> incident commander, ol_id -> operations lead, blank dropped, HttpError classified (404 NOT_FOUND), non-Google UNSUPPORTED_OPERATION. Fake in core/adapters/in_memory.py InMemoryLegacyRolesReader. Reused by TASK-145.7.12.
D2 IncidentConversation.purpose(conversation) -> OperationResult[str] (async): Slack conversations.info purpose.value ("" when absent), classified like is_writable; fake returns what set_purpose stored ("" by default, seedable). Parity suite extended.
D3 response/service/roles.py: frozen RolesChange(incident, announced: tuple[IncidentRole, ...], announcements: StageResult, purpose: StageResult) and `async def assign_roles(incidents, conversations, legacy, conversation, roles, *, announce: Callable[[IncidentRole, str], str]) -> OperationResult[RolesChange]`: find_incident_for_conversation (refusals pass through); shown = read_incident_roles; set_roles(all five from the submission) (failure stops); for each role whose submitted holder differs from shown and is set, post announce(role, holder) in role order, only if conversation_is_writable (else SKIPPED not_writable); purpose: read, purpose_with_roles(purpose, ic, ol), set_purpose (failures FAILED, logged). StageResult/StageOutcome reused from service/status.py. Pure purpose_with_roles(purpose, ic, ol): legacy regex IC: <@[\w]+> / OL: <@[\w]+> replaced by "\nIC: <@ic> / OL: <@ol>", else appended as f"{purpose} \nIC: ...", cut to 250 (byte-identical to the pins). Purpose rewrite needs IC and OL (both required by the modal).
D4 Entrypoint response/entrypoints/slack_roles.py (register_roles called from slack.py register): command `roles` (grouping node; `roles`, `roles show` answer its help) with child `manage` (handler: open the modal through registrar.reply.open_view with the trigger id; one scope; find + read_incident_roles via asyncio.run; refusal replies: not an incident, ambiguous, unavailable; no trigger -> open-failed reply). View: callback incident.response.roles; header "Roles for <channel name minus incident-/dev->" from platform_metadata channel_name (parity); five users_select inputs, block ids incident.response.roles.<role>, action id incident.response.roles.select, placeholders from the catalogue (IC "Select an incident commander", OL "Select an operations lead", three new), IC and OL required, the three others optional; private_metadata {channel_id, channel_name, locale}. Submission (register_view_submission): parse the five selections, ack() first, then assign_roles via asyncio.run; announcements "<@U> has been assigned as <role name> for this incident." from the catalogue in the submitter's locale; a refusal or record failure posts an ephemeral notice to the submitter (the view is closed by the ack). title "SRE - Roles management", submit "Save roles" kept.
D5 Named changes (PR body): (b) roles read from and written to the record, Drive properties no longer written (legacy_only tests deleted); (b) a channel with no incident answers not-an-incident (was "No incident document found ..."); (d) `roles show` stub retired (help instead); addition by the TASK-145.8 ruling: three optional pickers and their announcements.

## 3. Steps (TDD)
S1 Pins first on legacy: test_legacy_only_roles_show_answers_the_upcoming_feature_stub (exact stub text). Green on legacy.
S2 Core: purpose (api, slack, in_memory, parity); LegacyRolesReader + adapter + fake + read_incident_roles; unit tests first.
S3 response/service/roles.py with purpose_with_roles; unit tests first.
S4 response/entrypoints/slack_roles.py, slack.py register hook, providers.legacy_roles_reader, catalogue keys (en-US, fr-FR); unit + dispatch tests first.
S5 Legacy removal (registration, dispatcher entry, handle_roles, incident_roles.py, its tests).
S6 Rewire the roles pins (fixture: in-memory record store seeded with the channel's legacy incident and its report; legacy roles fake seeded U0OLDIC/U0OLDOL; conversation fake seeded with the purpose; helpers read posts and purpose from the fake). Edited assertions citing rulings: the placeholders map has five entries; the no-incident pin expects the not-an-incident reply. legacy_only Drive tests and the S1 stub test deleted. Seam owner text -> TASK-145.13.
S7 Docs: incident-management.md Migration amendment + Changes line; response README (roles); features/incident/README.md; INVENTORY.md roles row owner.
S8 Gates: ruff, targeted tests, lint-imports, package shape, test seams, key ownership; then mypy once; then pytest once.

## 4. Tests (app/tests)
unit/features/incident/core: test_incident_core_legacy_roles_read.py (record roles win; no roles + Google report -> Drive IC/OL; reader failure -> empty roles, logged; non-Google report -> no read; adapter: appProperties mapping, blanks dropped, 404 NOT_FOUND, runs in one to_thread); parity suite: purpose read after set, default "", unknown channel classified, non-Slack UNSUPPORTED.
unit/features/incident/response: test_incident_response_roles_assign.py (happy five roles; one changed announces one; unchanged announces none; shown from Drive for a legacy incident, unchanged submission announces none and writes the record; unassign an optional role; record conflict/unreadable/store down stops with nothing posted; not an incident; not writable skips announcements and still sets the purpose? -> no: purpose is a channel write, skipped too; purpose read or write failure logged, roles kept); test_incident_response_roles_purpose.py (append, replace, 250 cut, exact legacy spacing); test_incident_response_roles_entrypoint.py (modal from roles, required flags, header, submission parsing, locale en/fr, asyncio.run edge, refusal notices); locale parity test extended.
integration/features/incident/response: test_incident_response_roles_dispatch.py (real plugin: `/sre incident roles manage` opens the modal, the submission writes the record, posts and sets the purpose).
Run response tests with -W error::RuntimeWarning.

## 5. Size
Production: core/api.py ~45, legacy_roles.py ~45, in_memory.py ~25, slack.py ~20, service/roles.py ~110, entrypoints/slack_roles.py ~170, slack.py ~3, providers.py ~5, locales ~30 lines YAML; deleted ~170 (incident_roles.py 145, handle_roles 14, registrations). ~420 added / ~170 deleted, 10 files + 2 catalogues: at the gate, accepted under the approved split (one subsystem, one behaviour change).

## 6. Assumptions
A1 registrar.reply.open_view in the legacy harness records views_open on the harness client so last_view works (comms pins precedent). A2 The fixture record's report reference maps to a Google report (REPORT_URL), so the bridge reads the legacy roles fake. A3 A not-writable channel skips announcements and the purpose (both channel writes; ADR: an archived channel never blocks the record). A4 set_roles with all five keys and None for unset ones is accepted.

## 7. Blast radius and rollback
Affects /sre incident roles manage and its modal only. Roles land on the record; Drive properties stop changing. One git revert restores the legacy surface; after a revert the legacy modal reads Drive again, so roles saved through the rebuilt modal are not preselected (the purpose line still shows IC and OL); the L5r guard keeps legacy item reads correct on marker-2 items written by set_roles.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-16: implemented on stack-l/task-145.8.5.1-roles (above L6b #1859, 73681647), TDD: S1 stub pin green on legacy first, then core, service, entrypoint, legacy removal, pin rewire.
- Core: IncidentConversation.purpose (Slack adapter, fake with seed_purpose, parity); LegacyRolesReader, get_legacy_roles_reader, read_incident_roles in core/api.py; core/adapters/legacy_roles.py GoogleDriveLegacyRolesReader (one to_thread around get_metadata, classified HttpError, UNSUPPORTED for non-Google); InMemoryLegacyRolesReader. All TODO(TASK-145.13).
- Response: service/roles.py assign_roles (find, read shown roles through the bridge, set_roles commit point, announcements of roles changed against what the modal showed, purpose_with_roles byte-identical to legacy; channel stages skipped when not writable); entrypoints/slack_roles.py (roles node, roles manage opens the five-picker modal through registrar.reply.open_view, view submission incident.response.roles acks first, field errors for missing IC/OL, private notices for refusals and failed followers); entrypoints/scope.py (incident_scope moved out of slack.py to avoid an import cycle); providers.legacy_roles_reader; catalogue keys en-US/fr-FR.
- Legacy deleted: incident_roles.py, handle_roles and its entry, the view registration, test_incident_roles.py, three handle_roles tests.
- Pins: test_incident_roles_surface.py rewired (11 pins); two assertions edited with ruling comments (five placeholders; not-an-incident reply); Drive legacy_only tests and the stub test deleted. Seam owner text and baseline comment now TASK-145.13. Fixture calls provider._attach_interaction_listeners() (the harness builds the Bolt app before the plugin registers; same private plumbing the fixture already uses).
- Docs: incident-management.md Migration (legacy side store as an upgrade input; 2026-11-04 premise corrected) and Changes line; response README; features/incident README; INVENTORY.md.
- Gates (agent run, from app/): ruff clean; import contracts 13 kept; package shape OK (3 baselined); test seams OK (47/12 baselined); key ownership OK; fake coverage OK; mypy 40 errors in 13 files (baseline, none in touched files); pytest 7458 passed. Rechecked by the session: targeted roles/status/response/core tests 234 passed with -W error::RuntimeWarning; ruff clean.
- Size: ~535 production LOC added (+~30 YAML lines per locale), ~185 deleted; above the plan's ~420 estimate and the ~400 gate (one subsystem, one behaviour change; flagged to the human).
- PR body prepared (named changes with kinds, revert target, merge order after L6b).

2026-11-16: rebased above L6b b40706ae (head feff6cd2, force-pushed to #1862); conflicts only in the core README line and TASK-176 notes; no code change needed (its new ports were already async).
<!-- SECTION:NOTES:END -->
