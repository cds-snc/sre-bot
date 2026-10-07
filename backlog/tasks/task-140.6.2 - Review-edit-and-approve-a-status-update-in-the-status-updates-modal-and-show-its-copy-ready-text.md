---
id: TASK-140.6.2
title: >-
  Review, edit and approve a status update in the status-updates modal and show
  its copy-ready text
status: In Progress
assignee: []
created_date: '2026-10-07 18:52'
updated_date: '2026-10-07 22:24'
labels:
  - incident
dependencies:
  - TASK-140.6.1
parent_task_id: TASK-140.6
priority: high
type: feature
ordinal: 338000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slack slice of TASK-140.6. A Review button beside Draft on views showing a DRAFT (value carries incident_id and sequence) replaces the status-updates modal in place (views.update with view id and hash) with the review modal: stage select and the four EN and four FR fields prefilled. The view submission listener (scribe/entrypoints/slack.py, registered through the TASK-140.2 registrar) acks with response_action errors for invalid fields, otherwise acks with a saving view, calls approve_status_update and updates the view to the copy-ready text: one preformatted block per language under EN and FR headings (verify modal support and copy fidelity). Errors show as an in-modal error view with Close. Label builders and t() stay in scribe/platforms/slack.py. Nothing is posted to the incident channel. Real-provider dispatch coverage for the block action and the view submission, as for the 1d7db039 command-dispatch fix.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The Review button opens the review modal in place with the draft's EN, FR and stage prefilled
- [x] #2 Submitting with a blank field shows field errors in the modal and does not call the service
- [x] #3 A valid submit approves the record and the modal shows the copy-ready EN and FR text; service refusals and conflicts show an in-modal error with Close
- [x] #4 No message is posted to the incident channel
- [x] #5 Block action and view submission dispatch through a real SlackPlatformProvider in an integration test
- [ ] #6 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Basis: planned against the post-#1552 layout (entrypoints/slack.py uses `from packages.incident.scribe import providers` and `from packages.incident.scribe.status_update_approval import ...`). Consumes the TASK-140.6.1 contract as amended: StatusUpdateEdit, CopyReadyText, validate_approval_edit (pure), get_draft_for_review and approve_status_update both `async def`, providers.get_status_page_publisher() with async publish(update, labels_en=, labels_fr=), and the codes STATUS_UPDATE_FIELDS_INVALID / STAGE_BELOW_FLOOR / CONFLICT / NOT_APPROVED. Imports top level only, tests included; graph has no cycle (entrypoints.slack -> platforms.slack, status_update_approval, providers, domain; nothing imports entrypoints). t(), label builders, view builders, block-id constants and the submission parser stay in scribe/platforms/slack.py.

Settled decisions (human, 2026-10-07):
1. Service refusal after the saving view shows a Close-only in-modal error view (edits are lost; the draft stays DRAFT and Review reopens it). Possible follow-up, not in scope: re-render the form from the submitted values with a notice.
2. Copy-ready text is one rich_text block holding one rich_text_preformatted element per language under EN and FR headers. Verify rendering and copy fidelity manually in a real workspace; fallback is a fenced mrkdwn section split into chunks.
3. get_draft_for_review and approve_status_update are async (same precedent as draft_status_update: sync store called inline; when the core store goes async only the store calls inside the service change). Listeners run each service call with asyncio.run, as the Draft listener does (entrypoints/slack.py:113). The submit path runs approve and publish together in ONE asyncio.run of a small async helper (one event loop per submission). The helper is structured so a future async Bolt listener can await it directly (the pivot path). Unit tests stub the async functions.
4. Review button: pending view shows Draft and Review; the Draft-result view shows Review only; none on no-pending, error, confirmation or drafting views.
5. Dispatch-test harness: extract Harness and its fixture builder from tests/integration/integrations/slack/test_slack_provider_listener_dispatch.py into tests/factories/slack_bolt.py with a plugin-name parameter (test-only, existing test edited in place) and reuse it.
6. Stage select offers all four stages; the service enforces the forward-only floor and STATUS_UPDATE_STAGE_BELOW_FLOOR is the safety net.
Also settled in design: review inputs are optional:true so validate_approval_edit is the single blank-handling path (whitespace included); no chat_* call anywhere.

