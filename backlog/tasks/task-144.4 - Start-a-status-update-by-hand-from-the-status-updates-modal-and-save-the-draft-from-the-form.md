---
id: TASK-144.4
title: >-
  Start a status update by hand from the status-updates modal and save the draft
  from the form
status: To Do
assignee: []
created_date: '2026-10-09 12:53'
updated_date: '2026-10-09 13:01'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-144.3
references:
  - decisions/incident-management.md
  - decisions/platform-entrypoints.md
  - decisions/transport-slack.md
parent_task_id: TASK-144
priority: high
type: feature
ordinal: 348000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 4 of TASK-144 (first modal change; expand). The overview gains the human-first entry and the form gains Save; the AI buttons stay where they are until TASK-144.5, so no deploy loses AI drafting.

THIS SLICE (packages/incident/scribe/entrypoints/slack.py and slack_views.py, locales)
- Overview: with no pending draft, a primary "New update" button (action id incident.scribe.status_update.new) replaces Write it myself; the Draft button stays for now. With a pending draft, a line says who made it and how (origin: written by @user / drafted by AI / redrafted with instructions / carried forward; records without an origin show only the author) and when, in the responder's locale, and the Review button stays. New update calls the manual start (draft_status_update(manual=True) from TASK-144.3) and replaces the modal with the form for the stored draft, as Write it myself does today.
- Form: a "Save draft" button (action id incident.scribe.status_update.save) in its own actions block reads view.state.values with parse_review_submission and calls save_status_update_draft; the form re-renders for the new sequence with a "Draft saved" notice. A conflict shows the review conflict view; a store failure re-renders the form from the typed values with a notice. Submit stays Approve.
- Locales: EN and FR keys for the new button, the saved notice, the origin line and its time; the parity test covers them.
Handlers stay five-step (ack, parse, one service call, render); nothing is posted to the channel.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 With no pending draft the overview shows New update and no Write it myself button; pressing it stores a prefilled hand-written draft and replaces the modal with its form, in EN and FR
- [ ] #2 With a pending draft the overview shows who made it, how (origin) and when, plus Review; a record without an origin shows the author only
- [ ] #3 Save draft appends the next draft with the typed stage and fields and re-renders the form for the new sequence with a saved notice; partial fields are accepted; a stale sequence shows the conflict view; a failure keeps the typed values with a notice
- [ ] #4 The Draft, Confirm and draft, Review, Open, Back, published and Redraft listeners behave as before; the new action ids are registered once with the plugin prefix
- [ ] #5 Nothing is posted to the incident channel (test); EN/FR locale parity test passes; ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Grounded at main af6a316e (2026-10-09); paths assume TASK-144.1 (views in `entrypoints/slack_views.py`, handlers in `entrypoints/slack.py`) and TASK-144.3 (`save_status_update_draft`, `StatusUpdate.origin`) have merged. Expand step: the Draft, Confirm and Redraft paths keep working; only Write it myself is replaced.

## Discovered state (names as of af6a316e in `platforms/slack.py`, moved by TASK-144.1)

- `_draft_button_block(locale, update, *, with_draft)` (696): with `with_draft`, Draft (`DRAFT_ACTION_ID`, primary) and Write it myself (`WRITE_ACTION_ID`) buttons; with a draft, the Review button whose value is `{"incident_id", "sequence"}`. `build_overview_view` (826) renders `_pending_blocks` plus that block, or the `no_pending` text plus that block, then `_approved_blocks`.
- `build_review_view(update, locale, private_metadata, notice=None, *, instructions=None, security_confirm=False, with_redraft=True)` (950): optional notice, the Redraft section (`_redraft_blocks`: instructions input block `instructions`, checkbox block `security_confirm`, actions block `redraft_button`), stage select (block `stage`), EN then FR inputs (blocks `en.<field>`, `fr.<field>`, all optional), `callback_id=REVIEW_CALLBACK_ID`, submit Approve, close Cancel. `parse_review_submission(view)` reads `view.state.values` into a `StatusUpdateEdit`.
- `entrypoints/slack.py`: `handle_write_action` -> `_run_draft(body, client, security_confirmed=False, manual=True)` -> `draft_status_update(..., manual=True)` -> `_manual_review_view` -> `build_review_view(update, locale, review_metadata, notice, with_redraft=not hand_written)`. `handle_redraft_action` shows how a block action reads form state (`parse_redraft_form(view)`, `parse_review_submission(view)`), rebuilds `review_metadata(sequence)` and re-renders. `_ModalCursor` updates by view id and hash.
- Locales `incident_status_update.{en-US,fr-FR}.yml` keys include `draft_button`, `write_button`, `review_button`, `no_pending`, `redraft_*`, `manual_fallback`; `tests/unit/packages/incident/scribe/test_incident_scribe_status_update_locales.py` checks EN/FR parity.
- `comms_profile.format_profile_time(...)` formats a time in the profile's zone; `_stage_line` (767) shows the pattern for a one-line summary with a time.
- Tests touching the overview and the manual path: test_incident_scribe_status_update_overview.py, test_incident_scribe_status_update_manual_{view,entrypoint}.py, test_incident_scribe_status_update_history_view.py, test_incident_scribe_plugin_registration.py, integration dispatch tests.

## Steps

