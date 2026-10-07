---
id: TASK-140.5.2
title: >-
  Open the incident's status-updates modal with /sre incident status-update and
  draft from it with the default comms profile
status: To Do
assignee: []
created_date: '2026-10-07 14:55'
updated_date: '2026-10-07 15:21'
labels:
  - incident
dependencies:
  - TASK-140.5.1
parent_task_id: TASK-140.5
priority: high
type: feature
ordinal: 330000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Command and modal slice of TASK-140.5 (direction 2026-10-07, decisions/incident-management.md 'Where it happens'). /sre incident status-update opens the incident's status-updates modal, private to the invoker; no status-update text is ever posted to the incident channel. The modal shows the pending draft rendered by the default comms profile (scribe/comms_profile.py, modelled on GC Notify's published incident history) in EN and FR and lets the responder draft through the TASK-140.5.1 service, showing a drafting state while the model runs and then the drafted, carried-forward or pending result. Modal interactions are native Bolt listeners in scribe/entrypoints/slack.py registered through the TASK-140.2 registrar (platform-entrypoints.md rule 3); the command keeps the contract's command model and opens the view with the command's trigger id. Later layers add review and approval (TASK-140.6), the approved history (TASK-140.8) and redrafting with instructions (TASK-140.9). The same modal is later reached from the central incident modal (expansion draft).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 In an incident channel the command opens the incident's status-updates modal, visible only to the invoker, and nothing is posted to the channel
- [ ] #2 From the modal the responder can draft; the modal shows a drafting state while the model runs, then the drafted, carried-forward or pending draft in EN and FR
- [ ] #3 The profile shows stage, affected service, impact, current action, workaround and the next update time in America/Toronto as YYYY-MM-DD HH:MM ET (EN) or HE (FR), and omits the next update line when the stage is resolved
- [ ] #4 Outside an incident channel the command refuses with a localized message, and every error maps to a localized message
- [ ] #5 All bot strings are in EN and FR catalogues with matching keys
- [ ] #6 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Re-plan required. The 2026-10-07 plan (private ephemeral preview) was superseded the same day when the human moved all status-update interaction into modals. Decisions carried into the re-plan: the default comms profile lives here so the draft view and the copy-ready text match; time format YYYY-MM-DD HH:MM ET/HE in America/Toronto; resolved omits the next update line; stored EN and FR text use fixed en-US and fr-FR lookups; t() is called only in scribe/platforms/slack.py, and scribe/entrypoints/slack.py imports the label builders from there; no extra access gate (TASK-129).

Decision (human, 2026-10-07): opening the status-updates modal never starts drafting; the responder presses a Draft button, so opening the modal or browsing history never costs a model call.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-07 14:56
---
Plan approved by the human 2026-10-07 (all recommended decisions, including the 140.5.1/140.5.2 split). Clarified: nothing is ever pushed automatically; approved EN and FR text is proofread and copied by hand into whatever system the product team uses.
---

created: 2026-10-07 15:17
---
2026-10-07: the approved plan is superseded. The human moved drafting, review and history into modals (no status-update text in the incident channel), so the command now opens the status-updates modal instead of replying with an ephemeral preview. Title, description and ACs updated; re-plan before implementation.
---
<!-- COMMENTS:END -->
