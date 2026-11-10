---
id: TASK-145.7.7
title: >-
  IncidentStore.create writes the binding then the record, end-state shape only;
  source_alert becomes a MessageReference
status: In Progress
assignee: []
created_date: '2026-11-09T19:06:00Z'
updated_date: '2026-11-10T15:27:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-145.7.3
  - TASK-145.7.4
references:
  - decisions/incident-management.md
parent_task_id: TASK-145.7
priority: medium
type: feature
ordinal: 505000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L5 (approved program in TASK-145.7's plan, section 2; outline in the parent plan). IncidentStore.create(incident, binding): binding put, then record put (both put_if_not_exists; the record is the commit point); set_reference(incident_id, kind, reference) guarded on record_version; the item carries only end-state names plus channel_id, record_version 2, open_bucket and opened_at in the same put; MessageReference gains url and replaces SourceAlertReference. Inert until L9a.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 create writes the binding before the record; a replay is a no-op; a record failure leaves a dangling binding that the lookup ignores, and a retry with a new incident id resolves to the new incident, not AMBIGUOUS (tested)
- [x] #2 The created item holds only end-state attribute names plus channel_id, record_version 2, open_bucket and opened_at from format_stored_time (width and offset tested) (checks parent ACs #5, #7)
- [x] #3 SourceAlertReference is deleted; source_alert is a MessageReference with an optional url (checks the shape part of parent AC #6)
- [x] #4 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
- [x] #5 A retry of create with the same incident id after a failed or lost record write writes no second binding and stores one record; a replay returns the stored incident and rewrites nothing; a record write that landed but reported an error followed by a retry with a new id is AMBIGUOUS_INCIDENT_CONVERSATION (the documented fail-closed residual) (tested)
- [x] #6 set_reference(incident_id, kind, reference) replaces one reference map whole in one update guarded on record_version == RECORD_VERSION; a legacy or other-version item is INCIDENT_RECORD_CONFLICT, a missing incident NOT_FOUND, a reference of the wrong class for the kind raises ValueError; repeating it is a no-op (tested)
- [x] #7 create refuses (ValueError, nothing written) an incident that is not open or has no conversation, and a binding that is not the primary chat binding of that incident's conversation; a created incident is returned by find_by_conversation through its binding on the real store and the fake (tested)
- [x] #8 InMemoryIncidentStore implements create and set_reference with the same validation and classification as RecordIncidentStore (shared helpers; parity tests over both)
- [x] #9 decisions/incident-management.md states create's retry contract (idempotent on the incident id; a new-id retry leaves a dangling binding; the lost-response residual) and the stored source_alert attributes (conversation_id, message_id, url)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Stack L L5, planned in full 2026-11-09, revised 2026-11-10 with the human rulings below. Planned against the working tree at ae941c56 (L2a, PR #1842). Inert until L9a: nothing outside tests calls create or set_reference. Sources: decisions/incident-management.md :32-:40 (record, Bindings, Stored form), :136-:142 (Migration), :177-:178 (A1); TASK-145.7 plan section 2 row L5, OQ6/OQ9; doc-16 row L5; decisions/reliability.md; AWS DynamoDB docs (ConditionExpression, TransactWriteItems).

0. DECISIONS (human rulings 2026-11-10) AND STACKING
- R1 Restack: L5 stacks above L2b: L2a -> L2b -> L5 -> L3. Task dependencies are TASK-145.7.3,TASK-145.7.4. L5's branch stack-l/task-145.7.7-incident-create is added above L2b's branch (gh stack add). Reason: create stamps record_version 2 and set_reference guards on it; today core/store.py:79 has RECORD_VERSION = 1 and legacy_upgrade.py:233 stamps it on items without a binding, so the value belongs to L2b.
- R2 Constants: per TASK-145.7.4's OQ1 ruling, END_STATE_VERSION, RECORD_VERSION (= 2) and OPEN_BUCKET move to core/adapters/incident_items.py, and plan_item_upgrade to core/adapters/item_upgrade.py, both in L2b. L5 imports RECORD_VERSION and OPEN_BUCKET from incident_items.py (where its item writers live); L5 makes no edit to the store.py constants and defines none.
- R3 source_alert: a message-shaped MessageReference {system, tenant, conversation_id, message_id, url?} is accepted; the ADR names it as written (AC #9).

1. L2a CROSS-CHECK (git show ae941c56, read only)
Reused unchanged:
- binding_item(binding) (core/adapters/binding_items.py): create puts exactly its output. It writes incident_id and binding_key (the table's key attributes), omits url/archived_at when unset and writes conversation_id only for the chat kind, so the by_conversation index sees the item. binding_key is not called by create; tests use it to assert the stored key.
- bindings_table and BINDING_* constants (store.py:103), RecordIncidentStore._bindings (required keyword `bindings`, store.py:173), the record store's put_if_not_exists.
- select_active_bindings and the lookup (store.py:192-236): a created incident is found by find_by_conversation through its binding; unchanged. The record also carries channel_id and the conversation map, so the by_channel fallback agrees; it is read only when no live binding exists (store.py:232), so the two never double-count.
- Dangling bindings dropped before the ambiguity rule (store.py:225-236): the new-id-retry AC rests on it.
- IncidentBinding and its __post_init__ (domain.py): create validates further but does not change it.
- InMemoryIncidentStore.bind/seed and its find_by_conversation (in_memory.py:108-155): kept for seeding and for dangling bindings in tests; create is built on the same _bindings/_incidents dicts.
- tests/factories/incident.py: incident_on, binding_on, record_incident_store, CountingRecordStore reused; FlakyRecordStore added.
Changed:
- core/store.py: IncidentStore Protocol gains create and set_reference; RecordIncidentStore implements them; shared module-level validate_new_incident(incident, binding) (like select_active_bindings, so the real store and the fake cannot drift).
- core/domain.py: MessageReference gains url; SourceAlertReference deleted; Incident.source_alert is MessageReference | None; ReferenceKind added.
- core/adapters/incident_items.py: incident_item(), reference writers, a message-reference reader replacing the SourceAlertReference read (:89); imports its own RECORD_VERSION/OPEN_BUCKET (L2b).
- core/adapters/in_memory.py: create/set_reference on the fake.
- core/api.py: exports (SourceAlertReference out, ReferenceKind in).
- contracts/operations/codes.py: INCIDENT_RECORD_CONFLICT (one reviewed line).
No change to binding_items.py, select_active_bindings, the lookup, the tables or terraform.

2. DESIGN
IncidentStore.create(incident: Incident, binding: IncidentBinding) -> OperationResult[Incident]
- Caller errors raise ValueError before any write (as StatusUpdateStore.transition does): status not OPEN; no conversation; binding.incident_id != incident.id; binding not CHAT_CONVERSATION, not primary or archived; binding (system, tenant, vendor_id) differs from incident.conversation. This makes "a created incident is found by find_by_conversation" true by construction. The Protocol docstring (store.py:119-131, "Nothing raises") says so.
- Order: (1) put_if_not_exists(bindings, binding_item(binding)); (2) put_if_not_exists(incidents, item). The record is the commit point. A failed step 1 is a classified error and step 2 is not attempted. A failed step 2 is a classified error (generic message; the store's status/error_code/retry_after; logged by _failed) and leaves the binding.
- put_if_not_exists data False on the binding means this incident's own binding from an earlier attempt (key = incident_id + binding_key): continue. data False on the record means the id already has a record: replay no-op, nothing rewritten, success with the stored incident via get.
- Item = incident_item(incident), which also sets, in the same put, record_version: RECORD_VERSION, open_bucket: OPEN_BUCKET and opened_at: format_stored_time(incident.declared_at) (opened_at = declared_at as in the legacy plan). incident_item is pure and writes only the record's own names: id, title, status, declared_by, declared_at, security_incident, optional product/severity (int)/detected_at/impact_started_at/impact_ended_at/five roles when set, each reference as its map, channel_id = conversation.vendor_id. No legacy names (name, user_id, teams, created_at, report_url, channel_name).
- References: ResourceReference kinds -> {system, tenant, vendor_id, url?}; source_alert (MessageReference) -> {system, tenant, conversation_id, message_id, url?}. MessageReference gains url: str | None = None. read_message_reference mirrors read_reference: optional, unreadable => dropped and logged, never logging the map.
IncidentStore.set_reference(incident_id, kind: ReferenceKind, reference) -> OperationResult[Incident]
- ReferenceKind: REPORT, VIDEO_CALL, POSTMORTEM_MEETING, EXTERNAL_CASE (value = stored attribute). conversation and source_alert are set only in create's put (a recreated channel never moves the conversation, TASK-145.7 section 5).
- One records.update(SetAttribute(kind, map), expected={"record_version": RECORD_VERSION}); the map is replaced whole. Guard unmet (legacy item or other version) => PERMANENT_ERROR INCIDENT_RECORD_CONFLICT; missing item => NOT_FOUND NOT_AN_INCIDENT; success returns the updated Incident parsed from the update's full item. Wrong class for the kind raises ValueError. Idempotent: the guard holds after the write, so an SDK retry or replay re-applies the same map.
- Fake: set_reference replaces the field with dataclasses.replace; it holds no version (documented).

3. RETRY AND INCIDENT-ID ANSWER (AC #1)
create does not generate ids; it is idempotent on the id it is given:
(a) Same id (in-process retry of a transient failure, or Slack redelivery when 145.7.9 derives the id from the claim): binding put -> False (exists), record put -> True; exactly one binding and one record. A full replay (both exist) is a no-op returning the stored record.
(b) New id after a failed record write: the first binding is dangling and invisible (record missing, dropped before the ambiguity rule); the new binding and record resolve; find_by_conversation answers the new incident, not AMBIGUOUS. The dangling binding stays (never deleted, ADR :34/:178).
Residual, pinned by a test: a record put that LANDED but whose response was lost past the SDK retries (put_if_not_exists resolves its own SDK retry via _rs_write_token, infrastructure/records/service.py:238-289) returns an error; a retry with a NEW id then leaves two live records => AMBIGUOUS_INCIDENT_CONVERSATION, fail closed (ADR :34). Same-id retry converges. Handoff to TASK-145.7.9's plan: retry create with the same id within one declare and derive the id from the declare's idempotency id (uuid5 of the claim id; ADR :32 allows an app-generated opaque id) so a redelivery reuses it.
Why not TransactWriteItems (AWS API reference): atomic across tables in one account and region, up to 100 actions, no two on the same item; ClientRequestToken makes it idempotent for 10 minutes (different payload with the same token => IdempotentParameterMismatch). It would remove the dangling binding, but the RecordStore contract has no transaction method (contracts/records/store.py:229-297); adding one touches contracts, infrastructure/records and the portability ports (another subsystem, size-gate breach), and ADR :34 says "no multi-item transaction until TASK-34". ConditionExpression attribute_not_exists on a composite-key table is evaluated against the item with that full key (AWS developer guide, Conditional put), so the binding put cannot overwrite an existing binding. Revisit when a transaction method exists.

4. ORDERED STEPS
1. core/domain.py: MessageReference + url; delete SourceAlertReference; Incident.source_alert: MessageReference | None; ReferenceKind(StrEnum).
2. core/adapters/incident_items.py: drop the SourceAlertReference import and read (:34, :89), read source_alert with read_message_reference; add incident_item, reference_item, message_reference_item (importing the module's own RECORD_VERSION/OPEN_BUCKET from L2b).
3. contracts/operations/codes.py: INCIDENT_RECORD_CONFLICT.
4. core/store.py: Protocol create/set_reference (the "Writes arrive with their slices" paragraph updated); validate_new_incident and reference_attribute helpers; RecordIncidentStore.create/set_reference; import RECORD_VERSION from incident_items.py for the guard. No constant is edited.
5. core/adapters/in_memory.py: create/set_reference using the same helpers and dicts.
6. core/api.py: __all__ and imports.
7. decisions/incident-management.md (rides with this PR): :34 gains the create contract (idempotent on the incident id; same-id retry converges; new-id retry leaves a dangling binding; lost-response residual fails closed); :40 names the source_alert attributes (conversation_id, message_id, url) as written in R3; one dated Changes line.
8. Tests first (TDD), below; tests/factories/incident.py gains FlakyRecordStore (fail a named table's put_if_not_exists N times, optionally after the write lands).

5. AC TRACEABILITY
AC1 (order, replay no-op, dangling, new-id retry) -> steps 4, 5 -> test_incident_core_incident_store_create.py.
AC2 (end-state names, record_version 2, open_bucket, opened_at width/offset) -> steps 2, 4 -> test_incident_core_incident_item_write.py, ..._store_create.py.
AC3 -> steps 1, 2, 6 -> test_incident_core_reference_types.py, test_incident_core_incident_item_references.py, test_incident_core_api_surface.py.
AC4 gates -> all steps.
AC5 (same-id retry, replay, residual) -> steps 4, 5 -> ..._store_create.py.
AC6 (set_reference) -> steps 3, 4, 5 -> test_incident_core_incident_store_set_reference.py.
AC7 (validation, found by lookup) -> step 4 -> ..._store_create.py.
AC8 (fake parity) -> step 5 -> the two store test files parametrized real/fake.
AC9 (ADR) -> step 7 (review).
Every step maps to an AC; step 3 is enabling work for AC6.

6. TEST MATRIX (app/tests/unit/features/incident/core/, pytestmark unit)
test_incident_core_incident_item_write.py: stored attribute set == expected end-state names for a full and a minimal incident (optionals absent, no None); no legacy names; severity stored as int; opened_at == declared_at, fixed width (32 chars) and +00:00 offset for a non-UTC declared_at; round trip parse_incident_item(incident_item(x)) == x for every reference kind; source_alert map keys, url omitted when None; unreadable stored source_alert dropped and logged without the map.
test_incident_core_incident_store_create.py (real store over InMemoryRecordStore and the fake where shared):
- happy: both items stored, record_version == 2 (literal and == RECORD_VERSION), open_bucket "OPEN", channel_id, conversation map; list_open returns it; find_by_conversation returns it (bindings path) and the by_channel path agrees.
- order: recorded (table, operation) sequence is bindings then incidents; binding failure => no incident put attempted, classified error with generic message.
- record failure: error returned, binding stays, find_by_conversation => NOT_FOUND NOT_AN_INCIDENT (no AMBIGUOUS).
- new-id retry after record failure: succeeds; lookup returns the new incident; two bindings exist, one live.
- same-id retry after record failure: one binding, one record, success.
- full replay: second identical create is a no-op success, stored item unchanged (and returns the updated incident after a set_reference in between).
- lost response (record lands, call reports error): same-id retry converges; new-id retry => AMBIGUOUS_INCIDENT_CONVERSATION (pins the residual).
- validation: ValueError for non-open status, no conversation, id mismatch, non-primary, archived, other kind, binding place differing from the conversation (system, tenant, vendor_id each); nothing written.
- tenant: same channel id under another tenant is not matched.
test_incident_core_incident_store_set_reference.py: each kind sets its map and returns the updated incident; replaced whole (old url gone); same value twice is a no-op; legacy item (no record_version) => INCIDENT_RECORD_CONFLICT and unchanged; missing incident => NOT_FOUND; wrong class for kind => ValueError; store failure classified; guard payload is {"record_version": RECORD_VERSION}; fake parity for success/missing.
Updated: test_incident_core_reference_types.py, test_incident_core_incident_item_references.py, test_incident_core_api_surface.py, test_incident_core_incident_record.py, test_incident_core_timeline_entry_record.py (url optional).
Authorization not applicable (no caller identity at this layer); idempotency is the retry set above.

7. DOMAIN-MODEL EVOLUTION (gate)
Entities: Incident (source_alert retyped), MessageReference (optional url), ReferenceKind (new, closed set of 4), IncidentBinding (L2a, unchanged). Scenarios (TASK-145.7 plan section 3, 1-2, 5, 10): declare from Slack (primary binding + record); declare from an alert (source_alert = message in the alert channel, alert channel NOT bound, two incidents from one alert allowed: create does not dedupe on source_alert); two incidents on one channel (data allows it, lookup fails closed, create cannot cause it); crash between puts (dangling); replay (no-op); Backstage-only, Teams, rebind: not built (create requires a chat conversation binding). Cardinality: one record, one primary active binding per create, 0..1 source_alert. Edge cases: blank or '#' vendor ids rejected by IncidentBinding; naive times rejected; url an optional hint, never parsed. Compatibility/cascade: no stored source_alert exists (legacy_items.py maps none); an old-shape map would be dropped as an unreadable optional and logged. MessageReference.url is additive (TimelineEntry has no stored form yet). Consumers of SourceAlertReference: incident_items.py:34/:89, api.py:48/:86, domain.py:206/:264 and four tests; all in this PR. TimelineEntry.source_message already uses MessageReference, so no second message type.

8. ASSUMPTIONS AND DOUBTS (with checks)
- L2b lands RECORD_VERSION = 2, END_STATE_VERSION and OPEN_BUCKET in core/adapters/incident_items.py before L5 (R1/R2); verify on the L2b branch; tests import the constant and also assert the literal 2.
- by_conversation and by_channel are eventually consistent GSIs (RecordStore docstring): a lookup right after create may briefly miss on AWS; callers hold the Incident create returns. Verify no 145.7.9 step looks the incident up by conversation right after create.
- InMemoryRecordStore and the real service treat put_if_not_exists the same for composite keys (service.py:238-289, in_memory.py:106); the create tests include a composite-key replay case.
- 145.7.9 retries create with the same id (handoff above).
- Callers pass tenant-verified references (L9a); create cross-checks binding vs conversation.
- Nothing else implements IncidentStore (rg finds only the real store and the fake).

9. BLAST RADIUS AND ROLLBACK
Inert: no caller outside tests; no registration, terraform or settings. One git revert restores the tree; L5 writes no production data. Ordering: after L2b (constants in incident_items.py); the bindings table (L0) must be live before L9a calls create, not before L5 merges.

10. SIZE GATE
Production: domain.py (~25), incident_items.py (~90), store.py (~110), in_memory.py (~50), api.py (~4), codes.py (1) = ~280 LOC, 6 files, 1 subsystem (the error-code line is a registry entry). ADR text excluded. No mechanical refactor mixed in. Verdict: passes the gate (program table row L5 ~280 / 6); no decomposition. The R2 move trims store.py by a few lines and adds none elsewhere.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-09 (TASK-145.7.3 approval, R1): AC #1 gains the retry case: a crashed declare leaves a dangling binding, a retry with a new incident id adds a live one on the same conversation; the lookup drops the dangling one before the ambiguity rule (incident-management.md :34, revised in 145.7.3). The plan states whether the retry reuses the incident id.

2026-11-10 implementation (L5, stack-l/task-145.7.7-incident-create above L2b #1844). TDD: red run recorded first (the three new test files failed collection on missing incident_item/ReferenceKind; api_surface and timeline url tests failed), then green.
- domain.py: SourceAlertReference deleted; MessageReference gains url and moves above Incident; Incident.source_alert is MessageReference | None; ReferenceKind (report, video_call, postmortem_meeting, external_case).
- adapters/incident_items.py: incident_item (end-state names only, channel_id, record_version RECORD_VERSION, open_bucket/opened_at while open; ValueError without a conversation), reference_item, message_reference_item, read_message_reference (unreadable map dropped and logged without the map).
- store.py: IncidentStore.create/set_reference; RecordIncidentStore.create (binding put, then record put; data False on the record = replay, returns get), set_reference (one SetAttribute guarded on record_version; guard unmet = INCIDENT_RECORD_CONFLICT; NOT_FOUND without a code = NOT_AN_INCIDENT; with a code = store failure); shared validate_new_incident and validate_reference (explicit kind->type map), record_conflict.
- adapters/in_memory.py: fake create/set_reference over the shared validators (no version, never conflicts).
- contracts/operations/codes.py: INCIDENT_RECORD_CONFLICT. api.py: ReferenceKind exported, SourceAlertReference removed.
- decisions/incident-management.md (Bindings and Stored form paragraphs, Changes line) and features/incident/README.md (store row).
- Tests: new test_incident_core_incident_item_write.py, _incident_store_create.py, _incident_store_set_reference.py; FlakyRecordStore in tests/factories/incident.py; updated reference_types, incident_item_references, api_surface (store signatures incl. create/set_reference), timeline_entry_record.
Gates (from app/): ruff clean, format clean; lint-imports 13 kept 0 broken; make check-package-shape OK (3 baselined); make check-test-seams OK (47 + 12 baselined); make check-fake-coverage OK (4 baselined); mypy first run 54 (13 new, all in_memory.py:197 replace(**dict)), fixed, rerun 41 errors in 14 files, all pre-existing, none in touched files; pytest tests --ignore=tests/smoke 6843 passed. After the full run one test was added (record_version 1 conflict, AC #6) and two test-only typing fixes; tests/unit/features/incident/core rerun 1012 passed (mypy excludes tests/).
Handoff for TASK-145.7.9: retry create with the same incident id within one declare; derive the id from the declare's idempotency id.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-09T22:46:00Z

---

Planning 2026-11-09 (L5). (1) Proposed, not applied: add --dep TASK-145.7.4 (L2b). create stamps record_version 2 and set_reference guards on it, but core/store.py:79 still has RECORD_VERSION = 1 and legacy_upgrade.py:233 stamps it on legacy items without a binding; L2b owns END_STATE_VERSION = 1 / RECORD_VERSION = 2. Stack order L2a -> L2b -> L5 -> L3. doc-16 row L5 and doc-11 row 18.L5 'waits on' change from 145.7.3 to 145.7.4. (2) AC #4 is read as also requiring make check-fake-coverage to be unaffected (the fake gains methods only). (3) AC #1 retry case: create is idempotent on the id it is given; new-id retry resolves to the new incident (dangling binding dropped), same-id retry converges; see plan section 3. (4) Handoff for TASK-145.7.9's plan: retry create with the same incident id within one declare and derive the id from the declare's idempotency id so a redelivery reuses it.

---

created: 2026-11-10T15:15:00Z

---

Plan approved by the human 2026-11-10 as written (rulings R1-R3 in plan section 0). Implementation starts on stack-l/task-145.7.7-incident-create above L2b (#1844).

---
<!-- COMMENTS:END -->
