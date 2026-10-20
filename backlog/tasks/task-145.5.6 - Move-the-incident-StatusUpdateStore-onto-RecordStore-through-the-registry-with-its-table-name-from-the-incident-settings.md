---
id: TASK-145.5.6
title: >-
  Move the incident StatusUpdateStore onto RecordStore through the registry,
  with its table name from the incident settings
status: Done
assignee: []
created_date: '2026-10-14 23:09'
updated_date: '2026-10-20 17:30'
labels:
  - incident
  - features
  - records
dependencies:
  - TASK-145.5.5
references:
  - app/features/incident/core/adapters/status_updates.py
  - decisions/cloud-portability.md
  - decisions/dependency-injection.md
  - 'https://github.com/cds-snc/sre-bot/issues/1695'
parent_task_id: TASK-145.5
priority: medium
type: task
ordinal: 392000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 10 of Stack K (handoff doc-13). Behaviour-preserving for users. After TASK-145.5.5 the status-update store is the last incident store on get_aws_client: core/adapters/status_updates.py, with the table name hard-coded as sre_bot_incident_status_updates, built by the cached provider get_status_update_store in core/api.py. TASK-145's assumption that TASK-108 and TASK-109 would swap its inside for the records contract was never owned by a task (found 2026-10-14).

THIS SLICE
- The status-update store is rebuilt over RecordStore in core/store.py beside IncidentStore: the StatusUpdateStore Protocol moves there from core/api.py (re-exported by api.py), with RecordStatusUpdateStore and a status_updates RecordTable (PK partition, SK sort, as provisioned). append uses put_if_not_exists; transition(update, *, expected_state) uses the expected-guard update (TASK-27.2) on the stored state. Caller-visible item layout unchanged; core/adapters/status_updates.py keeps only the pure item conversion, as incident_items.py does for incidents.
- The table name comes from the incident core settings (TASK-145.5.3), with the provisioned table as default.
- Comms Slack entry points resolve RecordStore through the ServiceScopeOpener and pass the store built by build_status_update_store in core/api.py, as TASK-145.5.5 does for IncidentStore; get_status_update_store and every store=None fallback in the comms services are deleted (decisions/dependency-injection.md: resolve then pass).
- InMemoryStatusUpdateStore stays as the consumer fake, and the Stubber tests move to InMemoryRecordStore-backed tests with the same behavioural cases.
- TASK-140.11 (periodic drafting: a PERIODIC item in the same partition and a sparse GSI) builds on the new store and its shared RecordTable.

