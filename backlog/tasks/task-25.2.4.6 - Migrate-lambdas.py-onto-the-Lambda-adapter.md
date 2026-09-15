---
id: TASK-25.2.4.6
title: Migrate lambdas.py onto the Lambda adapter
status: To Do
assignee: []
created_date: '2026-09-14 17:39'
updated_date: '2026-09-15 17:30'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.4.2
references:
  - app/modules/aws/lambdas.py
  - app/tests/unit/modules/aws/test_lambdas_handler.py
parent_task_id: TASK-25.2.4
priority: high
ordinal: 205000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2d of TASK-25.2.4. Migrate modules/aws/lambdas.py off the legacy integrations.aws.lambdas mirror onto the Lambda adapter landed by TASK-25.2.4.2 (build_lambda_adapter() from packages/aws_platform/adapters/aws_lambda.py). Follow the caller idiom landed by TASK-25.2.4.3/.4/.5: an explicit non-success branch that logs status/error_code/error. No adapter, settings, providers.py or aws.py changes.

Call sites (read 2026-09-15):
- aws_lambdas.list_functions() (lambdas.py:48)
- aws_lambdas.list_layers() (lambdas.py:68)
Neither is a crash-on-False site: `if response:` already guards the False sentinel (TASK-25.2.1 inventory item 15, "DEFENDED"), so no pinned crash tests exist. The real defect is that both sites report "Lambda functions/layers management is currently disabled" for any falsy response, so a real AWS failure looks the same as an empty account.

Error policy (human decisions 2026-09-15):
- Non-success result (TRANSIENT/UNAUTHORIZED/NOT_FOUND/PERMANENT): log the classification and respond with a bilingual EN/FR failure message.
- Success with an empty list: respond with a bilingual EN/FR "none found" message.
- Raised errors propagate (bare minimum, .3 precedent). The client is in-account, with no AssumeRole at build time, and the only unmapped ListFunctions/ListLayers error is InvalidParameterValueException, a programmer error since no parameters are sent. Throttling (TooManyRequestsException) and ServiceException are already classified TRANSIENT.

