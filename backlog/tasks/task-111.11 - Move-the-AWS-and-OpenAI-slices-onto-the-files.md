---
id: TASK-111.11
title: Move the AWS and OpenAI slices onto the files
status: To Do
assignee: []
created_date: 2026-10-20 23:25
updated_date: '2026-10-26T22:22:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.3
  - TASK-111.4
  - TASK-111.6.2
  - TASK-111.16
  - TASK-111.17
references:
  - decisions/configuration.md
  - https://github.com/cds-snc/sre-bot/issues/1744
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
- [ ] #4 Both subtasks (TASK-111.11.1 AWS, TASK-111.11.2 OpenAI) are Done and every old AWS_* and OPENAI_* name they retire is unread
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
COORDINATOR (2026-10-26). The gate trips on one PR: two vendor slices (AWS 12 files ~230 prod LOC plus 3 config files and helpers; OpenAI ~7 files ~100 LOC), two sets of production-value merge gates and post checks, and both edit the same pyproject pytest-env block, bin/audit_env_names.py HINTS, bin/deploy-checks.zsh and doc-14 rows. Split:
1. TASK-111.11.1 AWS slice (deps 111.6.2, 111.3). No terraform expand needed; AWS_REGION / AWS_ENDPOINT_URL_DYNAMODB left to the SDK; role ARNs, SSO ids and permission-set names public (plan has the rationale and the iam.tf guard).
2. TASK-111.11.2 OpenAI slice (deps 111.11.1, 111.4). No terraform expand needed: terraform/ssm.tf:25 already creates and injects /sre-bot/OPENAI__API_KEY (111.4); only its value must be put-parameter'd and MATCH-checked.
Ordering: 111.11.2 after 111.11.1 is merged and deployed (shared files, one deploy-checks edit at a time). Old OPENAI_* / AWS_* blob lines stay inert until 111.15.1/111.15.2. ACs 1-3 map: #1 -> 111.11.1, #2 -> 111.11.2, #3 -> both; #4 closes the parent.
<!-- SECTION:PLAN:END -->
