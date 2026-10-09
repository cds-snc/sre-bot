---
id: doc-7
title: Stack I handoff
type: guide
created_date: '2026-10-09 13:34'
updated_date: '2026-10-09 14:10'
---
# Stack I handoff

## Stack

- Name: Stack I, human-first incident status updates. Trunk: `main`. gh stack initialised 2026-10-09 with layer 1 at the bottom.
- doc-2 line: none yet. The stack implements coordinator TASK-144, planned in backlog doc-6. doc-6 is the uncommitted planning record and is never staged with a layer.
- Each layer is reviewed, merged and deployed on its own, bottom-up (squash merges; the stack is rebased after each). Merges are manual and bottom-up, with a re-approval for each layer after its rebase.

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | TASK-144.1 merge scribe platforms/ into entrypoints/ | `fix/incident_scribe_shape` | [#1568](https://github.com/cds-snc/sre-bot/pull/1568) | in review | c2f1106f on top of 6f89a897 (TASK-144 planning); a squash merge folds both. ACs 1-5 checked; gates in the notes (4476 passed). PR title is still the branch name "fix/incident scribe shape" (the human chose to leave it). |
| 2 | TASK-144.2 human-first records and README | `stack-i/task-144.2-human-first-records` | - | ready | Docs only; uncommitted until the human runs Next actions 1. ACs 1-5 checked, notes written. Includes the feature-packages.md edit, which depends on layer 1 merging first. |
| 3 | TASK-144.3 service and store: start, save, AI-fill | `stack-i/task-144.3-status-update-service` | - | planned | Plan written; no approval comment yet. |
| 4 | TASK-144.4 modal: start by hand and save draft | `stack-i/task-144.4-...` | - | planned | |
| 5 | TASK-144.5 modal: AI inside the form | `stack-i/task-144.5-...` | - | planned | |

## Position

- Checked out: `stack-i/task-144.2-human-first-records` (layer 2, created by `gh stack add` on top of layer 1). Uncommitted: four decision records, the scribe README, and the TASK-144.2, TASK-140.11 and TASK-140.12 task files (CLI edits), all belonging to layer 2.
- Never stage `backlog/docs/doc-6*`.
- No background agents.

## Next actions

1. **human**: commit and submit layer 2:
   ```
   git add app/ decisions/ backlog/tasks/ backlog/docs/stacks/
   git commit -m "Record human-first status updates"
   gh stack submit
   gh pr view --web
   ```
2. **human**: record plan approval on TASK-144.3 (`backlog task edit TASK-144.3 --comment "Plan approved (human, <date>)"`), or tell the agent it is approved.
3. **human**: `gh stack add stack-i/task-144.3-status-update-service`
4. **agent**: execute TASK-144.3 from its plan (TDD: failing tests first), ending with the commit/submit block for layer 3 and the resume prompt for layer 4.
5. **human**: review #1568 (move: compare function inventories, see TASK-144.1 notes) and the layer 2 PR; merge bottom-up with re-approvals.

## Open decisions

- Plan approval for TASK-144.3, TASK-144.4 and TASK-144.5 (plans written, no approval comments).

## Planning queue

- Empty: TASK-144.3 to TASK-144.5 all have plans. They wait only on approval (Open decisions).
