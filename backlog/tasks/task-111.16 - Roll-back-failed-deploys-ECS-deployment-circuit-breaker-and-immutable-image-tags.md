---
id: TASK-111.16
title: >-
  Roll back failed deploys: ECS deployment circuit breaker and immutable image
  tags
status: To Do
assignee: []
created_date: '2026-10-21T20:05:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.4
references:
  - decisions/configuration.md
  - decisions/lifecycle.md
  - terraform/ecs.tf
  - .github/workflows/build_and_deploy.yml
parent_task_id: TASK-111
ordinal: 424000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The configuration and lifecycle ADRs rely on the ECS deployment circuit breaker rolling a failed deploy back to the previous task-definition revision (configuration.md "Renaming an environment name", lifecycle.md "Fail fast on deploy-coupled defects"). Production has neither half: aws_ecs_service.main has no deployment_circuit_breaker block (only CPU/memory alarm rollback), and the task definition runs sre-bot:latest while build_and_deploy.yml pushes :latest and forces a new deployment of the same revision, so the previous revision runs the same broken image. Today a deploy that fails boot hangs (old tasks keep serving under the default 100% minimum healthy), the workflow posts a failure to Slack after about 15 minutes, and recovery is a manual retag of the previous <sha>-<date> image as latest.

This lands before TASK-111.7, the first deploy that switches a slice to the renamed names, so every later 111.x deploy rolls back on its own.

Planning decides, with current sources: how the deploy workflow registers a task-definition revision pinned to the immutable <sha>-<date> tag while terraform keeps owning the task definition (for example ignore_changes on the service task_definition with the workflow rendering each revision, or terraform taking the image tag as an input), ECR tag immutability for the sha tags, and how a revert-and-redeploy or a manual rollback to a named tag works afterwards.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 aws_ecs_service.main enables deployment_circuit_breaker with rollback
- [ ] #2 Each deploy runs a task-definition revision pinned to that build's immutable image tag, so a rollback to the previous revision runs the previous image
- [ ] #3 terraform and the deploy workflow do not fight over the task definition: a tf apply after a deploy does not revert the running image
- [ ] #4 decisions/configuration.md and decisions/lifecycle.md describe the rollback that production actually has, with a dated history line
- [ ] #5 A documented manual rollback to a named image tag, for when the circuit breaker does not trigger (a deploy that boots but misbehaves)
- [ ] #6 The PR's tf plan shows only the expected service and task-definition changes; nothing is applied before review
<!-- AC:END -->
