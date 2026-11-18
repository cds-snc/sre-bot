---
id: TASK-145.9.2
title: Cut over floppy-disk timeline capture and the stale-channel nudge
status: To Do
assignee: []
created_date: '2026-11-09T19:06:00Z'
updated_date: '2026-11-18T21:26:00Z'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.9.1
  - TASK-145.8.1
  - TASK-145.8.5
  - TASK-145.7.10
  - TASK-145.8.5.2
  - TASK-64
references:
  - decisions/incident-management.md
parent_task_id: TASK-145.9
priority: medium
type: feature
ordinal: 517000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L10b. Reaction handlers registered by incident.response write timeline records through TASK-145.8's timeline store and report entries through L10a; the stale nudge registered by response's background-job hookimpl, posting the prefixed archive id; jobs/scheduled_tasks.py no longer imports it; incident_document.py deleted when no caller remains; the 36.1.5 pins rewired.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The capture and nudge pins pass with assertions unchanged; captured entries keep the same key on re-capture (checks parent ACs #1, #2, #5, #7, #8)
- [ ] #2 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
- [ ] #3 The stale notice's ignore button moves to incident.response (moved from TASK-145.8, TASK-145.8.5 OQ3): registered with the archive_channel alias scoped to the ignore value (TASK-145.8.5.2); new notices are Block Kit with one action id per button owner (incident.response archive and ignore, incident.postmortem schedule)
- [ ] #4 The report's timeline document read returns a classified OperationResult (a missing document is NOT_FOUND, a refused read UNAUTHORIZED, a timeout TIMEOUT) instead of collapsing every failure to DOCUMENT_UNREADABLE; the reacting user's notice is unchanged and decisions/incident-management.md's report-errors line drops the timeline exception (TASK-145.9.1 OQ4, human 2026-11-18)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-10: captured_entry_id is built here (uuid5 under TIMELINE_NAMESPACE in core/adapters/timeline_items.py from TASK-145.8.1); captured entries are TimelineEntry kind message with source_message, appended through TimelineStore.append.

2026-11-10 (TASK-145.8.7 planning): TimelineStore stays sync after TASK-145.8.7 because only the store bodies call it; when this task (or 145.9.1) gives it an async consumer, it becomes async def with its Record adapter offloading (decisions/outbound-clients.md async-port rule).

2026-11-16 (human, TASK-145.8.5.2 OQ7): claiming the ignore value makes the ignore branch of archive_channel_action unreachable; this task deletes that branch.

2026-11-16 (human, #1858 Q1-Q5 approved; production fix shipped without a task): the legacy capture now (a) captures the exact reacted-to message through reactions.get, a thread reply included, never its parent; (b) keys report entries by the Slack message (channel + full ts from the permalink), so same-second messages are distinct and removal no longer rebuilds the entry from the current profile and text; (c) posts a bilingual ephemeral notice to the reacting user when a save or removal fails or cannot be confirmed (keys in app/locales/incident.*.yml). #1858 pins (a) and (c) in tests/integration/legacy_surface. Scope for this task: the rebuilt capture keeps (a)-(c) with those pins passing unchanged; the notice keys move into incident_response's catalogue; captured_entry_id (uuid5 over system, tenant, conversation, message id) matches the report entry identity of (b).

2026-11-18 (TASK-64 split, human approved): the minimum hold is TASK-64.2; this task waits on it (through its TASK-64 dependency). Register with lease_ttl only; the hold is derived by the registry.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-16T15:51:00Z

---

2026-11-16 (human, TASK-145.8.4 OQ4): decisions/migration.md step 4 amended (rides with L6b): a cutover changes behaviour only as a named change of kind (a) legacy bug no pin asserts, (b) behaviour an accepted end-state ADR replaces, (c) expired deprecated form after a usage check, (d) retired surface; additions only by an explicit plan ruling. At planning, classify each behaviour change of this task by kind, pin it (test_legacy_only_* or edited pin citing the ruling) and list it in the PR body.

---

created: 2026-11-16T19:34:00Z

---

2026-11-16 (human, TASK-145.8.5 OQ3): the archive_channel callback is split by button value through value-scoped aliases (TASK-145.8.5.2): archive is TASK-145.8.5.3's, ignore is this task's (the nudge's delay, which rewrites the notice), schedule_retro is TASK-145.10's. Until TASK-145.10 lands, schedule_retro falls through to the legacy listener.

---

created: 2026-11-17T19:03:00Z

---

2026-11-17 (human, TASK-145.8.5.3 OQ2 and OQ6): (1) the rebuilt stale notice and the ignore reply follow the new i18n.md line: a request whose payload names no locale (block actions carry none) is answered in English and French, each from its catalogue. (2) /sre dev stale (modules/dev/platforms/slack.py handle_stale_dev_command) posts its own copy of the legacy notice with archive_channel and has no other owner: this task repoints it to the rebuilt notice's renderer or deletes it, before TASK-145.13 (AC #10) removes the value-scoped aliases.

---

created: 2026-11-18T00:01:00Z

---

2026-11-18 (human): depends on TASK-64's minimum-hold lease (reliability.md, 2026-11-18) before the stale-channel nudge registers as a leased job; a short run would otherwise nudge twice, once from each replica.

---
<!-- COMMENTS:END -->
