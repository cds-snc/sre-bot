---
id: TASK-164
title: >-
  Deploy verify waits out the alarm bake time; post-deploy and environment
  checks run in CI
status: To Do
assignee: []
created_date: '2026-10-23T18:47:00Z'
updated_date: '2026-10-29T18:44:00Z'
labels:
  - deployment
  - ci
  - dev-tooling
milestone: m-7
dependencies: []
references:
  - bin/deploy-checks.zsh
  - bin/env-checks.zsh
  - app/bin/audit_env_names.py
  - app/bin/audit_env_coverage.py
  - docs/runbooks/roll-back-a-deployment.md
type: task
ordinal: 436000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
With deployment alarms enabled, ECS keeps a rolling deployment IN_PROGRESS through the alarm bake time after the service is stable. The deploy action's waiter returns at steady state, so 'Verify the deployed revision' sees IN_PROGRESS and fails the job, posting a false failure, although the rollout completes moments later. The verify step polls the service until the PRIMARY deployment leaves IN_PROGRESS, inside the existing 15-minute budget: COMPLETED on the registered revision passes; FAILED, a rollback to another revision or the timeout fails. Workflow and its verify script only; no terraform change.

FOLDED IN FROM TASK-177 (human, 2026-10-29): one PR with a size exception (workflow, verify script, read-only OIDC role, helper scripts and decisions/deployment.md). The OIDC role is IAM in terraform, so this task is under the manual-check rule itself: zsh bin/deploy-checks.zsh pre at merge and post after deploy, by hand, for this one merge.

bin/deploy-checks.zsh and bin/env-checks.zsh (with app/bin/audit_env_names.py and audit_env_coverage.py) are read-only helpers the human runs by hand, and the agent reads their output from tmp/. Since the configuration migration closed (2026-10-29), they are required only for a task that changes terraform, the task definition, IAM or SSM parameters, or adds, renames or removes an environment name or secret, and for the contract step that deletes what a running revision used (configuration.md rename rule). Running them in CI would remove the manual step and make the check part of the deploy record.

Shape to decide:
- **Post-deploy checks:** they could run as a job in build_and_deploy after the deploy step, or as a workflow triggered when that run completes. They need the deploy role's read access (ECS describe, ECR, Logs Insights StartQuery and GetQueryResults), which is read-only and prints names, counts and verdicts, never values. They run after the verify step this task fixes.
- **Pre-merge baseline:** the rollback image tag and the error baseline could be a workflow step before deploy, or the deploy run's own record of the previous tag. docs/runbooks/roll-back-a-deployment.md would read it from there.
- **Environment checks:** they could run on a schedule and when a pull request changes settings, terraform/ssm.tf, .devcontainer or .github.
  - GITHUB_TOKEN cannot list Codespaces user or organization secrets. Those sources need a GitHub App token or stay manual; record which ones a workflow can read.
  - Only the plan runs in CI. Apply stays a human step; a workflow never deletes a secret or variable.
- **Where the scripts live:** move them to .github/workflows/scripts/, or keep them in bin/ and call them from the workflow. bin/ is outside the image, and a developer still runs them locally.
- **Output:** a job summary or an artifact instead of tmp/; a failed verdict fails the job.

Security:
- an OIDC role with read-only permissions scoped to the log group, the service and the repository;
- no secret value in any output (CodeQL's clear-text-logging rule applies to the scripts' identifiers);
- outputs go nowhere outside GitHub.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The verify step passes when the PRIMARY deployment reaches COMPLETED on the registered revision within the budget, after any number of IN_PROGRESS polls
- [ ] #2 It fails, naming the state and reason, on FAILED, on a PRIMARY deployment of another revision, or when the budget runs out
- [ ] #3 verify-ecs-deployment.sh tests cover IN_PROGRESS then COMPLETED, FAILED, a rolled-back revision and the timeout
- [ ] #4 decisions/deployment.md states that a deploy is verified only once ECS reports the rollout complete, bake time included
- [ ] #5 A decision recorded in decisions/deployment.md: which checks run in CI and where, their triggers, the IAM and token permissions, where the scripts live, and which sources stay manual and why
- [ ] #6 The post-deploy checks run automatically after every production deploy and fail the workflow on a failed verdict, with the output in the run's job summary
- [ ] #7 The environment-name audit runs in CI on its trigger and publishes its plan; applying a plan stays a human step
- [ ] #8 No CI output contains a secret value, checked by a test over the scripts' output with a canary
- [ ] #9 The delivery-session process and docs/runbooks no longer ask the human to run the automated checks by hand
- [ ] #10 The bin tests and ruff pass for the moved or changed scripts
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-29: TASK-177 folded in (human): one PR with a size exception; ACs #5 to #10 are TASK-177's ACs #1 to #6. Stays doc-11 row Z.

2026-10-29 scope line: TASK-175's production and local configuration check (pytest, configuration semantics and requirement resolution) is separate from this task's CI env-name audit; no overlap.
<!-- SECTION:NOTES:END -->
