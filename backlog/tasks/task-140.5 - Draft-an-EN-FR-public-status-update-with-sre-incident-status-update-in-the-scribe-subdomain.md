---
id: TASK-140.5
title: >-
  Draft an EN/FR public status update with /sre incident status-update in the
  scribe subdomain
status: To Do
assignee: []
created_date: '2026-10-06 15:57'
updated_date: '2026-10-07 15:41'
labels:
  - incident
dependencies:
  - TASK-140.3
  - TASK-140.4
parent_task_id: TASK-140
priority: high
type: feature
ordinal: 324000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Scribe use case: resolve the incident through core, read the transcript since the latest update's cutoff, and draft a structured update (stage, affected service, user impact, current action, workaround or no action needed, next update time ET) in EN and FR through the existing Summarizer with explicit structured instructions; answer parsing stays in scribe until TASK-134. Code, not the model, decides 'nothing new': no new human messages since the cutoff gives the prior update carried forward as 'no new information, next update by' with no model call; re-running while a draft is pending with nothing new returns that draft. Stages only move forward. The draft is stored as a draft record and shown privately to the responder.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 With new channel activity, one model call produces EN and FR drafts with every field, stored as a draft record and shown only to the invoker
- [x] #2 With no new human messages since the latest update, no model call is made and the prior update is carried forward with the no-new-information wording
- [x] #3 Running it twice with nothing new returns the same pending draft and stores nothing new
- [x] #4 A drafted stage earlier than the latest approved stage is raised to it
- [ ] #5 Outside an incident channel the command refuses with a localized message; all bot strings are in EN and FR catalogues
- [ ] #6 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Coordinator. Split on 2026-10-07 at the single-PR size gate (~14 files, ~520 LOC as one PR) into TASK-140.5.1 (scribe service: draft, carry forward, pending, stage floor, bot flag) and TASK-140.5.2 (/sre incident status-update opening the status-updates modal, drafting from it, and the default comms profile). Each is one Stack H layer and PR. The same day all status-update interaction moved into modals (decisions/incident-management.md), so 'shown only to the invoker' means a private modal, never a channel or ephemeral post. The ACs here are checked as the subtasks verify them: AC1 by 140.5.1 AC1 + 140.5.2 AC1-AC2; AC2 by 140.5.1 AC2; AC3 by 140.5.1 AC3; AC4 by 140.5.1 AC4; AC5 by 140.5.2 AC4-AC5; AC6 by both gates.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-06 (TASK-140.1): the model fills structured fields only; text shown to the responder is rendered by the default comms profile (decisions/incident-management.md, External status updates), never by the prompt. The scribe Slack entry point uses native Bolt objects; the service imports no Slack SDK (platform-entrypoints.md rule 3).

2026-10-07 (TASK-140.4): core/api.py exports StatusUpdate (+StatusUpdateText, StatusUpdateStage in forward declaration order, StatusUpdateState with can_move_to), StatusUpdateStore (append, latest, list_for_incident newest first, transition(update, expected_state=...)) and get_status_update_store(). The caller numbers updates: latest().sequence + 1, or 1; a concurrent draft at the same sequence returns PERMANENT_ERROR STATUS_UPDATE_CONFLICT (decide retry vs refusal here). transcript_fingerprint is an opaque string this task defines. author/approver are platform user ids. Tests inject packages.incident.core.adapters.in_memory.InMemoryStatusUpdateStore. Terraform sre_bot_incident_status_updates and its IAM grant must be applied before deploy.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-07 14:56
---
Plan approved by the human 2026-10-07 (all recommended decisions, including the 140.5.1/140.5.2 split). Clarified: nothing is ever pushed automatically; approved EN and FR text is proofread and copied by hand into whatever system the product team uses.
---
<!-- COMMENTS:END -->