Bugs in the touched file, fixed simply (human decisions 2026-09-15):
(a) request_list_layers calls AWS before responding "Fetching Lambda layers..." (lines 68-69). Respond first, as request_list_functions does.
(b) LayersListItem.LatestMatchingVersion is optional in the botocore model, so layer['LatestMatchingVersion']['Version'] can raise KeyError. Read it with .get() and omit the version suffix when absent.
(c) The three handler functions get full type annotations (body, args, -> None).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 modules/aws/lambdas.py no longer imports integrations.aws.lambdas; request_list_functions and request_list_layers call build_lambda_adapter() at function entry and branch on the OperationResult explicitly
- [ ] #2 A non-success result from list_functions or list_layers logs status, error_code and error and responds with a distinct bilingual failure message; a successful empty list responds with a distinct bilingual 'none found' message; the 'management is currently disabled' text is gone and its two tests are replaced by tests of both outcomes
- [ ] #3 request_list_layers responds 'Fetching Lambda layers...' before calling the adapter, and a layer without LatestMatchingVersion is listed without a version instead of raising KeyError
- [ ] #4 command_handler, request_list_functions and request_list_layers are fully type-annotated and mypy reports no error in modules/aws/lambdas.py
- [ ] #5 Per-call-site error-path behaviour (before/after) is documented in the task notes for review
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUND TRUTH (read 2026-09-15)
- app/modules/aws/lambdas.py: 78 LOC, read in full. Its only production caller is modules/aws/aws.py:99-100 (command_handler(client, body, respond, args)). tests/unit/modules/aws/test_aws_command_handler.py:166 patches command_handler and is unaffected.
- Mirror app/integrations/aws/lambdas.py: list_functions/list_layers return a flat list, or False via handle_aws_api_errors. get_layer_version was not ported (.2 AC#6).
- Adapter app/packages/aws_platform/adapters/aws_lambda.py:
  - list_functions (:88) and list_layers (:92) return OperationResult[list[dict[str, Any]]], with all pages flattened.
  - build_lambda_adapter (:97) builds the client in-account: SERVICE_ROLE_MAP has no 'lambda' entry, so role_arn is None and no STS call happens.
- Classification in integrations/aws/settings.py: ThrottlingException/TooManyRequestsException (:86-89) and ServiceException (:98) are TRANSIENT. InvalidParameterValueException propagates as a raw ClientError.
- botocore model (introspected): ListFunctions/ListLayers errors are InvalidParameterValueException, ServiceException and TooManyRequestsException. LayersListItem has no required members, so LatestMatchingVersion is optional. FunctionConfiguration has no required members either, but FunctionName is always present in real responses and the code keeps indexing it.
- Tests: tests/unit/modules/aws/test_lambdas_handler.py has 14 tests.
  - 8 command_handler routing tests stay unchanged.
  - 6 request_* tests patch modules.aws.lambdas.aws_lambdas.list_*. Of these, test_should_show_disabled_message_when_no_functions (:178) and ..._no_layers (:248) pin the "currently disabled" text.
- TASK-25.2.1 inventory item 15: both sites are DEFENDED, and no False-crash tests exist.
- Sibling idiom: spending.py:38 _failure_fields(result) -> {status, error_code, error} (3 lines, copied privately per the .5 precedent). Tests use the _logged(mock_logger, event) helper from test_spending_handler.py:48. Bilingual failure text follows aws.py's spending message ("... Please try again later.\n... Veuillez réessayer plus tard.").

ALIGNMENT WITH SIBLINGS
- Use the landed factory only: no adapter, settings, providers.py or aws.py change.
- Build the adapter inside each request_* function at call time, never at import.
- Log failures as log.error(<event>, **_failure_fields(result)) (.3/.4/.5). Copy _failure_fields privately rather than sharing it (.5 rationale: legacy modules are rearchitected on the move to packages/).
- Raised errors propagate (.3 bare-minimum precedent, human decision 2026-09-15).
- Keep the legacy test file name (predates testing-standards; .3/.5 precedent).
- After this task, rg over production code finds no import of integrations.aws.lambdas, which unblocks TASK-25.2.4.7 for the Lambda mirror.

STEP 1: tests first (red) in app/tests/unit/modules/aws/test_lambdas_handler.py
- Add a fixture that patches modules.aws.lambdas.build_lambda_adapter to return MagicMock(spec=LambdaAdapter). Add a fixture that patches modules.aws.lambdas.logger, and a local _logged helper copied from test_spending_handler.py.
- Re-stub the 4 remaining request_* tests (:154, :196, :218, :266): the adapter methods return OperationResult.success(data=[...]). Assertions are unchanged, apart from the respond order for layers.
- Replace :178 and :248, and add the new tests from the TEST MATRIX.

STEP 2: app/modules/aws/lambdas.py
- Imports: remove `from integrations.aws import lambdas as aws_lambdas`. Add `from typing import Any`, `from infrastructure.operations import OperationResult` and `from packages.aws_platform.adapters.aws_lambda import build_lambda_adapter`.
- Add the private _failure_fields(result: OperationResult[Any]) -> dict[str, Any] (3 lines, as in spending.py).
- Signatures (bug c): command_handler(client: WebClient, body: dict[str, Any], respond: Respond, args: list[str]) -> None; request_list_functions(client: WebClient, body: dict[str, Any], respond: Respond) -> None; request_list_layers with the same signature. Docstrings keep their current Google style; the types in the Args lines are dropped because they now duplicate the annotations.
- request_list_functions:
  - respond("Fetching Lambda functions...")
  - result = build_lambda_adapter().list_functions()
  - If not result.is_success: log.error("lambda_functions_lookup_failed", **_failure_fields(result)); respond("Failed to list Lambda functions. Please try again later.\nImpossible de lister les fonctions Lambda. Veuillez réessayer plus tard."); return.
  - functions = result.data or []. If empty: respond("No Lambda functions found.\nAucune fonction Lambda trouvée."); return.
  - Otherwise: log count and respond with the list, as today.
- request_list_layers (bug a): respond "Fetching Lambda layers..." first, then the same three branches:
  - event lambda_layers_lookup_failed
  - failure text "Failed to list Lambda layers. Please try again later.\nImpossible de lister les couches Lambda. Veuillez réessayer plus tard."
  - empty text "No Lambda layers found.\nAucune couche Lambda trouvée."
- Bug b: version = (layer.get("LatestMatchingVersion") or {}).get("Version"). The line is f"\n • {layer['LayerName']}" plus f" <latest version: {version}>" only when version is not None.
- Success messages ("Lambda functions found:" / "Lambda layers found:") and help text are unchanged.

STEP 3: gates (from app/)
- rg -n "integrations.aws" modules/aws/lambdas.py: expect no output.
- uv run ruff check .
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)': no error in modules/aws/lambdas.py. The repo-wide count must not increase from the baseline recorded before Step 2.
- uv run pytest tests --ignore=tests/smoke: the 6 known order-dependent SNS/google-directory failures are pre-existing. Call them out, don't fix them.
- bin/check_deprecated_infra_client_imports.py, bin/check_sdk_typing.py and bin/check_vendor_package_contract.py all pass. The integrations/aws/lambdas.py baseline entries (sdk_typing_antipatterns.txt:11, vendor_package_contract.txt:12) stay: .7 prunes them when it deletes the mirror.

