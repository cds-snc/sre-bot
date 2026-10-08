---
id: TASK-140.8.2
title: >-
  Mark an approved status update as published or not published from its
  copy-ready view
status: In Progress
assignee: []
created_date: '2026-10-07 22:57'
updated_date: '2026-10-08 15:36'
labels:
  - incident
dependencies:
  - TASK-140.8.1
parent_task_id: TASK-140.8
priority: high
type: feature
ordinal: 343000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Toggle slice of TASK-140.8 (Stack H layer 10), the only slice touching incident core. The copy-ready view opened from the approved-updates list (TASK-140.8.1) gains a status line (approved by whom and when, published by whom and when, ET/HE) and one button carrying the target state: Mark as published or Mark as not published. It records a person's confirmation that they posted the text to their platform and can be undone. Core: StatusUpdate gains published_by (str | None), StatusUpdateState allows PUBLISHED -> APPROVED (a deliberate reversal of 'nothing goes back'), and the DynamoDB adapter writes and reads published_by; no Terraform or IAM change. Service: async set_published(incident_id, sequence, *, published, actor) does one transition with a CAS on the expected state; APPROVED -> PUBLISHED sets published_at and published_by, PUBLISHED -> APPROVED clears both; already in the target state is success with no write; a draft is refused with STATUS_UPDATE_NOT_APPROVED; a lost CAS gets one re-read. Approval never sets PUBLISHED. Nothing is posted to the incident channel. Rollback: never revert the core field once data exists; revert only the toggle.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A published toggle moves an update between APPROVED and PUBLISHED, recording published_at and who set it, and can be undone (undo clears both); it is the only store write
- [x] #2 The toggle button carries the target state, so a stale view cannot invert it; a repeated toggle is success with no write and a draft is refused
- [x] #3 Core allows PUBLISHED -> APPROVED, StatusUpdate has published_by, and the DynamoDB adapter round-trips it
- [x] #4 Nothing is posted to the incident channel; all strings are in EN and FR catalogues; the toggle dispatches through a real SlackPlatformProvider in an integration test
- [x] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Basis: stack is on main a18167d2 (ruff PLC0415 on); this layer sits on TASK-140.8.1. Imports at module top only, tests included; no __import__/importlib. t() only in platforms/slack.py. No new ErrorCodes (STATUS_UPDATE_NOT_APPROVED, STATUS_UPDATE_CONFLICT). The only store write is StatusUpdateStore.transition; nothing is posted to the channel; approval still never sets PUBLISHED.

Settled (human, 2026-10-07, recommended answers): undo clears both published_at and published_by; PUBLISHED -> APPROVED is added in core as a deliberate reversal of the can_move_to docstring; the button carries the target state.

Design:
D5 (core). core/domain.py: StatusUpdate gains published_by: str | None = None (documented); _STATE_MOVES adds (PUBLISHED, APPROVED); can_move_to docstring updated. core/api.py: StatusUpdateStore.transition docstring says approve, publish and unpublish. core/adapters/status_updates.py: _to_item writes published_by when set, _from_item reads it (optional). in_memory.py needs no change (uses can_move_to). No Terraform or IAM change: the table declares only PK/SK.
D4 (service). scribe/status_update_history.py: async set_published(incident_id, sequence, *, published, actor, now=None, store=None) -> OperationResult[StatusUpdate]. Read via list_for_incident; missing sequence -> STATUS_UPDATE_CONFLICT; DRAFT -> STATUS_UPDATE_NOT_APPROVED; already in target state -> success, no write; else replace(...) (publish: state PUBLISHED, published_at=now, published_by=actor; undo: state APPROVED, both None) and transition(expected_state=current). On STATUS_UPDATE_CONFLICT one re-read: record now in the target state -> success, otherwise STATUS_UPDATE_CONFLICT; other store errors classified and returned. Structured logs with incident_id, sequence, actor.
UI. platforms/slack.py: build_copy_ready_view with update shows published line (by <@U..> at ET/HE) when PUBLISHED and one toggle button, action id incident.scribe.status_update.published, value JSON {incident_id, sequence, published: bool} with the target, text "Mark as published" / "Mark as not published" (for PUBLISHED the target is false); Back stays. entrypoints/slack.py: handle_published_action: ack, actor from body user id, asyncio.run of one helper (set_published, then the publisher + detail-view render shared with the open handler), views_update in place via _ModalCursor; failure -> Close-only error view with one new string for a toggle conflict. Registered next to the open/history actions.
Locale (both files, ~6 keys): published_by line, mark_published, mark_unpublished, toggle_conflict, published at/by pieces.

Steps: (1) core domain/api docstring; (2) DynamoDB adapter; (3) set_published; (4) slack.py toggle button + published line + error mapping; (5) entrypoint handler + registration; (6) locales.

