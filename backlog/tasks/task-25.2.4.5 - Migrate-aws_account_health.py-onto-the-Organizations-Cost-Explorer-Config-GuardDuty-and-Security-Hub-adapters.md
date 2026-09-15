---
id: TASK-25.2.4.5
title: >-
  Migrate aws_account_health.py onto the Organizations, Cost Explorer, Config,
  GuardDuty and Security Hub adapters
status: To Do
assignee: []
created_date: '2026-09-14 17:39'
updated_date: '2026-09-15 16:55'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.4.1
  - TASK-25.2.4.2
references:
  - app/modules/aws/aws_account_health.py
  - app/tests/unit/modules/aws/test_aws_account_health_handler.py
  - app/modules/aws/aws.py
  - app/modules/aws/spending.py
  - app/packages/aws_platform/adapters/organizations.py
  - app/packages/aws_platform/adapters/cost_explorer.py
  - app/packages/aws_platform/adapters/config.py
  - app/packages/aws_platform/adapters/guard_duty.py
  - app/packages/aws_platform/adapters/security_hub.py
  - app/integrations/aws/client.py
parent_task_id: TASK-25.2.4
priority: high
ordinal: 204000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2c of TASK-25.2.4. Migrate modules/aws/aws_account_health.py (247 LOC) off the legacy integrations.aws.{organizations,cost_explorer,config,guard_duty,security_hub} mirrors onto the adapters landed by TASK-25.2.4.1/.2: build_organizations_adapter(), build_cost_explorer_adapter(), build_config_adapter(), build_guard_duty_adapter(), build_security_hub_adapter(). Follow the caller idiom landed by TASK-25.2.4.3/.4: explicit non-success branch logging status/error_code/error, adapters built once per run and never at import. No adapter, settings, providers.py or modules/aws/aws.py changes. Production entry points: aws.py:56 (health_view_handler, the aws_health_view submit) and aws.py:94 (`/aws health` -> request_health_modal).

Call sites (read 2026-09-15; seven mirror calls in six places):
- get_account_spend :53 cost_explorer.get_cost_and_usage: a False return crashes the indexing at :54 (TypeError). The adapter returns the ResultsByTime list itself, and an empty list would raise IndexError.
- get_config_summary :66 config.describe_aggregate_compliance_by_config_rules: len(False) raises TypeError.
- get_guardduty_summary :70 guard_duty.list_detectors: False raises TypeError and an empty list raises IndexError at :78 (GuardDuty not enabled).
- get_guardduty_summary :78 guard_duty.get_findings_statistics: False raises TypeError at :79. The adapter returns the CountBySeverity dict.
- get_securityhub_summary :105 security_hub.get_findings: no crash, but an API error is reported as a clean "0 issues" (a false ✅).
- request_health_modal :211 organizations.list_organization_accounts: False crashes the comprehension (TypeError).

UX decisions (human, 2026-09-15):
- Partial failure: the other modal lines render normally, and the failed line shows ⚠️ unavailable instead of ✅/❌ and a count.
- Zero GuardDuty detectors: the line shows ⚠️ not enabled, and get_findings_statistics is not called.
- /aws health account-list failure: open a bilingual error modal with no submit button, reusing the trigger_id. aws.py is unchanged.
- Raised AWS errors (AssumeRole at adapter build, unmapped codes such as GuardDuty BadRequestException): catch ClientError/BotoCoreError narrowly, log, and update the "Loading data..." modal to a bilingual error so it never spins forever. Other exceptions propagate.

