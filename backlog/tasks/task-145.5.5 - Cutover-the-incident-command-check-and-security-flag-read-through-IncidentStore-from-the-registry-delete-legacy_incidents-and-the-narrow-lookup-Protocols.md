---
id: TASK-145.5.5
title: >-
  Cutover: the incident command check and security flag read through
  IncidentStore from the registry; delete legacy_incidents and the narrow lookup
  Protocols
status: Done
assignee: []
created_date: '2026-10-14 23:09'
updated_date: '2026-10-20 18:36'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.5.10
  - TASK-145.5.9
  - TASK-145.5.8
  - TASK-145.5.2
  - TASK-145.5.1
  - TASK-152
references:
  - decisions/dependency-injection.md
  - decisions/incident-management.md
  - 'https://github.com/cds-snc/sre-bot/issues/1694'
parent_task_id: TASK-145.5
priority: medium
type: task
ordinal: 391000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 9 of Stack K (handoff doc-13). The behaviour change of TASK-145.5: incident lookups move from a full-table scan to the by_channel index. Standalone merge and deploy, only after layers 5 and 6 (TASK-145.5.4, TASK-145.5.8) and layers 7 and 8 (TASK-145.5.9 configured-systems read, TASK-145.5.10 store builder) have merged, and TASK-152 and TASK-145.5.1 are applied. Split 2026-10-19 (human): the configured-systems read and the store builder moved to TASK-145.5.9 and TASK-145.5.10.

THIS SLICE
- Comms entry points: each handler that reads an incident opens a scope through the ServiceScopeOpener (TASK-145.5.2), resolves RecordStore, builds the IncidentStore with the TASK-145.5.10 builder, and builds the ConversationReference (Slack, the configured Slack tenant from the configured-systems read, the channel id). It passes the store and the reference to the service (human, 2026-10-19: the entry point builds the reference, so when writers take the tenant from the event payload, TASK-145.7 on, and when Teams arrives, only entry points change). No get_record_store import and no import-linter ignore entry (contract (k)).
- Startup skip (human, 2026-10-19): the comms entry points register only when Slack is in the configured-systems read; otherwise one startup event names SLACK_TEAM_ID. No per-invocation skip.
- core/api.py: find_incident_for_conversation takes the IncidentStore and the ConversationReference and calls IncidentStore.find_by_conversation. get_incident_lookup, get_incident_security_reader (lru_cache providers, which dependency-injection.md:37 forbids across layers) and the IncidentLookup and IncidentSecurityReader Protocols are deleted (human, 2026-10-14: one Protocol per core resource, as TASK-145.6 does for the report).
- comms/service.py and form.py: the lookup and security-reader fallbacks that resolve a service mid-function (service.py:106,178,257,361,498) go; the functions take the IncidentStore and the ConversationReference as required parameters.
- Comms tests move from their local lookup fakes to the in-memory IncidentStore fake (TASK-145.5.4).
- Security flag (human, 2026-10-15): comms moves from IncidentSecurityFlag to the bool returned by IncidentStore.read_security_flag (security_incident on the record). A missing legacy flag reads as false (the bridge, TASK-145.5.8), so the comms confirmation gate no longer fires for old incidents; the human accepted this.
- core/adapters/legacy_incidents.py is deleted; in the same PR the IncidentSecurityFlag enum (core/domain.py) and its tests are deleted.
- The new-incident policy is not read here (decisions/incident-management.md, amended 2026-10-19: resolved only by the declare path, TASK-145.7).
- Rollback: one revert restores the scan.

MERGE ORDER WITH TASK-24 (human, 2026-10-19)
- TASK-24.4 (Google settings move, edits server/configured_systems.py) follows the #1728 merge (TASK-145.5.9), so it rebases onto the configured-systems read rather than racing it.
- TASK-24.5 (Google and Slack tenant entries, deletes infrastructure/configuration/integrations/) merges only after this cutover has deployed and been checked in production; it never ships in the cutover's deploy.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 find_incident_for_conversation and the security flag resolve through IncidentStore, built at the entry point with the TASK-145.5.10 builder from a RecordStore resolved through the ServiceScopeOpener
- [x] #2 comms services take the IncidentStore and the ConversationReference as required parameters and resolve no incident lookup or security reader themselves (the StatusUpdateStore, transcript reader and generator defaults stay until TASK-145.5.6 and later)
- [x] #3 No get_record_store import and no new import-linter ignore entry; lint-imports passes
- [x] #4 Entry-point tests cover success and the not-an-incident, ambiguous and store-failure error mappings
- [x] #5 The entry point builds the ConversationReference from the configured Slack tenant (configured-systems read) and the channel id; find_incident_for_conversation passes it to IncidentStore.find_by_conversation
- [x] #6 core/adapters/legacy_incidents.py, IncidentLookup, IncidentSecurityReader, the IncidentSecurityFlag enum, their providers and tests are deleted; rg finds no reference in app/
- [x] #7 comms reads the security flag as the bool from IncidentStore.read_security_flag; a missing legacy flag reads as false and the confirmation gate does not fire (tested)
- [x] #8 A legacy item without record_version resolves end to end in the entry-point tests
- [x] #9 The comms entry points register only when Slack is in the configured-systems read; otherwise one startup event names SLACK_TEAM_ID (tested)
- [x] #10 ruff, mypy (no new errors in touched files), every make check-* CI step and make test pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Layer 9 of Stack K, on stack-k/task-145.5.5-incident-cutover above layer 8 (#1730).

