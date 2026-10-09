---
id: TASK-145.3
title: Make every status-update handler call one service method and render its result
status: In Progress
assignee: []
created_date: '2026-10-09 16:43'
updated_date: '2026-10-09 19:33'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.2
parent_task_id: TASK-145
priority: high
type: task
ordinal: 353000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer A3 of TASK-145, in place in features/incident/scribe. Behavioural refactor of the entry point only; the modal's behaviour is unchanged.

TODAY: handle_generate_action is about 80 lines, handle_save_action and handle_status_update_command about 58, the approve submission and the published toggle chain two or three service calls, and the save failure path rebuilds a domain object with dataclasses.replace in the handler. decisions/feature-packages.md Handler discipline: receive, translate, one service call, render.

THIS SLICE
- Service results carry what the handler needs to render on failure: the save result includes the typed edit, approve_and_publish and toggle_published are single service functions returning the copy-ready text or the classified error, the overview result includes the AI-availability flag.
- Each handler: ack, parse the payload into typed values, one service call, one view builder from the outcome kind. No dataclasses.replace, no OperationResult chaining and no try/except around business outcomes in entrypoints/slack.py.
- asyncio.run stays (tolerated until TASK-33) but appears once per handler at most.
- Handler tests stub the service and assert the rendered view; service tests cover the merged paths.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 No handler in scribe/entrypoints/slack.py exceeds about 30 lines or calls more than one service function
- [x] #2 scribe/entrypoints/slack.py imports no domain constructor and does not import dataclasses.replace
- [x] #3 approve_and_publish and toggle_published exist as single service functions with tests for success and each error outcome
- [x] #4 The status-update modal flows (start, save, generate, approve, history, published) behave as before: existing integration tests pass with handler stubs updated only
- [x] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Grounded at main d2d973ae (2026-10-09); paths assume TASK-145.1 and TASK-145.2 merged. Behaviour-preserving refactor of the status-update entry point: every handler renders the same view for the same input, proven by the existing entrypoint and dispatch tests with their service stubs retargeted.

## Discovered state (entrypoints/slack.py)
- handle_status_update_command (410-467, 58 lines): open loading view, one service call (get_status_update_overview), update view; acceptable shape, trimmed only by the helper below.
- handle_generate_action (665-745, 80 lines): parses metadata and form, runs a local coroutine that calls get_draft_for_review, generate_status_update_draft and get_draft_for_review again on failure, then four render branches; rebuilds the form with dataclasses.replace(stored.data, stage=edit.stage, ...); maps error codes to notice keys through _GENERATE_FAILURE_KEYS and _generate_failure_key (757-759).
- handle_save_action (747-805, 58 lines): save_status_update_draft, then on failure get_draft_for_review plus replace(...); calls text_generation_available() for with_ai.
- handle_review_submission (843-885) plus _approve_and_publish (888-905): approve_status_update then providers.get_status_page_publisher().publish(...) with build_profile_labels for EN and FR: two service calls chained in the entry point.
- handle_open_action, handle_history_action, handle_published_action use _read_and_publish, _toggle_and_publish and _render_record (808-840): get_approved_update or set_published, then publish: chained in the entry point.
- handle_new_update_action (470-500) and handle_review_action (524-561) are single-call handlers already. asyncio.run appears once per handler (8 in total; tolerated until TASK-33). _ModalCursor updates the modal by view id and hash.
- Service surface today: status_update.py get_status_update_overview, get_pending_status_update, start_status_update_draft, save_status_update_draft, generate_status_update_draft, text_generation_available; status_update_approval.py validate_approval_edit, get_draft_for_review, approve_status_update; status_update_history.py get_approved_update, set_published; publisher.render_copy_ready; providers.get_status_page_publisher. domain.py: StatusUpdateOutcomeKind, StatusUpdateDraftOutcome(update, kind), StatusUpdateEdit, CopyReadyText, StatusUpdateOverview(pending, approved).

