---
id: TASK-111.15
title: 'Contract: stop fetching the SSM parameters and remove the old deployment names'
status: To Do
assignee: []
created_date: '2026-10-20 23:25'
updated_date: '2026-10-21 17:07'
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
  - 'https://github.com/cds-snc/sre-bot/issues/1748'
parent_task_id: TASK-111
type: feature
ordinal: 421000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Delivers TASK-54 AC3: app/bin/entry.sh no longer fetches sre-bot-config and sre-bot-config-infrastructure; the task definition drops BACKEND_URL, CORS_ALLOWED_ORIGINS, SLACK__COMMAND_PREFIX and the old GCP_SRE_SERVICE_ACCOUNT_KEY_FILE secret; the IAM read on the two blob parameters and the old gcp_sre_service_account_key parameter goes, with that parameter's terraform resource and variable (its value sits in terraform state today) and the TF_VAR_gcp_sre_service_account_key lines in tf_plan.yml and tf_apply.yml; the CI workflow drops the unread secrets. Human: once the deploy is verified, delete both SSM parameters and the GCP_SRE_SERVICE_ACCOUNT_KEY_FILE GitHub secret. TASK-54 is set to Done in this PR.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 entry.sh fetches no SSM parameter and the image starts uvicorn directly or through a minimal entrypoint
- [ ] #2 The task definition sets only platform-provided env names and the renamed secrets
- [ ] #3 The IAM policy no longer grants read on sre-bot-config or sre-bot-config-infrastructure
- [ ] #4 The CI workflow and pytest env set no unread variable
- [ ] #5 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
- [ ] #6 TASK-54's AC3 is checked and TASK-54 is set to Done in this PR
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Both SSM parameters are deleted after the deploy is verified (human)
<!-- DOD:END -->