SIZE GATE (re-checked 2026-10-20): passes. Production: 7 Python files in one subsystem (features/incident): core/api.py, core/domain.py, core/store.py (docstring), core/adapters/legacy_incidents.py (deleted), comms/service.py, comms/form.py, comms/entrypoints/slack.py; plus the two incident READMEs. About 170 lines added or changed and 230 deleted. Tests: about 16 comms and core test files edited (mechanical move from local lookup stubs to the in-memory stores, tied to the signature change), 2 core test files deleted, 1 new entry-point test file, 1 new test fake. No mechanical refactor separate from the behaviour change.

STEPS
1. Test fake (tests/factories/services.py, new): FakeServiceScopeOpener over a mapping {contract: service}; create_scope yields a resolver whose get raises KeyError for an unregistered contract, and counts opened and closed scopes.
2. core/api.py: find_incident_for_conversation(store: IncidentStore, conversation: ConversationReference) -> OperationResult[Incident] calls store.find_by_conversation (stays the documented command check, which later grows conversation_is_writable). Delete IncidentLookup, IncidentSecurityReader, get_incident_lookup, get_incident_security_reader, the legacy_incidents imports and their __all__ entries; drop IncidentSecurityFlag from the exports. Module docstring updated.
3. Delete core/adapters/legacy_incidents.py and the IncidentSecurityFlag enum in core/domain.py. core/store.py docstring: production builds the store at the comms entry points.
4. comms/service.py: get_status_update_overview, get_pending_status_update, start_status_update_draft, save_status_update_draft and generate_status_update_draft take `incidents: IncidentStore` and `conversation: ConversationReference` as required parameters (replacing conversation_id, lookup and security_reader). Each calls find_incident_for_conversation(incidents, conversation) and uses incident.id; the transcript window reads conversation.vendor_id. _security_gate reads incidents.read_security_flag(incident_id): success with False passes; True refuses with SECURITY_CONFIRMATION_REQUIRED; a failed read refuses (logged), never passes. Log binds keep conversation_id (vendor_id) and incident_id. The StatusUpdateStore, transcript reader and generator defaults stay (TASK-145.5.6 and later).
5. comms/form.py: start_status_update_form, save_status_update_form and fill_status_update_form take incidents and conversation instead of conversation_id and pass them through.
6. comms/entrypoints/slack.py:
   - _incident_context(scopes, channel_id): context manager that opens one scope, resolves RecordStore and ConfiguredSystems, builds the store with build_incident_store(records, systems, get_incident_core_settings()) and the ConversationReference(system=SLACK, tenant=systems.tenants()[SLACK], vendor_id=channel_id), and yields both; the service call runs inside the scope.
   - handle_status_update_command, handle_new_update_action, handle_history_action, handle_generate_action and handle_save_action take the ServiceScopeOpener as a last parameter and call the services inside _incident_context. Review, open, published and the review submission read by incident id only and are unchanged.
   - register(registrar): opens one scope, reads ConfiguredSystems; without SLACK it logs one warning event incident_comms_registration_skipped (reason slack_not_configured, setting SLACK_TEAM_ID) and registers nothing. Otherwise it registers closures with Bolt's argument names (ack, body, client) that pass registrar.service_scopes to the handlers.
   - No get_record_store import and no import-linter ignore entry: RecordStore and ConfiguredSystems come from contracts, resolved through the scope.
   - INCIDENT_RECORD_UNREADABLE (a candidate the bridge cannot read) shows the generic error text; it is logged with its code.
