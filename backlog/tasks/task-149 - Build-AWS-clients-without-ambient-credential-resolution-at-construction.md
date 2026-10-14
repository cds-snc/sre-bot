---
id: TASK-149
title: Build AWS clients without ambient credential resolution at construction
status: To Do
assignee: []
created_date: '2026-10-14 18:57'
updated_date: '2026-10-14 19:23'
labels:
  - infrastructure
  - reliability
milestone: m-7
dependencies:
  - TASK-98
  - TASK-109
references:
  - decisions/outbound-clients.md
  - decisions/lifecycle.md
priority: medium
ordinal: 383000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-10-14 while planning TASK-109. decisions/outbound-clients.md says client construction never calls the network, and lifecycle.md phase 2 resolves core services at boot with construction and static validation only. Observed: with no static credentials in the environment, building a dynamodb client through boto3 (integrations/aws/client.py get_aws_client) opens a connection to the instance metadata endpoint (169.254.169.254:80) while the default credential chain resolves. TASK-98 makes assumed-role (STS) credentials deferred, but dynamodb has no SERVICE_ROLE_MAP entry, so this ambient-chain lookup is outside it.

Once TASK-109 resolves RecordStore and ConditionalWriteStore at boot, this lookup runs before yield. TASK-109's no-network boot test therefore sets static AWS credentials and AWS_EC2_METADATA_DISABLED=true, and tests/api does the same; production keeps the ambient lookup.

To establish first: on ECS (container credentials provider), whether client construction fetches credentials, and whether a fetch failure raises at construction. If it raises, a task-role problem aborts boot, which lifecycle.md forbids (state that changes without a deploy never aborts boot).

Target: client construction defers credential resolution to the first API call for the ambient chain too (for example deferred refreshable credentials on a shared session, in line with TASK-98's design), and the boot no-network test passes without static credentials.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Behaviour on ECS is recorded: whether client construction fetches container credentials and whether a failure raises at construction
- [ ] #2 Building an AWS client with only ambient credentials opens no network connection (socket.connect spy, no static credentials set)
- [ ] #3 A credential failure surfaces on the first API call, never at boot
- [ ] #4 TASK-109's boot test no longer needs static credentials or AWS_EC2_METADATA_DISABLED; tests/api's workaround is removed
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-14 19:23
---
2026-10-14 (agent, during TASK-109): measured with no credential files and no AWS_* keys: phase 2 building the two DynamoDB clients makes 2 connects to 169.254.169.254:80. Before TASK-109, six test files that boot the real lifespan made none; they now use the static_aws_credentials fixture (tests/conftest.py). tests/integration/jobs/test_scheduled_tasks_integration.py already made one such connect before TASK-109. ECS container-credential behaviour at construction was not verified (no ECS access in the session).
---
<!-- COMMENTS:END -->
