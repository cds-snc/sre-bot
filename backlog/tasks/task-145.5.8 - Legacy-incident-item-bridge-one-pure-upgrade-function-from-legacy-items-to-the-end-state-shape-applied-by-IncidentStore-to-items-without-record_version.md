---
id: TASK-145.5.8
title: >-
  Legacy incident item bridge: one pure upgrade function from legacy items to
  the end-state shape, applied by IncidentStore to items without record_version
status: Done
assignee: []
created_date: '2026-10-15 18:17'
updated_date: '2026-10-15 19:51'
labels:
  - incident
  - features
  - records
dependencies:
  - TASK-145.5.4
references:
  - decisions/incident-management.md
  - decisions/cloud-portability.md
  - 'https://github.com/cds-snc/sre-bot/issues/1719'
parent_task_id: TASK-145.5
priority: medium
type: task
ordinal: 396000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 6 of Stack K (handoff doc-13). Split out of TASK-145.5.4 (human, 2026-10-15): TASK-145.5.4 reads end-state items only and returns INCIDENT_RECORD_UNREADABLE for an item without record_version; this layer lets the store read legacy items. It follows the legacy data upgrade rule set in decisions/incident-management.md (Migration, rules 2, 4 and 7): one pure upgrade function shared by the read bridge and the backfill, applied only to items without record_version, never guessing.

THIS SLICE
- features/incident/core/adapters/legacy_items.py: one pure function taking a legacy item dict and the tenants mapping (the configured tenant per WorkplaceSystem, passed in; no settings import) and returning either the end-state item dict or a classified unreadable result (incident id, field, stored value), so the job can list what to fix by hand; the dict is what the end-state parser (core/adapters/incident_items.py, TASK-145.5.4) then reads unchanged. The function does not add record_version, open_bucket or opened_at: the store's writers and the upgrade job do. The end-state parser gains no legacy branch.
- Mapping:
  - name to title; user_id to declared_by; created_at (epoch seconds or ISO-8601) to declared_at.
  - teams[0] to product; "Unknown" or blank is not recorded.
  - severity: sev-0 to sev-4, ignoring case and spaces, to 0 to 4; none or missing is unset; any other value is unset and logged with the incident id.
  - status: the five IncidentStatus values matched ignoring case and surrounding spaces (production holds 30 `closed` and 1 `reviewed` in lowercase); any other value is unreadable.
  - A missing security_incident is false (it was only stored from 2026-10-07).
  - Times: "Unknown" or blank are not recorded.
  - incident_commander and operations_lead become roles when present.
  - channel_id becomes the Slack conversation reference with the configured Slack tenant.
  - report_url becomes the Google report reference, the document id taken from /document/d/<id>.
  - meet_url becomes the Google video call reference with the meet code as vendor id; "TBC" or "" is no reference.
  - retrospective_url is skipped.
- Stored times: core/adapters/incident_items.py gains the stored-time formatter format_stored_time (fixed-width ISO-8601 UTC, isoformat(timespec="microseconds"), +00:00, the 2026-10-14 key-format decision), used here for declared_at and the optional times and reused by TASK-145.5.7, TASK-145.7 and TASK-145.8. It lives in incident_items.py (not core/store.py: store.py imports legacy_items.py, so legacy_items.py importing store.py would be circular; the formatter sits beside the time parser it round-trips with).
- Pure and never raising: an unmatched required value (status, declared_by, declared_at) is a classified unreadable result naming the incident id and field, which the store returns as INCIDENT_RECORD_UNREADABLE.
- RecordIncidentStore gains the tenants constructor argument (TASK-145.5.4 takes none, because end-state maps carry their own tenant) and a small hook that runs items without record_version through the function before parsing. TASK-145.5.5 passes the tenants from the configured-systems read where it builds the store.
- Tests over every legacy item shape, including the production lowercase statuses, epoch and ISO created_at, "Unknown" and blank values, TBC meet URLs, malformed report URLs and missing optional attributes.

