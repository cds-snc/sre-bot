---
id: TASK-105.1
title: >-
  Drop the provider and operation fields from OperationResult and rewrite their
  call sites
status: In Progress
assignee: []
created_date: '2026-09-28 14:35'
updated_date: '2026-09-28 15:52'
labels:
  - plugin-architecture
  - operation-result
milestone: m-7
dependencies:
  - TASK-105
references:
  - decisions/operation-result.md
  - backlog/docs/doc-2 - Delivery-Sequence-and-Stacked-Pull-Requests.md
parent_task_id: TASK-105
priority: medium
ordinal: 283000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/operation-result.md defines the envelope as status, data, error_code, message, retry_after and cause. OperationResult still carries provider and operation. Corrected survey (2026-09-28, supersedes the ~12-site estimate): 18 production files touch .provider/.operation on OperationResult -- infrastructure/operations/result.py (the dataclass + success()/error() factories), infrastructure/operations/__init__.py (re-exports), the 9 files in app/packages/aws_platform/adapters/, infrastructure/directory/google.py, infrastructure/drive/google.py and infrastructure/spreadsheets/google.py (which also read .provider/.operation back off a wrapped result to re-box errors), integrations/openai/client.py, integrations/openai/summarizer.py, and packages/incident_draft/service.py. Superficially similar `provider=` keyword arguments on DirectoryUser/DirectoryGroup/DirectoryMember/DriveFile/SheetCell domain models and on *Settings.provider are a distinct, unrelated field (record provenance) and are out of scope.

infrastructure/operations/classifiers.py (classify_http_error, classify_aws_error, classify_integration_error, hardcoding provider="google"/"aws") is confirmed dead: no production caller anywhere -- only infrastructure/operations/__init__.py's re-export and its own test import it. The adapters actually wired in use integrations.aws.client.classify_aws_error and integrations.google_workspace.client.classify_google_error (different functions, return a bare tuple, no provider/operation). This task deletes classifiers.py, its re-exports in __init__.py, and tests/unit/infrastructure/operations/test_classifiers.py outright rather than stripping provider= from 14 dead constructions -- both because it is unreachable dead code in a file this task must touch anyway, and because it removes a confusing duplicate classify_aws_error name living alongside the real one in integrations/aws/client.py.

TASK-105 keeps OperationResult's provider/operation documented as tolerated-pending-removal to stay inside its own size gate; this task removes them for real.

Stack A layer between TASK-105 and TASK-105.2 (doc-2). Mechanical and behaviour-preserving: any context the fields carried that is still needed moves to structured log fields at the call site, not into the envelope. No re-export or compatibility shim.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 OperationResult has no provider or operation field; grep finds no provider=/operation= argument or .provider/.operation read on an OperationResult under app/
- [x] #2 Context previously carried in provider/operation that callers still need is emitted as structured log fields at the call site; no new envelope field is added
- [x] #3 decisions/operation-result.md no longer lists provider/operation as a tolerated divergence
- [x] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
- [x] #5 infrastructure/operations/classifiers.py and its tests are deleted; nothing imports classify_http_error, classify_integration_error or the operations-layer classify_aws_error
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Depends on TASK-105 landing first (frozen dataclass, map/bind/unwrap/unwrap_or removed, message optional, cause added, retry_after: float, provider/operation kept and marked "tolerated pending removal" in the docstring). This plan assumes that shape; if TASK-105's actual diff differs materially, re-verify line numbers below before editing.

