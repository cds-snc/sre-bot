---
id: doc-5
title: Stack H handoff
type: guide
created_date: '2026-10-07 14:30'
updated_date: '2026-10-07 16:22'
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
| 1 | TASK-140.4 status-update records and table | `task-140.4-status-update-records` (pushed before the stack existed; keeps its name) | [#1544](https://github.com/cds-snc/sre-bot/pull/1544) | in review | 56debe1c + 83a76f70 (handoff bookkeeping). Adds the Terraform table `sre_bot_incident_status_updates` and its IAM grant. |
| 2 | TASK-140.5.1 status-update draft service | `stack-h/task-140.5-status-update-draft` (rename not offered by `gh stack modify`; name kept, later layers use their task ids) | [#1545](https://github.com/cds-snc/sre-bot/pull/1545) | in review | ba78af9d (planning) + 481967de (implementation). ACs 1-7 checked, gates in the task notes. Includes the bot-message fix in `core/adapters/slack.py`. |
| 3 | TASK-140.5.2 command opens the status-updates modal with the pending draft | `stack-h/task-140.5.2-status-updates-modal` | - | ready | ACs 1-5 checked, gates in the task notes (6 known TASK-90 order failures only). Also registers `MISSING_VIEW_ID` in `contracts/operations/codes.py`. Plan approved 2026-10-07 (contract change kept in this layer). Re-planned 2026-10-07: loading view first, then `update_view`; adds `scribe/comms_profile.py`, `get_pending_status_update`, the Slack contract change (`open_view` returns the view id, new `update_view`); refusal and errors as an in-modal error view. About 8 files, 270 LOC + 80 YAML. Branch exists. |
| 4 | TASK-140.5.3 Draft button and drafting state | `stack-h/task-140.5.3-status-update-draft-button` | - | plan approved | Creates `scribe/entrypoints/slack.py` (block action `incident.scribe.status_update.draft`). About 6 files, 160 LOC + 30 YAML. |
| 5 | TASK-140.6 review and approve modal, copy-ready text | `stack-h/task-140.6-status-update-approve` | - | planned | No plan yet. Channel confirmation post removed from its ACs. |
| 6 | TASK-140.8 approved history in the status-updates modal | `stack-h/task-140.8-status-update-history` | - | planned | No plan yet. |
| 7 | TASK-140.9 redraft from reviewer instructions | `stack-h/task-140.9-status-update-redraft` | - | planned | No plan yet. |

TASK-140.5 is a coordinator with no branch; its ACs are checked as 140.5.1, 140.5.2 and 140.5.3 verify them (mapping in its plan).

## Position

- Checked out: `stack-h/task-140.5.2-status-updates-modal` (layer 3), at 481967de with no commits of its own yet. Uncommitted, all for layer 3: the TASK-140.5.2 implementation and tests under `app/` (9 production files, about 270 LOC + 50 YAML; 5 new test files plus 4 test files edited in place for the contract change), the TASK-140.5, 140.5.2 and new 140.5.3 task files, and this doc.
- Stack #1546 on GitHub: #1544 (base `main`) <- #1545 (base `task-140.4-status-update-records`). Both open, review required; #1544 is with a colleague for review.
- No background agents.

## Next actions

1. **human**: commit layer 3 and open its PR:
   ```bash
   git add app backlog
   git commit -m "Open incident status-updates modal"
   gh stack submit
   gh stack view
   ```
2. **human**: merge layer 1 (#1544) after review, then run `tf_apply` so the `sre_bot_incident_status_updates` table and its IAM grant exist. Layers 2+ must not be merged or deployed before that apply.
3. **human**: add layer 4 with `gh stack add stack-h/task-140.5.3-status-update-draft-button`.
4. **agent**: implement TASK-140.5.3 TDD (tests-creation agent, review the tests against the plan, then the implementation agent), run the gates, check its ACs and TASK-140.5 AC1, AC5 and AC6, and hand over the commit and `gh stack submit` commands.
5. **agent**: plan and implement TASK-140.6, TASK-140.8 and TASK-140.9 as layers 5 to 7, each added with `gh stack add <branch>` from the table.

Merging: bottom-up, one layer at a time, with a re-approval for each rebased layer (doc-2 rule; whole-stack merges fail on `main`).

## Open decisions

- Settled 2026-10-07: drafting starts only from a Draft button, never on open; loading view first via `open_view`/`update_view`; the 140.5.2/140.5.3 split; refusal and errors as an in-modal error view with Close.

## Planning queue

- TASK-140.5.2, TASK-140.5.3: plans approved 2026-10-07.
- TASK-140.6: no plan. Inputs fixed: the draft is core's `StatusUpdate` (DRAFT), rendered by `scribe/comms_profile.py` (created by 140.5.2); label builders live in `scribe/platforms/slack.py` because only that module may call `t()`; `scribe/entrypoints/slack.py` comes from 140.5.3.
- TASK-140.8, TASK-140.9: no plan; wait on 140.6's plan.
