---
id: TASK-25.1.6.10.2
title: >-
  Build a SpreadsheetProvider infrastructure capability (Protocol, Google
  implementation, models, settings, factory)
status: Done
assignee:
  - '@me'
created_date: '2026-09-09 15:02'
updated_date: '2026-09-09 16:33'
labels:
  - clients
  - phase-3
  - infrastructure
milestone: m-3
dependencies:
  - TASK-25.1.6.13
references:
  - decisions/dependency-injection.md
parent_task_id: TASK-25.1.6.10
priority: high
ordinal: 160000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Introduce app/infrastructure/spreadsheets/ as a new Path A infrastructure capability, mirroring app/infrastructure/drive/{provider,google,factory,models,settings}.py's exact shape. This is the foundation TASK-25.1.6.10.3 (incident) and TASK-25.1.6.10.4 (AWS spending) build on.

WHY PATH A, NOT A FEATURE ADAPTER (decided 2026-09-09, human-directed): two independent feature consumers of Sheets exist today - the incident feature (modules/incident/incident_folder.py, 4 call sites) and AWS spending reporting (modules/aws/spending.py, 1 call site). decisions/layers.md promotes to shared infrastructure on the second consumer; that second consumer is already known, so a feature-owned adapter would be pure churn. Same reasoning as TASK-25.1.6.8's Drive pivot.

NAMING (decided 2026-09-09, human-directed): the capability is vendor-neutral - app/infrastructure/spreadsheets/, SpreadsheetProvider, get_spreadsheet_provider(), SPREADSHEET_PROVIDER settings alias - matching directory/ and drive/. 'sheets' is Google vocabulary and is not used for the capability name.

SCOPE (this task only): the new infrastructure/spreadsheets/ package and its own tests. This task does NOT touch any consumer file (modules/incident/incident_folder.py, modules/aws/spending.py) and does NOT delete app/integrations/google_workspace/sheets.py - that module keeps serving its current callers until .10.3 and .10.4 migrate them.

PROTOCOL SHAPE, derived from the live consumers' actual call sites (grep-verified against modules/incident/incident_folder.py:277,307,322,345 and modules/aws/spending.py:190). All methods return OperationResult:
- warmup() -> OperationResult[None] and health_check() -> OperationResult[None], mirroring DriveProvider (health_check is fast local liveness, no API round-trip).
- read_values(spreadsheet_id, a1_range) -> OperationResult[list[list[str]]] - replaces sheets.get_values; a missing 'values' key maps to [].
- update_values(spreadsheet_id, a1_range, values) -> OperationResult[None] - replaces sheets.batch_update_values.
- append_values(spreadsheet_id, a1_range, values) -> OperationResult[None] - replaces sheets.append_values.
- read_cells(spreadsheet_id, a1_range) -> OperationResult[list[list[SheetCell]]] - replaces sheets.get_sheet(includeGridData=True). Google's includeGridData plumbing and the sheets[0].data[0].rowData walk stay inside the Google implementation; callers receive canonical cells.

NOT PORTED: sheets.batch_update (the addSheet request) - its only caller is modules/reports/google_groups.py, deleted outright by TASK-25.1.6.10.1. Do not add a batch_update / create-worksheet method with no consumer.

MODEL: a single frozen SheetCell dataclass (formatted_value: str | None, link: str | None, provider: str | None). Portability check per decisions/layers.md's two-provider rule: Microsoft Graph's workbookRange exposes text/values and formulas, so a second provider can populate formatted_value directly and link by parsing a HYPERLINK formula. Google's raw formattedValue/hyperlink keys never cross the boundary.

RANGE ADDRESSING (decided 2026-09-09, human-directed): A1 notation strings ('Sheet1', 'Sheet1!A:A', 'Sheet1!D3') cross the Protocol. A1 with a sheet!range prefix is a cross-vendor spreadsheet convention (Excel and Graph use the same addressing), not a vendor DSL like Drive's q= language, so it passes the vendor-neutrality litmus test that the retracted DriveProvider 'query' parameter failed.

