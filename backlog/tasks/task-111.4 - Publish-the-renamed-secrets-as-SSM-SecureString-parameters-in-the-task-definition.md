---
id: TASK-111.4
title: >-
  Publish the renamed secrets as SSM SecureString parameters in the task
  definition
status: Done
assignee:
  - '@me'
created_date: 2026-10-20 23:25
updated_date: '2026-10-21T20:14:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.1
references:
  - terraform/ecs.tf
  - terraform/templates/sre-bot.json.tpl
  - decisions/configuration.md
  - https://github.com/cds-snc/sre-bot/issues/1751
parent_task_id: TASK-111
type: feature
ordinal: 410000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Terraform moves to 1.16.6 so each renamed secret can be an SSM SecureString parameter created through the write-only value_wo argument (a placeholder; no value ever reaches terraform state), named /sre-bot/<NAME> and injected under its <SLICE>__<FIELD> name through the task definition's secrets:, with the execution role's read. The running image ignores the new names; the old blobs stay until the contract slice. The rename map comes from the inventory doc (doc-14). Human, after the merge applies: set every value with put-parameter --overwrite before TASK-111.7 to 111.13 merge.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Terraform is pinned to 1.16.6 in tf_plan.yml, tf_apply.yml and the devcontainer; terragrunt stays 0.48.0; the unused TERRAGRUNT_VERSION pin in ci_code.yml is removed
- [x] #2 Every secret in the inventory's rename map has an SSM SecureString parameter /sre-bot/<NAME> created through value_wo and a task-definition secrets: entry under <NAME>; no secret value is in terraform state or the repo
- [x] #3 The execution role can read exactly those parameters besides the ones it already reads; decryption uses the AWS-managed aws/ssm key
- [ ] #4 terraform plan creates the parameters, updates the IAM policy in place and rolls out a new task-definition revision, and changes nothing else; the running service behaves as before
- [x] #5 decisions/configuration.md names value_wo instead of ignore_changes, and doc-14 names the parameter paths
- [x] #6 ruff, mypy (no new errors in touched files), pytest tests --ignore=tests/smoke, make check-import-contracts and make check-settings-key-ownership pass
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Every /sre-bot/ parameter holds its real value (put-parameter --overwrite) before TASK-111.7 to 111.13 merge (human)
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Decisions (human, 2026-10-21 planning session)
- Option B in one PR: Terraform moves from 1.5.3 to 1.16.6 (latest 1.x patch, released 2026-10-14) and the parameters use the write-only value_wo argument, so no value is ever read into state. ignore_changes does not keep a SecureString out of state: every refresh reads the decrypted value into raw state (aws provider ssm_parameter docs; value_wo needs Terraform 1.11 or later). The ADR's ignore_changes wording is corrected here.
- Parameter names are /sre-bot/<NAME> (for example /sre-bot/SLACK__BOT_TOKEN); the env name injected through secrets: is the bare <NAME>.
- Terragrunt stays 0.48.0: releases past about 0.80 drop --terragrunt-non-interactive, which tf_apply.yml uses. The PR's tf plan proves 0.48 runs with 1.16.6 before anything is applied.
- State key (2026-10-21, after the first PR plan failed): terraform/terragrunt.hcl builds key "${path_relative_to_include()}/terraform.tfstate" = "./terraform.tfstate". Terraform 1.5 (AWS SDK v1) stripped the "./", so the object is s3://sre-bot-tf/terraform.tfstate; 1.6+ (SDK v2) sends the key as-is, S3 returns nothing and the DynamoDB digest check fails (hashicorp/terraform#34279). The key becomes the literal "terraform.tfstate" (one unit, no includes): the same object and the same lock/digest item under both 1.5.3 and 1.16.6.
- Locking stays on dynamodb_table. It is deprecated in favour of S3-native use_lockfile (no removal version announced; both can run together during a migration), but terragrunt 0.48.0 predates use_lockfile (terragrunt fixed it in v1.0.0) and the terragrunt upgrade changes tf_apply.yml flags. That is its own task after this one, not part of 111.4.

