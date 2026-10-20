---
id: TASK-145.5.7
title: >-
  Incident legacy upgrade job: upgrade every item without record_version to the
  end-state shape, the open index included
status: To Do
assignee: []
created_date: '2026-10-14 23:10'
updated_date: '2026-10-20 18:36'
labels:
  - incident
  - features
  - records
  - reliability
dependencies:
  - TASK-145.5.2
  - TASK-145.5.8
  - TASK-27.5
  - TASK-157
references:
  - decisions/reliability.md
  - decisions/lifecycle.md
  - 'https://12factor.net/admin-processes'
  - >-
    https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-indexes-general-sparse-indexes.html
  - 'https://github.com/cds-snc/sre-bot/issues/1696'
parent_task_id: TASK-145.5
priority: medium
type: task
ordinal: 393000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 12 of Stack K (handoff doc-13). The single legacy data upgrade for the incidents table. Legacy items carry legacy attribute names, bare reference strings, free-text status, no security_incident, no open_bucket or opened_at and no record_version. This job upgrades them all to the end-state shape; it follows the shared legacy backfill rule set in decisions/incident-management.md (Migration).

WHAT IT DOES
- Reads the whole incidents table with TASK-27.5's bounded full-table read and selects the items without record_version.
- Runs each through the pure upgrade function features/incident/core/adapters/legacy_items.py (TASK-145.5.8; the same function the read bridge uses), then writes the end-state attributes and the nested reference maps (conversation, report, video_call, postmortem_meeting, external_case, source_alert, each {system, tenant, vendor_id, url}), sets open_bucket OPEN and opened_at (fixed-width ISO-8601 UTC of the legacy created_at) for incidents not Closed, and stamps record_version 1, in one guarded RecordStore.update per item (guarded on record_version absent), so reruns are no-ops and a concurrent writer wins.
- RECORD_VERSION and OPEN_BUCKET come from core/store.py (TASK-145.5.4). opened_at and every stored time use the stored-time formatter format_stored_time in core/adapters/incident_items.py, added by TASK-145.5.8.
- Legacy attributes are kept on the item; TASK-145.13 leaves them in place (no strip pass). channel_id stays as the by_channel key.
- Status matches the five IncidentStatus values ignoring case and surrounding whitespace (production: 30 `closed` and 1 `reviewed` lowercase of 323 items). Any other value fails the run before apply writes anything, with the list of incident ids and stored values, for a manual fix in the table.
- A missing legacy security flag becomes security_incident false.

RUNNER (human, 2026-10-15; the shared runner pattern)
- An in-app leased Tier-2 job registered by the incident plugin, reached through the ServiceScopeOpener (TASK-145.5.2).
- A mode setting: off (default, the job is not registered), dry_run, apply.
- One structured report event per run with counts (scanned, already_upgraded, to_upgrade, upgraded, guard_lost, unmatched_status, pending).
- No bin script or management command: none can run in production (no ECS Exec, no RunTask).

TIMING
- Run per environment, dry run then apply, after TASK-145.8 deploys (the modal writers are the last legacy writers apart from the sheet import) and before TASK-145.9 merges (the stale-channel nudge is the first reader of the open index).
- Run again, dry run then apply, after TASK-145.12 removes the Google Sheet import (create_missing_incidents), which creates legacy items until then.
- TASK-145.13 deletes the job and legacy_items.py once a production run reports nothing pending.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The job ships with mode off (not registered); dry_run reports the counts and writes nothing; apply upgrades every item without record_version through legacy_items.py to the end-state attributes and reference maps and stamps record_version 1 (tested against InMemoryRecordStore over each legacy item shape)
- [ ] #2 Incidents not Closed get open_bucket OPEN and opened_at; Closed incidents get neither; a missing legacy security flag is written as security_incident false
- [ ] #3 Every write is a guarded RecordStore.update, so reruns change nothing and a concurrent writer wins (guard_lost counted); legacy attributes stay on the item
- [ ] #4 A status outside the five IncidentStatus values (ignoring case and surrounding whitespace) fails the run before any apply write, reporting the incident ids and stored values
- [ ] #5 One structured report event per run carries the counts; the run procedure (per environment, dry run then apply, after TASK-145.8 deploys and again after TASK-145.12) and the removal owner (TASK-145.13) are recorded; running it is a precondition of TASK-145.9, not of this task
- [ ] #6 The whole-table read is RecordStore.read_all with max_items from the documented incident core setting INCIDENT_CORE__FULL_READ_MAX_ITEMS (features/incident/common/settings.py, default 10000); past the cap the run fails before any apply write and the report names the cap (decisions/cloud-portability.md contract 4, whole-table reads)
- [ ] #7 Before apply writes anything, the job calls Slack auth.test and checks that its enterprise_id (when SLACK_ENTERPRISE_ID is set) or team_id equals the configured Slack tenant; a mismatch or a failed call fails the run with the expected and received ids, and dry_run reports the same check (decisions/workplace-systems.md rule 3, TASK-157)
- [ ] #8 IncidentStore.find_by_conversation logs a warning naming the stored and requested tenants for each by_channel candidate it drops for its tenant, never dropping one silently (decisions/incident-management.md, Stored form)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-15: scope widened from the open-index reconcile to the single incident legacy upgrade job (human, Stack K layer 5 planning). Needs re-planning at pickup, with a size-gate re-check then.

2026-10-20 (SLACK_TEAM_ID review): this job is the first writer to persist tenants without a request, so it verifies the configured tenant with auth.test before apply (AC7) and owns the lookup warning (AC8). Depends on TASK-157 (inbound tenant guard).
<!-- SECTION:NOTES:END -->