## Steps
1. domain.py: `StatusUpdateFormState(update: StatusUpdate, kind: StatusUpdateOutcomeKind | None, failure_code: str | None, ai_available: bool)` ("the form to show: the new draft on success, or the stored draft overlaid with the typed values and the code that explains why nothing changed") and `PublishedRecord(update, text: CopyReadyText)`. StatusUpdateOverview gains `ai_available: bool`.
2. status_update.py: `save_status_update_form(channel_id, incident_id, sequence, *, edit, author)` -> OperationResult[StatusUpdateFormState]: success with the saved draft; a non-conflict save failure returns success with the stored draft overlaid with edit and failure_code set; a conflict or an unreadable stored draft is the error result. `fill_status_update_form(channel_id, incident_id, sequence, *, edit, author, wording, instructions, security_confirmed, on_started)` the same shape around generate_status_update_draft: edit None means the stored draft is the model's base; kind set on success; refusal and failure codes carried in failure_code with the overlay draft. Both set ai_available from text_generation_available(). get_status_update_overview fills ai_available.
3. status_update_approval.py: `approve_and_publish(incident_id, sequence, *, approver, edit, labels_en, labels_fr, publisher=None)` -> OperationResult[CopyReadyText] (the body of _approve_and_publish; the publisher defaults to providers.get_status_page_publisher(), the module's existing default-argument convention). status_update_history.py: `read_published(incident_id, sequence, *, labels_en, labels_fr, publisher=None)` and `set_published_and_render(incident_id, sequence, *, published, actor, labels_en, labels_fr, publisher=None)` -> OperationResult[PublishedRecord] (the bodies of _read_and_publish, _toggle_and_publish, _render_record).
4. slack_views.py: `form_view_for(state: StatusUpdateFormState, locale, metadata, *, instructions=None)` chooses the notice from kind or failure_code (the _GENERATE_FAILURE_KEYS mapping and the saved/generated notices move here as view logic), security_confirm from SECURITY_CONFIRMATION_REQUIRED, with_ai from state.ai_available and TEXT_GENERATION_UNAVAILABLE.
5. entrypoints/slack.py: each handler becomes ack, parse (metadata, user, form), one service call inside one asyncio.run, one view builder, one modal update. Delete _approve_and_publish, _read_and_publish, _toggle_and_publish, _render_record, _as_edit, _generate_failure_key, _GENERATE_FAILURE_KEYS and the dataclasses.replace import. handle_status_update_command keeps its two reply calls (open, then update) around its one service call.
6. Tests: entrypoint tests (test_incident_scribe_status_update_{generate,save,review,published,history,new}_entrypoint.py, ..._slack.py) stub the new service functions and keep their view assertions; integration dispatch tests unchanged except stub targets; new service tests test_incident_scribe_status_update_form_save.py, ..._form_fill.py, ..._approval_publish.py, ..._history_render.py; view test test_incident_scribe_status_update_form_view.py for form_view_for.

## AC traceability
| AC | Steps | Tests |
| --- | --- | --- |
| 1 (no handler over ~30 lines or more than one service call) | 5 | a test in test_incident_scribe_status_update_slack.py asserting each registered handler's source has at most one asyncio.run and no call into status_update* modules other than one; plus review |
| 2 (no domain constructor or replace in the entry point) | 5 | grep in the same test (no `replace(` and no `StatusUpdateEdit(`/`replace` import in entrypoints/slack.py) |
| 3 (approve_and_publish, toggle as single functions with tests) | 3 | ..._approval_publish.py, ..._history_render.py |
| 4 (modal flows unchanged) | all | existing entrypoint and dispatch tests green with stubs retargeted |
| 5 | all | gates |

## Test matrix
save form: saved -> state with new sequence, no failure; conflict -> error; store failure -> overlay with failure_code; stored unreadable -> error. fill form: DRAFTED and CARRIED_FORWARD kinds; EMPTY_HISTORY, SECURITY_CONFIRMATION_REQUIRED, TEXT_GENERATION_UNAVAILABLE, DRAFT_UNPARSEABLE, generator error -> overlay with the code; conflict -> error; edit None -> stored draft is the base. approve_and_publish: refused approval -> error without publish; publisher failure -> error; success -> text. read/set published: read failure passed through; publisher failure; success. form_view_for: notice, checkbox and AI section per kind and code (table-driven).

## Assumptions and doubts
- Carrying failure_code inside a success result is the chosen shape because OperationResult failures carry no data; if the reviewer prefers a Protocol-level outcome type instead, the handler code is identical.
- Default-argument providers inside service functions follow the module's existing convention (store=None, lookup=None); the constructor-injection rule in feature-packages.md applies once TASK-109's registry exists.

## Size
status_update.py about +120, status_update_approval.py +30, status_update_history.py +40, domain.py +25, slack_views.py +40, entrypoints/slack.py about -170. About 300 production lines across 6 files. Under the gate.

## Blast radius and rollback
Modal behaviour only; a regression shows as a wrong view, caught by the entrypoint tests. Single `git revert`.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented on stack-j/task-145.3-status-update-handlers, re-grounded on layer 2.

Changes against the plan:
- The form functions live in a new status_update_form.py (start/open/save/fill_status_update_form), not in status_update.py: they compose get_draft_for_review from status_update_approval, which already imports status_update, and status_update.py is 666 lines.
- start_status_update_form and open_status_update_form were added: the New update and Review handlers also called text_generation_available(), a second service call under AC 1.
- StatusUpdateFormState has a kept flag besides failure_code, since an OperationResult error code may be None. StatusUpdateOverview did not gain ai_available: the overview view does not use it.
- validate_approval_edit became StatusUpdateEdit.blank_fields() so the approval submission makes one service call (approve_and_publish); the approval test class calls the method.
- form_view_for became two view builders, build_saved_form_view and build_filled_form_view (the save and fill notices differ for the same state); _GENERATE_FAILURE_KEYS moved to slack_views.
- Entry point: a _ModalAction parser replaces the per-handler payload parsing; _approve_and_publish, _read_and_publish, _toggle_and_publish, _render_record, _as_edit, _generate_failure_key and the replace import are gone.

Tests: existing entrypoint and dispatch tests pass with only their stub targets moved from the entry point module to status_update_form, status_update_approval and status_update_history. New: test_incident_scribe_status_update_form_save.py (save, start, open), ..._form_fill.py, ..._approval_publish.py, ..._history_render.py, ..._form_view.py, and TestHandlerDiscipline in ..._status_update_slack.py (AST check: one service call, at most one asyncio.run, body at most 35 lines, no domain import or replace). handle_status_update_command and handle_generate_action are 35 lines each, counting one keyword argument per line.

Gates (app/): ruff check . passed; ruff format --check passed; lint-imports 10 kept, 0 broken; mypy 0 errors in touched files (48 pre-existing elsewhere); pytest tests --ignore=tests/smoke 4603 passed.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-09 19:17
---
Plan approved
---
<!-- COMMENTS:END -->
