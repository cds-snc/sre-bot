---
id: TASK-140.6.1
title: >-
  Approve a status update and render its copy-ready bilingual text in the scribe
  service
status: Done
assignee: []
created_date: '2026-10-07 18:52'
updated_date: '2026-10-08 15:49'
labels:
  - incident
dependencies:
  - TASK-140.10.2
parent_task_id: TASK-140.6
priority: high
type: feature
ordinal: 337000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Platform-neutral slice of TASK-140.6, no Slack code. Adds StatusPagePublisher (scribe/publisher.py) with a pure render_copy_ready(update, labels_en, labels_fr) that TASK-140.8 reuses, the copy-ready adapter (scribe/adapters/copy_ready.py), and get_draft_for_review plus approve_status_update (scribe/status_update_approval.py). Approval: all four fields in each language non-blank after trim; target must be the latest record, a DRAFT, at the given sequence; stage may not be below the latest non-draft record's stage; next_update_at recomputed only when the stage changes; StatusUpdateStore.transition(..., expected_state=DRAFT) to APPROVED with approver, approved_at, en, fr, stage. A repeated identical submit is success; a different concurrent approval is PERMANENT_ERROR STATUS_UPDATE_CONFLICT. Approval stops at APPROVED: no PUBLISHED write. Copy-ready text is structured plain text (label lines, a blank line between sections) that pastes cleanly into plain-text and Markdown targets.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 approve_status_update stores APPROVED with approver, approved_at and the edited EN, FR and stage, and never sets PUBLISHED
- [x] #2 Blank or whitespace-only fields in either language are refused before any write, naming the fields
- [x] #3 A stage below the latest approved stage, a stale sequence or a non-draft target is refused; a repeated identical submit succeeds; a different concurrent approval returns STATUS_UPDATE_CONFLICT
- [x] #4 The copy-ready publisher returns EN and FR structured plain text identical to render_copy_ready, with no side effects
- [x] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Rebase dependency: PR #1552 (TASK-143) merges to main first and this layer is rebased onto it. Plan against the post-#1552 layout: Protocols live in scribe/ports.py (IncidentDocumentStore, IncidentReportLinkLookup, TextGenerator), status_update.py and service.py import `from packages.incident.scribe import providers` and `from packages.incident.scribe.ports import ...`. The new StatusPagePublisher Protocol goes in scribe/ports.py. Any function-level import left in a touched file after the rebase is fixed in this PR.

Import rules: top-level imports only, tests included. A circular import is a design flaw to fix in the design, never a lazy import (ruff PLC0415 is not enabled, check touched files manually). Planned graph has no cycle: publisher.py -> comms_profile, scribe.domain, core.api; adapters/copy_ready.py -> publisher; providers.py -> adapters/copy_ready; status_update_approval.py -> core.api, scribe.domain, scribe.settings, status_update (status_update does not import the approval module).

Settled design decisions (human, 2026-10-07):
1. next_update_at helper is made public in status_update.py as next_update_at_for (rename of _next_update_at, two internal call sites); approval imports it.
2. approve_status_update returns only the APPROVED StatusUpdate; the caller calls the publisher separately (approval is language- and label-free; TASK-140.8 reuses the publisher alone).
3. Three new ErrorCodes: STATUS_UPDATE_FIELDS_INVALID, STATUS_UPDATE_STAGE_BELOW_FLOOR, STATUS_UPDATE_NOT_APPROVED. A stale sequence or a non-draft target reuses STATUS_UPDATE_CONFLICT.
4. StatusPagePublisher is async and takes labels_en and labels_fr (ProfileLabels): async def publish(update, *, labels_en, labels_fr) -> OperationResult[CopyReadyText]. The only adapter is pure.
5. comms_profile gains render_profile_sections(...) -> tuple[str, ...]; render_profile becomes "\n".join(sections) with unchanged output; copy-ready joins sections with a blank line, so draft rendering and copy-ready cannot drift.
6. Replay is success only for the same approver and identical en, fr and stage; any other approved or published target is STATUS_UPDATE_CONFLICT.
7. The publisher refuses a DRAFT with STATUS_UPDATE_NOT_APPROVED.
8. get_draft_for_review and approve_status_update are async def, following draft_status_update (async def calling the sync StatusUpdateStore inline; the Slack listener runs it with asyncio.run). Pivot path: the core StatusUpdateStore stays sync (changing the core Protocol is out of scope); when the codebase moves the store to async, only the store calls inside these functions gain await; signatures and callers do not change. validate_approval_edit and render_copy_ready stay sync (pure, no I/O); the publisher is already async.