LIFECYCLE
- Reused unchanged by the TASK-145.5.7 upgrade job, so the legacy mapping exists once.
- Deleted by TASK-145.13 once a production run of that job reports nothing pending.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 legacy_items.py maps name, user_id, created_at (epoch seconds or ISO-8601 with an offset), teams[0], severity (sev-0 to sev-4 ignoring case and spaces; none or missing unset; others unset and logged with the incident id), status (the five values ignoring case and surrounding spaces), a missing security_incident (false), "Unknown" or blank times (detection_time, start_impact_time, end_impact_time) and products (not recorded), incident_commander and operations_lead (roles), channel_id (Slack conversation reference), report_url (Google report reference, document id from /document/d/<id>) and meet_url (Google video call reference, meet code; "TBC" or "" no reference) to the end-state shape, and skips retrospective_url
- [x] #2 Times are written with format_stored_time, added in core/adapters/incident_items.py (fixed-width ISO-8601 UTC, isoformat(timespec="microseconds"), +00:00) and tested for width, offset and the round trip through the end-state parser
- [x] #3 The tenants mapping is passed in by the caller; legacy_items.py imports no settings and no vendor settings slice
- [x] #4 The function is pure and never raises: it returns either the end-state item or a classified unreadable result naming the incident id, field and stored value, for an unmatched required value (id, name, status, user_id, created_at, security_incident) and for a reference whose system has no configured tenant
- [x] #5 RecordIncidentStore takes the tenants mapping and reads items without record_version through the function before parsing, in get, find_by_conversation and list_open; items with record_version bypass it; the end-state parser has no legacy branch; tests cover every legacy item shape against InMemoryRecordStore, and the layer 5 tests that expected an unreadable item without record_version are rewritten
- [x] #6 ruff, lint-imports, mypy (no errors in touched files) and pytest tests --ignore=tests/smoke pass, with commands and output recorded in notes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
SCOPE AND SIZE
Three production files, no new subsystem: core/adapters/legacy_items.py (new), core/adapters/incident_items.py (formatter added), core/store.py (tenants argument and hook). Estimate ~290 production lines with docstrings (~215 executable); the layer 5 ratio was 1.5x, so up to ~330 with docstrings is expected. Under the 400 LOC / 10 files gate. Mapping and hook are one behaviour change; no mechanical refactor is mixed in. Revert: one git revert restores layer 5 (items without record_version read as INCIDENT_RECORD_UNREADABLE); nothing in production builds the store before TASK-145.5.5, so blast radius is nil until then.