DECISIONS (human, 2026-10-20, checked against the ADRs and doc-11)
- Replay semantics follow the records contract and decisions/reliability.md (duplicates are absorbed by handler-level idempotency, not by store-side equality checks): an append at a taken sequence is a conflict even with identical content (the store's own SDK retry is resolved by put_if_not_exists); a transition whose guard no longer holds is a conflict, also after a lost-response retry. The comms callers already re-read once after a conflict and treat an identical winner or the target state as success, so user-visible behaviour is unchanged. Same rule as IncidentStore.update_field (TASK-145.8). The Protocol docstring and the fake change to match.
- The records contract docstring gains one sentence: a guarded set retried after a lost response reports the guard unmet.
- Every store over the records contract in incident core lives in core/store.py (decisions/feature-packages.md layout: one store.py per package; the TASK-114 shape check enforces the table), not one module per store.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The status-update store is implemented over RecordStore in core/store.py (status_updates RecordTable: PK partition, SK sort) with the same caller-visible item layout, append through put_if_not_exists and transition guarded on the expected stored state through the expected-guard update; no module in core/ imports an AWS client or botocore
- [x] #2 Its table name comes from IncidentCoreSettings.STATUS_UPDATES_TABLE (INCIDENT_CORE__STATUS_UPDATES_TABLE) with sre_bot_incident_status_updates as the default; the module-level table constant is gone
- [x] #3 Every comms Slack handler that reaches the store resolves RecordStore through the ServiceScopeOpener and passes build_status_update_store(...) to the services; get_status_update_store and every store=None fallback are removed
- [x] #4 The status-update behaviour tests run against InMemoryRecordStore with every behavioural case kept, plus conditional-create-lost, guard-lost, missing-record and replay-is-conflict cases
- [x] #5 The StatusUpdateStore Protocol docstring, the in-memory fake and the records contract docstring state the conflict semantics: an append at a taken sequence and a transition whose guard no longer holds are conflicts, also on a retry
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Approved 2026-10-20 (size gate: about 9 production files plus 2 READMEs, about +240/-250 production LOC, one subsystem, no Terraform; passes as one PR, a split would leave the old provider live with the new store unused).

1. Failing tests first:
   - tests/unit/features/incident/core/test_incident_core_status_update_record_store.py: RecordStatusUpdateStore over InMemoryRecordStore. append creates; append at a taken sequence (identical or different) is STATUS_UPDATE_CONFLICT; latest is empty-success and returns the highest sequence; list_for_incident is newest first and scoped to the incident (a non-UPDATE# item in the partition is ignored); transition applies only in the expected state; guard lost and missing record are conflicts; an illegal transition raises ValueError before any write; unpublish removes published_at and published_by; optional attributes round-trip; a malformed item is STATUS_UPDATE_UNREADABLE; a failing RecordStore stub passes status, error code and retry hint through with the generic message, and NOT_FOUND on a query is PERMANENT_ERROR.
   - Settings test: INCIDENT_CORE__STATUS_UPDATES_TABLE default, override, blank rejected.
   - core api surface test: build_status_update_store(records, settings) builds the records-backed store on the configured table; get_status_update_store is gone from the exported names.
   - Fake test: InMemoryStatusUpdateStore reports an identical append and a replayed transition as conflicts.
2. common/settings.py: STATUS_UPDATES_TABLE on IncidentCoreSettings (alias INCIDENT_CORE__STATUS_UPDATES_TABLE, default sre_bot_incident_status_updates, same blank validator).
3. core/store.py: move the StatusUpdateStore Protocol from core/api.py (docstring states the conflict semantics); add status_updates_table(name) (KeySchema PK, SK) and RecordStatusUpdateStore(records, table): append via put_if_not_exists, transition via _check_transition then update with SetAttribute and RemoveAttribute changes and expected={"state": ...}, latest and list_for_incident via RecordQuery (BEGINS_WITH UPDATE#, DESC, limit 1 for latest). Structured logs carry incident_id, sequence, operation and table.
4. core/adapters/status_updates.py: reduced to the pure plain-dict item conversion (to_item, from_item, unreadable error); botocore, get_aws_client, classify_aws_error, the table constant and build_status_update_store deleted.
5. core/api.py: build_status_update_store(records, settings) beside build_incident_store; get_status_update_store, its __all__ entry and docstring text deleted; StatusUpdateStore re-exported. core/adapters/in_memory.py: identical append and replayed transition are conflicts, docstring aligned.
6. contracts/records/store.py: one docstring sentence on update (a guarded set retried after a lost response reports the guard unmet; callers re-read).
7. comms service.py, approval.py, history.py (and form.py pass-through): store becomes a required keyword argument; fallbacks and "core's by default" docstrings removed.
8. comms/entrypoints/slack.py: the scope yields the built status-update store with the incident store and conversation; handle_open_action, handle_published_action and handle_review_submission (and handle_review_action if it reaches the store) are wrapped with _with_scopes; every store-using handler passes store=.
9. Tests: delete test_incident_core_status_update_store.py (Stubber; wire cases covered by the records conformance suite) and the provider-cache test; entry-point and dispatch tests seed updates through incident_scopes and drop the get_status_update_store monkeypatch; service tests pass store= explicitly.
10. Docs: features/incident/README.md core row and comms/README.md store line; status-update module docstrings. TASK-140.11 description: replace the stale legacy_incidents.py reference with IncidentStore (CLI).
11. Gates: every make check-* CI step and make test from app/; rg for function-level imports, __import__ and importlib; rg that no core/ module imports integrations.aws or botocore.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented 2026-10-20 on stack-k/task-145.5.6-status-update-store (layer 10), on top of layer 9.

- core/store.py: StatusUpdateStore Protocol (moved from api.py, re-exported), status_updates_table (PK, SK) and RecordStatusUpdateStore: append via put_if_not_exists, transition via update with SetAttribute/RemoveAttribute changes guarded on expected={state}, latest and list via a DESC BEGINS_WITH UPDATE# query, so non-update items in the partition (TASK-140.11 PERIODIC) are skipped.
- core/adapters/status_updates.py reduced to the pure item layout (same attribute names and types as the provisioned items; strings are type-checked on read). No core/ module imports integrations.aws, botocore or boto3 (rg).
- Records contract gap handled: update reports NOT_FOUND both for a missing item (no error code) and a missing table (backend error code); the store treats only the code-less one as a conflict, a missing table stays PERMANENT_ERROR (tested). One docstring sentence added to contracts/records/store.py on guarded-update retries.
- IncidentCoreSettings.STATUS_UPDATES_TABLE (INCIDENT_CORE__STATUS_UPDATES_TABLE, default sre_bot_incident_status_updates).
- core/api.py: build_status_update_store(records, settings); get_status_update_store deleted. comms services take store as a required keyword; slack.py builds the store in the scope for all nine listeners (review, open, published and the approval submission newly scoped).
- Fake: identical append and repeated transition are conflicts; comms service behaviour unchanged (callers re-read). No service-level test changed its expected result.
- Tests: Stubber file deleted; new test_incident_core_status_update_record_store.py (InMemoryRecordStore) and test_incident_core_api_build_status_update_store.py; comms entry-point and dispatch tests seed through incident_scopes(records) with tests/factories/incident.py::status_update_store_in and CountingRecordStore.
- Docs: incident README core row, comms README diagram; TASK-140.11 stale legacy_incidents reference replaced.

Gates (2026-10-20, from app/): make check-sdk-typing, check-vendor-package-contract, check-aws-platform-seam, check-runtime-imports, check-import-contracts (12 kept, 0 broken), check-fake-coverage all OK; ruff check and format clean; make test 4600 passed + 772 passed; mypy repo-wide 48 errors in 19 files, 0 in touched files.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-15 20:07
---
TASK-103 (2026-10-15): put_if_not_exists stamps a hidden _rs_write_token attribute (~45 bytes) on every item it writes and strips it from every read; read 'item layout unchanged' as the caller-visible attributes. Two concurrent writers of identical content now get one created and one conflict (today's equality check reports both as success); the replay of one caller's own write still reports created.
---

created: 2026-10-20 16:51
---
Plan approved by human 2026-10-20: Q1 identical append is a conflict, Q2 callers re-read after a lost guard, Q3 store required, Q4 stores in core/store.py (one store.py per package per decisions/feature-packages.md, not one module per store).
---
<!-- COMMENTS:END -->
