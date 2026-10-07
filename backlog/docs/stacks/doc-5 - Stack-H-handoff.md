---
id: doc-5
title: Stack H handoff
type: guide
created_date: '2026-10-07 14:30'
updated_date: '2026-10-07 15:21'
---
# Stack H handoff

## Stack

- Name: Stack H, incident status updates.
- Trunk: `main`.
- doc-2 line: Wave 5, "Incident status updates (prioritised 2026-10-06)". doc-2 said single PRs. On 2026-10-07 the human chose a stack for 140.4 -> 140.5 -> 140.6, and the same day approved splitting 140.5 at the size gate into 140.5.1 (service) and 140.5.2 (command), giving four layers. Later that day status updates moved entirely into modals (no channel posts), which added TASK-140.8 (history) and TASK-140.9 (redraft with instructions) as layers 5 and 6. 140.7 (legacy cutover) stays standalone after the stack and now depends on 140.8. 140.7 (the legacy cutover) stays a standalone PR after the stack.
- Scope (human, 2026-10-07, recorded in decisions/incident-management.md): nothing is ever pushed to an external platform and nothing about status updates is posted in the incident channel. Draft, review (edit or redraft with instructions), approve, then copy the EN and FR text by hand; the history of approved updates stays browsable. All of it lives in modals opened by `/sre incident status-update`, later also from the central incident modal (DRAFT-11).
- Not mechanical: 140.5 and 140.6 add user-facing behaviour, which doc-2's stacking rules normally keep standalone. Each layer is still reviewed, merged and deployed on its own, bottom-up.

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | TASK-140.4 status-update records and table | `task-140.4-status-update-records` (pushed before the stack existed; keeps its name) | [#1544](https://github.com/cds-snc/sre-bot/pull/1544) | in review | 56debe1c + 83a76f70 (handoff bookkeeping). Adds the Terraform table `sre_bot_incident_status_updates` and its IAM grant. |
| 2 | TASK-140.5.1 status-update draft service | `stack-h/task-140.5-status-update-draft`, to be renamed `stack-h/task-140.5.1-status-update-service` | - | plan approved | ~8 files, ~330 LOC. Includes the bot-message fix in `core/adapters/slack.py`. Unaffected by the modal direction. Also carries the 2026-10-07 planning commit (ADR + backlog). |
| 3 | TASK-140.5.2 status-updates modal opened by `/sre incident status-update` | `stack-h/task-140.5.2-status-updates-modal` | - | planned | Re-plan required: the approved ephemeral-preview plan was superseded by the modal direction. Creates `scribe/entrypoints/slack.py`. |
| 4 | TASK-140.6 review and approve modal, copy-ready text | `stack-h/task-140.6-status-update-approve` | - | planned | No plan yet. Channel confirmation post removed from its ACs. |
| 5 | TASK-140.8 approved history in the status-updates modal | `stack-h/task-140.8-status-update-history` | - | planned | No plan yet. |
| 6 | TASK-140.9 redraft from reviewer instructions | `stack-h/task-140.9-status-update-redraft` | - | planned | No plan yet. |

TASK-140.5 is a coordinator with no branch; its ACs are checked as 140.5.1 and 140.5.2 verify them (mapping in its plan).

## Position

- Checked out: `stack-h/task-140.5-status-update-draft` at 83a76f70 (no layer-2 commits yet). `gh stack`: main <- `task-140.4-status-update-records` (#1544) <- `stack-h/task-140.5-status-update-draft`.
- Uncommitted, the 2026-10-07 planning work, to be committed on layer 2 before the rename: `decisions/incident-management.md` (modal-only status updates, no automatic publishing, primary message direction); this handoff doc; TASK-140, 140.5, 140.5.1, 140.5.2, 140.6, 140.7, 140.8, 140.9; DRAFT-11.
- No background agents.

## Next actions

1. **human**: commit the planning work, then rename the layer 2 branch (it has no PR). In `gh stack modify` choose Rename on `stack-h/task-140.5-status-update-draft`, enter `stack-h/task-140.5.1-status-update-service`, save with Ctrl+S:
   ```bash
   git add decisions/incident-management.md backlog/docs backlog/tasks backlog/drafts
   git commit -m "Plan status updates as modal-only flow"
   gh stack modify
   gh stack view
   ```
2. **agent**: implement TASK-140.5.1 TDD on layer 2 (failing tests first, per its plan), run the gates, check its ACs and the TASK-140.5 ACs it covers, and hand over the commit and `gh stack submit` commands.
3. **human**: review and merge layer 1 (#1544) on its own, then run `tf_apply` so the `sre_bot_incident_status_updates` table and its IAM grant exist. Layers 2+ must not be merged or deployed before that apply.
4. **agent**: re-plan TASK-140.5.2 with `/plan-task task-140.5.2` (Draft button settled; ask any new questions in chat), then add layer 3 (`gh stack add stack-h/task-140.5.2-status-updates-modal`, run by the human) and implement it.
5. **agent**: plan and implement TASK-140.6, TASK-140.8 and TASK-140.9 as layers 4 to 6, each added with `gh stack add <branch>` from the table.

Merging: bottom-up, one layer at a time, with a re-approval for each rebased layer (doc-2 rule; whole-stack merges fail on `main`).

## Open decisions

- None waiting. Settled 2026-10-07 for TASK-140.5.2: drafting starts only from a Draft button in the status-updates modal, never on open (recorded in its plan). The re-plan still has to show the drafting state through `views.update` from the native listener (the command's trigger id lasts about 3 seconds) and confirm the layer fits one PR once the entry point is counted.

## Planning queue

- TASK-140.5.2: re-plan with the Draft button decision; carried decisions are in its plan field.
- TASK-140.6: no plan. Inputs fixed: the draft is core's `StatusUpdate` (DRAFT), rendered by `scribe/comms_profile.py`; label builders live in `scribe/platforms/slack.py` because only that module may call `t()`; `scribe/entrypoints/slack.py` comes from 140.5.2.
- TASK-140.8, TASK-140.9: no plan; wait on 140.6's plan.
