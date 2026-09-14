---
id: TASK-25.2.4.5
title: >-
  Migrate aws_account_health.py onto the Organizations, Cost Explorer, Config,
  GuardDuty and Security Hub adapters
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
