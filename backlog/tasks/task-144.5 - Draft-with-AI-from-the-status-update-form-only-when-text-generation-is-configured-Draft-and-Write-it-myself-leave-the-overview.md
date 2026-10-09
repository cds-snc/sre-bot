---
id: TASK-144.5
title: >-
  Draft with AI from the status-update form only when text generation is
  configured; Draft and Write it myself leave the overview
status: To Do
assignee: []
created_date: '2026-10-09 12:53'
updated_date: '2026-10-09 13:01'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-144.4
references:
  - decisions/incident-management.md
  - decisions/platform-entrypoints.md
  - decisions/transport-slack.md
parent_task_id: TASK-144
priority: high
type: feature
ordinal: 349000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 5 of TASK-144 (contract). The AI moves inside the form and the overview becomes human-first.

THIS SLICE (packages/incident/scribe/entrypoints/slack.py and slack_views.py, status_update.py, locales)
- Form: the Redraft section becomes the AI section: one "Draft with AI" button (action id incident.scribe.status_update.generate, replacing redraft), an optional instructions input ("tell the AI what to change"), and the security confirmation checkbox when the service refused. The whole section is omitted when text_generation_available() is False. The handler calls generate_status_update_draft with the typed fields as the base: a carried-forward outcome re-renders the form with the wording applied and a "nothing new since the last approved update" notice (no model call); a drafted outcome re-renders the form for the new sequence with a note; SECURITY_CONFIRMATION_REQUIRED re-renders with the checkbox; TEXT_GENERATION_UNAVAILABLE, a failed or unparseable call keep the typed values with a notice. A drafting view is shown only while the model call runs.
- Overview: the Draft, Confirm and draft and Write it myself buttons, the security confirmation view, the drafting view and the result view are deleted with their handlers (handle_draft_action, handle_draft_confirmed_action, handle_write_action, _run_draft, _manual_review_view); draft_status_update loses its model path and keeps only the manual start, renamed start_status_update_draft; redraft_status_update is deleted; the obsolete locale keys go.
- Checks from decisions/incident-management.md hold: no model call without confirmation for a security or unknown-flag incident; a hand-written draft needs none; no new human messages means no model call; nothing reaches the conversation.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The form shows Draft with AI, the optional instructions input and, after a refusal, the confirmation checkbox only when text generation is configured; with it unconfigured the form has no AI section and Save and Approve work
- [ ] #2 Draft with AI with no new human messages since the latest approved update makes no model call and re-renders the form with the carried-forward wording and a notice; with new messages it makes one model call and re-renders the form for the new draft; typed instructions are passed to the model
- [ ] #3 A security or unknown-flag incident shows the confirmation checkbox and no model call is made until it is checked; a hand-written draft is saved and approved without any confirmation
- [ ] #4 The overview has no Draft, Confirm and draft or Write it myself button; the obsolete handlers, views, service paths and locale keys are deleted; the registration test lists the final action ids
- [ ] #5 Nothing is posted to the incident channel (test); EN/FR parity passes; ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass; import-linter ignore entries unchanged or fewer
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Grounded at main af6a316e (2026-10-09); paths assume TASK-144.1 to TASK-144.4 have merged. Contract step: the AI moves into the form, the overview loses its AI buttons, the obsolete paths are deleted.

## Discovered state (names as of af6a316e, moved by TASK-144.1)

- Overview AI path: `handle_draft_action`, `handle_draft_confirmed_action`, `_run_draft(body, client, *, security_confirmed, manual)`, `_manual_review_view` in `entrypoints/slack.py`; views `build_security_confirmation_view`, `build_drafting_view`, `build_result_view`, `manual_fallback_notice`, `_draft_button_block`'s Draft button; constants `DRAFT_ACTION_ID`, `CONFIRM_ACTION_ID`; locale keys `draft_button`, `drafting`, `drafted`, `carried_forward`, `pending`, `security_confirmation`, `confirm_button`, `manual_fallback`.
- Form AI path: `_redraft_blocks(locale, instructions, *, security_confirm)` (instructions input, optional checkbox `security_confirm`, actions block `redraft_button` with `REDRAFT_ACTION_ID`), `build_review_view(..., with_redraft)`, `parse_redraft_form(view) -> (instructions, confirmed)`, `build_redrafting_view`, `redraft_notice(key, locale)` with keys `redrafted_note`, `redraft_blank`, `redraft_failed`, `redraft_unparseable`, `redraft_security`, `redraft_label`, `redraft_hint`, `redraft_button`; handler `handle_redraft_action` (reads form state, calls `redraft_status_update`, re-renders on every outcome, shows the redrafting view only around the model call).
- Service after TASK-144.3: `generate_status_update_draft` (blank instructions allowed; carried-forward without a model call; outcome kinds CARRIED_FORWARD and DRAFTED), `redraft_status_update` wrapper, `draft_status_update` with its model path and manual path, `text_generation_available()`.
- `decisions/incident-management.md` Checks: no model call without confirmation for a security or unknown-flag incident; no new human messages means no model call; nothing reaches the conversation.

