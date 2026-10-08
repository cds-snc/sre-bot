---
id: TASK-140.10.1
title: >-
  Store the security flag at declare and read it as yes, no or unknown through
  incident core
status: Done
assignee: []
created_date: '2026-10-07 19:02'
updated_date: '2026-10-08 15:54'
labels:
  - incident
dependencies:
  - TASK-140.5.3
parent_task_id: TASK-140.10
priority: high
type: feature
ordinal: 339000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 1 of TASK-140.10, Stack H layer 5 (branch stack-h/task-140.6-status-update-approve, name kept). The declare modal's yes/no answer is stored on the legacy incident item as a boolean (yes true, no false, anything else NULL; the recreate-missing-resources path at modules/incident/core.py:292-303 stores NULL). Incident (models/incidents.py, extra forbid) gains security_incident: bool | None = None. Core exposes a separate IncidentSecurityReader Protocol (not a new IncidentLookup method, so existing fakes stay valid) returning IncidentSecurityFlag YES, NO or UNKNOWN; LegacyIncidentTableLookup implements it with get_item by id and a projection. A failed read is a classified error, never NO. Nothing consumes it yet. Rollback: because Incident forbids extra attributes, never revert the model field once incidents carry the attribute; revert only the declare write, or roll forward.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Declaring an incident stores security_incident true for yes, false for no, NULL otherwise; the recreate path stores NULL
- [x] #2 Incident round-trips the field and the show and update modals render items with and without it
- [x] #3 IncidentSecurityReader.read_security_flag returns YES, NO or UNKNOWN (missing or NULL attribute), and a classified error with a generic message on a store failure or missing item
- [x] #4 The reader interface and its provider are in incident core's public surface
- [x] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Plan 2026-10-07. Layer 5 of Stack H (after TASK-140.5.3), branch stack-h/task-140.6-status-update-approve. Slice 1 of TASK-140.10; nothing consumes the reader until TASK-140.10.2.

Decisions
- Human 2026-10-07: store the flag on the legacy incident item and read it through an incident core interface returning yes/no/unknown; unknown fails closed downstream.
- Separate Protocol IncidentSecurityReader, not a new IncidentLookup method, so existing IncidentLookup fakes stay valid. LegacyIncidentTableLookup implements both.
- Stored as a boolean attribute security_incident: yes -> True, no -> False, anything else -> None (NULL). IncidentPayload.security_incident stays the modal's yes/no string; the mapping is a small private helper in modules/incident/core.py.
- Read by get_item on the item's id (key read, no scan) with ProjectionExpression for security_incident. BOOL true -> YES, BOOL false -> NO, missing or NULL or any other type -> UNKNOWN. Store failure or missing item -> classified error with a generic message, never NO and never UNKNOWN.
- Reuses the adapter's existing botocore error classification; no provider text in messages.
- No terraform or DynamoDB Local change (schemaless attribute).

Findings (path:line)
- models/incidents.py:7-33 Incident, extra forbid at :31; IncidentPayload.security_incident: str at :42.
- modules/incident/core.py:499-510 declare incident_data (no flag) -> db_operations.create_incident; :292-303 recreate-missing-resources incident_data (no flag); :545 only existing consumer (invites security group).
- modules/incident/db_operations.py:65 Incident(**incident_data); :74-77 returns existing id without overwrite; :79-84 serializes every model_dump key with TypeSerializer then put_item, so an unset optional already writes NULL.
- Incident(**item) readers that need the field on the model: modules/incident/information_display.py:29, modules/incident/information_update.py:329.
- Other item readers deserialize to plain dicts and are unaffected: modules/dev/incident.py, modules/slack/webhooks.py:203.
- packages/incident/core/adapters/legacy_incidents.py:36-72 LegacyIncidentTableLookup, :74-83 scan, :94-97 build_legacy_incident_lookup. packages/incident/core/api.py:44-57 IncidentLookup, :147-150 get_incident_lookup (cached provider), __all__ at :27-39. core/adapters has no in-memory incident adapter (in_memory.py holds only the status-update store), so tests use Stubber and inline fakes.

Steps (TDD order; each step starts with its failing tests)
1. Tests first (all failing): new core test file, edited api-surface, declare, db_operations and information_display tests (see matrix). Run and confirm they fail for the right reason.
2. models/incidents.py: add security_incident: bool | None = None to Incident (field only).
3. modules/incident/core.py: add a private mapper (yes True, no False, else None); add the key to the declare incident_data at :499-510 only; recreate path at :292-303 is left without the key so the model default stores NULL.
4. packages/incident/core/domain.py: IncidentSecurityFlag StrEnum (YES, NO, UNKNOWN).
5. packages/incident/core/api.py: IncidentSecurityReader Protocol with read_security_flag(incident_id) -> OperationResult[IncidentSecurityFlag] (documented outcomes); get_incident_security_reader() cached provider returning the legacy adapter; add IncidentSecurityFlag, IncidentSecurityReader, get_incident_security_reader to __all__.
6. core/adapters/legacy_incidents.py: LegacyIncidentTableLookup.read_security_flag using get_item (Key id S, ProjectionExpression with an alias, same table constant); catch ClientError and BotoCoreError, classify as the existing lookup does (a missing table stays PERMANENT_ERROR); item absent -> NOT_FOUND with NOT_AN_INCIDENT; build function shared with build_legacy_incident_lookup.
7. packages/incident/README.md: one line for the new interface.
8. Run gates; check ACs one by one as each test passes.

