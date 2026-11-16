---
id: TASK-145.7.8
title: 'Switch the legacy upgrade job on in production: dry run, then apply'
status: To Do
assignee: []
created_date: '2026-11-09T19:06:00Z'
updated_date: '2026-11-10T16:37:00Z'
labels:
  - incident
  - config
dependencies:
  - TASK-145.7.4
  - TASK-145.8.3
  - TASK-145.8.4
  - TASK-145.8.5
  - TASK-145.8.6
references:
  - decisions/incident-management.md
  - app/features/incident/README.md
parent_task_id: TASK-145.7
priority: medium
type: chore
ordinal: 512000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L8. After the TASK-145.8 cutovers have deployed: one config PR sets [incident_response] upgrade_mode = "dry_run" in production.toml; the human reads the report (blockers listed per Migration rule 7, already_upgraded expected 0); a second PR sets "apply"; the human records the applied report. Then mode back to off or kept for the rerun per the README.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The dry-run and apply reports are recorded in the notes with zero blockers left (checks the production part of parent AC #13)
- [ ] #2 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-10 (human question, answered from the program plan): when the job may run.
- dry_run writes nothing: safe in any environment once L2b (TASK-145.7.4, #1844) is deployed; running it earlier than this task's config PR only surfaces blockers sooner.
- apply waits on: L2b deployed (before it the job raises items to version 1 without a binding); L5r (TASK-145.8.2) rollback guard deployed; L6a-L7b (TASK-145.8.3-145.8.6) deployed and soaked (TASK-145.7 OQ18: the legacy Incident model, extra=forbid, cannot read an upgraded item, so a reader cutover reverted after apply breaks; after apply a regression is fixed forward).
- No need to wait for the whole stack: the stored shape is versioned (record_version); a later shape change bumps the version with its own upgrade step while readers accept both; the job reruns after TASK-145.12.2 anyway (README Rerun rule), and the rebuilt writers upgrade each item they touch from L3/L6a on regardless of the job.
- The L5 re-plan (TASK-145.7.7 R4-R6, 2026-11-10) does not change what the job writes: legacy items always have a channel, so they keep the conversation copy, one primary chat binding and record_version 2.
<!-- SECTION:NOTES:END -->
