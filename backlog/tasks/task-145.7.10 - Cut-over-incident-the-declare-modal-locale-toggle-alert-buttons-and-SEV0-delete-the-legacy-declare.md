---
id: TASK-145.7.10
title: >-
  Cut over /incident, the declare modal, locale toggle, alert buttons and SEV0;
  delete the legacy declare
status: To Do
assignee: []
created_date: '2026-11-09T19:06:00Z'
updated_date: '2026-11-26T19:33:00Z'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.7.8
  - TASK-145.7.9
  - TASK-145.7.13
references:
  - decisions/incident-management.md
  - decisions/transport-slack.md
  - decisions/webhooks.md
  - decisions/reliability.md
parent_task_id: TASK-145.7
priority: medium
type: feature
ordinal: 514000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L9b, size exception approved 2026-11-09 (approved program in TASK-145.7's plan, section 2; outline in the parent plan). Registers /incident, view incident.response.declare (validates before its single ack), action incident.response.locale, and the alert buttons incident.response.alert_buttons with handle_incident_action_buttons as a legacy alias (the producer keeps posting the legacy id until L9c); ignore claims the action (reliability.md:18) and increments through the interim AlertAcknowledgements adapter (approximate count, webhooks.md line); SEV0 in the declare and update pickers. Deletes the legacy declare, incident_alert handler, registrations and app/models/incidents.py; rewires the declare pins; deletes legacy_acknowledged_webhooks_seam and baseline lines 9 and 17. One revert restores the legacy declare.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The declare and alert-button pins are rewired to the new stack's fakes with their names and Slack-visible assertions unchanged except the deliberate SEV0 option and the named changes; /incident, the declare view, the locale action and the alert buttons (legacy alias handle_incident_action_buttons) are served by incident.response; the legacy registrations (server/lifespan.py incident.register, incident_helper.py handle_incident_action_buttons) are gone (checks parent ACs #1, #4, #6, #11)
- [ ] #2 legacy_acknowledged_webhooks_seam and legacy_incident_folders_seam and baseline lines 9, 17 and 18 of bin/baselines/test_seams_legacy.txt are deleted; the legacy declare modules, app/models/incidents.py and the L5r rollback guard stay on disk for the revert and are deleted by TASK-145.7.10.1 (layer B)
- [ ] #3 decisions/webhooks.md section 8 (lands with TASK-37.1, #1889) is the authority for acknowledged_count as approximate and the interim AlertAcknowledgements adapter as tolerated; this task adds no wording, the adapter carries TODO(TASK-37.6.2) and no ADR citation; checked once #1889 is merged (no Waits on)
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
- [ ] #5 The declare pin names the deliberate list-sheet changes: the extra column F (incident id), the configured initial status ([incident_response] initial_status, default Open; TASK-145.7.9) where it differs from the legacy In Progress, and an empty product column until TASK-165.1 maps product names; the PR body states them for the sheet's readers (TASK-145.12.1 rulings, 2026-11-16)
- [ ] #6 INCIDENT_RESPONSE__NOTIFY_MANAGEMENT_PLACEMENT_ID and its value come from TASK-145.7.13, merged and its value confirmed before this layer merges; a Notify-placement declare invites the Notify management group
- [ ] #7 decisions/migration.md states the deletion-layer rule: a cutover whose legacy path stays for rollback stacks its deletion layer directly above it, prepared in the same session, merged after the exit criterion (7 days deployed, the post-deploy check recorded, no revert, one use on the new path)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLAN 2026-11-26 (task-planner, against main 20fbd2ed; human review required before any code). Stack L L9b, size exception already approved 2026-11-09 (TASK-145.7 plan section 2). Not a handoff until approved. REVISED 2026-11-26 after the program-scope assessment of OQ1-OQ7 (task comment of the same date): B becomes subtask TASK-145.7.10.1 prepared in the same session with an exit criterion; the SSM name moves to a terraform-only expand PR TASK-145.7.13 ahead of A; S3(b) follows comment #4; S4 writes new builders and copies the locale keys (no move in A); OQ6 owner corrected. Rows marked OQ need a human ruling; each has a recommendation under "Open questions".

## 0. Findings that change the approved outline (read first)
F1. No AlertAcknowledgements port or adapter exists (rg -i AlertAcknowledg: no hits). 145.7.9 did not build it; this task builds it (step S6).
F2. No declare entrypoint exists: features/incident/response/entrypoints/ has slack.py (status/update, calls register_roles/archive/show at :107-109), slack_roles.py, slack_archive.py, slack_show.py, slack_show_views.py only. The declare service (service/declare.py, 496 lines) is complete and unregistered (README.md:85) but lacks three things this task adds: commander = declarer, MultilingualText shared posts (DeclareTexts returns str, interfaces.py:59-120; talk.post already accepts str | MultilingualText, core/api.py:270), and nothing builds DeclareTexts or DeclarePorts (no declare provider; providers.py has declare_policy at :77 only).
F3. AC #2 conflicts with live code. app/models/incidents.py (Incident, 53 lines) validates db_operations.create_incident (modules/incident/db_operations.py:59-66), still called by modules/incident/incident_folder.py:456 create_missing_incidents (dev load-incidents) and modules/dev/incident.py:104 add_incident, both deleted only in L11 (TASK-145.12.2). Deleting the model in L9b therefore needs those two dev commands, create_missing_incidents, create_incident, log_activity and update_incident_field (no non-test caller left once core.py and the L6 cutovers are gone) deleted in the same task. This pulls forward a kind (d) retirement from 145.12.2 (OQ17 of the parent plan accepted dev list failing until L11 only). OQ1.
F4. Stale refs: parent plan says incident_helper.py:149 registers handle_incident_action_buttons; it is incident_helper.py:128 (called from server/lifespan.py:87; incident.register at lifespan.py:86). TASK-145.7.10 AC #5 and comment #2 say the policy key lives in "[incident]"; it is [incident_response] policy_group_id (features/incident/response/settings.py:54, config/base.toml:244, config/production.toml:34). Comment #2 says 15 policy tests; 21 test names contain "policy" in tests/modules/incident/test_incident_core.py and test_incident.py: recount at implementation and map each (section 5).
F5. tests/integration/legacy_surface/test_incident_declare_surface.py (14 tests, lines 122-440) pins only the payload handed to the fan-out seam, not the list-sheet row, initial status, SEV options, commander or logs append. Those are asserted nowhere today. AC #5's "declare pin names the deliberate sheet changes" is satisfied by new tests that assert them (S9), not by editing a pin.
F6. bin/baselines/test_seams_legacy.txt lines 9 and 17 verified: line 9 = inline:tests/integration/legacy_surface/test_incident_declare_surface.py::modules.incident.core.initiate_resources_creation; line 17 = legacy_acknowledged_webhooks_seam::modules.slack.webhooks.increment_acknowledged_count  # TASK-145.7. Line 18 (legacy_incident_folders_seam; the baseline tags it TASK-145.13, but TASK-145.13's ACs never name it) is used only by conftest.py:333 and test_incident_declare_surface.py: it dies with the rewire (the new modal lists IncidentReport.list_placements, core/api.py:359); delete it too if rg finds no other consumer, and say so in the PR body (OQ6).
F7. Rule-7 sites to fix: TODO(TASK-145.7.10) at features/incident/core/adapters/legacy_rollback.py:10 and modules/incident/db_operations.py:9, :147, :173, :198 (all deleted); non-TODO mentions that must be reworded or removed: features/incident/response/entrypoints/slack_show_views.py:50 and :189, service/declare.py:4, modules/incident/on_call.py:24 (file deleted), app/pyproject.toml:478 (import-linter ignore "modules.incident.on_call -> integrations.opsgenie" # TASK-145.7.10; unmatched_ignore_imports_alerting = "error" makes it fail if left), response/README.md:67-68, :85-86, :125.
F8. Existing record-first pin: test_incident_response_declare_run.py:292 asserts column index 3 == "In Progress" with the default setting; initial_status default is Open (settings.py:58): reconcile when adding the sheet test.

## 1. Scope and shape (recommended: two stack layers, one task)
The approved L9b is one PR with an exception. Recommendation (OQ2): split on the line "registration flip" vs "delete":
- PR A "cutover" (stack-l2/task-145.7.10-declare-cutover, bottom of the new stack): steps S1-S10. Adds the entrypoints, the ack adapter, SEV0, DeclareTexts/commander changes, terraform; removes the legacy REGISTRATIONS only (server/lifespan.py:86, incident_helper.py:128); rewires the declare pins; deletes seam baseline lines 9 and 17 (and 18). The legacy modules stay on disk, orphaned. One git revert restores the legacy declare whole, including the L5r guard and models.incidents (still present), which is strictly safer than the approved single PR.
- PR B "contract" (stack-l2/task-145.7.10-delete-legacy-declare, on top): steps S11-S15, deletion only (not bound by the size gate): modules/incident/incident.py, incident_alert.py, core.py, on_call.py; db_operations create/update/log paths; models/incidents.py; legacy_rollback.py; dead incident_folder and dev functions; legacy tests, factories, locales; INVENTORY rows; pyproject ignore. B merges after A's bake window (same rule as OQ18: the L5r guard must outlive any plausible revert of A). ACs #2 and the last part of #1 close with B; #3-#6 with A.
B is subtask TASK-145.7.10.1 (doc-2: one layer is one task), stacked directly above A and prepared in the same session as A: its PR opens while A is in review, so the deletion is never left as an open question. Exit criterion for merging B: A deployed for 7 days, the post-deploy test-incident check recorded, no revert, and at least one declare on the new path (the test declare counts). L10b-L10d stack above B; their review normally outlasts the bake. If the human keeps the approved single PR, S2-S15 land together under the exception.
Stack: L9b is the bottom of a new stack from main: branch stack-l2/task-145.7.10-declare-cutover (human runs gh stack init); above it stack-l2/task-145.7.10-delete-legacy-declare, then L10b-L10d (TASK-145.9.2-145.9.4) and L11/L11b (145.12.2/.3). L9c (TASK-145.7.11) is a side PR from main after A has baked (it must not merge before A is kept; its revert is safe, A's is not once L9c is live).

## 2. Size estimate and gate verdict (counts moved lines once)
PR A: production added ~750 LOC (slack_declare.py ~260 new; slack_declare_views.py ~230 of which ~180 are the legacy modal moved/rewritten from incident.py:234-413; declare_texts.py ~130; alert_acknowledgements.py + port + provider ~70; declare.py/interfaces.py/providers.py edits ~60; SEV0 + README + register ~15; ssm.tf 1) plus ~80 yml lines moved verbatim from app/locales/incident.{en-US,fr-FR}.yml; production removed ~15 (registrations). Files: ~6 new, ~9 modified, 2 locale files grown; ~17 production files, 2 subsystems (app, terraform one line). Trips rules 1 and 2: size exception approved; split recommended above.
PR B: ~1,500 production lines deleted, 0 added, ~15 files; tests deleted ~4,000 lines. Deletion-only, so gate-exempt.
Verdict: gate trips (files, ~750 LOC, app+terraform); exception stands; the A/B split reduces A to a reviewable behaviour diff and B to a pure delete. A deletion-ONLY split before the flip is impossible (the legacy code is live until A); after A it is exactly B.

## 3. Ordered steps (files exact)
PR A
S1 (moved out of this task to TASK-145.7.13, a terraform-only expand PR from main that merges before A, precedent INCIDENT_RESPONSE__HANDBOOK_ID in TASK-145.7.2; A has no terraform) terraform/ssm.tf: add "INCIDENT_RESPONSE__NOTIFY_MANAGEMENT_PLACEMENT_ID" to locals.sre_bot_secret_names (after INCIDENT_RESPONSE__HANDBOOK_ID, :24; the list is sorted). ecs.tf:31-33 and iam.tf:28-31 derive from the set. Setting already env_only (settings.py:69), documented in app/.env.example:24-25. Tests: tests/integration/server/test_server_plugins_configuration_requirements.py:197 (terraform_parameters vs entries) and tests/unit/infrastructure/configuration/test_configuration_settings_production_names.py:44: extend if they enumerate names. (AC #6)
S2 SEV0: features/incident/response/entrypoints/slack_show_views.py:50-51 SEVERITY_OPTIONS gains "sev-0" first; check the parse at slack_show.py:295 (Severity(int(...))) maps "sev-0"; drop the two comments (:50, :189); README.md:67-68. The declare picker built in S4 reuses the same tuple (one list). Test: test_incident_response_show_views.py (options include SEV0; SEV0 record preselects it, :189 case flips). (comment #3, parent OQ14)
S3 service/declare.py + interfaces.py: (a) DeclareTexts shared posts (announcement, severity_warning, on_call_unavailable, next_steps, source_alert_posted) return str | MultilingualText; ChatSurface gains the LanguagePolicy so the service computes shared_languages(system, tenant, conversation_id) per target conversation (the announcement channel has its own) and passes the tuple to the texts; the locale toggle never reaches the service. (b) commander: the Incident created at declare sets incident_commander=request.declarer unconditionally (comment #4; on-call people are invited, never made commander, oncall.md:20; the record is written first). Who else may become commander is TASK-145.10.5's incident-role rule. Tests: test_incident_response_declare_run.py (extend). (comments #4, #5)
S4 entrypoints/slack_declare_views.py (new Block Kit builders written for the new service, adapted from modules/incident/incident.py:42-50, :234-413, :415; the legacy builders stay on disk in A and are deleted in B, so A carries no move mixed with behaviour change, doc-2:51): loading view, declare modal (name, product from IncidentReport.list_placements, security radio, severity with SEV0, policy-help radio carried from the legacy modal, locale toggle), success/failure modal. Ids: view incident.response.declare, action incident.response.locale; read from the opened view in tests. Strings: app/locales/incident.*.yml (39 lines each) copied into features/incident/response/locales/incident_response.{en-US,fr-FR}.yml under a declare.* subtree (the legacy keys stay for the orphaned code and go in B); the "incident.timeline" key used by modules/incident/incident_conversation.py:261 (check) stays in app/locales.
S5 entrypoints/slack_declare.py (new): register_declare(registrar, scopes) registers (all at startup through plugin.register_slack_commands, never at import):
 - root command "incident" (parent=None; the host's _auto_register_root_commands registers /<prefix>incident, provider.py:563-600; precedent: other root commands): handler opens the loading view from payload.platform_metadata["trigger_id"] then updates it with the modal (legacy sequence incident.py:52-80); a failed open answers an ephemeral reply.
 - register_view_submission("incident.response.declare"): validates (name regex ^[\w\-\s]+$, product, severity, security radio) BEFORE its single ack (ack(response_action="errors") on invalid, plain ack otherwise), then builds DeclareRequest (idempotency_key = Slack view id; source_alert = MessageReference from private_metadata with permalink hint; policy_help from the radio), runs declare in the scope, answers the invoker privately in the locale toggle's locale.
 - register_block_action("incident.response.locale"): re-renders the open view in the other language, keeping entered values (pins 189, 223).
 - register_attachment_action("incident.response.alert_buttons", handler, legacy_callback_ids=("handle_incident_action_buttons",)): call-incident opens the declare modal prefilled from the alert (pin 385); ignore-incident: claim then increment (S6), then replace the buttons exactly as legacy (pins 405, 440).
 Wire into entrypoints/slack.py register() next to register_show (:109). Tests: S9.
S6 AlertAcknowledgements: Protocol in response/interfaces.py (async increment(webhook_id) -> OperationResult[None]); adapter response/adapters/alert_acknowledgements.py over contracts.records RecordStore.update(RecordTable("webhooks", key id), key {"id": id}, [IncrementAttribute("acknowledged_count", 1)]) in asyncio.to_thread; failure logged and dropped (a counter never blocks the click, as modules/slack/webhooks.py:124-145); comment names TASK-37.6.2 as the replacement; provider in providers.py. ignore claims the action first through Claims (reliability.md:18), key "incident:alert_ignore:<channel>:<message_ts>": NEW -> increment, complete; COMPLETED/IN_PROGRESS -> no increment, buttons still replaced. The store may retry the SDK call (records/store.py docstring): over-count accepted and recorded as approximate (webhooks.md section 8 landed with TASK-37.1, #1889; this PR adds no ADR wording, AC #3).
S7 Declare wiring: providers.py gets declare_ports(scope) and declare_texts(...) builders (RecordStore, IncidentStore, reports, video call, projection, ThreadedClaims, placement lookup, oncall_lookup, Slack conversations), production flag from the ConfiguredEnvironment as declare_policy(production=) already takes. No import-time construction. Tests: test_incident_response_declare_providers_build.py.
S8 Delete legacy REGISTRATIONS only: server/lifespan.py:86 (incident.register(bot)) and the import at :86-87 as needed; modules/incident/incident_helper.py:128 (bot.action("handle_incident_action_buttons")). Legacy /incident would otherwise double-register with the host root command. Tests rewired: tests/unit/modules/incident/test_incident_command_registration.py, tests/integration/server/test_lifespan.py, test_lifespan_sre_single_registration.py, tests/integration/legacy_surface/test_slack_command_registration_surface.py (assert /incident and the alias now served by incident.response).
S9 Pins and new tests (section 5): rewire tests/integration/legacy_surface/test_incident_declare_surface.py to the new stack's Protocol fakes (record-first, fake IncidentConversation, in-memory store and projection) keeping its 14 test names and Slack-visible assertions; delete fixture legacy_acknowledged_webhooks_seam (conftest.py:318-329) and its use in legacy_handler_harness (:347-366), baseline lines 9 and 17 (and 18 with legacy_incident_folders_seam if unused). Update tests/integration/legacy_surface/INVENTORY.md rows 43, 52-54 (owner and entry point now incident.response).
S10 PR body: the named-change table (section 4), the list-sheet paragraph for the sheet's readers (AC #5), the policy-help carry list, the kind (b) logs-append line, the SSM human steps, rollback note.
PR B (deletion only; lands after A's bake)
S11 Delete modules/incident/incident.py, incident_alert.py, core.py, on_call.py; app/pyproject.toml:478 ignore entry; unused i18n keys in app/locales/incident.*.yml (delete the files if nothing else reads them).
S12 modules/incident/db_operations.py: delete create_incident, update_incident_field, _read_record_version, _field_update_request, log_activity and the legacy_rollback / models.incidents imports (TODO sites :9, :147, :173, :198); keep list_incidents, get_incident_by_channel_id, lookup_incident (still used by dev list and incident_folder until L11). Delete features/incident/core/adapters/legacy_rollback.py and models/incidents.py.
S13 (pending OQ1) pull-forward deletes: modules/dev/incident.py add_incident (:56-) and load_incidents (:39-) with their registrations modules/dev/platforms/slack.py:254-270 and handlers; modules/incident/incident_folder.py create_missing_incidents (:438), add_new_incident_to_list (:279) and list_incident_folders (:36) if rg shows no other caller; tests for each. get_incidents_from_sheet, complete_incidents_details and get_incident_details stay for 145.12.2 unless rg shows them dead after S13.
S14 Delete tests: tests/unit/models/test_models_incident_legacy_attribute_load.py, tests/factories/legacy_rollback.py, tests/unit/features/incident/core/test_incident_core_legacy_rollback_{view,write,round_trip}.py, tests/unit/modules/incident/test_incident_db_operations_update_field_marker.py, tests/modules/incident/test_incident.py (41 tests), test_incident_core.py (47), test_incident_alert.py (6), test_incident_on_call.py, the create/log/update/model parts of test_db_operations.py (keep list/lookup/get_by_channel parts; drop its models.incidents import :16), the create_missing/add_new_incident_to_list parts of test_incident_folder.py, add/load parts of tests/unit/modules/dev/test_dev_incident_handler.py; the Incident import in legacy_surface/conftest.py:85. Check: rg "models.incidents|legacy_rollback" app returns nothing.
S15 Docs: features/incident/response/README.md (declare registered, ack adapter), delete migration TODO mentions; doc-11 rows by the human, not here.

## 4. Named changes (decisions/migration.md step 4; comment #1)
| # | Change | Kind | Authority | Pin | PR-body line |
| 1 | Record written first, then conversation/binding/resources; a conversation failure leaves record + list row (legacy created the channel first, item last) | (b) | incident-management.md record as commit point; TASK-145.7.7 R4-R6 | test_incident_declare_surface.py rewired tests 317, 335; declare_run :394 | "declare is record-first" |
| 2 | Item written in end-state shape (marker 2, binding, MessageReference source_alert, int severity) not the legacy shape | (b) | incident-management.md A1; Migration rules 1, 5 | declare_run store assertions | "declare writes the end-state item" |
| 3 | Legacy logs list append at create (db_operations.py:100 create_incident -> log_activity) ends | (b) | comment #3; incident-management.md:32; rule 5 | new test_legacy_only-free test asserting no logs attribute; timeline entry instead | "declare no longer appends to logs" |
| 4 | SEV0 offered in declare picker and update modal, with the severity warning | (b) | parent OQ14 (approved 2026-11-09); comment #3 | show_views options; declare_views options | "SEV0 added" |
| 5 | incident_commander = declarer when on-call names none | (b) | comment #4 (2026-11-20); TASK-145.10.5 | declare_run commander test | "commander defaults to the declarer" |
| 6 | List sheet: extra column F (incident id) | (b) | TASK-145.12.1 rulings 2026-11-16 | new test_incident_response_declare_sheet_row.py | sheet paragraph |
| 7 | List sheet: status is [incident_response] initial_status (default Open) instead of In Progress | (b) | TASK-145.7.9; incident-management.md status vocabulary | same | sheet paragraph |
| 8 | List sheet: product column empty until TASK-165.1 maps names | (b) | TASK-145.12.1 rulings | same | sheet paragraph |
| 9 | Shared posts (announcement, severity warning, next steps, on-call notice) are MultilingualText from LanguagePolicy.shared_languages; locale toggle drives modal and private replies only (legacy posted one i18n language) | (b) | languages.md; comment #5 (2026-11-25) | declare_texts test; surface test 277 locale | "bilingual shared posts" |
| 10 | Submit validates then acks once (legacy acks at incident.py:136 then again with errors at :154) | (a) | no pin asserts the double ack (pin 363 asserts outcome only) | surface 363 | "submit acks once" |
| 11 | ignore claims the click once (a repeat click does not increment again); count approximate, retries accepted | (b) | reliability.md:18; webhooks.md section 8 (#1889) | alert_buttons entrypoint idempotency test | "ignore is claimed" |
| 12 | On-call invite through capabilities.oncall instead of Opsgenie via the Drive folder (on_call.py); schedule still read from the placement folder (tolerated, owner TASK-165.1) | (b) | oncall.md; TASK-145.7.9 | declare_run on-call tests | "on-call through the capability" |
| 13 | Notify management group invited by the Notify placement folder id (env_only INCIDENT_RESPONSE__NOTIFY_MANAGEMENT_PLACEMENT_ID) instead of product == "Notify" (core.py:204) | (b) | human, TASK-145.7.9 2026-11-18 | declare_run Notify tests; settings load test | "Notify by placement" |
| 14 | Product options come from IncidentReport.list_placements (no 10-folder display cap, sorted by placement) instead of Drive child folders | (b) | TASK-145.7.5 placements | declare_views products test | "product list from placements" |
| 15 | Dev commands add-incident, load-incidents retired a release early (PR B, OQ1) and dev list fails on end-state items | (d) | parent OQ17; 145.12 AC #2 | removed with tests | "dev incident commands retired" |
Carried unchanged (not changes): #1853 policy-help invite (modal question, policy_help -> DeclareRequest -> invite of [incident_response] policy_group_id, declare.py:439); alert-button ids still posted (legacy id until L9c); ack on the same modal ids semantics.

## 5. Test matrix (new files in tests/unit/features/incident/response/ unless noted; fakes per testing-standards; strict seam zone)
Happy: test_incident_response_declare_entrypoint.py (root command opens loading then modal; submit builds DeclareRequest and replies; locale toggle re-renders keeping fields; source alert prefilled); test_incident_response_declare_views.py (modal blocks; products from placements; severity options include SEV0 and equal the update modal's; policy-help radio; ids read from the view); test_incident_response_alert_buttons_entrypoint.py (call-incident; ignore replaces buttons, keeps non-rich-text blocks); test_incident_response_alert_acknowledgements_increment.py (one IncrementAttribute on table webhooks); test_incident_response_declare_texts.py (MultilingualText order from shared_languages; announcement channel uses its own languages).
Boundary: name regex edge (empty, symbols, accented letters), empty name stays empty on locale toggle, severity none vs SEV0 value 0 (falsy!), 3-second trigger_id missing, no placements, long name.
Failure: invalid view answers errors with a single ack and creates nothing (pin 363); record write fails -> nothing else runs; conversation creation fails -> invoker warned privately, list row still written (pin 317/335 rewired); loading-view open fails; ack counter write fails -> logged, buttons still replaced; claim store failure -> fail closed, no increment.
Idempotency / ack-once: same view id replay yields same incident id and no second record/conversation (declare_run :439 extended through the entrypoint); second ignore click on the same message increments once; submit acks exactly once on both paths.
Authorization: Slack tenant not configured registers nothing (as slack.py:79-83); incident.response disabled in plugins.* registers nothing; legacy alias handle_incident_action_buttons reaches the same handler through the registrar (tests/integration/features/incident/response/test_incident_response_declare_dispatch.py with the real provider registry); legacy ids no longer registered by modules (registration surface).
Sheet/pins: test_incident_response_declare_sheet_row.py (column F = incident id; status = Open by default and In Progress when [incident_response] initial_status says so; product empty; record has no logs attribute). tests/integration/legacy_surface/test_incident_declare_surface.py keeps its 14 names, rewired. Policy-help: the 21 "policy" tests in test_incident_core.py/test_incident.py are mapped one by one in the PR body to (i) declare_run policy tests (:304-322), (ii) declare_views/entrypoint policy-question tests, or (iii) dropped as legacy-internal; none silently lost.
Gates: make check-import-contracts, check-settings-key-ownership (no new key), check-package-shape (new files in response/entrypoints and adapters), check-test-seams (baseline shrinks only), ruff, mypy (baseline main 33 errors in 11 files: no new errors in touched files), pytest tests --ignore=tests/smoke.

## 6. AC <-> step <-> test traceability
AC1 -> S2, S5, S8, S9 (+S11 completes "registrations gone") -> legacy_surface test_incident_declare_surface.py (14 rewired), show_views SEV0 test, registration surface tests.
AC2 -> S9 (seams), S11-S14 (deletions) -> rg checks (below), check-test-seams; test deletions listed in S14.
AC3 -> S6 (cites webhooks.md section 8; no wording) -> none (docs); checked when #1889 merges (OQ3).
AC4 -> all -> gates in section 5.
AC5 -> S6-S9, S10 -> test_incident_response_declare_sheet_row.py; PR body paragraph.
AC6 -> S1 + human steps (section 8) -> settings/terraform tests; deploy-checks output.
Reverse: S3 -> comments #4/#5 (named changes 5, 9); S4/S5/S7 -> AC1; S10 -> AC5; every step maps to an AC or comment ruling.
Verification commands at PR B: rg -n "models\.incidents|legacy_rollback|TODO\(TASK-145\.7\.10\)" app (empty, incl. tests/modules/incident and tests/integration/legacy_surface); rg -n "legacy_acknowledged_webhooks_seam" app bin (empty).

## 7. Assumptions and how to verify
A1 Root command "incident" with parent=None routes through route_hierarchical_command and the handler can open a modal inside the 3 s trigger window (the host acks first, provider.py:563-600). Verify with a dispatch test against the real provider; precedent: other root commands.
A2 The host's attachment-action alias matches by callback_id "handle_incident_action_buttons" with the payload shape the producer posts (api/v1/routes/webhooks.py:165-190, attachments with callback_id and actions[0].name/value). Verify in the dispatch test using the producer's real output.
A3 Records adapter reaches the existing "webhooks" table (terraform/dynamodb.tf:1, IAM dynamodb.tf:303) with key "id" and RecordStore.update supports a missing item via IncrementAttribute (absent counts as 0; contracts/records/store.py:146); an increment on a deleted webhook must not create an item (if the store upserts, add expected={"id": exists}). Verify against infrastructure/records/service.py.
A4 capabilities.oncall get_oncall_lookup (api.py:60) is wired to Opsgenie in production, so the on-call invite does not regress; the dependency graph lists TASK-146.1 as To Do while code exists. Verify the task state and a production config read before merge; if not wired the on-call notice is posted (visible, not silent).
A5 incident.response is enabled in production (config/base.toml:298 true) and requires slack.tenant, google_workspace.tenant, incident_response.handbook_id (plugin.py:35-44): add Requirement for incident_response.notify_management_placement_id only if the setting must exist; today empty means no Notify invite (policy: optional).
A6 No other consumer of app/locales/incident.*.yml keys beyond incident.py and incident_conversation.py "incident.timeline" (rg). Verify before moving.
A7 legacy_acknowledged_webhooks_seam and legacy_incident_folders_seam have no consumers beyond the declare pins (rg tests/).
A8 The policy-help modal question is shown to everyone as in the legacy modal (incident.py:145-146 default "no"); carried verbatim.
A9 Slack view id is stable across redelivery of one view submission (idempotency key). Verify with Slack docs/Bolt payload (view.id) and the dispatch test.

## 8. Blast radius, rollback, ordering, human steps
Blast radius: merge of A deploys the production declare path: /incident, the declare modal, the locale toggle, the alert buttons (ignore on every alert message), SEV0 in the update modal, the Notify placement invite and the list-sheet row all flip at once. A bug breaks incident declaration. Mitigations: record-first (a record survives any later failure; retry under the same view id), legacy code left on disk in A, a quiet-window merge.
Rollback: one git revert of PR A restores the legacy registrations and (because A deleted nothing) every legacy module, the L5r guard, models.incidents and the seam baseline. Items declared meanwhile are end-state items; the restored legacy readers read them through the guard and the bridge (that is what the guard is for). Caveats: (1) A carries no terraform (the name lands in TASK-145.7.13 first), so a revert of A never touches SSM; removing the name later goes through the RETIRED map and a removed block with lifecycle { destroy = false }, never a plain revert. (2) Messages already carry the legacy callback id until L9c, so a revert strands nothing; L9c must not merge before A is kept. (3) PR B, once merged, cannot be reverted together with A safely after items were written: B merges only after the bake and a fix-forward policy applies (migration.md rules 1, 5). If the human keeps one PR, the revert restores all and caveat (3) does not exist.
Ordering: terraform/SSM value before the deploy (the ECS task definition references the parameter ARN; a missing value fails task start). A before B; L9c is a side PR after A's bake, independent of B. PR #1889 (webhooks.md section 8) should merge first (OQ3).
Human steps (AC #6), in order:
 1. TASK-145.7.13 (before A): deploy-checks pre, merge, wait for the apply, then aws ssm put-parameter --name /sre-bot/INCIDENT_RESPONSE__NOTIFY_MANAGEMENT_PLACEMENT_ID --type SecureString --value '<Notify placement Drive folder id>' --overwrite (profile for the core_services account, region ca-central-1; the value is the folder id of the Notify placement under the incident folder, never written in files, tasks or chat). Terraform creates the parameter with the placeholder value_wo "set-outside-terraform" and never overwrites it afterwards; the placeholder must never reach a running declare, which is why A merges only after the value is set; confirm with aws ssm get-parameter --name ... --with-decryption (output not shared).
 2. zsh bin/deploy-checks.zsh pre summary (SSM and env-name change; baseline rollback tag, task definition, 24h errors) before the merge; after the deploy zsh bin/deploy-checks.zsh post summary (config_hash identical across tasks; no secret in boot lines). env-checks: make env-checks (human runs) to confirm the new name is registered and not in RETIRED.
 3. Merge A in a quiet window (not during an open incident); keep L9c unmerged.
 4. Post-deploy check in a test incident channel (security flag off): /incident opens the loading view then the modal; toggle locale and see the form re-render keeping the name; declare with SEV0 and with a Notify placement (Notify management group invited), with the policy question yes (policy group invited); confirm the record, conversation, bilingual announcement, report, Meet link, list-sheet row (columns A-F; F is the incident id; status Open) and the update modal offering SEV0; post a test alert via the webhook, click call-incident (modal prefilled), click ignore (buttons replaced, acknowledged_count +1 once; a second click adds nothing); repeat the declare submit double-click (one incident). Record the result in the task notes; the task stays In Progress until then.
Domain-model gate (domain-model-evolution): not applicable as a model change. No domain entity is added or reshaped: Incident, IncidentBinding and MessageReference are unchanged; incident_commander already exists (core/domain.py:292) and only gets a value at create; the new AlertAcknowledgements is a behaviour Protocol over a counter attribute of the existing webhooks table (no entity, no migration), tolerated until TASK-37.6.2. Cardinality unchanged (one incident, one primary binding per declare; two incidents from one alert allowed, parent plan scenario 2); idempotency by view id covered above. Type boundaries: Protocol for AlertAcknowledgements/DeclareTexts, frozen dataclasses for requests, no Pydantic (the Slack payload is parsed into the existing dataclasses at the edge).

## 9. Open questions (program-scope assessment 2026-11-26; recommendations)
OQ1 Retire dev add-incident and load-incidents in B. ADR-backed: migration.md:40 kind (d), no usage check required; evidence that production never runs them: modules/dev/platforms/slack.py:36-47 refuses outside local. incident-management.md:149 lists the dev writer "until TASK-145.12", a ceiling. Prior: TASK-145.7 OQ17 accepted dev list failing L9b-L11. Upcoming: TASK-145.12.2 (L11) loses those two deletions (comment on it at approval). Recommend yes.
OQ2 Split A (cutover) / B (TASK-145.7.10.1, deletion only). Gap: no ADR sets when a contract layer merges after a cutover. Precedents (145.8.3, 145.8.4, 145.8.5.3) deleted in the flip PR; the implementation-planning skill prescribes cutover then contract and bans the big-bang delete. Web practice: flip and removal as separate PRs, the removal PR prepared ahead, removal in the definition of done (Fowler parallel change, LaunchDarkly flag debt). Proposed fix: migration.md rule: a cutover whose legacy path stays for rollback stacks its deletion layer directly above it, prepared in the same session, merging after a stated exit criterion (default: 7 days deployed, the post-deploy check recorded, no revert, one use on the new path). Recommend yes.
OQ3 AC #3. ADR: webhooks.md section 8 exists only in #1889 (Lane B). doc-11 Lane B bullet: whichever lands second rebases; no Waits on. Recommend: no gate; AC #3 is checked when #1889 merges (the task cannot close before); code carries TODO(TASK-37.6.2) and no ADR section citation, so nothing on main points at missing text. Lane B gap reported, not edited: TASK-37.6.2 ACs do not name the adapter's removal or acknowledged_count.
OQ4 Settled by comment #4 (human, 2026-11-20): declarer unconditionally; S3(b) corrected. Product gap, not this task: no ADR says whether on-call or an acknowledger is ever made commander (incident.io assigns the lead through workflows: on-call schedule, the escalation acknowledger, or by hand). Recommend a question on TASK-145.10.5, which owns the incident-role rule.
OQ5 Ignore claim per message ("incident:alert_ignore:<channel>:<message_ts>"). ADR-backed: reliability.md:18 key shape, existing Claims (interfaces.py:37); webhooks.md section 8 makes the count approximate. Slack documents retries only for the Events API; repeat clicks are the risk. Per-user sets are rejected: they reshape Lane B's webhooks table and the first ignore replaces the buttons. Recommend yes, no change.
OQ6 Delete baseline line 18. ADR-backed: baseline header ratchets down only; TASK-187 AC #4 treats stale entries as removable. Recommend yes; the PR body says TASK-145.13 never named it.
OQ7 SSM revert safety. Gap: deployment.md and configuration.md have no revert rule for ssm.tf names; prevent_destroy does not survive a removed resource block, a removed block with destroy = false does (HashiCorp docs). Recommend: TASK-145.7.13 terraform-only expand PR first, the human value set after its apply, A merges after; deployment.md gains "a new SSM name lands in its own PR before its consumer; a revert never removes an ssm.tf name; removal goes through the RETIRED map and a removed block with destroy = false".
A4 checked: OPSGENIE__INTEGRATIONS_KEY in ssm.tf:28, [opsgenie.tenant] in production.toml:58, oncall enabled (base.toml:301). Risk low; the post-deploy check confirms the on-call invite.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-10 (TASK-145.7.7 rulings R4-R6): the cut-over Slack declare follows the record-first order (create, then the conversation and attach_conversation, then resources); the legacy pins that assert channel-before-record ordering are updated deliberately in this task's plan.

2026-11-18 (human, TASK-145.7.9): the Notify placement key's SSM parameter and value ride here, the first change that makes the declare service run.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-16T15:51:00Z

---

2026-11-16 (human, TASK-145.8.4 OQ4): decisions/migration.md step 4 amended (rides with L6b): a cutover changes behaviour only as a named change of kind (a) legacy bug no pin asserts, (b) behaviour an accepted end-state ADR replaces, (c) expired deprecated form after a usage check, (d) retired surface; additions only by an explicit plan ruling. At planning, classify each behaviour change of this task by kind, pin it (test_legacy_only_* or edited pin citing the ruling) and list it in the PR body.

---

created: 2026-11-17T19:10:00Z

---

2026-11-17 (found at the Stack L sync, TASK-145.8.5.3 session): #1853 (fba4ff8b, merged to main, not a Stack L change) added a policy-help answer to the legacy declare: production-only invite of the policy group ([incident] policy_group_id in features/incident/response/settings.py; modules/incident/core.py and incident.py; pinned in tests/modules/incident/test_incident_core.py and test_incident.py, 15 policy tests). The declare rebuild carries it (pins rewired, not dropped) or rules it a named change at planning.

---

created: 2026-11-17T20:56:00Z

---

2026-11-17 (TASK-145.8.3 OQ7): the rebuilt field updates (L6a) and close (L7a.3) no longer append to the item's legacy logs list (incident-management.md:32, Migration rule 5). The legacy declare's append (db_operations.py:100 create_incident -> log_activity) ends with this cutover: name it in the PR body as a kind (b) change. Also from L6a: the update modal's severity options are one list; add SEV0 there with the declare picker.

---

created: 2026-11-20T22:04:00Z

---

2026-11-20 (human, TASK-145.10 program-scope rulings): declare writes the incident commander as the declarer when on-call names none (not decided before; neither legacy nor TASK-145.7.9 sets it). Named change of kind (b) under the incident-role rule that lands with TASK-145.10.5; until then the core role check falls back to declared_by.

---

created: 2026-11-25T19:10:00Z

---

2026-11-25 (human, TASK-193 approved): declare's shared posts (DeclareTexts: announcement, severity warning, next steps, on-call notice) are MultilingualText from LanguagePolicy.shared_languages (decisions/languages.md); the locale toggle drives the modal and private replies only.

---

created: 2026-11-26T18:56:00Z

---

2026-11-26 (task-planner) proposed AC changes, none applied (existing ACs are not reworded by the agent):
AC #3 proposed wording: "decisions/webhooks.md section 8 (landed with TASK-37.1, #1889) covers acknowledged_count as approximate and the interim adapter as tolerated; this PR cites it and adds no wording". Human ruling 2026-11-26. Ordering: merge #1889 before the cutover when ready; otherwise check AC #3 when #1889 merges (task stays In Progress for it). See plan OQ3.
AC #2 proposed addition (plan F3, OQ1): the same deletion also removes db_operations create_incident, update_incident_field and log_activity, the dev add-incident and load-incidents commands, create_missing_incidents and modules/incident/on_call.py, because models.incidents cannot go while they exist; and baseline line 18 (legacy_incident_folders_seam) if unused (OQ6).
AC #1 proposed wording: "The declare and alert-button pins are rewired to the new stack's fakes with their names and Slack-visible assertions unchanged except the deliberate SEV0 option and the named changes; legacy registrations are gone" (the legacy pins assert only the fan-out payload; sheet, status, commander and logs are new tests).
Plan found: no AlertAcknowledgements port exists (145.7.9 did not build it; built here); no declare entrypoint or declare provider exists; policy key is [incident_response] policy_group_id, not [incident]; 21 (not 15) test names contain "policy"; parent plan's incident_helper.py:149 is now :128.

---

created: 2026-11-26T19:11:00Z

---

2026-11-26 program-scope assessment of OQ1-OQ7 (human asked; plan revised, awaiting approval). Gaps proposed for ADR edits riding with the code: migration.md, when a deletion layer merges after a cutover (OQ2: stacked directly above, prepared in the same session, exit criterion 7 days deployed + post-deploy check + no revert + one use); deployment.md, SSM names land in their own PR before the consumer and are never removed by a revert (OQ7: removal through RETIRED and a removed block with destroy = false). Proposed scope changes: new subtask TASK-145.7.10.1 (deletion layer B; AC #2, the dev-command retirement); new subtask TASK-145.7.13 (terraform-only expand PR with the SSM name; AC #6's terraform and put-parameter parts; merges before A); TASK-145.12.2 drops dev add-incident/load-incidents; question on TASK-145.10.5 whether on-call or an acknowledger is ever made commander. Settled without change: OQ1 (kind d), OQ4 (comment #4), OQ5 (reliability.md:18), OQ6 (baseline ratchet). Sources: martinfowler.com/bliki/ParallelChange.html, launchdarkly.com/docs/guides/flags/technical-debt, docs.slack.dev/interactivity/handling-user-interaction, docs.aws.amazon.com/amazondynamodb/latest/developerguide/WorkingWithItems.html, developer.hashicorp.com/terraform/language/block/removed, docs.incident.io/incidents/roles.

---

created: 2026-11-26T19:33:00Z

---

2026-11-26 (human): plan APPROVED as recommended, OQ1-OQ7 and the program-scope assessment (comment of the same date). Applied: TASK-145.7.13 created (terraform-only SSM expand PR, merges before layer A; deployment.md rule rides with it); TASK-145.7.10.1 created (deletion layer B above A, exit criterion; old AC #2 deletions, dev add-incident/load-incidents retired as kind (d)); ACs reworded (#1 rewired pins, #2 A-scope seams, #3 cites webhooks.md section 8 checked after #1889, #6 via 145.7.13) and #7 added (migration.md deletion-layer rule, rides with layer A); depends on 145.7.13; TASK-145.12.2 scope narrowed; question recorded on TASK-145.10.5. Order: 145.7.13 (side PR from main), then layer A on a new stack (branch stack-l2/task-145.7.10-declare-cutover), then 145.7.10.1 above it.

---
<!-- COMMENTS:END -->
