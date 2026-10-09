---
id: TASK-144.2
title: >-
  Record human-first status updates in the decision records and the scribe
  README
status: In Progress
assignee:
  - '@me'
created_date: '2026-10-09 12:53'
updated_date: '2026-10-09 14:10'
labels:
  - incident
  - features
  - docs
dependencies:
  - TASK-144.1
references:
  - decisions/incident-management.md
  - decisions/interaction-toolkits.md
  - decisions/transport-slack.md
  - decisions/feature-packages.md
parent_task_id: TASK-144
priority: high
type: docs
ordinal: 346000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 2 of TASK-144 (documentation only). decisions/incident-management.md "External status updates" (Drafting, Where it happens, Approval bullets) and its Checks describe the AI-first flow TASK-140 shipped: the model fills the fields, the modal offers "a way to draft", approval is where a person edits. This task rewrites them to the direction in TASK-144: a responder writes the update; "Draft with AI" is an optional assist inside the form, shown only when text generation is configured; the carried-forward rule, the security confirmation before any model call and "nothing in the incident conversation" stay. The Migration section names TASK-144 and keeps TASK-140 as the shipped first cut. transport-slack.md's sentence on the first registered view ("AI drafts are reviewed and edited by a human") and interaction-toolkits.md's "first consumer" line are reworded. feature-packages.md Context drops incident/scribe from the platforms/ list once TASK-144.1 has merged. The scribe README's status-update reference section describes the target flow, marking what lands with TASK-144.3 to TASK-144.5. Every record gets a dated Changes line. No task file is edited by hand; TASK-140.11 and TASK-140.12 get a CLI comment pointing at the new vocabulary (Draft with AI, origin).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 incident-management.md External status updates reads human-first: a responder writes, AI assists inside the form when configured, code still decides nothing-is-new, confirmation precedes any model call, nothing reaches the conversation; Checks and Migration updated; dated Changes line
- [x] #2 transport-slack.md and interaction-toolkits.md no longer describe the first registered view as AI drafts reviewed by a human; each has a dated Changes line
- [x] #3 feature-packages.md Context no longer lists incident/scribe among the packages with platforms/; dated Changes line
- [x] #4 scribe/README.md status-update section describes the target flow and names the layer each part lands with
- [x] #5 TASK-140.11 and TASK-140.12 carry a CLI comment translating their Draft/Redraft wording to the human-first flow; no task markdown edited by hand
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Grounded at main af6a316e (2026-10-09). Documentation only; no production code, no tests. Starts after TASK-144.1 has merged (the feature-packages.md edit depends on it).

## Discovered state

- `decisions/incident-management.md` "External status updates" is lines 74-83: bullets Stage, Fields, Drafting ("the text-generation capability fills the fields ... For a security or unknown-flag incident the responder confirms in the modal after pressing Draft"), Where it happens ("the pending draft, a way to draft, and the history"), Approval ("a responder edits and approves the draft in the review modal ... Instead of editing, the responder can ask the model to redraft"), Rendering and publishing. Checks lines 133-135 are the three status-update tests. Migration line 139 lists TASK-140; the tolerated list already dropped the legacy `updates` item (2026-10-08 Changes line).
- `decisions/transport-slack.md:39`: "The first consumer is the status-update approval modal: AI drafts are reviewed and edited by a human before they are published, as incident platforms do."
- `decisions/interaction-toolkits.md:178`: "The first consumer is the incident status-update approval modal (TASK-140)."; line 207 names `incident/scribe` as the proof feature.
- `decisions/feature-packages.md:13`: "Four packages (`geolocate`, `incident/scribe`, `rant`, `user_rotations`) put Slack handlers in `platforms/`".
- `app/packages/incident/scribe/README.md`: "### `/sre incident status-update`" starts at line 525 and describes the AI-first modal (Draft, Write it myself, review, redraft, published toggle).
- TASK-140.11 and TASK-140.12 descriptions are written against the Draft and Redraft buttons ("human drafts win" means a draft made with Draft or Redraft; TASK-140.12 says "fixed by a correction ... Draft or Redraft to refresh").

## Steps

1. `decisions/incident-management.md`, section "External status updates":
   - Replace the Drafting bullet with a "Writing and drafting" bullet: a responder writes the update in the form, prefilled from the latest approved update (blank at the first stage when there is none); "Draft with AI" is offered inside the form only when text generation is configured and fills the fields in EN and FR from the conversation since the latest approved update's transcript cutoff; code, not the model, decides nothing is new (no new human messages: the carried-forward wording, no model call); for a security or unknown-flag incident the responder confirms in the form before any model call, a hand-written draft needs no confirmation because nothing is sent, and automatic drafting (TASK-140.11) skips those incidents.
   - Where it happens: the modal shows the pending draft with its origin (who, how, when) or a "New update" button, and the approved history; the form saves a draft or approves it.
   - Approval: the form has Save draft and Approve; redrafting with instructions is the AI button with instructions typed; nothing leaves draft unapproved; each record carries its origin (hand-written, model, model with instructions, carried forward).
   - Checks: keep "with no new human messages since the latest update, drafting makes no model call"; reword the confirmation test to "a security or unknown-flag incident makes no model call until the responder confirms; a hand-written draft asks for no confirmation"; add "the AI section is absent when text generation is unconfigured, and saving and approving still work".
   - Migration: add TASK-144 to the tickets line ("TASK-144 turns the flow human-first"); Changes line dated the day of the PR: "status updates are written by the responder first; AI drafting is an optional assist inside the form, shown only when text generation is configured (TASK-144)".
