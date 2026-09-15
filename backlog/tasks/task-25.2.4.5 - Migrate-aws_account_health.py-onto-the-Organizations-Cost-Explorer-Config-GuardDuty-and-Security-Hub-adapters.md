---
id: TASK-25.2.4.5
title: >-
  Migrate aws_account_health.py onto the Organizations, Cost Explorer, Config,
  GuardDuty and Security Hub adapters
status: To Do
assignee: []
created_date: '2026-09-14 17:39'
updated_date: '2026-09-14 20:01'
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
parent_task_id: TASK-25.2.4
priority: high
ordinal: 204000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2c of TASK-25.2.4, largest single-file migration (5 adapters, 6 call sites in modules/aws/aws_account_health.py). get_account_spend (line 53: cost_explorer.get_cost_and_usage, line 54 crashes indexing response['ResultsByTime'][0] on False); get_config_summary (line 66: config.describe_aggregate_compliance_by_config_rules, len() crashes on False); get_guardduty_summary (line 70: guard_duty.list_detectors, line 78 indexes detector_ids[0] which crashes on False/empty; line 78: guard_duty.get_findings_statistics, line 79 dict-indexes crashes on False); get_securityhub_summary (line 105: security_hub.get_findings, line 108 iterates crashes on False); request_health_modal (line 211: organizations.list_organization_accounts, line 220 comprehension crashes on False). Each becomes an explicit OperationResult branch; get_account_health's aggregate dict (lines 23-44) and health_view_handler's Slack modal (lines 122-207) need a defined per-field fallback (e.g. 'unknown'/'N/A' string and a note in the modal) when a sub-call fails, since today's crash silently blocked the whole health check.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 modules/aws/aws_account_health.py no longer imports integrations.aws.{organizations,cost_explorer,config,guard_duty,security_hub}; all six call sites use the corresponding adapters and branch on OperationResult explicitly
- [ ] #2 The six call sites that crashed on a bare False/empty return (TASK-25.2.1 characterization) instead produce a logged failure with a defined per-field fallback shown in the Slack health modal; the pinned crash tests in tests/unit/modules/aws/test_aws_account_health_handler.py are replaced by tests of the new explicit-status behaviour
- [ ] #3 Per-call-site error-path behaviour, including the guard_duty two-call chain's behaviour when list_detectors returns zero detectors, is documented in the task notes for review
<!-- AC:END -->

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
<!-- SECTION:NOTES:END -->