DELEGATION: no delegated_user_email parameter on the Protocol. No Sheets caller passes one today, and integrations/google_workspace/client.py::_build_service already defaults the delegation subject to SRE_BOT_EMAIL. Keeping the Google auth subject out of the vendor-neutral contract is what decisions/layers.md's 2026-09-08 portability note asks for.

SCOPES: define the Sheets OAuth scope constant inside infrastructure/spreadsheets/google.py. Do NOT import it from integrations/google_workspace/sheets.py - that module is deleted by .10.4, and infrastructure/drive/google.py's import of DRIVE_SCOPES from the equally doomed google_drive.py is the wart .10.5 has to unpick. Scopes are Google-specific and belong in the Google implementation.

CLASSIFICATION - A NAMED DEVIATION THAT MUST BE HANDLED HERE (found 2026-09-09 during planning): integrations/google_workspace/client.py::classify_google_error maps only {404}, {401,403} and {429,5xx}, and RE-RAISES everything else. The Sheets 'Unable to parse range' failure that modules/incident/incident_folder.py:346 depends on is an HTTP 400, so a bare classify_google_error would let it escape the Path A boundary - the one error case a live consumer relies on. GoogleSpreadsheetProvider therefore maps HttpError status 400 whose reason contains 'Unable to parse range' onto OperationStatus.NOT_FOUND with a stable error_code before delegating everything else to classify_google_error. That is vendor error interpretation, correctly homed in the Google implementation; the caller-side SWALLOW (warn and return []) stays in incident_folder.py per TASK-25.1.6's standing instruction that the business rule must not move into the vendor layer. The shared classifier is NOT modified, so Directory/Drive/Docs/Calendar classification is untouched.

SETTINGS: SpreadsheetSettings(InfrastructureSettings) mirrors DriveSettings - provider: Literal['google'] = 'google' via SPREADSHEET_PROVIDER. No require_startup_warmup field and no server/lifespan.py wiring: DriveProvider has neither, and no consumer needs startup warmup.

FACTORY: get_spreadsheet_provider() singleton via @cache, mirroring get_drive_provider(); builds GoogleSpreadsheetProvider from integrations.google_workspace.client.get_sheets_service. Consumers resolve the provider only through this factory, never by constructing GoogleSpreadsheetProvider directly.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 app/infrastructure/spreadsheets/provider.py defines a runtime_checkable SpreadsheetProvider Protocol with exactly read_values, update_values, append_values and read_cells, all returning OperationResult; there is no warmup, no health_check, no delegated_user_email and no batch_update/add-worksheet method
- [x] #2 app/infrastructure/spreadsheets/models.py defines a single frozen SheetCell dataclass (formatted_value, link, provider); no Google response key (formattedValue, hyperlink, rowData, sheets) appears in any type or return value crossing the Protocol
- [x] #3 app/infrastructure/spreadsheets/google.py::GoogleSpreadsheetProvider implements the Protocol via integrations.google_workspace.client.get_sheets_service, owns its own SHEETS scope constant (no import from integrations.google_workspace.sheets), and keeps includeGridData plus the sheets[0].data[0].rowData walk internal
- [x] #4 No retry policy is named anywhere in the new package: every .execute() call is plain, with retry inherited from the construction-time configuration in integrations/google_workspace/client.py (TASK-25.1.6.13); there is no _NUM_RETRIES constant and no num_retries argument
- [x] #5 GoogleSpreadsheetProvider maps HttpError 400 with an 'Unable to parse range' reason onto OperationStatus.NOT_FOUND with a stable exported error code, delegates all other HttpErrors to classify_google_error, and leaves integrations/google_workspace/client.py::classify_google_error unmodified
- [x] #6 app/infrastructure/spreadsheets/settings.py::SpreadsheetSettings (InfrastructureSettings, SPREADSHEET_PROVIDER alias) and factory.py::get_spreadsheet_provider() (cached singleton) exist, mirroring infrastructure/drive's shape; server/lifespan.py is not modified and no startup warmup is wired
- [x] #7 app/integrations/google_workspace/sheets.py is untouched and still exists; no consumer file (modules/incident/incident_folder.py, modules/aws/spending.py) is modified by this task
- [x] #8 Unit tests under app/tests/unit/infrastructure/spreadsheets/ cover each Protocol method's success path, the parse-range 400 to NOT_FOUND mapping, at least one classify_google_error path, an unmapped HttpError propagating, cell mapping for a row with and without a hyperlink, an empty/absent values response, plus settings and factory construction
- [x] #9 mypy, ruff, and app/bin/check_sdk_typing.py pass for the new package
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
REVISION NOTE (2026-09-09, human review round 2): this plan replaces the first draft. Three changes - warmup/health_check dropped from the Protocol, per-call num_retries dropped in favour of construction-time retry (now TASK-25.1.6.13, a dependency of this task), and the drive/directory shape is treated as a template to improve on rather than to copy verbatim.