LEGACY SHAPE (enumerated, path:line)
Model: app/models/incidents.py:10-33 (Incident, extra="forbid"): id, channel_id, channel_name, name, user_id, teams (list[str]), report_url (str), status (str, default "Open"), created_at (str, default str(datetime.now(UTC).timestamp()), an epoch float string), start_impact_time / end_impact_time / detection_time (str, default "Unknown", epoch strings), environment, logs, meet_url (str|None), incident_commander, operations_lead, severity (str|None), retrospective_url, security_incident (bool|None, absent on 316 of 323 production items).
Writers: modules/incident/core.py:505-519 (declare: teams=[team_name] where team_name defaults to "Unknown" at :503, report_url https://docs.google.com/document/d/<id>/edit at :491, meet_url = meetingUri, severity = modal value "none"/"sev-1".."sev-4"); modules/incident/db_operations.py:74-103 (create_incident, put_item of model_dump); modules/incident/information_update.py:15-45 (FIELD_SCHEMA: severity options none, sev-1..sev-4; status options the five values; the three times set from a date picker as epoch strings, :296-330); sheet import modules/incident/incident_folder.py:396-410 (user_id "", teams=[sheet cell], report_url=row link (may be None), created_at = sheet formatted date text, meet_url "TBC") and :436-465 (user_id filled from the Slack creator, created_at replaced by str(channel_info["created"]) epoch, meet_url replaced by the "Meet link" bookmark), :494-503 (create_missing_incidents). Local seed: bin/seed.sh:94 writes the incident created_at as an epoch (the naive value at :51 is the webhooks table, not incidents).
Readers of "Unknown": modules/incident/information_display.py:37-46.
Forms to handle: created_at epoch float string, epoch int string, ISO with offset, naive ISO / date-only text (sheet fallback, seed); status in five values with case/space variants; severity "none"/"sev-N"/None; teams ["Unknown"]/[""]/[]/missing; report_url "", None, non-/document/d/ link; meet_url "TBC", "", None, https://meet.google.com/<code>[?query].

DECISIONS
1. The stored-time formatter lives in core/adapters/incident_items.py as format_stored_time, not core/store.py: store.py imports legacy_items.py, so legacy_items.py importing store.py would be a cycle, and incident_items.py already holds the time parser it round-trips with. The task text, TASK-145.5.7 and TASK-145.7 descriptions were updated (CLI) to the new location.
2. Return form: upgrade_legacy_item(item, tenants) -> UpgradedItem | UnreadableLegacyItem. Both are @dataclass(frozen=True) in legacy_items.py (internal entities, no Pydantic). UpgradedItem.item is the end-state dict; UnreadableLegacyItem carries incident_id, field, value so TASK-145.5.7 can list ids and stored values (its AC 4) and count unmatched_status without re-deriving anything. tenants is Mapping[WorkplaceSystem, str]; TASK-145.5.5 builds it from the configured-systems read. No settings import.
3. The function never adds record_version, open_bucket or opened_at (writers and TASK-145.5.7 do), and never emits channel_id (already on the item, the by_channel key). Nested reference maps are {system, tenant, vendor_id[, url]} with url omitted when absent so a DynamoDB write has no NULLs.
4. Required (unreadable on failure, field and stored value reported): id, name (title), status, user_id (declared_by), created_at (declared_at), security_incident when present but not bool (missing or None is false).
   - created_at: epoch seconds as str/int/float/Decimal, or ISO-8601 carrying an offset. Naive ISO and date-only text are unreadable, never assumed UTC (rule 7, never guess). Out-of-range epochs, nan and inf are unreadable (caught, no raise).
   - status: strip and casefold against the five IncidentStatus values, output the canonical value; anything else unreadable.
5. Optional (dropped and logged with incident_id and field, never the value of a URL): product from teams[0] ("Unknown", blank, non-list, empty list not recorded); severity regex sev-[0-4] after removing spaces and lowercasing -> int, "none"/None/blank unset silently, anything else unset with a warning carrying the incident id and value; the three times via the same epoch/ISO reader, "Unknown"/blank not recorded, unreadable dropped and logged; incident_commander and operations_lead copied when non-blank text; report_url -> Google report reference, vendor_id from /document/d/<id>, url = the stored link, no match = no reference, logged; meet_url -> Google video call reference, vendor_id the last path segment of a meet.google.com URL without query, "TBC"/""/None/other host = no reference, logged for non-blank non-TBC; retrospective_url, channel_name, environment, logs, teams[1:] skipped.
6. References need a configured tenant: channel_id (non-blank) needs tenants[SLACK]; a usable report_url or meet_url needs tenants[GOOGLE]. A missing tenant for a present value is UnreadableLegacyItem(field=...) rather than a silent drop, because the job would otherwise stamp record_version over a lost reference. A blank channel_id yields no conversation.
7. Store hook (store.py): __init__(records, table, tenants). One private method replaces _is_end_state: returns the item as is when record_version is present, else runs upgrade_legacy_item and returns the upgraded dict, or logs incident_record_unreadable (operation, incident_id, field; the status value only for status, as the end-state parser does) and returns None. _parse, find_by_conversation (before read_reference, so legacy candidates are matched by the upgraded conversation's system and tenant) and list_open all go through it. parse_incident_item and the end-state parser are untouched. list_open only sees items carrying open_bucket, so legacy items appear only after TASK-145.5.7; its docstring says so.
8. Logging adds incident_id and field everywhere it is touched; no tokens, no URLs.
9. Bugs in touched files: the stale "until the bridge" wording in store.py's module docstring and the removed incident_item_not_upgraded event go with the hook; ruff will flag any deprecated construct in the three files at the first gate run and it is fixed there.

STEPS (TDD, tests first)
1. tests/unit/features/incident/core/test_incident_core_stored_time_format.py (new) then format_stored_time in core/adapters/incident_items.py: aware datetime -> UTC isoformat(timespec="microseconds") (+00:00, fixed width 32 chars), non-UTC offset converted, naive raises ValueError (programmer error), round trip through the parser's _parse_time-based read. Update the module docstring ("Read and format"). ~12 lines.
2. tests/unit/features/incident/core/test_incident_core_legacy_item_required.py, ..._legacy_item_optional.py, ..._legacy_item_references.py (new) then core/adapters/legacy_items.py: the two dataclasses, upgrade_legacy_item and private helpers (status, time, severity, product, report, meet, references). ~215 executable lines.
3. tests/unit/features/incident/core/test_incident_core_incident_store_legacy_items.py (new, over InMemoryRecordStore) then store.py: tenants argument, the hook, docstring updates. ~25 lines.
4. Edit in place the layer 5 store tests for the new constructor argument (list_open:46,90; find_by_conversation:63,141,199,213; security_flag:40,75; get:48,84) and rewrite the three tests that asserted the unreadable-until-bridge behaviour (get:93, list_open:71, find_by_conversation:183) so each states the new behaviour (an item that is neither shape stays unreadable; a legacy item reads).
5. Gates from app/: ruff check ., lint-imports, mypy on touched files (zero errors; repo-wide errors elsewhere ignored), pytest tests --ignore=tests/smoke; record commands and output in notes; check each AC as its test passes.

AC TRACEABILITY
AC1 -> step 2 (required, optional, references test files). AC2 -> step 1. AC3 -> step 2: an import-scan test asserting legacy_items.py imports neither infrastructure.configuration nor any settings module (a Path-based source scan, as test_incident_core_api_surface.py already reads source files; confirm its approach at implementation) and lint-imports. AC4 -> step 2 (every required-field failure and missing-tenant case returns UnreadableLegacyItem, fuzz-style parametrised inputs of wrong types prove nothing raises). AC5 -> steps 3 and 4. AC6 -> step 5. Every step maps to an AC; step 4 is enabling work for AC5.

TEST MATRIX
Happy path: full legacy item (declare writer shape) -> Incident with every field; sheet-import shape (user_id filled, meet TBC, teams cell, epoch created_at); status lowercase "closed" and "reviewed" (production), padded " Open "; created_at epoch float string, epoch int, ISO with offset (+00:00 and -04:00 converted to UTC), Decimal epoch; severity "sev-0".."sev-4", "SEV-2", " sev-3 "; roles present; report URL /document/d/<id>/edit; meet URL with query.
Boundary: security_incident missing/None -> false, True stays true; "Unknown" and blank times and product; teams [] / ["Unknown"] / [""]; severity "none", None, blank unset silently; stored-time width and offset; epoch 0 and a far-future epoch.
Failure: status "Done" or None -> unreadable status with value; blank user_id; missing name; naive ISO and date-only created_at; nan/inf/out-of-range epoch; security_incident "yes"; severity "critical" unset and logged with id; malformed report URL and non-meet meet URL dropped and logged without the URL; tenant missing for Slack and for Google -> unreadable field; non-Mapping stuff (teams as str) does not raise.
Store (InMemoryRecordStore): get, find_by_conversation (legacy candidate matched by upgraded tenant, other-tenant legacy candidate skipped, mixed legacy and end-state), read_security_flag of a legacy item with missing flag -> false, legacy unreadable -> INCIDENT_RECORD_UNREADABLE with incident id and field in the log; item with record_version bypasses the function (assert via a legacy-looking attribute that would change the result if upgraded); list_open with a record-version-less item in the open index is upgraded.
Idempotency: the function is pure, repeat call returns an equal result and does not mutate the input mapping (asserted).

ASSUMPTIONS AND DOUBTS (verify at implementation)
- Production created_at values are epoch strings: a read-only scan of the incidents table on 2026-10-15 found no non-epoch created_at. Naive or date-only text stays unreadable (decision 4) as a guard; the TASK-145.5.7 dry run would list such an item for a manual fix from the Slack channel created epoch.
- Production meet_url values are https://meet.google.com/<code> or TBC. Verify: dry-run drop log lists incident ids of dropped URLs.
- teams[0] is the product for every writer. Verify: rg '"teams"' app/modules (done above: core.py:307,514; incident_folder.py:403).
- Numbers reach the function as Decimal from the records contract; handled for epoch and severity.
- incident_items.py gaining a writer-side function does not break the "pure reader" docstring: reworded.
- import-linter: legacy_items.py imports only contracts.workplace, features.incident.common.vocabulary, core.domain (value only) and structlog; no new ignore entry. Verify with lint-imports.

BLAST RADIUS AND ROLLBACK
No production caller exists until TASK-145.5.5 builds the store; this layer changes only an unwired class and adds a pure function. Wrong mapping would surface as wrong reads once 145.5.5 deploys, and as wrong writes once 145.5.7 applies (guarded, rerunnable only until stamped), which is why unmappable values are unreadable rather than guessed. One git revert restores layer 5. Ordering: merges after layer 5 (#1722); TASK-145.5.5 passes the tenants; TASK-145.5.7 reuses the function and format_stored_time unchanged; TASK-145.13 deletes legacy_items.py.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented as layer 6 of Stack K on stack-k/task-145.5.8-legacy-item-bridge, TDD (tests first, red on ImportError, then green).

Production (3 files, ~323 lines added with docstrings, ~200 executable; plan estimate ~290-330):
- core/adapters/legacy_items.py (new, 267 lines, 183 executable): upgrade_legacy_item(item, tenants) -> UpgradedItem | UnreadableLegacyItem (frozen dataclasses). Unreadable names the incident id, the legacy attribute and the stored value. Epoch seconds are read exactly through Decimal (no float rounding); ISO-8601 needs an offset; naive or date-only text is unreadable for created_at and dropped for the optional times. Decimal overflow, NaN, sNaN and infinity are caught (ArithmeticError), so nothing raises. Optional drops log incident_legacy_field_dropped with incident_id and field (value for severity only, never a link).
- core/adapters/incident_items.py: format_stored_time (aware -> UTC isoformat(timespec="microseconds"), 32 chars, +00:00; naive raises ValueError).
- core/store.py: RecordIncidentStore(records, table, tenants); _end_state replaces _is_end_state and runs get, find_by_conversation and list_open through the bridge; an unreadable legacy item logs incident_record_unreadable with operation, incident_id and field (value for status only). find_by_conversation parses the matched upgraded item directly. The incident_item_not_upgraded event is gone.

Tests: 4 new files (stored_time_format, legacy_item_required, legacy_item_optional, legacy_item_references) plus test_incident_core_incident_store_legacy_items over InMemoryRecordStore. The layer 5 store tests pass the tenants. The three tests that expected an item without record_version to be unreadable now state the new rule: an item of neither shape (no record_version, no legacy name) stays unreadable.

Decisions (approved 2026-10-15): formatter in incident_items.py (store.py import cycle); naive created_at unreadable (production scan found none); missing tenant for a present reference is unreadable; malformed report or Meet link dropped and logged.

Follow-up created: TASK-155 (enable ruff DTZ, 60 naive datetime calls repo-wide, 4 in features/incident/scheduling/availability.py, not touched here).

Gates (from app/):
- uv run ruff check . -> All checks passed!
- uv run ruff format --check (touched files) -> 2 new files reformatted, then clean
- uv run lint-imports -> Contracts: 12 kept, 0 broken.
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> Found 48 errors in 19 files (checked 414 source files); 0 in touched files (pre-existing, outside this layer)
- uv run pytest tests --ignore=tests/smoke -> 5300 passed in 108.21s
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-15 19:39
---
Plan approved by the human 2026-10-15, with decisions: (1) format_stored_time in core/adapters/incident_items.py (store.py import cycle); (2) naive or date-only created_at is unreadable, never assumed UTC (production scan 2026-10-15: no non-epoch created_at, so no impact); times are stored as UTC instants with an explicit offset and shown in each viewer's zone; (3) a channel_id, report or Meet URL with no configured tenant for its system is unreadable; (4) a malformed report or Meet URL is dropped and logged, the legacy attribute stays on the item.
---
<!-- COMMENTS:END -->