## Steps

1. `status_update.py`: delete `redraft_status_update`. Reduce `draft_status_update` to the manual start and rename it `start_status_update_draft(conversation_id, *, author, lookup=None, reader=None, store=None, now=None) -> OperationResult[StatusUpdateDraftOutcome]`: resolve, list, read the window (for the cutoff and fingerprint), return the pending draft as PENDING when one exists, otherwise append the prefilled draft (`_prefill_fields`) with origin HAND as MANUAL. Remove `wording`, `security_confirmed`, `on_started`, `generator` and `security_reader` from it; `_holds` and the "abandoned prefill" branch go with the model path. Keep `_security_gate`, `_generate_fields`, `_read_window`, `_carry_forward`, `_draft_record`, `_append` for `generate_status_update_draft`. Rewrite the module docstring around start, save, generate.
2. `slack_views.py`: rename `_redraft_blocks` to `_ai_blocks(locale, instructions, *, security_confirm)`: the button becomes "Draft with AI" (`GENERATE_ACTION_ID = "incident.scribe.status_update.generate"`, key `generate_button`), the instructions input keeps block id `instructions` with label "Instructions for the AI (optional)" and hint "Leave empty to draft from the conversation, or say what to change, for example: do not name the vendor." (keys `generate_label`, `generate_hint`), the checkbox block stays. `build_review_view(..., with_ai: bool)` replaces `with_redraft` and omits the section when False. `parse_redraft_form` becomes `parse_ai_form`. `build_redrafting_view` becomes `build_generating_view` (key `generating`). Notices: `generated_note`, `generate_carried_forward` ("Nothing new since the last approved update; the fields repeat it with the no-new-information wording."), `generate_failed`, `generate_unparseable`, `generate_security`, `generate_unavailable`. Delete `build_security_confirmation_view`, `build_drafting_view`, `build_result_view`, `manual_fallback_notice`, `DRAFT_ACTION_ID`, `CONFIRM_ACTION_ID`, `REDRAFT_ACTION_ID`. `_draft_button_block` becomes `_overview_actions(locale, update)`: New update when there is no pending draft, Review when there is.
3. `entrypoints/slack.py`: delete `handle_draft_action`, `handle_draft_confirmed_action`, `_run_draft`, `_manual_review_view`. `handle_new_update_action` calls `start_status_update_draft` and builds the form with `with_ai=text_generation_available()`. `handle_save_action`, `handle_review_action` and the failure re-renders pass the same flag. Rename `handle_redraft_action` to `handle_generate_action`: `instructions, confirmed = parse_ai_form(view)`, `edit = parse_review_submission(view)`, call `generate_status_update_draft(channel_id, sequence, current=edit, author=user_id, wording=build_no_new_information_wording(), instructions=instructions, security_confirmed=confirmed, on_started=show_generating)`; outcomes: CARRIED_FORWARD -> form for the new sequence with `generate_carried_forward`; DRAFTED -> form with `generated_note`; `SECURITY_CONFIRMATION_REQUIRED` -> form from the typed values with `generate_security`, instructions kept, `security_confirm=True`; `TEXT_GENERATION_UNAVAILABLE` -> `generate_unavailable`; `DRAFT_UNPARSEABLE` -> `generate_unparseable`; `STATUS_UPDATE_CONFLICT` -> review conflict view; other -> `generate_failed`; `EMPTY_HISTORY` -> `generate_failed` wording variant (key `generate_empty_history`). `register` registers new, save, generate, review, open, history, published and the approve submission; nothing else.
4. Locales: delete `draft_button`, `drafting`, `drafted`, `pending`, `security_confirmation`, `confirm_button`, `manual_fallback`, `redraft_label`, `redraft_hint`, `redraft_button`, `redrafting`, `redrafted_note`, `redraft_blank`, `redraft_failed`, `redraft_unparseable`, `redraft_security`; add the `generate_*` and `generating` keys in EN and FR; keep `carried_forward` only if still referenced (grep).
5. README: status-update section marks the AI section and the overview as live; the "Call path" and "Files" sections mention `generate` instead of `draft`/`redraft`.
6. Tests: delete test_incident_scribe_status_update_entrypoint.py (Draft), test_incident_scribe_status_update_confirmation.py, test_incident_scribe_status_update_redraft_{entrypoint,view}.py and the integration redraft dispatch test; add test_incident_scribe_status_update_generate_entrypoint.py, test_incident_scribe_status_update_generate_view.py and integration test_incident_scribe_status_update_generate_dispatch.py; rewrite test_incident_scribe_status_update_service.py, _pending.py and _security_gate.py for `start_status_update_draft` and `generate_status_update_draft` (the security-gate cases move to generate); test_incident_scribe_status_update_redraft.py cases become generate-with-instructions cases inside test_incident_scribe_status_update_generate.py (from TASK-144.3) or are deleted when duplicated; registration test lists the final ids; locales parity.

