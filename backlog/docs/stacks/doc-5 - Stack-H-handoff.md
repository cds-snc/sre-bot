---
id: doc-5
title: Stack H handoff
type: guide
created_date: '2026-10-07 14:30'
updated_date: '2026-10-07 20:04'
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
| 3 | TASK-140.5.2 command opens the status-updates modal with the pending draft | `stack-h/task-140.5.2-status-updates-modal` | [#1547](https://github.com/cds-snc/sre-bot/pull/1547) | in review | Base `main`, rebased onto 6c3c57a0. Commits: modal (5b158387), "Fix status-update command dispatch" (1d7db039, was 5b2b94be before the rebase: the command was registered with `arguments=[]`, so the provider called the handler with the payload only; covered by `test_incident_scribe_status_update_dispatch.py` through a real `SlackPlatformProvider`), and `chore: fmt` (ac5f7531). Loading view then `update_view`; `scribe/comms_profile.py`, `get_pending_status_update`, Slack contract change (`open_view` returns the view id, `update_view`, `MISSING_VIEW_ID`). |
| 4 | TASK-140.5.3 Draft button and drafting state | `stack-h/task-140.5.3-status-update-draft-button` | [#1548](https://github.com/cds-snc/sre-bot/pull/1548) | in review | Commits 57bd2965 and `chore: fmt` b7e758fa (fixed the CI `fmt-ci` failure). Creates `scribe/entrypoints/slack.py` (block action `incident.scribe.status_update.draft`) and an autouse `get_slack_provider` cache-clear fixture in `tests/conftest.py`. Do not deploy before layer 6 merges. |
| 5 | TASK-140.10.1 store and read the security flag | `stack-h/task-140.6-status-update-approve` (name kept: `gh stack modify` cannot rename it) | [#1549](https://github.com/cds-snc/sre-bot/pull/1549) | in review | Commits 5112b599 and 6f9d677f (4 function-level test imports moved to module top in `test_db_operations.py`), submitted. ACs 1-5 checked, gates in the task notes. Rollback: never revert the `Incident` field (extra forbid); revert only the declare write. |
| 6 | TASK-140.10.2 confirm before drafting a security or unknown-flag incident | `stack-h/task-140.10.2-security-draft-confirm` | - | in progress | Plan approved 2026-10-07. Implemented with ACs 1-8 checked and gates green (evidence in the task notes), but uncommitted. Gate in `draft_status_update` (`SECURITY_CONFIRMATION_REQUIRED`), confirm listener `incident.scribe.status_update.draft_confirmed`, drafting view sent from `on_started`, `_ModalCursor`. #1548 must not deploy before this merges. Confirmation view, gate in `draft_status_update`, drafting view moves to `on_started`, decision record update. #1548 must not deploy before this merges. |
| 7 | TASK-140.6.1 approve service and copy-ready publisher | `stack-h/task-140.6.1-status-update-approve` | - | planned | No plan yet. Platform-neutral; approval stops at APPROVED. |
| 8 | TASK-140.6.2 review modal and copy-ready view | `stack-h/task-140.6.2-status-update-review` | - | planned | No plan yet. Review button, views.update in place, preformatted copy-ready text. |
| 9 | TASK-140.8 approved history in the status-updates modal | `stack-h/task-140.8-status-update-history` | - | planned | No plan yet. Gains the published / not published toggle (APPROVED <-> PUBLISHED). |
| 10 | TASK-140.9 redraft from reviewer instructions | `stack-h/task-140.9-status-update-redraft` | - | planned | No plan yet. |

TASK-140.5 and TASK-140.6 are coordinators with no branch (140.6 split 2026-10-07 into 140.6.1 and 140.6.2, ACs mapped in its notes). TASK-140.5 is a coordinator with no branch; its ACs are checked as 140.5.1, 140.5.2 and 140.5.3 verify them (mapping in its plan).

## Position

- Checked out: `stack-h/task-140.10.2-security-draft-confirm` (layer 6), at 6f9d677f (same as layer 5). Uncommitted, for layer 6: the changes under `app/` and `decisions/incident-management.md`, the TASK-140.10.2 task file and this doc. Untracked and NOT for this layer: `backlog/tasks/task-143 - ...md` (TASK-143, standalone off `main`).
- Stack #1546: #1544 and #1545 merged; #1547 (base `main`) <- #1548 <- #1549, all open, review required. Layer 6 has no PR yet.
- Function-level imports: ruff `PLC0415` is not selected in `app/pyproject.toml`, so gates miss them. Layers 3-4 test files still have 18 (`tests/conftest.py:67`, `test_incident_scribe_status_update_entrypoint.py` x16, `test_incident_scribe_status_update_slack.py` x1); left as is by the human on 2026-10-07. Enabling the rule repo-wide is a separate branch off `main`, independent of this stack, run by the human later.
- No background agents.

## Next actions

1. **human**: review the layer 6 diff, then commit and submit (leave the TASK-143 file out):
   ```bash
   git add app decisions "backlog/docs/stacks/doc-5 - Stack-H-handoff.md" backlog/tasks/task-140.10.2*
   git commit -m "Confirm before drafting a security incident update"
   gh stack submit
   ```
2. **agent**: plan TASK-140.6.1, then TASK-140.6.2, with the task-planner agent (tell it: imports at module top level only, tests included; a circular import is a design flaw, not a reason for a lazy import); ask questions in chat and wait for approval.
3. **human**: reviews; merge #1547 when approved. Do not merge/deploy #1548 until layer 6 (140.10.2) can merge right after it.

Merging: bottom-up, one layer at a time, with a re-approval for each rebased layer (doc-2 rule; whole-stack merges fail on `main`).

## Open decisions

- None pending.
- Settled 2026-10-07: 140.10.2 plan answers (skip the flag read when confirmed; `_ModalCursor`; wording in the plan, open to feedback; top-level imports only, and a circular import is a design flaw to fix, not to work around); the scribe import cycle is fixed by TASK-143, a standalone PR off `main` outside the stack, which the stack rebases onto (or vice versa); TASK-140.10 split into 140.10.1/140.10.2 as layers 5-6 above #1548, #1548 held until 140.10.2 merges; confirmation view with Confirm and draft / Cancel, one wording for yes and unknown, Draft button unchanged; layer 5 keeps its branch name; drafting starts only from a Draft button; loading view then `update_view`; the 140.5.2/140.5.3 split; in-modal error views with Close; 140.6 split into 140.6.1 (service) and 140.6.2 (Slack); review modal via `views.update` in place; approval stops at APPROVED and PUBLISHED is a user toggle in 140.8; all four fields per language non-blank; forward-only stage floor at approval (un-approve is TASK-140.12); next_update_at recomputed only on stage change (timer drafts are TASK-140.11); copy-ready text is structured plain text in a preformatted block per language, per-product formats in DRAFT-10; security confirmation moved from approval to drafting (TASK-140.10, removed from 140.6's ACs).

## Planning queue

- TASK-140.10.1: plan approved and implemented.
- TASK-140.10.2: plan approved and implemented.
- TASK-140.6.1, TASK-140.6.2: tasks created; plans not yet written. Inputs: the draft is core's `StatusUpdate` (DRAFT), rendered by `scribe/comms_profile.py`; `t()` only in `scribe/platforms/slack.py`; listeners in `scribe/entrypoints/slack.py` `register()`; real-Bolt dispatch harness in `tests/integration/integrations/slack/test_slack_provider_listener_dispatch.py`.
- TASK-140.8, TASK-140.9: no plan; wait on 140.6.1 and 140.6.2.
- Follow-ups outside the stack: TASK-143 (move scribe Protocols to `scribe/ports.py`, remove 3 function-level imports; standalone off `main`, not planned yet), TASK-140.11 (timer pre-generated drafts, low), TASK-140.12 (un-approve or correct, to be decided, low).
