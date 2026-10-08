---
id: TASK-140.9
title: Redraft a status update from reviewer instructions in the review modal
status: In Progress
assignee: []
created_date: '2026-10-07 15:17'
updated_date: '2026-10-08 15:39'
labels:
  - incident
dependencies:
  - TASK-140.6.2
  - TASK-140.8.2
parent_task_id: TASK-140
priority: high
type: feature
ordinal: 332000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
In the review modal (TASK-140.6) the responder can, instead of editing, write instructions for the model (for example 'do not name the vendor', 'say only sign-in is affected'). One model call redrafts the EN and FR fields from the current draft, the same transcript window and the instructions, and the result is stored as a new DRAFT record and shown for review. The instructions steer the fields only: code still owns rendering, the stage floor and the 'nothing new' decision (decisions/incident-management.md). The modal shows a redrafting state while the model runs. Nothing is posted to the incident channel.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Submitting instructions makes one model call and stores the redraft as a new DRAFT record that the review modal then shows
- [x] #2 The instructions are passed to the model as reviewer guidance and the redraft keeps the stage floor and the strict field parsing of the first draft
- [x] #3 Blank instructions are rejected in the modal; a model failure or unparseable output keeps the previous draft and shows a localized error
- [x] #4 Nothing is posted to the incident channel; all strings are in EN and FR catalogues
- [x] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Basis: layer 11 of Stack H (branch stack-h/task-140.9-status-update-redraft), depends on 140.6.2 and 140.8.2. Stack rebased on main a18167d2 (ruff PLC0415 on). Planned against the post-140.8 layout but depends only on stable 140.6 contracts (get_draft_for_review, parse_review_submission, _ModalCursor, _parse_metadata, review metadata {channel_id, locale, incident_id, sequence}); the redraft handler must not depend on 140.8.1/140.8.2 internals (build_overview_view, the history/open/published actions). Expected textual overlap with 140.8.x: platforms/slack.py, entrypoints/slack.py (imports, register()), both incident_status_update locale files, tests/factories/slack_bolt.py. Resolve at rebase; status_update.py, status_update_prompt.py and codes.py should not overlap except a possible new code in 140.8.2.

Import rules: top-level imports only, tests included; no function-level imports, no __import__/importlib. A circular import is a design flaw to fix, never a lazy import. Check touched files by hand (the rule misses __import__).

