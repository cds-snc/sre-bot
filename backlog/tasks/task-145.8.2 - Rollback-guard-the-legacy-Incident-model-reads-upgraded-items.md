---
id: TASK-145.8.2
title: 'Rollback guard: the legacy Incident model reads upgraded items'
status: Done
assignee: []
created_date: '2026-11-09T19:06:00Z'
updated_date: '2026-11-10T19:43:00Z'
labels:
  - incident
  - legacy
dependencies: []
parent_task_id: TASK-145.8
priority: medium
type: task
ordinal: 507000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L5r (approved 2026-11-09, OQ18; widened 2026-11-10 after a program-scope assessment): prepare the legacy path so reverting any reader cutover keeps legacy readers and writers working on marker-2 items (AWS Builders' Library, rollback safety, prepare phase). Strict writes, tolerant reads: Incident keeps extra=forbid; the two legacy readers (information_display.py:29, information_update.py:329) build it with model_validate(extra=ignore) over a read-new-fallback-old overlay (int severity as sev-N, detected_at/impact_*_at as epoch text, title, report and video_call urls). Legacy field writes (db_operations.update_incident_field) write the new-name attribute in end-state form when the item's record_version is 2 or more, learning the marker by a read before the write pinned by a ConditionExpression; status writes also keep the open index (open_bucket, opened_at) right. A translated write, never dual-write. create_incident stays strict. Every guard site is tagged TODO(TASK-145.7.10) and deleted with the legacy model by TASK-145.7's declare cutover. Merges before the first reader cutover (L6a). Carries the incident-management.md Migration edit and the TASK-145.7.7 Done task file.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A legacy Incident built from an upgraded (marker 2) item validates through the tolerant reader path (per-call extra=ignore over the new-first overlay): int or Decimal severity renders sev-N, detected_at and impact_*_at render as epoch text, title, report and video_call urls win when present and the legacy attribute is the fallback; strict Incident construction (create_incident) still rejects unknown keys (tested)
- [x] #2 update_incident_field on an item with record_version >= 2 writes the new-name attribute in end-state form (severity int or REMOVE for none, times as ISO UTC, status with open_bucket and opened_at kept right for Closed and reopen) under a ConditionExpression pinning the marker it read, retries once when the condition is lost, and is unchanged for items without the marker (tested at the DynamoDB client edge)
- [x] #3 Round trips are tested with the real shapes: upgrade, then a legacy translated write, then the new-shape reader (parse_incident_item) sees a valid value; and upgrade, then a rebuilt writer change, then the legacy reader sees the new value
- [x] #4 _drop_retired_incident_updates is deleted if no strict construction from stored rows remains (otherwise kept and the PR says why); every guard site is tagged # TODO(TASK-145.7.10): remove with the legacy model
- [x] #5 The PR body states it is a rollback guard (translated write, never dual-write) deleted with the legacy model by TASK-145.7.10; the PR carries the decisions/incident-management.md Migration edit and the TASK-145.7.7 Done task file
- [x] #6 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## 0. Scope (approved wider scope, 2026-11-10) and ground truth

Goal: prepare the legacy path so that reverting any reader cutover (L6a, L7a, L7b) leaves a legacy reader AND legacy writers that work on items the rebuilt writers upgraded or updated. Pattern: AWS Builders' Library "Ensuring rollback safety during deployments", prepare phase: the old code reads the new shape first and writes the new shape on items already in it. Strict writes, tolerant reads, translated writes. This is a rollback guard, never dual-write (a legacy writer writes ONLY the new-name attribute on a marker-2 item, never both). It stays in legacy code, every site tagged `# TODO(TASK-145.7.10): remove with the legacy model`, and is deleted by TASK-145.7.10 (L9b); after that, fixes go forward only.

Decisions applied: (Q2) `Incident.model_config` KEEPS extra="forbid"; the two readers use pydantic per-call `Incident.model_validate(item, extra="ignore")` (pydantic 2.14.1 installed, signature verified by the coordinator); `create_incident` stays strict. (Q1) read-new-fallback-old plus translated writes.

### Marker-2 item shape (what is new, renamed, retyped)
Source: app/features/incident/core/adapters/incident_items.py:48 (RECORD_VERSION = 2), item_upgrade.py (plan = SetAttribute only, never RemoveAttribute), legacy_items.py:42-127 (mapping).
- Upgraded in place: legacy attributes survive with legacy types (name, user_id, created_at, channel_id, channel_name, teams, report_url, meet_url, detection_time, start_impact_time, end_impact_time, retrospective_url, logs) AND gain record_version, title, declared_by, declared_at, detected_at, impact_started_at, impact_ended_at, conversation, report, video_call, open_bucket, opened_at; roles and security_incident keep their names.
- Retyped under the SAME name: severity (legacy string "sev-N"/"none" -> int 0-4, a DynamoDB N, so a Decimal after TypeDeserializer). status: SAME strings. Verified: IncidentStatus values (vocabulary.py:11-15) equal the legacy dropdown options (information_update.py:36-42); the bridge only casefold-normalizes (legacy_items.py:154-159). No value translation in either direction.
- Times: legacy stores epoch-seconds text ("1760000000.0", written by information_update.py:304) and the legacy view does `int(float(...))` on it (information_display.py:37-44), so an ISO string would crash the view. End-state stores `format_stored_time` ISO-8601 UTC. Both directions need a conversion.
- Status has a COUPLED effect on end-state items: Closed removes open_bucket and opened_at; any other status carries open_bucket = "OPEN" and opened_at (store.py:107/336; TASK-145.8 plan section 3, L3 close/reopen). A legacy status write that only SETs status would leave a Closed incident in the open index (or a reopened one out of it).
- No end-state attribute exists for retrospective_url, channel_name, teams, logs (verified: rg retrospective_url app/features returns nothing).

## 1. Pairs mapped (read side: new value wins when present, else the legacy attribute)
| legacy model field | marker-2 attribute | read translation | translated legacy write (marker >= 2) |
|---|---|---|---|
| severity (str) | severity (int) | int/Decimal 0-4 (not bool) -> "sev-N"; legacy str passes through | "sev-N" -> SET severity = N (N); "none" -> REMOVE severity |
| detection_time | detected_at | ISO -> epoch text str(timestamp()); absent -> legacy attribute | epoch text -> SET detected_at = format_stored_time(UTC) |
| start_impact_time | impact_started_at | same | SET impact_started_at |
| end_impact_time | impact_ended_at | same | SET impact_ended_at |
| name | title | title wins when present | not written by any legacy writer (no FIELD_SCHEMA entry); read only |
| report_url | report.url | url when the map has one, else keep legacy | not written by any legacy writer |
| meet_url | video_call.url | same | not written by any legacy writer |
| status | status | none (same strings) | SET status, plus Closed: REMOVE open_bucket, opened_at; any other: SET open_bucket = "OPEN", opened_at = if_not_exists(opened_at, now ISO) |
| retrospective_url | none | pass through unchanged | unchanged (writes the legacy name; no counterpart exists) |
| incident_commander, operations_lead, security_incident | same name, same type | none | no legacy writer sets them |
Extra end-state keys (communications_lead, policy_lead, postmortem_owner, source_alert, conversation, open_bucket, opened_at, record_version, declared_*, ...) are dropped by the per-call extra="ignore" and never reach model_dump.

## 2. Legacy writers found (every SET on an incident item)
All incidents-table writes (rg `"incidents"` outside db_operations.py: none; webhooks.py writes other tables):
1. app/modules/incident/db_operations.py:144-150 `update_incident_field` (UpdateExpression `SET #field = :field`, no ConditionExpression). Callers: information_update.py:322 (update modal: detection_time, start_impact_time, end_impact_time, retrospective_url, severity, status; all type "S") and incident_status.py:59 (status). THIS is the one site needing translation.
2. db_operations.py:169-173 `log_activity` (`SET logs = list_append(...)`): `logs` is not a record field, same name and shape on marker-2 items. No change. Callers: db_operations.py:134, incident_folder.py:544 (sheet import).
3. db_operations.py:84 `create_incident` put_item: creates a NEW legacy item (no marker) from IncidentPayload-derived dicts (core.py:316, 525, dev/incident.py:104, incident_folder.py:541). Strict, unchanged; never meets a marker-2 item (the existing-channel check returns the existing id first, db_operations.py:74-77).
4. Roles, archive, recreate: no legacy SET on the incident item (role/commander/operations_lead are read-only in the legacy modules; archive and recreate act on Slack/Google). The core cutovers L7a/L7b own those writes.
Readers building the model (guard takes effect): information_display.py:29 (show) and information_update.py:329 (after update; its incident_data is the prior model_dump held in private_metadata, information_display.py:51-53, so it is already legacy-named). db_operations.py:65 is the strict create. The domain dataclass at incident_items.py:78 is a different class.

## 3. How the writer learns the marker (decision): read before write, with a condition pinning the observed marker
DynamoDB UpdateItem cannot choose which attributes to SET from a stored value, so the writer must know the marker before it builds the expression. Recommended: one GetItem (ProjectionExpression: record_version, status) via the existing adapter.get_item (dynamodb.py:96), then ONE UpdateItem with a ConditionExpression that pins what was read: `attribute_not_exists(record_version)` for a legacy item (the write is exactly today's `SET #field`), `record_version = :seen` for a marker item. On ConditionalCheckFailed re-read once and retry, then log and give up as the writer does today on failure. Why not condition-only (try legacy write, fall back on failure): a conditional write cannot SET different attributes per branch, and trying the legacy form first on a marker-2 item would need a second round trip anyway while risking a partial write if the condition were forgotten. Why the condition at all: the upgrade job or upgrade-on-write can raise the item between the read and the write; without it a legacy-name write would land on a marker-2 item (stale, ignored by the new-first read). Cost: one extra GetItem per legacy field update (modal and status command, low volume). Item missing at read: fall back to today's behavior (SET on a missing key, as now).
Assumption to verify before coding: the adapter's update_item surfaces ConditionalCheckFailedException as a classified failure result (rg the dynamodb adapter and its error mapping; the store already relies on conditional updates through RecordTable). If it does not, the guard falls back to the read's result with one retry and a note.

## 4. Files to change (production)
1. NEW app/features/incident/core/adapters/legacy_rollback.py (~110 LOC): pure, no I/O, tagged TODO(TASK-145.7.10). `legacy_view(item) -> dict` (the new-first overlay per section 1, input TypeDeserializer output); `translated_update(field, value, *, marker) -> UpdatePlan` (SET/REMOVE expression parts and values for marker >= 2, `None` for marker absent so the caller keeps its current expression). Reuses format_stored_time (incident_items.py), the severity bounds of legacy_items.py:43/214-225 (same "sev-([0-4])" rule, imported or mirrored with a pointer), IncidentStatus. Does not touch legacy_items.py or item_upgrade.py.
2. app/modules/incident/db_operations.py (~50 LOC): `update_incident_field` reads the marker, builds the translated expression, adds the ConditionExpression and the one retry; `get_incident_by_channel_id`/lookup unchanged (the overlay is applied by the readers below, not at the scan).
3. app/modules/incident/information_display.py:29 and information_update.py:329: `Incident.model_validate(legacy_view(incident_data), extra="ignore")` (2 LOC each + import).
4. app/models/incidents.py: `model_config` unchanged (forbid). `_drop_retired_incident_updates` (lines 6, 38-45): re-checked. After this change no production path builds the model from a stored row strictly (readers ignore extras; create dicts never carry incident_updates: rg shows the key only in models/incidents.py and tests), so the validator is dead and is DELETED with its constant and the `Any` import if unused; the per-call ignore covers the retired key. Its three tests move to the tolerant path (see tests). If the rg at implementation time finds a strict-from-row build, keep it and say so in the PR.
5. decisions/incident-management.md (Migration rules 1 and 5 plus changelog line): written by the coordinator, rides in this PR.
6. backlog/tasks/task-145.7.7 ... .md (status Done, already modified): rides in this commit, not authored here.
Production total: 5 files, ~170-200 changed LOC (guard module ~110, db_operations ~50, readers ~10, model ~-10), plus the ADR edit and a task file.

## 5. TDD test matrix (failing first; unit marker; names per testing-standards)
New app/tests/unit/features/incident/core/test_incident_core_legacy_rollback_view.py (pure overlay):
1. Upgraded item (built by the real plan_item_upgrade, applied, round-tripped through TypeSerializer/Deserializer so ints are Decimal) -> `legacy_view` -> `Incident.model_validate(..., extra="ignore")` validates; severity "sev-2".
2. Parametrized severity 0-4 as Decimal and int -> "sev-N"; absent -> None; bool, 7, 2.5 not rendered (stay invalid/unchanged).
3. detected_at/impact_*_at ISO -> epoch text the legacy view accepts (`int(float(x))` works); absent new name -> legacy attribute kept; title/report.url/video_call.url win over name/report_url/meet_url when present, and fall back when absent.
4. Rebuilt writer then legacy reader: an item upgraded, then changed by the real store/in-memory update (severity, title, impact time) -> legacy view shows the new value.
New app/tests/unit/features/incident/core/test_incident_core_legacy_rollback_write.py (pure translation): per field in section 1: severity "sev-3" -> N 3; "none" -> REMOVE; each time epoch -> ISO UTC; status Closed -> REMOVE open_bucket/opened_at; status In Progress on a closed item -> SET open_bucket, if_not_exists opened_at; retrospective_url unchanged; marker absent -> no translation.
New app/tests/unit/modules/incident/test_incident_db_operations_update_field_marker.py (adapter faked at the DynamoDB client edge, per the existing db_operations tests): marker absent -> today's expression plus attribute_not_exists condition; marker 2 -> translated expression plus `record_version = :seen`; lost condition -> one re-read and retry, second loss -> logged, no raise; Closed on marker 2 removes the open index attributes.
New round-trip test (same dir as view test): upgrade -> LEGACY translated write applied to the item -> the new-shape reader (`parse_incident_item`, incident_items.py; severity at 279-285) returns the right values (severity int, impact time, Closed bucket rules via is_open) and upgrade -> new writer -> legacy reader sees the new value (item 4). Uses real functions, no infra imports.
Edited: tests/unit/models/test_models_incident_legacy_attribute_load.py: retired-key tests run through the per-call ignore (and the unknown-key-rejection test stays: strict construction still refuses); an added test that a strict `Incident(**row_with_new_key)` still fails (create stays strict). tests/modules/incident/test_information_display.py and test_information_update (existing) stay green, plus a case with a marker-2 item.
Must stay green: tests/modules/incident/test_db_operations.py (create invalid data), tests/integration/legacy_surface/ (seed through Incident(...) strict).
AC traceability: AC1 -> steps 1,3 + tests 1-3; AC2 -> step 2 + write tests + marker test; AC3 -> round-trip tests; AC4 -> step 4 + attribute_load test; AC5 -> tag check test by rg in review (and the PR body); AC6 -> gates.

## 6. Size gate
Production ~170-200 LOC, 5 files (+ ADR + task file, docs), one subsystem (legacy incident modules with a pure helper in the incident bridge), no mechanical refactor mixed with behavior, one revert restores. Within the gate (<400 LOC, <10 files). Tests add ~350 LOC across 4 new files and 1 edit; tests are excluded from the gate. If review needs less: split read side (steps 1 minus translated_update, 3, 4) from the write side (2 plus translated_update); both must land before L6a, so I recommend one PR.

## 7. Revert story and ordering
One revert removes the guard and restores today's strict reader and the plain `SET`. Ordering: merges and deploys before L6a (first marker-2 writer) and before L8 apply. Reverting a reader cutover afterward leaves a reader/writer that handle marker-2 items. Writes by the legacy modal on a marker-2 item are NOT mirrored into the legacy attributes (single-write rule): reverting this PR after legacy translated writes leaves those values only in new-name attributes (the rebuilt readers read them fine). Known limits stated in the PR body: a legacy severity change on a marker-2 item appends no severity_changed timeline entry (the legacy logs line is still written); items created fresh by the rebuilt declare (after TASK-145.7.10, no legacy code left) are not covered by design.

## 8. Assumptions and doubts (each with its check)
- ConditionalCheckFailed classification in the DynamoDB adapter (section 3): rg the adapter and its tests before coding.
- No retrospective_url counterpart in the end-state shape: if TASK-145.8.1's update_fields stores the "retrospective link" under a name (for example postmortem_meeting.url), add that pair (read and write) here; verify against the merged 145.8.1 store before coding.
- import-linter and make check-package-shape allow modules.incident -> features.incident.core.adapters.legacy_rollback (the legacy modules already import features adapters) and a new file in that package: run both early.
- No other code depends on Incident rejecting extra keys on read: rg extra_forbidden in tests shows only the strict test kept.
- Domain-model evolution gate: not applicable (no entity change; compatibility is the pair table and revert story above).

## 9. Gates (from app/, in order)
During the work: `uv run ruff check .` and targeted files only: the four new test files, test_models_incident_legacy_attribute_load.py, tests/modules/incident/test_db_operations.py, test_information_display.py. At the end, once each, sequentially: `uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'`, then `uv run pytest tests --ignore=tests/smoke`; plus `lint-imports`, `make check-package-shape`, `make check-test-seams` (repo root). Report command and actual output. PR body states: rollback guard (prepare phase), tagged TODO(TASK-145.7.10), deleted with the model, never dual-write. Commit also carries the TASK-145.7.7 Done task file and the ADR edit.

Placement (human, 2026-11-10): the guard module stays at app/features/incident/core/adapters/legacy_rollback.py; a transitional file's location is free as long as it is tagged TODO(TASK-145.7.10), listed in 145.7.10's deletions, and lint-imports, check-package-shape and check-test-seams pass. No end-state reader or core module imports it (rule 2: the end-state reader never contains a legacy branch); only modules.incident does. OQ1 resolved: on the 145.8.1 branch no end-state attribute holds the retrospective link (postmortem_meeting is the meeting reference, set through set_reference), so retrospective_url passes through under its legacy name. OQ2 (adapter reports ConditionalCheckFailedException as a classified failure) is unverified: check first at implementation.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-10: this guard must be deployed before TASK-145.7.8 sets upgrade_mode apply (see TASK-145.7.8 notes).

Implemented. Adapter finding: DynamoDBAdapter.update_item does not raise on a lost condition; _call catches ClientError and classify_aws_error (integrations/aws/client.py:206) returns OperationResult.error(PERMANENT_ERROR, error_code='ConditionalCheckFailedException'). The writer classifies by result.error_code and retries once (re-reading the marker); a second loss is logged as incident_update_failed. A failed marker read logs a warning and falls back to the write pinned to attribute_not_exists(record_version), so the condition still protects an item that was upgraded meanwhile. _drop_retired_incident_updates deleted: both readers now validate with extra=ignore, create_incident builds only from payload dicts; strict Incident still rejects incident_updates (tested). Guard: features/incident/core/adapters/legacy_rollback.py (legacy_view, translated_update, TranslatedUpdate). Existing fixture edit: tests/integration/legacy_surface/conftest.py FakeDynamoDbClient gained get_item (the writer now reads the marker first). Gates: ruff, lint-imports (13 kept), check-package-shape, check-test-seams, check-settings-key-ownership OK; mypy 41 errors in 14 files (baseline, none in touched files); pytest 6999 passed. AC5 (PR body) left unchecked until the PR exists.

PR body draft (AC #5) is the text the PR is opened with; AC #5 is checked once the PR exists.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-10T18:52:00Z

---

2026-11-10 (human): plan APPROVED after the program-scope OQ assessment. Rulings: prepared legacy path (per-call extra="ignore" reads preferring end-state attributes; translated writes on marker-2 items; Incident keeps extra="forbid"); guard module at app/features/incident/core/adapters/legacy_rollback.py (location free for a transitional file if tagged TODO(TASK-145.7.10), listed in 145.7.10's deletions and the contract checks pass); OQ1 retrospective_url passes through under its legacy name; OQ2 adapter condition handling checked first at implementation; OQ3 no severity_changed timeline entry from a legacy write on a marker-2 item, stated in the PR body; OQ4 translated-write values live only in end-state attributes after a revert of L5r, accepted. No revert is anticipated; the guard is due diligence.

---
<!-- COMMENTS:END -->