Bugs in touched code, fixed simply (standing TASK-25.2.4 decision):
(a) Cost Explorer TimePeriod.End is exclusive, and the last day of the month is passed, so that day's cost is dropped. Query with the first day of the next month; the modal keeps displaying the last day.
(b) An empty ResultsByTime list must give 0.00, not IndexError.
(c) The GuardDuty criterion "service.archived": {"Eq": ["false", "false"]} becomes ["false"]. The filter is OR over the array, so results don't change.
(d) arrow.utcnow() is called four times, so a check that spans a month boundary can mix months. Compute it once.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 modules/aws/aws_account_health.py no longer imports integrations.aws; all seven mirror calls go through build_organizations_adapter / build_cost_explorer_adapter / build_config_adapter / build_guard_duty_adapter / build_security_hub_adapter, built at run time (never at import, Cost Explorer once per health check) and branching on OperationResult explicitly
- [ ] #2 A non-success result from get_cost_and_usage, describe_aggregate_compliance_by_config_rules, list_detectors, get_findings_statistics or get_findings is logged with status, error_code and error, and only that line of the health modal shows ⚠️ unavailable while the other lines render normally (a Security Hub failure no longer reads as ✅ 0 issues); the pinned False tests in tests/unit/modules/aws/test_aws_account_health_handler.py are replaced by tests of this behaviour
- [ ] #3 When list_detectors succeeds with no detectors, the GuardDuty line shows ⚠️ not enabled and get_findings_statistics is not called
- [ ] #4 A non-success result from list_organization_accounts is logged and /aws health opens a bilingual error modal with no submit button instead of raising
- [ ] #5 A ClientError or BotoCoreError raised by adapter construction or an unmapped AWS error code is logged; health_view_handler replaces the Loading data... modal with a bilingual error view and request_health_modal opens its error modal; other exceptions still propagate
- [ ] #6 Cost Explorer is queried with End set to the first day of the following month (exclusive) while the modal still displays the month's last day; an empty ResultsByTime list yields 0.00; the GuardDuty service.archived criterion is ["false"]
- [ ] #7 Per-call-site error-path behaviour (one line per call site, including the GuardDuty zero-detector chain) is recorded in the task notes for review
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUND TRUTH (read 2026-09-15)
- app/modules/aws/aws_account_health.py: 247 LOC, read in full.
- Production callers: app/modules/aws/aws.py:56 (bot.view registration) and :94 (request_health_modal(client, body), no respond). rg confirms no other production caller of any function in the module.
- Adapters: organizations.py list_organization_accounts -> OperationResult[list[dict]] :97, build_organizations_adapter :115; cost_explorer.py get_cost_and_usage(time_period, granularity, metrics, filter_expression=None, group_by=None) -> OperationResult[list[dict]] (ResultsByTime entries, NextPageToken followed) :75, build_cost_explorer_adapter :114; config.py describe_aggregate_compliance_by_config_rules(config_aggregator_name, filters=None) -> OperationResult[list[dict]] :86, build_config_adapter :100; guard_duty.py list_detectors -> OperationResult[list[str]] :84, get_findings_statistics(detector_id, finding_criteria=None) -> OperationResult[dict[str, int]] (CountBySeverity, {} when absent) :90, build_guard_duty_adapter :109; security_hub.py get_findings(filters) -> OperationResult[list[dict]] (flat Findings) :90, build_security_hub_adapter :95.
- Roles are unchanged: SERVICE_ROLE_MAP ce/organizations -> ORG, config -> AUDIT, guardduty/securityhub -> LOGGING, matching the mirrors' role_arn params (integrations/aws/{cost_explorer:35,organizations:18,config:38,guard_duty:27,61,security_hub:27}).
- integrations/aws/client.py:196-221 classify_aws_error: BotoCoreError -> TRANSIENT_ERROR, mapped ClientError codes -> NOT_FOUND/UNAUTHORIZED/TRANSIENT, and any other ClientError is re-raised (so GuardDuty BadRequestException propagates out of the adapter). NoSuchConfigurationAggregatorException -> NOT_FOUND; InvalidAccessException (Security Hub not enabled) -> UNAUTHORIZED.
- Tests: app/tests/unit/modules/aws/test_aws_account_health_handler.py has 19 tests. Its 6 pinned False tests are at :280, :297, :313, :329, :347 (Security Hub, which returns 0) and :367. test_aws_command_handler.py:102 patches request_health_modal and stays unchanged.
- Sibling idiom: spending.py _failure_fields (private, 3 lines) plus log.error(event, **_failure_fields(result)); the test helper _logged(mock_logger, event) in test_spending_handler.py:48. freezegun==1.5.5 is a dev dependency.

