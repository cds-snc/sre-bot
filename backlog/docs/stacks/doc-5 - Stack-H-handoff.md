---
id: doc-5
title: Stack H handoff
type: guide
created_date: '2026-10-07 14:30'
updated_date: '2026-10-07 17:04'
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
| 2 | TASK-140.5.1 status-update draft service | `stack-h/task-140.5-status-update-draft` (rename not offered by `gh stack modify`; name kept, later layers use their task ids) | [#1545](https://github.com/cds-snc/sre-bot/pull/1545) | in review | Base `main` after `gh stack sync`. 3 commits: planning, implementation, and the DynamoDB Local table for `sre_bot_incident_status_updates` in `.devcontainer/dynamodb-create.sh` (TASK-140.4 missed it; added here because #1544 was already in review). Includes the bot-message fix in `core/adapters/slack.py`. |
| 3 | TASK-140.5.2 command opens the status-updates modal with the pending draft | `stack-h/task-140.5.2-status-updates-modal` | [#1547](https://github.com/cds-snc/sre-bot/pull/1547) | in review | Loading view first, then `update_view`; `scribe/comms_profile.py`, `get_pending_status_update`, the Slack contract change (`open_view` returns the view id, new `update_view`, `MISSING_VIEW_ID`); refusal and errors as an in-modal error view. ACs 1-5 checked, gates in the task notes. |
| 4 | TASK-140.5.3 Draft button and drafting state | `stack-h/task-140.5.3-status-update-draft-button` | - | ready | ACs 1-4 checked, gates in the task notes. Also adds an autouse `get_slack_provider` cache-clear fixture in `tests/conftest.py` (first real block-action registration). Plan approved 2026-10-07. Creates `scribe/entrypoints/slack.py` (block action `incident.scribe.status_update.draft`). About 6 files, 160 LOC + 30 YAML. |
| 5 | TASK-140.6 review and approve modal, copy-ready text | `stack-h/task-140.6-status-update-approve` | - | planned | No plan yet. Channel confirmation post removed from its ACs. |
| 6 | TASK-140.8 approved history in the status-updates modal | `stack-h/task-140.8-status-update-history` | - | planned | No plan yet. |
| 7 | TASK-140.9 redraft from reviewer instructions | `stack-h/task-140.9-status-update-redraft` | - | planned | No plan yet. |

TASK-140.5 is a coordinator with no branch; its ACs are checked as 140.5.1, 140.5.2 and 140.5.3 verify them (mapping in its plan).

## Position

- Checked out: `stack-h/task-140.5.3-status-update-draft-button` (layer 4), on top of #1547 with no commits of its own yet. Uncommitted, all for layer 4: the TASK-140.5.3 implementation and tests under `app/`, the TASK-140.5 and 140.5.3 task files, and this doc.
- TASK-140.5 (coordinator): all six ACs checked; stays In Progress until the human sets Done after the layers merge.
- Stack #1546: #1544 merged; #1545 (base `main`) <- #1547 <- layer 4. #1545 and #1547 open, review required, mergeable.
- Local DynamoDB has `sre_bot_incident_status_updates` (ACTIVE), so the modal and Draft button are testable locally.
- No background agents.

## Next actions

1. **human**: commit layer 4 and open its PR:
   ```bash
   git add app backlog
   git commit -m "Draft status updates from the modal"
   gh stack submit
   gh stack view
   ```
2. **human**: get #1545, #1547 and the layer 4 PR reviewed and merge them bottom-up (re-approval after each rebase; run `gh stack sync` after each merge).
3. **human**: add layer 5 with `gh stack add stack-h/task-140.6-status-update-approve`.
4. **agent**: plan TASK-140.6 on layer 5 with the task-planner agent, ask any new questions in chat, and wait for approval. Then do TASK-140.8 and TASK-140.9 as layers 6 and 7.

Merging: bottom-up, one layer at a time, with a re-approval for each rebased layer (doc-2 rule; whole-stack merges fail on `main`).

## Open decisions

- Settled 2026-10-07: drafting starts only from a Draft button, never on open; loading view first via `open_view`/`update_view`; the 140.5.2/140.5.3 split; refusal and errors as an in-modal error view with Close.

## Planning queue

- TASK-140.6: no plan. Inputs fixed: the draft is core's `StatusUpdate` (DRAFT), rendered by `scribe/comms_profile.py` (created by 140.5.2); label builders live in `scribe/platforms/slack.py` because only that module may call `t()`; `scribe/entrypoints/slack.py` (from 140.5.3) holds the native listeners; register new ones in its `register()`.
- TASK-140.8, TASK-140.9: no plan; wait on 140.6's plan.