7. READMEs: features/incident/README.md core row and comms/README.md dependency diagram lose the deleted names and describe the store built at the entry point.
8. tests/unit/bin/test_bin_fake_coverage_check.py: the fixture's sample Protocol name IncidentLookup becomes a neutral name, so rg finds no reference in app/.

AC -> STEP -> TEST
- AC1 -> 2, 4, 6 -> test_incident_comms_status_update_entrypoint_incident_resolution.py (command over FakeServiceScopeOpener with InMemoryRecordStore and a configured-systems fake; overview shows the incident's updates).
- AC2 -> 4, 5 -> service tests (overview, pending, save, origin, generate, generate_instructions, service) call with InMemoryIncidentStore and a ConversationReference; inspect.signature check that incidents and conversation have no default.
- AC3 -> 6 -> make check-import-contracts; rg for get_record_store in features/incident.
- AC4 -> 6 -> entry-point resolution file: success; not an incident (no item for the channel); ambiguous (two items on the channel); store failure (RecordStore stub whose query returns a transient error) each map to the localized view text; scope closed after each call.
- AC5 -> 6 -> same file: an item on the same channel under another Slack tenant is not found; the ConversationReference passed carries the configured tenant.
- AC6 -> 2, 3, 7, 8 -> api surface test asserts the names are absent; rg over app/ returns nothing; test_incident_core_incident_find.py rewritten over InMemoryIncidentStore, test_incident_core_incident_security_flag.py deleted.
- AC7 -> 4 -> test_incident_comms_status_update_security_gate.py rewritten: True refuses, False passes, failed read refuses, a legacy item without security_incident read through RecordIncidentStore passes without confirmation.
- AC8 -> 6 -> entry-point resolution file: a legacy item without record_version (lowercase status, epoch created_at) resolves and its updates show.
- AC9 -> 6 -> test_incident_comms_status_update_slack.py: Slack absent registers nothing and logs one event naming SLACK_TEAM_ID (capture_logs); Slack present registers the command and every listener; review entrypoint registration test updated for wrapped listeners.
- AC10 -> all -> ruff, mypy on touched files, every make check-* CI step, make test.

TEST MATRIX
- Happy: end-state item and legacy item resolve at the entry point; generate and save keep working through form with the store passed.
- Boundary: blank channel id is not an incident; other tenant on the same channel id is not a match; 10 candidates is ambiguous (store rule, already covered in core).
- Failure: store query failure, unreadable candidate, security read failure.
- Startup: Slack configured or not.

ASSUMPTIONS AND DOUBTS
- Incident.id from the store equals the legacy UUID the status-update records are keyed under (same incidents table, key id): checked in incident_items.py and settings default INCIDENTS_TABLE=incidents.
- The task role can Query incidents/index/by_channel: TASK-152 granted /index/* but its post-apply simulation (doc-13 next action 5) is not recorded. Verify before deploying this layer, with the incidents table index ARN added to the simulation.
- The RecordStore client is in-account like the legacy adapter: SERVICE_ROLE_MAP has no dynamodb entry in terraform.
- Bolt binds listener arguments by parameter name, so the registered closures use exactly ack, body, client.

BLAST RADIUS AND ROLLBACK
- Ships alone: the status-update command and modal actions read through the by_channel index. Wrong wiring shows the generic error in the modal; nothing is written to incident items.
- Legacy incidents without a stored security flag no longer require confirmation before an AI draft (accepted 2026-10-15).
- Rollback: one revert of the squash commit restores the scan adapter. Order: layer 8 merged first, layer 10 submitted above, TASK-152 and TASK-145.5.1 applied; TASK-24.5 waits until this deploy is checked.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented 2026-10-20 on stack-k/task-145.5.5-incident-cutover (layer 9), per the approved plan.

PRODUCTION (7 Python files, features/incident; +200/-330 with the deleted adapter)
- core/api.py: find_incident_for_conversation(store, conversation) -> OperationResult[Incident] over IncidentStore.find_by_conversation. IncidentLookup, IncidentSecurityReader, get_incident_lookup, get_incident_security_reader and the legacy imports deleted; IncidentSecurityFlag no longer exported.
- core/adapters/legacy_incidents.py and the IncidentSecurityFlag enum (core/domain.py) deleted; core/store.py docstring says the entry points build the store.
- comms/service.py and form.py: incidents (IncidentStore) and conversation (ConversationReference) are required positional parameters; lookup and security_reader parameters are gone. The security gate reads incidents.read_security_flag: False passes, True or a failed read refuses with SECURITY_CONFIRMATION_REQUIRED. StatusUpdateStore, transcript reader and generator defaults stay (TASK-145.5.6 and later).
- comms/entrypoints/slack.py: _incident_scope(scopes, channel_id) opens one service scope, resolves RecordStore and ConfiguredSystems, builds the store with build_incident_store(..., get_incident_core_settings()) and the Slack ConversationReference under the configured tenant; the command, New, Back, Save and Draft with AI handlers call their service inside it. register() reads ConfiguredSystems once through a scope; without Slack it registers nothing and logs incident_comms_registration_skipped (reason slack_not_configured, setting SLACK_TEAM_ID). Wrapped listeners keep Bolt's ack/body/client argument names. Two small helpers keep the handlers within the 35-line discipline test: _text_view and _ModalCursor.updater.
- READMEs: features/incident/README.md core row and comms/README.md updated.
- INCIDENT_RECORD_UNREADABLE shows the generic modal error (logged with its code).

TESTS
- New: tests/factories/services.py (FakeServiceScopeOpener), tests/factories/incident.py (incident_on, incident_store_with, slack_conversation, FakeConfiguredSystems, incident_scopes), test_incident_comms_status_update_entrypoint_incident_resolution.py (legacy item, end-state item, other tenant, no incident, ambiguous, store failure, scope closed).
- Rewritten: security gate tests on the bool flag, including a legacy item without security_incident drafted without confirmation; registration tests for Slack configured and not configured.
- Deleted: test_incident_core_incident_find.py and test_incident_core_incident_security_flag.py (legacy adapter tests).
- About 25 comms test files moved from local lookup and security stubs to the in-memory stores; UNKNOWN-flag cases dropped (no third state any more), failed-read cases kept.
- tests/factories/slack_bolt.py: harness_fixture takes an optional scope opener factory. The legacy-surface conftest and the access discovery test give their providers a scope opener, since comms registration now needs one (the host sets it in lifespan before registration).
- Touched-file mypy cleanups of pre-existing errors: SimpleNamespace settings and FakeSlackClient casts in slack_bolt.py and legacy_surface/conftest.py, the failing-update reply in the Slack command test built on FakeSlackReply.

GATES (2026-10-20, from app/)
- uv run ruff check . : All checks passed; ruff format --check: 981 files already formatted.
- mypy on the 40 touched Python files: 0 errors in touched files (the remaining errors are in followed modules: infrastructure/i18n, integrations/openai/settings.py, features/incident/scheduling and meet adapters).
- make check-sdk-typing, check-vendor-package-contract, check-runtime-imports, check-aws-platform-seam, check-fake-coverage: OK; make check-import-contracts: Contracts: 12 kept, 0 broken.
- make test: 4593 passed (unit + integration, 453.89s); legacy 772 passed (exit 0).
- rg over app/ finds no legacy_incidents, IncidentLookup, IncidentSecurityReader, IncidentSecurityFlag, get_incident_lookup or get_incident_security_reader; features/incident has no get_record_store import.

DEPLOY PRECONDITIONS
- Merges and deploys alone, after #1730 (layer 8) merges and with layer 10 (TASK-145.5.6) submitted above it.
- Before the deploy: TASK-152 post-apply simulation should show the task role allowed to Query <incidents table ARN>/index/by_channel (not yet recorded).
- After the deploy: open /sre incident status-update in an existing incident channel and in a non-incident channel; TASK-24.5 waits for this check. Rollback: revert the squash commit.

2026-10-20 (SLACK_TEAM_ID review, reviewer question on #1734): no code change. The cutover stamps the configured tenant onto legacy items on every read and status updates store no tenant, so nothing persisted depends on SLACK_TEAM_ID yet and a corrected value fixes every read at once. The per-request tenant check is TASK-157; the first persisting writers (TASK-145.5.7 apply, TASK-145.7) depend on it.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-19 15:26
---
Split 2026-10-19 (human) after the size gate tripped (~12 prod files, ~375-500 LOC, platform and feature): TASK-145.5.9 configured-systems read (layer 7), TASK-145.5.10 store builder (layer 8), this task the cutover (layer 9). Decisions: the new-incident policy is resolved only by the declare path (ADR amended; old AC5 policy part dropped); the entry point builds the ConversationReference (old AC8 reworded); skip events fire once at startup. Old AC9 (store built with the tenants mapping) moved to TASK-145.5.10.
---

created: 2026-10-20 15:33
---
Plan approved 2026-10-20 (human): single PR, deletions included; AC2 and AC10 reworded at planning. Branch stack-k/task-145.5.5-incident-cutover.
---
<!-- COMMENTS:END -->
