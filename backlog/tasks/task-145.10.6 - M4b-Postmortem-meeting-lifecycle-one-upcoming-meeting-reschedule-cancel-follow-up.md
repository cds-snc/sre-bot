---
id: TASK-145.10.6
title: >-
  M4b Postmortem meeting lifecycle: one upcoming meeting, reschedule, cancel,
  follow-up
status: To Do
assignee: []
created_date: '2026-11-20T22:05:00Z'
updated_date: '2026-11-25T15:18:00Z'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.10.5
parent_task_id: TASK-145.10
priority: medium
ordinal: 537000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack M layer M4b. One upcoming meeting per incident, claimed before booking (per-incident IdempotencyStore claim, as the TASK-145.7.5 I1-I5 rules). The calendar owns the time, the record holds only the reference; state is derived, never stored: none, upcoming (event end in the future), ended, missing (event deleted: reference cleared, logged, schedule offered). The command and nudge button show the scheduled view (time in viewer locale, link, attendees; Reschedule, Cancel, Close) when a meeting exists. Reschedule patches the same event (sendUpdates=all; next free slot or picked date and time; attendees editable); cancel confirms, deletes with notifications and clears the reference; an ended meeting is never patched or deleted and a follow-up session replaces the reference. System timeline kinds postmortem_meeting_scheduled, _rescheduled, _cancelled; bilingual channel posts; audit events. Merges soon after M3 (hand edits on the shared calendar are risky). ADR: incident-management.md Postmortem paragraph and :44 line. Branch stack-m/145.10.6-meeting-lifecycle.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 At most one upcoming meeting per incident, enforced by a claim before booking; state none/upcoming/ended/missing derived from the event
- [ ] #2 Reschedule patches the same event; cancel deletes and clears the reference; ended meetings are never patched or deleted; a follow-up replaces the reference
- [ ] #3 Scheduled view with Reschedule, Cancel and Close; timeline kinds and bilingual posts; role check from M4a applied
- [ ] #4 incident-management.md Postmortem paragraph and :44 line amended; ruff, mypy, the four make checks and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Grounded outline (plan in full at pickup; merge soon after M3). Depends on M4a.
Grounding: MeetingScheduler get/patch/delete from M2a; IncidentStore.set_reference and the new clear path (check store.py:275 for removal support; add if absent); idempotency claim pattern from TASK-145.7.5 I1-I5 (contracts/coordination ConditionalWriteStore facades); timeline store (core TimelineStore, entries kinds) for system kinds postmortem_meeting_scheduled/_rescheduled/_cancelled; M3 entrypoints and views; M4a role check.
Steps: derived state (none/upcoming/ended/missing; missing clears the reference, logs, offers schedule); claim before booking; scheduled view (viewer-locale time, link, attendees; Reschedule, Cancel, Close) for command and nudge button; reschedule = patch same event with sendUpdates=all (next free slot or picked date/time; attendees editable); cancel = confirm, delete with notifications, clear reference; ended is never patched or deleted, follow-up replaces the reference; timeline entries, bilingual channel posts, audit events; ADR Postmortem paragraph and :44 line. Tests: claim race, each state, patch/delete failures classified, role refusals. Size likely over the gate: split at pickup (service+state vs views) if so. Blast radius: calendar writes on a shared calendar; revert restores M3 behaviour but leaves events created; hand edits on the shared calendar are risky, hence merge soon after M3.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-25T15:18:00Z

---

2026-11-25 (TASK-145.10.2 rulings, OQ3): the MeetingRequest.idempotency_key passed to create is stable across re-claims of one booking attempt, e.g. <incident_id>:postmortem:<booking generation>, the generation advancing only after a cancel or a missing event. Never the ConditionalWriteStore claim token: it is issued per NEW claim, so a re-claim after a timed-out insert would get a new key and book a second event. Patch is one attempt; If-Match with get's etag is its end state (TASK-87.1).

---
<!-- COMMENTS:END -->
