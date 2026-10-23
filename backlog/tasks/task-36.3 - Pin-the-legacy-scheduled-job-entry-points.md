---
id: TASK-36.3
title: Pin the legacy scheduled-job entry points
status: To Do
assignee: []
created_date: 2026-09-28 14:36
updated_date: '2026-10-23T17:09:00Z'
labels:
  - migration
  - testing
milestone: m-5
dependencies:
  - TASK-36
references:
  - decisions/testing.md
  - decisions/migration.md
  - https://github.com/cds-snc/sre-bot/issues/1613
parent_task_id: TASK-36
priority: high
ordinal: 287000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Pin the 5 scheduled-job rows of the TASK-36 inventory (app/tests/integration/legacy_surface/INVENTORY.md, 'Scheduled job entry points'): the 3 legacy jobs scheduled in jobs/scheduled_tasks.py init() (provision_aws_identity_center over modules.aws.identity_center, notify_stale_incident_channels from modules.incident, and spending.execute_spending_data_update_job from modules.aws.spending) and the 2 plugin-registered jobs (access_sync_reconciliation and oncall_sync, registered through the register_background_jobs hookimpl). They are the before/after check for the TASK-52 scheduler move and the TASK-145.9 and TASK-88 rebuilds. Invoke each job's entry point directly with faked integrations and assert on its observable effects; do not start the scheduler. The host-owned Tier-1 jobs (scheduler_heartbeat, integration_healthchecks) are not inventory rows.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each legacy job entry point in the TASK-36 inventory has a pinning test with faked integrations
- [ ] #2 Tests live in app/tests/integration/legacy_surface/ and run in the normal gate
- [ ] #3 The TASK-36 inventory marks each job row pinned by this task
- [ ] #4 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
