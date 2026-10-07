---
id: doc-5
title: Stack H handoff
type: guide
created_date: '2026-10-07 14:30'
updated_date: '2026-10-07 15:41'
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
| 2 | TASK-140.5.1 status-update draft service | `stack-h/task-140.5-status-update-draft` (rename not offered by `gh stack modify`; name kept, later layers use their task ids) | - | ready | ba78af9d (planning) + implementation commit pending. ACs 1-7 checked, gates in the task notes. Includes the bot-message fix in `core/adapters/slack.py`. |
| 3 | TASK-140.5.2 status-updates modal opened by `/sre incident status-update` | `stack-h/task-140.5.2-status-updates-modal` | - | planned | Re-plan required: the approved ephemeral-preview plan was superseded by the modal direction. Creates `scribe/entrypoints/slack.py`. |
| 4 | TASK-140.6 review and approve modal, copy-ready text | `stack-h/task-140.6-status-update-approve` | - | planned | No plan yet. Channel confirmation post removed from its ACs. |
| 5 | TASK-140.8 approved history in the status-updates modal | `stack-h/task-140.8-status-update-history` | - | planned | No plan yet. |
| 6 | TASK-140.9 redraft from reviewer instructions | `stack-h/task-140.9-status-update-redraft` | - | planned | No plan yet. |

TASK-140.5 is a coordinator with no branch; its ACs are checked as 140.5.1 and 140.5.2 verify them (mapping in its plan).

## Position

- Checked out: `stack-h/task-140.5-status-update-draft`, at ba78af9d (planning commit) plus uncommitted TASK-140.5.1 implementation: 6 modified and 6 new files under `app/` and the TASK-140.5.1, TASK-140.5 and doc-5 backlog edits. All of it belongs to layer 2.
- No background agents.

## Next actions

1. **human**: commit layer 2 and open its PR:
   ```bash
   git add app backlog
   git commit -m "Draft incident status updates in scribe"
   gh stack submit
   gh stack view
   ```
2. **human**: review and merge layer 1 (#1544) on its own, then run `tf_apply` so the `sre_bot_incident_status_updates` table and its IAM grant exist. Layers 2+ must not be merged or deployed before that apply.
3. **agent**: re-plan TASK-140.5.2 with `/plan-task task-140.5.2` on a new layer added with `gh stack add stack-h/task-140.5.2-status-updates-modal` (run by the human), ask any new questions in chat, and wait for approval.
4. **agent**: after approval, implement TASK-140.5.2 TDD, run the gates, check its ACs and TASK-140.5 AC1, AC5 and AC6, and hand over the commit and `gh stack submit` commands.
5. **agent**: plan and implement TASK-140.6, TASK-140.8 and TASK-140.9 as layers 4 to 6, each added with `gh stack add <branch>` from the table.

Merging: bottom-up, one layer at a time, with a re-approval for each rebased layer (doc-2 rule; whole-stack merges fail on `main`).

## Open decisions

- None waiting. Settled 2026-10-07 for TASK-140.5.2: drafting starts only from a Draft button in the status-updates modal, never on open (recorded in its plan). The re-plan still has to show the drafting state through `views.update` from the native listener (the command's trigger id lasts about 3 seconds) and confirm the layer fits one PR once the entry point is counted.

## Planning queue

- TASK-140.5.2: re-plan with the Draft button decision; carried decisions are in its plan field.
- TASK-140.6: no plan. Inputs fixed: the draft is core's `StatusUpdate` (DRAFT), rendered by `scribe/comms_profile.py`; label builders live in `scribe/platforms/slack.py` because only that module may call `t()`; `scribe/entrypoints/slack.py` comes from 140.5.2.
- TASK-140.8, TASK-140.9: no plan; wait on 140.6's plan.
