---
id: TASK-25.2.4.4
title: Migrate spending.py onto the Organizations and Cost Explorer adapters
status: To Do
assignee: []
created_date: '2026-09-14 17:39'
updated_date: '2026-09-14 17:57'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.4.1
  - TASK-25.2.4.2
references:
  - app/modules/aws/spending.py
  - app/tests/unit/modules/aws/test_spending_handler.py
parent_task_id: TASK-25.2.4
priority: high
ordinal: 203000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2b of TASK-25.2.4. modules/aws/spending.py: organizations.list_organization_accounts() (line 40, list comprehension crashes on False), organizations.get_account_details()/get_account_tags() (lines 61-62, dict access crashes on False), cost_explorer.get_cost_and_usage() (line 79, .get('ResultsByTime', []) at line 88 crashes on False since a bool has no .get). Replace each with the organizations/cost_explorer adapters, branching on OperationResult explicitly. generate_spending_data, get_accounts_details and get_accounts_spending change signature/behaviour on failure (currently silently propagate a TypeError); decide and document whether a partial-failure account is skipped-and-logged or the whole run aborts, consistent with execute_spending_data_update_job's existing failure handling (lines 205-225, which already logs and returns early on empty/failed data).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 modules/aws/spending.py no longer imports integrations.aws.organizations or integrations.aws.cost_explorer; all four call sites use the organizations and cost_explorer adapters and branch on OperationResult explicitly
- [ ] #2 The four call sites that crashed on a bare False return (TASK-25.2.1 characterization) instead produce a logged failure that generate_spending_data/execute_spending_data_update_job handle without raising; the pinned crash tests in tests/unit/modules/aws/test_spending_handler.py are replaced by tests of the new explicit-status behaviour
- [ ] #3 Per-call-site error-path behaviour is documented in the task notes for review
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Candidate bugs verified 2026-09-14 during TASK-25.2.4.1 planning (organizations/sso_admin scope); these are owned by .4.4 (spending.py), not .1:

1. CONFIRMED - Cost Explorer TimePeriod.End is exclusive (AWS docs: 'The end date is exclusive... retrieves cost and usage data up to, but not including, end'). spending.py:73-77 sets end_date = start_date + pd.offsets.MonthEnd(1) (the last calendar day of the month) as TimePeriod.End, so the last day of every month's cost is silently dropped from the report. Simple fix when migrating onto the Cost Explorer adapter: pass end_date + 1 day (first day of the next month) as End.

2. CONFIRMED - spending.py:40 `account_ids = [account["Id"] for account in organizations.list_organization_accounts()]` crashes with TypeError if list_organization_accounts() returns the legacy False-on-error sentinel (handle_aws_api_errors). Already covered by TASK-25.2.4 AC#4 (crash-on-False sites); citing the exact line here for traceability - handle it as one of the 4 spending.py sites when migrating onto the Organizations adapter's OperationResult.

3. CONFIRMED - spending.py:61-63 `details = organizations.get_account_details(id); account_tags = organizations.get_account_tags(id); details["Tags"] = account_tags` mutates `details` without checking it for False first; if get_account_details errors, details is False and `details["Tags"] = ...` raises TypeError, aborting the whole account batch. Same AC#4 crash-on-False class; fold into the OperationResult migration (check organizations_adapter.get_account_details(id).is_success before building the Tags dict).

4. CONFIRMED, cross-referenced on TASK-25.2.4.2 - spending.py:79-88 calls Cost Explorer get_cost_and_usage in a single call per month with no NextPageToken handling. get_cost_and_usage has no boto3 paginator (manual token loop required, confirmed via AWS/boto3 docs), so a response with more than one page silently drops results. The Cost Explorer adapter built in .4.2 needs a manual NextPageToken loop; when migrating spending.py onto it in .4.4, verify the adapter already loops and that spending.py doesn't need its own workaround.
<!-- SECTION:NOTES:END -->
