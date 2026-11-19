---
id: TASK-147.6
title: Due action-item reminders as a scheduled job behind the flag
status: To Do
assignee: []
created_date: 2026-10-13 14:00
updated_date: '2026-11-18T20:52:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-147.3
  - TASK-64
references:
  - https://github.com/cds-snc/sre-bot/issues/1711
parent_task_id: TASK-147
priority: low
type: feature
ordinal: 375000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A background job, registered by postmortem/ through the hookimpl with a lease, reminds owners of due and overdue follow_up action items, per the cadence in the design doc. Reminders query the action-item due index (TASK-147.2) with RecordQuery(index='due', partition the follow_up due bucket, sort lt now), never a table scan. Response action items are reminded by response/ (TASK-165.4) from their own partitions of the same index; core/ registers no job. Index reads may be eventually consistent, so the once-per-window guard does not depend on read-your-writes.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Reminders are sent once per due window, safe to run twice, and only while the flag is on
- [ ] #2 The job reads only the follow_up partitions of the due index and is registered by postmortem/, not core/
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-04 (TASK-145.5.7 planning, human approved): the reminders job takes its lease through the lease_ttl keyword on the feature job registry added by TASK-145.5.7.1, its TTL from the postmortem settings (reliability.md 2026-11-04).

2026-11-18 (TASK-64 split, human approved): the minimum hold is TASK-64.2; this task waits on it (through its TASK-64 dependency). Register with lease_ttl only; the hold is derived by the registry.

2026-11-18 (TASK-64.2 implemented, branch task-64.2-lease-minimum-hold, In Progress awaiting PR/merge): a leased job registered with lease_ttl now holds its lease after a short run for min(lease_ttl, interval - [scheduler] lease_hold_margin_seconds), a daily job its TTL; nothing to configure. Register only after TASK-64.2 is merged.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-18T00:01:00Z

---

2026-11-18 (human): depends on TASK-64's minimum-hold lease (reliability.md, 2026-11-18) before the reminders job registers as a leased job; a short run would otherwise post each reminder twice.

---
<!-- COMMENTS:END -->