2. `decisions/transport-slack.md:39`: "The first consumer is the status-update modal: a responder writes or AI-drafts the update, then reviews and approves it in place (TASK-140, TASK-144)." Add a Changes line.
3. `decisions/interaction-toolkits.md:178`: "The first consumer is the incident status-update modal (TASK-140; human-first in TASK-144): a form that saves, AI-fills and approves in place." Add a Changes line. Leave the Open questions unchanged.
4. `decisions/feature-packages.md:13`: "Three packages (`geolocate`, `rant`, `user_rotations`) put Slack handlers in `platforms/`"; Changes line: "incident/scribe handlers merged into `entrypoints/` (TASK-144.1)". The tolerated list (line 115) stays.
5. `app/packages/incident/scribe/README.md`, status-update section: describe the target flow (modal with pending draft or New update, the form with Save draft, Approve and the AI section when configured, origin line, history and published toggle unchanged) and mark each part with the layer that lands it: TASK-144.3 (origin, save, generate, availability), TASK-144.4 (New update, Save draft, origin line), TASK-144.5 (AI inside the form, overview buttons removed). Keep the settings and scopes subsections.
6. CLI only: `backlog task edit TASK-140.11 --comment "..."` and `backlog task edit TASK-140.12 --comment "..."` stating that after TASK-144 "Draft" and "Redraft" mean the form's "Draft with AI" button (with or without instructions), "a draft made with Draft or Redraft" means any pending draft whose origin is hand-written, model or model-with-instructions, and the periodic label becomes the record's origin.

## AC traceability

| AC | Steps |
| --- | --- |
| 1 | 1 |
| 2 | 2, 3 |
| 3 | 4 |
| 4 | 5 |
| 5 | 6 |

## Test matrix

None (documentation). Verification: `rg -n 'a way to draft|after pressing Draft' decisions/` empty; `rg -n 'incident/scribe' decisions/feature-packages.md` shows only the 2026-10-02 Changes line; every edited record has a new dated Changes line (`git diff decisions/`).

## Assumptions and doubts

- TASK-144.1 has merged before the feature-packages.md edit (dependency). If this PR is opened first in a stack, land step 4 in the same PR anyway; the stack order guarantees the merge order.
- The records' "applies: target" status means describing the end state before TASK-144.3 to 144.5 ship is correct; the README marks what is not yet live.

## Size, blast radius and rollback

Five markdown files and two CLI comments. No runtime effect. Single revert.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
What changed (documentation only; no Python, no tests)
- decisions/incident-management.md, External status updates:
  - Drafting becomes "Writing and drafting". A responder writes in a form prefilled from the latest approved update; "Draft with AI" is offered inside the form only when text generation is configured. Unchanged: code decides nothing-is-new, confirmation comes before any model call, and automatic drafting skips security incidents. A hand-written draft needs no confirmation.
  - "Where it happens": pending draft with its origin, or a "New update" button.
  - Approval: Save draft or Approve; redraft is Draft with AI with instructions; records carry their origin.
  - Checks: the confirmation test is reworded and a new test covers no AI section when text generation is unconfigured.
  - Migration names TASK-140 as the shipped first cut and adds TASK-144. Changes line dated 2026-10-09.
- decisions/transport-slack.md: the first-consumer sentence now reads "a responder writes or AI-drafts the update, then reviews and approves it in place (TASK-140, TASK-144)". Changes line added.
- decisions/interaction-toolkits.md, line 18 (the plan said 178; the sentence has since moved): the first consumer is the human-first form. Changes line added; Open questions untouched.
- decisions/feature-packages.md Context: "Three packages (geolocate, rant, user_rotations) put Slack handlers in platforms/". Changes line names TASK-144.1. Lines 14 and 116 still name incident/scribe for its integrations.openai import, which is still true (service.py:39), so they stay. The plan's expectation that rg would find only the Changes line was too strict.
- app/packages/incident/scribe/README.md, status-update section: new "Target flow (TASK-144)" subsection with each part marked by its layer (144.3 origin, save, generate, availability; 144.4 New update, Save draft, origin line; 144.5 AI inside the form, overview buttons removed; approval, copy-ready, history and published toggle unchanged). The existing description sits under "Shipped today".
- CLI comments on TASK-140.11 and TASK-140.12 translate Draft and Redraft to New update, Draft with AI and origin. No task markdown was edited by hand.

Verification
- rg -n 'a way to draft|after pressing Draft' decisions/ -> no matches (exit 1)
- git diff decisions/ -> four new "2026-10-09" Changes lines, one per record
- git diff --stat -> 8 files, +72/-13 (README, 4 decision records, 3 task files via CLI); no .py file changed, so the ruff, mypy and pytest gates do not apply. Layer 1's gates are unchanged (TASK-144.1 notes).
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-09 14:07
---
Plan approved (human, 2026-10-09); implementation on stack-i/task-144.2-human-first-records, stacked on fix/incident_scribe_shape (PR #1568)
---
<!-- COMMENTS:END -->