Steps
1. Version pins: TERRAFORM_VERSION 1.5.3 -> 1.16.6 in .github/workflows/tf_plan.yml:10 and tf_apply.yml:13; .devcontainer/devcontainer.json:59 terraform feature version 1.16.6 (terragrunt 0.48.0 kept). Remove the unused TERRAGRUNT_VERSION: v0.31.1 env from .github/workflows/ci_code.yml:10 (no step reads it).
2. terraform/ssm.tf: locals.sre_bot_secret_names = the eleven doc-14 names (SLACK__BOT_TOKEN, SLACK__APP_TOKEN, SLACK__USER_TOKEN, GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY, OPENAI__API_KEY, NOTIFY__SRE_USER_NAME, NOTIFY__SRE_CLIENT_SECRET, OPSGENIE__INTEGRATIONS_KEY, TRELLO__APP_KEY, TRELLO__TOKEN, SENTINEL__SHARED_KEY). resource aws_ssm_parameter.sre_bot_secret, for_each over the set: name "/sre-bot/${each.value}", provider aws.core_services, type SecureString, value_wo a fixed non-secret placeholder, value_wo_version 1 (never bumped: a bump writes the placeholder over the real value; a comment says so), tags as the existing parameter. The existing gcp_sre_service_account_key parameter is untouched (111.15 removes it).
3. terraform/templates/sre-bot.json.tpl: "secrets": ${secrets}; terraform/ecs.tf builds secrets = jsonencode(concat([{GCP_SRE_SERVICE_ACCOUNT_KEY_FILE -> existing ARN}], [for name in sort(local.sre_bot_secret_names) : {name, valueFrom = aws_ssm_parameter.sre_bot_secret[name].arn}])) and drops the GCP_SRE_SERVICE_ACCOUNT_KEY_FILE template variable. Sorted so the rendered JSON is stable across plans.
4. terraform/iam.tf:31-35: add the eleven ARNs to the existing ssm:GetParameters/GetParameter statement (values(aws_ssm_parameter.sre_bot_secret)[*].arn). No kms statement: SecureStrings on the AWS-managed aws/ssm key need no kms:Decrypt grant for ECS secret injection (ECS docs: kms:Decrypt only for a customer managed key). Execution role and task role are the same role (sre-bot-ecs-role), so the app can also read them; splitting the roles is out of scope.
5. decisions/configuration.md:57: "Terraform creates each parameter with a placeholder through the write-only value_wo argument (Terraform 1.11 or later), so no value is read into terraform state; the value is set outside terraform." Add a dated history line (2026-10-21, TASK-111.4) after the 2026-10-20 entry.
6. doc-14 "Secrets TASK-111.4 creates": name the /sre-bot/<NAME> path and that GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY takes the current gcp_sre_service_account_key value.
7. terraform/terragrunt.hcl: key = "terraform.tfstate" with a comment naming the SDK change and the issue.

AC -> step -> check
- AC1 -> steps 1, 7 -> rg finds no 1.5.3 / v0.31.1 pin; terragrunt render-json shows key terraform.tfstate; PR tf plan runs on 1.16.6 with terragrunt 0.48.0 and reads the existing state.
- AC2 -> steps 2, 3 -> terraform fmt -check and validate (init -backend=false) with a 1.16.6 binary downloaded to the session scratchpad (the devcontainer has 1.5.3 until rebuilt); terraform console renders the container definition: twelve secrets entries, the eleven under bare names with /sre-bot/ ARNs; rg finds no secret value in the diff; value_wo is never stored in state (provider docs).
- AC3 -> step 4 -> validate plus the rendered policy in terraform console lists the thirteen parameter ARNs (two blobs, old GCP key, eleven new) and nothing wider.
- AC4 -> steps 2-4 -> the PR's tf plan comment (human reads it): 11 aws_ssm_parameter created, aws_iam_policy updated in place, aws_ecs_task_definition replaced (new revision; task definitions are immutable), aws_ecs_service updated in place to it, nothing destroyed except the old revision. The running image reads none of the new names: only LoggingSettings has an env_prefix (LOGGING__) and every other slice reads its own names with extra="ignore".
- AC5 -> steps 5, 6 -> review.
- AC6 -> ruff, mypy, pytest, make check-import-contracts, make check-settings-key-ownership (no Python change; run to show nothing moved).
No Python tests: no app code changes. TDD does not apply to the terraform change; terraform validate and the rendered console output are the checks.

