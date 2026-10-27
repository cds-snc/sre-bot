---
id: TASK-111.11.1
title: >-
  Move the AWS slice onto the files; AWS_REGION and AWS_ENDPOINT_URL_DYNAMODB
  are left to the SDK
status: In Progress
assignee: []
created_date: '2026-10-26T22:21:00Z'
updated_date: '2026-10-27T00:01:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.6.2
  - TASK-111.3
references:
  - decisions/configuration.md
parent_task_id: TASK-111.11
type: feature
ordinal: 449000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
AWSSettings (integrations/aws/settings.py) becomes the [aws] ConfigurationSlice (extra=forbid, no aliases): retry and timeout values, the error-code catalogues, the SSO permission set names, the per-account role ARNs and the SSO instance id and ARN move to the files (public values: decisions/configuration.md; the account ids are already published in terraform/iam.tf). AWS_REGION and AWS_ENDPOINT_URL_DYNAMODB stop being declared as fields: boto3 resolves the region (AWS_DEFAULT_REGION, which ECS sets, or the shared config file) and the dynamodb-local endpoint (AWS_ENDPOINT_URL_DYNAMODB, honored natively). The old AWS_* names are no longer read; production.toml, local.toml and ci.toml name the values. The blob lines stay inert until TASK-111.15. Split from TASK-111.11 on 2026-10-26.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 [aws] holds only the client tuning (retry, timeouts, error-code lists; base.toml defaults, per-environment overrides) and declares no AWS_* SDK name (AWS_REGION, AWS_ENDPOINT_URL_DYNAMODB) as a field; an unknown key in [aws] fails boot naming the key
- [x] #2 get_aws_client resolves the region and the dynamodb-local endpoint through the SDK alone (AWS_DEFAULT_REGION or the shared config file, AWS_ENDPOINT_URL_DYNAMODB); the dynamodb-only endpoint and the ca-central-1 default are gone from code
- [ ] #3 No configuration file names a value of the AWS tenant entry or [access_permission_sets]; the five production values (AWS__TENANT__INSTANCE_ID, AWS__TENANT__INSTANCE_ARN, AWS__TENANT__ORG_ROLE_ARN, ACCESS_PERMISSION_SETS__SYSTEM_ADMIN_PERMISSIONS, ACCESS_PERMISSION_SETS__VIEW_ONLY_PERMISSIONS) are SSM parameters that pre aws shows as MATCH against the blob lines they replace, with both instance formats OK; no file holds a credential
- [x] #4 The old names (AWS_SSO_SYSTEM_ADMIN_PERMISSIONS, AWS_SSO_VIEW_ONLY_PERMISSIONS, AWS_AUDIT_ACCOUNT_ROLE_ARN, AWS_ORG_ACCOUNT_ROLE_ARN, AWS_LOGGING_ACCOUNT_ROLE_ARN, AWS_SSO_INSTANCE_ID, AWS_SSO_INSTANCE_ARN, AWS_RETRY_MAX_ATTEMPTS, AWS_RETRY_MODE, AWS_CONNECT_TIMEOUT_SECONDS, AWS_READ_TIMEOUT_SECONDS, AWS_TRANSIENT_RETRY_AFTER_SECONDS, AWS_NOT_FOUND_CODES, AWS_UNAUTHORIZED_CODES, AWS_TRANSIENT_CODES) are no longer read from the environment or .env
- [x] #5 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass; make check-import-contracts and make check-settings-key-ownership pass
- [x] #6 The AWS organisation is the optional AWS tenant entry (AWS__TENANT__<FIELD>, environment only; instance_id and instance_arn required and checked against the documented AWS patterns; audit/org/logging role ARNs each optional, empty counting as unset); a malformed entry fails boot naming the key; ci.toml names no tenant and an absent tenant keeps today's behaviour (the bot's own credentials, empty instance values); [aws] holds only the client tuning
- [x] #7 The two SSO permission-set values are read by an access-owned slice in packages/access/common/settings.py ([access_permission_sets]), moved mechanically (no policy redesign); build_sso_admin_adapter takes them as parameters and integrations/aws no longer declares them
- [ ] #8 The tenant's role ARNs, instance id and ARN, and the two permission-set ARNs are non-public values supplied from the environment (SSM parameters in production, Codespaces secrets in development); production behaviour is identical (same ARNs, same instance); .devcontainer/docker-compose.yml sets AWS_DEFAULT_REGION
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Deployed; zsh bin/deploy-checks.zsh post aws PASS and the manual checks recorded
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLAN FOR TASK-111.11.1 (AWS slice onto the configuration files). Revised 2026-10-26 with the human's decisions. Split from TASK-111.11 (111.11.2 is OpenAI). Written against main dcf10406; modelled on 111.7 (extra=forbid, base + per-environment files) and 111.10.2 (tenant entry, helpers, pins). Re-run every rg below first.

