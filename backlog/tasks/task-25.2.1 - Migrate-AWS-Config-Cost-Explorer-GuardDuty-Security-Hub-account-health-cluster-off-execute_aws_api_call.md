---
id: TASK-25.2.1
title: >-
  Migrate AWS Config/Cost Explorer/GuardDuty/Security Hub (account-health
  cluster) off execute_aws_api_call
status: To Do
assignee: []
created_date: '2026-07-31 18:48'
updated_date: '2026-08-04 19:39'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-22.2
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/aws/config.py
  - app/integrations/aws/cost_explorer.py
  - app/integrations/aws/guard_duty.py
  - app/integrations/aws/security_hub.py
parent_task_id: TASK-25.2
priority: high
ordinal: 118000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 1 of TASK-25.2 (smallest, done first). Migrate integrations/aws/{config,cost_explorer,guard_duty,security_hub}.py off integrations/aws/client.py's execute_aws_api_call/handle_aws_api_errors onto get_aws_client + classify_aws_error (reuse/extend the TASK-22.2 primitive; these 4 services have no existing get_aws_client instance yet - add them). Production consumers (grep-confirmed 2026-07-31): modules/aws/aws_account_health.py (all 4 services) and modules/aws/spending.py (cost_explorer only). Critically: today's handle_aws_api_errors SWALLOWS all exceptions and returns False - the migration must convert this to raise+classify (explicit OperationResult or a documented behavior change at the 2 consumer call sites), not silently preserve the swallow; flag the exact resulting behavior for human sign-off since it is not zero-diff.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/aws/config.py, cost_explorer.py, guard_duty.py, and security_hub.py no longer call execute_aws_api_call/handle_aws_api_errors; each routes through get_aws_client(<service>) + classify_aws_error, raising/classifying per the outbound-clients.md contract
- [ ] #2 modules/aws/aws_account_health.py and modules/aws/spending.py are updated to handle the new raise+classify contract explicitly (no silent False-swallowing); resulting behavior on error paths is documented and human-reviewed, not assumed zero-diff
- [ ] #3 classify_aws_error gains any Config/CostExplorer/GuardDuty/SecurityHub-specific mapped families with unit coverage under tests/unit/integrations/aws/
- [ ] #4 moto-backed integration conformance test(s) under app/tests/integration/ exercise cost_explorer.py's get_cost_and_usage and security_hub.py's get_findings against real ce/securityhub semantics via moto.mock_aws(), additive alongside existing MagicMock-based unit tests -- EXCLUDES config.py (its sole call, describe_aggregate_compliance_by_config_rules, is unimplemented in moto per getmoto/moto IMPLEMENTATION_COVERAGE.md) and guard_duty.py's get_findings_statistics (also unimplemented in moto); guard_duty.py's list_detectors MAY be moto-covered but is not required by this AC since get_findings_statistics cannot be, so this task's guardduty/config paths keep MagicMock-only coverage
<!-- AC:END -->