Size: 9 files (3 workflows/devcontainer pins, terragrunt.hcl, ssm.tf, ecs.tf, iam.tf, template, ADR) + doc-14, about 50 LOC of terraform. Under the gate. One subsystem (deployment); the mechanical version bump rides with the behaviour change by human decision.

Order and blast radius
- Merging applies to production (tf_apply.yml on push to main). Apply creates the parameters with the placeholder and rolls out a new task-definition revision; the placeholders are injected under names the image ignores, so behaviour is unchanged. Human after apply: put-parameter --overwrite each real value (taken from the sre-bot-config blobs and gcp_sre_service_account_key). Running tasks see the real values at their next deployment; 111.7 to 111.13 depend on that, so the values must be set before the first of them merges.
- Failure modes: if terragrunt 0.48 or the cds-snc plan action fails on 1.16.6, the PR's plan fails before anything applies. A missing parameter at task start blocks the start and the circuit breaker rolls back, which cannot happen here because terraform creates them.
- Rollback: the parameters are additive; reverting the terraform part destroys them (values must be set again). Keep 1.16.6 when rolling back: a 1.5.3 run against state holding value_wo resources is untested, so revert the resources first under 1.16.6 and leave the version pin. Never revert the state key: the new key reads the same object on 1.5.3 and 1.16.6, while the old "./" key on 1.5.3 compares the state the first 1.16.6 apply writes against the digest stored under LockID sre-bot-tf/./terraform.tfstate-md5 and fails on every run until that item's Digest is corrected or deleted.
- Open PR branches that still have the old key and Terraform 1.5.3 (renovate/all-minor) fail their tf plan the same way once this merges and applies: rebase them on main. After the first 1.16.6 apply, the human deletes the stale digest item (sre-bot-tf/./terraform.tfstate-md5); nothing reads it any more, and that removes the trap above.

Follow-up synced: TASK-111.15 also removes the old gcp_sre_service_account_key parameter, its variable and the TF_VAR_gcp_sre_service_account_key / GCP_SRE_SERVICE_ACCOUNT_KEY_FILE GitHub secret, since that value sits in state today.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
What changed
- Terraform 1.5.3 -> 1.16.6 in .github/workflows/tf_plan.yml, tf_apply.yml and .devcontainer/devcontainer.json; terragrunt stays 0.48.0. The unread TERRAGRUNT_VERSION: v0.31.1 env is removed from ci_code.yml (no step read it).
- terraform/ssm.tf: local sre_bot_secret_names (the eleven doc-14 names) and aws_ssm_parameter.sre_bot_secret (for_each, /sre-bot/<NAME>, SecureString, value_wo placeholder, value_wo_version 1 with a never-bump comment, core_services provider, same tags as the existing parameter).
- terraform/ecs.tf builds the secrets: list (old GCP_SRE_SERVICE_ACCOUNT_KEY_FILE first, then the eleven sorted by name) and the template takes it as ${secrets}; the GCP_SRE_SERVICE_ACCOUNT_KEY_FILE template variable is gone. terraform fmt realigned the templatefile map.
- terraform/iam.tf: the ssm:GetParameters/GetParameter statement adds the eleven ARNs; no kms statement (AWS-managed aws/ssm key).
- decisions/configuration.md: the secrets paragraph names /sre-bot/<NAME> and value_wo, says why ignore_changes does not keep a SecureString out of state, and a 2026-10-21 history line. doc-14 names the paths and the source of the Google key value.