== Decisions (human, 2026-10-26) ==
D1 AWS role ARNs and the SSO instance id/ARN are PUBLIC (AWS: account ids are not secret, https://docs.aws.amazon.com/general/latest/gr/acct-identifiers.html; terraform/iam.tf:19-21 already publishes three sre_bot_role ARNs). They go in production.toml now. A separate deployment repository for organisation configuration is a long-term goal recorded in the ADRs, not this task.
D2 Split per configuration.md 'vendor enablement is the presence of a tenant entry': [aws] = client tuning shared with hosting (DynamoDB); [aws.tenant] (SubModel | None) = the managed AWS organisation. ci.toml names no [aws.tenant].
D3 The two permission-set values are access policy: they leave the AWS vendor slice for an access-owned slice in packages/access, moved mechanically (no redesign; follow-up for the access tasks: the permission-set policy is redesigned in the access feature).
D4 Size exception: one PR while under 20 production code files (count below).
D5 [aws] is validated at boot; a malformed [aws.tenant] fails boot. D6 AWS_DEFAULT_REGION added to .devcontainer/docker-compose.yml. D7 pyproject placeholder ARNs dropped if no test needs them; ci.toml never gets an [aws.tenant]; a test that needs one constructs it. D8 the dead aws_region template variable (terraform/ecs.tf:33) stays for 111.15.1.

== Size ==
Production code/config files: 16. Python 8 (integrations/aws/settings.py, integrations/aws/client.py, server/configuration/host_configuration.py, packages/aws_platform/adapters/sso_admin.py, packages/aws_platform/adapters/identity_center.py, packages/access/sync/adapters/aws_identity_center.py, modules/aws/ops_group_assignment.py, packages/access/common/settings.py); config 3 (app/config/base.toml, production.toml, local.toml; ci.toml unchanged); wiring 3 (app/pyproject.toml, .github/workflows/ci_code.yml, .devcontainer/docker-compose.yml); helpers 2 (app/bin/audit_env_names.py, bin/deploy-checks.zsh). Docs 3 on top (decisions/configuration.md, doc-14, packages/access/sync/adapters/README.md) = 19 files with docs, still under 20. ~300 prod LOC. Subsystem: the AWS vendor slice plus its two pass-through readers; no terraform. Over the ~10-file gate only by the human's D4 exception; if implementation finds the count would reach 20 (e.g. a reader needing an edit that this plan assumes unchanged), stop and split the access-slice move out as 111.11.3.

== Context (verified 2026-10-26) ==
- integrations/aws/settings.py:22-125 AWSSettings(BaseSettings, aliases, extra=ignore). Fields and homes after this task: aws_region, dynamodb_endpoint_url -> DELETED (SDK namespace); retry_max_attempts, retry_mode, connect_timeout_seconds, read_timeout_seconds, transient_retry_after_seconds, not_found/unauthorized/transient_codes -> [aws]; audit/org/logging_role_arn, instance_id, instance_arn -> [aws.tenant]; system_admin_permissions, view_only_permissions -> access slice. service_role_map stays on AWSSettings (computed from the tenant).
- Tuning readers (stay on [aws], hosting uses them without any tenant): client.py:158-165 (_build_config), :204-215 (codes, transient_retry_after); server/services.py:40,44 builds DynamoDB stores through get_aws_client.
- Organisation readers and the fields they use (all inside functions; no import-time read, so no prerequisite): role map -> packages/aws_platform/adapters/{organizations.py:115 (org), cost_explorer.py:114 (org), config.py:100 (audit), guard_duty.py:109 (logging), security_hub.py:95 (logging), aws_lambda.py:97 and dynamodb.py:129 (no entry: in-account), identity_center.py:301 (org), sso_admin.py:170 (org)}, packages/access/sync/adapters/aws_identity_center.py:1225 (org), features/incident/core/adapters/status_updates.py:247 (no entry). instance_id -> identity_center.py:304, aws_identity_center.py:1227. instance_arn -> sso_admin.py:173. Callers: jobs/scheduled_tasks.py:147 (IdC healthcheck), modules/provisioning/{users.py:61,groups.py:142}, modules/aws/identity_center.py, modules/aws/ops_group_assignment.py:24,63, packages/access/sync/providers.py:40.
- Because service_role_map keeps its name and shape, the eight role-map readers need NO edit (an absent tenant yields {}, so .get(...) is None: the bot's own credentials, exactly what an empty ARN gives today). Only the three instance readers and sso_admin's builder change.
- Permission-set values: only reader is packages/aws_platform/adapters/sso_admin.py:167-175 (build_sso_admin_adapter passes them to SsoAdminAdapter, whose constructor already takes them: :44-50, aliases :97-98), called only by legacy modules/aws/ops_group_assignment.py:63. The access feature (packages/access) itself reads neither. Existing access settings pattern: packages/access/common/settings.py (AccessConfigSettings, AccessSyncSettings, AccessRequestsSettings: BaseSettings, ACCESS_<SUB>_ env, built by plugin providers). None is on the files yet, so this is the first ConfigurationSlice in packages/access.
- Region and endpoint: botocore 1.43.116 reads AWS_DEFAULT_REGION and the shared config file, NOT AWS_REGION (verified); ECS sets both in Fargate (https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs-environment-variables.html); the task definition template sets neither; production works today on the field default. AWS_ENDPOINT_URL_DYNAMODB is honored natively (verified: dynamodb overridden, sts not); .devcontainer/docker-compose.yml:31 already sets it. Local region: ~/.aws/config; CI: pytest-env.
- Production (doc-14 rows 34-42): the seven names are in sre-bot-config; production_names test says only AWS_ORG_ACCOUNT_ROLE_ARN has a value; tuning names unset. AWS_SRE_ACCOUNT_ROLE_ARN and AWS_SSO_ROLE_ARN have no reader (delete rows, 111.15).
- Tests reading old names: tests/unit/integrations/aws/*, tests/unit/packages/aws_platform/*_provider.py (11 files), test_configuration_settings_production_names.py (33 refs), tests/integration/integrations/aws/test_identity_store_conformance.py:37, tests/unit/bin/test_bin_audit_env_names_classify.py, test_bin_settings_key_ownership_check.py.
- Out of scope: infrastructure/configuration/features/aws_ops.py (AWSFeatureSettings: AWS_ADMIN_GROUPS, AWS_OPS_GROUP_NAME) moves with its package (TASK-159 / 111.14).

== The [aws.tenant] entry ==
- AwsTenant (frozen, extra=forbid, Pydantic at the config boundary like GoogleWorkspaceTenant): instance_id (required), instance_arn (required), audit_role_arn, org_role_arn, logging_role_arn (each optional, default empty).
- Required vs optional, from the readers: a present entry requires the Identity Center pair because the three IdC readers need the id (identity_center.py:304, aws_identity_center.py:1227) and the ARN (sso_admin.py:173) and an entry without them fails at use with a boto validation error today; the instance id and ARN identify one instance, so a half pair is never valid. The three role ARNs are individually optional: 'when unset, the bot's own credentials are used' is a supported mode (adapters README :79) and production sets only the org ARN, so requiring all three would change production behaviour. An empty role value counts as unset.
- The AWS tenant id (workplace-systems.md rule 3, 'the entry carries the vendor's real tenant id') is the Identity Center identity store id (instance_id, d-xxxxxxxxxx). Recommendation and reason: it is the id every Identity Center and Identity Store call carries and the one the access feature addresses; the organisation id (o-...) and the management account id are used by no reader (the org role ARN already implies the account). Format check, documented: IdentityStoreId pattern d-[0-9a-f]{10} or a UUID (https://docs.aws.amazon.com/singlesignon/latest/IdentityStoreAPIReference/API_ListUsers.html); instance_arn pattern arn:aws(-[a-z]{1,5}){0,3}:sso:::instance/(sso)?ins-[a-zA-Z0-9-.]{16} (https://docs.aws.amazon.com/singlesignon/latest/APIReference/API_ListAccountAssignments.html). No pattern is documented for a role ARN, so none is added. AWS is not a WorkplaceSystem (contracts/workplace/systems.py): no TenantSource row; the rule applies by analogy through configuration.md's vendor-enablement paragraph.
- Absent tenant (ci.toml, a developer without one): service_role_map is {} (readers use the bot's own credentials) and AWSSettings.identity_store_id and .sso_instance_arn return '' (properties on the slice), so the three IdC builders behave exactly as with empty strings today. Production behaviour is identical because production.toml names the tenant with today's values. No environment names exist for [aws]/[aws.tenant]: every value is public.

== The access-owned permission slice ==
- packages/access/common/settings.py gains AccessPermissionSetsSettings(ConfigurationSlice): toml_table_header=("access_permission_sets",), env_prefix="ACCESS_PERMISSION_SETS__", extra=forbid; fields system_admin_permissions and view_only_permissions (str, default '', names and semantics unchanged: they are the permission set ARNs the 'write' and 'read' aliases resolve to, sso_admin.py:36-37), plus get_access_permission_sets_settings() (lru_cache) beside the other providers; module docstring list updated. base.toml [access_permission_sets] (empty strings), production.toml the production values. Read at use (the access plugins are disabled in production and a disabled plugin never validates its settings), validated by the files test.
- Reader: build_sso_admin_adapter() in packages/aws_platform takes system_admin_permissions and view_only_permissions as keyword parameters (the adapter constructor already does) and no longer reads them; its only caller modules/aws/ops_group_assignment.py:63 passes them from get_access_permission_sets_settings(). aws_platform never imports packages.access (direction kept). Verify make check-import-contracts accepts modules.aws -> packages.access.common.settings; if not, the legacy caller imports through the existing allow-list entry or the contract file gains one line (no new file).
- Follow-up (access tasks, not here): the permission-set policy itself is redesigned in the access feature; record it with backlog task comment on the access epic after merge.

== Steps (TDD, red first) ==
B1 Tests (red): T-1..T-9.
B2 integrations/aws/settings.py: AWSSettings(ConfigurationSlice) toml_table_header=("aws",), env_prefix="AWS__"; tuning fields + code lists; tenant: AwsTenant | None = None; service_role_map, identity_store_id, sso_instance_arn; aws_region, dynamodb_endpoint_url, the two permission fields and every alias deleted; docstring rewritten.
B3 integrations/aws/client.py:147-152,170,180: drop endpoint_url and region_name (SDK resolves); docstrings :1-10,:139-146.
B4 server/configuration/host_configuration.py:152: get_aws_settings() beside get_google_workspace_settings() (+import).
B5 packages/access/common/settings.py (new slice and provider); packages/aws_platform/adapters/sso_admin.py:167-175 (parameters; instance_arn from settings.sso_instance_arn); identity_center.py:304 (settings.identity_store_id); packages/access/sync/adapters/aws_identity_center.py:1227 (settings.identity_store_id); modules/aws/ops_group_assignment.py:63.
B6 app/config/base.toml: [aws] (retry_max_attempts=3, retry_mode="standard", connect/read 10, transient_retry_after_seconds=60, the three code lists as today; comment: values are public (decisions/configuration.md); region and endpoint are the SDK's; the tenant entry names the managed organisation) and [access_permission_sets]. production.toml: [aws.tenant] (instance_id, instance_arn, the roles production sets) and [access_permission_sets], values from pre aws. local.toml: the same from the Codespace (H1). ci.toml: nothing.
B7 app/pyproject.toml pytest env: drop the AWS_*_ACCOUNT_ROLE_ARN lines (:154-156) if the suite passes without them; add AWS_DEFAULT_REGION=ca-central-1 under the existing comment. .github/workflows/ci_code.yml:79: delete the AWS_ORG_ACCOUNT_ROLE_ARN line. .devcontainer/docker-compose.yml: AWS_DEFAULT_REGION: 'ca-central-1' beside :31 (a devcontainer rebuild picks it up).
B8 Existing tests moved off the old names (aws unit tests install tmp files, provider tests construct AWSSettings(tenant=AwsTenant(...)) or patch the provider, identity_store_conformance sets AWS_DEFAULT_REGION literally).
B9 Helpers. app/bin/audit_env_names.py HINTS: AWS_AUDIT_ACCOUNT_ROLE_ARN, AWS_ORG_ACCOUNT_ROLE_ARN, AWS_LOGGING_ACCOUNT_ROLE_ARN, AWS_SSO_INSTANCE_ID, AWS_SSO_INSTANCE_ARN -> '[aws.tenant] <key>'; AWS_SSO_SYSTEM_ADMIN_PERMISSIONS, AWS_SSO_VIEW_ONLY_PERMISSIONS -> '[access_permission_sets] <key>'; AWS_RETRY_MAX_ATTEMPTS, AWS_RETRY_MODE, AWS_CONNECT_TIMEOUT_SECONDS, AWS_READ_TIMEOUT_SECONDS, AWS_TRANSIENT_RETRY_AFTER_SECONDS, AWS_NOT_FOUND_CODES, AWS_UNAUTHORIZED_CODES, AWS_TRANSIENT_CODES -> '[aws] <key>'; AWS_REGION, AWS_DEFAULT_REGION, AWS_ENDPOINT_URL_* stay RUNTIME (none) and win over HINTS (AWS_RETRY_MODE is also an SDK name: T-8). bin/deploy-checks.zsh: task check aws (pre and post below); TASK_CHECKS=(google aws), PRE_CHECKS=(google aws).
B10 Docs: decisions/configuration.md Changes line (AWS values public incl. role ARNs and SSO ids; [aws] tuning vs [aws.tenant]; permission sets access-owned; region/endpoint the SDK's; tenant id = identity store id) and the current-state lines naming AWS; doc-14 rows 34-42 (tenant keys, access slice keys, 'no longer read (TASK-111.11.1)', blob lines inert until 111.15); adapters README :77-79.

== deploy-checks aws ==
pre (merge gate, human runs it): from the blobs print which of the seven names are set and, these being public, their values for production.toml; whether instance_id and instance_arn match the documented patterns (a NO blocks: boot would fail); for each role ARN whether its account id appears in terraform/iam.tf (informational: INFO NOT-PUBLISHED, does not block under D1); names of any AWS_RETRY_*, AWS_*_TIMEOUT_SECONDS, AWS_*_CODES lines (expected none: a present one needs an [aws] key in production.toml first); task-definition environment names (expect no AWS_REGION; ECS injects it). aws_pre PASS when both patterns match and no unexpected tuning line.
post: boot lines clean (generic section); zero NoRegionError, EndpointConnectionError, InvalidClientTokenId, AssumeRole AccessDenied lines since the deploy; DynamoDB-backed coordination/record events present since the deploy; a configuration_invalid line absent; blob lines still present (inert). aws PASS/FAIL.

== Tests ==
T-1 tests/unit/integrations/aws/test_aws_settings_load.py (replaces test_aws_settings_fields.py; installed tmp files): [aws] tuning and overrides; [aws.tenant] fills the role map ({'organizations','identitystore','sso-admin','ce'} -> org, 'audit','config' -> audit, 'logging','guardduty','securityhub' -> logging); only the org ARN set gives only org entries (production shape); absent tenant gives {} and ''/'' for identity_store_id/sso_instance_arn; all old names (fifteen AWS_*, including the two permission names) in env and .env ignored; no aws_region, dynamodb_endpoint_url or permission attribute exists (AC 1, 4).
T-2 test_aws_settings_tenant_validate.py: tenant without instance_arn or instance_id fails naming the key; instance_id/instance_arn off the documented patterns fail; empty role ARN counts as unset; unknown key in [aws] or [aws.tenant] fails naming the key (AC 1).
T-3 tests/unit/integrations/aws/test_aws_client_factory_config.py (edited): region from AWS_DEFAULT_REGION; AWS_ENDPOINT_URL_DYNAMODB overrides dynamodb only; no region anywhere -> NoRegionError (documents the dependency); AssumeRole builds STS and the assumed session in the resolved region (AC 2).
T-4 tests/unit/infrastructure/configuration/test_configuration_files_aws.py: production.toml and local.toml parse; production has a tenant, ci has none, base has none; no file holds a key, token or secret-shaped value; the access table is in base.toml (AC 3, 6).
T-5 tests/integration/server/test_lifespan_vendor_slice_validation.py: unknown [aws] key and a malformed [aws.tenant] each fail load_host_configuration naming the key; no tenant boots (AC 1, 7).
T-6 tests/unit/packages/access/common/test_access_permission_sets_settings.py: reads [access_permission_sets]; old AWS_SSO_*_PERMISSIONS ignored; unknown key fails; tests/unit/packages/aws_platform/test_aws_platform_sso_admin_provider.py: build_sso_admin_adapter(system_admin_permissions=..., view_only_permissions=...) resolves 'write'/'read'; tests/unit/modules/aws/test_ops_group_assignment_handler.py: the handler passes the access slice's values (AC 6).
T-7 pin file test_configuration_settings_production_names.py: AWS rows move to [aws]/[aws.tenant]/[access_permission_sets] keys; the fifteen old names asserted unread; no ConfigurationSlice declares AWS_REGION/AWS_ENDPOINT_URL_*/AWS_DEFAULT_REGION (also make check-settings-key-ownership) (AC 1, 4).
T-8 tests/unit/bin/test_bin_audit_env_names_classify.py: the HINTS classify with their destination; SDK names stay none (AC 4).
T-9 provider tests (tests/unit/packages/aws_platform/*, access aws_identity_center, status_updates): adapters built from an AWSSettings with and without a tenant; unchanged assertions.
AC -> step -> test: #1 B2,B4,B6 / T-1,T-2,T-5,T-7 ; #2 B3 / T-3 ; #3 B6 / T-4 + G1,H1 ; #4 B2,B5,B7 / T-1,T-6,T-7,T-8 ; #5 gates ; #6 (tenant) B2,B6 / T-1,T-2,T-4,T-5 ; #7 (access-owned names) B5,B6 / T-6 ; #8 (ci has no tenant, absent-tenant behaviour) B2,B7 / T-1,T-4.

== Assumptions and doubts ==
(a) ECS supplies AWS_DEFAULT_REGION in the running task: pre prints the task-definition env; post greps NoRegionError. If absent, an expand PR adds it to the task definition BEFORE this merges.
(b) The dotenv source with prefix AWS__/ACCESS_PERMISSION_SETS__ ignores the old lines in .env under extra=forbid: T-1, T-6.
(c) AWS_RETRY_MODE is an SDK variable too; the explicit Config(retries=...) already overrides it today: T-3.
(d) Nested table [aws.tenant] deep-merges with env (none here) and the ownership check accepts [aws.tenant] as part of [aws]: make check-settings-key-ownership.
(e) modules.aws -> packages.access import is allowed: make check-import-contracts (B5).
(f) The production permission values really are permission-set ARNs; pre prints them; no format check added (mechanical move; the policy is redesigned later).
(g) No test needs the placeholder ARNs: verify by blanking (B7).
(h) File count stays under 20 (see Size).

== Blast radius and rollback ==
DynamoDB stores (records, coordination, scheduler leases, incident status updates), and Identity Center / Organizations / SSO surfaces where used (ops-group assignment, IdC healthcheck, provisioning). A malformed [aws]/[aws.tenant] fails boot and the ECS circuit breaker rolls back; a wrong ARN, instance id or permission value fails at use, so post aws and the manual check decide rollback; a missing region would fail every DynamoDB call (pre checks (a)). The previous image reads the unchanged blob lines (kept until 111.15), so one git revert plus build_and_deploy with the pre image_tag restores.

== Merge gates (human) ==
G1 zsh bin/deploy-checks.zsh pre aws from this branch: both patterns match; the agent copies the printed values into production.toml; rerun at merge for the rollback image_tag and task-definition env.
G2 Gates from app/: ruff, mypy (no new errors in touched files), pytest tests --ignore=tests/smoke, make check-import-contracts, make check-settings-key-ownership.
H1 local.toml: the agent reads the seven AWS_* names from the Codespace environment (public values; no key or token) and writes [aws.tenant] and [access_permission_sets].
H2 app/.env.example: remove any old AWS_* role/SSO/retry/permission lines (agents are denied app/.env*; the human edits it). Rebuild the devcontainer for the AWS_DEFAULT_REGION line.
H3 zsh bin/env-checks.zsh --all AWS_ from this branch: the old names classify delete in Codespaces; SDK names (AWS_REGION, AWS_DEFAULT_REGION, AWS_ENDPOINT_URL_DYNAMODB, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY) none; blob lines none.

== Post-deploy ==
zsh bin/deploy-checks.zsh post aws. Manual: a DynamoDB-backed read (incident status updates list, or any scheduler lease log event after the deploy); and one Identity Center read through the new tenant (the aws entry of the scheduled healthcheck in jobs/scheduled_tasks.py:147 logs success, or a read-only Identity Center listing if enabled). Rollback on FAIL: build_and_deploy with image_tag=<pre tag> (docs/runbooks/roll-back-a-deployment.md), then revert.

== Cleanup (after the post-deploy PASS) ==
- Codespaces: gh secret delete AWS_SSO_SYSTEM_ADMIN_PERMISSIONS, AWS_SSO_VIEW_ONLY_PERMISSIONS, AWS_AUDIT_ACCOUNT_ROLE_ARN, AWS_ORG_ACCOUNT_ROLE_ARN, AWS_LOGGING_ACCOUNT_ROLE_ARN, AWS_SSO_INSTANCE_ID, AWS_SSO_INSTANCE_ARN (--app codespaces -R cds-snc/sre-bot); confirm with env-checks.
- Actions: gh secret delete AWS_ORG_ACCOUNT_ROLE_ARN -R cds-snc/sre-bot.
- SSM: no edit; blob lines go with the blobs in 111.15.1/111.15.2.

AC TRACEABILITY CORRECTION (supersedes the AC line in Tests): #1 B2,B4,B6 / T-1,T-2,T-5,T-7 ; #2 B3 / T-3 ; #3 B6 / T-4 + G1,H1 ; #4 B2,B5,B7 / T-1,T-6,T-7,T-8 ; #5 gates ; #6 (tenant entry, absent tenant, ci none) B2,B6,B7 / T-1,T-2,T-4,T-5 ; #7 (access-owned permission values) B5,B6 / T-6 ; #8 (public values in production.toml and local.toml, AWS_DEFAULT_REGION in docker-compose) B6,B7 / T-4 + G1,H1.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-26 plan approved (human), with the AC #1 and #3 rewording and open questions 1 to 4 as recommended: empty instance values with no tenant (a not-configured error is the access redesign's), [access_permission_sets] read at use, import contracts confirmed by make check-import-contracts, AWS_DEFAULT_REGION confirmed by pre aws before merge (else an expand PR first).

2026-10-26 implementation (agent), In Progress.
Changed: integrations/aws/settings.py (AWSSettings is the [aws] ConfigurationSlice; AwsTenant [aws.tenant] with instance id/ARN pattern checks, optional role ARNs; identity_store_id, sso_instance_arn, service_role_map from the tenant; aws_region, dynamodb_endpoint_url, permission fields and every alias deleted), integrations/aws/client.py (no region or endpoint argument; the SDK resolves both), server/configuration/host_configuration.py (get_aws_settings validated at boot), packages/aws_platform/adapters/{sso_admin,identity_center}.py, packages/access/sync/adapters/aws_identity_center.py, modules/aws/ops_group_assignment.py, packages/access/common/settings.py (AccessPermissionSetsSettings, [access_permission_sets]), app/config/{base,local,production}.toml, app/pyproject.toml (AWS_DEFAULT_REGION in pytest env, placeholder ARN lines dropped), .github/workflows/ci_code.yml, .devcontainer/docker-compose.yml (AWS_DEFAULT_REGION), app/bin/audit_env_names.py HINTS, bin/deploy-checks.zsh (task check aws, pre and post), decisions/configuration.md, doc-14, adapters README. Tests T-1..T-9 written first (red on missing names), then code; existing aws/provider/integration tests moved off the old names; test_configuration_files_google_tenant.py Drive-id scan now cuts the [aws] error-code lists out (CamelCase codes matched the Drive-id shape).
Gates (app/): ruff check: All checks passed!; ruff format: clean; mypy: Found 47 errors in 18 files (baseline 47, none in touched files); pytest tests --ignore=tests/smoke: 1 failed, 5858 passed (the failure is test_configuration_files_production_values_are_recorded, red by design while production.toml holds placeholders); make check-import-contracts: Contracts: 13 kept, 0 broken; make check-settings-key-ownership: OK.
Remaining for the human: (1) run zsh bin/deploy-checks.zsh pre aws and give the agent the printed values for production.toml [aws.tenant] (instance_id, instance_arn, org_role_arn; audit/logging only if set) and [access_permission_sets]; replace the marked placeholders; the production-values test then goes green (AC #3, #5, #8). (2) Edit app/.env.example (agents are denied): remove the old AWS_* role/SSO/retry/permission lines. (3) Rebuild the devcontainer for AWS_DEFAULT_REGION. (4) After the post-deploy PASS: the Codespaces and Actions secret cleanup in the plan. Stale docstring left: packages/access/common/providers.py still names AWS_SSO_INSTANCE_ID (kept out of this PR to stay under the file budget).

2026-10-26 rework (human decision): the AWS tenant entry and the SSO permission sets are environment only, as Google's tenant. The identity store id and instance ARN are non-public values (internal tenant identifiers; the d- id is the default access-portal subdomain) and the permission-set ARNs embed the instance id. Changes: AWSSettings reads the tenant from AWS__TENANT__<FIELD> only (present when AWS__TENANT__INSTANCE_ID is set, empty counts as unset, a role or ARN without an instance id fails naming the variable, same pattern checks); production.toml and local.toml name no tenant or permission set (the development values were removed, not copied anywhere); base.toml comments name the variables and keep the two empty access keys; pytest-env blanks the five AWS__TENANT__ and two ACCESS_PERMISSION_SETS__ names; tests use synthetic values, the production-values and local-roles-against-iam.tf tests are replaced by Google-style files tests (no file names a tenant or permission-set value; each environment builds no tenant); audit HINTS and doc-14 rows point to the new SSM names; bin/deploy-checks.zsh pre aws hash-compares the five parameters with the blob lines (MATCH/DIFFER/MISSING), checks the blob values' formats and the AWS_ names in the task definition; post aws unchanged. terraform/ssm.tf and the ADR were done by the human.
Gates (app/): ruff check: All checks passed!; mypy: Found 47 errors in 18 files (baseline 47); pytest tests --ignore=tests/smoke: 5860 passed in 159.12s; make check-import-contracts: Contracts: 13 kept, 0 broken.; make check-settings-key-ownership: OK. Nothing is red by design.
Human steps: after the terraform expand PR applies, put-parameter /sre-bot/AWS__TENANT__INSTANCE_ID from the AWS_SSO_INSTANCE_ID blob line, INSTANCE_ARN from AWS_SSO_INSTANCE_ARN, ORG_ROLE_ARN from AWS_ORG_ACCOUNT_ROLE_ARN, ACCESS_PERMISSION_SETS__SYSTEM_ADMIN_PERMISSIONS from AWS_SSO_SYSTEM_ADMIN_PERMISSIONS, ACCESS_PERMISSION_SETS__VIEW_ONLY_PERMISSIONS from AWS_SSO_VIEW_ONLY_PERMISSIONS; run zsh bin/deploy-checks.zsh pre aws (all MATCH, formats OK); Codespaces secrets under the new names (AWS__TENANT__INSTANCE_ID, INSTANCE_ARN, AUDIT_ROLE_ARN, ORG_ROLE_ARN, LOGGING_ROLE_ARN, ACCESS_PERMISSION_SETS__SYSTEM_ADMIN_PERMISSIONS, VIEW_ONLY_PERMISSIONS; audit and logging are development only); edit app/.env.example; rebuild the devcontainer; then post aws.

2026-10-27 AC #3, #6 and #8 reworded for the environment-only tenant entry (human approval); #1, #2, #4 to #7 re-checked on the reworked tree (gates re-run 2026-10-26: 5860 passed, mypy 47 = baseline, contracts 13 kept, key ownership OK); #3 and #8 wait on pre aws after the ssm-aws-tenant-parameters expand PR applies and the five values are put.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-26T22:40:00Z

---

Proposal (human decision 2026-10-26, for approval to reword; not applied): AC #1 should read '[aws] holds only the client tuning and declares no AWS_* SDK name'; AC #3 should say '[aws.tenant]' and '[access_permission_sets]' for the production values; AC #4's list of old names is still exact. Added ACs #6-#8 cover the tenant entry, the access-owned permission names and the public values. No AC deleted.

---
<!-- COMMENTS:END -->
