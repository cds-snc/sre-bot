---
id: TASK-98
title: >-
  Stop re-assuming the AWS role on every adapter build: eager AssumeRole runs
  uncached per call site
status: To Do
assignee: []
created_date: '2026-09-17 19:06'
labels:
  - clients
  - architecture
dependencies:
  - TASK-92
references:
  - app/integrations/aws/client.py
  - app/integrations/aws/settings.py
  - app/modules/aws/ops_group_assignment.py
  - app/jobs/scheduled_tasks.py
  - decisions/outbound-clients.md
priority: medium
ordinal: 226000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-09-17 while investigating the make dev boot crash for TASK-92. Not covered by TASK-89 (portability), TASK-92 (health/startup model), TASK-25.2.6 (dispatcher removal) or TASK-88 (dissolve aws_platform): those own the BOOT-time consequence of eager AssumeRole, this owns the PER-CALL runtime cost.

MECHANISM (verified on main @ 27fb2bda). integrations/aws/client.py:154 -> :181 -> :192 performs a live sts:AssumeRole inside get_aws_client whenever role_arn is truthy, at client CONSTRUCTION. client.py:7-9 states the deliberate design: "Clients are built per call and never cached, so assumed credentials never need refreshing." No build_*_adapter() in packages/aws_platform/adapters/ is lru_cached, so every call site pays a fresh STS round-trip.

MEASURED. Repeated build_identity_center_adapter() calls each opened a new STS socket connection (1, 1, 1 over three calls; no caching). Builders that construct BOTH a retrying and a retries-disabled client make it two AssumeRole calls per build: identity_center.py:304-305 and dynamodb.py:132-133.

AFFECTED SERVICES. Only those with a SERVICE_ROLE_MAP entry resolving to a non-empty ARN (integrations/aws/settings.py:113-125): audit, organizations, identitystore, sso-admin, logging, ce, config, guardduty, securityhub. dynamodb has NO entry, so role_arn is None and storage/idempotency pay nothing — which is why local DynamoDB work is unaffected.

CALL SITES THAT AMPLIFY (build inside a request or job, not once):
- modules/aws/ops_group_assignment.py:24, :49, :63 - three builders in one flow (identity_center + organizations + sso_admin) = 4 AssumeRole calls per invocation.
- jobs/scheduled_tasks.py:127 - build_identity_center_adapter().healthcheck() on the 5-minute integration_healthchecks loop = 2 AssumeRole calls every 5 minutes, for a probe whose result is only logged.
- modules/provisioning/users.py:61, modules/provisioning/groups.py:142, modules/aws/lambdas.py:56 and :85, plus the aws_account_health.py and spending.py builders.

WHY IT MATTERS. STS AssumeRole is account-throttled and adds a serialized network round-trip to the front of every AWS operation, so the cost is latency and a throttling ceiling that scales with traffic rather than with the number of roles. The current design trades that for never having to refresh credentials.

SCOPE. Decide and implement how assumed credentials are reused: botocore's own refreshable credential provider, a TTL cache keyed on (role_arn, session_name, retries), or caching the adapter rather than the client. Expiry, refresh-before-expiry and thread/async safety must be explicit, and the "never need refreshing" docstring claim in client.py must be updated or defended. TASK-92 AC#1 decides whether AssumeRole may happen at boot at all; this task must not contradict that outcome, which is why it depends on TASK-92.

OUT OF SCOPE: the boot-time failure itself (TASK-92), off-AWS credential acquisition (TASK-89), and the fate of the integration_healthchecks loop (TASK-92 AC#4).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The per-call AssumeRole amplification is measured and recorded before any change: STS calls per build for each affected builder, and per invocation for ops_group_assignment.py and the 5-minute healthcheck loop
- [ ] #2 A credential-reuse mechanism is chosen and recorded with alternatives and tradeoffs (botocore refreshable provider vs TTL cache keyed on role_arn/session_name/retries vs adapter-level caching), covering expiry, refresh-before-expiry and concurrency safety
- [ ] #3 After the change, repeated builds of the same adapter make at most one AssumeRole call per credential lifetime, proven by a test that counts STS calls across repeated builds; the two-client builders (identity_center.py:304-305, dynamodb.py:132-133) do not double it
- [ ] #4 Credentials are not shared across different role_arn or session_name values, pinned by a test
- [ ] #5 The integrations/aws/client.py module docstring claim 'Clients are built per call and never cached, so assumed credentials never need refreshing' is corrected or explicitly defended, and decisions/outbound-clients.md records the outcome if it changes the contract
- [ ] #6 The chosen mechanism does not reintroduce AssumeRole at import or boot time in a way that conflicts with TASK-92 AC#1; the conflict check is recorded in notes
<!-- AC:END -->