GROUNDING (read/grep/empirically verified against main, 2026-09-09)
Call sites the Protocol must serve, and the exact SDK chains they use today (app/integrations/google_workspace/sheets.py):
- get_values -> service.spreadsheets().values().get(spreadsheetId, range, fields); consumer incident_folder.py:307 wraps the result in dict() and reads .get('values', []).
- get_sheet -> service.spreadsheets().get(spreadsheetId, ranges, includeGridData); consumer incident_folder.py:345 walks response['sheets'][0]['data'][0]['rowData'] and reads values[n]['formattedValue'] / ['hyperlink'].
- batch_update_values -> service.spreadsheets().values().batchUpdate(spreadsheetId, body={'valueInputOption':..., 'data':[{'range':..., 'values':...}]}); consumers incident_folder.py:322 and spending.py:190.
- append_values -> service.spreadsheets().values().append(spreadsheetId, range, body, valueInputOption='USER_ENTERED', insertDataOption='INSERT_ROWS'); consumer incident_folder.py:277 passing body={'majorDimension':'ROWS','values':[...]} containing =HYPERLINK(...) formulas.
- batch_update (addSheet) -> only consumer is modules/reports/google_groups.py, deleted by TASK-25.1.6.10.1. NOT PORTED.
No consumer passes delegated_user_email. client.get_sheets_service(scopes, delegated_user_email=None) already exists, stub-typed to SheetsResource; _build_service defaults the delegation subject to settings.SRE_BOT_EMAIL.
Guardrail baselines checked: neither app/bin/baselines/sdk_typing_antipatterns.txt nor deprecated_infra_client_imports.txt lists any file this task creates or touches, so no baseline edits are required or possible.
Template with named exceptions: infrastructure/drive/ is the structural template (six-file split, settings/factory shape, _call/_map_sdk_exception helpers). It is NOT copied wholesale - see the two deviations below, both human-directed.

DEVIATION 1 - NO warmup() AND NO health_check() ON THIS PROTOCOL (human-directed 2026-09-09)
Evidence: DriveProvider.warmup(), DriveProvider.health_check() and DirectoryProvider.health_check() have ZERO production callers; GoogleDriveProvider.health_check() returns success unconditionally without touching the service, so it cannot fail. Only DirectoryProvider.warmup() is really used (server/lifespan.py:172 and modules/dev/google.py:55). No accepted decision record requires these methods: decisions/dependency-injection.md's eager startup warmup is about the DI registry INVOKING EVERY PROVIDER at boot (construction/validation), not a method on each capability contract, and decisions/health-checks.md is exclusively about container/ECS/ALB/Route53 HTTP checks.
Practicality clinches it here: the Sheets API exposes no listing or about endpoint reachable without a spreadsheet id, so there is no cheap connectivity probe to implement - any warmup() would either be a no-op or need a configured probe spreadsheet.
So SpreadsheetProvider declares neither. No lifespan wiring, no require_startup_warmup setting. The broader question (should warmup/liveness belong to the vendor SDK client rather than each capability) is registered as TASK-82 and must NOT be pre-empted here by inventing a Sheets-specific answer.

