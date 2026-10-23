---
id: TASK-111.15
title: 'Contract: stop fetching the SSM parameters and remove the old deployment names'
status: To Do
assignee: []
created_date: 2026-10-20 23:25
updated_date: '2026-10-23T17:30:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.7
  - TASK-111.8
  - TASK-111.9
  - TASK-111.10
  - TASK-111.11
  - TASK-111.12
  - TASK-111.13
  - TASK-111.14
references:
  - app/bin/entry.sh
  - terraform/templates/sre-bot.json.tpl
  - decisions/configuration.md
  - https://github.com/cds-snc/sre-bot/issues/1748
parent_task_id: TASK-111
type: feature
ordinal: 421000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Coordinator for the contract step of the configuration move: the old deployment names and the SSM blob go once every slice reads the files (TASK-111.7 to TASK-111.14). Two PRs, because a terraform task-definition change reaches production only at the next deploy while an IAM removal applies at tf apply (decisions/deployment.md): TASK-111.15.1 stops entry.sh fetching the two blob parameters and drops the old names and secret from the task definition; TASK-111.15.2, after that deploy is verified, removes the IAM read on the blobs and the old GCP key parameter, its terraform resource and variable and the TF_VAR lines. Together they deliver TASK-54 AC #3.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 TASK-111.15.1 and TASK-111.15.2 are done
<!-- AC:END -->