ALIGNMENT WITH SIBLINGS
- Use only the landed factories: no adapter, settings, providers.py or aws.py change.
- Adapters are built inside the functions at run time, never at import (eager AssumeRole). get_account_health builds Cost Explorer, Config, GuardDuty and Security Hub once and passes them into the helpers, so Cost Explorer is built once for both months, as in .4. request_health_modal builds Organizations.
- Logging shape as in .3/.4: event name plus status=result.status.value, error_code, error=result.message. _failure_fields is copied privately (3 lines) rather than shared: both legacy modules are rearchitected when they move to packages/, and sharing it would need a new modules/ helper or an infrastructure/operations change, which is out of scope.
- The legacy test file name is kept (it predates testing-standards; renaming would mix a mechanical change into a behaviour PR; .3 precedent).
- After this task, the only remaining mirror users are modules/aws/lambdas.py (.6) and the mirrors' own legacy tests. .7 deletes them.

STEP 1: tests first (red) in app/tests/unit/modules/aws/test_aws_account_health_handler.py
- Re-stub the existing helper tests: pass MagicMock adapters whose methods return OperationResult.success(data=...) in the new shapes (ResultsByTime list, CountBySeverity dict, flat findings list), instead of patching the removed module attributes.
- Patch build_*_adapter for get_account_health and request_health_modal. Add a local _logged(mock_logger, event) helper that copies the spending test pattern, and patch modules.aws.aws_account_health.logger.
- Replace the 6 pinned False tests and add the new tests from the TEST MATRIX.

