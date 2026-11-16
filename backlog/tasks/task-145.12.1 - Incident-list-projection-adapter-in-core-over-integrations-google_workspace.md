---
id: TASK-145.12.1
title: Incident list projection adapter in core over integrations/google_workspace
status: In Progress
assignee: []
created_date: '2026-11-09T19:06:00Z'
updated_date: '2026-11-16T13:26:00Z'
labels:
  - incident
  - features
dependencies: []
references:
  - decisions/incident-management.md
  - decisions/workplace-systems.md
parent_task_id: TASK-145.12
priority: medium
type: feature
ordinal: 504000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L4c (approved program in TASK-145.7's plan, section 2; outline in TASK-145.12's plan). core/api.py IncidentListProjection (append_row, update_status), core/adapters/google_sheets.py over integrations/google_workspace, fake and parity test; row format copied from incident_folder.py:279 and :311. Inert until TASK-145.8's status cutover and the declare service register writers.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The projection exposes only append_row and update_status and calls integrations/google_workspace directly; nothing in the incident umbrella uses infrastructure/spreadsheets (parent ACs #1 adapter part, #6)
- [x] #2 Columns A-E match the legacy writer's format (tested against the pinned values); column F holds the incident id; update_status finds the row by F, falling back to the channel id in E for rows without one
- [x] #3 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
- [x] #4 append_row and update_status upsert on the incident id; an incident without a report, a conversation or a product writes blank or plain-text cells and is never refused; plain-text cells are written as text per the OWASP leading-character list (decisions/workplace-systems.md rule 5)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Planned 2026-11-10 against main 0e12a616, revised and APPROVED 2026-11-16 (human: "accept all recommended changes" after the program-scope OQ assessment; rulings R1-R9 in the task comment). Side PR on branch task-145.12.1-list-projection cut from main 0e12a616, NOT on Stack L. Stack PRs #1846 (145.8.1) and #1852 (145.8.7) are open above main and are not on it; everything below is read from main.