1. `slack_views.py`: add `NEW_ACTION_ID = "incident.scribe.status_update.new"` and `SAVE_ACTION_ID = "incident.scribe.status_update.save"`; delete `WRITE_ACTION_ID`. In `_draft_button_block`, with no pending draft render Draft and a primary "New update" button (`NEW_ACTION_ID`, key `new_update_button`); with a pending draft render Draft and Review as today, no Write it myself. Add `origin_line(update, locale) -> str`: "Written by <@author> at <time>" / "Drafted by AI at <time>" / "Redrafted with instructions at <time>" / "Carried forward at <time>" by `update.origin`, and "By <@author> at <time>" when `origin` is None, with keys `origin.hand`, `origin.model`, `origin.model_instructed`, `origin.carried_forward`, `origin.unknown` and the time through `format_profile_time` in the responder's locale. `build_overview_view` inserts a context block with that line before `_pending_blocks` when there is a pending draft.
2. `slack_views.py`, `build_review_view`: after the FR fields, an actions block `save_button` holding a "Save draft" button (`SAVE_ACTION_ID`, key `save_button`). Add `save_notice(key, locale)` for `saved_note` ("Draft saved.") and `save_failed` ("The draft could not be saved; your text is still here."). Approve stays the only submit.
3. `entrypoints/slack.py`: rename `handle_write_action` to `handle_new_update_action` and register it under `NEW_ACTION_ID`; `_run_draft(manual=True)` and `_manual_review_view` stay as they are (TASK-144.5 replaces them). Add `handle_save_action(ack, body, client)`: ack; read `channel_id`, `locale`, `incident_id`, `sequence` from the view's private metadata; `edit = parse_review_submission(view)`; call `save_status_update_draft(channel_id, sequence, edit=edit, author=user_id)` in `asyncio.run` (keep the sync listener shape until TASK-33); success -> `build_review_view(result.data, locale, review_metadata(result.data.sequence), notice=save_notice("saved_note"))`; `STATUS_UPDATE_CONFLICT` -> `build_review_error_view(error_code, locale, review_metadata(sequence))`; other failure -> re-render the form from the typed values: `stored = get_draft_for_review(incident_id, sequence)`, `replace(stored.data, stage=edit.stage, en=edit.en, fr=edit.fr)` with `save_notice("save_failed")`, as `handle_redraft_action` does. `edit is None` (no stage) is treated as the failure branch with the stored draft. Register `SAVE_ACTION_ID`. Update `register`'s docstring and the module docstring.
4. Locales: add `new_update_button`, `save_button`, `saved_note`, `save_failed`, `origin.hand`, `origin.model`, `origin.model_instructed`, `origin.carried_forward`, `origin.unknown` in EN and FR; delete `write_button`.
5. README status-update section: the overview and form as they now are (TASK-144.2 described the target; this step marks New update and Save draft as live).
6. `INVENTORY.md` is unchanged (block actions are not inventoried rows); the registration test's expected action ids gain `new` and `save` and lose `write`.

## AC traceability

| AC | Steps | Tests |
| --- | --- | --- |
| 1 | 1, 3, 4 | test_incident_scribe_status_update_overview.py (New update present, Write absent, EN and FR labels); new test_incident_scribe_status_update_new_entrypoint.py (replaces test_incident_scribe_status_update_manual_entrypoint.py: stores a HAND draft via the in-memory store and the modal is replaced by the form) |
| 2 | 1, 4 | test_incident_scribe_status_update_overview.py (origin line per origin value; None shows author only; time in locale) |
| 3 | 2, 3 | new test_incident_scribe_status_update_save_entrypoint.py and test_incident_scribe_status_update_save_view.py; integration test_incident_scribe_status_update_save_dispatch.py (registrar dispatch through the fake Bolt payload, as the redraft dispatch test does) |
| 4 | 3, 6 | test_incident_scribe_plugin_registration.py; existing entrypoint tests unchanged |
| 5 | all | the "nothing posted" assertion (`chat_postMessage` never called) in the new entrypoint tests; locales parity; gates |

## Test matrix

Overview: no pending -> New update primary plus Draft, no Write; pending -> origin line, Review, Draft; origin None -> author-only line; FR locale labels. New update: stores a prefilled draft (latest approved fields, else blank at the first stage) with origin HAND and shows the form; a pending draft already present -> that draft's form (PENDING); lookup refusal -> error view. Save: happy path -> form for sequence+1 with the saved notice and the new sequence in private metadata; partial fields saved; stale sequence -> conflict view; store failure -> form keeps typed values with the failed notice; Slack `views_update` failure logged, not raised; nothing posted to the channel. Registration: `new`, `save` registered once with the plugin prefix; `write` absent.

## Assumptions and doubts

- A block-action payload from a modal carries `view.state.values` for the inputs in that view; `parse_redraft_form` already relies on it (verify in the recorded fixtures under tests/integration/packages/incident/scribe).
- An in-flight modal opened before deploy still shows Write it myself; pressing it hits an unregistered action id and Bolt logs an unhandled action. Accepted; deploy in a quiet window.
- `format_profile_time` renders ET; the responder's locale selects EN or FR wording only (same as the stage line).

## Size

Production: `slack_views.py` about 110 lines (origin line, buttons, save block, notices), `entrypoints/slack.py` about 70, locales about 2 x 12, README. About 200 production lines across 4 files; tests about 450 lines across 5 files (2 renamed from manual_*). Under the gate.

## Blast radius and rollback

Only the overview's buttons and the form's Save button change; Draft, Redraft, Review, Approve, Open and the toggle are untouched. A defect in Save leaves the pending draft as it was (append-only). Single `git revert`; records saved with origin HAND remain readable by the previous layer.
<!-- SECTION:PLAN:END -->
