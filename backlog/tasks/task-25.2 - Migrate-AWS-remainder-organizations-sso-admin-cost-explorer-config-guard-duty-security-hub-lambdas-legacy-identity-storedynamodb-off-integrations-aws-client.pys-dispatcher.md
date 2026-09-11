---
id: TASK-25.2
title: >-
  Retire integrations/aws to client.py: typed factory, SDK-native
  retry/pagination/AssumeRole, adapters own classification
status: To Do
assignee: []
created_date: '2026-07-31 18:48'
updated_date: '2026-09-11 19:54'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-22.2
  - TASK-22.3
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - decisions/feature-packages.md
  - decisions/capability-packages.md
  - decisions/workplace-systems.md
  - decisions/layers.md
  - app/integrations/aws/client.py
  - app/integrations/google_workspace/client.py
parent_task_id: TASK-25
priority: high
ordinal: 117000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Coordinator for the AWS slice of TASK-25, re-scoped 2026-09-11 (human-directed) after TASK-25.1 showed that the Google migration needed a second, larger series once the per-method mirror modules were treated as the destination. This series reaches the AWS endstate in one pass, fixing the vendor client and its seams rather than the business features that call it.

ENDSTATE. app/integrations/aws/ ends as __init__.py, client.py and settings.py, and nothing else (the three modules the vendor-package guard allows). client.py exports get_aws_client, overloaded on Literal service names so each call returns the types-boto3 typed client without a cast, configured once with SDK-native standard retries, connect/read timeouts, an explicit retries-disabled option for non-idempotent writes, eager AssumeRole through the public sts.assume_role API, and the single dynamodb-local endpoint gate; and classify_aws_error(exc) -> (OperationStatus, error_code, retry_after). No dispatcher, no decorator, no hand-rolled paginator, no per-service mirror module.

SETTINGS (human decision 2026-09-11). integrations/aws/settings.py, colocated with client.py, is the home of every AWS setting until the business features reach their final packages and define their own settings.py (TASK-88). It already holds the transport fields (region, endpoint, retry mode/attempts, timeouts, error-code catalogues) that the factory today fails to read; the feature-level fields still in infrastructure/configuration/integrations/aws.py (SSO permission sets, AUDIT/ORG/LOGGING role ARNs, SSO instance id/ARN, SERVICE_ROLE_MAP) move into it, and the infrastructure module plus its export in infrastructure/configuration/integrations/__init__.py are retired: that barrel is the reason AWS settings were being moved out of infrastructure/configuration, so reading from or growing it would be a regression. The AWS client needs no credentials of its own because the app runs inside an AWS account on the ambient credential chain, unlike the Google client, which carries a service-account key; a separate spike (TASK-89) assesses hosting outside AWS.

