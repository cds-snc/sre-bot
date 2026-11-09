---
id: TASK-145.7
title: >-
  Rebuild declare and the alert buttons in incident/response, writing the record
  through core
status: To Do
assignee: []
created_date: 2026-10-09 16:43
updated_date: '2026-11-09T18:10:00Z'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-36.1.1
  - TASK-103
  - TASK-111.10
  - TASK-111.14
  - TASK-145.5.9
  - TASK-145.6
  - TASK-157
  - TASK-111.15.1
  - TASK-187
  - TASK-145.8
references:
  - https://github.com/cds-snc/sre-bot/issues/1698
  - decisions/incident-management.md
parent_task_id: TASK-145
priority: medium
type: feature
ordinal: 357000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer C1 of TASK-145, the first response slice: plugin incident.response. Rebuilds /incident, the declare modal, the locale toggle and the call-incident and ignore-incident buttons shown under alerts (fed into alert channels by product infrastructure or the SIEM through the webhooks pipeline), then cuts them over.

THIS SLICE
- response/entrypoints/slack.py and slack_views.py: the handlers above, each one service call, registered through the Slack registrar; the alert actions register into the webhooks capability's extension point when it exists, otherwise through the registrar with a later move.
- The declare submission validates before its single ack. The legacy submit() in modules/incident/incident.py acks twice (an empty body, then response_action=errors), so its validation errors reach Slack only by winning a race; TASK-36.1.1 pins the errors response.
- response/service.py declare flow: create the record through IncidentStore with severity and the declarer, create the conversation and set its purpose, create the report from the template and bookmark it, create the video call and bookmark it, create the canvas, bookmark the source alert when present, invite the on-call people (ProductCatalog schedule today; the on-call capability with TASK-146.3) and the configured groups, append the list projection row, post the announcement. Each reference is written to the record as it is created; a failed resource leaves the record with that reference empty and the recreate path (TASK-145.8) fills it.
- The video-call creator moves from features/incident/meet into core/adapters/google_meet.py; meet/ is deleted.
- The product picker reads ProductCatalog and respects Slack option limits. The severity picker offers none and SEV0 to SEV4 from common/vocabulary: SEV0 is the only new option, and the announcement's severity warning covers it as it covers SEV1 to SEV4.
- Legacy registration of these surfaces is removed from modules/incident in the same PR; names, fields, replies and i18n keys unchanged, pinned by TASK-36.1. The declare path reads its settings (the incident announcement channel and the security and Notify management group ids) from the incident response slice in common/settings.py, which TASK-111.15.1 makes their one owner.

