---
id: TASK-111.14
title: >-
  Move the feature values production sets into the files; delete the dead atip
  and groups slices
status: To Do
assignee: []
created_date: 2026-10-20 23:25
updated_date: '2026-10-26T19:09:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.3
references:
  - decisions/configuration.md
  - https://github.com/cds-snc/sre-bot/issues/1747
parent_task_id: TASK-111
type: feature
ordinal: 420000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Production sets INCIDENT_CHANNEL, SLACK_SECURITY_USER_GROUP_ID, SLACK_NOTIFY_MGMT_USER_GROUP_ID and SRE_OPS_CHANNEL_ID. Their current slices (infrastructure/configuration/features/incident.py and sre_ops.py) become ConfigurationSlice subclasses with their own table and case_sensitive=False, and read the channel and group ids from production.toml under lower snake_case keys; their per-field aliases are dropped, since a slice on the files reads only <TABLE>__ names (bin/check_settings_key_ownership.py env-naming). Field names stay until each package move, which also renames fields, prefixes and sets extra=forbid. AtipSettings (ATIP_ANNOUNCE_CHANNEL) and GroupsFeatureSettings (GROUP_DOMAIN, GROUP_PROVIDERS) have no reader outside their own modules and are deleted with their tests and pytest env entries. The sre-bot-config values stay for the rollback image until TASK-111.15.2.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every live feature value in the inventory is read from the files under its current slice's table, with production resolving the same values
- [ ] #2 AtipSettings and GroupsFeatureSettings, their getters, exports, tests and env entries are deleted
- [ ] #3 No feature value remains needed from the SSM parameters
- [ ] #4 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
- [ ] #5 Every reader of the incident feature slice builds it at use, not at import (found 2026-10-26 in TASK-111.10.1: modules/incident/core.py:22 and modules/incident/incident.py:22 read get_incident_settings() at import, and a slice on the files fails closed before the app factory installs them); a fresh-interpreter import test proves the provider cache stays empty
<!-- AC:END -->