## AC traceability

| AC | Steps | Tests |
| --- | --- | --- |
| 1 | 2, 3 | generate_view: section present with the button, optional input and no checkbox by default; `with_ai=False` -> no `instructions`, `security_confirm` or `generate` blocks and the stage, fields, Save and Approve remain; generate_entrypoint: availability False -> form built without the section |
| 2 | 1, 3 | generate_entrypoint with the in-memory store and a recording generator fake: no new messages -> zero calls, form shows the wording and the notice; new messages -> one call; typed instructions reach the generator's instructions argument |
| 3 | 1, 3 | generate_entrypoint: security YES unconfirmed -> no call, checkbox shown; checked -> one call, flag not read; save_entrypoint and review submission for a security incident -> no confirmation and no model call (assert the generator fake has zero calls) |
| 4 | 1, 2, 3, 4, 6 | overview test: no Draft, Confirm, Write buttons; registration test: final ids; `rg -n 'DRAFT_ACTION_ID|CONFIRM_ACTION_ID|REDRAFT_ACTION_ID|redraft_status_update|build_result_view' app` empty |
| 5 | all | `chat_postMessage` never called in every entrypoint test; locales parity; gates; `git diff app/pyproject.toml` empty |

## Test matrix

Form rendering: with and without AI; instructions prefilled after a refusal; checkbox only after a refusal; FR labels. Generate: carried forward (no call), drafted (one call, base prompt), instructed (redraft prompt), security refusal then confirmed, unavailable generator, unparseable answer, generator error, stale sequence conflict, EMPTY_HISTORY on a first update with no messages; every failure keeps the typed values and sequence. Start: no pending -> HAND prefilled draft and form; pending -> that draft's form. Registration: exactly seven block actions and one view submission.

## Assumptions and doubts

- `text_generation_available()` is a pure predicate (TASK-144.3); the handler passing its value to a view builder is wiring, not business logic, and keeps the one-service-call rule.
- Deleting `draft_status_update`'s model path removes the only automatic-drafting entry; TASK-140.11 (deferred) will build on `generate_status_update_draft` with `security_confirmed=False`, which refuses security incidents as the gate requires. Record this on TASK-140.11 in the notes.
- In-flight modals opened before deploy carry the old action ids; a press logs an unhandled action. Accepted.

## Size

Production: `status_update.py` about -120 +40, `slack_views.py` about -90 +110, `entrypoints/slack.py` about -140 +90, locales about 2 x 15, README. Net about 240 production lines changed across 5 files, more deletions than additions; tests about 600 lines (new and rewritten). Under the gate; deletions are cheap to review.

## Blast radius and rollback

Users lose the overview Draft button and gain the in-form one in the same deploy; the service keeps one model call per press and the security gate. Records are unchanged in shape. Single `git revert` restores the previous layer; no config, no Terraform.
<!-- SECTION:PLAN:END -->
