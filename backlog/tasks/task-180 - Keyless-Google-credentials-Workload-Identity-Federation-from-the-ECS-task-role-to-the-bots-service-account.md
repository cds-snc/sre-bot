---
id: TASK-180
title: >-
  Keyless Google credentials: Workload Identity Federation from the ECS task
  role to the bot's service account
status: In Progress
assignee: []
created_date: '2026-11-05T00:09:00Z'
updated_date: '2026-11-09T19:59:00Z'
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
- [x] #1 With GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_EMAIL and GOOGLE_WORKSPACE__TENANT__FEDERATION_AUDIENCE set, every Google factory authenticates through STS and service-account impersonation from the ECS task role and reads no key; tests drive the chain with a fake supplier and no network I/O
- [x] #2 The AWS supplier reads the botocore session's refreshable credentials on each call, so rotated task-role credentials are picked up, and the region from the session
- [x] #3 Source selection: an audience means AWS federation and wins over a key (both coexist until TASK-182); else a key means the key, and a set SERVICE_ACCOUNT_EMAIL must equal the key's client_email; else the email alone means application default credentials impersonating it, resolved on first use; a customer id with none of them, an audience without the email, or an audience of the wrong shape (a placeholder included) fails boot naming the variable; boot makes no network call
- [x] #4 Delegating factories on the federated and application-default paths delegate through signJwt (impersonated credentials with a subject); the key path keeps with_subject; all request exactly the scopes requested today; impersonated credentials are cached per subject and scope set and refresh themselves
- [x] #5 This PR changes no terraform and deploys on the key with both new names absent. After it deploys: a terraform-only PR (no task, as #1792) declares GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_EMAIL in terraform/ssm.tf, the human sets its value before any deploy and redeploys the running tag; deploy-checks pre at this merge, and post google after the redeploy, pass with every task on the key and the email set (boot checks it is the key's account). The audience parameter is TASK-180.1; the Codespaces secret is TASK-185
- [ ] #6 A Codespace or devcontainer authenticates with gcloud application-default login plus Token Creator, granted per developer and revocable; the devcontainer installs the gcloud CLI; the Codespaces key secret is no longer needed (deleted by TASK-182; the development account is TASK-185)
- [x] #7 ruff, mypy, lint-imports, make check-import-contracts, make check-settings-key-ownership and pytest tests --ignore=tests/smoke pass
- [x] #8 A google task check in bin/deploy-checks.zsh (post only; per task credential source from the configuration summary and error counts, never message bodies; google:federation requires federation on every task) passes on the key after this PR deploys; TASK-180.1 runs it after the cutover; TASK-183 deletes it when Done
- [x] #9 Documentation a new developer can follow: the Google README and the runbook carry a credentials-at-a-glance table (ECS, Codespace or devcontainer, another platform through a credential configuration file, the key until TASK-182), the selection order and troubleshooting rows per source; the root README's local setup links to them; the runbook's 'Until TASK-180 ships' section names only what TASK-180.1, 181 and 183 still change
- [x] #10 Portability: the application-default path accepts a Workload Identity Federation credential configuration file (file-sourced token, no key) through GOOGLE_APPLICATION_CREDENTIALS, proven by a test with no network; decisions/service-accounts.md rule 5 names the AWS supplier as the ECS adapter and application default credentials as the platform default
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## Summary

Add the keyless path to the same service account (same OAuth client id), with production still on the key when this PR deploys. The tenant entry chooses its credential source at boot without a network call:

- **AWS federation (the ECS adapter).** STS federation from the task role `sre-bot-ecs-role` (also the execution role), then impersonation of the service account. Delegation goes through signJwt.
- **Application default credentials (the platform default).** A developer's gcloud login, a GCP runtime, or a Workload Identity Federation credential configuration file for another platform (Azure, Kubernetes, OpenShift), then the same impersonation.
- **The key**, tolerated until TASK-182.

Sequence, following the #1792 / TASK-111.10.1 precedent (a parameter has its value before anything reads it):

1. **Expand PR (no task, terraform only):** `GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_EMAIL` in terraform/ssm.tf. A terraform-only path does not deploy. The human sets the value with put-parameter and sets the Codespaces secret.
2. **This PR (TASK-180):** the code, the check, the devcontainer CLI and the documentation. Its deploy runs on the key, and the email is verified against the key's client_email at boot.
3. **TASK-180.1 (cutover, terraform only):** the GCP steps, then the audience parameter, put-parameter and a redeploy of the same tag. Rollback is a revert plus a redeploy until TASK-182.

