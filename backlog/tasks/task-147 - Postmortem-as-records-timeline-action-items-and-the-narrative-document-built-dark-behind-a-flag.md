---
id: TASK-147
title: >-
  Postmortem as records: timeline, action items and the narrative document,
  built dark behind a flag
status: To Do
assignee: []
created_date: '2026-10-13 13:59'
labels:
  - incident
  - features
  - slack
dependencies: []
references:
  - decisions/incident-management.md
  - decisions/workplace-systems.md
priority: high
type: feature
ordinal: 369000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The postmortem becomes a record the app owns, not a Google Doc. Today the report doc is the whole postmortem: the timeline is a doc section filled by floppy-disk reactions, and action items are a hand-kept table at the end with priority, owner and a pasted URL to an external task, with nothing tying them to GitHub Issues, no interactivity and no tracking across incidents.

Target (decisions/incident-management.md, postmortem):
- Facts (timeline, severity, roles, impact window, participants) and action items are records through the records contract. Action items carry owner, priority, due date, status and a reference to the issue that tracks the work (GitHub Issues first, as a feature-owned adapter; an issue-tracking capability only when a second tracker is needed).
- The report document keeps one job: real-time co-writing of the narrative (what happened, contributing factors, lessons). The bot creates it from the record, with the facts and action items rendered as read-only context, and stores a snapshot of the narrative in the record when the review is marked complete. One feature-owned Google Docs adapter; no documents capability until a second suite or consumer exists (workplace-systems.md rule 2).
- No in-app editor and no new editing dependency.

Delivery:
- Built dark. Every new surface is gated by one incident settings flag, default off, following the access-management pattern (a settings slice with enabled: bool = False and an env var). While it is off, users see today's behaviour exactly: the doc timeline, the doc action-items table and the current draft.
- A UX design session runs in parallel with the backend slices; slices with user-facing surfaces wait for its output.
- Turning the flag on is a rollout with an internal comms package, because it changes how people run a postmortem.

Separate from TASK-145, which rebuilds today's behaviour by surface: this epic is new behaviour and doc-2 forbids mixing a move with a behaviour change.
<!-- SECTION:DESCRIPTION:END -->
