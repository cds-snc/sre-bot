---
id: TASK-180.1
title: >-
  Cut production over to keyless Google credentials: the federation audience
  parameter
status: To Do
assignee: []
created_date: '2026-11-05T21:17:00Z'
updated_date: '2026-11-06T01:56:00Z'
labels:
  - security
  - configuration
milestone: m-7
dependencies:
  - TASK-180
references:
  - decisions/service-accounts.md
  - decisions/configuration.md
  - docs/runbooks/set-up-google-workspace-access.md
parent_task_id: TASK-180
priority: high
type: feature
ordinal: 485000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Cutover step of TASK-180, as its own terraform-only PR (precedent: #1792 and TASK-111.10.1, rows 9.10.1 and 9.10.2: a parameter exists with its value before anything reads it). TASK-180 ships the federation code with production still on the key and SERVICE_ACCOUNT_EMAIL set and verified against the key. This PR adds GOOGLE_WORKSPACE__TENANT__FEDERATION_AUDIENCE to terraform/ssm.tf (the task-definition secrets: entry is derived). Terraform-only paths do not deploy, so the human sets the value with put-parameter and then redeploys the running image tag through the build_and_deploy dispatch. A deploy that reads the placeholder fails the audience shape check at boot, and the circuit breaker keeps the previous revision. Rollback, until TASK-182 deletes the key: revert this PR and redeploy the same tag; the key path resumes. Human GCP steps (pool, AWS provider pinned to account and role, the two grants on the service account) come before the merge, from the runbook.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Before merge: the workload identity pool, its AWS provider (condition on account 283582579564 and role sre-bot-ecs-role) and the two IAM grants on the service account exist in cdssnc as the runbook describes; deploy-checks pre passes
- [ ] #2 terraform/ssm.tf declares GOOGLE_WORKSPACE__TENANT__FEDERATION_AUDIENCE; tf_apply succeeds; the value is set with put-parameter before any deploy renders the new revision
- [ ] #3 After the redeploy: deploy-checks post google:federation passes (every task on federation, no token refusal, attribute-condition or getAccessToken error), and a test incident (folder, document, Meet) and a test retro invitation work
- [ ] #4 Rollback is written in the PR body and the runbook (revert, redeploy the same tag) and was not needed, or was exercised and recorded
- [ ] #5 The doc-11 row, TASK-182's precondition (at least one deploy on federation) and the runbook's 'Until TASK-180 ships' section reflect the cutover
- [ ] #6 docs/runbooks/set-up-google-workspace-access.md is walked end to end while setting up CDS's federation and corrected where it is wrong
- [ ] #7 Before merge: TASK-180 AC #5 is checked (SERVICE_ACCOUNT_EMAIL set in production and verified against the key by post google on every task), since an audience without the email fails boot
- [ ] #8 docs/runbooks/set-up-google-workspace-access.md step 4 states Google's generic federation practices: a dedicated project for pools and providers unless only a few administrators hold Google Cloud access, provider administration limited, one provider per pool, Data Access audit logs on for the STS, IAM and IAM Service Account Credentials APIs
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Scope: a terraform-only PR (one name in terraform/ssm.tf) plus the documentation the cutover changes, framed by human GCP steps before the merge and human cutover steps after it. No application code and no tests: the federation path, its boot checks (audience shape, email required, AWS region) and the google:federation deploy check all shipped in TASK-180 (#1828). Domain-model gate: not applicable (no entity, no stored data). Size gate: 1 terraform line, about 30 documentation lines, 4 files, one subsystem (deployment configuration). Passes.

Waits on: TASK-180 AC #5 (#1829 merged, SERVICE_ACCOUNT_EMAIL set from the key's client_email, the running tag redeployed, post google showing service_account_email=set on every task). Reason: an audience without the email fails boot (settings.py, TASK-180 AC #3), so this PR must not merge first.

Before merge (human, cdssnc; runbook docs/runbooks/set-up-google-workspace-access.md)
H1. Step 2: values set once in one terminal (PROJECT_ID=cdssnc, AWS_ACCOUNT_ID=283582579564, TASK_ROLE_NAME=sre-bot-ecs-role; SA_NAME, POOL_ID=sre-bot, PROVIDER_ID=aws-ecs), then SA_EMAIL replaced by the existing account's email (the "already exists" block). The check line must print OK.
H2. Step 3.2: enable the APIs (sts and iamcredentials are the new ones for federation; the command is idempotent). Skip 3.3. 3.4 is not needed (the delegation entry is unchanged: same client id).
H3. Step 4.1: create the pool sre-bot and the AWS provider aws-ecs with attribute.aws_role == arn:aws:sts::283582579564:assumed-role/sre-bot-ecs-role (terraform/iam.tf:67 sets path "/", so the assumed-role ARN has no path). Evidence: the provider describe output (condition, account 283582579564, state ACTIVE).
H4. Step 4.2: roles/iam.workloadIdentityUser and roles/iam.serviceAccountTokenCreator for the principalSet member on the existing service account only (no project-level binding). Evidence: the get-iam-policy table listing both roles for the principalSet member.
H5. Note every place the runbook was wrong or unclear while doing H1 to H4 (AC #6).
H6. deploy-checks pre at the merge (bin/deploy-checks.zsh pre: an SSM change), recorded with its file name.

The PR (agent, branch task-180.1-federation-audience from main after #1829 merged)
P1. terraform/ssm.tf: add "GOOGLE_WORKSPACE__TENANT__FEDERATION_AUDIENCE" to the parameter list in sorted position (after DELEGATED_USER_EMAIL). The task-definition secrets: entry is derived (ecs.tf); the parameter starts at the value_wo placeholder set-outside-terraform, which fails the audience shape check at boot (TASK-180 AC #3), so a deploy before put-parameter cannot run on a wrong audience: the circuit breaker keeps the previous revision.
P2. docs/runbooks/set-up-google-workspace-access.md: corrections from H5; step 4 states Google's generic federation practices for every adopter (service-accounts.md rule 5, 2026-11-06): a dedicated project for pools and providers unless only a few administrators hold Google Cloud access, provider administration limited to a few administrators (editing a mapping can impersonate the account), one provider per pool, Data Access audit logs on for the Security Token Service, IAM and IAM Service Account Credentials APIs (the existing line about IAM Credentials logs moves there); in step 9 or 11 a short "Cutting over an existing deployment from the key" paragraph: order (grants, parameter, put-parameter, redeploy the running tag, post google:federation) and rollback (revert the PR, tf_apply, redeploy the same tag; only while the key exists, until TASK-182); the "Until the transition ends" section drops the TASK-180.1 bullet (merge and cutover happen in one human session; a revert restores the bullet).
P3. app/integrations/google_workspace/README.md:74: drop the TASK-180.1 row of its transition table; the "Production until TASK-182" row of the at-a-glance table now reads as the fallback until TASK-182.
P4. ADRs: rule 5's project bullet and the incident-management.md verification-incident rule were amended at planning (2026-11-06). At cutover, service-accounts.md gets a dated Changes line "production authenticates to Google through federation from the ECS task role; the key remains only as the rollback until TASK-182". decisions/configuration.md needs no new rule (rule of 2026-11-05 line 174 already covers the order).
P5. Gates: terraform fmt -check on terraform/; make check-settings-key-ownership (the new SSM name maps to a settings field shipped in #1828); ruff, make check-import-contracts (unchanged code, run once for evidence). Full mypy and pytest are not needed for a terraform and docs PR; run them once at the end only if any Python file changes.

After merge (human; production changes only via GitHub Actions, local AWS read-only except the documented put-parameter)
C1. Watch the tf_apply run on main: success; the parameter exists with the placeholder.
C2. Immediately: aws ssm put-parameter --name /sre-bot/GOOGLE_WORKSPACE__TENANT__FEDERATION_AUDIENCE (in the core services account, as the email parameter) --value "$AUDIENCE" --overwrite (the parameter already exists as SecureString from terraform); confirm with get-parameter --with-decryption that it equals $AUDIENCE. No other PR merges between C1 and C3 (a deploy in that window would read the placeholder and roll back by circuit breaker, harmless but noisy).
C3. build_and_deploy workflow dispatch with image_tag = the running tag from deploy-checks pre.
C4. zsh bin/deploy-checks.zsh post google:federation after the rollout completes: rollout COMPLETED, every task source=aws_federation, google_federation PASS, google_no_refusal PASS (no attribute-condition, getAccessToken or token refusal), boot and runtime errors PASS.
C5. Slack: declare a test incident titled starting with TEST (folder, document, Meet link appear), close it straight away (incident-management.md 2026-11-06: verification incidents are marked; TASK-165.7 adds the record marker); schedule a test retro (invitation from the bot user).
C6. Record outcomes in the task notes; check ACs #2 to #4; update TASK-182's precondition evidence (AC #7 there: one deploy on federation with post google passing; the key's last-authentication time is read later).

Rollback: revert the PR (tf_apply deletes the parameter and its secrets: entry), then redeploy the same tag; boot selects the key again (the key and email are still set). One revert plus one dispatch; valid until TASK-182 deletes the key. Faster interim: none (setting the parameter back to the placeholder fails boot by design).

Blast radius: Google-backed features only (incident folder, document, sheets, Meet, retro invitations, directory reads). A wrong pool condition or missing grant shows as a token refusal on first Google call, not at boot, so C4 and C5 are the gate. Slack, AWS and other vendors are unaffected.

AC to step: #1 H1-H4, H6 · #8 P2 · #2 P1, C1, C2 · #3 C3-C5 · #4 P2, PR body, C6 · #5 P2, P3, C6, doc-11 row · #6 H5, P2 · #7 Waits on.
Tests: none (no code). The behaviour is covered by TASK-180's tests (federation selection, shape check, fake supplier chain); production verification is C4 and C5.

Assumptions, each verified:
A1 Fargate sets AWS_REGION in the container (AWS ECS environment variables docs); a missing region fails boot by name, so C4 would show it.
A2 The provider's default attribute mapping yields attribute.aws_role = arn:aws:sts::<account>:assumed-role/<role> (no session name); the H3 describe output and C4 confirm.
A3 tf_apply on a terraform-only path does not deploy (precedent #1792, TASK-111.10.1); confirmed by the ECS service staying on the pre revision until C3.

Decisions (2026-11-06, human, program-scope reassessment): GCP steps stay manual in cdssnc (TASK-169 D4; only a few administrators hold any Google Cloud access, so no dedicated pool project and no extra pool-admin evidence for CDS); the runbook carries the generic practices (P2, AC #8). Test incidents: TEST title now, record marker in TASK-165.7 (accepted for now). Docs ride in this PR (TASK-180 precedent). The window between tf_apply and the redeploy is covered by deployment.md (circuit breaker, a deploy succeeds only on its own revision) and configuration.md 2026-11-05. google-auth's regional-access-boundary lookup copies the transport: no task (TASK-180 notes).
<!-- SECTION:PLAN:END -->
