---
id: TASK-25.2.2
title: >-
  Rationalize integrations/aws/client.py: typed Literal-overloaded factory,
  eager AssumeRole, SDK-native retry and timeout policy, settings consolidated
  in integrations/aws/settings.py
status: To Do
assignee: []
created_date: '2026-07-31 18:48'
updated_date: '2026-09-11 15:56'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.1
references:
  - app/integrations/aws/client.py
  - app/integrations/aws/settings.py
  - app/infrastructure/configuration/integrations/aws.py
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/infrastructure/storage/service.py
  - app/infrastructure/idempotency/factory.py
  - app/infrastructure/resilience/retry/factory.py
  - app/integrations/google_workspace/client.py
parent_task_id: TASK-25.2
priority: high
ordinal: 119000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 1 of TASK-25.2. Rework get_aws_client into the single AWS client factory the rest of the series builds on, without yet touching the legacy helpers: handle_aws_api_errors, execute_aws_api_call, paginator, assume_role_session and get_aws_service_client stay as they are until TASK-25.2.6 so the mirror modules keep working through the intermediate slices.

Target shape: get_aws_client(service, *, role_arn=None, session_name=..., retries=True) overloaded on Literal service names (dynamodb, identitystore, organizations, sso-admin, ce, config, guardduty, securityhub, lambda, sts) so each call returns the matching types-boto3 client type and call sites need no cast; the session_config/client_config dict kwargs are removed. AssumeRole is done eagerly through the public API (sts.assume_role, then boto3.Session from the returned credentials) instead of writing DeferredRefreshableCredentials into botocore's private _session._credentials; clients are built per operation and never cached, so no credential refresh is needed. Retries use Config(retries={"mode": "standard", "max_attempts": N}) with explicit connect/read timeouts (decisions/outbound-clients.md items 20-23), plus a retries-disabled variant for non-idempotent writes (item 25) that later slices use wherever a replay is unsafe. The dynamodb-local endpoint gate stays, once (botocore's native AWS_ENDPOINT_URL_DYNAMODB variable is the SDK-native replacement if the local/ci environment files can set it; evaluate at planning, do not assume).

Settings (human decision 2026-09-11): integrations/aws/settings.py, colocated with client.py, becomes the single source of every AWS setting for this series. It already defines the transport fields (AWS_REGION, AWS_ENDPOINT_URL, RETRY_MODE, RETRY_MAX_ATTEMPTS, CONNECT/READ timeouts, NOT_FOUND/UNAUTHORIZED/TRANSIENT code catalogues) that client.py today tries to read through getattr defaults from infrastructure/configuration/integrations/aws.py, where they do not exist; wire get_aws_client and classify_aws_error to it. Add to it, with identical field names and env aliases, the feature-level fields the mirrors and the later adapters need (SYSTEM_ADMIN_PERMISSIONS, VIEW_ONLY_PERMISSIONS, AUDIT/ORG/LOGGING_ROLE_ARN, INSTANCE_ID, INSTANCE_ARN, SERVICE_ROLE_MAP) so TASK-25.2.3 onwards read only this module. Mirror modules keep importing the infrastructure module until they are deleted; the infrastructure module and its barrel export are retired in TASK-25.2.6. Do not add AWS fields to infrastructure/configuration (the export barrel there is why they are being moved out).

Callers updated: infrastructure/storage/service.py, infrastructure/idempotency/factory.py and infrastructure/resilience/retry/factory.py drop their casts. packages/access/sync/adapters/aws_identity_center.py keeps working as is (its get_aws_client("identitystore", role_arn=...) call stays valid); dropping its now-redundant cast is a fine incidental edit, but nothing beyond that: the access feature is not enabled yet and its own migration is out of this series' scope.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 get_aws_client is overloaded on Literal service names and returns the types-boto3 client type for each; mypy passes with the casts removed from the storage, idempotency and retry-store callers; packages/access needs at most its redundant cast removed
- [ ] #2 AssumeRole uses sts.assume_role and a public boto3.Session constructor; no private botocore attribute is accessed anywhere under app/integrations
- [ ] #3 Retry mode, max attempts, connect and read timeouts, region and endpoint are read from integrations/aws/settings.py and set once at construction, a retries-disabled option exists, and unit tests assert the botocore Config the factory produces for both variants and that environment overrides take effect
- [ ] #4 classify_aws_error reads its code catalogues from integrations/aws/settings.py and its tests cover each mapped family (not-found, unauthorized, transient with retry_after, ConditionalCheckFailedException permanent, BotoCoreError transient) plus one unmapped ClientError propagating
- [ ] #5 integrations/aws/settings.py carries the feature-level fields (permission sets, role ARNs, SSO instance id/ARN, SERVICE_ROLE_MAP) with the same names and env aliases as the infrastructure module, covered by tests; infrastructure/configuration gains no AWS field
- [ ] #6 The legacy helpers remain callable and every existing mirror-module test still passes
<!-- AC:END -->