## 0. Scope and decisions carried
- Parent plan (TASK-145.12, approved 2026-11-09): L4c, IncidentListProjection with append_row and update_status only; adapter in core/adapters/ calling integrations/google_workspace directly (AC #6, TASK-169 ruling); inert until TASK-145.8.4 (status fan-out, record -> report -> projection -> channel) and TASK-145.7.9 (declare service) register writers. No route, handler, plugin or settings wiring here.
- Rules applied: decisions/workplace-systems.md rule 5 (a projection is never read back as a source of truth and is rebuildable), Consequences (a failed projection write is a retry or a rebuild); decisions/incident-management.md:34 (an incident has zero or more bindings; one with none is complete) and :99; decisions/outbound-clients.md async-port rule (new core ports are async; a blocking Google adapter offloads with one asyncio.to_thread per call; callers never offload); decisions/operation-result.md:20,:25 (a new code is a reviewed one-line change; programmer errors raise).
- Approved rulings (2026-11-16): R1 rows carry the incident id in column F and are found by it (legacy rows without F: channel-id fallback on column E, deleted by TASK-145.12.3); R2 channel label derived (display only, empty without a conversation); R3 the Status cell is incident.status.value, the declared record's initial status is decided by TASK-145.7.9; R4 the OWASP leading-character guard on every plain-text cell, quotes doubled inside formulas; R5 README new row only, ADR lines A-C ride in this PR; R6 both methods upsert on the incident id (no NOT_FOUND for a missing row), the rebuild is new TASK-145.12.3; R7 signature (incident) / (incident, status) kept; R8 size about 340 LOC accepted; R9 no new ErrorCode: an incident without a report, conversation or product is written with blank or plain-text cells, never refused.

## 1. Re-grounded state on main (path:line)
- Legacy writers, the format to copy (app/modules/incident/incident_folder.py): add_new_incident_to_list :279-308 builds one row [today %Y-%m-%d, '=HYPERLINK("<document_link>", "<name>")', product, "In Progress", '=HYPERLINK("<channel_url>", "#<slug>")'] and appends at "Sheet1!A:A" on [incident_core] list_sheet_id (:304). update_spreadsheet_incident_status :311-376 reads the whole "Sheet1", finds the first row containing "#<slug>", writes "Sheet1!D<i+1>". Legacy recreate appends a missing row (modules/incident/core.py:251-266).
- Legacy callers stay until their cutovers (not touched): modules/incident/core.py:266 and :498; incident_status.py:57; information_update.py:314. infrastructure/spreadsheets stays (modules/aws/spending.py uses it; TASK-121).
- Gateway: integrations/google_workspace/client.py get_sheets_service :332, classify_google_error :381, GoogleCredentialsRefused :205; _build_service raises ValueError without a Google tenant (:344-350), so the adapter pre-checks the tenant like google_meet.py.
- Sibling pattern (TASK-145.7.6): core/adapters/google_meet.py; VideoCall Protocol core/api.py:377-399; provider get_video_call :402; fake InMemoryVideoCall core/adapters/in_memory.py:634; tests test_incident_core_video_call_{create_space,errors,protocol_parity}.py; surface test test_incident_core_api_surface.py:36-85.
- Record: core/domain.py Incident :247 (id, title, status, declared_at, product str|None, conversation ConversationReference|None, report ReportReference|None). The record stores no channel name; the Slack adapter's ConversationReference has no url (adapters/slack.py:346, :365), so the link is computed (legacy channel_url modules/incident/core.py:27). Legacy declare stores "Open" (models/incidents.py:17) but writes "In Progress" to the sheet.
- Settings: [incident_core] list_sheet_id (common/settings.py:62, default empty). Nothing in features/incident uses infrastructure/spreadsheets today.

## 2. Port (core/api.py)
    @runtime_checkable
    class IncidentListProjection(Protocol):
        """Write-only view of the incident list sheet, one row per incident keyed by its id; never read back as a source of truth."""
        async def append_row(self, incident: Incident) -> OperationResult[None]: ...
        async def update_status(self, incident: Incident, status: IncidentStatus) -> OperationResult[None]: ...

    @lru_cache(maxsize=1)
    def get_incident_list_projection() -> IncidentListProjection  # GoogleSheetsIncidentListProjection()

- Both methods upsert on incident.id (R6): append_row writes the full row (updates the incident's row in place if found, else appends); update_status sets the Status cell of the incident's row, or appends the full row with that status if no row exists. A retried or repeated write converges; a recreate (145.8.6) or a filled-in report re-upserts with append_row.
- Never refused for missing parts (R9): no report -> column B is the guarded plain title; no conversation -> column E empty; no product -> column C empty. A conversation of another system -> PERMANENT_ERROR UNSUPPORTED_OPERATION (as the Slack adapter's _conversation_unsupported). Wrong-typed arguments raise.
- Domain model: no entity changes; Incident.id already exists. A row/sheet reference on the record is rejected (rows shift on sort; it would tie the record to a projection).

## 3. Row format (core/adapters/list_rows.py, pure, shared by adapter and fake)
- list_row(...) -> list[str], six columns: A "%Y-%m-%d" UTC date of declared_at; B =HYPERLINK("<report_url>", "<title>") or the guarded title; C guarded product or ""; D status.value; E =HYPERLINK("<channel_url>", "#<slug>") or ""; F incident.id. Columns A-E byte-identical to legacy for normal values (pinned); F is new; later columns only append to the right of F.
- Guard (R4, OWASP CSV injection): a plain-text cell starting with = + - @, tab, CR, LF or their full-width forms (＝ ＋ － ＠) is prefixed with an apostrophe; text placed inside a HYPERLINK string has its double quotes doubled.
- Row lookup helpers: row_index_for(incident_id, channel_id, rows) over the E:F values read with FORMULA render: first row whose F equals the id; otherwise (fallback, R1) the first row whose F is empty and whose E formula carries the channel id (app_redirect?channel= or /archives/<id>; channel_id_from_row_formula). Header row cannot match.
- core/adapters/slack.py gains slack_conversation_link(conversation) (reference.url wins, else app_redirect with tenant team_id, as legacy channel_url) and slack_conversation_label(incident) (display only).

## 4. Adapter (core/adapters/google_sheets.py): GoogleSheetsIncidentListProjection
- Settings read at call time: empty list_sheet_id -> PERMANENT_ERROR CONFIG_NOT_CONFIGURED naming [incident_core] list_sheet_id; no Google tenant -> same code naming google_workspace.tenant; both before any request.
- One asyncio.to_thread per method call over one sync function: (1) values().get(range "Sheet1!E:F", valueRenderOption FORMULA) with SDK default retries; (2) found -> values().update of "Sheet1!A<n>:F<n>" (append_row) or values().batchUpdate of D<n> (and F<n> when the match came through the fallback, so the row is keyed from then on) (update_status), USER_ENTERED, retryable (idempotent cell sets); not found -> values().append range "Sheet1!A:A", USER_ENTERED, INSERT_ROWS, num_retries=0 (Sheets has no idempotency key). Residual risk: two writes racing for the same incident may both append; the rebuild (145.12.3) repairs.
- Error mapping: HttpError and GoogleCredentialsRefused through classify_google_error -> classified OperationResult (log incident_list_projection_failed with operation, error_code, retry_after; never the sheet id or row text); 400 "Unable to parse range" -> NOT_FOUND RANGE_NOT_FOUND; unknown errors propagate.
- Imports integrations.google_workspace only; never infrastructure.spreadsheets.
- Provider inert: nothing resolves get_incident_list_projection until 145.8.4 / 145.7.9, which state list_sheet_id as required when they register (parent AC #5).

## 5. Files and size (size gate: pass, R8)
Production, about 340 LOC: core/api.py (~35), core/adapters/google_sheets.py new (~150), core/adapters/list_rows.py new (~75), core/adapters/in_memory.py (+InMemoryIncidentListProjection appended at the end, ~50), core/adapters/slack.py (~25), features/incident/README.md (one new where-to-go row). ADR lines (this PR, R5): decisions/workplace-systems.md rule 5 (wording A) + Changes line; decisions/incident-management.md:54 core-owns list (wording B) + Changes line; decisions/outbound-clients.md:69 tolerated num_retries=0 list (wording C). One subsystem; no terraform, config, settings, env or dependency change; no deletion.

## 6. Test matrix (TDD, app/tests/unit/features/incident/core/)
- test_incident_core_list_rows_format.py: pinned legacy values for columns A-E plus F id; blank cells for no report / conversation / product; five status values; guard cases (each leading character incl. full-width, quote doubling, unchanged otherwise); UTC date; channel_id_from_row_formula forms; row_index_for: id match, fallback only on empty F, id match wins over an earlier fallback row, header, no match.
- test_incident_core_slack_conversation_link.py: url wins; app_redirect with team id; no tenant; label equals legacy slug; non-Slack refused.
- test_incident_core_list_projection_append_row.py: found -> update A<n>:F<n>; not found -> append with pinned range, USER_ENTERED, INSERT_ROWS, num_retries=0; incident without conversation or report appended with blank/plain cells; one thread hop per call.
- test_incident_core_list_projection_update_status.py: found by F -> D<n>; found by fallback -> D<n> and F<n>; not found -> full row appended with the given status; read uses E:F FORMULA; one thread hop.
- test_incident_core_list_projection_errors.py: 429/403/credentials refused classified; parse-range -> RANGE_NOT_FOUND; unknown HttpError propagates; empty sheet id / no tenant refused before any service is built; non-Slack conversation UNSUPPORTED_OPERATION; logs carry no sheet id.
- test_incident_core_list_projection_protocol_parity.py: parametrised over adapter (stubbed service) and fake: isinstance Protocol; append twice -> one row; update_status on a missing incident -> one row with that status; two incidents -> two rows; same rows through list_rows.
- test_incident_core_list_projection_boundaries.py: Protocol members exactly append_row and update_status, both coroutines; no infrastructure.spreadsheets import under features/incident (AST); google_sheets imports integrations.google_workspace; provider cached.
- test_incident_core_api_surface.py: __all__ gains IncidentListProjection and get_incident_list_projection.
Stubs at the edge only (integrations getters, settings getters), as the meet tests; no test-seams baseline entry.
AC traceability: AC #1 -> boundaries; AC #2 -> list_rows_format + append/update; AC #4 -> append/update/parity/format; AC #3 -> section 7.

## 7. Verification (from app/)
- During TDD: uv run ruff check . ; targeted pytest on the files above.
- End: lint-imports; make check-package-shape; make check-test-seams; make check-fake-coverage; make check-import-contracts; then once each, sequentially: uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' ; uv run pytest tests --ignore=tests/smoke.

## 8. Blast radius, revert, conflicts, deletions
- Blast radius: none at runtime (inert provider). One git revert removes it.
- Conflicts with #1846/#1852: core/api.py, in_memory.py tail, README, api-surface __all__, decisions/incident-management.md (both stack PRs edit it; this PR adds one clause in the core-owns sentence and one Changes line), and the task files of 145.7.9 (#1852 edits its dependencies) and 145.8.4/145.8.6 if they changed on the stack. Whoever merges second rebases by hand (mechanical).
- Deletions: none dead. Temporary duplicates removed by later tasks: legacy channel_url / channel_id_from_link (145.7.10 / 145.12.2), legacy valid_statuses (145.8.4), the channel-id fallback (145.12.3 after its first production run).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented 2026-11-16 on branch task-145.12.1-list-projection. Production: core/api.py (IncidentListProjection Protocol + get_incident_list_projection, after get_video_call), core/adapters/google_sheets.py (new, GoogleSheetsIncidentListProjection), core/adapters/list_rows.py (new: guard_text, list_row, channel_id_from_row_formula, row_index_for), core/adapters/slack.py (slack_conversation_link, slack_conversation_label), core/adapters/in_memory.py (InMemoryIncidentListProjection, upsert, fail_with), features/incident/README.md (one new row). ADR lines A/B/C and 2026-11-16 Changes entries in decisions/workplace-systems.md, incident-management.md, outbound-clients.md. Tests: 7 new files + surface edit under tests/unit/features/incident/core/, plus shared stand-in tests/factories/incident_list_sheet.py (stateful fake Sheets service at the gateway factory). No new ErrorCode, no test-seams baseline entry. Decisions while coding: channel label is slack_channel_name(first candidate name, production prefix) minus 'incident-', from the declared UTC day; slack_conversation_link raises ValueError for non-Slack (adapter and fake refuse with UNSUPPORTED_OPERATION first); failure message omits the HttpError text because it carries the request url with the sheet id. Gates: lint-imports 13 kept 0 broken; check-package-shape, check-test-seams, check-fake-coverage, check-import-contracts, check-settings-key-ownership all OK; ruff all passed; mypy 40 errors in 13 files (= main baseline; 5 transient errors in google_sheets fixed by typing ValueRange/Literal); pytest 7228 passed. Deferred: none.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-16T13:16:00Z

---

2026-11-16 plan approved (human: accept all recommended changes, after the program-scope assessment of OQ1-OQ8 against decisions/, doc-11, doc-15 and prior/upcoming tasks). Rulings:
R1 (OQ1) Rows carry the incident id in a new column F and are found by it; legacy rows without F fall back to the channel id parsed from column E. Reason: incident-management.md:34 (zero or more bindings; one with none is complete), 145.8.6 moves the primary channel, doc-15 165.5 children without bindings and embargo need a key independent of display text. No entity change (Incident.id exists); a row reference on the record is rejected. The fallback is deleted by TASK-145.12.3 after its first production run.
R2 (OQ2) Channel label derived (display only); empty without a conversation.
R3 (OQ3) Status cell is incident.status.value; the declared record's initial status is decided and recorded by TASK-145.7.9 (AC added there).
R4 (OQ4) OWASP CSV-injection guard on every plain-text cell (= + - @, tab, CR, LF and full-width forms prefixed with an apostrophe); quotes doubled inside HYPERLINK strings.
R5 (OQ5) README: new where-to-go row only; ADR wording rides in this PR: workplace-systems.md rule 5 (row key, upsert, rebuild, injection guard), incident-management.md:54 (IncidentListProjection in the core-owns list), outbound-clients.md:69 (list append in the tolerated num_retries=0 item).
R6 (OQ6) Both methods upsert on the incident id (no NOT_FOUND for a missing row); append stays num_retries=0; the rebuild job is new TASK-145.12.3.
R7 (OQ7) Signatures append_row(incident), update_status(incident, status) kept; doc-15 needs (165.5, embargo 165.3, drill exclusion 165.7, product name 165.1, D37 root id) are adapter-only.
R8 (OQ8) About 340 LOC / 6 production files accepted, within the gate.
R9 (ErrorCode) No INVALID_INPUT: missing report, conversation or product is a normal state written as blank cells; UNSUPPORTED_OPERATION for another chat system, CONFIG_NOT_CONFIGURED for a missing sheet id or tenant (operation-result.md:20,:25).
Sources: Azure Materialized View pattern https://learn.microsoft.com/en-us/azure/architecture/patterns/materialized-view ; OWASP CSV Injection https://community.owasp.org/attacks/CSV_Injection ; Sheets ValueInputOption https://developers.google.com/workspace/sheets/api/reference/rest/v4/ValueInputOption ; incident.io statuses https://docs.incident.io/api-reference/incident-statuses-v1

---
<!-- COMMENTS:END -->