DEVIATION 2 - NO num_retries IN THIS PACKAGE (human-directed 2026-09-09)
Empirically verified against google-api-python-client 2.198.0: HttpRequest.execute(self, http=None, num_retries=0) is the SDK's built-in retry primitive (googleapiclient.http._retry_request does randomized exponential backoff over 429/5xx), and discovery.build(..., num_retries=N) applies ONLY to the discovery-document fetch (discovery.py:439), never to API calls. The construction-time seam is build(requestBuilder=...), which is stored as Resource._requestBuilder and used for every request and every nested sub-resource.
decisions/outbound-clients.md wants SDK-native resilience 'configured once' at construction, so repeating num_retries at every .execute() - as infrastructure/directory/google.py and infrastructure/drive/google.py do today across 12 call sites with two duplicate _NUM_RETRIES constants - is existing drift, not the target. This package must not become the third copy.
TASK-25.1.6.13 configures retry once in integrations/google_workspace/client.py via requestBuilder and removes the 12 per-call arguments. It is a dependency of this task, so this provider is born compliant: every .execute() here is PLAIN, and the package defines no retry constant and names no retry policy. If .13 slips, this package still ships correct - it simply inherits whatever client.py provides, which is exactly the point of moving the decision there.

STEP 1 - models.py
app/infrastructure/spreadsheets/models.py::SheetCell, frozen dataclass mirroring DriveFile's shape:
  formatted_value: str | None
  link: str | None = None
  provider: str | None = None
One canonical cell type for grid reads. No Google key names (formattedValue, hyperlink, rowData, effectiveValue) appear in the model or its public contract.

STEP 2 - provider.py
app/infrastructure/spreadsheets/provider.py::SpreadsheetProvider, @runtime_checkable Protocol, docstring conventions from infrastructure/drive/provider.py (OperationResult-wrapped, no exceptions cross the boundary). Exactly four methods:
  read_values(spreadsheet_id: str, a1_range: str) -> OperationResult[list[list[str]]]
  update_values(spreadsheet_id: str, a1_range: str, values: list[list[Any]]) -> OperationResult[None]
  append_values(spreadsheet_id: str, a1_range: str, values: list[list[Any]]) -> OperationResult[None]
  read_cells(spreadsheet_id: str, a1_range: str) -> OperationResult[list[list[SheetCell]]]
No warmup, no health_check, no delegated_user_email, no fields, no batch_update. The a1_range docstring states the accepted forms ('Sheet1', 'Sheet1!A:A', 'Sheet1!D3') and notes A1 addressing is a cross-vendor spreadsheet convention, not a vendor query language. The read_cells docstring states that a range naming a sheet that does not exist yields OperationStatus.NOT_FOUND with error_code RANGE_NOT_FOUND, so callers distinguish 'nothing to read' from a failed read without inspecting provider messages.