Steps (production):
1. app/contracts/operations/codes.py: add the three codes (~6 LOC).
2. scribe/domain.py: frozen dataclasses StatusUpdateEdit(stage, en, fr) and CopyReadyText(en, fr) (~25).
3. scribe/comms_profile.py: add render_profile_sections; render_profile delegates (~10).
4. scribe/publisher.py (new): pure sync render_copy_ready(update, labels_en, labels_fr) -> CopyReadyText; per language "\n\n".join(sections), stored next_update_at, RESOLVED omits the next-update line (~30).
5. scribe/ports.py: StatusPagePublisher Protocol (~15).
6. scribe/adapters/copy_ready.py (new): CopyReadyPublisher returns render_copy_ready wrapped in success; refuses DRAFT with STATUS_UPDATE_NOT_APPROVED; no side effects (~30).
7. scribe/providers.py: cached get_status_page_publisher() (~8).
8. scribe/status_update.py: rename _next_update_at to public next_update_at_for (~6).
9. scribe/status_update_approval.py (new, ~150):
   - validate_approval_edit(edit) -> tuple[str, ...]: sync and pure, blank field names after trim (e.g. en.impact, fr.workaround), used by 140.6.2 for modal field errors.
   - async def get_draft_for_review(incident_id, sequence, *, store=None) -> OperationResult[StatusUpdate]: latest record only if a DRAFT at that sequence, else STATUS_UPDATE_CONFLICT or the store's error. Calls the sync store inline (decision 8).
   - async def approve_status_update(incident_id, sequence, *, approver, edit, store=None, now=None) -> OperationResult[StatusUpdate], in order: (a) validate, blanks -> STATUS_UPDATE_FIELDS_INVALID naming the fields, before any read or write; (b) list_for_incident, latest sequence != given -> STATUS_UPDATE_CONFLICT; (c) target APPROVED with same approver and identical en/fr/stage -> success with stored record, any other non-draft -> STATUS_UPDATE_CONFLICT; (d) stage below the latest non-draft record's stage (_STAGE_ORDER) -> STATUS_UPDATE_STAGE_BELOW_FLOOR; (e) replace(draft, state=APPROVED, approver, approved_at=now, en, fr, stage), next_update_at recomputed via next_update_at_for only when the stage changed; (f) store.transition(..., expected_state=DRAFT) inline; on conflict one re-read, same approval -> success, otherwise STATUS_UPDATE_CONFLICT. Never sets PUBLISHED. Structured logs with incident_id, sequence, approver.
10. scribe README: one line for the approval service and publisher (drop if the gate is tight).

Size gate: ~280-300 production LOC, 9-10 files (3 new modules + codes, domain, comms_profile, ports, providers, status_update, optional README), one subsystem (scribe plus one shared enum), all behavior with one in-file rename. Under the gate. Not wired to any entrypoint, so one git revert restores service.

AC traceability and tests (app/tests/unit/packages/incident/scribe/, InMemoryStatusUpdateStore, fixed now). Tests of the async functions are `async def` with @pytest.mark.asyncio, the existing style of the draft_status_update tests (asyncio_mode is auto); pure sync functions get plain tests:
- AC1 (APPROVED stored with approver, approved_at, edited en/fr/stage; never PUBLISHED): step 9; test_incident_scribe_status_update_approval.py (stored fields, published_at None, state APPROVED).
- AC2 (blank/whitespace refused before any write, naming fields): step 9; same file (parametrized over all 8 fields, whitespace-only, counting fake store asserts zero calls, message names fields; validate_approval_edit directly as a sync test).
- AC3 (stage floor, stale sequence, non-draft refused; identical replay succeeds; different concurrent approval -> STATUS_UPDATE_CONFLICT): step 9; same file (stage below floor refused, equal stage OK, stale sequence, approved target, identical replay success, different approver or content conflict, next_update_at kept on same stage and recomputed on change including RESOLVED, store list and transition errors propagate; get_draft_for_review returns a DRAFT at the sequence and refuses stale or non-draft).
- AC4 (publisher returns EN and FR identical to render_copy_ready, no side effects): steps 3-7; test_incident_scribe_status_update_publisher.py (sync render_copy_ready: layout, label lines, blank line between sections, RESOLVED omits next-update line, Toronto time) and test_incident_scribe_copy_ready_adapter.py (async publish output equals render_copy_ready, DRAFT refused with STATUS_UPDATE_NOT_APPROVED, store untouched); existing test_incident_scribe_comms_profile_render.py edited in place proves render_profile output unchanged.
- AC5 (gates): ruff, mypy (0 new errors in touched files), lint-imports, pytest tests --ignore=tests/smoke, plus manual check for function-level imports in touched files.

