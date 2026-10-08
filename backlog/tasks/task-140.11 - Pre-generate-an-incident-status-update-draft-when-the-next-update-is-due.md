---
id: TASK-140.11
title: >-
  Draft incident status updates periodically once a responder starts them, with
  manual pause and resume
status: To Do
assignee: []
created_date: '2026-10-07 18:52'
updated_date: '2026-10-08 00:23'
labels:
  - incident
dependencies:
  - TASK-140.6
  - TASK-140.10
parent_task_id: TASK-140
priority: low
type: feature
ordinal: 335000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Status updates for an incident always begin with a person: the first draft is made only when a responder presses Draft in the status-updates modal opened by /sre incident status-update. Today every draft is manual; NEXT_UPDATE_MINUTES (30) only sets the "next update" time printed in the text, and nothing drafts on a schedule.

A status update gives the state of things since the previous update, or since the incident began when it is the first one. The draft service already works that way: it reads the conversation since the latest update's transcript cutoff.

This task adds periodic drafting. It is opt-in and off by default for every incident: a responder turns it on with an explicit control in the status-updates modal (reachable later from the central incident modal, DRAFT-11). While it is on, the scribe prepares a fresh draft ahead of the latest approved update's next update time, so responders find a draft ready instead of starting from scratch. It also fixes stale next-update times on drafts that are reviewed long after they were made. Drafts are still only drafts: a person reviews, approves and copies every update by hand, as today.

Why pause matters: most incidents last a few hours, but the incident channel often stays open for days or weeks after the fix is deployed, for example while the retro is scheduled and held. Periodic drafting must not keep producing drafts during that time. A responder can pause it from the status-updates modal and resume it later. Pausing and resuming are always a person's action; the bot never pauses or resumes on its own. On resume a draft is prepared right away from the messages since the latest update (or since the incident began when there is none), with one model call when people have posted since. Periodic drafting also stops when:
- a responder approves a RESOLVED update, which has no next update time, so nothing is due afterwards;
- the incident is closed.

Rules that stay as they are:
- Security and unknown-flag incidents are never drafted periodically; only a manual Draft with confirmation drafts them (TASK-140.10, the service-level gate).
- Nothing is posted to the incident channel; drafts appear only in the status-updates modal (decisions/incident-management.md).
- With no new human messages since the latest update, the previous update is carried forward without a model call, so a quiet incident costs no model calls.
- An incident has at most one pending draft; a periodic run never adds a second one next to a pending draft. The store's conditional append already makes a concurrent manual Draft and periodic run converge on one draft.

Design direction (human, 2026-10-08):
- Storage: the on/paused state is per incident, so it is one more item in the incident's partition of sre_bot_incident_status_updates (PK INCIDENT#<id>, a non-UPDATE# sort key such as PERIODIC), not a field on a StatusUpdate record and not the legacy incidents table, which is retired with its adapter. Existing update queries already filter on begins_with(SK, "UPDATE#"), so listing updates is unaffected. It records on/paused, who changed it and when. Finding every incident with periodic drafting on needs a sparse GSI or a filtered scan; pick one when planning.
- Trigger: the simplest option is one interval job registered through the plugin BackgroundJobRegistry (register_interval) and run under a Tier-2 lease (jobs/scheduled_tasks.py) so only one replica runs it. Each run sweeps every incident with periodic drafting on and handles each one independently, so several incidents in parallel are covered and a failure on one does not stop the others. Model calls in one run may need bounded concurrency. The job is synchronous and the draft service is async, so the job needs an explicit event-loop boundary.
- Closed: the run checks the incident's status through incident core and skips closed incidents.

To decide when planning:
- How far ahead of the next update time the draft is prepared, and the sweep interval.
- Whether and how a responder is told a draft is ready, without posting in the incident channel.
- Whether reopening a closed incident brings back periodic drafting or needs a responder to turn it on again.

Over the single-PR size gate: decompose before implementation, for example (1) the per-incident state item and its store in incident core, (2) the Start / Pause / Resume control and state display in the status-updates modal, (3) the sweep job.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The first status update of an incident is never drafted automatically; it needs a responder's Draft press
- [ ] #2 Periodic drafting is off by default and starts for an incident only when a responder turns it on with an explicit control in the status-updates modal
- [ ] #3 While periodic drafting is on, a draft is prepared ahead of the latest approved update's next update time
- [ ] #4 One scheduled run covers every incident with periodic drafting on, runs on one replica at a time, and a failure on one incident does not stop the others
- [ ] #5 A responder can pause periodic drafting from the status-updates modal, and no periodic draft is made while it is paused
- [ ] #6 A responder can resume periodic drafting from the status-updates modal; on resume a draft is prepared from the messages since the latest update, or since the incident began when there is none
- [ ] #7 Periodic drafting is never paused or resumed automatically; the modal shows whether it is on or paused, who changed it and when
- [ ] #8 The on/paused state is stored as its own item in the incident's partition of the status-updates table, and listing an incident's status updates is unchanged
- [ ] #9 No periodic draft is made after a RESOLVED update has been approved
- [ ] #10 No periodic draft is made for a closed incident
- [ ] #11 Security and unknown-flag incidents are never drafted periodically
- [ ] #12 A periodic run with no new human messages since the latest update makes no model call
- [ ] #13 A periodic run never adds a second pending draft
- [ ] #14 No message is posted to the incident channel; the draft appears in the status-updates modal
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-08 00:17
---
2026-10-08: found while working through the Stack H workflow (layer 10). Nothing in Stack H drafts automatically, so it has nothing to pause; this is not a Stack H gap. Reshaped: status updates always start with a person; periodic drafting is opt-in for each incident and can be paused or resumed only by a person, for channels that stay open after the fix (for example while waiting for the retro).
---

created: 2026-10-08 00:23
---
2026-10-08 (human): opt-in with an explicit control, off by default; the simplest trigger that handles many incidents in parallel (a scheduled sweep job is acceptable); on resume, draft from the messages since the latest update; closing the incident stops periodic drafting. Storage: the state is a separate per-incident item in the status-updates table, not on a StatusUpdate record or the legacy incidents table.
---
<!-- COMMENTS:END -->