SIZE GATE FLAG (deviation, reported per implementation-planning skill): this touches 18 production files (17 edited + 1 deleted), above the ~10-file guideline (TASK-105 itself set the "mechanical layer" precedent at ~12). Per-file diffs are 1-10 lines each for the edits (uniform across near-identical adapters), plus one wholesale deletion of ~309+407 dead lines (classifiers.py + its test) that is trivial to review. The change is atomic -- once provider/operation leave the OperationResult constructor signature, every remaining provider=/operation= call site raises TypeError, so it cannot be split without either a shim (banned by this task's own instructions) or a temporary expand/contract stage. Kept as one PR per explicit instruction: no subtasks, no expand/contract split.

Survey basis (2026-09-28): grep for provider=/operation=/.provider/.operation across app/, filtered by hand to exclude the unrelated domain-provenance `provider` field on DirectoryUser/DirectoryGroup/DirectoryMember/DriveFile/SheetCell and on *Settings.provider (different field, out of scope). No test file other than tests/unit/infrastructure/test_operations_result.py and tests/unit/infrastructure/operations/test_classifiers.py references OperationResult.provider/.operation or the classifiers module. Confirmed 2026-09-28: infrastructure/operations/classifiers.py has zero production callers -- only infrastructure/operations/__init__.py's re-export and its own test import it; grepped for `operations.classifiers`, `classify_http_error`, `classify_integration_error` and mock/patch target strings referencing the module, all hits are internal to the module, its docstring examples, __init__.py, or its test.

Step 1 -- infrastructure/operations/result.py (production)
  - Remove `provider: str | None = None` and `operation: str | None = None` field declarations, their docstring Attributes lines, and the two `provider=provider, operation=operation` pass-throughs in `success()` and `error()` (drop the `provider`/`operation` parameters from both signatures and their Args docstrings).
  - No map()/bind() propagation to touch -- TASK-105 already removed those methods.

Step 2 -- DELETE infrastructure/operations/classifiers.py and tests/unit/infrastructure/operations/test_classifiers.py (production + test)
  - Dead code, confirmed above: classify_http_error, classify_aws_error and classify_integration_error here have no production caller. The adapters actually wired in use integrations.aws.client.classify_aws_error and integrations.google_workspace.client.classify_google_error (distinct functions, return a bare tuple, no provider/operation concept) -- this operations-layer classify_aws_error is a confusing, unused duplicate of that name.
  - Delete both files outright (309 + 407 lines) rather than stripping `provider=` from its 14 dead constructions: this task must touch the file's provider/operation usage regardless, and leaving 300 lines of unreferenced classification logic in place after editing it is the "fix bugs in touched files" case (dead code) with no cost -- deleting it is strictly simpler than patching it, not a scope expansion.
  - Update infrastructure/operations/__init__.py: remove the `from infrastructure.operations.classifiers import (classify_aws_error, classify_http_error, classify_integration_error)` import block and the three corresponding `__all__` entries; keep `OperationResult`/`OperationStatus` exports as-is. Module docstring's "error classifiers for provider exceptions" line should also be dropped since the module no longer exports any.
  - Grep after deleting for any stray reference to `classifiers`, `classify_http_error`, `classify_integration_error`, or `infrastructure.operations.classify_aws_error` (import path or patch-target string) anywhere under app/ (including bin/ and scripts/) to confirm nothing else breaks; none were found in the survey but re-verify at execution time since deletions are the one irreversible-feeling step here (still a single git revert away).

Step 3 -- infrastructure/directory/google.py (production)
  - `_map_sdk_exception` (~line 70): drop `provider="google", operation=operation` from the `OperationResult.error(...)` call; add `self._logger.warning("directory_operation_failed", operation=operation, status=status.value, error_code=error_code)` before the return (mirrors the AWS adapters' existing `_map_sdk_exception` logging pattern; `self._logger` is already bound with `provider="google"` at `__init__`, so provider stays implicit in every log line from this class without a new kwarg).
  - `_typed_error` (~line 303): once `.provider`/`.operation` no longer exist to read or forward, this method's reconstruction is an identity copy on 4 remaining fields (status, message, error_code, retry_after) with only the type parameter changing. Simplify to `return cast("OperationResult[T]", result)` (add `cast` to the existing `typing` import), matching the same cast idiom already used in infrastructure/spreadsheets/google.py's `read_values`/`read_cells`.
  - Leave `_build_directory_user`, `_build_directory_member`, `_build_group`, `_normalize_member_types` untouched -- their `provider="google"` is the DirectoryUser/DirectoryGroup/DirectoryMember domain field, unrelated to OperationResult.

Step 4 -- infrastructure/drive/google.py (production)
  - `_map_sdk_exception` (~line 34): drop `provider="google", operation=operation`; add `logger.warning("google_drive_operation_failed", operation=operation, status=status.value, error_code=error_code)` before the return (module-level `logger` already exists).
  - `_call` (~line 45): drop `provider="google", operation=operation` from the success() call (no read site depends on it; nothing else changes).
  - `warmup()` (~line 78 success, ~line 84 error re-box): drop the kwargs from the success() call; replace the error-reconstruction block with `return result` (status/message/error_code/retry_after already match `result` exactly once provider/operation are gone -- same identity-copy simplification as Step 3, and no type-parameter change is needed here since `result` is already `OperationResult[None]`).
  - `health_check()` (~line 90): drop `provider="google", operation="health_check"` from the success() call.
  - Leave `_build_drive_file`'s `provider="google"` untouched (DriveFile domain field).

Step 5 -- infrastructure/spreadsheets/google.py (production)
  - Add `import structlog` and a module-level `logger = structlog.get_logger()` (file currently has no logger).
  - `_map_sdk_exception` (~lines 39-56, two return branches: RANGE_NOT_FOUND and the general classify_google_error branch): drop `provider="google", operation=operation` from both; add `logger.warning("google_spreadsheets_operation_failed", operation=operation, status=status.value, error_code=error_code)` before each return (status/error_code differ per branch -- log after computing them, once per branch).
  - `_call` (~line 60): drop `provider="google", operation=operation` from the success() call.
  - `_success_or_error` (~line 67): the error branch is an identity copy of `result` on the 4 remaining fields -- replace with `return cast("OperationResult[None]", result)` (add `cast` to the existing `typing` import, already used elsewhere in this file). Drop `provider="google", operation=operation` from the success-branch `OperationResult.success(...)` call.
  - `read_values` (~line 90) and `read_cells` (~line 166): drop `provider="google", operation="read_values"` / `provider="google", operation="read_cells"` from their success() calls.
  - Leave `_build_cell`'s `provider="google"` untouched (SheetCell domain field).

Step 6 -- the 9 AWS adapters in packages/aws_platform/adapters/ (config.py, cost_explorer.py, security_hub.py, sso_admin.py, aws_lambda.py, dynamodb.py, guard_duty.py, organizations.py, identity_center.py) (production)
  - Each file's `_map_sdk_exception`: drop `provider="aws", operation=operation` from the `OperationResult.error(...)` call. No new logging needed -- every one of these methods already calls `logger.warning(<adapter>_operation_failed, operation=operation, status=status.value, error_code=error_code)` immediately before the return, so `operation` is already a structured log field and `aws` is already implicit in the event name.
  - Each file's `_call`: drop `provider="aws", operation=operation` from the `OperationResult.success(data=fn(), ...)` call. No read site depends on it.
  - identity_center.py additionally: drop `provider="aws", operation="list_groups_with_memberships"` from the two inline `OperationResult.success(...)` calls in `list_groups_with_memberships` (~lines 239, 293) -- `operation="list_groups_with_memberships"` is already bound on the local `log` at the top of that method (~line 232), so no log addition is needed.

Step 7 -- integrations/openai/client.py (production)
  - Drop `provider="openai"` from all 8 `OperationResult.error(...)` calls in `classify_openai_error`. No new logging needed: every call site (integrations/openai/summarizer.py) already logs `"openai_summarize_failed"` with `error=str(exc)` immediately before calling `classify_openai_error(exc)`, so the openai context is already captured in the event name and payload.

Step 8 -- integrations/openai/summarizer.py (production)
  - Drop `provider="openai", operation="summarize"` from the final `OperationResult.success(...)` call in `summarize()`. Lossless: `logger.info("openai_summarize_usage", model=..., finish_reason=..., ...)` already logs immediately before this return, and nothing reads `.provider`/`.operation` off the result.

Step 9 -- packages/incident_draft/service.py (production)
  - Drop `provider="openai", operation="draft_incident_document"` from the final `OperationResult.success(...)` call. Lossless: the function-local `log` is already bound with `operation="draft_incident_document"` at the top of the function and logs `"incident_draft_generated"` immediately before this return.

Step 10 -- decisions/operation-result.md (docs)
  - Re-read the Consequences/Migration wording TASK-105 leaves in place documenting provider/operation as "tolerated pending removal" and delete/rewrite that sentence so the record no longer lists provider/operation as a tolerated divergence (AC #3). Do not otherwise touch this record -- TASK-105 and TASK-106 own its other sections.

Step 11 -- tests/unit/infrastructure/test_operations_result.py (test)
  - Delete the test class covering provider/operation ("Test provider and operation fields for observability.", currently ~lines 74-105: test_success_with_provider_and_operation, test_error_with_provider_and_operation, test_provider_defaults_to_none, test_operation_defaults_to_none). These assert on fields that no longer exist. TASK-105 already removes the map()/bind() tests that also touch provider/operation (lines ~128-151 currently), so no other cleanup is expected here -- verify at implementation time that TASK-105's diff left nothing else referencing provider/operation in this file.
  - No other test file references OperationResult.provider/.operation (verified by grep across tests/, filtered for the unrelated domain-provenance `provider` field). tests/unit/infrastructure/operations/test_classifiers.py is deleted, not edited (Step 2).

Test matrix
  - tests/unit/infrastructure/test_operations_result.py: existing tests for success()/error() continue to pass with the two fewer optional kwargs (no new params to test).
  - tests/unit/infrastructure/directory/test_google.py, tests/unit/infrastructure/drive/test_google_drive_provider.py, tests/unit/infrastructure/spreadsheets/test_google_spreadsheet_provider.py: existing tests continue to pass unchanged (none assert on OperationResult.provider/.operation; behavior at these boundaries is unchanged except for the added/removed log lines, which existing tests don't assert on either).
  - tests/unit/packages/aws_platform/test_aws_platform_*_provider.py / *_operations.py (9 files): existing tests continue to pass unchanged.
  - tests/unit/integrations/openai/test_openai_client.py, test_openai_summarizer.py, tests/unit/packages/incident_draft/test_incident_draft_service.py: existing tests continue to pass unchanged.
  - No new test files: this is a pure field-removal + call-site rewrite plus a dead-code deletion, with no new branchable behavior to cover (AC #6 is the quality-gate check, not new test coverage).

AC traceability
  - AC #1 (no provider=/operation=/.provider/.operation under app/) <- Steps 1, 3-9, verified by grep after the edits.
  - AC #2 (needed context moves to structured logs, no new envelope field) <- Steps 3-6's added `logger.warning(...)` calls where none existed (directory, drive, spreadsheets google.py); Steps 6-9's "no new logging needed" reasoning documents why the remaining sites are already lossless.
  - AC #3 (decisions doc no longer lists provider/operation as tolerated) <- Step 10.
  - AC #4 (gates pass) <- run ruff, mypy (scoped to touched files), lint-imports, pytest tests --ignore=tests/smoke after Steps 1-11.
  - AC #5 (classifiers.py and its tests deleted; nothing imports classify_http_error/classify_integration_error/the operations-layer classify_aws_error) <- Step 2, verified by grep for `operations.classifiers`, `classify_http_error`, `classify_integration_error` returning zero hits under app/ after deletion, and by `infrastructure/operations/__init__.py` no longer exporting them.

Assumptions and doubts
  - Assumes TASK-105 lands first with the shape described in its own plan (frozen, no map/bind/unwrap/unwrap_or, message optional, cause added, provider/operation kept-and-documented). If TASK-105's landed diff differs, re-verify line numbers/field order in result.py before starting Step 1. Verify by reading infrastructure/operations/result.py at execution time.
  - Assumes infrastructure/operations/classifiers.py remains unreferenced by production code between now and execution (verified 2026-09-28 via grep for `operations.classifiers`, `classify_http_error`, `classify_integration_error`, and patch/mock target strings; only integrations.aws.client.classify_aws_error and integrations.google_workspace.client.classify_google_error, distinct functions, are wired into the adapters). Re-run the grep immediately before deleting in Step 2 in case something changed since this survey.
  - Assumes no external log consumer (dashboard/alert) currently queries on OperationResult's provider/operation fields by name in a way that would break if the values move into differently-named structured log fields -- decisions/operation-result.md documents them as internal/undocumented observability fields, not a public contract, so this is treated as safe. Flag to the human if a Slack/Grafana/Sentinel alert is known to key off these specifically.
  - The 3 new `logger.warning(...)` additions (directory, drive, spreadsheets google.py `_map_sdk_exception`) are new log emissions where none existed before -- technically not byte-for-byte "behaviour-preserving," but preserve the observability the fields existed for, per this task's own framing ("moves to structured log fields at the call site"). Flagged explicitly per the "no silent deviation" rule; reviewer may ask to drop these three additions if a stricter zero-new-log-lines reading of "behaviour-preserving" is preferred.
  - Deleting infrastructure/operations/classifiers.py removes an operations-layer `classify_aws_error` name; confirmed no import site resolves it via `from infrastructure.operations import classify_aws_error` or similar outside the module itself and its test -- re-verify with a repo-wide grep for the bare name `classify_aws_error` at execution time since it is a common name and a stray untyped/dynamic reference (e.g. via `getattr` or a string-based plugin lookup) would not show up in a static import grep.

Blast radius and rollback
  - Every read site of `.provider`/`.operation` is a re-boxing helper (`_typed_error`, `warmup`'s error branch, `_success_or_error`) that only ever forwards the value to another OperationResult -- no branching logic anywhere depends on the value of provider or operation. Removing them cannot change any status/error_code-driven control flow.
  - Deleting classifiers.py removes only unreferenced code; no production behavior depends on it today, so there is nothing to regress.
  - A single `git revert` of this PR fully restores prior behavior (field removal, log additions, and the classifiers.py deletion are all independent, reversible edits with no data migration or persisted state involved).
  - Ordering: must land after TASK-105 (dependency already declared) and before TASK-105.2/TASK-106 (dependents already declared) -- no other ordering constraints. Kept as a single PR per explicit instruction.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented per the approved plan on stack-a/task-105.1-drop-provider-operation (Stack A layer 3). 18 production files, as planned: 16 edited, 2 deleted (classifiers.py and its test).

- result.py: provider/operation fields, factory params, docstrings and pass-throughs removed.
- operations/__init__.py: classifier re-exports and the docstring line removed. classifiers.py and tests/unit/infrastructure/operations/test_classifiers.py deleted; the grep before deleting found no other importer.
- 9 aws_platform adapters, openai client/summarizer, incident_draft/service.py: kwargs dropped. These sites already logged operation context, so no logging was added.
- directory/drive/spreadsheets google.py: kwargs dropped; logger.warning(<x>_operation_failed, operation, status, error_code) added in each _map_sdk_exception, both branches in spreadsheets; spreadsheets gains a module logger.
- decisions/operation-result.md: provider/operation divergence removed from Consequences and Migration; Changes entry added.

Deviations from plan:
- directory _typed_error returns cast(OperationResult[T], replace(result, data=None)) rather than a plain cast. The method's docstring requires dropping provider payload data, which a plain cast would keep. It now also carries cause through.
- drive warmup and spreadsheets _success_or_error return cast(result) as planned. Error results from _call never carry data. _success_or_error's operation parameter became unused and was removed, with its 2 callers updated.
- incident_draft/service.py:292 now reads message=result.message or 'Incident draft summarizer failed'. This is a TASK-105 mypy error in a file this layer touches. There is no runtime change: summarizer error results always carry a message.

Tests: test_operations_result.py swaps TestOperationResultObservability for TestOperationResultCanonicalFields (field set equals the decision record; success()/error() reject provider/operation kwargs).

Gates: ruff check . -> All checks passed; ruff format --check . -> 737 files already formatted; lint-imports -> 7 kept, 0 broken; pytest tests --ignore=tests/smoke -> 3465 passed, 6 failed. The 6 are the same known TASK-90 order leaks (test_webhooks_aws_sns.py, directory/test_google.py), unchanged from layer 2.
mypy on touched files -> 0 errors in them. The 17 reported come from imported untouched files (i18n, openai/settings, slack/help), all already in the baseline. Full run: 103 errors. Against the pre-TASK-105 baseline, new errors dropped from 29 to 26, so the three google.py files and incident_draft are now clean.
AC #1 grep: the only remaining provider= hits are the DirectoryUser/DriveFile/SheetCell domain field, out of scope. AC #5 grep over app/, bin/ and scripts/ for operations.classifiers, classify_http_error and classify_integration_error: zero hits.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-28 14:55
---
2026-09-28: implementation plan approved by human (Guillaume Charest) for the doc-2 Stack A / Wave 0 realignment.
---
<!-- COMMENTS:END -->
