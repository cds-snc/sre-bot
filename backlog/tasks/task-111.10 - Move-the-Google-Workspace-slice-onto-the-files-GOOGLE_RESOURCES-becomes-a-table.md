---
id: TASK-111.10
title: >-
  Move the Google Workspace slice onto the files; GOOGLE_RESOURCES becomes a
  table
status: To Do
assignee: []
created_date: 2026-10-20 23:25
updated_date: '2026-10-22T13:57:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.3
  - TASK-111.4
  - TASK-111.6.1
  - TASK-111.16
references:
  - decisions/configuration.md
  - https://github.com/cds-snc/sre-bot/issues/1743
parent_task_id: TASK-111
type: feature
ordinal: 416000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Google non-secret values (delegated admin email, SRE bot email, customer id in the tenant entry, retries and timeouts) move to [google_workspace]; the service-account key is read as a <SLICE>__<FIELD> secret; GOOGLE_RESOURCES becomes a [google_resources] table read by the interim GoogleResourcesConfig until its owners split it; the unread incident_drive_id is deleted.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The Google slice reads its non-secret values, the tenant included, from the files and its key from a <SLICE>__<FIELD> name
- [ ] #2 GoogleResourcesConfig reads [google_resources] from the files with the same ids production uses; GOOGLE_RESOURCES is no longer read; incident_drive_id is deleted
- [ ] #3 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
