---
id: TASK-180.1
title: >-
  Cut production over to keyless Google credentials: the federation audience
  parameter
status: To Do
assignee: []
created_date: '2026-11-05T21:17:00Z'
updated_date: '2026-11-05T21:17:00Z'
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
<!-- AC:END -->
