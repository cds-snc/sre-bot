---
id: TASK-111.15.1
title: >-
  Contract 1: entry.sh stops fetching SSM; task definition drops the old names
  and secret
status: To Do
assignee: []
created_date: '2026-10-22T13:57:00Z'
updated_date: '2026-10-28T16:50:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.7
  - TASK-111.8
  - TASK-111.9
  - TASK-111.10
  - TASK-111.10.3
  - TASK-111.11
  - TASK-111.12
  - TASK-111.13
  - TASK-111.14
  - TASK-111.16
references:
  - app/bin/entry.sh
  - terraform/templates/sre-bot.json.tpl
  - decisions/configuration.md
  - decisions/deployment.md
  - docs/runbooks/roll-back-a-deployment.md
  - https://github.com/cds-snc/sre-bot/issues/1778
parent_task_id: TASK-111.15
priority: medium
type: feature
ordinal: 429000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
First half of TASK-111.15. app/bin/entry.sh no longer fetches sre-bot-config or sre-bot-config-infrastructure, and the task definition drops BACKEND_URL, CORS_ALLOWED_ORIGINS, SLACK__COMMAND_PREFIX and the old GCP_SRE_SERVICE_ACCOUNT_KEY_FILE secret. Dropping CORS_ALLOWED_ORIGINS removes its entry in terraform/templates/sre-bot.json.tpl, the cors_allowed_origins variable (terraform/variables.tf) and its template argument in terraform/ecs.tf. The IAM read on the two blob parameters stays until TASK-111.15.2, so a task from the previous revision (which still fetches them) keeps working through the deploy and any rollback. Under decisions/deployment.md a terraform task-definition change reaches production only at the next deploy: after merge, tf_apply registers the revision, then a workflow_dispatch deploy runs the current image on it and the running revision is checked (runbook: redeploy the current image after a terraform task-definition change).

The declare-path incident values (announcement channel, security and Notify management group ids) move from the legacy IncidentFeatureSettings (infrastructure/configuration/features/incident.py) to the incident response slice in features/incident/common/settings.py, which becomes the one owner of their table; modules/incident reads them from there, and infrastructure/configuration/features/incident.py is deleted. Values unchanged; the move standardises the keys TASK-111.14 froze ([incident] incident_channel, slack_security_user_group_id, slack_notify_mgmt_user_group_id repeat their table and carry vendor words): lower snake_case keys that do not repeat the table (decisions/configuration.md), fields renamed to match, extra=forbid, base.toml and production.toml renamed in the same PR, HINTS and doc-14 updated for the renamed INCIDENT__* override names (decisions/incident-management.md, Settings).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 entry.sh fetches no SSM parameter and the image starts uvicorn directly or through a minimal entrypoint
- [ ] #2 The task definition template sets only platform-provided env names and the renamed secrets
- [ ] #3 IAM grants are unchanged in this PR
- [ ] #4 The CI workflow and pytest env set no unread variable
- [ ] #5 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
- [ ] #6 After merge and a dispatch deploy, describe-task-definition of the running revision shows only platform-provided names and the renamed secrets (output in the notes)
- [ ] #7 IncidentFeatureSettings is gone: the incident response slice in features/incident/common/settings.py owns [incident] with standardised keys (lower snake_case, no table-name repeat), renamed fields and extra=forbid; base.toml and production.toml keys renamed with values unchanged, and modules/incident reads it
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Human: tf_apply succeeded, the dispatch deploy was verified, and the roll-back runbook Verify checklist passed
<!-- DOD:END -->