RECORD SHAPE (decisions/incident-management.md Stored form and Migration)
- create sets record_version = RECORD_VERSION and writes the end-state attribute names, never the legacy ones as the record of truth. RECORD_VERSION and OPEN_BUCKET are imported from core/store.py (defined by TASK-145.5.4, where list_open queries OPEN_BUCKET).
- create sets open_bucket = OPEN_BUCKET and opened_at in the same write. opened_at uses the stored-time formatter format_stored_time in core/adapters/incident_items.py (fixed-width ISO-8601 UTC, isoformat(timespec="microseconds"), +00:00), added by TASK-145.5.8 and shared with TASK-145.8 (reopen) and the TASK-145.5.7 job.
- References are nested maps per kind (conversation, report, video_call, postmortem_meeting, external_case, source_alert), each {system, tenant, vendor_id, url}, written whole. The conversation map and the top-level channel_id (the by_channel key) are set in one multi-change update.
- security_incident is a required bool taken from the modal.
- create relies on put_if_not_exists (TASK-103) reporting created for its own SDK-retried write; every item written through it carries a hidden _rs_write_token attribute that reads strip, and attribute names starting with _rs_ are reserved and rejected.
- Decide the source_alert shape at planning: a chat alert is a message, so conversation plus message id, like MessageReference.
- Legacy readers stay live until TASK-145.8: app/models/incidents.py Incident (extra="forbid"; channel_name, teams and report_url required), used by information_display.py, information_update.py and db_operations.py, raises on a new-shape item. Decide at planning: either dual-write the legacy attributes and relax that model to extra="ignore", or ship in the same release as TASK-145.8.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 features/incident/response/ is registered as incident.response and handles /incident, the declare modal, the locale toggle and the alert buttons; the legacy registrations are gone
- [ ] #2 The declare flow writes the record first and every resource reference as it is created; a failing resource is logged and leaves its reference empty without aborting the rest
- [ ] #3 features/incident/meet is deleted and the video-call adapter lives in core/adapters/
- [ ] #4 The pinned declare and alert-button behaviour passes unchanged
- [ ] #5 create stamps record_version 1 and writes the end-state attribute names, the nested reference maps and security_incident as a bool from the modal; the conversation map and channel_id are set in one multi-change update
- [ ] #6 The legacy readers (app/models/incidents.py Incident and its callers) keep working on new items until TASK-145.8, by the option chosen at planning (dual-write with extra="ignore", or the same release as TASK-145.8), and the source_alert shape is recorded in the plan
- [ ] #7 create imports RECORD_VERSION and OPEN_BUCKET from core/store.py and sets record_version, open_bucket and opened_at in the same write; opened_at comes from format_stored_time in core/adapters/incident_items.py (fixed-width ISO-8601 UTC, isoformat(timespec="microseconds"), +00:00), tested for width and offset
- [ ] #8 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
- [ ] #9 The new-incident policy (INCIDENT_CORE__NEW_INCIDENT_SYSTEM) resolves at startup against the configured-systems read (TASK-145.5.9): set, or unset with one configured system; when the named system is unconfigured, none is configured, or the policy is unset with several, boot fails with one CRITICAL plugin_boot_failed event naming the key (declare is the feature's core path, so an enabled incident feature requires it: decisions/plugins.md, TASK-172) (tested)
- [ ] #10 incident.response reads the handbook id from [incident_response] handbook_id (features/incident/response/settings.py) and states it as required when it registers (decisions/plugins.md: a plugin states what it requires by resolving it; boot fails naming the key when it is empty). The key itself is already in place (TASK-111.10.3: non-public, declared empty in base.toml, value from the environment only)
- [ ] #11 Cutover per decisions/migration.md step 4 and decisions/testing.md seams: the pins pass with assertions unchanged, their fixtures rewired to the target Protocol fakes with the matching seam-baseline entries removed; legacy_only_* tests for behaviour this task ends are deleted; modal-internal ids take the incident.<subdomain> prefix and ids on posted messages stay registered as legacy aliases; new tests pass make check-test-seams
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PROPOSED, AWAITING APPROVAL. Stack L program re-plan of 2026-11-09 against main 3075170b (#1827 and #1840 merged). Supersedes the 2026-10-09 outline and the uncommitted 145.7-only split (twelve slices, then seven PRs). Planning only: no subtasks until the human approves the breakdown. The cross-task order lives in doc-11 row 18; this plan holds 145.7's slices (L0, L1, L2a, L2b, L4a, L4b, L4d, L5, L9a, L9b), the domain-model gate and the A1 clauses. TASK-145.8 holds L3, L6a, L6b, L7a, L7b; TASK-145.9 holds L10a-L10d; TASK-145.12 holds L4c and L11.

## 0. Program rules (human, 2026-11-09)
- One storage expand: sre_bot_incident_surface_bindings is the only new table in TASK-145; incidents, sre_bot_incident_timeline and sre_bot_incident_status_updates already exist (terraform/dynamodb.tf:91, :153, :73).
- The final shape is built in core per area, inert until a cutover registers it.
- Readers before writers: every legacy reader of incident items is cut over (TASK-145.8) before the rebuilt declare writes. Declare writes only the end-state shape: no dual-write, no extra="ignore" and no severity coercion on app/models/incidents.py.
- The 145.5.7 job upgrades every item and puts its binding in one pass (marker 2).
- Each cutover is one git revert. TASK-145.13 contracts only the by_channel fallback, the legacy alert/button aliases and modules/incident.

## 1. Re-grounded state at main 3075170b (corrections to the 2026-11-09 research)
- Legacy declare (frozen, legacy: do not cite as reference): modules/incident/incident.py:31-33 registers /incident, incident_view, incident_change_locale; submit (128) acks at 130 and again with errors at 146. incident_alert.py:52 handle_incident_action_buttons, registered at incident_helper.py:149; producer of its callback id api/v1/routes/webhooks.py:173 (append_incident_buttons, 165). core.py: initiate_resources_creation 422 writes the item through db_operations.create_incident at 525; _create_database_record 291 (create at 316) is reached from recreate_missing_resources 336 (call at 406); meet import core.py:12. on_call.py:12 reads Drive folder appProperties (genie_schedule) through incident_folder.py:115 then integrations.opsgenie.
- Every legacy writer of incident items: core.py:525 (declare, until L9b), core.py:316 via recreate (until L7b), incident_folder.py:541 create_missing_incidents via dev load-incidents and modules/dev/incident.py:104 add-incident (until L11), db_operations.update_incident_field from information_update.py:322 and incident_status.py:59 (until L6a/L6b), log_activity (logs list_append, safe on any shape).
- Every legacy reader that breaks on an end-state-only item: information_display.py:29 and information_update.py:329 (Incident(**item), extra="forbid"), incident_helper.py:443 and :592 (status/close), core.py:377 (recreate): all TASK-145.8. modules/dev/incident.py:20-30 list (dev only, KeyError): L11. Not item readers: reaction capture (incident_conversation.py:261, :322), the stale nudge (notify_stale_incident_channels.py:10), retro scheduling, folder metadata, scribe summarize; comms and scribe draft already read through core. So readers-first holds with TASK-145.8 alone.
- app/models/incidents.py: Incident is validated by db_operations.create_incident (:65), the writer legacy declare and recreate use; IncidentPayload by incident.py:14 and core.py:15. The file can only go with the legacy declare (L9b), not with TASK-145.8.
- Core: store.py RECORD_VERSION 1 (61), OPEN_BUCKET (63), query bound 10 (66); IncidentStore (91) has get, find_by_conversation (150: by_channel, system/tenant filter 181, mismatch warning 185), list_open, read_security_flag; no writes. api.py: IncidentConversation (150) has post, set_purpose, add_bookmark, invite, archive, is_writable only; IncidentReport (194) create_from_template(title) (204); build_incident_store (244); find_incident_for_conversation (305). domain.py: SourceAlertReference 206, MessageReference 278. Job: response/legacy_upgrade_job.py:15, core/legacy_upgrade.py (_plan_item 230 private, guards record_version absent plus each read attribute); upgrade_legacy_item core/adapters/legacy_items.py:99 is pure.
- Registrar: contracts/slack/registrar.py command 32, block action 68, view submission 85; server/plugins/slack_registrar.py prefix check 81-83; integrations/slack/provider.py _register_listener 636, _attach_interaction_listeners 653. No attachment actions, no aliases, although decisions/transport-slack.md:39 already promises aliases.
- No resolver of incident_core.new_incident_system (field only, common/settings.py:49; a test asserts build_incident_store ignores it). GAP: production configures Slack and Google with the policy unset (production.toml has no key), so the ADR rule "unset with several systems fails boot" would take production down the moment a resolver is wired. L1 sets it.
- Job README (features/incident/README.md:50-82) names no legacy writer except the sheet import and implies none remains after TASK-145.12; it omits modules/dev/incident.py:104, the recreate path and legacy declare. L2b fixes it.
- infrastructure/services/providers.py and dependencies.py do not exist (CLAUDE.md cites them): the spreadsheets getter is infrastructure/spreadsheets/factory.py:24; TASK-145.12 AC #6 forbids it for incident anyway.
- No contract enforces "no umbrella module imports integrations.opsgenie" (decisions/incident-management.md:108, oncall.md:32): pyproject contract (e) permits any adapters/ module; packages/oncall_sync/adapters/opsgenie.py already imports it.

## 2. Program breakdown (all four tasks; size per PR is production code only)
| PR | Task | Scope | Prod LOC / files | Subsystem | Waits on | Pins / seams | Blast radius, revert |
| L0 | 145.7 | bindings table + by_conversation GSI + IAM index grant; A1 | ~45 HCL / 2 + ADR | terraform | - | none | additive empty table; revert destroys it (no reader) |
| L1 | 145.7 | registrar attachment actions + legacy aliases (block and attachment); new-incident policy resolver + production.toml policy; handbook requirement | ~280 / 9 | host + incident response | - (side PR, any time) | none | boot: a misconfigured policy or empty handbook id fails boot (rolled back by the circuit breaker); revert restores |
| L2a | 145.7 | IncidentSurfaceBinding, binding items, bindings-first lookup with by_channel fallback, fake | ~300 / 7 | incident core | L0 deployed | none | every lookup; empty table means fallback = today; revert restores |
| L2b | 145.7 | job binding step, marker 2, shared per-item upgrade plan made public; README legacy writers | ~230 / 5 | incident core + response job | L2a | none | job is off in production: inert; revert restores |
| L3 | 145.8 | core update operations (see 145.8) | ~350 / 5 | incident core | L2b | none | inert |
| L4a | 145.7 | IncidentConversation create, create_canvas, group_members, set_topic, post blocks; IncidentReport list_placements + create_from_template(placement) | ~280 / 6 | incident core | - | none | inert |
| L4b | 145.7 | VideoCall Protocol; features/incident/meet moved to core/adapters/google_meet.py; meet/ deleted | ~140 / 6 | incident core (move) | - | none | legacy declare and recreate call the moved function: one revert |
| L4c | 145.12 | list projection adapter in core (append_row, update_status) over integrations/google_workspace | ~150 / 4 | incident core | - | none | inert |
| L4d | 145.7 | interim on-call adapter in core (OQ1; only if allowed) + ratchet contract | ~130 / 4 | incident core + pyproject | - | none | inert |
| L5 | 145.7 | IncidentStore.create (binding, then record; end-state only); set_reference; source_alert = MessageReference + url | ~280 / 6 | incident core | L2a | none | inert |
| L6a | 145.8 | cutover show + update modal (severity, security flag) | ~380 / 9 | response | L3 | rewires field-update pins | show/update; one revert |
| L6b | 145.8 | cutover status; IncidentReport.set_status_text (mapping moved) | ~300 / 7 | response + core adapter | L3, L4c | rewires status pins | status; one revert |
| L7a | 145.8 | cutover roles + archive (alias archive_channel); 36.1.2 rulings | ~350 / 8 | response | L1, L3 | rewires roles and archive pins; deletes legacy_sre_web_client_seam and its baseline entry | roles/archive; one revert |
| L7b | 145.8 | cutover recreate (create resources) | ~250 / 6 | response | L3, L4a, L4b | recreate unit tests | recreate; one revert |
| L8 | job | production.toml upgrade_mode dry_run, then apply (two config PRs) + human runs | ~2 / 1 each | config | L2b, L6a-L7b deployed | none | job writes every item; revert = mode off; items stay upgraded (readers accept both) |
| L9a | 145.7 | declare service in response, unregistered | ~380 / 5 | response | L4a, L4b, L4c, L4d?, L5, L1 | none | inert |
| L9b | 145.7 | cutover /incident, modal, locale toggle, alert buttons, SEV0; legacy declare and app/models/incidents.py deleted (size exception) | ~650 + deletions / ~14 | response + api/v1 webhooks producer | L8 applied, L9a | rewires declare pins; deletes legacy_acknowledged_webhooks_seam, baseline lines 9 and 17 | declare, the most used surface; one revert restores legacy declare (it writes legacy items, which the core bridge reads) |
| L10a-d | 145.9 | see 145.9 | | | | | |
| L11 | 145.12 | see 145.12 | | | | | |
| L12 | human | job rerun after the last legacy writer (Migration rule 6) | - | - | L11 deployed | - | - |
Then TASK-145.13 (contract) after Stack M; its gate is OQ12.
Corrections to the expected list: L2 split (bindings vs job step: ~530 LOC together); L4 split in three (conversation/report, the meet move is mechanical, the projection adapter belongs to 145.12 but is needed by L6b's status fan-out); L6 and L7 split in two each (~450-500 and ~600 LOC); L9 split into the inert service and the cutover (exception shrinks to ~650 LOC); the Incident model goes in L9b, not L7 (legacy declare validates it); L10 splits in four and only summarize waits on 25.10.

## 3. Domain-model gate: IncidentSurfaceBinding (decision of the human: one new table)
Entity: child record of the incident, keyed (incident_id, binding_key = "<kind>#<system>#<tenant>#<vendor_id>"); kind chat_conversation now, backstage_page reserved; fields kind, system, tenant, vendor_id, url hint, conversation_id (chat kinds only: sparse GSI by_conversation), primary, bound_by, bound_at, archived_at. Never deleted; visibility is the incident's.
Scenarios (create / link / reassign / close / roll up):
1 Slack declare: conversation, binding (primary), record as commit point (D2). 2 Declare from an alert: same plus source_alert (MessageReference + permalink hint); the alert channel is not bound; two incidents from one alert are allowed. 3 Rebind to a new channel: not built in Stack L (recreate runs inside the channel and never moves the conversation); TASK-165.x adds it (new primary, old archived_at). 4 Second channel bound (165.x): n chat bindings, one primary; not built. 5 One channel bound to two incidents: lookup fails closed (AMBIGUOUS_INCIDENT_CONVERSATION); declare cannot cause it. 6 Backstage-only incident later: no conversation_id, absent from the GSI. 7 Teams later: system and tenant in the key. 8 Legacy item without a conversation: open = blocker for the job (Migration rule 7), Closed = marker only. 9 Tenant mismatch: dropped with a warning naming both tenants. 10 Dangling binding (crash between puts) invisible; replayed put no-op (TASK-103). 11 Closed incident: bindings stay, read commands work. 12 NEW: a 145.8 write onto a legacy item between L6 and the job (and onto items legacy declare creates until L9b): upgrade-on-write puts the binding and writes the upgraded item with the change and marker 2 in one guarded update (TASK-145.8 AC #7). 13 NEW: revert of L9b: legacy declare writes legacy items again; no legacy reader remains (cut over in L6/L7), the bridge reads them and the next write or job run upgrades them.
Cardinality: incident -> bindings 1..n while active (0 only for Closed legacy items without a channel); primary 1; conversation -> active incidents 0..1 (data allows n, lookup fails closed); incident -> conversation map 0..1 (copy of the primary); incident -> source_alert 0..1.
Options: separate child table chosen (same pattern as timeline and status updates; no list attribute, no read-modify-write). Rejected: list attribute on the incident; a map of maps in conversation; channel_id only; a binding per resource.
Compatibility: no-binding items fall back to by_channel; new declare items keep top-level channel_id (the ADR's lookup copy) so a rollback to a pre-binding build still finds them; end-state-only items are unreadable by app/models/incidents.py, which is safe only because L6a-L7b remove every reader first (the ordering is the compatibility plan); unknown kinds skipped and logged, never routed.
Name: "surface" also means a rebuilt legacy interaction group in migration.md and the pins (OQ10).
Decisions carried from the research (still hold): D2 conversation, then binding put, then record put as commit point until TASK-34; D3 table name, keys and GSI; D4 END_STATE_VERSION 1 and RECORD_VERSION 2; D5 lookup order (bindings, then by_channel, never merged; bindings error is a classified failure); D7 source_alert = MessageReference + url hint, SourceAlertReference deleted; D8 report placements (no product, option C); D9 ids (modal-internal prefixed, posted-message ids aliased); D10 AlertAcknowledgements Protocol + interim records adapter on the webhooks table; D14 boot policy and handbook requirement. Dropped: D6 (dual-write with extra="ignore" and severity coercion), superseded by readers-first.

## 4. L0 in full: storage expand + A1
Branch stack-l/l0-surface-bindings-table from main. Files: terraform/dynamodb.tf, terraform/iam.tf, decisions/incident-management.md.
1. dynamodb.tf, after sre_bot_incident_status_updates (:73): resource aws_dynamodb_table sre_bot_incident_surface_bindings, hash incident_id (S), range binding_key (S), attribute conversation_id (S), read/write capacity 2, GSI by_conversation hash conversation_id, projection ALL, read 1 / write 2; point_in_time_recovery and server-side encryption exactly as the timeline table; header comment: one item per working surface, sort key "<kind>#<system>#<tenant>#<vendor_id>", conversation_id only on chat bindings (sparse index).
2. dynamodb.tf local.dynamodb_table_arns (:262-272): add the arn (backup selection and the task role's table statement, iam.tf:36-46).
3. iam.tf:53-59: add "${aws_dynamodb_table.sre_bot_incident_surface_bindings.arn}/index/*" to the Query-on-index resources.
4. decisions/incident-management.md, docs only (A1):
 a. Vocabulary (26): severity chosen by a person, may be unset at declare, changes as evidence arrives and each change is recorded, never computed from the number of products or teams; 0 per the handbook's criteria (Revision 1).
 b. The incident record (30): declaring binds at least one working surface (a chat conversation now, the Backstage page later); an active incident has one or more bindings, exactly one primary; commands find the incident through any bound conversation; IncidentSurfaceBinding is a child record; "working surface" defined (where responders work the incident; unrelated to migration's rebuilt surfaces) (Revision 2).
 c. Stored form (38): lookup reads the bindings by_conversation index first, then channel_id/by_channel until TASK-145.13; source_alert is a message reference (conversation id, message id, url hint); record_version 1 = end-state shape, 2 = end-state shape with its binding; channel_id stays the lookup copy on new items.
 d. core/ owns (50): find_incident_for_conversation through any bound conversation; IncidentStore create (binding, then record) and updates; the binding store.
 e. System selection (77): resource failure at runtime leaves the reference empty and is reported; declare is unavailable only when no working surface can be bound (Revision 2's per-resource wording, runtime only: OQ9).
 f. Checks (103): declare writes the binding before the record; a binding without a record is not an incident; lookup prefers bindings, falls back to by_channel.
 g. Migration tolerated (121): channel_id and by_channel until the binding backfill is verified (TASK-145.13); the stale "served by a scan of the legacy table" fixed.
 h. Migration ordering (new rule): readers before writers. Every legacy reader of incident items is cut over before the rebuilt declare writes; writers write only the end-state shape; no dual-write; a write onto an item without the marker upgrades it first (upgrade-on-write, with its binding, marker 2) so no partial update stamps the marker (TASK-145.8 AC #7, if OQ approved).
 i. Rule 4 (136) amended: a later step may raise the marker on end-state items: guarded on the value read, side records first (idempotent conditional puts under deterministic keys), marker last, only items below its version. Rule 6 (138): legacy writers named (legacy declare until its cutover, recreate until its cutover, modules/dev/incident.py and the sheet import until TASK-145.12). "For incidents" (141): the binding step (one binding per item from its conversation map for the verified Slack tenant; open item without a conversation fails the run; Closed one only raised).
 j. Changes: one dated line (TASK-145.7 L0, A1).
5. Verification: terraform fmt -check and validate (cd terraform); rg proves no app code names the table. Human: zsh bin/deploy-checks.zsh pre before merge, post after the deploy (terraform and IAM change).
AC traceability: enabling work for AC #5 (re-worded) and for the A1 decisions; no AC is closed by L0. Tests: none (L2a adds the RecordTable-vs-terraform drift test). Rollback: one revert (terraform destroys the empty table, the grant goes). Ordering: deployed before L2a merges.

## 5. L1 in full: host prerequisites (side PR from main, any review window)
Branch task-145.7-l1-host-prerequisites from main. ~280 production LOC, 9 files, two subsystems (host Slack transport; incident response boot). Gate passes (two subsystems allowed; no mechanical move).
1. app/contracts/slack/registrar.py: register_attachment_action(callback_id, listener, *, legacy_callback_ids: Sequence[str] = ()) and a legacy_action_ids keyword on register_block_action (same semantics); docstrings name decisions/transport-slack.md:39.
2. app/server/plugins/slack_registrar.py: the plugin-prefix check (81-83) applies to the primary id only; legacy ids are exempt, must be non-blank and unique, and are logged once at registration (event slack_legacy_id_registered, fields plugin, legacy_id, id).
3. app/integrations/slack/provider.py: _attachment_actions store beside _block_actions (223); register_attachment_action; aliases stored as extra keys of the same listener; duplicate id (alias or primary, across both kinds) aborts boot as _register_listener (636) does; _attach_interaction_listeners (653) attaches app.attachment_action(id) per key; a read-only legacy_ids() listing for TASK-145.13.
4. decisions/transport-slack.md: the alias mechanism (block and attachment actions), legacy ids exempt from the prefix, listed for the contract task; Changes line.
5. app/features/incident/core/api.py (or core/systems.py if api.py nears its size): resolve_new_incident_system(policy: WorkplaceSystem | None, configured: ConfiguredSystems) -> WorkplaceSystem, pure, raising a typed error naming incident_core.new_incident_system.
6. app/features/incident/response/plugin.py: the declare-path requirement: a register_requirements entry Requirement("incident_response.handbook_id") (TASK-184) and the policy resolved in the plugin's startup hookimpl from the configured-systems read (145.5.9), so boot logs one CRITICAL plugin_boot_failed naming the key (plugins.md, TASK-172).
7. app/config/production.toml: [incident_core] new_incident_system = "google" (the only system that creates a report and video call); local.toml the same if it configures both; ci.toml keeps the plugin off (TASK-175). decisions/incident-management.md System selection: unset resolves to the only configured system, and production sets the policy explicitly; Changes line.
Tests (strict zone): tests/unit/server/plugins/test_server_slack_registrar_legacy_ids.py (alias registered and listed, prefix refused on primary only, duplicate across kinds aborts boot, blank alias refused); tests/unit/integrations/slack/test_slack_provider_attachment_action_dispatch.py (an interactive_message payload with the legacy callback id reaches the listener through Bolt dispatch); tests/unit/features/incident/core/test_incident_core_new_incident_system_resolve.py (set + configured; unset + one; unset + several fails; named unconfigured fails; none fails); tests/unit/features/incident/response/test_incident_response_plugin_requirements.py (empty handbook id fails boot naming incident_response.handbook_id; production.toml resolves to google: a configuration test loading production.toml).
AC traceability: #9 (steps 5-7), #10 (step 6), #11 aliases (steps 1-4).
Assumptions: Bolt routes interactive_message to attachment_action(callback_id) (slack_bolt installed has it; test proves it); production's INCIDENT_RESPONSE__HANDBOOK_ID SSM value is non-empty (doc-14 lists it; the legacy modal reads the same slice at incident.py:231) - human confirms before merge.
Blast radius: boot of the whole app (the response plugin is enabled in production): a wrong policy or empty handbook id fails boot; the ECS circuit breaker (TASK-111.16) keeps the previous revision. Revert restores. No deploy-checks script required (no terraform, IAM, SSM or env-name change); post-deploy: one boot with no plugin_boot_failed.

## 6. Outlines (planned in full at pickup)
L2a: core/domain.py SurfaceKind and IncidentSurfaceBinding; core/adapters/binding_items.py (key, item, parse; unknown kind skipped); core/store.py surface_bindings_table + RecordIncidentStore lookup per D5; in-memory fake; common/settings.py surface_bindings_table; build_incident_store passes it. Tests: lookup cases (hit, fallback, dangling, archived, tenant mismatch, ambiguous, bindings error), drift test RecordTable vs terraform.
L2b: core/legacy_upgrade.py: the per-item plan becomes a public function in core (plan_item_upgrade(item, tenant) -> ItemUpgrade(binding, changes, expected)), used by the job and by TASK-145.8's upgrade-on-write; the job puts the binding then raises to RECORD_VERSION 2 (END_STATE_VERSION 1 items get binding + raise); report counts bindings_put, bindings_existing, marker_raised, binding_skipped; README legacy writers listed (legacy declare, recreate, modules/dev/incident.py:104, the sheet import) and the rerun rule. Tests: one pass to 2; rerun no-op; crash between put and update converges; open item without channel fails before any write; dry run writes nothing.
L4a: IncidentConversation create(name) -> ConversationReference (the 145.6.3 ruling: create arrives with the first binding), create_canvas, group_members, set_topic, post(..., blocks); Slack adapter, fake, parity suite; IncidentReport list_placements and create_from_template(title, placement=None).
L4b: VideoCall Protocol (create -> OperationResult[VideoCallReference]), core/adapters/google_meet.py (moved verbatim plus a classified result; no subject kwarg: 145.6 AC #7), fake, get_video_call; modules/incident/core.py:12 repointed; features/incident/meet/ deleted.
L4d (only if OQ1 allows): core/adapters/on_call.py: OnCallInvitees Protocol in core/api.py; the adapter reads the chosen placement folder's genie_schedule through the Drive gateway and the people through integrations.opsgenie; pyproject import-linter contract (n) "integrations.opsgenie only from capabilities/oncall/adapters" with shrink-only ignore entries for packages.oncall_sync.adapters.opsgenie (# TASK-146.2) and features.incident.core.adapters.on_call (# TASK-146.3); ADR Checks lists it as tolerated with its owner.
L5: IncidentStore.create(incident, binding) (binding put, then record put; both put_if_not_exists; the record is the commit point), set_reference(incident_id, kind, reference) guarded on record_version; incident_item() writes end-state names only plus channel_id, record_version = RECORD_VERSION (2), open_bucket and opened_at (format_stored_time) in the same put; MessageReference gains url, SourceAlertReference deleted (api.py, incident_items.py and its tests). Tests: order binding then record; replay no-op; record failure leaves an invisible dangling binding; opened_at width and offset (AC #7).
L9a: response/service/declare.py orchestrating over the Protocols: validate, conversation, binding + record, purpose, report in the chosen placement + reference + bookmark, video call + reference + bookmark, canvas, severity warning, source alert bookmark/message, invites (declarer, security group, Notify management group per OQ2, on-call per OQ1), announcement, next steps, list row (L4c). A failing conversation creates no record (OQ6); each later failure leaves its reference empty and continues. Unregistered.
L9b: response/entrypoints/slack.py and slack_views.py: /incident (ack, loading view, update), view incident.response.declare validating before its single ack, action incident.response.locale, alert buttons incident.response.alert_buttons with legacy alias handle_incident_action_buttons (L1), ignore through AlertAcknowledgements (records adapter on the webhooks table, OQ7); api/v1/routes/webhooks.py:173 posts the new id (OQ4); SEV0 option and warning (the pinned options assertion changed deliberately); locales moved verbatim; legacy incident.py, incident_alert.py handler, registrations (incident.py:31-33, incident_helper.py:149), core.py declare path and app/models/incidents.py with tests/unit/models/test_models_incident_legacy_attribute_load.py deleted; pins rewired to Protocol fakes, legacy_acknowledged_webhooks_seam and baseline lines 9 and 17 deleted; INVENTORY rows. Size exception requested: one revert must restore legacy declare whole.

## 7. AC traceability and proposed AC changes (proposed in a comment; no AC edited)
#1 L9b. #2 L9a (reworded). #3 L4b. #4 L9b. #5 L5 (reworded: RECORD_VERSION 2). #6 superseded by readers-first (proposed: "no legacy reader of incident items remains when declare cuts over; declare writes only the end-state shape; source_alert = MessageReference with url hint"). #7 L5. #8 every PR. #9 L1. #10 L1. #11 L1 + L9b.

## 8. Assumptions and doubts
1 Bolt attachment_action dispatch (L1 test). 2 Production handbook id set (human, before L1). 3 The registrar's reply sender supports the loading-view pattern of /incident (verify at L9b against comms). 4 RecordStore.update with IncrementAttribute may be retried by the SDK (records/store.py docstring); the ack adapter accepts an over-count as today's lost count is accepted. 5 No production item is at record_version 1 (first dry run reports already_upgraded 0). 6 terraform apply on merge needs only deploy-checks (ci workflow).

## 9. Open questions: see doc-11 row 18 and the comment on this task (OQ1-OQ4, OQ6, OQ7, OQ9, OQ10 carried; OQ11 onward new).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-14 (TASK-145.5 split): create sets open_bucket OPEN and opened_at (fixed-width ISO-8601 UTC, microseconds, +00:00) in the same write, and every reference takes its tenant from the event payload (Slack team_id), not from settings.

2026-10-20 (SLACK_TEAM_ID review): writers stamp the configured Slack tenant, which TASK-157's runtime guard has verified against the request (decisions/workplace-systems.md rule 3); with SLACK_ENTERPRISE_ID set the tenant is the Enterprise org id. Depends on TASK-157.

- 2026-10-28 (TASK-167 accepted): locales/incident.*.yml carry CDS wording; each incident surface rebuild moves the strings it touches to provisioned organisation wording (message overrides by key over generic app strings, decisions/organisation-content.md, i18n.md), keeping generic defaults in the app.

2026-11-04 (TASK-145.5.7 planning, human approved): (1) incident.response is already a plugin when this task starts: TASK-145.5.7.3 adds its entry point, contract (m) entry, [plugins.incident_response] key (true in base, false in ci), register_requirements for the Slack and Google tenants, and one hookimpl registering the legacy upgrade job; declare is added to that plugin. (2) The binding backfill (doc-11 row 18) is a step added to the TASK-145.5.7 job, not a new runner (incident-management.md Migration rule 3): after declare writes bindings and lookups fall back (rule 1), the step puts one binding per record from its conversation map idempotently and raises the version marker to 2 for every item below it (rule 4 amendment recorded for A1, doc-11 row 17a). (3) Batch writers stamp the tenant verified through contracts/workplace TenantVerifier (workplace-systems.md rule 3, 2026-11-04).

2026-11-04 (human approved, coordinated-incidents reconciliation): option C: declare ships without a product. The record's product stays unset until TASK-165.1's catalogue exists; the declare picker becomes a labelled report-folder choice (placement configuration of the report adapter) or a single configured incidents folder, never a product picker over Drive folders. The on-call invite from folder metadata stays on the legacy path until the on-call capability (TASK-146) provides it. Adding the product to declare later is additive (an optional field and a picker over ProductCatalog).

2026-11-06 (TASK-36.1.2 OQ1, human-approved; for the Stack L re-plan): interaction ids follow decisions/transport-slack.md as amended: modal-internal ids (the declare modal, the locale toggle) take the incident.response prefix and the pin reads them from the opened view; ids on messages already posted (the alert buttons under webhook alerts) keep a registered legacy alias until TASK-145.13. 'names unchanged' in this task means command names and posted-message ids.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-03T19:00:00Z

---

Coordinated incidents target-shape note (doc-11 row 18): after the A1 incident-management ADR amendment, re-plan declare to create incident_surface_bindings and use binding-based lookup. E1.1/E1.2 are the first slices; retain the by_channel fallback only until legacy bindings are backfilled, then retire it in the existing contract task.

---

created: 2026-11-05T20:31:00Z

---

2026-11-05 (TASK-145.6.3 approval, OQ1, G1): IncidentConversation ships in 145.6.3 without create. 145.7 adds create(name, *, private) -> OperationResult[ConversationReference] to it, designed with the first working-surface binding (E1.1/E1.2, after A1): declare's record plus first binding is one durable operation, and a replayed Slack conversations.create answers name_taken, so create must converge on retry instead of failing or duplicating. Its Slack call goes through the rate-limit-only write handle (outbound-clients.md non-idempotent write rule). Every conversation write calls conversation_is_writable(conversations, conversation | None) first; pass the record's conversation (the primary binding once bindings exist). invite takes chat account ids in the conversation's tenant (people-and-accounts.md). The port is async (transport-slack.md).

---

created: 2026-11-09T18:10:00Z

---

Stack L re-plan 2026-11-09: open questions (recommendation each; human rules):
OQ1 on-call invite after the declare cutover: allow one interim on-call adapter in core (L4d: genie_schedule read from the chosen placement folder through the Drive gateway, people through integrations.opsgenie), enforced as a ratchet: a new import-linter contract "integrations.opsgenie only from capabilities/oncall/adapters" with shrink-only ignore entries (core adapter # TASK-146.3, packages.oncall_sync adapter # TASK-146.2), listed as tolerated in incident-management.md Checks. Rejected: a gap until 146.3 (user-visible regression on every declare).
OQ2 Notify management group: key on the chosen placement's id from [incident_response] notify_management_placement_id (an id, no organisation string); revisit with the product id at TASK-165.1.
OQ3 list row writer: an incident-owned core adapter over integrations/google_workspace (TASK-145.12 AC #6, TASK-169 ruling), not infrastructure.spreadsheets and not a modules/ wrapper; built early as L4c.
OQ4 alert id producer api/v1/routes/webhooks.py:173: posts incident.response.alert_buttons from L9b; handle_incident_action_buttons stays a registered alias until TASK-145.13.
OQ6 a failed conversation creates no record (the user is told, as today when the channel cannot be created): accept.
OQ7 ignore-button counter: AlertAcknowledgements Protocol in response with an interim records adapter (IncrementAttribute) on the webhooks table; moves into the webhooks capability when TASK-168 builds it.
OQ9 Revision 2's per-resource "disables" wording: runtime only (a failed resource leaves its reference empty); the startup policy still fails boot.
OQ10 the term: keep IncidentSurfaceBinding, define "working surface" in A1 (where responders work the incident), distinct from migration's rebuilt surfaces.
OQ11 (new) production policy: L1 sets [incident_core] new_incident_system = "google" in production.toml; otherwise the ADR rule (unset with several systems fails boot) takes production down when the resolver is wired. Alternative: narrow "unset" to the only configured system that can create a report (rejected: hides a capability check in a default).
OQ12 (new) the TASK-145.13 gate (incident-management.md 2026-11-06 line; reassessed): (A) keep the waits on 165.1 and 146.3: by_channel, the aliases and modules/incident live into doc-15; (B) recommended: OQ1's interim adapter, so 145.13 waits on neither (declare's folder picker is report placement configuration since option C, not the catalogue); 165.1's one-off import and 146.3 replace the adapter later and delete its ignore entry; (C) adapter plus the one-off genie_schedule import into the bot's product list now: pulls 165.1's store and D28-D32 into Stack L.
OQ13 (new) each person-chosen severity change is recorded by TASK-145.8 (TASK-154 owns lifecycle only) as a timeline entry; 145.9 AC #5 (timeline_table, entry_key, ids) moves to L3.
OQ14 (new) SEV0: the update modal keeps none, sev-1..sev-4 at L6a (pin unchanged); L9b adds SEV0 to the declare and update pickers together.
OQ15 (new) TASK-36.1.2 legacy bugs at L7a: Sentinel archive event sent once; a refused archive logs nothing; the roles purpose output kept as pinned (the note does not match the pin); products vs product left to 145.13 (the command is retired).
OQ16 (new) recreate in a channel with no record answers not-an-incident (AC #1); the legacy record-creating branch is not carried.
OQ17 (new) the dev incident commands (list, add-incident, load-incidents) are deleted in L11 (145.12 AC #2); dev list fails on end-state items from L9b to L11 (dev only): accept.
OQ18 (new) revert window: once a rebuilt writer upgrades an item (L6a onward), reverting that reader cutover leaves the legacy Incident model (extra=forbid) unable to read it. Accept: each reader cutover soaks before L8; after first writes a regression is fixed forward. Alternative (rejected by the program rules): extra="ignore" on the legacy model.
OQ19 (new) size exceptions: L9b (~650 production LOC plus deletions; one revert restores legacy declare) and L10c (pure move ~450 lines).
OQ20 (new) 145.9 AC #4 moves to 145.12 (legacy importers of db_operations remain until L11).

---

created: 2026-11-09T18:10:00Z

---

Proposed AC changes (not applied; human decides): #2 'writes the record first' -> once the conversation exists, the binding then the record are written, every other reference as it is created, a failing resource leaves its reference empty, a failing conversation creates no record. #5 'record_version 1' -> RECORD_VERSION (2: end-state shape with its binding) from core/store.py; the conversation map and channel_id in the record's put. #6 (dual-write option) -> superseded: no legacy reader of incident items remains when declare cuts over; declare writes only the end-state shape; source_alert is a MessageReference with a url hint. #11 add: posted-message ids registered as aliases through the host registrar (L1). New: lookup prefers bindings and falls back to by_channel, fail-closed on ambiguity; the upgrade job puts one binding per item and raises the marker to 2 in one pass; app/models/incidents.py is deleted with the legacy declare.

---
<!-- COMMENTS:END -->
