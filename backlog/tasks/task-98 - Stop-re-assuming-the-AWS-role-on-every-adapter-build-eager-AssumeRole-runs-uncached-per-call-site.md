---
id: TASK-98
title: >-
  Make AWS assumed-role credentials lazy and refreshable: no STS call when a
  client is built, one per credential lifetime
status: To Do
assignee: []
created_date: '2026-09-17 19:06'
updated_date: '2026-09-25 15:53'
labels:
  - clients
  - architecture
dependencies:
  - TASK-92
references:
  - decisions/outbound-clients.md
  - decisions/lifecycle.md
priority: high
ordinal: 226000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/outbound-clients.md and lifecycle.md (2026-09-25): a factory does no network I/O at construction, and the only vendor call before yield is a declared, classified credential check. Assumed-role credentials resolve on the first API call and refresh themselves before they expire.

TODAY. integrations/aws/client.py get_aws_client calls sts.assume_role while it builds a client whenever role_arn is set (_session_for). client.py's module docstring gives the reason: 'Clients are built per call and never cached, so assumed credentials never need refreshing.' That has two effects:
1. BOOT CRASH (live in development, possibly in production). packages/access/sync's startup_warmup builds the Identity Center adapter, which assumes AWS_ORG_ACCOUNT_ROLE_ARN through STS. With ACCESS_SYNC_ENABLED=true, a non-empty role ARN and no valid ambient credentials, boot aborts with ClientError InvalidClientTokenId, so one business feature the SRE Bot does not require takes the whole app down. Reproduced on main @ 27fb2bda (2026-09-17). app/pyproject.toml pins ACCESS_SYNC_ENABLED=false for tests to work around it.
2. PER-CALL COST. No build_*_adapter() is cached, so every build pays an STS round-trip, and builders that make a retrying and a retries-disabled client pay two (identity_center.py, dynamodb.py). modules/aws/ops_group_assignment.py makes four AssumeRole calls per invocation; jobs/scheduled_tasks.py's 5-minute integration_healthchecks makes two. AssumeRole is account-throttled.

TARGET. The factory builds a boto3 Session whose credentials are botocore DeferredRefreshableCredentials fed by an AssumeRoleCredentialFetcher (botocore 1.42 ships both): no STS call until the first API call, then refresh before expiry, handled by botocore. Sessions are reused per (role_arn, session_name) so repeated builds share one credential lifetime, created in a thread-safe way, since boto3 Sessions are not thread-safe to share for creation. The retrying and retries-disabled clients share the session. Affected services are those in SERVICE_ROLE_MAP with a non-empty ARN; dynamodb has no entry and is unaffected.

BOOT BEHAVIOUR. Today a misconfigured credential aborts boot as a side effect of construction. After this change it must not abort (decisions/lifecycle.md: credential checks alert, they never abort), but it must still be reported at boot: access/sync's startup_warmup runs one explicit credential check, identitystore ListUsers with MaxResults=1 through the adapter (one attempt, bounded timeout). UNAUTHORIZED, PERMANENT_ERROR or NOT_FOUND logs ERROR credential_check_failed; TRANSIENT_ERROR logs WARNING credential_check_inconclusive. Boot completes either way and access sync stays registered. TASK-126 later moves this check onto the generic credential-check hookspec.

OUT OF SCOPE: off-AWS credential acquisition (TASK-89), the fate of integration_healthchecks (TASK-127).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Building any role-bearing AWS client opens no outbound connection (socket.connect spy test); the first API call performs the AssumeRole
- [ ] #2 Repeated builds for the same (role_arn, session_name) make at most one AssumeRole call per credential lifetime, and the two-client builders do not double it (test counting STS calls with botocore Stubber or a fake fetcher)
- [ ] #3 Credentials are never shared across different role_arn or session_name values, and expiry triggers a refresh (tests)
- [ ] #4 The client.py module docstring states the deferred, refreshable credential design; decisions/outbound-clients.md Migration drops the eager AssumeRole tolerance and lifecycle.md drops access sync's boot-time AssumeRole
- [ ] #5 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
- [ ] #6 Access sync enabled with invalid credentials or an unassumable role completes boot and logs ERROR credential_check_failed; a TRANSIENT_ERROR result (Stubber throttling or timeout) logs WARNING credential_check_inconclusive; a later sync call after the credential is fixed succeeds without a restart (tests); the app/pyproject.toml ACCESS_SYNC_ENABLED=false test pin comment no longer cites construction-time AssumeRole
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-24 20:11
---
2026-09-24 alignment with decisions/dependency-injection.md: construction moves to the svcs service registry (TASK-109). The service's lifetime (a value or factory closing over one instance) is the host's registration choice, not an lru_cache on a provider function. Whether AssumeRole runs eagerly at boot is decided in TASK-92.
---
<!-- COMMENTS:END -->
