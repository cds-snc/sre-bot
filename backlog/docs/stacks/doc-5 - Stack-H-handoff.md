---
id: doc-5
title: Stack H handoff
type: guide
created_date: '2026-10-07 14:30'
updated_date: '2026-10-07 14:31'
---
# Stack H handoff

## Stack

- Name: Stack H, incident status updates.
- Trunk: `main`.
- doc-2 line: Wave 5, "Incident status updates (prioritised 2026-10-06)". doc-2 said single PRs. On 2026-10-07 the human chose a stack for 140.4 -> 140.5 -> 140.6. 140.7 (the legacy cutover) stays a standalone PR after the stack.
- Not mechanical: 140.5 and 140.6 add user-facing behaviour, which doc-2's stacking rules normally keep standalone. Each layer is still reviewed, merged and deployed on its own, bottom-up.

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | TASK-140.4 status-update records and table | `task-140.4-status-update-records` (pushed before the stack existed; adopted by `gh stack init`, keeps its name) | not opened yet | ready | 56debe1c. ACs 1-7 checked. Gates in the task notes. Adds the Terraform table `sre_bot_incident_status_updates` and its IAM grant. |
| 2 | TASK-140.5 draft command `/sre incident status-update` | `stack-h/task-140.5-status-update-draft` | - | planned | No plan yet. Depends on 140.3 (merged #1543) and 140.4 (layer 1). |
| 3 | TASK-140.6 approval modal and copy-ready publish | `stack-h/task-140.6-status-update-approve` | - | planned | No plan yet. Depends on 140.2 (merged #1542) and 140.5 (layer 2). |

## Position

- Checked out: `task-140.4-status-update-records` at 56debe1c (pushed). Uncommitted, and belonging to layer 1 as stack bookkeeping: doc-2 (the Stack H decision), this handoff doc (doc-5), and the approval comment on TASK-140.4.
- `gh stack` is not initialised yet. Layer 2's branch does not exist yet.
- No background agents.

## Next actions

1. **human**: initialise the stack on the pushed 140.4 branch, open its PR, and add layer 2:
   ```bash
   git checkout task-140.4-status-update-records
   git add backlog/docs backlog/tasks
   git commit -m "Start Stack H handoff"
   git push
   gh stack init task-140.4-status-update-records
   gh stack submit
   gh stack add stack-h/task-140.5-status-update-draft
   gh stack view
   ```
2. **agent**: plan TASK-140.5 with `/plan-task task-140.5` on `stack-h/task-140.5-status-update-draft`, ask the open questions in chat, and wait for approval before writing tests or code.
3. **human**: review and merge layer 1 on its own, then run `tf_apply` so the `sre_bot_incident_status_updates` table and its IAM grant exist. Layer 2 must not be merged or deployed before that apply.
4. **agent**: after approval, implement 140.5 TDD, run the gates, check the ACs, and hand over the commit and `gh stack submit` commands.
5. **agent**: plan, then implement, TASK-140.6 as layer 3, added with `gh stack add stack-h/task-140.6-status-update-approve`.

Merging: bottom-up, one layer at a time, with a re-approval for each rebased layer (doc-2 rule; whole-stack merges fail on `main`).

## Open decisions

- None waiting. Planning 140.5 raises its own questions, including: on `STATUS_UPDATE_CONFLICT` (two drafts at the same sequence), retry or refuse; the format of `transcript_fingerprint`.

## Planning queue

- TASK-140.5: no plan. Its inputs are ready: `core/api.py` exports `find_incident_for_conversation`, `get_incident_transcript_reader`, `StatusUpdateStore`, `get_status_update_store` and the record types. The in-memory fake is `packages.incident.core.adapters.in_memory.InMemoryStatusUpdateStore`. See the TASK-140.5 notes from 2026-10-07.
- TASK-140.6: no plan. Waits on 140.5's plan, which fixes the draft shape that the modal edits. The registrar from 140.2 is merged.
