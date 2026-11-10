---
id: TASK-145.7.7
title: >-
  IncidentStore.create writes the record first; attach_conversation binds a chat
  conversation; end-state shape only; source_alert becomes a MessageReference
status: Done
assignee: []
created_date: '2026-11-09T19:06:00Z'
updated_date: '2026-11-10T18:33:00Z'
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
Stack L L5 (approved program in TASK-145.7's plan, section 2; re-planned 2026-11-10, rulings R4-R6). IncidentStore.create(incident): the record put alone (put_if_not_exists, the commit point); attach_conversation(incident_id, binding): the binding put, then for a primary binding the record's conversation copy and channel_id in one update guarded on record_version; set_reference(incident_id, kind, reference) guarded on record_version. The item carries only end-state names plus record_version 2, open_bucket and opened_at, and conversation/channel_id only while a primary chat binding exists. MessageReference gains url and replaces SourceAlertReference. Bindings are chat conversations only, zero or more per incident; the HTTP API needs none. Inert until L9a.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 create(incident) puts only the record (put_if_not_exists, the commit point) and writes no binding; a replay returns the stored incident and rewrites nothing; a same-id retry after a failed or lost write stores one record; a new-id retry after a lost write leaves an orphan open incident with no surface, matched to no conversation (the documented residual) (tested)
- [x] #2 The created item holds only end-state attribute names plus record_version 2, open_bucket and opened_at from format_stored_time (width and offset tested), and conversation/channel_id only when the incident has a conversation (checks parent ACs #5, #7)
- [x] #3 SourceAlertReference is deleted; source_alert is a MessageReference with an optional url (checks the shape part of parent AC #6)
- [x] #4 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
- [x] #5 attach_conversation(incident_id, binding) puts the binding, then for a primary binding copies conversation and channel_id into the record in one update guarded on record_version and conversation absent; repeating it is a no-op; a crash between the steps leaves a live binding the lookup follows and a retry completes; a different conversation on the record, a legacy or other-version item is INCIDENT_RECORD_CONFLICT; a missing incident NOT_AN_INCIDENT; a non-primary binding is stored without touching the record (tested)
- [x] #6 set_reference(incident_id, kind, reference) replaces one reference map whole in one update guarded on record_version == RECORD_VERSION; a legacy or other-version item is INCIDENT_RECORD_CONFLICT, a missing incident NOT_FOUND, a reference of the wrong class for the kind raises ValueError; repeating it is a no-op (tested)
- [x] #7 create refuses (ValueError, nothing written) an incident that is not open or already carries a conversation; attach_conversation refuses a binding of another incident, of a kind other than the chat conversation, or archived; an attached incident is returned by find_by_conversation through its binding on the real store and the fake (tested)
- [x] #8 InMemoryIncidentStore implements create, attach_conversation and set_reference with the same validation and classification as RecordIncidentStore (shared helpers; parity tests over both)
- [x] #9 decisions/incident-management.md states: a binding is a conversation on an enabled chat platform, the HTTP API needs none and the Backstage plugin is an API caller; zero or more bindings, at most one active primary; declare writes the record first, then attaches surfaces in retriable steps; the create and attach retry contracts and the orphan residual; conversation/channel_id only while a primary chat binding exists; the stored source_alert attributes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Stack L L5. Planned in full 2026-11-09, revised 2026-11-10 (rulings R1-R3), re-planned 2026-11-10 (rulings R4-R6, record first). Inert until L9a: nothing outside tests calls create, attach_conversation or set_reference. Sources: decisions/incident-management.md :28, :32-:40, :52, :111, :177-:180; decisions/authorization.md:12 and security.md:18 (Backstage is an HTTP caller); TASK-145.7 plan section 2 row L5; AWS DynamoDB docs (ConditionExpression); industry survey 2026-11-10 (incident.io channelless incidents and API create with idempotency_key; Rootly optional channels 2022; PagerDuty/FireHydrant/Rootly channel creation as skippable workflow steps; Netflix Dispatch record first, conversation in a background flow; Jira Service Management chat channels as a linkable list).

0. DECISIONS AND STACKING
- R1 Restack: L5 above L2b (L2a -> L2b -> L5 -> L3); deps TASK-145.7.3, TASK-145.7.4.
- R2 Constants: RECORD_VERSION (= 2) and OPEN_BUCKET imported from core/adapters/incident_items.py (L2b); L5 defines none.
- R3 source_alert: a MessageReference {system, tenant, conversation_id, message_id, url?}; the ADR names it.
- R4 Surfaces (human 2026-11-10): business features are API first. The HTTP API is always a way to work an incident and needs no binding. A binding is a conversation on an enabled chat platform (Slack; Teams later). An external portal (the Backstage plugin) is an API caller (authorization.md:12, security.md:18), never a binding; the reserved backstage_page kind is dropped from the ADR. An incident has zero or more bindings, at most one active primary. Supersedes Revision 2's "at least one working surface" and TASK-145.7 OQ9 ("declare unavailable only when no working surface can be bound").
- R5 Order (human 2026-11-10): record first, the commit point; chat surfaces attached afterwards in idempotent, retriable steps (industry pattern). Replaces ADR :34 "creates the conversation, then writes the binding, then the record".
- R6 API declare: the HTTP declare route (POST /incidents) is folded into TASK-145.7.9 with the declare service.

1. L2a/L2b CROSS-CHECK (read only)
Reused unchanged: binding_item (attach puts exactly its output), bindings_table and BINDING_* constants, RecordIncidentStore._bindings, select_active_bindings and the lookup (bindings first, by_channel fallback, a binding whose record is missing dropped), IncidentBinding, InMemoryIncidentStore.bind/seed, tests/factories/incident.py helpers, RECORD_VERSION/OPEN_BUCKET from incident_items.py.
Changed: core/domain.py, core/adapters/incident_items.py, core/store.py, core/adapters/in_memory.py, core/api.py, contracts/operations/codes.py (INCIDENT_RECORD_CONFLICT). No change to binding_items.py, the lookup, tables or terraform.

2. DESIGN
IncidentStore.create(incident: Incident) -> OperationResult[Incident]
- Caller errors raise ValueError before any write: status not OPEN; incident.conversation set (the conversation arrives only through attach_conversation, so the record copy and the binding cannot disagree).
- One put_if_not_exists(incidents, incident_item(incident)). data True: success with the incident. data False: replay, nothing rewritten, success with the stored incident (get). Failure: classified error, generic message, logged by _failed.
- incident_item writes only the record's own names (optional fields only when set), record_version RECORD_VERSION, and while open open_bucket OPEN_BUCKET and opened_at = format_stored_time(declared_at); conversation map and channel_id only when the incident has a conversation (the legacy-read and attach paths). No legacy names.
IncidentStore.attach_conversation(incident_id: str, binding: IncidentBinding) -> OperationResult[Incident]
- Caller errors raise ValueError: binding.incident_id != incident_id; kind not CHAT_CONVERSATION; archived.
- Step 1: read the record (raw). Missing -> NOT_AN_INCIDENT; record_version != RECORD_VERSION (legacy or other version) -> INCIDENT_RECORD_CONFLICT; a primary binding while the record names another conversation -> INCIDENT_RECORD_CONFLICT (moving the primary is TASK-145.8.6's). Nothing is written on any refusal, so attach leaves no dangling binding. A read failure is classified.
- Step 2: put_if_not_exists(bindings, binding_item(binding)) (False = stored by an earlier attempt: continue). A failure is classified and step 3 is not attempted.
- Step 3 (primary, record without a conversation): one update SetAttribute(conversation map) + SetAttribute(channel_id) guarded on {"record_version": RECORD_VERSION, "conversation": None}. Guard unmet -> re-read once: same conversation -> success, otherwise INCIDENT_RECORD_CONFLICT (a concurrent attach). Returns the updated incident. Same conversation already stored, or a non-primary binding: no update; returns the stored incident.
- A crash between the steps leaves a live binding on an existing record: the lookup finds the incident through the binding; a retry completes the copy.
IncidentStore.set_reference(incident_id, kind: ReferenceKind, reference) -> OperationResult[Incident]: unchanged from the first implementation (one update guarded on record_version; legacy/other version -> INCIDENT_RECORD_CONFLICT; missing -> NOT_FOUND; wrong class -> ValueError; idempotent). ReferenceKind: report, video_call, postmortem_meeting, external_case.
Shared validators in store.py (validate_new_incident, validate_attachment, validate_reference) used by the real store and the fake. The fake holds no record_version: set_reference never conflicts; attach_conversation conflicts only on a different conversation.

3. RETRY CONTRACT
- create is idempotent on the incident id: a same-id retry after a failed or lost write stores one record; a replay returns the stored record.
- attach_conversation is idempotent on (incident id, binding key): a retry stores one binding and one record copy.
- Residual, pinned by a test: a create whose write landed but whose response was lost, retried with a NEW id, leaves an orphan open incident with no surface: listed by list_open, readable through the API, matched to no conversation (no AMBIGUOUS, since only the retried incident is attached). TASK-145.7.9 derives the incident id from the declare's idempotency key (uuid5 of the surface's request id; an HTTP Idempotency-Key for POST /incidents) so retries reuse it.
- No transaction (RecordStore has none; ADR :34 "no multi-item transaction until TASK-34").

4. ORDERED STEPS
1. domain.py: MessageReference + url (moved above Incident); SourceAlertReference deleted; Incident.source_alert: MessageReference | None; ReferenceKind.
2. incident_items.py: incident_item (conversation and channel_id only when set), reference_item, message_reference_item, read_message_reference.
3. codes.py: INCIDENT_RECORD_CONFLICT.
4. store.py: Protocol create/attach_conversation/set_reference; validators; RecordIncidentStore implementations.
5. in_memory.py: fake create/attach_conversation/set_reference.
6. api.py: exports.
7. decisions/incident-management.md: :28 binding definition (chat conversation on an enabled chat platform; the API needs no binding; Backstage is an API caller); :34 zero or more bindings, record first, attach steps, retry contract and residual, failure reported (timeline entry once TASK-145.9); :40 conversation and channel_id only while a primary chat binding exists, source_alert message map, references set by guarded update; :52 core owns; :111 checks; Changes line.
8. features/incident/README.md store row.
9. Tests first (TDD), below.

5. AC TRACEABILITY
AC1 create record only, replay, residual -> steps 2, 4, 5 -> test_incident_core_incident_store_create.py. AC2 item shape -> step 2 -> test_incident_core_incident_item_write.py. AC3 SourceAlertReference -> steps 1, 2, 6. AC4 gates. AC5 attach_conversation -> step 4, 5 -> test_incident_core_incident_store_attach_conversation.py. AC6 set_reference -> test_incident_core_incident_store_set_reference.py. AC7 caller errors -> create and attach test files. AC8 fake parity -> the three store files parametrized real/fake. AC9 ADR -> step 7.

6. TEST MATRIX (app/tests/unit/features/incident/core/, pytestmark unit)
- incident_item_write: required-only and full attribute sets; no None; no legacy names; severity int; opened_at fixed width (32) and +00:00 from a non-UTC declared_at; conversation/channel_id absent without a conversation and present with one; source_alert map, url omitted when None; round trip; unreadable source_alert dropped and logged without the map.
- incident_store_create (real and fake): created incident readable, listed open, not found by any conversation; record holds record_version 2, open_bucket, no conversation, no channel_id; one put on the incidents table, nothing on bindings; failure classified with a generic message; same-id retry after failed and after lost write converges on one record; replay returns the stored incident and rewrites nothing (a reference set in between survives); new-id retry after a lost write leaves an orphan open incident (two open, neither ambiguous); ValueError for a non-open status and for an incident carrying a conversation, nothing written.
- incident_store_attach_conversation (real and fake where shared): primary attach -> find_by_conversation returns the incident, record has conversation map and channel_id, return value carries the conversation; write order bindings then incidents; repeat is a no-op; binding failure -> no record write, classified; crash after the binding put (record update fails) -> lookup finds the incident through the binding, retry completes the copy; a different conversation already on the record -> INCIDENT_RECORD_CONFLICT, nothing written, the new channel unbound; concurrent attach of another or the same conversation between read and update (guard + re-read); legacy item -> INCIDENT_RECORD_CONFLICT, nothing written; record read failure classified, nothing written; missing incident -> NOT_AN_INCIDENT, no binding left; non-primary attach -> binding stored, record unchanged, lookup through it; ValueError for id mismatch, archived binding, nothing written; another tenant's same channel not matched; guard payload names record_version and conversation absent.
- incident_store_set_reference: as implemented (each kind, replaced whole, repeat no-op, legacy and version-1 items conflict, missing NOT_FOUND, wrong class ValueError, store failure, missing table, guard payload); fixtures create then attach.
Updated: reference_types, incident_item_references, api_surface (create, attach_conversation, set_reference signatures), timeline_entry_record (url optional).

7. DOMAIN-MODEL EVOLUTION (gate)
Entities: Incident (conversation optional at create, source_alert retyped), MessageReference (+url), ReferenceKind (closed, 4), IncidentBinding (unchanged; chat kind only by R4). Scenarios: declare from Slack (record, conversation, attach); declare from the API (record only, or attach a conversation the caller chose); declare from an alert (source_alert set at create; the alert channel not bound); coordinated parent or child without its own conversation (record only); crash between record and attach (incident reachable through the API, retried); crash inside attach (live binding, record copy retried); two incidents on one channel (data allows, lookup fails closed, attach refuses moving a primary); Teams later (same kind, another system); Backstage (API caller, no binding). Cardinality: bindings 0..n, active primary 0..1, record conversation copy 0..1 (the primary's), source_alert 0..1. Compatibility: legacy items still read with their channel; no stored source_alert exists; additive url.

8. ASSUMPTIONS AND DOUBTS
- by_conversation and by_channel are eventually consistent GSIs: callers hold the Incident attach returns.
- The records contract's equality guard with a None value means "attribute absent" (contracts/records/store.py docstring); tested on InMemoryRecordStore.
- TASK-145.7.9 follows R5/R6 (record, conversation, attach, resources; HTTP route; idempotency-derived id).
- Nothing else implements IncidentStore (rg: the real store and the fake).

9. BLAST RADIUS AND ROLLBACK
Inert; no caller outside tests, no registration, terraform or settings. One git revert. Ordering: after L2b; the bindings table (L0) is live.

10. SIZE GATE
Production: domain.py (~25), incident_items.py (~95), store.py (~200), in_memory.py (~55), api.py (~4), codes.py (1) = measured 412 added and 32 removed lines against L2b, docstrings included (about 300 without them), 6 files plus the README row, 1 subsystem, no mechanical refactor. At the ~400 line; kept as one PR because the three writes share the validators and the item writer and splitting would leave an inert half.
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

2026-11-10 re-implementation (rulings R4-R6, record first), on top of acf0e20f (the first implementation, already committed and in PR #1845). TDD: red run recorded first (tests/unit/features/incident/core: 31 failed, 34 errors), then green.
- store.py: create(incident) puts the record only (validate_new_incident: open, no conversation); attach_conversation(incident_id, binding) reads the raw record first (missing NOT_AN_INCIDENT; not RECORD_VERSION or a primary while another conversation is stored INCIDENT_RECORD_CONFLICT; nothing written on refusal), puts the binding, then for a primary on a record without a conversation one update guarded on record_version and conversation absent, re-read once when the guard fails; validate_attachment; _end_state_record and _conflict helpers; set_reference unchanged.
- incident_items.py: incident_item writes conversation/channel_id only when the incident has a conversation (no longer raises).
- in_memory.py: fake create/attach_conversation with the shared validators.
- ADR decisions/incident-management.md: Binding vocabulary (chat conversation on an enabled chat platform; API needs no binding; Backstage plugin is an API caller), Bindings (zero or more, record first, attach steps, retry contracts, orphan residual, industry sources), Stored form, core owns, Checks, Changes line rewritten. README store row.
- Tests: create rewritten, attach_conversation new (incl. concurrent attach via a guard spy, legacy, read failure), set_reference fixtures on create(incident), item_write (no-surface item), api_surface signatures; factories: declared_incident, FlakyRecordStore fail_updates.
Gates (from app/): ruff clean, format clean; lint-imports 13 kept 0 broken; package shape OK (3 baselined); test seams OK (47 + 12); fake coverage OK (4 baselined); mypy 41 errors in 14 files, all pre-existing, none in features/incident/core or contracts (new test files and factories also type-check: no issues in 4 files); pytest tests --ignore=tests/smoke 6854 passed.
Scope changes recorded the same session: TASK-145.7 (cardinality 0..n, OQ9 superseded), TASK-145.7.9 (AC #1 record first; AC #4 HTTP declare route), TASK-145.7.10 (record-first cutover), TASK-145.8.6 (AC: moving the primary), TASK-165.5 (AC #2 zero or more chat bindings).
The task file name still carries the old title; rename with git mv (human).
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

created: 2026-11-10T16:05:00Z

---

Re-plan approved by the human 2026-11-10 (rulings R4-R6 in plan section 0: API-first, bindings are chat conversations only, zero or more; record first; HTTP declare folded into TASK-145.7.9). The first implementation (binding then record) is reworked on the same branch before any commit.

---
<!-- COMMENTS:END -->
