---
id: TASK-111.11
title: Move the AWS and OpenAI slices onto the files
status: To Do
assignee: []
created_date: '2026-10-20 23:25'
updated_date: '2026-10-20 23:35'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.3
  - TASK-111.4
  - TASK-111.6
references:
  - decisions/configuration.md
  - 'https://github.com/cds-snc/sre-bot/issues/1744'
parent_task_id: TASK-111
type: feature
ordinal: 417000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
AWS role ARNs, SSO instance ids and permission set names, retry and timeout values move to [aws]; AWS_REGION and AWS_ENDPOINT_URL_* are left to the SDK (external namespace) and stop being declared as fields; OpenAI model and limits move to [openai], the key is read as OPENAI__API_KEY; extra=forbid.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The AWS slice reads its values from the files and declares no AWS_* SDK name as a field
- [ ] #2 The OpenAI slice reads its non-secret values from the files and its key as OPENAI__API_KEY
- [ ] #3 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
