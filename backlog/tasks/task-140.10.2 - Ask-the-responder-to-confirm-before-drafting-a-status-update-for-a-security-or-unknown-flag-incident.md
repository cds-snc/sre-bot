---
id: TASK-140.10.2
title: >-
  Ask the responder to confirm before drafting a status update for a security or
  unknown-flag incident
status: In Progress
assignee: []
created_date: '2026-10-07 19:02'
updated_date: '2026-10-07 20:04'
labels:
  - incident
dependencies:
  - TASK-140.10.1
parent_task_id: TASK-140.10
priority: high
type: feature
ordinal: 340000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2 of TASK-140.10, Stack H layer 6. draft_status_update gains security_confirmed (default False) and an injected IncidentSecurityReader; for a YES or UNKNOWN incident it returns permanent error SECURITY_CONFIRMATION_REQUIRED just before a model call is needed (after the PENDING/CARRIED_FORWARD branches, before on_started), so other entry points and future automatic drafting (TASK-140.11) cannot bypass it; a flag read failure also refuses. The Draft handler then updates the modal to a confirmation view (one wording for yes and unknown: the incident is, or may be, a security incident and drafting sends the channel and comms content to the AI model) with a Confirm and draft button (incident.scribe.status_update.draft_confirmed) and Cancel as the view close; the confirm listener calls the service with security_confirmed=True. The Draft button itself is unchanged. The drafting view moves into on_started so it shows only when a model call is imminent. decisions/incident-management.md moves the security confirmation from approval to drafting.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Pressing Draft on a YES or UNKNOWN incident shows the in-modal confirmation view and makes no model call
- [x] #2 Confirm and draft drafts; Cancel or closing makes no model call
- [x] #3 A NO incident drafts as before with no confirmation step
- [x] #4 draft_status_update refuses YES or UNKNOWN without security_confirmed, and refuses on a flag read failure, with no model call and no on_started; PENDING and CARRIED_FORWARD need no confirmation
- [x] #5 The drafting view appears only when a model call is about to happen
- [x] #6 New strings exist in EN and FR with matching keys; nothing is posted to the incident channel
- [x] #7 decisions/incident-management.md places the security confirmation on drafting, not approval
- [x] #8 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Plan 2026-10-07. Layer 6 of Stack H (after TASK-140.10.1), branch stack-h/task-140.10.2-security-draft-confirm. Slice 2 of TASK-140.10.

Decisions
- Human: confirmation is a server-driven confirmation view with a Confirm and draft button (action id incident.scribe.status_update.draft_confirmed); Cancel is the view's close button. One wording for yes and unknown. Draft button unchanged. In-modal views use views.update. Nothing is posted to the incident channel.
- Gate lives in draft_status_update after the PENDING/CARRIED_FORWARD branches and before on_started; refusal is permanent error SECURITY_CONFIRMATION_REQUIRED, so other entry points and TASK-140.11 cannot bypass it. A flag read failure also refuses with the same code (underlying error logged, never shown).
- With security_confirmed=True the flag is not read (confirmation is explicit consent, so a transient read failure is recoverable through the confirm view).
- The drafting view moves into on_started so it shows only when a model call is imminent.
- decisions/incident-management.md moves the security confirmation from approval to drafting.
- Wording (open to change after feedback). EN: "This incident is, or may be, a security incident. Drafting sends the incident channel and comms content to the AI model. Do you want to continue?" Buttons "Confirm and draft" / "Cancel". FR: "Cet incident est, ou pourrait être, un incident de sécurité. La rédaction envoie le contenu du canal de l'incident et des communications au modèle d'IA. Voulez-vous continuer?" Buttons "Confirmer et rédiger" / "Annuler".
- Imports: top level only. No new function-level imports. All function-level imports in the two test files edited in place move to module top. The security reader is imported at module top from core.api (no cycle involved). status_update.py's lazy import in _default_generator is left as is here and removed by TASK-143 (scribe/ports.py, standalone PR off main); whichever lands second rebases onto the other.
- A small private _ModalCursor (view id plus latest hash, one update method that logs and swallows Slack errors) replaces inline hash threading.

