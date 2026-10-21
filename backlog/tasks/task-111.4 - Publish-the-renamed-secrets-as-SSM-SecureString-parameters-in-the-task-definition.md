---
id: TASK-111.4
title: >-
  Publish the renamed secrets as SSM SecureString parameters in the task
  definition
status: To Do
assignee: []
created_date: '2026-10-20 23:25'
updated_date: '2026-10-20 23:36'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.1
references:
  - terraform/ecs.tf
  - terraform/templates/sre-bot.json.tpl
  - decisions/configuration.md
  - 'https://github.com/cds-snc/sre-bot/issues/1751'
parent_task_id: TASK-111
type: feature
ordinal: 410000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Terraform creates one SSM SecureString per renamed secret (placeholder value, lifecycle ignore_changes on value, so values stay out of state) and adds each under its <SLICE>__<FIELD> name to the task definition's secrets:, with the execution role's read and decrypt permissions. The running image ignores the new names; the old blob stays until the contract slice. The rename map comes from the inventory doc. Human: set every value, then apply.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every secret in the inventory's rename map has an SSM SecureString parameter and a task-definition secrets: entry under its new name; no secret value is in terraform state or the repo
- [ ] #2 The execution role can read and decrypt exactly those parameters
- [ ] #3 terraform plan shows only additions; after apply the running service is unchanged
<!-- AC:END -->