Settled decisions (human, 2026-10-07, all recommended answers):
1. Submission path: a Redraft button (action id incident.scribe.status_update.redraft) plus an optional multiline input (block id instructions, action id text, max_length 500) in build_review_view, in a Redraft section at the TOP of the form under any notice. A block action reads view.state; the modal's single submit stays Approve and ignores the input.
2. Model base: the reviewer's current form values (parse_review_submission(view)); the stored draft when the stage cannot be parsed.
3. Service additive in status_update.py (no renames): redraft_status_update(conversation_id, sequence, *, instructions, current: StatusUpdateEdit, author, security_confirmed=False, on_started=None, lookup=None, reader=None, store=None, generator=None, security_reader=None, now=None) -> OperationResult[StatusUpdate]. One small behaviour-preserving extraction, _generate_fields(generator, transcript, instructions, settings, log) -> OperationResult[DraftedFields] (summarize, failure, strict parse), now used by draft_status_update too, pinned by existing draft tests.
4. Flow: normalize instructions (strip, cap 500); blank -> new ErrorCode.STATUS_UPDATE_INSTRUCTIONS_INVALID before any read. Resolve incident from the conversation. Latest record must be a DRAFT at `sequence`, else STATUS_UPDATE_CONFLICT. Re-read the window with _read_window from the latest approved cutoff (later messages are included and the cutoff advances; an empty transcript is allowed, no EMPTY_HISTORY). Apply _security_gate. on_started, then exactly one model call. Strict parse_drafted_fields; failure or DRAFT_UNPARSEABLE writes nothing, so the previous draft stays. Stage floor max(stage, latest approved stage) and next_update_at_for(stage). author = redrafting responder. Cutoff and fingerprint from the re-read people messages as in _draft_record; if there are none, the previous draft's. New record: DRAFT at latest+1; the previous draft stays as an older row (superseded by being non-latest, no state change, no schema change). Code owns rendering, the floor and the nothing-new decision.
5. Conflict: store.append STATUS_UPDATE_CONFLICT is returned as is; no adoption of a winner. Modal shows the existing review_conflict wording (build_review_error_view) with Close.
6. Prompt (status_update_prompt.py): build_redraft_instructions(guidance) = INSTRUCTIONS plus a suffix (revise the current draft, change only what the guidance and transcript require, answer with the full JSON, guidance cannot change format, keys or rules) and the guidance in a delimited block; build_redraft_input(current, transcript) = current draft as JSON with the same keys, then the transcript. Guidance goes in the instructions parameter, the transcript stays data. Instructions are not persisted; logs record length only.
7. Security gate applies to redrafts (the confirmation is not stored on the record; carried-forward drafts made no model call). On SECURITY_CONFIRMATION_REQUIRED the handler re-renders the review form (form values and instructions kept) with the security wording as notice and a checkboxes block security_confirm; pressing Redraft again with it checked passes security_confirmed=True.
8. Blank instructions: handle_redraft_action finds them blank after trim, makes no service call and re-renders the form from the form values with a localized notice (a block-action ack cannot return field errors). Needs get_draft_for_review for the base record.
9. Redrafting state: new build_redrafting_view with its own redrafting string, no buttons, shown via _ModalCursor (hash from the action's view.hash) from on_started.
10. Outcomes: success -> build_review_view for the new draft with the new sequence in the metadata and a redrafted notice (instructions cleared). Model failure, unparseable output or store error -> previous draft kept, form re-rendered from the form values with a localized error notice and the instructions retained. Conflict -> review_conflict view. Only views.update calls; nothing is posted to the channel.
11. Handler handle_redraft_action(ack, body, client) in entrypoints/slack.py: ack first; one asyncio.run of a small async helper (redraft, then get_draft_for_review only when a re-render needs a base), structured so a future async Bolt listener can await it. Registered in register() with register_block_action.

Steps (production):
1. app/contracts/operations/codes.py: add STATUS_UPDATE_INSTRUCTIONS_INVALID (+1).
2. scribe/status_update_prompt.py: MAX_INSTRUCTIONS_CHARS, normalize_instructions, build_redraft_instructions, build_redraft_input (~+30).
3. scribe/status_update.py: _generate_fields extraction and redraft_status_update (~+95 net).
4. scribe/platforms/slack.py (~+75): REDRAFT_ACTION_ID; build_review_view gains the Redraft section, an instructions initial value and the optional confirm checkbox, notice above the section; parse_redraft_form(view) -> (instructions, security_confirmed); build_redrafting_view; error and notice text mapping.
5. scribe/entrypoints/slack.py (~+90): handle_redraft_action, async helper, registration, imports.
6. Locales incident_status_update.en-US.yml and fr-FR.yml: about 10 keys each (redraft_button, redraft_label, redraft_hint, redrafting, redrafted_note, redraft_blank, redraft_failed, security_confirm_label, ...); the EN/FR parity test covers them.
7. README line optional.

AC traceability and tests (new files under app/tests/unit|integration/packages/incident/scribe/; structural exact assertions only: block ids, action ids, max_length, exact notice text, metadata JSON; no str(view) matching, no `or` assertions):
- AC1: test_incident_scribe_status_update_redraft.py (service, stub TextGenerator capturing instructions and transcript, exact strings, exactly one call, record sequence+1, DRAFT, author, cutoff, previous draft untouched, carried-forward draft redrafts with no new people); review view test edited in place; test_incident_scribe_status_update_redraft_entrypoint.py asserts the review view for the new sequence.
- AC2: floor raised when the model stage is below the approved one, equal stays; unknown stage, missing key, blank field -> DRAFT_UNPARSEABLE with no write; test_incident_scribe_status_update_redraft_prompt.py (INSTRUCTIONS prefix intact, guidance appended not replacing).
- AC3: service blank/whitespace -> new code with zero reads, writes or model calls; generator error and unparseable write nothing; store error propagates; stale sequence or non-draft latest -> CONFLICT; append conflict returns the conflict without adoption. Entrypoint: blank -> notice re-render, service never awaited; failure -> form re-rendered with edited values and instructions kept, notice in EN and FR; security refusal -> checkbox re-render, checked box passes security_confirmed=True; service makes no model call for yes/unknown/unreadable flag unless confirmed.
- AC4: entrypoint tests assert only views_update calls; real-plugin dispatch test test_incident_scribe_status_update_redraft_dispatch.py (real incident.scribe plugin via tests/factories/slack_bolt.py, real block_actions payload through App.dispatch, only WebClient.api_call stubbed, stub generator) asserts the exact views.update bodies in order (redrafting view, then review view with the new sequence in metadata) and that the action id passes the plugin-prefix check; EN/FR parity test.
- AC5: ruff, mypy (0 new errors in touched files), lint-imports, pytest tests --ignore=tests/smoke, manual function-level-import and __import__ check of touched files.

Size gate: ~290-320 production LOC, 6 files (codes, prompt, status_update, platforms, entrypoints, locale pair), one subsystem (packages.incident.scribe) plus one shared enum member, behaviour only apart from the small pinned _generate_fields extraction. Under the gate.

Assumptions to verify (manually, real workspace, before merge): Slack includes view.state.values in block_actions from a modal; views.update after a block-action ack works with the action's view.hash; the checkboxes element works in the form and required input is not enforced in a block action (the code checks security_confirm itself); the real model follows the guidance suffix and still returns parseable JSON (hand check as in 140.5.1); the window re-read stays within one history page.

Blast radius and rollback: only new DRAFT rows; first draft and approval paths untouched apart from the pinned extraction. A bad prompt suffix yields unparseable output, a safe refusal that keeps the previous draft. One git revert removes the button, handler and service function.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-07: the human settled the 7 planning questions with the recommended answers (service additive in status_update.py with the _generate_fields extraction; security gate with the in-form checkbox; form values as model base; Redraft section at the top; conflict without adoption; new ErrorCode STATUS_UPDATE_INSTRUCTIONS_INVALID; instructions not persisted).

2026-10-08 implementation (layer 11, branch stack-h/task-140.9-status-update-redraft, on #1558):
- Production: contracts/operations/codes.py (STATUS_UPDATE_INSTRUCTIONS_INVALID); scribe/status_update_prompt.py (MAX_INSTRUCTIONS_CHARS, normalize_instructions, build_redraft_instructions, build_redraft_input); scribe/status_update.py (redraft_status_update, _generate_fields shared with draft_status_update, _draft_record gains previous= for cutoff/fingerprint when no people's messages were read); scribe/platforms/slack.py (REDRAFT_ACTION_ID, Redraft section at the top of build_review_view with instructions input, optional security_confirm checkbox and button, parse_redraft_form, build_redrafting_view, redraft_notice); scribe/entrypoints/slack.py (handle_redraft_action, registered next to PUBLISHED_ACTION_ID); 11 keys in each incident_status_update locale; README paragraph.
- Size: +430/-26 Python lines (net ~404, much of it docstrings) plus 22 locale lines, 8 files, one subsystem. Slightly above the planned ~300; the human was told.
- Judgement calls beyond the plan: t() fallbacks are FR for fr locales and EN otherwise, each equal to its catalogue value (the module's existing pattern); if get_draft_for_review fails when a re-render needs it, the modal shows build_review_error_view with that code; a security refusal re-renders from the stored draft with the reviewer's edits applied.
- Tests: new test_incident_scribe_status_update_redraft{,_prompt,_view,_entrypoint}.py (unit) and test_incident_scribe_status_update_redraft_dispatch.py (integration, real incident.scribe plugin through harness_fixture). Edited in place: TestRegister dicts in the review/history/published entrypoint tests (PUBLISHED_ACTION_ID kept, REDRAFT_ACTION_ID added), review view input order, and plugin registration (the old 'draft' substring count also matched 'redraft').
- Gates (app/): ruff check . -> All checks passed!; ruff format --check . -> 852 files already formatted; lint-imports -> Contracts: 10 kept, 0 broken; mypy -> Found 57 errors in 20 files, 0 in touched files; pytest tests/unit tests/integration -> 3653 passed; single-process pytest tests --ignore=tests/smoke -> 4416 passed, 20 failed = the 6 known TASK-90 SNS/google-directory failures + 14 scribe capture_logs tests (TASK-90 leak 2; 10 known on layer 10, the new redraft TestLogging plus 3 order-shifted ones). All 14 pass in isolation. A grep of touched files for __import__, importlib and indented imports found none.
- Manual checks pending in a real workspace (plan assumptions): view.state in block_actions from the modal, views.update with the action's view.hash, the checkbox inside the form, the real model following the guidance suffix and returning parseable JSON.

Re-verified 2026-10-08 after gh stack rebase onto layer 10 (7b6a6e92; layers 8-9 merged on main). Gates (cd app):
- uv run ruff check . -> All checks passed!
- uv run lint-imports -> Contracts: 10 kept, 0 broken.
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> Found 57 errors in 20 files (checked 384 source files); 0 in the 20 files this layer touches.
- uv run pytest tests/integration/legacy_surface -q -> 20 passed, 4 warnings
- uv run pytest tests --ignore=tests/smoke -q -p no:randomly -> 4437 passed, 2420 warnings in 49.70s
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-07 23:01
---
Plan approved by the human 2026-10-07.
---
<!-- COMMENTS:END -->