Evidence
- terraform 1.16.6 (release zip, SHA256SUMS OK) on a scratch copy: fmt -check -recursive clean; init -backend=false and validate: Success. A mocked terraform test (mock providers, targeted at the task definition and the policy, scratch only, not committed) passed: 11 parameters named /sre-bot/<key>, SecureString, value_wo_version 1; the rendered container definition's secrets names equal GCP_SRE_SERVICE_ACCOUNT_KEY_FILE plus the eleven; the SSM statement's resources are the two blobs plus the parameter ARNs (the mock gives every parameter one ARN, so the count of eleven is shown by the config, not the mock).
- uv run ruff check .: All checks passed. mypy: 47 errors in 18 files, all pre-existing; no Python file is touched (0 in touched files). make test: 4726 + 776 passed; uv run pytest tests --ignore=tests/smoke: 5502 passed. make check-import-contracts: 12 kept, 0 broken. make check-settings-key-ownership: OK.

Left for the human
- AC4: read the PR's tf plan comment. Expected: 11 aws_ssm_parameter.sre_bot_secret created, aws_iam_policy.sre-bot_secrets_manager updated in place, aws_ecs_task_definition.sre-bot replaced (new revision), aws_ecs_service.main updated in place; nothing else. The plan also proves terragrunt 0.48.0 and cds-snc/terraform-plan run on 1.16.6.
- Merging applies to production; the running image ignores the new names (only LoggingSettings has an env prefix, every other slice reads its own names with extra=ignore).
- DoD: put-parameter --overwrite each real value before TASK-111.7 to 111.13 merge; rebuild the devcontainer for terraform 1.16.6.
- Rollback: revert the resources under 1.16.6 (the values must then be set again); keep the version pin.

State key fix (2026-10-21, after the first PR plan failed)
- The PR's terraform-plan failed: "checksum calculated for the state stored in S3 does not match the checksum stored in DynamoDB", calculated checksum empty, key ./terraform.tfstate. Plans on 1.5.3 (renovate/all-minor) passed against the same state 30 minutes earlier. Cause: Terraform 1.6+ uses AWS SDK v2, which sends the "./" literally; SDK v1 stripped it, so the object is s3://sre-bot-tf/terraform.tfstate (hashicorp/terraform#34279, maintainer workaround: drop the "./").
- terraform/terragrunt.hcl: key = "terraform.tfstate" with a comment. Nothing else reads the key (rg).
- Evidence: terragrunt 0.48.0 render-json shows key terraform.tfstate; terraform 1.16.6 fmt -check -recursive clean; init -backend=false and validate: Success. terragrunt hclfmt --terragrunt-check reports "Invalid file format" when run inside terraform/, but the same file passes on its own in a scratch directory, as does the committed version, so the in-repo failure comes from something else in that directory, not from this edit. No Python change; the earlier gate evidence stands.
- Locking stays on dynamodb_table (deprecated, no removal version). S3-native use_lockfile needs a terragrunt upgrade past 0.48.0 and new tf_apply.yml flags: proposed as its own task, not created.
- Rollback: never revert the key; it reads the same object on 1.5.3 and 1.16.6. The old key on 1.5.3 fails against the stale digest item sre-bot-tf/./terraform.tfstate-md5 once 1.16.6 has applied.

Left for the human (added)
- AC4 again: the re-run plan must read the existing state; expected changes as listed above.
- After merge: rebase open PRs that run tf plan (renovate/all-minor); after the first 1.16.6 apply, delete the stale DynamoDB item LockID sre-bot-tf/./terraform.tfstate-md5.

Re-run plan after the key fix (1c9cf581): terraform-plan passed on 1.16.6 with terragrunt 0.48.0 and read the existing state. Plan: 12 to add, 2 to change, 1 to destroy = the 11 aws_ssm_parameter.sre_bot_secret, aws_ecs_task_definition.sre-bot replaced (new revision added, old one destroyed), aws_ecs_service.main and aws_iam_policy.sre-bot_secrets_manager updated in place. Matches AC4's expectation; the human confirms AC4.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-21T20:05:00Z

---

Correction 2026-10-21: the plan's failure-mode line says the circuit breaker rolls back; production has no deployment_circuit_breaker and runs :latest, so it would not. TASK-111.16 adds both before TASK-111.7.

---
<!-- COMMENTS:END -->