Size gate: passes. About 250 production LOC in 7 code files (integrations/google_workspace settings, client and a new credentials module; bin/deploy-checks.zsh; .devcontainer; pyproject CI blanks; generated .env.example), plus documentation. No mechanical refactor is mixed in; one subsystem changes behaviour.

Domain-model gate: not applicable. The tenant entry is a settings model at the configuration boundary, not a stored or shared domain entity, and no port or record changes. TASK-145.6 ports stay credential-blind (TASK-169 D6, TASK-145.6 AC #7).

## Steps

1. **integrations/google_workspace/settings.py**: the tenant entry.
   - New fields `service_account_email: str | None` (non-public; codespaces tag) and `federation_audience: str | None` (codespaces tag absent: no Codespace federates). The audience is shape-checked locally: `//iam.googleapis.com/projects/<digits>/locations/global/workloadIdentityPools/<id>/providers/<id>`, so the terraform placeholder fails boot naming the variable.
   - `service_account_key` becomes optional; `_TENANT_FIELDS` gains both new fields.
   - Before-validator, with CUSTOMER_ID set:
     - an audience requires the email: `aws_federation`;
     - else a key: `key`. A set email must equal the key's client_email, or boot fails naming both variables;
     - else the email alone: `application_default`;
     - else boot fails naming the three ways to configure the entry.
   - The audience wins over the key, so TASK-180.1 adds it while the key stays. A key beside an audience is not parsed.
   - A value set without CUSTOMER_ID still fails as today; no tenant entry still boots Google unconfigured (the bot runs standalone).
   - Exposes `credential_source: Literal["aws_federation", "key", "application_default"]` and docstrings.

2. **integrations/google_workspace/credentials.py** (new, about 150 LOC). build_service_account_credentials moves here from settings.py.
   - `BotocoreCredentialsSupplier(google.auth.aws.AwsSecurityCredentialsSupplier)`:
     - holds a `botocore.session.Session` built at boot (no network);
     - on each call returns the cached RefreshableCredentials' `get_frozen_credentials()`, and `session.get_config_variable("region")`;
     - a missing region fails boot, read from the environment;
     - botocore errors are re-raised as `RefreshError` without their message, so `_TokenCheckedHttp` maps them to GoogleCredentialsRefused.
   - `GoogleCredentialSource` Protocol (`for_call(scopes, subject) -> Credentials`), three implementations:
     - **Key:** `with_subject` then `with_scopes`, as today.
     - **AWS federation:** `aws.Credentials(audience, subject_token_type="urn:ietf:params:aws:token-type:aws4_request", aws_security_credentials_supplier=..., scopes=[cloud-platform])` built once. Each call is wrapped in `impersonated_credentials.Credentials(source_credentials=base, target_principal=email, target_scopes=scopes, subject=subject or None, lifetime=3600)`. With a subject, google-auth 2.62 signs through IAM signJwt and takes the JWT grant; without one, it uses generateAccessToken.
     - **Application default:** `google.auth.default(scopes=[cloud-platform])` resolved on the first call under a lock, then the same wrapper. It covers a gcloud user login, a GCP runtime and an external_account credential configuration file through `GOOGLE_APPLICATION_CREDENTIALS` (an SDK name, exempt from the naming rule).
   - Wrappers are cached by `(subject, frozenset(scopes))` under a lock: a bounded set fixed by the code. This follows outbound-clients.md rule 1 (credentials resolve on first call and refresh themselves) and avoids the per-build token cost tolerated in integrations/aws/client.py.
   - `@lru_cache get_google_credential_source()` is the integration-owned provider, as get_google_workspace_settings is.

3. **integrations/google_workspace/client.py** `_build_service` (:170-206): `get_google_credential_source().for_call(scopes, subject)` replaces `with_subject().with_scopes()`. The subject resolves as today (argument, else `tenant.delegated_user_email`) and the scopes are exactly the caller's (AC #4). No caller changes until TASK-181.

4. **bin/deploy-checks.zsh**: a `google` task check, post only.
   - Per log stream, the `google_workspace` configuration_slice event gives the tenant configured on every task and the credential source from which fields are set.
   - Counts, never message bodies: `google_token_refused` by cause, and lines matching `attribute condition`, `iam.serviceAccounts.getAccessToken` and `unauthorized_client` since the rollout.
   - `google` passes on any source; `google:federation` fails unless every task reports aws_federation.
   - The header names TASK-183 as its deleter.

5. **.devcontainer**: install the gcloud CLI (the Google apt repository, or a devcontainer feature pinned by digest, whichever the existing Dockerfile style uses). The ADC file lives in the home folder, so a rebuild means logging in again, and the documentation says so.

6. **pyproject.toml:151-153**: the two new names join the CI blanks. Regenerate app/.env.example (bin/generate_env_example.py).

7. **Documentation, written for a new developer:**
   - **Google README service identity:** a credentials-at-a-glance table:

     | Where | Source | What to set | Who grants |
     | --- | --- | --- | --- |
     | ECS | AWS federation | audience + email | — |
     | Codespace / devcontainer | gcloud login | email | Token Creator |
     | Another platform | credential file | `GOOGLE_APPLICATION_CREDENTIALS` + email | — |
     | Production until TASK-182 | key | key | — |

     Plus the selection order and the failure each half entry gives.
   - **Runbook:**
     - a "Run the bot locally" section: install check, `gcloud auth application-default login` (with the Codespace URL flow), the email secret, verifying with one directory call, what does not work locally (meetings), revocation;
     - troubleshooting rows per source;
     - 'Until TASK-180 ships' rewritten to name TASK-180.1, 181 and 183.
   - **Root README.md local setup (step 4):** link to the runbook section instead of "contact the SRE team".

8. **ADRs, edited this session:**
   - service-accounts.md rule 5: the AWS supplier is the ECS adapter; application default credentials are the platform default, including credential configuration files; developers use a development account (TASK-185); AWS outbound identity federation considered and not used; Migration names TASK-180.1 and TASK-185.
   - configuration.md: the selection order, the email-matches-key check, the audience shape check, and the expand-first rule for a new secret parameter.
   - cloud-portability.md: rule 1's workload identity names the credential configuration file as the portable seam.

## Human steps

- **Before this PR merges:**
  1. Merge the expand PR (one line in terraform/ssm.tf). tf_apply runs; no deploy runs.
  2. `aws ssm put-parameter --overwrite` for /sre-bot/GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_EMAIL.
  3. Set the Codespaces secret of the same name; `make env-checks` shows it set.
- **At merge:** `zsh bin/deploy-checks.zsh pre`.
- **After deploy:** `zsh bin/deploy-checks.zsh post google`: every task on the key, no error, and the email check passed (boot succeeded).
- **Developers:** AC #6 is verified once by the human with a temporary Token Creator grant on the production account, removed right after. Codespaces keep the key until TASK-185 gives them the development account; no developer holds a standing grant on the production account.

Blast radius: the expand PR changes nothing that runs. This PR's deploy runs the key path through the new credential module, so a defect there affects every Google call. The circuit breaker covers boot failures, and a call-time regression is reverted with one `git revert` plus the normal deploy. The audience is absent, so federation code is not exercised in production until TASK-180.1.

## AC traceability

| AC | Steps | Tests |
| --- | --- | --- |
| #1 | 2, 3 | credentials_aws_federation_build; client test on the federated source (fake supplier, no network) |
| #2 | 2 | credentials_aws_supplier |
| #3 | 1, 2 | settings_tenant_validate matrix; lifespan boot test with outbound sockets blocked |
| #4 | 2, 3 | credentials_impersonation_delegate; credentials_cache; existing client tests keep the key path |
| #5 | human, expand PR | deploy-checks pre/post output (human runs, agent reads) |
| #6 | 2, 5, 7 | credentials_application_default_lazy; devcontainer builds with `gcloud --version` |
| #7 | all | gates at the end |
| #8 | 4 | deploy-checks post google output after deploy |
| #9 | 7 | review against the table; a new developer's read |
| #10 | 2, 8 | credentials_application_default_credential_file (external_account JSON with a file-sourced token, STS and IAM transports faked) |

## Test matrix (app/tests/unit/integrations/google_workspace/)

- **test_google_workspace_settings_tenant_validate.py** (extend):
  - audience + email gives aws_federation; key gives key; email alone gives application_default; audience + key gives aws_federation and the key is not parsed;
  - an audience without the email fails naming SERVICE_ACCOUNT_EMAIL;
  - an audience at the placeholder or malformed fails naming FEDERATION_AUDIENCE;
  - a key with a mismatched email fails naming both;
  - a customer id alone fails naming the three options;
  - no entry boots unconfigured.
- **test_google_workspace_credentials_aws_supplier.py:** fake botocore credentials rotate between calls and the second call returns the new keys; the region comes from the session; a missing region fails at construction; a botocore error becomes a RefreshError without its message.
- **test_google_workspace_credentials_aws_federation_build.py:** aws.Credentials carries the audience and the supplier; the impersonated target is the email with the caller's scopes; no network at construction (transport patched to raise).
- **test_google_workspace_credentials_impersonation_delegate.py:**
  - with a subject, refresh calls signJwt and then the token endpoint (faked transport);
  - without one, generateAccessToken;
  - a refused grant surfaces as GoogleCredentialsRefused through the client.
- **test_google_workspace_credentials_cache.py:** the same (subject, scopes) returns one object; different scopes return a new one.
- **test_google_workspace_credentials_application_default_lazy.py:** google.auth.default is not called at construction and is called once across concurrent first calls.
- **test_google_workspace_credentials_application_default_credential_file.py:** an external_account file with a file-sourced token, through GOOGLE_APPLICATION_CREDENTIALS (tmp_path, monkeypatch), yields impersonated credentials for the email; STS and IAM are faked. This proves another platform needs no code.
- **tests/integration/server/test_lifespan_vendor_slice_validation.py** (extend): a federation entry boots configured with no outbound socket.

## Assumptions to verify during implementation

- google-auth 2.62 `impersonated_credentials.Credentials(subject=...)` works with a non-service-account source. The library's subject branch signs through IAM signJwt with the source token, independent of its type; a faked-transport test pins it.
- The AWS provider's default attribute mapping gives `attribute.aws_role` without the session name (Google WIF with other clouds). This is checked during TASK-180.1 with the runbook's troubleshooting row.
- Fargate sets AWS_REGION / AWS_DEFAULT_REGION. Checked in TASK-180.1; a missing region fails boot and the circuit breaker keeps the previous revision.
- gcloud's remote login flow works in a Codespace. Checked while writing the runbook section, with a fresh Codespace.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-05 implementation (TDD; branch task-180-keyless-google-credentials from main).

Done:
- integrations/google_workspace/settings.py: tenant entry gains service_account_email (non-public, codespaces) and federation_audience (non-public, local); service_account_key optional. Source chosen at boot in order: audience (shape-checked: project number, pool and provider ids of 4-32 [a-z0-9-]; AWS region required from botocore's config, no network), key (email must be the key's client_email), email alone (ADC). Exposes authentication, credentials (key path), aws_region.
- integrations/google_workspace/client.py: credential_source(tenant) (lru_cache) builds KeyCredentialSource, or ImpersonatingCredentialSource over aws.Credentials with BotocoreCredentialsSupplier, or over google.auth.default (lazy, locked). Impersonated credentials are cached per (subject, scopes); a subject delegates through signJwt. DefaultCredentialsError maps to GoogleCredentialsRefused(application_default_credentials_unavailable). _token_error_code reads IAM's status and STS's "Error code" prefix.
- bin/deploy-checks.zsh: google and google:federation checks (post only), reading set and partial field names of the google_workspace configuration_slice, plus google_token_refused counts by cause.
- .devcontainer/Dockerfile: Google Cloud CLI from Google's apt repo (verified in debian:bookworm-slim: SDK 592.0.0; --no-launch-browser exists).
- pyproject CI blanks and .env.example regenerated; docs: Google README (credentials at a glance, selection order, causes), runbook (provider id aws-ecs: Google requires 4-32 characters, so the former `aws` was invalid; section 8a Run the bot locally; boot and cause troubleshooting tables; transition section), root README step 5.
- ADRs: configuration.md (parameter ordering corrected, see below), outbound-clients.md Changes, service-accounts.md and cloud-portability.md from planning.

Deviations from the plan:
- No credentials.py: the vendor-package contract (bin/check_vendor_package_contract.py, outbound-clients.md) allows only __init__, client and settings modules, and construction belongs in client.py. Settings validates only.
- AC #5 order reversed: the tenant entry rejects unknown variables (extra=forbid; verified), so the email parameter must follow this PR, not precede it.
- google.auth.default resolves a credential file's project once on the first call (one STS exchange plus a Cloud Resource Manager read): library behaviour, not boot.

Observation (not changed, for the human): google-auth 2.62 starts a background regional-access-boundary lookup after a token refresh, on every credential type in googleapis.com, using the request object of the call, i.e. the service's httplib2.Http, which is not thread-safe (outbound-clients.md). It already runs on the key path in production. Tests switch it off (conftest no_regional_access_boundary_lookup). Worth a follow-up task: pass a dedicated transport for refresh, or confirm the lookup is harmless.

Gates: ruff All checks passed; make check-import-contracts 13 kept 0 broken; make check-settings-key-ownership OK; check-vendor-package-contract, check-runtime-imports, check-sdk-typing OK; mypy Found 41 errors in 14 files (all pre-existing, none in touched files); pytest tests --ignore=tests/smoke 6294 passed.

Open ACs: #5 (terraform-only PR, value, redeploy, deploy-checks), #6 (a human logs in from a Codespace with a temporary grant), #8 (post google after deploy).

2026-11-05: #1828 merged 23:43 UTC (e85a30c5), deployed as sre-bot-task:88. deploy-checks post google at 23:48:14Z (tmp/deploy-checks/post-google-20261105T234814Z.txt): google_configured PASS and google_no_refusal PASS, both tasks source=key with service_account_email unset; version PASS (e85a30c5); boot_errors, runtime_errors and slack_up PASS. rollout showed IN_PROGRESS because the check ran 1.5 minutes into the rollout (deploy job still running), so it gets a rerun. The 4 non-JSON lines (debug built_conditional_write_store, the starlette import warning) are not from this change. AC #8 checked; AC #5 waits on the email parameter PR.

2026-11-06: regional-access-boundary observation resolved, no task. google-auth 2.62 deep-copies the request before the background lookup (_regional_access_boundary_utils.py start_refresh) and skips the lookup when the copy fails. Checked: copy.deepcopy(google_auth_httplib2.Request(httplib2.Http())) returns a new Http with no connections, before and after use. The lookup never shares the service's Http, so outbound-clients.md's thread rule holds.

2026-11-09: AC #5 evidence. #1829 merged 2026-11-06 00:57 UTC (0aa97520; tf_apply success), the human set SERVICE_ACCOUNT_EMAIL from the key's client_email, and build_and_deploy deployed af75dffe (run created 17:51:32Z, success) as sre-bot-task:99. deploy-checks post google at 2026-11-09T17:56:15Z (tmp/deploy-checks/post-google-20261109T175615Z.txt): rollout PASS (COMPLETED, 2/2), boot_errors, runtime_errors and slack_up PASS; both tasks source=key with service_account_email=set, so the boot check accepted the email as the key's account; google_configured PASS, google_no_refusal PASS. version CHECK: af75dffe was running while the 3075170b run was in progress (that run completed with success after the check). The 4 non-JSON lines (debug built_conditional_write_store, the starlette import warning) are the known ones. The pre at this PR's merge is pre-20261105T233149Z (#1828). AC #5 checked. AC #6 waits on TASK-185. The chain stays PARKED (human, 2026-11-06) until doc-15's coordinated-incidents enhancements; TASK-180.1's wait on AC #5 is met.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-05T21:17:00Z

---

2026-11-05 (human approved the program-scope reassessment): ACs reworded. #3 adds precedence, the email check and lazy ADC. #5 follows the #1792 expand precedent, and the audience parameter, GCP steps and runbook walk-through move to TASK-180.1. #6 adds the gcloud CLI. #8 is the check only. #9 is documentation for a new developer. #10 is new (portability). TASK-185 created for the development identity.

---

created: 2026-11-05T21:46:00Z

---

2026-11-05 (implementation): AC #5 reordered. The tenant entry rejects unknown variables (extra=forbid), so an email parameter created before this code ships would fail every deploy of today's main. This PR ships first with both names optional; the terraform-only PR and the value follow before the next deploy. decisions/configuration.md and the runbook say so.

---
<!-- COMMENTS:END -->
