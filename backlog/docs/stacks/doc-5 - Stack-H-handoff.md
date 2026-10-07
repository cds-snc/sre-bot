---
id: doc-5
title: Stack H handoff
type: guide
created_date: '2026-10-07 14:30'
updated_date: '2026-10-07 21:38'
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
| 7 | TASK-140.6.1 approve service and copy-ready publisher | `stack-h/task-140.6.1-status-update-approve` | - | ready (uncommitted) | Plan approved 2026-10-07. Implemented: ACs 1-5 checked, gates in the task notes (ruff, format, lint-imports green; mypy 0 in touched files; pytest 4021 passed, 6 known TASK-90 leaks). New `status_update_approval.py` (async `get_draft_for_review` / `approve_status_update`), `publisher.py` (`render_copy_ready`), `adapters/copy_ready.py`, `StatusPagePublisher` in `ports.py`, `render_profile_sections`, `next_update_at_for`, 3 error codes. ~240 production LOC, 10 files. Commit also carries the 140.6.2 plan file and this doc. |
| 8 | TASK-140.6.2 review modal and copy-ready view | `stack-h/task-140.6.2-status-update-review` | - | plan approved | Plan approved 2026-10-07 (6 decisions settled in the notes). Review button, review form via `views.update` in place, approve and publish in one `asyncio.run` helper, `rich_text_preformatted` copy-ready view, dispatch harness moved to `tests/factories/slack_bolt.py`; ~340 LOC, 4-5 files. |
| 9 | TASK-140.8 approved history in the status-updates modal | `stack-h/task-140.8-status-update-history` | - | planned | No plan yet. Gains the published / not published toggle (APPROVED <-> PUBLISHED). |
| 10 | TASK-140.9 redraft from reviewer instructions | `stack-h/task-140.9-status-update-redraft` | - | planned | No plan yet. |

TASK-140.5 and TASK-140.6 are coordinators with no branch (140.6 split 2026-10-07 into 140.6.1 and 140.6.2, ACs mapped in its notes). TASK-140.5 is a coordinator with no branch; its ACs are checked as 140.5.1, 140.5.2 and 140.5.3 verify them (mapping in its plan).

## Position

- Checked out: `stack-h/task-140.6.1-status-update-approve` (layer 7), created with `gh stack add` on top of layer 6 after the stack was rebased onto `main` 7315eb33 (#1552 merged). Uncommitted, all for layer 7: the production and test changes under `app/`, the TASK-140.6.1 and TASK-140.6.2 task files (plans, approval comments) and this doc.
- Stack #1546: #1544, #1545, #1547, #1548 merged; #1549 (base `main`) <- #1550 <- layer 7 (no PR yet). #1549 and #1550 were force-pushed by the rebase and need re-approval.
- Function-level imports: ruff `PLC0415` is not selected in `app/pyproject.toml`, so gates miss them, and inline `__import__(...)` is the same violation; check touched files by hand. Enabling the rule repo-wide is a separate branch off `main`, run by the human later.
- No background agents.

## Next actions

1. **human**: review the layer 7 diff, then commit, submit and create layer 8:
   ```bash
   git add app backlog/tasks/task-140.6.1* backlog/tasks/task-140.6.2* "backlog/docs/stacks/doc-5 - Stack-H-handoff.md"
   git commit -m "Approve a status update and render copy-ready text"
   gh stack submit
   gh stack add stack-h/task-140.6.2-status-update-review
   ```
2. **agent**: implement TASK-140.6.2 test-first (tests-creation then implementation agents; imports at module top level only, tests included, no `__import__`; a circular import is a design flaw), verify gates, check ACs, update this doc.
3. **human**: review and merge #1549, then #1550, then layer 7, bottom-up with re-approval after each rebase.

Merging: bottom-up, one layer at a time, with a re-approval for each rebased layer (doc-2 rule; whole-stack merges fail on `main`).

## Open decisions

- None pending.
- Settled 2026-10-07: 140.6.1 decisions 1-8 and 140.6.2 decisions 1-6 are in the task plans (async approval service with an `asyncio.run` pivot path to async listeners); 140.10.2 plan answers (skip the flag read when confirmed; `_ModalCursor`; wording in the plan, open to feedback; top-level imports only, and a circular import is a design flaw to fix, not to work around); the scribe import cycle is fixed by TASK-143, a standalone PR off `main` outside the stack, which the stack rebases onto (or vice versa); TASK-140.10 split into 140.10.1/140.10.2 as layers 5-6 above #1548, #1548 held until 140.10.2 merges; confirmation view with Confirm and draft / Cancel, one wording for yes and unknown, Draft button unchanged; layer 5 keeps its branch name; drafting starts only from a Draft button; loading view then `update_view`; the 140.5.2/140.5.3 split; in-modal error views with Close; 140.6 split into 140.6.1 (service) and 140.6.2 (Slack); review modal via `views.update` in place; approval stops at APPROVED and PUBLISHED is a user toggle in 140.8; all four fields per language non-blank; forward-only stage floor at approval (un-approve is TASK-140.12); next_update_at recomputed only on stage change (timer drafts are TASK-140.11); copy-ready text is structured plain text in a preformatted block per language, per-product formats in DRAFT-10; security confirmation moved from approval to drafting (TASK-140.10, removed from 140.6's ACs).

## Planning queue

- TASK-140.10.1: plan approved and implemented.
- TASK-140.10.2: plan approved and implemented.
- TASK-140.6.1: plan approved and implemented.
- TASK-140.6.2: plan approved 2026-10-07; implementation waits on layer 7's commit and `gh stack add`. Consumes 140.6.1's contract (async service, `validate_approval_edit` field names `en.affected_service`..`fr.workaround`).
- TASK-140.8, TASK-140.9: no plan; wait on 140.6.1 and 140.6.2.
- Follow-ups outside the stack: TASK-143 (PR #1552, move scribe Protocols to `scribe/ports.py`, remove 3 function-level imports; standalone off `main`; lands first, the stack rebases onto it), TASK-140.11 (timer pre-generated drafts, low), TASK-140.12 (un-approve or correct, to be decided, low).