Findings (path:line)
- scribe/status_update.py:107-184 draft_status_update: incident id :152-156, store list :158-165, PENDING/CARRIED_FORWARD returns :171-181, on_started :183-184. Gate goes between :181 and :183.
- core/api.py:68-79 IncidentSecurityReader.read_security_flag -> OperationResult[IncidentSecurityFlag] (YES/NO/UNKNOWN; classified error on store failure or missing incident, core/adapters/legacy_incidents.py:70-100); get_incident_security_reader at api.py:176, already in __all__.
- scribe/entrypoints/slack.py:34-80: register() registers only DRAFT_ACTION_ID; handle_draft_action sends the drafting view before the service call (:55-64) and calls draft_status_update(..., on_started=None) (:66-68).
- scribe/platforms/slack.py: DRAFT_ACTION_ID :65, _status_update_view :582, _status_error_text :558, _draft_button_block :633, build_drafting_view :649, build_draft_error_view :667. Only module that translates.
- contracts/operations/codes.py ErrorCode registry has no security code; tests/unit/contracts/operations/test_error_code_registry.py fails on unregistered literals.
- contracts/slack/registrar.py:62 register_block_action requires the incident.scribe. prefix; the new id satisfies it.
- Locales scribe/locales/incident_status_update.{en-US,fr-FR}.yml; parity test test_incident_scribe_status_update_locales.py.
- decisions/incident-management.md: Drafting bullet :80, Approval bullet :82, test bullets ~:133, decision log ~:157.
- Edit-in-place tests: tests/unit/packages/incident/scribe/test_incident_scribe_status_update_entrypoint.py patches draft_status_update in the entrypoint module; test_sends_drafting_view_with_view_id_hash_and_no_button (:100) and test_logs_when_drafting_view_update_fails_but_continues (:363) assume the drafting view precedes the service call and must have the patched service call on_started; test_calls_draft_status_update_with_channel_id_and_user_id (:433) gains security_confirmed=False. test_incident_scribe_status_update_service.py: _draft helper (:171) needs an injected security reader; add _StubSecurityReader beside _StubLookup (:89); model-path tests use a NO reader. No in-memory security reader exists, so inline stubs.

Steps (TDD order; each step starts with its failing tests)
1. Tests first, failing for the right reason (matrix below).
2. contracts/operations/codes.py: add SECURITY_CONFIRMATION_REQUIRED to ErrorCode.
3. scribe/status_update.py: draft_status_update gains security_confirmed: bool = False and security_reader: IncidentSecurityReader | None = None (core.api imports at module top). After the PENDING/CARRIED_FORWARD block and before on_started, a private helper returns None when security_confirmed; otherwise reads the flag: NO proceeds; YES or UNKNOWN refuses (permanent, SECURITY_CONFIRMATION_REQUIRED, info log); a read failure refuses with the same code (warning log with underlying status and code, generic message, no provider text). Update the docstring (on_started now follows the gate; new args; new return code).
4. scribe/platforms/slack.py: CONFIRM_ACTION_ID = "incident.scribe.status_update.draft_confirmed"; build_security_confirmation_view(locale, private_metadata): one wording section, an actions block (block_id draft_confirm_button) with a primary Confirm and draft button, close "Cancel", no notify_on_close. No _status_error_text mapping (the entrypoint handles the code before rendering).
5. Locales EN and FR with the same keys: security_confirmation, confirm_button, cancel (wording above).
6. scribe/entrypoints/slack.py: add _ModalCursor; factor _run_draft(ack, body, client, *, security_confirmed); handle_draft_action calls it with False, new handle_draft_confirmed_action with True; both ack first. on_started callback updates to the drafting view and records the new hash (logs, never raises). On SECURITY_CONFIRMATION_REQUIRED, update to the confirmation view with the click's hash and stop; otherwise render result or error as today. register() also registers CONFIRM_ACTION_ID. Update the module docstring.
7. decisions/incident-management.md: drop the second confirmation from the Approval bullet; add to the Drafting bullet that for a security or unknown-flag incident the responder confirms in the modal after pressing Draft, no model call is made without it, the service refuses, and automatic drafting skips these incidents; add a test bullet and a dated decision-log line.
8. scribe/README.md: one line for the gate and the confirm action.
9. Move function-level imports in the two edited test files to module top.
10. Run gates; check each AC as its test passes.

AC traceability
- AC1: steps 3, 4, 6; entrypoint tests for YES and UNKNOWN (confirmation view with confirm action id and Cancel close, no drafting view) and service tests (no generator call).
- AC2: steps 3, 6; confirm handler passes security_confirmed=True and renders the result; Cancel is view close with no notify_on_close (asserted).
- AC3: service test with a NO reader; entrypoint test of on_started drafting view then result view.
- AC4: service gate tests.
- AC5: step 6; service tests assert on_started not called on refusal, PENDING or CARRIED_FORWARD; entrypoint tests assert no drafting view when the service never calls on_started.
- AC6: locales parity test; no-post_message test on the confirm path.
- AC7: step 7, verified by review and grep.
- AC8: gates.