STEP 4: notes (AC#5). One before/after line per call site, plus gate evidence. Check each AC as it is verified.

TEST MATRIX (test_lambdas_handler.py; adapter as MagicMock(spec=LambdaAdapter) returning OperationResult; Stubber stays reserved for adapter tests)
| Case | Test | AC |
|---|---|---|
| functions success lists every name; adapter built once, list_functions called once | test_should_list_functions_successfully (re-stubbed) + test_should_log_functions_count (re-stubbed) | 1 |
| functions non-success (parametrized TRANSIENT_ERROR, UNAUTHORIZED) -> exact bilingual failure text, lambda_functions_lookup_failed logged with status/error_code/error, no "found" message | test_should_respond_failure_and_log_when_list_functions_fails (replaces :178) | 2 |
| functions success [] -> exact bilingual "No Lambda functions found" text, no failure log | test_should_respond_none_found_when_no_functions | 2 |
| layers success lists names and versions | test_should_list_layers_successfully + test_should_format_layer_version_correctly (re-stubbed) | 1 |
| layers non-success (parametrized) -> bilingual failure text, lambda_layers_lookup_failed logged | test_should_respond_failure_and_log_when_list_layers_fails (replaces :248) | 2 |
| layers success [] -> bilingual "No Lambda layers found" text | test_should_respond_none_found_when_no_layers | 2 |
| "Fetching Lambda layers..." is respond call 0 and is sent before list_layers is called (side_effect records the order) | test_should_respond_fetching_before_listing_layers | 3 |
| layer without LatestMatchingVersion -> listed by name, no "latest version" suffix, no KeyError | test_should_list_layer_without_latest_matching_version | 3 |
| adapter raises ClientError (InvalidParameterValueException) -> propagates | test_should_propagate_unclassified_error_from_list_functions | 1 |
| 8 command_handler routing tests | unchanged | - |
AC#4 is verified by mypy (Step 3), not by a test.

AC TRACEABILITY
- AC#1 <- Step 2 imports and factory calls; re-stubbed success tests, propagate test, Step 3 rg
- AC#2 <- Step 2 non-success and empty branches; 4 failure/empty tests
- AC#3 <- Step 2 respond order and .get(); order test, missing-version test
- AC#4 <- Step 2 signatures; Step 3 mypy
- AC#5 <- Step 4 notes

ASSUMPTIONS / DOUBTS (verify during implementation)
- modules/aws/lambdas.py is not under a mypy exclude or ignore_errors override, so AC#4 is actually checked. Verify with: rg -n "modules" app/pyproject.toml app/mypy.ini.
- Importing packages.aws_platform.adapters.aws_lambda from modules/ passes bin/check_vendor_package_contract.py and the import guards. The .4/.5 siblings import other adapters from modules/aws the same way; verify by running the guards.
- body really is a dict at runtime (Slack Bolt payload). The tests pass MagicMock, which mypy does not see. If aws.py's call site does not type-check against dict[str, Any], use the same annotation aws.py uses.
- No other caller of request_list_functions/request_list_layers exists. Re-run rg -n "request_list_(functions|layers)" app --glob '!**/.venv/**' (2026-09-15: only the module and its test).
- Slack message size for very large function lists is unchanged from today and out of scope.

BLAST RADIUS AND ROLLBACK
- Only the read-only /aws lambda functions|layers Slack commands. Worst case: a wrong message text. No writes, settings, env or terraform.
- Visible on merge: an empty account now says "No Lambda ... found" instead of "management is currently disabled", and an AWS failure shows a failure message. A raised InvalidParameterValueException now propagates to Bolt instead of being swallowed by handle_aws_api_errors, which is theoretical since no parameters are sent.
- A single git revert restores the mirror-based behaviour; the mirror remains until .7.

SIZE ESTIMATE AND GATE VERDICT
- Production: 1 file (modules/aws/lambdas.py), about 40 changed LOC. One subsystem. The type annotations sit on the lines already being rewritten, so no separate mechanical refactor is mixed in.
- Tests: 1 file (not gated).
- VERDICT: under the gate. One PR.

OPEN QUESTIONS FOR HUMAN REVIEW
- None. Scope decisions were recorded 2026-09-15 (see notes).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Cross-reference from TASK-25.2.4.2 planning (2026-09-14): the Lambda adapter module is packages/aws_platform/adapters/aws_lambda.py (not lambda.py, because 'lambda' is a Python keyword): LambdaAdapter, build_lambda_adapter(). list_functions/list_layers return OperationResult[list[dict]] across all pages. The client is in-account with no role assumed, matching the mirror. ServiceException now classifies as TRANSIENT; InvalidParameterValueException still propagates.

Planning 2026-09-15 (human decisions):
- Scope adjusted to the sibling implementations (.3/.4/.5): landed factory only, _failure_fields logging, legacy test file name kept.
- Original AC#2 premise corrected. lambdas.py:48/68 never crashed on False (`if response:` guards it; TASK-25.2.1 item 15 marked it DEFENDED), so there were no pinned crash tests. The real defect is that "management is currently disabled" is shown for both failure and empty. ACs rewritten: failure vs empty (#2), bug fixes (#3), typing (#4), notes (#5).
- Raised errors propagate: bare minimum, .3 precedent. The client is in-account, so there is no AssumeRole at build time.
- New Slack messages are bilingual EN/FR, matching aws.py's spending failure text.
- Bugs fixed simply: "Fetching" respond order in request_list_layers; optional LatestMatchingVersion (KeyError); handler signatures typed.

Failing tests authored 2026-09-15 (no production code changed):
- tests/unit/modules/aws/test_lambdas_handler.py rewritten in place (legacy name kept): 21 test cases, up from 14.
  - The 8 command_handler routing tests are unchanged.
  - A lambda_adapter fixture patches modules.aws.lambdas.build_lambda_adapter with MagicMock(spec=LambdaAdapter) and exposes the factory mock. A mock_logger fixture and a _logged helper are copied from test_spending_handler.py.
  - Re-stubbed onto OperationResult.success: list functions, log count (now also asserts the adapter is built and queried once), list layers, format layer version.
  - The two "currently disabled" tests are replaced by failure tests for functions and layers, parametrized TRANSIENT_ERROR/UNAUTHORIZED. Each asserts the exact bilingual failure text and that the lookup-failed event is logged with status, error_code and error.
  - New tests: none-found for functions and for layers (exact bilingual text, no failure log); unclassified ClientError propagates; "Fetching Lambda layers..." is sent before list_layers (shared order list); a layer without LatestMatchingVersion is listed with no version suffix.
- Exact texts the implementation must match:
  - "Failed to list Lambda functions. Please try again later.\nImpossible de lister les fonctions Lambda. Veuillez réessayer plus tard."
  - "No Lambda functions found.\nAucune fonction Lambda trouvée."
  - "Failed to list Lambda layers. Please try again later.\nImpossible de lister les couches Lambda. Veuillez réessayer plus tard."
  - "No Lambda layers found.\nAucune couche Lambda trouvée."
  - Log events: lambda_functions_lookup_failed and lambda_layers_lookup_failed.

Red-state evidence (from app/):
- uv run pytest tests/unit/modules/aws/test_lambdas_handler.py -q: 8 passed, 13 errors. Every error is at setup: AttributeError, modules.aws.lambdas does not have the attribute 'build_lambda_adapter'. This setup error hides the assertion-level red, which only shows once the import lands.
- uv run ruff check / ruff format --check on the file: All checks passed; 1 file already formatted.
- uv run mypy tests/unit/modules/aws/test_lambdas_handler.py: 0 errors in the test file or modules/aws/lambdas.py. The 63 reported errors are in other files mypy followed from imports.
<!-- SECTION:NOTES:END -->
