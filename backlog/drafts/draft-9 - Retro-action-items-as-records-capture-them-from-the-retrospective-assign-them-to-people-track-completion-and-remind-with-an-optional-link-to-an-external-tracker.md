---
id: DRAFT-9
title: >-
  Retro action items as records: capture them from the retrospective, assign
  them to people, track completion and remind, with an optional link to an
  external tracker
status: Draft
assignee: []
created_date: '2026-10-02 16:59'
labels:
  - incident
  - later-wave
dependencies:
  - TASK-38.8
  - TASK-83
references:
  - decisions/incident-management.md
parent_task_id: TASK-97
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
EXPANSION (after doc-2; noted 2026-10-02 as the change that would most raise the workflow's value). Today the action items of a retrospective are tables at the end of the Google Docs report. Unless the facilitator creates them in an external tracker and pastes a link into the table, they are forgotten: there is no record of whether they were done.

THIS TASK makes action items records of the incident (decisions/incident-management.md: records of truth live in app storage; the report is a collaboration space):
- an ActionItem record under the incident: text, owner (a person reference), due date, status, optional external tracker reference (system, tenant, id, vendor link: Jira is an optional target in this organization, not everyone has a seat; GitHub issues are plausible);
- capture: from the retro meeting (a modal or command during or after the retro) and, if feasible, by reading the report's action-item table once as an import, never as an ongoing source of truth;
- tracking: list open items per incident and per owner, mark done, remind owners, and surface overdue items in the stale nudge;
- the report gets the current list written back as a projection.
Decide at planning whether action items are an incident subdomain or belong with a generic follow-ups capability if a second feature needs them.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Action items are records under the incident with owner, due date and status; the report table is at most a one-time import and is otherwise a write-only projection
- [ ] #2 Open and overdue items are listed per incident and per owner and reminders go to owners through their chat home; marking done is idempotent
- [ ] #3 An external tracker link, when present, is a typed reference with system, tenant and id rendered by its adapter; no record of truth lives in the tracker
<!-- AC:END -->
