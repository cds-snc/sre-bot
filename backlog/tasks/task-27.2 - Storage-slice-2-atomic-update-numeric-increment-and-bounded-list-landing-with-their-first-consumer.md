---
id: TASK-27.2
title: >-
  Records slice 2: atomic change-set update with an optional expected guard
  (set, remove, increment)
status: To Do
assignee: []
created_date: '2026-09-16 13:58'
updated_date: '2026-10-13 20:00'
labels:
  - infrastructure
  - phase-4
  - portability
milestone: m-4
dependencies:
  - TASK-27.1
references:
  - decisions/webhooks.md
  - app/modules/slack/webhooks.py
  - decisions/plugin-architecture.md
parent_task_id: TASK-27
priority: high
ordinal: 220000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2 of TASK-27. Adds ONE operation to the records contract, update, and lands it with named first consumers rather than ahead of them (decisions/plugin-architecture.md: capabilities are never built speculatively).

SHAPE. update(table: RecordTable, key, changes, *, expected=None) -> OperationResult. changes is a typed, non-empty set of attribute changes: set an attribute, remove an attribute, or add an integer delta to a numeric attribute (a missing attribute counts as 0). The item must already exist; update never creates one. expected is an optional equality guard on non-key attributes, checked in the same atomic step. Same shape as slice 1: the table is a RecordTable, key and index attribute names come from its declaration, and no vendor expression appears in a signature.

FIRST CONSUMERS (each named so none is speculative)
- update with expected: TASK-145.8, IncidentStore.update_field.
- set and remove in one call: closing an incident (TASK-145.8 status change to Closed sets the status and removes the sparse open-index attributes atomically).
- set: TASK-147.3, editing and assigning action items.
- increment: TASK-37.1, webhook invocation and acknowledgement counters (decisions/webhooks.md forbids read-modify-write).

TWO-PROVIDER CHECK. DynamoDB UpdateItem with ConditionExpression; Cosmos DB patch with a filter predicate and incr; Postgres UPDATE ... WHERE ... RETURNING with COALESCE; Firestore update inside a transaction for the guard. Passes.

DEFERRED. The bounded full-table list moves to its own task, shaped with its first consumer (TASK-37.1 list and lookup, TASK-145.12 sheet rebuild). Appending to a list attribute is not added: incident timeline entries are their own records in a separate timeline table.

CONDITIONS FROM SLICE 1. Index semantics are documented on the Protocol: items missing an index's key attributes are excluded from index queries (sparse), and index reads may be eventually consistent and are not unique. gt and between stay gated on a real consumer.

NOT IN SCOPE. The atomic multi-item conditional write (TASK-83.2); idempotent replay of an increment (an SDK retry may double-apply a counter increment, acceptable for counters and documented).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 RecordStore exposes update(table, key, changes, *, expected=None); changes is a typed non-empty set of set, remove and integer-increment changes defined as frozen dataclasses next to the other value types in infrastructure/records/protocol.py, and no vendor expression, projection or condition string appears in any Protocol signature
- [ ] #2 update requires the item to exist: a missing item returns NOT_FOUND and is never created, in the DynamoDB store (attribute_exists on the table's partition attribute) and in the fake; a missing attribute counts as 0 for increment, remove of an absent attribute succeeds, and every change in one call applies atomically with the updated item returned
- [ ] #3 expected is an equality-only guard on non-key attributes evaluated atomically with the change; when it does not hold nothing is written and the result is a successful, distinct non-error result (no new OperationStatus member) that callers can tell apart from an applied update and from NOT_FOUND
- [ ] #4 One shared validation helper in protocol.py, used by both stores, raises ValueError (programming error) for a key that does not match table.key exactly, a change or expected entry on a key attribute, an empty change set, an attribute named by more than one change, or a non-integer increment delta
- [ ] #5 InMemoryRecordStore guards every mutation with a threading.Lock, and DynamoDBRecordStore maps the change set to a single UpdateExpression (SET, if_not_exists plus delta for increments, REMOVE) with ExpressionAttributeNames placeholders for every attribute name; neither is a read-modify-write
- [ ] #6 The conformance suite runs every update case against the fake and the moto-backed DynamoDB store: set, remove, increment, mixed changes, missing item, absent-attribute increment and remove, guard pass and fail, key-attribute rejection, and a concurrent-increment case with threads whose final value equals the total of all deltas
- [ ] #7 The Protocol documentation states that items missing an index's key attributes are excluded from index queries (sparse indexes), that index reads may be eventually consistent and are not unique, and that an increment is not idempotent under SDK retry (acceptable for counters)
- [ ] #8 Appending to a list attribute is explicitly NOT added to the Protocol; a note records that incident timeline entries are their own records in a separate timeline table (declared by TASK-145.5, written by TASK-145.9), and the bounded full-table list is explicitly deferred to its own task with its consumers named
- [ ] #9 Notes name each first consumer (TASK-145.8, TASK-147.3, TASK-37.1) and record the two-plausible-provider justification required by decisions/plugin-architecture.md
- [ ] #10 ruff, lint-imports, mypy (no errors in touched files) and pytest tests --ignore=tests/smoke pass, with the commands and their output recorded in notes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Grounded at main (TASK-27.4 and 27.1 merged). Decisions only; the open items are verification assumptions, listed below.