STEP 2: app/modules/aws/aws_account_health.py
- Imports: drop the integrations.aws block. Add the five build_*_adapter factories (plus the adapter classes for type hints), OperationResult, botocore ClientError/BotoCoreError, and typing Any/Literal.
- Add `type SecuritySummary = int | Literal["not_enabled"] | None` and the private _failure_fields(result).
- get_account_health(account_id) -> dict[str, Any] (AC#1, #6d): call now = arrow.utcnow() once. For last and current month: start = now.shift(months=k).floor("month"), display_end = span end, and query_end = start.shift(months=1) (bug a). Build the four adapters once. The data dict keeps the same keys; amount is str | None, and the security values are SecuritySummary.
- get_account_spend(cost_explorer_adapter, account_id, start_date, end_date) -> str | None, where end_date is exclusive. Call adapter.get_cost_and_usage(time_period=..., granularity="MONTHLY", metrics=[...], filter_expression=..., group_by=...). On non-success, log aws_health_cost_lookup_failed (account_id, start, end, failure fields) and return None. On success, use first = (result.data or [None])[0]; with no entry or no Groups, return "0.00" (bug b). Otherwise format the amount as today.
- get_config_summary(config_adapter, account_id) -> int | None: on non-success, log aws_health_config_lookup_failed and return None; otherwise return len(result.data or []).
- get_guardduty_summary(guard_duty_adapter, account_id) -> SecuritySummary: if list_detectors fails, log aws_health_guardduty_detectors_failed and return None. If it succeeds with no ids, log aws_health_guardduty_not_enabled (info) and return "not_enabled" without calling statistics. Otherwise call get_findings_statistics(detector_ids[0], criteria with "service.archived": {"Eq": ["false"]}) (bug c). On failure, log aws_health_guardduty_statistics_failed (detector_id) and return None; on success, return sum((result.data or {}).values()).
- get_securityhub_summary(security_hub_adapter, account_id) -> int | None: on non-success, log aws_health_securityhub_lookup_failed and return None (no more false ✅); otherwise return len(result.data or []). get_ignored_security_hub_issues is unchanged.
- Rendering helpers (private): _cost_line(start, end, amount), where None gives "⚠️ unavailable" and a value gives "$X USD" as today; _security_line(label, value), where None gives "⚠️ {label} (unavailable)", "not_enabled" gives "⚠️ {label} (not enabled)", 0 gives "✅ {label} (0 issues)" and n gives "❌ {label} (n issues)"; _error_view(title, text), a modal with a Close button, no submit, and one bilingual mrkdwn section.
- health_view_handler (AC#2, #5): ack, parse and open the loading modal as today. Wrap get_account_health in `try ... except ClientError, BotoCoreError:` (PEP 758 form), log.exception("aws_health_check_failed", account_id), update the view with _error_view("AWS - Health Check", "⚠️ Could not load the health check. Please try again later.\nImpossible de charger la vérification de santé. Veuillez réessayer plus tard."), and return. Build the final modal with the helpers; the block layout is otherwise unchanged.
- request_health_modal (AC#4, #5): wrap build_organizations_adapter().list_organization_accounts() in the same narrow except, and on a raise log.exception("aws_health_accounts_list_failed") and open the error modal. On non-success, log.error("aws_health_accounts_list_failed", **_failure_fields) and views_open(trigger_id, _error_view("AWS - Account health", "⚠️ Could not list AWS accounts. Please try again later.\nImpossible de lister les comptes AWS. Veuillez réessayer plus tard.")), then return. On success, options come from result.data or [], sorted as today. Note: the narrow catch in request_health_modal extends the handler decision to the second entry point, so /aws health never fails silently. It is 3 extra LOC; flag in review if unwanted.

STEP 3: gates from app/: rg -n "integrations.aws" modules/aws/aws_account_health.py (expect nothing); uv run ruff check .; uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' (baseline 87 errors in 31 files, none added in the touched file); uv run pytest tests --ignore=tests/smoke (known 6 order-dependent SNS/google-directory failures). Also run bin/check_deprecated_infra_client_imports.py, bin/check_sdk_typing.py and bin/check_vendor_package_contract.py; no baseline lists aws_account_health.py.

STEP 4: notes (AC#7): one line per call site, plus gate evidence. Check ACs one by one as each is verified.

TEST MATRIX (test_aws_account_health_handler.py; adapters as MagicMocks returning OperationResult, as in .3/.4; Stubber stays reserved for adapter tests)
| Case | Test | AC |
|---|---|---|
| get_account_health builds each of the 4 adapters once, passes them to the helpers, and keeps the data dict keys (freeze 2024-12-15) | test_should_get_account_health_successfully (re-stubbed) | 1 |
| Spend: formatted amount / no Groups / empty ResultsByTime list -> "0.00"; called with filter_expression | 3 existing tests re-stubbed + test_should_return_zero_when_results_by_time_empty | 1, 6 |
| Exclusive End: frozen 2024-12-15 -> last month Start 2024-11-01 End 2024-12-01 and current month Start 2024-12-01 End 2025-01-01; frozen 2024-03-10 -> Feb End 2024-03-01; data dict end_date still 2024-11-30 / 2024-12-31 | test_should_query_cost_explorer_with_exclusive_month_end (parametrized) | 6 |
| Config: count / zero (re-stubbed) | 2 existing tests | 1 |
| GuardDuty: sum / zero findings (re-stubbed); criteria archived Eq == ["false"] | 2 existing tests + assertion | 1, 6 |
| Security Hub: len of flat list / empty (re-stubbed) | 2 existing tests | 1 |
| Cost non-success (TRANSIENT) -> None, aws_health_cost_lookup_failed logged with status/error_code/error | test_should_return_none_and_log_when_cost_lookup_fails (replaces :280) | 2 |
| Config non-success (NOT_FOUND) -> None, logged | test_should_return_none_and_log_when_config_lookup_fails (replaces :297) | 2 |
| list_detectors non-success -> None, logged, statistics not called | test_should_return_none_and_log_when_guardduty_detectors_fail (replaces :313) | 2 |
| get_findings_statistics non-success -> None, logged with detector_id | test_should_return_none_and_log_when_guardduty_statistics_fail (replaces :329) | 2 |
| Security Hub non-success (UNAUTHORIZED) -> None, logged (not 0) | test_should_return_none_and_log_when_securityhub_lookup_fails (replaces :347) | 2 |
| list_detectors success [] -> "not_enabled", statistics not called | test_should_report_guardduty_not_enabled_when_no_detectors | 3 |
| health_view_handler renders ⚠️ unavailable for a None cost and a None Security Hub, ⚠️ GuardDuty (not enabled), and ✅/❌ for the rest | test_should_render_per_field_warnings_in_health_modal | 2, 3 |
| health_view_handler happy render unchanged ($ amounts, ✅/❌ counts) | test_should_handle_health_view_handler (existing) | 1 |
| get_account_health raises ClientError (and parametrized BotoCoreError) -> views_update with the bilingual error view, aws_health_check_failed logged | test_should_show_error_view_when_health_check_raises_aws_error | 5 |
| get_account_health raises KeyError -> propagates | test_should_propagate_non_aws_errors_from_health_check | 5 |
| request_health_modal success: sorted options from result.data | test_should_request_health_modal (re-stubbed) | 1 |
| list_organization_accounts non-success -> views_open error modal (no "submit" key, bilingual text), logged | test_should_open_error_modal_when_account_list_fails (replaces :367) | 4 |
| build_organizations_adapter raises ClientError -> error modal, logged | test_should_open_error_modal_when_organizations_adapter_raises | 5 |

AC TRACEABILITY
- AC#1 <- Step 2 imports/factories/helper signatures; re-stubbed happy tests plus the Step 3 rg
- AC#2 <- Step 2 non-success branches + _security_line/_cost_line; the 5 replacement tests + the render test
- AC#3 <- get_guardduty_summary empty branch; not-enabled test + render test
- AC#4 <- request_health_modal non-success branch; error-modal test
- AC#5 <- narrow excepts in both handlers; raise/propagate tests
- AC#6 <- get_account_health date math, get_account_spend empty guard, GuardDuty criteria; exclusive-end, empty-results and criteria tests
- AC#7 <- notes

ASSUMPTIONS / DOUBTS (verify during implementation)
- freezegun freezes arrow.utcnow() (arrow reads datetime.now(timezone.utc)). Verify: the exclusive-End test is red first for the right reason.
- An AssumeRole failure at adapter build raises ClientError (STS) or a BotoCoreError subclass (e.g. NoCredentialsError). Verify by reading the eager AssumeRole path in integrations/aws/client.py get_aws_client before writing the except.
- Cost Explorer accepts a future End for the current month: spending.py has sent the same since .4, so the risk is unchanged.
- trigger_id validity is unchanged: views_open in request_health_modal still runs right after the single account listing, as today.
- No other caller of the helper functions: re-run rg -n "get_account_spend|get_config_summary|get_guardduty_summary|get_securityhub_summary|get_account_health" app --glob '!**/.venv/**' before changing signatures (2026-09-15: only the module and its test).

BLAST RADIUS AND ROLLBACK
- Only the read-only /aws health flow. Worst case: a line shows ⚠️ when data was available, or an error modal. No writes, settings, env or terraform.
- Behaviour visible on merge: cost figures now include each month's last day (a slightly higher amount for last month), and a disabled Security Hub or GuardDuty now shows ⚠️ instead of ✅.
- A single git revert restores the mirror-based behaviour; the mirrors remain until .7.

SIZE ESTIMATE AND GATE VERDICT
- Production: 1 file (aws_account_health.py), about 100-120 changed LOC (imports about 12, helpers about 45, render helpers/error view about 30, handler branches about 20). One subsystem. The helper signature changes are part of the behaviour change and have no outside callers, so no mechanical refactor is mixed in.
- Tests: 1 file (not gated).
- VERDICT: under the gate. One PR.

OPEN QUESTIONS FOR HUMAN REVIEW
- Only the request_health_modal narrow catch (Step 2 note), which applies the raised-error decision to the second entry point. Everything else was decided 2026-09-15.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Candidate bugs verified 2026-09-14 during TASK-25.2.4.1 planning (organizations/sso_admin scope); these are owned by .4.5 (aws_account_health.py), not .1:

1. CONFIRMED - Cost Explorer TimePeriod.End is exclusive (same AWS-doc citation as recorded on TASK-25.2.4.4). aws_account_health.py:18-21,33-34,48 passes the literal last calendar day of the month as TimePeriod.End, so the last day's cost is silently dropped. Fix: pass the first day of the next month as End when migrating onto the Cost Explorer adapter.

2. CONFIRMED - aws_account_health.py:78 `detector_ids[0]` (from guard_duty.list_detectors() at line 70) is indexed without checking for an empty list or the legacy False-on-error sentinel: an account/region with zero GuardDuty detectors raises IndexError, and an API error raises TypeError. Fix: branch on the GuardDuty adapter's OperationResult and on an empty detector list explicitly (e.g. report "GuardDuty not enabled" rather than crashing) when migrating onto the GuardDuty adapter.

3. CONFIRMED (duplication) / REJECTED as a result-altering bug - aws_account_health.py:74 `"service.archived": {"Eq": ["false", "false"]}`. GuardDuty FindingCriteria.Eq is OR-semantics across the array, so a duplicated "false" doesn't change which findings match - it's dead/sloppy duplication, not a correctness bug. Simple cleanup fix while touching this line for the GuardDuty adapter migration: collapse to `["false"]` (or fix if a second distinct value, e.g. "true", was actually intended - worth a second look at the original intent, not verifiable from code alone).

4. CONFIRMED - aws_account_health.py:66 `len(config.describe_aggregate_compliance_by_config_rules(config_name, filters))` crashes with TypeError if that call returns the legacy False-on-error sentinel. Already covered by TASK-25.2.4 AC#4 (crash-on-False sites); citing the exact line for traceability when migrating onto the Config adapter.

5. CONFIRMED - aws_account_health.py:70 `detector_ids = guard_duty.list_detectors()` can itself be the False-on-error sentinel (compounds with bug #2 above). Same AC#4 crash-on-False class.

6. CONFIRMED - aws_account_health.py:211 `accounts = organizations.list_organization_accounts()` is a crash-on-False site for the Organizations adapter migration (AC#4 class); citing for traceability.

7. Not a crash but a silent-failure mode, flagged for awareness: aws_account_health.py:105-109 `response = security_hub.get_findings(filters); if response: ...` already guards against the False sentinel (no crash), but on a real API error it silently reports "0 issues" rather than surfacing the failure - worth an explicit non-success branch when migrating onto the Security Hub adapter, consistent with the AC#4 intent even though it isn't a literal crash site.

8. NEW FINDING, cross-referenced on TASK-25.2.4.2 - security_hub.py's get_findings calls execute_aws_api_call(..., paginated=True, ...) without passing keys=. In client.py's generic paginator(), when keys is None every non-ResponseMetadata page key is flattened into one flat list - including scalar values like NextToken - not just the Findings list. aws_account_health.py:105-109 then does `for res in response: issues += len(res["Findings"])`, assuming each item is a page dict with a "Findings" key, which breaks once pagination flattening changes the shape. This is a real shape-mismatch bug in security_hub.py, needs fixing when the Security Hub adapter is built in .4.2 (paginate with an explicit response_key="Findings" the way identity_center.py's _paginate() does), not preserved as-is.

Cross-reference from TASK-25.2.4.2 planning (2026-09-14), adapter return shapes differ from the mirrors:
- Cost Explorer get_cost_and_usage returns OperationResult[list[dict]] of concatenated ResultsByTime entries, so get_account_spend reads result.data[0] instead of response['ResultsByTime'][0], and the filter argument is filter_expression.
- GuardDuty get_findings_statistics returns OperationResult[dict[str, int]]: the CountBySeverity dict itself, {} when absent. get_guardduty_summary sums result.data.values(). list_detectors returns OperationResult[list[str]].
- Security Hub get_findings returns OperationResult[list[dict]], a flat list of findings. get_securityhub_summary uses len(result.data) instead of summing len(res['Findings']) per page (resolves candidate bug #8).
- New error classifications in AWSSettings: NoSuchConfigurationAggregatorException -> NOT_FOUND, InvalidAccessException (Security Hub not enabled) -> UNAUTHORIZED, InternalServerErrorException/InternalException/LimitExceededException -> TRANSIENT. GuardDuty BadRequestException still propagates as a raw ClientError, so decide whether get_guardduty_summary catches it. SERVICE_ROLE_MAP now has securityhub -> LOGGING_ROLE_ARN.

Planning 2026-09-15 (human decisions):
- Scope adjusted to the sibling implementations. Builds use the landed factories only (no adapter/settings/aws.py changes), adapters are built once per run, and failures are logged with status/error_code/error as in .3/.4. Bugs in the touched file are fixed simply (the exclusive End from bug #1, empty ResultsByTime, duplicate "false" from bug #3, a single utcnow).
- Health modal partial failure: per-field ⚠️ unavailable, other lines normal (answers the TASK-25.2.4 coordinator open question).
- Zero GuardDuty detectors: ⚠️ not enabled, no statistics call (resolves candidate bug #2).
- /aws health account-list failure: bilingual error modal (no submit), aws.py unchanged.
- Raised AWS errors (AssumeRole at build, unmapped codes like GuardDuty BadRequestException): catch ClientError/BotoCoreError narrowly, log, update the loading modal to a bilingual error. The plan applies the same narrow catch to request_health_modal (flagged for review).
- Security Hub silent 0-on-error (candidate bug #7) now shows ⚠️ unavailable. Bug #8 (pagination shape) is resolved by the .2 adapter (flat Findings list).
- ACs rewritten: the original AC#2 split into failure fallback (#2), zero detectors (#3), modal-open failure (#4), raised errors (#5) and bug fixes (#6). Per-call-site notes stay as the last AC (#7).

Failing tests authored 2026-09-15 (no production code changed):
- tests/unit/modules/aws/test_aws_account_health_handler.py rewritten in place (legacy name kept): 29 test cases, up from 19.
  - Helper tests call get_account_spend / get_config_summary / get_guardduty_summary / get_securityhub_summary directly, each with a MagicMock(spec=<Adapter>) passed in.
  - get_account_health tests use one fixture that patches the four build_*_adapter factories.
  - Handler rendering tests patch get_account_health, as the original test did.
  - Log assertions match events by name on the patched module logger, as in test_spending_handler.py.
- The 6 pinned False tests are replaced: cost / Config / GuardDuty detectors / GuardDuty statistics / Security Hub failure each returns None and logs its classification; account-list failure opens an error modal.
- New tests:
  - each adapter built once, with Cost Explorer shared by both months;
  - exclusive End (year rollover, leap February) while the displayed end date stays the last day;
  - one failed lookup leaves the other fields intact;
  - get_cost_and_usage called with filter_expression/group_by;
  - empty ResultsByTime shapes give 0.00;
  - GuardDuty criteria archived Eq ["false"] on the first detector;
  - zero detectors gives "not_enabled" and no statistics call;
  - the per-field ⚠️ render;
  - ClientError/BotoCoreError from the health check replaces the loading modal with a bilingual error (logged with account_id);
  - KeyError propagates;
  - the sorted account selector;
  - request_health_modal shows the error modal on non-success and on a raised ClientError/BotoCoreError.
- The render and error-modal tests assert exact line fragments where the plan fixes the format ("⚠️ SecurityHub (unavailable)", "2024-11-01 - 2024-11-30: ⚠️ unavailable"). The error texts must contain "Please try again later." and "Veuillez réessayer plus tard.".
- Verified: freezegun freezes arrow.utcnow(). An AssumeRole failure at adapter build raises ClientError (STS) or BotoCoreError (e.g. NoCredentialsError).

Red-state evidence (from app/):
- uv run pytest tests/unit/modules/aws/test_aws_account_health_handler.py -> 22 failed, 4 errors, 3 passed. The 4 errors happen at fixture setup: the build_*_adapter patch targets don't exist yet. The 3 passes are intended regression guards: the ignore list, the happy-path render, and KeyError propagation.
- The same run with a scratch pytest plugin that stubs the missing factories and makes the legacy mirrors fail loudly (verification only, not committed) -> 26 failed, 3 passed. Every failure is for the intended reason: a legacy mirror is called (cost_explorer.get_cost_and_usage, organizations.list_organization_accounts), a helper still has its old signature, the modal renders "$None USD" / "not_enabled issues", or ClientError/BotoCoreError is raised instead of handled.
- uv run ruff check / ruff format on the file -> All checks passed (formatted).
- uv run mypy on the file -> 11 call-arg errors in the test file, all on the four helpers' new signatures; they clear on implementation. The remaining errors are existing ones in modules/ followed through imports.
- uv run pytest tests/unit/modules/aws/test_aws_command_handler.py -> 13 passed (unchanged).
<!-- SECTION:NOTES:END -->
