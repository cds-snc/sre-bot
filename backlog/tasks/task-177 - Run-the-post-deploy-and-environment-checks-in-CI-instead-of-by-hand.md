---
id: TASK-177
title: Run the post-deploy and environment checks in CI instead of by hand
status: To Do
assignee: []
created_date: '2026-10-29T17:08:00Z'
updated_date: '2026-10-29T17:25:00Z'
labels:
  - deployment
  - ci
  - dev-tooling
dependencies: []
priority: medium
ordinal: 462000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
bin/deploy-checks.zsh and bin/env-checks.zsh (with app/bin/audit_env_names.py and audit_env_coverage.py) are read-only helpers the human runs by hand, and the agent reads their output from tmp/. Since the configuration migration closed (2026-10-29), they are required only for a task that changes terraform, the task definition, IAM or SSM parameters, or adds, renames or removes an environment name or secret, and for the contract step that deletes what a running revision used (configuration.md rename rule). Running them in CI would remove the manual step and make the check part of the deploy record.

Shape to decide:
- **Post-deploy checks:** they could run as a job in build_and_deploy after the deploy step, or as a workflow triggered when that run completes. They need the deploy role's read access (ECS describe, ECR, Logs Insights StartQuery and GetQueryResults), which is read-only and prints names, counts and verdicts, never values. TASK-164 (row Z) changes the verify step, so decide whether this joins or follows it.
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
- [ ] #1 A decision recorded in decisions/deployment.md: which checks run in CI and where, their triggers, the IAM and token permissions, where the scripts live, and which sources stay manual and why
- [ ] #2 The post-deploy checks run automatically after every production deploy and fail the workflow on a failed verdict, with the output in the run's job summary
- [ ] #3 The environment-name audit runs in CI on its trigger and publishes its plan; applying a plan stays a human step
- [ ] #4 No CI output contains a secret value, checked by a test over the scripts' output with a canary
- [ ] #5 The delivery-session process and docs/runbooks no longer ask the human to run the automated checks by hand
- [ ] #6 The bin tests and ruff pass for the moved or changed scripts
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-29: folded into TASK-164 (human, doc-11 row Z): its description and ACs were copied there as TASK-164 ACs #5 to #10. Archive is a human step, TASK-176 AC #6.
<!-- SECTION:NOTES:END -->