## Decisions
- ONE operation: RecordStore.update(table, key, changes, *, expected=None) -> OperationResult. Bounded list is TASK-27.5; list-attribute append is not added (timeline entries are their own records, separate timeline table declared by TASK-145.5, written by TASK-145.9).
- Change set: three frozen slotted dataclasses in infrastructure/records/protocol.py, SetAttribute(attribute, value), RemoveAttribute(attribute), IncrementAttribute(attribute, delta: int), and `type RecordChange = SetAttribute | RemoveAttribute | IncrementAttribute`. Chosen over one AttributeChange with an op enum because each kind carries only the fields it means (no value on remove, an int delta on increment), the union narrows with match and mypy, and an enum plus optional value would allow invalid states. Frozen dataclasses per type-model-boundaries: internal value types, not Pydantic.
- changes is a Sequence[RecordChange] (non-empty); expected is Mapping[str, KeyValue | bool | None] | None, equality only, non-key attributes only.
- Semantics: item must exist; never upsert; missing item -> OperationResult.error(NOT_FOUND). Applied -> success(data=updated item dict, ALL_NEW). Guard not held -> success(data=None, message="Guard not satisfied"), nothing written, same style as put_if_not_exists returning success(data=False); no new OperationStatus member. A missing attribute counts as 0 for increment; remove of an absent attribute succeeds; deltas are int only (bool rejected). Increment is not idempotent under SDK retry; documented as acceptable for counters.
- Validation: one shared helper validate_record_update(table, key, changes, expected) in protocol.py (next to resolve_query_key), called first by both stores; raises ValueError for key not matching table.key exactly, change or expected entry on a key attribute, empty changes, one attribute in more than one change, non-int or bool delta. Programming errors, not result errors.
- DynamoDB: one UpdateItem, ExpressionAttributeNames placeholders for every attribute (#pk, #c0, #c1 ...) and ExpressionAttributeValues (:v0, :zero ...); `SET #c0 = :v0, #c1 = if_not_exists(#c1, :zero) + :d1 REMOVE #c2`; ConditionExpression `attribute_exists(#pk) AND #e0 = :e0 ...`; ReturnValues=ALL_NEW; ReturnValuesOnConditionCheckFailure=ALL_OLD distinguishes missing item (no Item in the failure) from guard failure (Item present). Reuses the module's existing serializer and error mapping.
- Fake: threading.Lock around every mutating method (put, put_if_not_exists, delete, update); update validates, checks existence and guard, applies all changes to a copy, then swaps in, all under the lock.
- Protocol docstring additionally documents sparse indexes (items lacking an index key attribute are excluded from that index's queries), eventually consistent and non-unique index reads, and increment retry behaviour.
- Two-provider justification (recorded in notes): DynamoDB UpdateItem + ConditionExpression; Cosmos DB patch with filter predicate and incr; Postgres UPDATE ... WHERE ... RETURNING with COALESCE; Firestore update inside a transaction for the guard.
- End-state checks: TASK-108 moves protocol.py as-is (new types move with it, no vendor strings); TASK-83.2 may reuse the change-set and guard vocabulary; TASK-103 replay-safety applies to put_if_not_exists, not here; table names stay with consumers' package settings, key layout in code; no new settings, no hardcoded constants.

## Steps (TDD, each step test first)
1. tests/unit/infrastructure/records/test_records_store_update_validation.py: failing cases for validate_record_update (key mismatch, key-attribute change or guard, empty, duplicate attribute, bool or float delta, valid inputs). Then protocol.py: the three dataclasses, RecordChange, the helper, the update method on the Protocol, docstring additions.
2. tests/integration/infrastructure/records/test_records_store_update_conformance.py on any_record_store (fake + moto): set, remove, increment, mixed changes in one call, missing item -> NOT_FOUND and nothing created, absent-attribute increment starts at 0, remove of absent attribute, guard holds, guard fails (non-error, nothing written, data None), distinguishing missing item from guard failure, key-attribute and validation ValueErrors, returned item is the full updated item, sparse-index exclusion after remove of an index attribute, and a thread-based concurrent-increment case (N threads x M increments, final equals N*M). Failing first.
3. in_memory.py: Lock in all mutators; update implementation; step 2 passes on the fake.
4. service.py: update implementation (expression builder as a small private function, tested through the conformance suite); step 2 passes on moto. Error mapping through the existing result path; ConditionalCheckFailed handled as above.
5. Fix small bugs or deprecated constructs found in the touched files (rule), without widening scope.
6. Notes: consumers, two-provider justification, deferral of the list and of list-append, gate output.

## AC traceability
AC1: steps 1, 3, 4 (test_records_store_update_conformance set/remove/increment + signature check); AC2: step 2 missing-item, absent-attribute and mixed-change cases; AC3: step 2 guard pass and fail; AC4: step 1 validation tests plus step 2 ValueError cases on both stores; AC5: step 3 Lock, step 4 single UpdateExpression with placeholders (assert the UpdateItem call shape in a unit test with a stubbed client) and concurrent-increment case; AC6: step 2 full matrix on fake and moto; AC7: step 1 docstring; AC8, AC9: step 6 notes; AC10: gates below.

## Test matrix
Happy: set, remove, increment, mixed. Boundary: increment by 0 and negative delta, set to None/False/0, one change only, remove of the last non-key attribute. Failure: missing item, guard fails, every ValueError. Concurrency: threaded increments on fake and moto. Guard: holds, fails, guard on an absent attribute (expected None means absent). Atomicity: a mixed call whose guard fails changes nothing. Files: tests/unit/infrastructure/records/test_records_store_update_validation.py, tests/unit/infrastructure/records/test_records_store_update_expression.py, tests/integration/infrastructure/records/test_records_store_update_conformance.py (docstrings describe behaviour only).

## Assumptions to verify
- moto supports UpdateExpression with SET if_not_exists plus arithmetic, REMOVE, ConditionExpression, ReturnValues=ALL_NEW (verify with a first failing run in step 2).
- moto returns the existing Item on ReturnValuesOnConditionCheckFailure=ALL_OLD for UpdateItem; if not, on a condition failure do one get to classify missing vs guard (classification read only, never a write decision).
- moto is reliable under concurrent threads for update_item; verify empirically first. If it is not, the implementer reports and the concurrency case runs on the fake with a sequential equivalent on moto (AC6 wording to be changed with approval).
- No consumer exists yet, so no call sites change; confirm with rg that nothing else implements RecordStore (tests/doubles) and needs the new method (the fake-coverage check in TASK-27.3).

## Size gate
Production: 3 files (protocol.py, in_memory.py, service.py), about 150 to 200 LOC, one subsystem (infrastructure/records). Tests add 3 files. Mechanical refactor not mixed. Passes the gate; one PR.

## Blast radius and rollback
Additive: a new Protocol method and types; no existing signature changes and no consumer calls it. A single revert restores prior state. Risk: any other RecordStore implementer (test doubles) must gain the method for the runtime-checkable Protocol; the fake-coverage check will show it. No Terraform, no settings, no ordering constraints; dependents TASK-145.8, TASK-147.3 and TASK-37.1 wait for this merge.

## Verification (from app/)
uv run ruff check . ; uv run lint-imports ; uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' (0 errors in touched files) ; uv run pytest tests --ignore=tests/smoke. Record commands and output in notes.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-13: scope revised after research. No current code can move onto an update, increment or list operation (access save_request is a whole-item put; the retry store and the status-update adapter use conditional writes; the legacy incident lookup is a filtered scan of an unbounded table), so the operation lands with named consumers: TASK-145.8 (update_field with expected, close as set plus remove), TASK-147.3 (set), TASK-37.1 (increment). Bounded list split to TASK-27.5. Dependents: TASK-145.8 and TASK-37.1 depend on this task; TASK-147.3 now does too.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-24 20:11
---
2026-09-24 citation fix: decisions/layers.md, capability-packages.md and events.md were deleted and replaced by decisions/plugin-architecture.md (six layers: server, features, capabilities, infrastructure, integrations, contracts). Read those references in this task as plugin-architecture.md. Path A infrastructure capabilities are now split: hosting contracts (storage, coordination, queue, secrets) live in app/contracts/ with implementations in app/infrastructure/; workplace systems and shared business engines live in app/capabilities/. Path B adapters are unchanged (outbound-clients.md).
---

created: 2026-10-13 17:59
---
2026-10-13 (TASK-27.1 implemented): AC wording proposals, not applied because the CLI cannot edit an AC in place. AC3: replace 'required by decisions/layers.md' with 'required by decisions/plugin-architecture.md'. AC5: replace 'pointing the incident activity log at TASK-38' with 'pointing the incident activity log at TASK-145' (TASK-145 replaces TASK-38 and its slices; its timeline entries are their own records).
---
<!-- COMMENTS:END -->
