---
id: TASK-164
title: Deploy verify step waits for the ECS rollout to finish its alarm bake time
status: To Do
assignee: []
created_date: '2026-10-23T18:47:00Z'
labels:
  - deployment
  - ci
milestone: m-7
dependencies: []
type: task
ordinal: 436000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
With deployment alarms enabled, ECS keeps a rolling deployment IN_PROGRESS through the alarm bake time after the service is stable. The deploy action's waiter returns at steady state, so 'Verify the deployed revision' sees IN_PROGRESS and fails the job, posting a false failure, although the rollout completes moments later. The verify step polls the service until the PRIMARY deployment leaves IN_PROGRESS, inside the existing 15-minute budget: COMPLETED on the registered revision passes; FAILED, a rollback to another revision or the timeout fails. Workflow and its verify script only; no terraform change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The verify step passes when the PRIMARY deployment reaches COMPLETED on the registered revision within the budget, after any number of IN_PROGRESS polls
- [ ] #2 It fails, naming the state and reason, on FAILED, on a PRIMARY deployment of another revision, or when the budget runs out
- [ ] #3 verify-ecs-deployment.sh tests cover IN_PROGRESS then COMPLETED, FAILED, a rolled-back revision and the timeout
- [ ] #4 decisions/deployment.md states that a deploy is verified only once ECS reports the rollout complete, bake time included
<!-- AC:END -->