STEP 3 - google.py::GoogleSpreadsheetProvider
Constructor takes injected get_service: Callable[[list[str], str | None], SheetsResource] plus spreadsheet_settings: SpreadsheetSettings, mirroring GoogleDriveProvider.__init__. Module constants: SHEETS_SCOPES = ['https://www.googleapis.com/auth/spreadsheets'] DEFINED HERE (never imported from integrations/google_workspace/sheets.py, which .10.4 deletes - infrastructure/drive/google.py's import of DRIVE_SCOPES from the equally doomed google_drive.py is the wart .10.5 has to unpick; do not repeat it), _VALUE_INPUT_OPTION = 'USER_ENTERED', _INSERT_DATA_OPTION = 'INSERT_ROWS'. NO retry constant (Deviation 2).
Internal helpers mirror GoogleDriveProvider's _call / _map_sdk_exception / _service shape. TYPE_CHECKING import of SheetsResource from googleapiclient._apis.sheets.v4 with the same pyright ignore comment used in client.py; keep the Literal casts sheets.py applies to valueInputOption/insertDataOption.
Method bodies, each preserving today's request shape and calling .execute() with NO arguments:
  read_values: values().get(spreadsheetId=..., range=a1_range).execute(); map response.get('values', []) to list[list[str]] with str() coercion per cell. An absent 'values' key yields [].
  update_values: values().batchUpdate(spreadsheetId=..., body={'valueInputOption': _VALUE_INPUT_OPTION, 'data': [{'range': a1_range, 'values': values}]}); return success with no data.
  append_values: values().append(spreadsheetId=..., range=a1_range, body={'majorDimension': 'ROWS', 'values': values}, valueInputOption=..., insertDataOption=...). The 'majorDimension'/'values' body wrapper moves in here so callers pass a plain values matrix. USER_ENTERED is what keeps the incident list's =HYPERLINK(...) formulas interpreted rather than written as literal text - do not switch it to RAW.
  read_cells: spreadsheets().get(spreadsheetId=..., ranges=a1_range, includeGridData=True); walk sheets[0].data[0].rowData defensively (each level missing/empty yields []) and build SheetCell(formatted_value=cell.get('formattedValue'), link=cell.get('hyperlink'), provider='google') per cell via a private _build_cell. incident_folder.py's index chain moves in here; returning [] instead of raising TypeError on a response with no sheets/data/rowData is deliberate hardening - name it in the PR.

STEP 4 - the 400 classification gap (the one non-mechanical piece)
integrations/google_workspace/client.py::classify_google_error maps only {404}, {401,403}, {429,5xx} and RAISES for anything else - including 400. 'Unable to parse range' is a 400 and is the exact outcome modules/incident/incident_folder.py:346 depends on, so a bare classify_google_error would let it escape the Path A boundary.
_map_sdk_exception does, in order:
  1. if int(exc.resp.status) == 400 and 'Unable to parse range' in str(exc): return OperationResult.error(status=OperationStatus.NOT_FOUND, message=str(exc), error_code=RANGE_NOT_FOUND, provider='google', operation=operation)
  2. otherwise delegate to classify_google_error(exc) exactly as GoogleDriveProvider does, letting genuinely unmapped statuses propagate per decisions/outbound-clients.md's 'programmer errors crash loudly' rule.
str(exc) is the right probe: googleapiclient's HttpError renders resp.reason into its string form, and the existing helper in app/tests/modules/incident/test_incident_folder.py:418 builds errors that way, so .10.3's migrated tests work against the same fixture shape.
RANGE_NOT_FOUND is a module-level constant exported from the package __init__, NOT a bare string. .10.3's caller-side swallow checks status is NOT_FOUND and error_code == RANGE_NOT_FOUND; it must never string-match a provider message.
integrations/google_workspace/client.py is NOT modified. Whether 400s deserve a mapped family in the shared classifier is registered on TASK-25.1.6.11, not decided here.

STEP 5 - settings.py
SpreadsheetSettings(InfrastructureSettings): provider: Literal['google'] = Field(default='google', alias='SPREADSHEET_PROVIDER', description=...). get_spreadsheet_settings() via @lru_cache(maxsize=1). Mirrors DriveSettings, which also has no require_startup_warmup - consistent with Deviation 1.

STEP 6 - factory.py
build_google_spreadsheet_provider(*, get_service, spreadsheet_settings) -> SpreadsheetProvider (pure constructor, testable) and get_spreadsheet_provider() -> SpreadsheetProvider as an @cache singleton dispatching on spreadsheet_settings.provider, raising ValueError for anything other than 'google'. get_service is integrations.google_workspace.client.get_sheets_service passed directly (its signature already matches Callable[[list[str], str | None], SheetsResource]); no partial and no scope pre-binding, because the scope constant lives in google.py.

STEP 7 - __init__.py
Re-export SheetCell, SpreadsheetProvider, SpreadsheetSettings, get_spreadsheet_provider, get_spreadsheet_settings and RANGE_NOT_FOUND with an __all__, mirroring infrastructure/drive/__init__.py. No side effects, no registration: this is a capability, not a plugin.

STEP 8 - tests (app/tests/unit/infrastructure/spreadsheets/, mirroring the drive test tree's three-file split)
test_google_spreadsheet_provider.py - the fake SheetsResource is a MagicMock chain standing in for the SDK only (the SDK is not the subject under test), as tests/unit/infrastructure/drive/test_google_drive_provider.py does; the subject is the real GoogleSpreadsheetProvider. Reuse that file's local FakeResp/HttpError helper convention rather than centralizing it.
  read_values: success returns the values matrix and asserts spreadsheetId/range reached the SDK; an absent 'values' key returns []; non-string cells are coerced.
  update_values: asserts the exact body dict (valueInputOption plus a single data entry with range and values) and a success result carrying no data.
  append_values: asserts range, the {'majorDimension':'ROWS','values':...} body, valueInputOption='USER_ENTERED' and insertDataOption='INSERT_ROWS'; one case passes a row containing an =HYPERLINK(...) string to pin that formulas are sent verbatim under USER_ENTERED.
  read_cells: a two-row grid where one cell has a hyperlink and one does not maps to SheetCell link=... / link None; includeGridData=True and ranges reached the SDK; responses missing 'sheets', missing 'data' and missing 'rowData' each return [] rather than raising.
  classification: a 400 whose reason contains 'Unable to parse range' returns NOT_FOUND with error_code RANGE_NOT_FOUND on read_cells AND on read_values; a 404 and a 429 route through classify_google_error to NOT_FOUND/TRANSIENT_ERROR with retry_after preserved; a 400 with an unrelated reason PROPAGATES (pytest.raises(HttpError)) proving unmapped statuses still crash loudly.
  retry: assert .execute() is called with NO arguments, pinning that this package makes no retry decision (the inverse of the drive/directory assertion, and the guard against the constant creeping back in).
  Protocol surface: assert the provider has no warmup and no health_check attribute, pinning Deviation 1 against future copy-paste from infrastructure/drive.
test_spreadsheet_settings.py - default provider is 'google'; SPREADSHEET_PROVIDER honoured via monkeypatch.setenv (never a pyproject env block, per decisions/testing.md); get_spreadsheet_settings caching.
test_factory.py - mirrors tests/unit/infrastructure/drive/test_factory.py: cache_clear in the fixture, get_spreadsheet_provider returns a GoogleSpreadsheetProvider built from get_sheets_service, isinstance against the runtime_checkable Protocol, singleton identity across two calls, and an unsupported provider value raising ValueError.

STEP 9 - guardrails
cd app && uv run pytest tests/unit/infrastructure/spreadsheets -q; uv run mypy infrastructure/spreadsheets; uv run ruff check .; uv run python bin/check_sdk_typing.py. Confirm grep finds no import of integrations.google_workspace.sheets under infrastructure/, and no num_retries under infrastructure/spreadsheets/.

AC TRACEABILITY
AC#1 (four-method Protocol, no warmup/health_check/delegation/batch_update) -> Step 2 and Deviation 1; proven by test_factory.py's runtime_checkable isinstance assertion plus Step 8's explicit no-warmup/no-health_check assertion.
AC#2 (SheetCell, no Google keys crossing) -> Steps 1, 3 (_build_cell); proven by read_cells mapping tests.
AC#3 (Google impl via get_sheets_service, owns its scope constant, grid walk internal) -> Steps 3, 6, 9; proven by the provider tests plus the Step 9 grep.
AC#4 (no retry policy in this package) -> Deviation 2, Step 3; proven by Step 8's plain-execute assertion and the Step 9 grep.
AC#5 (400 parse-range -> NOT_FOUND, others via classify_google_error, shared classifier untouched) -> Step 4; proven by the four classification tests including the propagating unmapped 400.
AC#6 (settings + cached factory, lifespan untouched, no startup warmup) -> Steps 5, 6, Deviation 1.
AC#7 (sheets.py and consumers untouched) -> scope discipline; proven by the PR diff containing no file under integrations/ or modules/.
AC#8 (test coverage) -> Step 8.
AC#9 (gates) -> Step 9.

TEST MATRIX
Happy path: all four data methods against a stubbed SheetsResource chain.
Boundary: absent 'values'; empty grid at each of the three nesting levels; a cell with no hyperlink; non-string cell values; a formula-bearing append row.
Failure: parse-range 400 -> NOT_FOUND/RANGE_NOT_FOUND; 404 -> NOT_FOUND; 429 -> TRANSIENT_ERROR with retry_after; unmapped 400 -> propagates.
Shape guards: .execute() receives no arguments; the provider exposes no warmup/health_check.
Not covered (intentional): the real Google Sheets API (no network per decisions/testing.md), consumer behavior (.10.3/.10.4), retry behavior itself (owned by TASK-25.1.6.13), and lifespan wiring (none exists).

ASSUMPTIONS AND DOUBTS FOR HUMAN REVIEW
(a) read_values coerces cells to str to satisfy list[list[str]]. Under Google's default FORMATTED_VALUE render option this is expected to be a no-op for the incident list; if a consumer later needs typed values that is a Protocol change, not a cast at the caller.
(b) The parse-range probe is a substring match on the vendor's error text. That is vendor error interpretation, correctly homed in the Google implementation, but string-fragile: a Google wording change would silently turn a NOT_FOUND back into a propagating 400. Mitigated by dedicated tests and by .10.3 raising rather than silently returning [] on unexpected failures.
(c) Dropping warmup/health_check makes SpreadsheetProvider structurally different from DirectoryProvider and DriveProvider. That inconsistency is intentional and temporary - TASK-82 decides the convention and reconciles all three. If TASK-82 lands first and rules that capabilities keep these methods, this Protocol must be revisited before .10.3 builds on it.

BLAST RADIUS AND ROLLBACK
Additive only. Six new files under app/infrastructure/spreadsheets/ and three new test files; nothing existing is imported, registered, or modified - no consumer, no settings aggregator, no lifespan, no terraform, no CI. The new package is dead code until TASK-25.1.6.10.3 imports it, so this PR cannot change runtime behavior. A single git revert removes it cleanly.

SIZE GATE
Production: __init__.py, models.py, provider.py, google.py, settings.py, factory.py = 6 new files, roughly 200 LOC (down from the first draft after dropping warmup/health_check), one subsystem, no consumer touched, no mixed refactor. Comfortably inside the single-PR gate; no decomposition needed.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented app/infrastructure/spreadsheets: runtime-checkable four-method SpreadsheetProvider Protocol, frozen SheetCell model, Google implementation with local Sheets scope and canonical grid mapping, parse-range NOT_FOUND/RANGE_NOT_FOUND handling, partitioned settings, cached factory, and package exports. Added focused provider, settings, and factory tests. Verified ACs 1-9 individually. Evidence: from app, uv run pytest tests/unit/infrastructure/spreadsheets -q -> 22 passed; from app, uv run mypy with a fresh cache on infrastructure/spreadsheets -> no issues; from app, uv run ruff check . -> passed; from app, uv run python bin/check_sdk_typing.py -> passed; user reports make test -> all green; scope grep checks passed. Remaining human verification: review the change and merge/close the task; no runtime Google API or smoke validation was run.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @task-planner
created: 2026-09-09 15:28
---
PLAN REVISED AFTER HUMAN REVIEW 2026-09-09. All three open questions answered; the plan and ACs were rewritten, not patched. Recording the AC replacement explicitly.

1. WARMUP AND HEALTH_CHECK DROPPED FROM THE PROTOCOL (was AC#1, plan Steps 2-3, doubt (a)). Human instinct: warmup belongs closer to the configured vendor SDK client than to each capability service. The evidence supports it - DriveProvider.warmup, DriveProvider.health_check and DirectoryProvider.health_check have ZERO production callers, GoogleDriveProvider.health_check returns success unconditionally without touching the service, and the only production health_check() call in the app is on the i18n translation service. No accepted record requires these methods: decisions/dependency-injection.md's eager startup warmup is about the DI registry invoking every provider at boot, and decisions/health-checks.md is exclusively about container/ECS/ALB/Route53 HTTP checks. Sheets also has no cheap probe endpoint reachable without a spreadsheet id, so the method would have been ceremony. The broader convention question is NOT decided here - it is TASK-82, which also owns reconciling Directory and Drive.

2. NO num_retries IN THIS PACKAGE (was AC#7's test list and doubt (b)). Verified empirically against google-api-python-client 2.198.0 rather than assumed: HttpRequest.execute(self, http=None, num_retries=0) IS the SDK's built-in retry primitive (googleapiclient.http._retry_request, randomized exponential backoff over 429/5xx), so it is not hand-rolled retry - but discovery.build(..., num_retries=N) applies ONLY to the discovery-document fetch (discovery.py:439) and would be a silent no-op for API calls. The real construction-time seam is build(requestBuilder=...), stored as Resource._requestBuilder (discovery.py:1442), used for every request (discovery.py:1266) and propagated to nested resources (discovery.py:1566). Since decisions/outbound-clients.md wants resilience 'configured once' at construction, the 12 per-call num_retries arguments and two duplicate _NUM_RETRIES constants in infrastructure/directory/google.py and infrastructure/drive/google.py are existing drift; this package must not become the third copy. NEW TASK-25.1.6.13 moves the configuration into client.py and removes the drift, and is now a dependency of this task. Every .execute() here is plain, and a test asserts it receives no arguments so the constant cannot creep back in.

3. THE DRIVE/DIRECTORY PACKAGES ARE A STRUCTURAL TEMPLATE, NOT A BEHAVIORAL ONE. Per the human's standing instruction that current code may be outdated and drift must not be carried forward, the plan now names its two deliberate deviations from infrastructure/drive/ up front and pins both with tests, so a future reader sees intent rather than an inconsistency to 'fix' by copying the older packages.

NET EFFECT ON SIZE: roughly 200 production LOC, down from 230. Still one PR.
---

author: @task-planner
created: 2026-09-09 16:33
---
ORDER-OF-IMPLEMENTATION VALIDATION (2026-09-09): this task shipped (Done) before its declared dependency TASK-25.1.6.13 ("Configure google-api-python-client retry once at construction and retire the per-call num_retries drift"). Validated: no conflict resulted. Every .execute() call in app/infrastructure/spreadsheets/google.py (lines 83,116,138,148) was already written with no num_retries argument and the package defines no retry constant, per this task's own Deviation 2/AC#4 - i.e. it was already born compliant with TASK-25.1.6.13's target end state rather than becoming a third copy of the directory/drive per-call retry drift. The only practical consequence of the reversal is a temporary one: Sheets calls made through GoogleSpreadsheetProvider currently have zero retry on 429/5xx (unlike Drive/Directory's num_retries=3) until TASK-25.1.6.13 lands and configures retry once at construction in integrations/google_workspace/client.py - at which point this package inherits it automatically with no code change here. The dependencies field is left as-is (historical record of intended order); TASK-25.1.6.13's description/plan were updated accordingly. No action needed on this task.
---
<!-- COMMENTS:END -->