Design:
- Review button: action id incident.scribe.status_update.review, value JSON {incident_id, sequence} from the rendered StatusUpdate. `_draft_button_block` becomes an actions-block builder over (locale, update | None, with_draft).
- handle_review_action: ack; asyncio.run(get_draft_for_review(incident_id, sequence)); success -> views_update in place (view id and hash from the body) via _ModalCursor with build_review_view; failure (STATUS_UPDATE_CONFLICT, store error) -> build_draft_error_view with Close. Slack failures logged, never raised.
- build_review_view(update, locale, private_metadata, notice=None): callback_id incident.scribe.status_update.approve, Approve submit and Cancel close; private_metadata JSON {channel_id, locale, incident_id, sequence}; stage static_select (block id `stage`, initial_option from the draft, stage names in the invoker's locale); EN header + four multiline plain_text_input, FR header + four, block ids equal to the validate_approval_edit field names (en.impact, fr.workaround, ...), labels from build_profile_labels("en-US") / ("fr-FR").
- handle_review_submission (registrar.register_view_submission): parse_review_submission(view) -> StatusUpdateEdit | None (None on missing/unknown stage -> ack errors on `stage`); blank fields -> ack(response_action="errors", errors={block_id: localized "Enter a value"}) from validate_approval_edit, service not called; otherwise ack(response_action="update", view=saving view), then one asyncio.run of an async helper that calls approve_status_update(incident_id, sequence, approver=body["user"]["id"], edit=edit) then providers.get_status_page_publisher().publish(update, labels_en=build_profile_labels("en-US"), labels_fr=build_profile_labels("fr-FR")); success -> views_update by view id (no hash) to build_copy_ready_view; any non-success -> build_draft_error_view(code, ...). Ack precedes the service call (3 s window).
- build_copy_ready_view(copy, locale, private_metadata): approved note ("Approved. Proofread, then copy into your product's channel. Nothing was posted."), EN header + preformatted block, FR header + preformatted block, Close only.
- _status_error_text gains STAGE_BELOW_FLOOR (stage_below_floor), CONFLICT while reviewing (review_conflict: changed or approved elsewhere, reopen the status updates); NOT_APPROVED and others use the generic error.
- Locale: ~14 new keys in incident_status_update.{en-US,fr-FR}.yml (review_button, approve_button, review title/note, field_blank, saving, approved_note, stage_below_floor, review_conflict, ...); existing EN/FR parity test covers them.

Steps: (1) platforms/slack.py: constants, button block, build_review_view, parse_review_submission, build_review_field_errors, build_saving_view, build_copy_ready_view, error cases, pass `update` at the two call sites. (2) locale files. (3) entrypoints/slack.py: handle_review_action, handle_review_submission, async approve-and-publish helper, shared view-context helper, two more registrations; reuse _ModalCursor and _parse_metadata. (4) optional README line. (5) tests/factories/slack_bolt.py harness extraction.

AC traceability and tests (new files under app/tests/unit/packages/incident/scribe/ and app/tests/integration/packages/incident/scribe/):
- AC1 Review opens in place prefilled: steps 1,3; test_incident_scribe_status_update_review_view.py (button placement, value, 8 inputs + select, initial values/options, block ids), test_incident_scribe_status_update_review_entrypoint.py (views_update with hash; conflict -> error view; Slack failure logged), dispatch test.
- AC2 blank -> field errors, no service call: step 3; entrypoint test (each of the 8 fields, whitespace; approve mock never awaited), dispatch test asserts the ack body.
- AC3 valid submit approves and shows copy-ready; refusals/conflicts in-modal error with Close: step 3; entrypoint tests (approver id, edit passed, each error code mapped, publish failure, update failure logged, update without hash), copy-ready view test (one rich_text_preformatted per language, exact text).
- AC4 nothing posted: entrypoint tests assert only views_update client calls; dispatch test asserts recorded api_calls are only views.update.
- AC5 real-provider dispatch: test_incident_scribe_status_update_review_dispatch.py registers the real packages.incident.scribe plugin as `incident.scribe` on a real pluggy manager and SlackPlatformProvider, dispatches a real block_actions and view_submission through App.dispatch with only WebClient.api_call stubbed, asserts ack bodies (errors; response_action update with the saving view) and views.update calls, and proves ids pass the plugin-prefix check at boot.
- AC6 gates: ruff, mypy (0 new errors in touched files), lint-imports, pytest tests --ignore=tests/smoke, manual function-level-import check of touched files.

Size gate: ~340 production LOC (+-15%: platforms/slack.py ~200, entrypoints/slack.py ~110, locales ~32), 4 files (5 with README), one subsystem, all new behavior, no mechanical refactor; under the gate. If it nears 400, trim README and secondary polish first (a form-only / submit-only split is not independently useful).

Assumptions to verify: validate_approval_edit field names equal en.impact etc. (140.6.1 gives them as "e.g."); Slack accepts views.update by view id after a submission ack with response_action update; rich_text_preformatted renders and copies faithfully in a modal; import-linter contracts unaffected (platforms.slack -> infrastructure.i18n already ignored).

Blast radius and rollback: first layer that writes (APPROVED records). One revert removes the button and listeners; APPROVED records already written stay valid for TASK-140.5.1 draft logic. No env/terraform/manifest changes.

For later layers: TASK-140.8 reuses build_copy_ready_view and a shared copy-ready helper (publish plus error view) in entrypoints/slack.py, plus the cursor and metadata helpers. TASK-140.9 extends build_review_view (update and optional notice args allow in-place re-render), reuses block ids, parse_review_submission and metadata shape, and imports REVIEW_ACTION_ID, REVIEW_CALLBACK_ID and the field-name constants.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-07: the 6 planning questions were settled by the human on 2026-10-07: async get_draft_for_review/approve_status_update for Q3 (approve and publish in one asyncio.run helper, pivot path to an async Bolt listener), the recommended answers for Q1, Q2, Q4, Q5 and Q6. Re-rendering the form with submitted values on a refusal is a possible follow-up, not in scope.

Implemented 2026-10-07. Files (production, +added lines): scribe/platforms/slack.py +159/-12, scribe/entrypoints/slack.py +130/-3, locales en-US/fr-FR +8 each; about 305 LOC, 4 files, README skipped. Gates: ruff format --check clean (837 files); mypy 57 errors in 20 files, all pre-existing in modules/*, 0 in touched files; lint-imports 10 kept 0 broken; pytest tests/unit tests/integration 3376 passed and legacy set 783 passed (make test split green). Single-process pytest tests --ignore=tests/smoke: the 6 known TASK-90 failures plus 4 log-capture failures (2 draft entrypoint tests, 2 review entrypoint tests) caused by the new dispatch test being the first to call the module logger.bind under a cached structlog config; same TASK-90 leak class, passes in every split run. ruff check . reports 3 unused imports in tests/integration/integrations/slack/test_slack_provider_listener_dispatch.py (harness extraction leftover, not touched here). Deviation: added build_review_error_view (required by the pre-authored tests) because the review CONFLICT wording differs from the drafting conflict; _status_error_text is unchanged. Manual check needed in a real workspace: rich_text_preformatted rendering and copy fidelity in a modal, and views.update by view id after a view_submission update ack. AC6 left unchecked pending the ruff and single-process items above.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-07 21:25
---
Plan approved by the human 2026-10-07.
---
<!-- COMMENTS:END -->