Assumptions to verify: post-#1552 names and imports in status_update.py match the plan; no exhaustive-enum test breaks on new ErrorCode members (grep tests for ErrorCode); the Slack modal value carries incident_id and sequence so approval needs no conversation lookup.

Blast radius and rollback: additive and unwired until TASK-140.6.2. The only change to existing behavior is the render_profile refactor, pinned by existing tests. One revert restores the previous state.

Contract TASK-140.6.2 consumes (all under packages.incident.scribe):
- status_update_approval.validate_approval_edit(edit: StatusUpdateEdit) -> tuple[str, ...]: sync and pure, blank field names for modal field errors, called before any service call.
- await status_update_approval.get_draft_for_review(incident_id, sequence) -> OperationResult[StatusUpdate]: async, prefills the review modal.
- await status_update_approval.approve_status_update(incident_id, sequence, *, approver, edit) -> OperationResult[StatusUpdate]: async and awaited (the Slack listener runs it with asyncio.run, as for draft_status_update); returns the APPROVED record (also on an identical replay), never sets PUBLISHED. Errors: STATUS_UPDATE_FIELDS_INVALID, STATUS_UPDATE_STAGE_BELOW_FLOOR, STATUS_UPDATE_CONFLICT, plus classified store errors.
- providers.get_status_page_publisher() -> StatusPagePublisher, then await publisher.publish(update, labels_en=..., labels_fr=...) -> OperationResult[CopyReadyText]; labels are ProfileLabels from the builders in platforms/slack.py.
- Domain types StatusUpdateEdit(stage, en, fr) and CopyReadyText(en, fr). 140.6.2 owns the error-code to message mapping, t() strings and blank-field to block-id mapping. TASK-140.8 reuses render_copy_ready and the publisher unchanged.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-07: the 7 design questions of the TASK-140.6.1 plan (public next_update_at_for, approval returns only the APPROVED record, three new error codes with stale/non-draft reusing STATUS_UPDATE_CONFLICT, async publisher with labels_en/labels_fr, shared render_profile_sections, replay success only for same approver and identical en/fr/stage, publisher refuses DRAFT) were settled by the human with the recommended answers.

2026-10-07: human chose async get_draft_for_review and approve_status_update (decision 8).

Implemented. Files: contracts/operations/codes.py (+3 codes), scribe/domain.py (+StatusUpdateEdit, CopyReadyText), comms_profile.py (render_profile_sections; render_profile delegates), publisher.py (new, 24 LOC), ports.py (+StatusPagePublisher), adapters/copy_ready.py (new, 31), providers.py (+get_status_page_publisher), status_update.py (_next_update_at -> next_update_at_for), status_update_approval.py (new, 181), README line. Gates (app/): ruff check passed; ruff format --check 833 files formatted; mypy 57 errors in 20 files, all pre-existing, 0 in touched files; lint-imports 10 kept 0 broken; pytest tests --ignore=tests/smoke 6 failed 4021 passed (the 6 known SNS/google-directory TASK-90 order leaks); function-level import grep over touched production files empty. Deviations: none from the plan. Note: pre-authored tests use inline __import__(...) calls (approval and publisher test files) which the function-level import grep does not catch; left unedited as the contract.

2026-10-07 review fix: replaced inline __import__(...) calls (a function-level import in disguise) in test_incident_scribe_status_update_approval.py and test_incident_scribe_status_update_publisher.py with top-level imports of OperationResult and StatusUpdateState. Re-verified: ruff check . All checks passed; ruff format --check 833 files already formatted; lint-imports 10 kept, 0 broken; mypy 57 errors in 20 files, 0 in touched files (all pre-existing in modules/*); pytest tests --ignore=tests/smoke 6 failed, 4021 passed (the 6 are the known TASK-90 SNS/google-directory order leaks); no function-level imports in touched files.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-07 21:25
---
Plan approved by the human 2026-10-07.
---
<!-- COMMENTS:END -->