AC traceability
- AC1: steps 3; tests in tests/modules/incident/test_incident_core.py (declare stores True/False/None for yes/no/other; recreate stores no flag).
- AC2: steps 2; tests in test_db_operations.py (round trip, serialized BOOL/NULL) and test_information_display.py (item with and without the attribute renders).
- AC3: steps 4, 5, 6; tests in test_incident_core_incident_security_flag.py.
- AC4: step 5; test_incident_core_api_surface.py.
- AC5: gates.

Test matrix
- NEW tests/unit/packages/incident/core/test_incident_core_incident_security_flag.py (botocore Stubber on a real dynamodb client, as test_incident_core_incident_find.py does): BOOL true -> YES; BOOL false -> NO; attribute absent -> UNKNOWN; NULL -> UNKNOWN; wrong type (S) -> UNKNOWN; no Item in response -> NOT_FOUND NOT_AN_INCIDENT; Stubber ClientError and EndpointConnectionError -> classified error, generic message free of provider text; missing table -> PERMANENT_ERROR; request shape (Key, TableName, projection) validated by Stubber; blank incident id handled as not found without a call.
- Edit in place tests/unit/packages/incident/core/test_incident_core_api_surface.py: exact __all__, provider is cached and returns the legacy adapter, adapter satisfies the Protocol.
- Edit in place tests/modules/incident/test_incident_core.py: the incident_data passed to create_incident carries the right value for yes, no, other; the recreate path's data has no flag.
- Edit in place tests/modules/incident/test_db_operations.py: Incident accepts and round-trips the field; put_item serializes BOOL and NULL; items without it still validate.
- Edit in place tests/modules/incident/test_information_display.py: modal view builds from an item with and without the attribute.

Assumptions and doubts (how to verify)
- Nothing else builds Incident(**item) from table items: run rg 'Incident\(\*\*' --glob '!tests' before step 2.
- get_item with ProjectionExpression validates under Stubber's service model for the dynamodb client (red/green in the new test).
- The dynamodb client and role used for the scan are valid for get_item (same IAM role; check terraform/ policy lists dynamodb:GetItem on the incidents table; if missing, that is a terraform change and must land first, so verify before step 6).
- The declare modal only offers yes and no, so NULL appears only for unexpected values.

Size gate
- Production files: 6 (models/incidents.py, modules/incident/core.py, core/domain.py, core/api.py, core/adapters/legacy_incidents.py, packages/incident/README.md); about 85-100 production LOC (2 + 8 + 8 + 25 + 40 + 2). Two subsystems (legacy declare write, incident core), one behaviour change, no mechanical refactor. Within the gate.

Blast radius and rollback
- Declare writes one extra attribute; nothing reads it until TASK-140.10.2, so user-visible behaviour is unchanged.
- ROLLBACK RULE: Incident has extra=forbid, so once any incident item carries security_incident, reverting the model field would make Incident(**item) fail in the show and update modals. Never revert the model field after items carry the attribute. If a revert is needed, revert only the declare write in modules/incident/core.py (stops new items carrying it), or roll forward. A whole-PR git revert is therefore NOT safe after deploy, and the PR description must say so.
- Rolling deploy: an old instance reading a new item before this model change reaches it would fail validation for that item; short window, mitigated by deploying all instances before relying on it.
- Ordering: if the IAM policy lacks dynamodb:GetItem on the incidents table, add it before this merges (verify per assumptions).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-07: verified terraform/iam.tf:41-59 already allows dynamodb:GetItem on aws_dynamodb_table.incidents_table; no terraform change needed.

Implemented 2026-10-07. Gates from app/: ruff check passed; lint-imports 10 kept 0 broken; mypy no errors in touched files (57 pre-existing elsewhere); pytest tests --ignore=tests/smoke: 3941 passed, 6 failed (3 SNS webhook + 3 google directory = known TASK-90 order leaks); make test green (3164 + 783 passed). ruff format --check flags only untouched packages/incident/scribe/entrypoints/slack.py (pre-existing). Test edit: test_incident_core.py::test_initiate_resources_creation_succeeds exact create_incident dict gained security_incident True (stale after the declare write). Added build_legacy_incident_security_reader (required by new tests).
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-07 19:05
---
Plan approved by the human on 2026-10-07.
---
<!-- COMMENTS:END -->
