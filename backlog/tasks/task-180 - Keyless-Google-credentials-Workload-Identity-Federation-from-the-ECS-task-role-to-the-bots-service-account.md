---
id: TASK-180
title: >-
  Keyless Google credentials: Workload Identity Federation from the ECS task
  role to the bot's service account
status: To Do
assignee: []
created_date: '2026-11-05T00:09:00Z'
updated_date: '2026-11-05T00:13:00Z'
labels:
  - security
  - configuration
milestone: m-7
dependencies: []
references:
  - decisions/service-accounts.md
  - app/integrations/google_workspace/README.md
  - >-
    https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-other-clouds
priority: high
type: feature
ordinal: 477000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the TASK-169 ruling (2026-11-05, human; decisions/service-accounts.md rule 5). Today the Google gateway signs every call with a JSON service-account key stored in SSM (GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY): a private key that never expires and, through domain-wide delegation, lets whoever holds it act as any user of the domain within the granted scopes. Google: "Using service account keys is not necessary to perform domain-wide delegation. Use the signJwt API instead" (https://knowledge.workspace.google.com/admin/apps/domain-wide-delegation-best-practices). decisions/cloud-portability.md rule 1 prefers ambient workload identity inside integrations/.

This task adds the keyless path to the SAME service account (same OAuth client id), so the delegation entry, the SRE shared-drive membership and the Drive appProperties the bot wrote are unchanged; only the proof of identity changes.

Scope (integrations/google_workspace/ only, plus terraform/ssm.tf and the task definition):
- A boto3-backed google.auth.aws.AwsSecurityCredentialsSupplier: the ECS container credentials endpoint is not read by google-auth's built-in AWS source (IMDS and environment only; Fargate has no instance profile), so the supplier returns the botocore session's current frozen credentials and region (Google sample: https://docs.cloud.google.com/iam/docs/authenticate-with-auth-libraries; google-auth >= 2.29).
- aws.Credentials with the federation audience, then google.auth.impersonated_credentials.Credentials targeting the service account (with subject for the delegating factories: keyless domain-wide delegation through signJwt; google-auth >= 2.56.1, locked 2.62.0).
- Credential source chosen by the tenant entry: federation audience set -> AWS federation; key set -> key (tolerated until the key-retirement task); neither -> application default credentials (a developer's gcloud login or a GCP runtime, as an adopter on GCP would run) impersonating the service account.
- Tenant entry gains GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_EMAIL (non-public: an account holding domain privileges) and GOOGLE_WORKSPACE__TENANT__FEDERATION_AUDIENCE, from the environment like the rest of the Google tenant entry (configuration.md).
- No network I/O at construction (outbound-clients.md): tokens resolve on the first call and refresh themselves.

Human GCP steps (in cdssnc, from the README service identity section): enable iam, iamcredentials, sts; create the workload identity pool and AWS provider, condition pinned to the AWS account and the ECS task role; grant roles/iam.workloadIdentityUser and roles/iam.serviceAccountTokenCreator on the service account to that role's principalSet only. Cutover is setting the two parameters; rollback is unsetting them (the key path still works).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 With the federation audience and service-account email set, every Google factory authenticates through STS and service-account impersonation from the ECS task role and reads no key; tests drive the chain with a fake supplier and no network I/O
- [ ] #2 The AWS supplier reads the botocore session's refreshable credentials on each call, so rotated task-role credentials are picked up, and the region from the session
- [ ] #3 Source selection: audience set means federation, key set means key, neither means application default credentials impersonating the service account; a half entry fails boot naming the missing variable; boot makes no network call
- [ ] #4 Delegating factories on the federated path delegate through signJwt (impersonated credentials with a subject); the key path keeps with_subject; both request exactly the scopes requested today
- [ ] #5 terraform/ssm.tf declares GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_EMAIL and GOOGLE_WORKSPACE__TENANT__FEDERATION_AUDIENCE (placeholder through value_wo) with their task-definition secrets: entries; deploy-checks pre and post pass
- [ ] #6 A Codespace authenticates with gcloud application-default login plus Token Creator on the service account, granted per developer and revocable; the README says so and the Codespaces key secret is no longer needed
- [ ] #7 ruff, mypy, lint-imports, make check-import-contracts, make check-settings-key-ownership and pytest tests --ignore=tests/smoke pass
- [ ] #8 The pool, AWS provider with its account-and-role condition and the two IAM grants exist in cdssnc as the README describes; a google task check is added to bin/deploy-checks.zsh (post: Google configured on every running task, no Google credential or delegation error line since the rollout) and passes after the parameters are set; TASK-183 deletes the check when it is Done
- [ ] #9 docs/runbooks/set-up-google-workspace-access.md is walked end to end while setting up CDS's federation and corrected where it is wrong; its 'Until TASK-180 ships' section names only what TASK-181 and 183 still change
<!-- AC:END -->
