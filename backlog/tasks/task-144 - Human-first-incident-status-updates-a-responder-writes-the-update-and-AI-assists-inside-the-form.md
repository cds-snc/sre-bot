---
id: TASK-144
title: >-
  Human-first incident status updates: a responder writes the update and AI
  assists inside the form
status: To Do
assignee: []
created_date: '2026-10-09 12:51'
updated_date: '2026-10-09 12:52'
labels:
  - incident
  - features
  - slack
dependencies: []
references:
  - decisions/incident-management.md
  - decisions/feature-packages.md
  - decisions/platform-entrypoints.md
  - decisions/transport-slack.md
priority: high
type: feature
ordinal: 344000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
COORDINATOR: contains no implementation. Replaces the AI-first framing of TASK-140 (whose shipped slices stay as history; TASK-140.11 and TASK-140.12 remain its open children and are re-read against this task).

DIRECTION (human, 2026-10-09): TASK-140 started from AI drafting and made the review form the edit step. The intended experience is the other way round. /sre incident status-update opens the status-updates modal; it shows the pending draft when there is one (who wrote it, how, when) or a "New update" button, and the approved history. "New update" opens the form prefilled from the latest approved update (blank at the first stage when there is none); the responder edits the fields, saves the draft or approves it. Inside the form, "Draft with AI" is shown only when text generation is configured: it applies the security confirmation for a security or unknown-flag incident, then code decides (no new human messages since the latest approved update's transcript cutoff means no model call and the carried-forward wording; otherwise one model call fills the fields), and "redraft with instructions" is the same button with instructions typed. Approve, copy-ready text, history and the published toggle are unchanged. Nothing is posted to the incident conversation.

STARTING POINT (main at af6a316e, 2026-10-09): #1566 "Let responders write status updates by hand" is merged. It added a Write it myself button beside Draft in the overview, a manual mode in draft_status_update (prefilled draft, no model call, no security gate, MANUAL outcome), _prefill_fields and _holds, UnavailableTextGenerator with TEXT_GENERATION_UNAVAILABLE when the OpenAI settings do not load, and build_review_view(with_redraft=False). The modal is still AI-first; this task turns it around and reuses those pieces. #1564 retired the legacy /sre incident updates command (TASK-140.7), so nothing legacy remains in scope here.

LEAST REWORK (human, 2026-10-09): everything ships in place in packages/incident/scribe and packages/incident/core, with the interim DynamoDB StatusUpdateStore adapter. Later rework is mechanical: TASK-124.5 renames the paths, TASK-108/TASK-109 swap the inside of the one adapter for the storage contract, TASK-25.10 replaces the AI-availability predicate with the text-generation capability's own signal. No new Protocol method: a saved or AI-filled draft is appended as the next DRAFT record, as a redraft already is.

ASSUMPTIONS IN FORCE (stated 2026-10-09; change them here before the slice that depends on them starts):
- one pending draft per incident, as today; "New update" is hidden while one is pending (TASK-140.11 keeps "human drafts win");
- the drafting window starts at the latest approved update's transcript cutoff, as today; a pending draft does not move it;
- a new hand-written draft is prefilled from the latest approved update's stage and fields, blank at the first stage otherwise; "New update" stores that prefilled draft at once (manual mode) so the form always edits a stored draft;
- "Draft with AI" replaces the form's fields; the responder presses "Save draft" first to keep typed text;
- submit is Approve with blank-field validation; "Save draft" is a button and accepts partial fields; the stage floor is enforced at approval only;
- AI availability means the text-generation binding can be built (the OpenAI settings load); there is no separate on/off setting;
- a model call that fails leaves the form as it is with a notice; the responder keeps writing by hand;
- a hand-written draft for a security incident needs no confirmation because nothing is sent to a model.

LAYERS, each a single PR under the size gate, merged and deployed bottom-up (a gh stack is acceptable so the next layer is written while the previous one is reviewed): TASK-144.1 shape fix (platforms/ merged into entrypoints/) -> TASK-144.2 records -> TASK-144.3 service and store -> TASK-144.4 modal: start and save -> TASK-144.5 modal: AI inside the form, Draft and Write it myself leave the overview.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every subtask is done
<!-- AC:END -->