WHERE THE CALLS GO. Every legacy AWS call site (modules/aws/*, modules/provisioning/{users,groups}.py, modules/slack/webhooks.py, modules/incident/{db_operations,incident_folder}.py, jobs/{revoke_aws_sso_access,scheduled_tasks}.py) moves onto an adapter that holds the typed client, calls the SDK directly (pagination via client.get_paginator), does try/except + classify_aws_error and returns OperationResult; callers branch on the result instead of on the silent False that handle_aws_api_errors returns today. Adapters live under a PROVISIONAL packages/aws_platform/adapters/<service>.py (one per AWS service: identity_center, organizations, sso_admin, config, cost_explorer, guard_duty, security_hub, lambda, dynamodb). packages/aws_platform is a transition seam, not a feature or capability package: modules/aws was a vendor-named mix of business features (access requests, account health, spending, Lambda inventory, Identity Center administration) and the feature split is deferred to TASK-88, which migrates those modules to feature packages per decisions/feature-packages.md and dissolves packages/aws_platform. Do not add business logic to packages/aws_platform beyond what an in-flight caller already needs.

TIER RULES (so the Google-series pattern of vendor-neutral infrastructure services for workplace concerns is not repeated). Nothing in this series creates an app/infrastructure/<service>/ Protocol. Eventual homes, owned by TASK-88: Identity Center holds people's accounts, so a shared Identity Center adapter belongs in a capability package (decisions/capability-packages.md, decisions/people-and-accounts.md), never in infrastructure/; Organizations, SSO-Admin, Config, Cost Explorer, GuardDuty, Security Hub and Lambda are Path B feature adapters (decisions/layers.md) and stay inside the feature that acts on AWS; DynamoDB is a hosting service whose home is the existing infrastructure/storage capability, so the thin DynamoDB adapter here is a seam and its callers move onto the storage Protocol later (TASK-88 with TASK-27).

SCOPE NOTE ON packages/access. The access feature is not enabled yet and still in development, so migrating or improving it is not a priority in this series and no shims or workarounds are built for it; it keeps working because get_aws_client("identitystore", role_arn=...) and classify_aws_error keep their call shapes. Small direct edits that fall out of this work are fine (dropping a redundant cast, repointing its settings import); its own migration and improvements come later, with the feature. infrastructure/storage, idempotency and retry-store keep their existing compliant use of the factory (only casts are removed). DynamoDBStorageService is not adopted by legacy callers in this series.

ERROR CONTRACT (human-decided 2026-09-11). Adapters return OperationResult at every boundary; callers handle status explicitly. This is a behaviour change from the False-swallow: each subtask documents the resulting error-path behaviour per call site for review, and TASK-25.2.1 locks the current behaviour in tests first so the change is visible in diffs.

TESTS. Adapters are unit-tested with botocore.stub.Stubber (SDK-native request validation against the service model) plus classification tests per mapped error family. Existing moto suites (DynamoDB storage, identitystore conformance) are retargeted or kept; no new moto conformance ACs.

SEQUENCING. 25.2.1 characterization gate -> 25.2.2 client.py + settings consolidation -> 25.2.3 Identity Center -> 25.2.4 Organizations/SSO-Admin/account-health/Lambda -> 25.2.5 DynamoDB -> 25.2.6 deletions (folds TASK-25.5). Each adapter subtask deletes the mirror modules and legacy tests it orphans, so 25.2.6 only removes client.py's legacy helpers, shield/sqs/schemas, the infrastructure settings module, and prunes the guard baselines. Prose consumer lists in every subtask are starting points: re-grep before planning (lesson recorded on TASK-25.1).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/integrations/aws/ contains only __init__.py, client.py (get_aws_client + classify_aws_error) and settings.py; bin/baselines/vendor_package_contract.txt and bin/baselines/sdk_typing_antipatterns.txt carry no integrations/aws entries; make client-usage-matrix and a repo-wide grep show zero callers of execute_aws_api_call, handle_aws_api_errors, paginator, assume_role_session and get_aws_service_client
- [ ] #2 Every legacy AWS call site listed in the description reaches AWS through a packages/aws_platform adapter that returns OperationResult, with per-call-site error-path behaviour documented and human-reviewed in the owning subtask
- [ ] #3 get_aws_client returns typed clients via Literal overloads with SDK-native retries, timeouts, eager AssumeRole and a retries-disabled option, reading every AWS setting from integrations/aws/settings.py; infrastructure/configuration/integrations/aws.py and its barrel export no longer exist; no boto3.client or boto3.Session construction exists outside client.py in production code
- [ ] #4 TASK-25 AC#3, AC#4 and AC#5 hold for AWS: classification tests per mapped family with one unmapped exception propagating, zero shield code hits under app/integrations, no hand-rolled retry in app/integrations
- [ ] #5 No new app/infrastructure/<service>/ package or Protocol is introduced by this series; TASK-88 records the eventual home of each adapter (capability package for Identity Center, feature adapters for the Path B services, infrastructure/storage for DynamoDB callers)
- [ ] #6 A follow-up top-level task (TASK-88) and a hosting-outside-AWS spike (TASK-89) exist
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-08-31 18:52
---
Forward reference from TASK-23.2 planning (2026-08-31): the DynamoDB idempotency store keeps a conservative error-swallow on one path - a classified (mapped) SDK failure while re-reading a contended claim is downgraded to ClaimResult.IN_PROGRESS rather than raised. That was deliberately left as-is for TASK-23.2 and is flagged for reassessment during this AWS-remainder work, alongside the same question for other classify-and-continue call sites.
---

created: 2026-09-11 19:48
---
2026-09-11 finding from TASK-25.2.3.1's full-suite run: since TASK-25.2.2 made AssumeRole eager, app startup (lifespan -> plugin manager -> packages/access/sync providers -> build_aws_identity_center_adapter -> get_aws_client('identitystore', role_arn=ORG_ROLE_ARN)) performs a real sts.assume_role whenever AWS_ORG_ACCOUNT_ROLE_ARN is set. In this devcontainer (role ARNs exported, compose dummy keys) that raises InvalidClientTokenId and errors 32 API/e2e tests that build the app through TestClient; .github/workflows/ci_code.yml:72 also injects AWS_ORG_ACCOUNT_ROLE_ARN from secrets, so CI may hit the same startup call. Not caused by and not fixed in 25.2.3.1. Candidate follow-up: make the access-sync adapter build lazily (at first sync) or stub STS in the app-startup test fixtures; the access feature is not enabled so a lazy build has no runtime cost.
---

created: 2026-09-11 19:54
---
2026-09-11 correction to the previous comment (human challenged the attribution): the AssumeRole at app startup is not a devcontainer-only artefact. pytest-env pins AWS_ORG_ACCOUNT_ROLE_ARN to a placeholder for every test run, and app/.env's ACCESS_SYNC_ENABLED=true is read by pydantic env_file during tests, so any developer with that .env line gets 32 startup errors in the api/e2e/app-state tests since TASK-25.2.2 made AssumeRole eager. CI does not enable access sync, so CI is unaffected. Root gaps are in test isolation, not in 25.2.2's design: (1) settings read the developer's real .env under pytest, so feature toggles leak into tests; (2) the app-startup fixtures stub the directory provider but not the AWS boundary, so a warmup can reach STS. Proposed tests-only fix: pin ACCESS_SYNC_ENABLED=false in pytest-env (tests that need the feature enable it explicitly) and add an autouse fixture in the startup-test conftests that patches integrations.aws.client._assume_role_credentials, plus optionally a no-network guard. Awaiting the human's decision on where to track it.
---
<!-- COMMENTS:END -->
