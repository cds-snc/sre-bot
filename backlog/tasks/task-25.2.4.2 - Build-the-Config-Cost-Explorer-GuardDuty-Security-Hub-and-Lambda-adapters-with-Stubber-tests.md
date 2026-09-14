---
id: TASK-25.2.4.2
title: >-
  Build the Config, Cost Explorer, GuardDuty, Security Hub and Lambda adapters
  with Stubber tests
status: In Progress
assignee: []
created_date: '2026-09-14 17:39'
updated_date: '2026-09-14 20:15'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.4
references:
  - app/integrations/aws/config.py
  - app/integrations/aws/cost_explorer.py
  - app/integrations/aws/guard_duty.py
  - app/integrations/aws/security_hub.py
  - app/integrations/aws/lambdas.py
  - app/integrations/aws/settings.py
  - app/packages/aws_platform/adapters/identity_center.py
  - app/packages/aws_platform/adapters/organizations.py
  - app/infrastructure/configuration/integrations/aws.py
  - app/tests/unit/integrations/aws/test_aws_settings_fields.py
  - app/tests/unit/integrations/aws/test_aws_client_classify_error.py
parent_task_id: TASK-25.2.4
priority: high
ordinal: 201000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 1b of TASK-25.2.4 (build phase, expand only, no caller changes). Create packages/aws_platform/adapters/{config,cost_explorer,guard_duty,security_hub,aws_lambda}.py following the shape landed by TASK-25.2.4.1 (organizations.py/sso_admin.py, itself from identity_center.py): typed client from get_aws_client with the role from SERVICE_ROLE_MAP, _call/_paginate + classify_aws_error, OperationResult returns, build_<svc>_adapter() factory, Stubber operations + provider tests. The Lambda module is aws_lambda.py, not lambda.py, because `lambda` is a Python keyword (human decision 2026-09-14).

Operations: config.describe_aggregate_compliance_by_config_rules (integrations/aws/config.py:12, AUDIT role); cost_explorer.get_cost_and_usage (cost_explorer.py:14, ORG role); guard_duty.list_detectors and get_findings_statistics (guard_duty.py:14,35, LOGGING role); security_hub.get_findings (security_hub.py:12, LOGGING role); aws_lambda.list_functions and list_layers (lambdas.py:9,24, no role, in-account like the mirror). lambdas.get_layer_version (lambdas.py:39) has zero production callers (re-grepped 2026-09-14) and is dropped, not ported. Re-verify before dropping.

