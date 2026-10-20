---
id: TASK-24.5
title: Add the Google and Slack tenant entries
status: To Do
assignee: []
created_date: '2026-10-19 17:19'
updated_date: '2026-10-20 15:06'
labels:
  - clients
  - phase-3
  - configuration
milestone: m-3
dependencies:
  - TASK-24.3
  - TASK-24.4
  - TASK-145.5.5
references:
  - decisions/configuration.md
  - decisions/workplace-systems.md
parent_task_id: TASK-24
priority: medium
ordinal: 403000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 5 of TASK-24 (decisions/configuration.md: vendor enablement is the presence of a tenant entry; workplace-systems.md rule 3). The behaviour change of TASK-24:
- Google: GOOGLE_WORKSPACE_CUSTOMER_ID loses its my_customer default; a tenant entry (SubModel | None) in integrations/google_workspace/settings.py is present when the service-account key file is set and carries the real customer id; a present entry missing a secret or the id fails boot naming the variable.
- Slack: SLACK_TEAM_ID becomes the Slack tenant entry; SLACK_ENABLED stays the interim transport switch until TASK-112, and the transport on without a tenant entry fails boot naming the key.
- server/configured_systems.py reads the tenant entries in its Google and Slack TenantSource rows.
TASK-24.4 already deleted app/infrastructure/configuration/integrations/. GoogleResourcesConfig (also in integrations/google_workspace/settings.py) is feature data, not a vendor slice, and stays until TASK-111.
No <VENDOR>_ENABLED key. Env names unchanged (renames in TASK-111); TASK-112 moves the tenant entries into the configuration files.

Merge order (human, 2026-10-19): only after TASK-145.5.5 (Stack K layer 9, the incident cutover) has deployed and been checked, so the cutover runs on the tenant configuration production already has. The cutover is the first real consumer of the configured-systems read. Never in the same deploy.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 GOOGLE_WORKSPACE_CUSTOMER_ID has no default; the Google slice holds a tenant entry that is present only when configured and carries the real customer id
- [ ] #2 The Slack slice holds a tenant entry carrying SLACK_TEAM_ID; Slack transport on without it fails boot naming the variable
- [ ] #3 server/configured_systems.py builds the Google and Slack tenants from the tenant entries; its tests cover present, absent and invalid entries
- [ ] #4 Each vendor has exactly one vendor settings slice (GoogleResourcesConfig is feature data, tolerated until TASK-111)
- [ ] #5 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
