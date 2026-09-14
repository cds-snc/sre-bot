---
id: TASK-25.2.4.4
title: Migrate spending.py onto the Organizations and Cost Explorer adapters
status: To Do
assignee: []
created_date: '2026-09-14 17:39'
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