Test matrix (layered tree)
- Edited in place: test_incident_scribe_status_update_service.py, test_incident_scribe_status_update_entrypoint.py.
- New tests/unit/packages/incident/scribe/test_incident_scribe_status_update_security_gate.py: refuses YES and UNKNOWN; refuses a read failure (store error and NOT_FOUND) with the same code and no provider text; NO drafts; security_confirmed=True drafts for YES, UNKNOWN and a failing reader without calling the reader; every refusal makes no generator call, no on_started and no store append; PENDING and CARRIED_FORWARD with a raising reader never consult it; refusal log carries no incident text.
- New tests/unit/packages/incident/scribe/test_incident_scribe_status_update_confirmation.py: confirmation view (button action id, Cancel close, no notify_on_close, EN and FR text); register() registers both ids on a fake registrar; Draft handler turns the refusal into a confirmation views.update using the click's hash; confirm handler acks first, passes security_confirmed=True, renders the result; drafting-view and confirmation-view update failures are logged, not raised; no chat.postMessage or postEphemeral on either path.
- Existing error-code registry and locales parity tests cover the new code and keys.

Assumptions and doubts (verify)
- on_started runs inside asyncio.run on the sync handler thread, so a synchronous views_update there blocks nothing else (entrypoints/slack.py:44; no other task in that loop).
- The click's view hash on the confirmation view is current since nothing updates the view between Draft and the gate (entrypoint test asserts the body hash is used).
- A views.update-ed view's close button closes the modal and sends no event without notify_on_close (Slack documented behavior).
- get_incident_security_reader() constructs without side effects (default-path test with a monkeypatched provider).
- No other caller of draft_status_update exists (rg draft_status_update app --glob '*.py'; only the entrypoint now, TASK-140.11 later).

Blast radius and rollback
- A wrong gate either blocks drafting for all incidents or lets a security incident reach the model; both covered by the matrix. UNKNOWN covers every incident declared before the flag was stored, so older incidents now show the confirmation (intended).
- One git revert restores the previous behavior; the 140.10.1 field and stored attribute stay, so no data rollback. Never revert the Incident field.
- Ordering: #1548 must not deploy before this layer merges. TASK-143 and this PR are independent; whichever lands second rebases.

Size: about 8-9 production files (codes.py, status_update.py, platforms/slack.py, entrypoints/slack.py, two locales, decisions record, scribe README), about 150-190 production LOC, one subsystem; within the single-PR gate.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Plan approved by the human 2026-10-07.

Implemented to plan. Files: contracts/operations/codes.py (+1), scribe/status_update.py (security gate helper, ~50), scribe/platforms/slack.py (confirmation view, ~37), scribe/entrypoints/slack.py (_ModalCursor, _run_draft, confirm handler, ~95), two locale files (+3 each), decisions/incident-management.md, scribe/README.md.
Gates (app/): ruff check All checks passed; ruff format --check 826 files already formatted; lint-imports 10 kept, 0 broken; mypy 57 errors in 20 files, all pre-existing legacy modules, 0 in touched files; pytest tests --ignore=tests/smoke 6 failed, 3967 passed (the known SNS x3 and google-directory x3 order leaks). PLC0415: only the existing status_update._default_generator lazy import.
AC7 grep (decisions/incident-management.md): the Approval bullet no longer says 'second confirmation'; the Drafting bullet states the responder confirms in the modal after Draft; a test bullet and the 2026-10-07 decision-log line record the move from approval to drafting.
Deviation: pre-authored tests needed fixes that keep their intent: service test helper had no default NO security reader (added _StubSecurityReader); gate tests compared store list to [] (store returns a tuple) and used readers returning a message newer than the cutoff for the PENDING/CARRIED_FORWARD cases (StubReader treats [] as default); entrypoint tests asserted a drafting view call when the mocked service never calls on_started (>=2 -> >=1, result-failure side_effect); plugin registration test asserted exactly one draft block action (now draft and draft_confirmed).

Review fix: the security gate now logs through the service's bound logger, so refusal logs carry incident_id like every other draft_status_update log. The log test now asserts that incident_id is present and that the transcript text is absent; it previously forbade incident_id, which misread 'no incident text'. Gates after the fix, run from app/: ruff check passed; ruff format --check: 826 already formatted; lint-imports 10 kept 0 broken; mypy 0 errors in touched files; pytest 3967 passed and 6 failed, the 6 being the known SNS/google-directory order leaks. PLC0415: only status_update.py:383 (_default_generator, removed by TASK-143). The test-file hit in test_incident_scribe_status_update_slack.py:36 is in a layer 3-4 file this layer does not touch.
<!-- SECTION:NOTES:END -->
