---
id: TASK-25.2.4.2
title: >-
  Build the Config, Cost Explorer, GuardDuty, Security Hub and Lambda adapters
  with Stubber tests
status: To Do
assignee: []
created_date: '2026-09-14 17:39'
updated_date: '2026-09-14 17:57'
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
parent_task_id: TASK-25.2.4
priority: high
ordinal: 201000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 1b of TASK-25.2.4 (build phase, expand only, no caller changes). Create packages/aws_platform/adapters/{config,cost_explorer,guard_duty,security_hub,lambda}.py following the shape proven by identity_center.py. config.describe_aggregate_compliance_by_config_rules (integrations/aws/config.py:12) with role_arn=AUDIT_ROLE_ARN; cost_explorer.get_cost_and_usage (cost_explorer.py:14) with role_arn=ORG_ROLE_ARN; guard_duty.list_detectors and get_findings_statistics (guard_duty.py:14,35) with role_arn=LOGGING_ROLE_ARN; security_hub.get_findings (security_hub.py:12) with role_arn=LOGGING_ROLE_ARN; lambdas.list_functions and list_layers (lambdas.py:9,24) with no role_arn (in-account, matching today's mirror). lambdas.get_layer_version (lambdas.py:39) has zero production callers (re-grepped 2026-09-14) and is dropped, not ported -- re-verify before dropping. Fix integrations/aws/settings.py:105-116 SERVICE_ROLE_MAP: it is missing a 'securityhub' -> LOGGING_ROLE_ARN entry (security_hub.py:12 already uses LOGGING_ROLE_ARN directly today) -- add it; 'lambda' correctly has no entry (no role assumed).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 packages/aws_platform/adapters/config.py, cost_explorer.py, guard_duty.py, security_hub.py and lambda.py each return OperationResult from every operation, build their clients only through get_aws_client, and have Stubber unit tests for each operation plus classification paths
- [ ] #2 integrations/aws/settings.py SERVICE_ROLE_MAP includes a securityhub entry mapped to LOGGING_ROLE_ARN
- [ ] #3 lambdas.get_layer_version is re-grepped for callers and dropped (not ported) if still unused
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Candidate bugs verified 2026-09-14 during TASK-25.2.4.1 planning (organizations/sso_admin scope); these are owned by .4.2 (Config/CE/GuardDuty/SecurityHub/Lambda adapters), not .1:

1. CONFIRMED - Cost Explorer's get_cost_and_usage has no boto3 paginator (confirmed via AWS/boto3 docs: GetCostAndUsage is not in the Cost Explorer paginator list) but its response can include NextPageToken when results exceed one page. The legacy mirror (integrations/aws/cost_explorer.py) and both its callers (spending.py, aws_account_health.py - see notes on TASK-25.2.4.4 and TASK-25.2.4.5) make a single call and never read NextPageToken. The new Cost Explorer adapter needs a manual NextPageToken loop (there is no client.get_paginator("get_cost_and_usage") to lean on, unlike the other adapters' paginate() helpers) so results aren't silently truncated.

2. CONFIRMED - integrations/aws/security_hub.py's get_findings calls execute_aws_api_call(service, "get_findings", paginated=True, ...) without a keys= argument. client.py's generic paginator() only flattens by named keys when keys is not None; with keys=None it flattens every non-ResponseMetadata field from each page - including scalar fields like NextToken - into one flat list alongside the Findings list items, corrupting the shape aws_account_health.py:105-109 expects (a list of {"Findings": [...]} page dicts). Also see the cross-reference on TASK-25.2.4.5. Fix when building the Security Hub adapter: paginate with an explicit response_key="Findings" using the identity_center.py _paginate() pattern (response_key parameter, list-type guard on each page's value) rather than reusing the legacy unkeyed paginator() helper's behavior.
<!-- SECTION:NOTES:END -->
