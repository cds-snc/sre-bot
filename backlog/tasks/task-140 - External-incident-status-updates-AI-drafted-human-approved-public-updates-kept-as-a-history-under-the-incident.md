---
id: TASK-140
title: >-
  External incident status updates: AI-drafted, human-approved public updates
  kept as a history under the incident
status: To Do
assignee: []
created_date: '2026-10-06 15:57'
updated_date: '2026-10-09 13:01'
labels:
  - incident
  - features
  - slack
dependencies: []
references:
  - decisions/incident-management.md
  - decisions/interaction-toolkits.md
  - decisions/platform-entrypoints.md
  - decisions/transport-slack.md
priority: high
type: feature
ordinal: 319000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Teams want a current public status update instead of the unused legacy /sre incident status and updates commands (DynamoDB shows two incidents ever used updates). The scribe subdomain drafts a structured EN/FR update from the incident channel; a responder edits and approves it in a modal; every update is stored as its own record under the incident's id (the legacy incidents table UUID), never as the incident_updates list attribute. Running it again with nothing new reuses the prior update as a 'no new information, next update by' message, decided by code and not by the model. The first slice publishes copy-ready bilingual text; status-page adapters come later behind a StatusPagePublisher interface.

Conventions (research 2026-10-06): stages Investigating / Identified / Monitoring / Resolved (FR: Enquête en cours / Problème identifié / Sous surveillance / Résolu); fields: stage, affected service by public name, user-visible impact, what we are doing (no root-cause speculation), workaround or 'no action needed', next update time in ET with date; plain language per Canada.ca style and GC Notify's published wording; update about every 30 minutes, never silent. AI drafting with human approval matches FireHydrant/Rootly practice; security incidents need a second confirmation.

Decisions (human, 2026-10-06): modal approval over a minimal Slack interaction contract; copy-ready text as the first publish target; records keyed by the existing incident UUID, resolved from the channel through core, never by channel; command /sre incident status-update; legacy updates retired after this ships, legacy status (internal lifecycle state) stays with TASK-38.4. Public stage and internal lifecycle status are distinct vocabularies.

Decisions (human, 2026-10-07): status updates never reach the incident channel; drafting, review, redrafting with reviewer instructions and the approved history all live in modals private to the responder, opened by /sre incident status-update and later from the central incident modal (DRAFT-11). Approved text is proofread and copied by hand; nothing is pushed automatically. Slices: 140.5 (140.5.1 service, 140.5.2 status-updates modal), 140.6 review and approve, 140.8 history, 140.9 redraft with instructions, then 140.7 retires the legacy command.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every subtask is done
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-06 (TASK-140.1): the records now hold the design. Slack interactions follow platform-entrypoints.md rule 3 (business code platform-neutral; a feature's entrypoints/slack.py uses native Bolt listeners; the host owns registration only). StatusPagePublisher and its copy-ready adapter live in scribe/; a comms profile renders the stored fields, with one default modelled on GC Notify's published incident history; per-product profiles and status-page adapters are DRAFT-10. The command model is reassessed in TASK-141.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-09 13:01
---
2026-10-09: the AI-first framing of this task (AI-drafted, human-approved) is superseded by TASK-144 (human-first: a responder writes the update, AI assists inside the form when configured). The shipped slices 140.1 to 140.10 stay as history; 140.7 is merged (#1564) and waits for a human to move it to Done; 140.11 and 140.12 stay open here because the CLI cannot re-parent them, and are re-read against TASK-144 (comments added by TASK-144.2). Nothing else from this task is open.
---
<!-- COMMENTS:END -->