AC traceability and tests:
- AC3: edit in place unit/packages/incident/core/test_incident_core_status_update_record.py (flip PUBLISHED->APPROVED to True, published_by default/field), the DynamoDB adapter tests (published_by round trip, PUBLISHED->APPROVED transition CAS with the expected-state condition, absent attribute reads None) and test_incident_core_status_update_fake.py (undo allowed, still refuses PUBLISHED->DRAFT).
- AC1/AC2: new unit/packages/incident/scribe/test_incident_scribe_status_update_published.py over InMemoryStatusUpdateStore with fixed now: publish records published_at/by, undo clears both, repeat is success with a counting store showing zero transitions, draft refused with STATUS_UPDATE_NOT_APPROVED, missing sequence conflict, lost CAS re-read success vs conflict, store errors propagate, only transition is called; plus a view test file (toggle button value carries the target for APPROVED and PUBLISHED, published line, EN/FR strings) named test_incident_scribe_status_update_published_view.py.
- AC4: test_incident_scribe_status_update_published_entrypoint.py (fake client: only views_update, hash handling, actor id passed, error view on conflict) and integration/packages/incident/scribe/test_incident_scribe_status_update_published_dispatch.py via harness_fixture("incident.scribe") dispatching a real block_actions through a real SlackPlatformProvider, asserting views.update calls only.
- AC5: ruff, mypy (0 new in touched files), lint-imports, pytest tests --ignore=tests/smoke, manual function-level-import check.
Structural exact assertions; no str(view) matching.

Size gate: ~170 production LOC (core ~15, service ~55, slack.py ~45, entrypoint ~40, locales ~14), ~8 files (core domain, api, adapter; status_update_history; platforms/slack; entrypoints/slack; 2 locales), two subsystems (core + scribe), no refactor mixed with behaviour. Under the gate.

Assumptions to verify: no other test or code enumerates StatusUpdate fields positionally; the legacy store reader ignores unknown attributes (DynamoDB reader reads named keys only).

Blast radius and rollback: first core change since layer 1. Revert only the toggle (UI, service, entrypoint). Never revert the core field once data exists: records with published_by or PUBLISHED state must stay readable. The core change is additive and unwired until the button ships.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-07: the human settled the 6 planning questions (split, in-place open with Back, overview function, draft/approval views unchanged, undo clears both, 50-row cap) with the recommended answers.

2026-10-08 implemented test-first (tests by a general-purpose opus agent, reviewed; then the implementation agent; diff reviewed and every gate rerun by the session).
Core: StatusUpdate.published_by (str | None = None), _STATE_MOVES adds PUBLISHED -> APPROVED (still no move to DRAFT), DynamoDB _to_item/_from_item write and read published_by (absent -> None). No Terraform or IAM change. Never revert the core field once data exists.
Service: set_published in status_update_history.py; get_approved_update's body moved into a shared _read_approved used for the first read and the one re-read; _failure helper mirrors status_update_approval.py.
UI: the toggle is the accessory of the approved_status section (value carries the target), published_status line at blocks[1] when PUBLISHED with a publisher, Back stays last; build_published_error_view (toggle_conflict wording, else build_draft_error_view). Entrypoint handle_published_action shares the render path with Open via _render_record; registered after Back. 5 new keys in both locale files (FR feminine: publiée, matching row.published). README entry for status_update_history.py. Sibling tests updated in place: TestRegister in the history and review entrypoint files, the approved status-line test in the history view file.
Production diff: 9 files, +220/-25 (incl. README and locales).
Gates (cd app):
- uv run ruff check . -> All checks passed!
- uv run ruff format --check . -> 847 files already formatted
- uv run lint-imports -> Contracts: 10 kept, 0 broken.
- uv run mypy . --exclude ... -> Found 57 errors in 20 files; 0 in touched files (3 under packages/incident are in scheduling/google_calendar.py and meet/google_meet.py, untouched).
- uv run pytest tests/unit tests/integration -q -> 3544 passed
- uv run pytest tests --ignore=tests/smoke -q (single process) -> 16 failed, 4311 passed: 6 known TASK-90 (SNS, google directory) + 8 known scribe capture_logs + 2 new capture_logs tests of the same leak-2 kind (test_incident_scribe_status_update_published_entrypoint.py test_toggle_failure_is_logged, test_slack_failure_is_logged_not_raised); that file passes alone (20 passed).
- grep of touched .py files for __import__/importlib/inline imports -> only the existing TYPE_CHECKING boto3 import.
Manual workspace checks pending: toggle in place in a real modal (accessory button on the status section), ET/HE published line.

Re-verified 2026-10-08 after gh stack rebase onto main (layers 8-9 merged; branch is 2 commits above df070fc8). PR #1558 retitled via REST (gh pr edit fails on the reviewRequests GraphQL lookup). Gates (cd app):
- uv run ruff check . -> All checks passed!
- uv run lint-imports -> Contracts: 10 kept, 0 broken.
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> Found 57 errors in 20 files (checked 384 source files); 0 in the 22 files this layer touches.
- uv run pytest tests/integration/legacy_surface -q -> 20 passed, 4 warnings
- uv run pytest tests --ignore=tests/smoke -q -p no:randomly -> 4328 passed, 2051 warnings in 49.15s
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-07 23:01
---
Plan approved by the human 2026-10-07.
---
<!-- COMMENTS:END -->