Bug fixes in scope: Cost Explorer follows NextPageToken manually (no boto3 paginator); Security Hub paginates on the Findings key (the mirror's unkeyed paginator flattens NextToken into the result); Config omits Filters when none are given.

Settings: add securityhub -> LOGGING_ROLE_ARN to SERVICE_ROLE_MAP in integrations/aws/settings.py, mirrored in the legacy infrastructure settings map so the parity test holds ('lambda' deliberately has no entry). Add the clear-cut service codes to AWSSettings defaults: NOT_FOUND NoSuchConfigurationAggregatorException; UNAUTHORIZED InvalidAccessException; TRANSIENT InternalServerErrorException, InternalException, ServiceException, LimitExceededException (human decision 2026-09-14, same precedent as .1's Organizations not-found codes).

Size: ~485 production LOC across 7 files, over the ~400 guideline; kept as one PR by human decision 2026-09-14 (additive, single subsystem, repetitive boilerplate).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 packages/aws_platform/adapters/config.py, cost_explorer.py, guard_duty.py, security_hub.py and aws_lambda.py each return OperationResult from every operation, build their clients only through get_aws_client with the SERVICE_ROLE_MAP role (none for Lambda), and have Stubber operations and provider unit tests plus classification paths
- [ ] #2 Cost Explorer get_cost_and_usage follows NextPageToken across all pages and returns the concatenated ResultsByTime, verified by a two-page Stubber test
- [ ] #3 Security Hub get_findings returns a flat list of findings paginated on the Findings key, verified by a two-page Stubber test
- [ ] #4 SERVICE_ROLE_MAP maps securityhub to LOGGING_ROLE_ARN in integrations/aws/settings.py, and the settings parity test with the legacy infrastructure module stays green
- [ ] #5 AWSSettings defaults classify NoSuchConfigurationAggregatorException as NOT_FOUND, InvalidAccessException as UNAUTHORIZED, and InternalServerErrorException, InternalException, ServiceException and LimitExceededException as TRANSIENT, covered by test_aws_client_classify_error.py cases
- [ ] #6 lambdas.get_layer_version is re-grepped for callers and dropped (not ported) if still unused
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUND TRUTH (read 2026-09-14): TASK-25.2.4.1's closed plan and notes; landed adapters app/packages/aws_platform/adapters/{organizations.py (118 LOC), sso_admin.py (178), identity_center.py (306)} and their tests under app/tests/unit/packages/aws_platform/; legacy mirrors app/integrations/aws/{config.py 45, cost_explorer.py 42, guard_duty.py 71, security_hub.py 32, lambdas.py 58}; app/integrations/aws/{client.py, settings.py}; app/infrastructure/configuration/integrations/aws.py; legacy tests tests/integrations/aws/test_{legacy_config,cost_explorer,guard_duty,security_hub,lambas}.py; tests/unit/integrations/aws/{test_aws_client_classify_error.py, test_aws_settings_fields.py}; callers modules/aws/{spending.py, aws_account_health.py, lambdas.py}; downstream tasks .4.4/.4.5/.4.6; bin/check_sdk_typing.py and bin/check_vendor_package_contract.py. botocore service models introspected locally (`client.can_paginate`, operation input/output/error shapes).

ALIGNMENT WITH TASK-25.2.4.1 (applied verbatim, no reinvention)
- Adapter shape: class holding one typed client (TYPE_CHECKING import from types_boto3_<svc>), `_map_sdk_exception` staticmethod logging `aws_<svc>_operation_failed`, `_call[T]` catching only (ClientError, BotoCoreError), `_paginate(paginator_name: _PaginatorName, response_key, **kwargs)` with the list-type guard per page, module-level `build_<svc>_adapter()` reading `get_aws_settings().SERVICE_ROLE_MAP.get(<svc>) or None` (organizations.py:30-118). Module docstring states "build at function entry, never at import" (eager AssumeRole).
- Tests: `test_aws_platform_<svc>_operations.py` (one TestX class per operation + TestErrorClassification on one representative operation) and `test_aws_platform_<svc>_provider.py` (records get_aws_client args; asserts service name, role ARN, empty setting -> None), same as organizations_{operations,provider}.py. `pytestmark = pytest.mark.unit`, real boto3 client with dummy credentials wrapped in botocore.stub.Stubber.
- Standing decisions carried from TASK-25.2.4 notes: Stubber (not moto), fix bugs in touched files simply, legacy tests not rewritten (their pinned cases are carried into the new tests; files deleted in .4.7).
- Settings follow-up precedent: .1 added service-specific codes to AWSSettings.NOT_FOUND_CODES (human option B). This slice does the same for its five services (human decision 2026-09-14, below).
- No infrastructure/services/providers.py registration, no client.py change: get_aws_client already has Literal overloads for ce, config, guardduty, securityhub, lambda (client.py:89-127) and the stubs are installed (types-boto3-ce/config/guardduty/securityhub/lambda).
- Guard scripts: check_sdk_typing.py and check_vendor_package_contract.py scan only integrations/, so new packages/ files need no baseline entry.

HUMAN DECISIONS 2026-09-14 (this planning session)
1. MODULE NAME: `lambda` is a Python keyword, so `adapters/lambda.py` is unimportable. The Lambda adapter is `packages/aws_platform/adapters/aws_lambda.py` (LambdaAdapter, build_lambda_adapter). TASK-25.2.4.6 imports from that module.
2. SIZE GATE: estimate is ~480 production LOC across 7 files, over the ~400 LOC gate (the coordinator estimated ~260). Human chose to keep one PR: purely additive, one subsystem, repetitive boilerplate that reviews quickly. No split, no shared-base extraction (which would leave the three landed adapters inconsistent or mix a refactor in).
3. ERROR CODES: add the clear-cut unmapped codes these services raise to AWSSettings defaults. NOT_FOUND: NoSuchConfigurationAggregatorException. UNAUTHORIZED: InvalidAccessException (Security Hub not enabled/subscribed). TRANSIENT: InternalServerErrorException (GuardDuty), InternalException (Security Hub), ServiceException (Lambda), LimitExceededException (Cost Explorer, Security Hub throttling). Left propagating as programmer/input errors: BadRequestException, InvalidInputException, ValidationException, InvalidParameterValueException, InvalidLimitException, InvalidNextTokenException, RequestChangedException, DataUnavailableException, BillExpirationException.

STEP 1 - app/integrations/aws/settings.py (+ legacy parity line)
- SERVICE_ROLE_MAP (settings.py:107-116): add `"securityhub": self.LOGGING_ROLE_ARN`. 'lambda' deliberately gets no entry (in-account).
- CONFLICT RESOLVED BY DEFAULT (flag for review): tests/unit/integrations/aws/test_aws_settings_fields.py:136 asserts AWSSettings().SERVICE_ROLE_MAP == the legacy InfrastructureAwsSettings().SERVICE_ROLE_MAP "while both exist". Add the same one line to app/infrastructure/configuration/integrations/aws.py:62-71 so the parity guard stays meaningful (neither map has a production reader other than the adapters' build_* factories; the legacy mirrors pass role ARNs explicitly). Update the pinned dict in test_aws_settings_fields.py:119-128 with the securityhub key.
- NOT_FOUND_CODES / UNAUTHORIZED_CODES / TRANSIENT_CODES defaults (settings.py:56-94): append the codes from decision 3.

STEP 2 - app/packages/aws_platform/adapters/config.py (new, ~90 LOC)
ConfigAdapter(client: ConfigServiceClient). `_PaginatorName = Literal["describe_aggregate_compliance_by_config_rules"]`.
- `describe_aggregate_compliance_by_config_rules(config_aggregator_name: str, filters: dict[str, Any] | None = None) -> OperationResult[list[dict[str, Any]]]`: `_paginate(..., "AggregateComplianceByConfigRules", ConfigurationAggregatorName=name, **({"Filters": filters} if filters else {}))`. Port of config.py:12-45 (already paginated with keys=[...]).
- BUG FIX (touched-file policy): the mirror always sends `Filters=filters`, so `filters=None` raises botocore ParamValidationError (a BotoCoreError -> would be classified TRANSIENT in the adapter). Omit the key when no filters are given.
- `build_config_adapter()`: role SERVICE_ROLE_MAP["config"] (AUDIT_ROLE_ARN), matching config.py:37.

STEP 3 - app/packages/aws_platform/adapters/cost_explorer.py (new, ~100 LOC)
CostExplorerAdapter(client: CostExplorerClient). No `_paginate`/`_PaginatorName`: botocore confirms `can_paginate("get_cost_and_usage") is False`.
- `get_cost_and_usage(time_period: dict[str, str], granularity: GranularityType, metrics: list[str], filter_expression: dict[str, Any] | None = None, group_by: list[dict[str, str]] | None = None) -> OperationResult[list[dict[str, Any]]]` (GranularityType from types_boto3_ce.literals under TYPE_CHECKING; `filter_expression` avoids shadowing the builtin).
- BUG FIX (TASK notes #1): manual NextPageToken loop inside one `_call("get_cost_and_usage", collect)`: build params once (Filter/GroupBy only when provided, as cost_explorer.py:26-29), call, extend results with `ResultsByTime`, repeat with `NextPageToken=token` while the response carries a non-empty NextPageToken. Params are identical across pages (CE raises RequestChangedException otherwise).
- RETURN SHAPE: the concatenated ResultsByTime list, not the raw response. Both callers read only ResultsByTime (spending.py:88 extends it; aws_account_health.py:54 indexes [0]); GroupDefinitions/DimensionValueAttributes have no reader (rg, excluding tests). With GroupBy, one TimePeriod can repeat across pages carrying different Groups; concatenation keeps every group, and .4.4 iterates groups per entry. Recorded for .4.4/.4.5.
- `build_cost_explorer_adapter()`: role SERVICE_ROLE_MAP["ce"] (ORG_ROLE_ARN), matching cost_explorer.py:35. Region stays AWS_REGION like the mirror.

STEP 4 - app/packages/aws_platform/adapters/guard_duty.py (new, ~100 LOC)
GuardDutyAdapter(client: GuardDutyClient). `_PaginatorName = Literal["list_detectors"]`; `_paginate` typed `list[Any]` so DetectorIds (list[str]) fits.
- `list_detectors() -> OperationResult[list[str]]`: `_paginate("list_detectors", "DetectorIds")`, port of guard_duty.py:14-31.
- `get_findings_statistics(detector_id: str, finding_criteria: dict[str, Any] | None = None) -> OperationResult[dict[str, int]]`: single call, `FindingStatisticTypes=["COUNT_BY_SEVERITY"]`, FindingCriteria only when provided (guard_duty.py:50-55). Not paginated: the input shape has no NextToken and the output NextToken is documented "currently not supported". Returns `response.get("FindingStatistics", {}).get("CountBySeverity", {})`, i.e. the only statistic requested (legacy returned the raw response; aws_account_health.py:79 reads exactly this path, and the legacy empty case pins `{}`). Same inner-object precedent as organizations.get_account_details.
- Out of scope: the `["false", "false"]` duplication and `detector_ids[0]` crash belong to .4.5 (its notes #2, #3).
- `build_guard_duty_adapter()`: role SERVICE_ROLE_MAP["guardduty"] (LOGGING_ROLE_ARN).

STEP 5 - app/packages/aws_platform/adapters/security_hub.py (new, ~90 LOC)
SecurityHubAdapter(client: SecurityHubClient). `_PaginatorName = Literal["get_findings"]`.
- `get_findings(filters: dict[str, Any]) -> OperationResult[list[dict[str, Any]]]`: `_paginate("get_findings", "Findings", Filters=filters)`.
- BUG FIX (TASK notes #2): the mirror paginates with keys=None, so client.py's legacy paginator flattens every page field (including NextToken) into one list. The adapter returns a flat list of findings keyed on "Findings". .4.5 counts with len(result.data) instead of summing per-page len(res["Findings"]).
- `build_security_hub_adapter()`: role SERVICE_ROLE_MAP["securityhub"] (LOGGING_ROLE_ARN, new entry from Step 1), matching security_hub.py:27.

STEP 6 - app/packages/aws_platform/adapters/aws_lambda.py (new, ~95 LOC)
LambdaAdapter(client: LambdaClient). `_PaginatorName = Literal["list_functions", "list_layers"]`.
- `list_functions() -> OperationResult[list[dict[str, Any]]]`: `_paginate("list_functions", "Functions")` (lambdas.py:9-21).
- `list_layers() -> OperationResult[list[dict[str, Any]]]`: `_paginate("list_layers", "Layers")` (lambdas.py:24-36).
- DROPPED, not ported: `get_layer_version` (lambdas.py:39-58). Re-grepped 2026-09-14 with `rg -n 'get_layer_version' app --glob '!tests/**'`: only its own definition, plus baseline lines naming the whole lambdas.py module. Re-run immediately before implementation (AC#6).
- `build_lambda_adapter()`: `get_aws_client("lambda", role_arn=get_aws_settings().SERVICE_ROLE_MAP.get("lambda") or None)`, which resolves to None today. Verified in-account parity: the mirror passes no role_arn, and legacy get_aws_service_client builds a plain ambient boto3.Session when role_arn is falsy (client.py:332). execute_aws_api_call's docstring claim of an ORG_ROLE fallback is stale.

STEP 7 - tests (non-production, not gated). New files under app/tests/unit/packages/aws_platform/:
test_aws_platform_{config,cost_explorer,guard_duty,security_hub,lambda}_{operations,provider}.py (10 files). Modified: tests/unit/integrations/aws/test_aws_client_classify_error.py (extend the parametrize lists at :33-50), tests/unit/integrations/aws/test_aws_settings_fields.py (:119 pinned map). TDD: write these red first, then Steps 1-6.

TEST MATRIX (* = pinned case carried from the legacy test file, which is left untouched and deleted in .4.7)
| Case | Op | New test | AC | Legacy carried |
|---|---|---|---|---|
| Single page | config.describe_aggregate_compliance_by_config_rules | test_describe_aggregate_compliance_single_page | 1 | ..._returns_compliance_list_when_success* |
| Two pages via NextToken | same | test_describe_aggregate_compliance_pagination_two_pages | 1 | none |
| Empty | same | test_describe_aggregate_compliance_empty | 1 | ..._returns_empty_compliance_list* |
| Filters sent (expected_params) / omitted when None | same | test_describe_aggregate_compliance_sends_filters_only_when_given | 1 | ..._passes_filters_to_api_call* |
| Single page, raw response reduced to ResultsByTime | cost_explorer.get_cost_and_usage | test_get_cost_and_usage_single_page | 1 | ..._returns_cost_and_usage_list_when_success* |
| Two pages via NextPageToken, second request echoes token + identical params | same | test_get_cost_and_usage_follows_next_page_token | 2 | none (bug fix) |
| Filter/GroupBy sent only when provided | same | test_get_cost_and_usage_sends_filter_and_group_by_only_when_given | 1 | ..._adds_filters_and_group_by_if_provided* |
| Single + two pages | guard_duty.list_detectors | test_list_detectors_single_page, test_list_detectors_pagination_two_pages | 1 | ..._returns_list_when_success* |
| Empty | same | test_list_detectors_empty | 1 | ..._returns_empty_list_when_no_detectors* |
| CountBySeverity returned, COUNT_BY_SEVERITY + criteria sent | guard_duty.get_findings_statistics | test_get_findings_statistics_returns_count_by_severity | 1 | ..._returns_statistics_when_success*, ..._parse_finding_criteria* |
| No statistics -> {} | same | test_get_findings_statistics_empty_returns_empty_dict | 1 | ..._returns_empty_object_if_no_statistics_found* |
| Single page flat findings | security_hub.get_findings | test_get_findings_single_page | 1,3 | ..._returns_findings_list_when_success* |
| Two pages flattened to findings only (no NextToken leak) | same | test_get_findings_pagination_two_pages_returns_flat_findings | 3 | none (bug fix) |
| Empty | same | test_get_findings_empty | 1 | ..._returns_empty_findings_list*, ..._when_no_findings* |
| Single + two pages via NextMarker | aws_lambda.list_functions | test_list_functions_single_page, test_list_functions_pagination_two_pages | 1 | test_list_functions* |
| Single page | aws_lambda.list_layers | test_list_layers_single_page | 1 | test_list_layers* |
| Classification per adapter (representative op): NOT_FOUND/UNAUTHORIZED/TRANSIENT with retry_after/BotoCoreError transient/unmapped ClientError propagates/programmer error propagates | one op per adapter | TestErrorClassification (6 tests x 5 adapters) | 1 | none |
| Service-specific code per adapter: Config NoSuchConfigurationAggregatorException->NOT_FOUND; Security Hub InvalidAccessException->UNAUTHORIZED; GuardDuty InternalServerErrorException->TRANSIENT and BadRequestException propagates; Lambda ServiceException->TRANSIENT; CE LimitExceededException->TRANSIENT and DataUnavailableException propagates | representative op | test_<code>_classification | 1,5 | none |
| Factory: service name + role ARN; empty setting -> None | build_*_adapter x5 (Lambda: role_arn None even with every role ARN env var set) | test_aws_platform_<svc>_provider.py | 1 | none |
| New default codes classify as intended | classify_aws_error | extended parametrize cases in test_aws_client_classify_error.py | 5 | none |
| SERVICE_ROLE_MAP has securityhub -> logging; parity with legacy module holds | settings | test_service_role_map_composes_the_configured_role_arns (updated), ..._matches_the_infrastructure_module_while_both_exist (unchanged, stays green) | 4 | none |
Not carried: test_get_layer_version (dropped function).

AC TRACEABILITY
- AC#1 <- Steps 2-6 + every operations/provider test above
- AC#2 (CE NextPageToken) <- Step 3, test_get_cost_and_usage_follows_next_page_token
- AC#3 (Security Hub flat Findings) <- Step 5, test_get_findings_pagination_two_pages_returns_flat_findings
- AC#4 (securityhub role map) <- Step 1, test_aws_settings_fields.py map tests + test_aws_platform_security_hub_provider.py
- AC#5 (error codes) <- Step 1, test_aws_client_classify_error.py cases + per-adapter service-code tests
- AC#6 (get_layer_version drop) <- Step 6 re-grep; no test (removal step)

ASSUMPTIONS (each with how to verify)
- Adding LimitExceededException to TRANSIENT_CODES also changes DynamoDB's LimitExceededException (control-plane concurrency limit) from propagate to TRANSIENT for existing classify_aws_error users. That is a retry-later condition, so acceptable. Verify with `rg -n 'LimitExceededException|InternalException|ServiceException|InvalidAccessException|NoSuchConfigurationAggregatorException|InternalServerErrorException' app --glob '!.venv/**'`: 0 production hits on 2026-09-14. Identitystore/Shield use differently spelled codes (InternalServerException, LimitsExceededException, InternalErrorException), so they're unaffected.
- No AWS_*_CODES env override exists outside tests (same check .1 made). Verify with `rg -n 'AWS_(NOT_FOUND|UNAUTHORIZED|TRANSIENT)_CODES' --glob '!app/tests/**' .` (terraform/ and compose files included).
- Cost Explorer's endpoint resolves from AWS_REGION exactly as today (the mirror builds its client in the same region), so there's no behaviour change.
- Returning reduced shapes (ResultsByTime list, CountBySeverity dict, flat Findings) is safe in an expand-only slice with no callers; .4.4/.4.5 consume these shapes. Recorded in their notes when they start.

BLAST RADIUS AND ROLLBACK
- New adapters: zero production callers; the mirrors keep serving traffic. Reverting the PR is a no-op for adapter behaviour.
- settings.py code lists: live today for identity_center, access sync, DynamoDB and Shield classify_aws_error users. The only overlap is DynamoDB LimitExceededException (see assumptions). A revert restores the lists exactly.
- SERVICE_ROLE_MAP securityhub line in both settings modules: no current reader, so no runtime effect until .4.5.
- No ordering constraints, no env/terraform changes.

SIZE ESTIMATE AND GATE VERDICT
- Production: 5 new adapter files (~90 + 100 + 100 + 90 + 95 = ~475 LOC incl. docstrings), settings.py (~8 LOC), infrastructure/configuration/integrations/aws.py (1 LOC). Total ~485 LOC across 7 files, one subsystem (AWS client/adapters), purely additive, no mechanical refactor.
- Tests: 10 new files + 2 modified (not gated).
- VERDICT: over the ~400 LOC guideline. Kept as one PR by human decision 2026-09-14 (see decision 2).

VERIFICATION (from app/)
cd app && uv run ruff check .
cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'
cd app && uv run pytest tests --ignore=tests/smoke
(Known pre-existing: 6 order-dependent failures in test_webhooks_aws_sns.py and directory/test_google.py; mypy errors outside this change. Call them out, don't fix them.)

OPEN QUESTIONS FOR HUMAN REVIEW
None. Parity resolution confirmed 2026-09-14.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Candidate bugs verified 2026-09-14 during TASK-25.2.4.1 planning (organizations/sso_admin scope); these are owned by .4.2 (Config/CE/GuardDuty/SecurityHub/Lambda adapters), not .1:

1. CONFIRMED - Cost Explorer's get_cost_and_usage has no boto3 paginator (confirmed via AWS/boto3 docs: GetCostAndUsage is not in the Cost Explorer paginator list) but its response can include NextPageToken when results exceed one page. The legacy mirror (integrations/aws/cost_explorer.py) and both its callers (spending.py, aws_account_health.py - see notes on TASK-25.2.4.4 and TASK-25.2.4.5) make a single call and never read NextPageToken. The new Cost Explorer adapter needs a manual NextPageToken loop (there is no client.get_paginator("get_cost_and_usage") to lean on, unlike the other adapters' paginate() helpers) so results aren't silently truncated.

2. CONFIRMED - integrations/aws/security_hub.py's get_findings calls execute_aws_api_call(service, "get_findings", paginated=True, ...) without a keys= argument. client.py's generic paginator() only flattens by named keys when keys is not None; with keys=None it flattens every non-ResponseMetadata field from each page - including scalar fields like NextToken - into one flat list alongside the Findings list items, corrupting the shape aws_account_health.py:105-109 expects (a list of {"Findings": [...]} page dicts). Also see the cross-reference on TASK-25.2.4.5. Fix when building the Security Hub adapter: paginate with an explicit response_key="Findings" using the identity_center.py _paginate() pattern (response_key parameter, list-type guard on each page's value) rather than reusing the legacy unkeyed paginator() helper's behavior.

Plan review 2026-09-14 (human): (1) confirmed adding securityhub to the legacy infrastructure settings map as well, keeping the parity test; (2) accepted LimitExceededException -> TRANSIENT for every classify_aws_error user, including DynamoDB; revert that entry if it causes issues; (3) return shapes and the aws_lambda module name are cross-referenced in the notes of TASK-25.2.4.4, .4.5 and .4.6.
<!-- SECTION:NOTES:END -->
