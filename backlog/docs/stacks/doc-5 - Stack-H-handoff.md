---
id: doc-5
title: Stack H handoff
type: guide
created_date: '2026-10-07 14:30'
updated_date: '2026-10-07 23:39'
---
# Stack H handoff

## Stack

- Name: Stack H, incident status updates.
- Trunk: `main`.
- doc-2 line: Wave 5, "Incident status updates (prioritised 2026-10-06)". doc-2 said single PRs. On 2026-10-07 the human chose a stack for 140.4 -> 140.5 -> 140.6, and the same day approved splitting 140.5 at the size gate into 140.5.1 (service) and 140.5.2 (command), giving four layers. Later that day status updates moved entirely into modals (no channel posts), which added TASK-140.8 (history) and TASK-140.9 (redraft with instructions) as layers 5 and 6. Still on 2026-10-07 the human approved splitting 140.5.2 at the size gate into 140.5.2 (open the modal) and 140.5.3 (Draft button), giving seven layers. 140.7 (legacy cutover) stays standalone after the stack and now depends on 140.8.
- Scope (human, 2026-10-07, recorded in decisions/incident-management.md): nothing is ever pushed to an external platform and nothing about status updates is posted in the incident channel. Draft, review (edit or redraft with instructions), approve, then copy the EN and FR text by hand; the history of approved updates stays browsable. All of it lives in modals opened by `/sre incident status-update`, later also from the central incident modal (DRAFT-11).
- Not mechanical: 140.5 and 140.6 add user-facing behaviour, which doc-2's stacking rules normally keep standalone. Each layer is still reviewed, merged and deployed on its own, bottom-up.

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | TASK-140.4 status-update records and table | `task-140.4-status-update-records` | [#1544](https://github.com/cds-snc/sre-bot/pull/1544) | merged | Squash-merged 2026-10-07 as f3525fd8; Terraform table `sre_bot_incident_status_updates` and IAM grant applied by the merge workflow. |
| 2 | TASK-140.5.1 status-update draft service | `stack-h/task-140.5-status-update-draft` | [#1545](https://github.com/cds-snc/sre-bot/pull/1545) | merged | Squash-merged 2026-10-07 as 6c3c57a0. Included the DynamoDB Local table in `.devcontainer/dynamodb-create.sh` and the bot-message fix in `core/adapters/slack.py`. |
| 3 | TASK-140.5.2 command opens the status-updates modal with the pending draft | `stack-h/task-140.5.2-status-updates-modal` | [#1547](https://github.com/cds-snc/sre-bot/pull/1547) | merged | Squash-merged 2026-10-07 as 1ca8065c. Commits: modal (5b158387), "Fix status-update command dispatch" (1d7db039, was 5b2b94be before the rebase: the command was registered with `arguments=[]`, so the provider called the handler with the payload only; covered by `test_incident_scribe_status_update_dispatch.py` through a real `SlackPlatformProvider`), and `chore: fmt` (ac5f7531). Loading view then `update_view`; `scribe/comms_profile.py`, `get_pending_status_update`, Slack contract change (`open_view` returns the view id, `update_view`, `MISSING_VIEW_ID`). |
| 4 | TASK-140.5.3 Draft button and drafting state | `stack-h/task-140.5.3-status-update-draft-button` | [#1548](https://github.com/cds-snc/sre-bot/pull/1548) | merged | Squash-merged 2026-10-07 as aca15521. Merged before layer 6 (#1550), although the earlier hold said not to deploy it until layer 6 merged. Creates `scribe/entrypoints/slack.py` (block action `incident.scribe.status_update.draft`) and an autouse `get_slack_provider` cache-clear fixture in `tests/conftest.py`. |
| 5 | TASK-140.10.1 store and read the security flag | `stack-h/task-140.6-status-update-approve` (name kept: `gh stack modify` cannot rename it) | [#1549](https://github.com/cds-snc/sre-bot/pull/1549) | in review | Commits 5112b599 and 6f9d677f (4 function-level test imports moved to module top in `test_db_operations.py`), submitted. ACs 1-5 checked, gates in the task notes. Rollback: never revert the `Incident` field (extra forbid); revert only the declare write. |
| 6 | TASK-140.10.2 confirm before drafting a security or unknown-flag incident | `stack-h/task-140.10.2-security-draft-confirm` | [#1550](https://github.com/cds-snc/sre-bot/pull/1550) | in review | Commits 452b2f3b (implementation, ACs 1-8 checked, gates in the task notes) and 1d091820 (handoff doc). Gate in `draft_status_update` (`SECURITY_CONFIRMATION_REQUIRED`), confirm listener `incident.scribe.status_update.draft_confirmed`, drafting view sent from `on_started`, `_ModalCursor`, decision record update. Base #1549. |
| 7 | TASK-140.6.1 approve service and copy-ready publisher | `stack-h/task-140.6.1-status-update-approve` | [#1555](https://github.com/cds-snc/sre-bot/pull/1555) | in review | Commit c99de0b6 (also carries the 140.6.2 plan and this doc). ACs 1-5 checked, gates in the task notes. Approval service (async), `CopyReadyPublisher`, `StatusPagePublisher` in `ports.py`, 3 error codes. |
| 8 | TASK-140.6.2 review modal and copy-ready view | `stack-h/task-140.6.2-status-update-review` | [#1556](https://github.com/cds-snc/sre-bot/pull/1556) | in review | Commits b3b09ed4 and 0ef47e37 (after the rebase onto `main` a18167d2). ACs 1-6 checked. Single-process pytest has 4 extra `capture_logs` failures from TASK-90 leak 2 (human: fixed in TASK-90, not here); `pytest tests/unit tests/integration` 3376 passed, ruff/format/lint-imports green, mypy 0 in touched files. One plan deviation: `build_review_error_view` (review conflict wording differs from drafting). Also moves the Bolt test harness into `tests/factories/slack_bolt.py`. Manual check in a real workspace still needed: `rich_text_preformatted` copy fidelity, `views.update` after an update ack. |
| 9 | TASK-140.8.1 approved-updates list and reopen copy-ready text | `stack-h/task-140.8-status-update-history` (name kept from before the split) | - | ready (uncommitted) | Plan approved 2026-10-07. Implemented, ACs 1-6 checked, gates in the task notes. Overview service, `status_update_history.py`, list + detail views, Open/Back in place, 50-row cap. Also fixed catalogue-inconsistent fallbacks (`_language_heading`, FR modal title/Close) that made view output depend on test order. |
| 10 | TASK-140.8.2 published / not published toggle | `stack-h/task-140.8.2-status-update-published` | - | plan approved | Plan approved 2026-10-07. Core `published_by` + PUBLISHED -> APPROVED + DynamoDB adapter (no Terraform), `set_published`, toggle; ~170 LOC, ~8 files. Never revert the core field once data exists. |
| 11 | TASK-140.9 redraft from reviewer instructions | `stack-h/task-140.9-status-update-redraft` | - | plan approved | Plan approved 2026-10-07. Redraft section in the review form, `redraft_status_update` in `status_update.py`, security gate with in-form checkbox, new `STATUS_UPDATE_INSTRUCTIONS_INVALID`; ~300 LOC, 6 files. |

TASK-140.5, TASK-140.6 and TASK-140.8 are coordinators with no branch (140.8 split 2026-10-07 into 140.8.1 and 140.8.2, ACs mapped in its notes) (140.6 split 2026-10-07 into 140.6.1 and 140.6.2, ACs mapped in its notes). TASK-140.5 is a coordinator with no branch; its ACs are checked as 140.5.1, 140.5.2 and 140.5.3 verify them (mapping in its plan).

## Position

- Checked out: `stack-h/task-140.8-status-update-history` (layer 9) on #1556. Uncommitted, all for layer 9: the TASK-140.8.1 production and test changes under `app/`, the task files of TASK-140.7, 140.8, 140.8.1, 140.8.2 and 140.9 (split, plans, approvals, dependencies) and this doc.
- Stack #1546 rebased onto `main` a18167d2 (#1554, ruff PLC0415 on) and submitted: #1549 (base `main`) <- #1550 <- #1555 <- #1556 <- layer 9. All four open PRs need (re-)approval.
- Single-process pytest on layer 9: 4235 passed, 14 failed = 6 known TASK-90 + 8 scribe `capture_logs` tests (TASK-90 leak 2, cached structlog loggers; pass in isolation and in the split runs). TASK-90 is deferred by the human to a later standalone PR; branch `fix/task-90-test-order-leaks` exists locally (tracking `origin/main`; push with `-u origin fix/task-90-test-order-leaks`), no worktree.
- Function-level imports: ruff `PLC0415` now enforces them; inline `__import__(...)` is still missed, check by hand.
- Subagent quality: the tests-creation agent twice produced vacuous Slack view tests; a general-purpose agent on opus with an explicit quality bar did it right. Review subagent tests structurally before implementing.
- No background agents.

## Next actions

1. **human**: review the layer 9 diff, commit, submit and create layer 10:
   ```bash
   git add app backlog/tasks "backlog/docs/stacks/doc-5 - Stack-H-handoff.md"
   git commit -m "List approved status updates and reopen their text"
   gh stack submit
   gh stack add stack-h/task-140.8.2-status-update-published
   ```
2. **agent**: implement TASK-140.8.2 (layer 10) test-first (tests by a general-purpose opus agent with the quality bar, then the implementation agent), verify gates, check ACs.
3. **human**: commit layer 10, `gh stack submit`, `gh stack add stack-h/task-140.9-status-update-redraft`; agent implements TASK-140.9 (layer 11) the same way.
4. **human**: review and merge #1549, #1550, #1555, #1556, then layers 9-11, bottom-up with re-approval after each rebase; move each task to Done after its merge (agents never set Done).
5. Then TASK-140.7 (legacy cutover, standalone after the stack, depends on 140.6 and 140.8.1).

Merging: bottom-up, one layer at a time, with a re-approval for each rebased layer (doc-2 rule; whole-stack merges fail on `main`).

## Open decisions

- None pending.
- Settled 2026-10-07: 140.6.1 decisions 1-8 and 140.6.2 decisions 1-6 are in the task plans (async approval service with an `asyncio.run` pivot path to async listeners); 140.10.2 plan answers (skip the flag read when confirmed; `_ModalCursor`; wording in the plan, open to feedback; top-level imports only, and a circular import is a design flaw to fix, not to work around); the scribe import cycle is fixed by TASK-143, a standalone PR off `main` outside the stack, which the stack rebases onto (or vice versa); TASK-140.10 split into 140.10.1/140.10.2 as layers 5-6 above #1548, #1548 held until 140.10.2 merges; confirmation view with Confirm and draft / Cancel, one wording for yes and unknown, Draft button unchanged; layer 5 keeps its branch name; drafting starts only from a Draft button; loading view then `update_view`; the 140.5.2/140.5.3 split; in-modal error views with Close; 140.6 split into 140.6.1 (service) and 140.6.2 (Slack); review modal via `views.update` in place; approval stops at APPROVED and PUBLISHED is a user toggle in 140.8; all four fields per language non-blank; forward-only stage floor at approval (un-approve is TASK-140.12); next_update_at recomputed only on stage change (timer drafts are TASK-140.11); copy-ready text is structured plain text in a preformatted block per language, per-product formats in DRAFT-10; security confirmation moved from approval to drafting (TASK-140.10, removed from 140.6's ACs).

## Planning queue

- TASK-140.10.1: plan approved and implemented.
- TASK-140.10.2: plan approved and implemented.
- TASK-140.6.1: plan approved and implemented.
- TASK-140.6.2: plan approved and implemented. Consumes 140.6.1's contract (async service, `validate_approval_edit` field names `en.affected_service`..`fr.workaround`).
- TASK-140.8.1 implemented; TASK-140.8.2 and TASK-140.9 plans approved 2026-10-07. Expected textual overlap between layers in `platforms/slack.py`, `entrypoints/slack.py` (`register()`), the locale files. 140.8 reuses `build_copy_ready_view`, `_approve_and_publish`, `_ModalCursor`/`_parse_metadata`; 140.9 extends `build_review_view` (optional `notice`), block ids `stage`/`en.*`/`fr.*`, input action ids `stage`/`text`, review metadata `{channel_id, locale, incident_id, sequence}`.
- Follow-ups outside the stack: TASK-143 (PR #1552, move scribe Protocols to `scribe/ports.py`, remove 3 function-level imports; standalone off `main`; lands first, the stack rebases onto it), TASK-90 (test-order leaks; human 2026-10-07: later standalone PR off `main`; it clears layer 8's 4 extra single-process `capture_logs` failures), TASK-140.11 (timer pre-generated drafts, low), TASK-140.12 (un-approve or correct, to be decided, low).
