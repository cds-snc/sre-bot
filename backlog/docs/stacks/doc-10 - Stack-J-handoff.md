---
id: doc-10
title: Stack J handoff
type: guide
created_date: '2026-10-09 18:23'
updated_date: '2026-10-13 16:19'
---
# Stack J handoff

## Stack

- Name: Stack J, incident rebuild group A: the umbrella moves to `features/incident/` and the status-update code is cleaned and carved out as `comms`. Trunk: `main`. gh stack #1578.
- doc-2 line: Wave 5, "Legacy rebuild by surface": TASK-145.1 -> TASK-145.2 -> TASK-145.3 -> TASK-145.4. What follows Stack J is in doc-2 and doc-9.
- Squash merges, bottom-up, with a re-approval for each layer after its rebase. Layer 4 is the last layer.

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 0 | TASK-145 plans (docs only) | `stack-j/plan` | #1576 | merged | |
| 1 | TASK-145.1 move packages/incident to features/incident | `stack-j/task-145.1-move-incident-to-features` | #1577 | merged | 7cb97921. Task Done. |
| 2 | TASK-145.2 status-update wording out of the views module | `stack-j/task-145.2-status-update-wording` | #1579 | merged | acced10b. Task still In Progress: set Done in layer 4's commit. |
| 3 | TASK-145.3 one service call per status-update handler | `stack-j/task-145.3-status-update-handlers` | #1580 | in review | c6e1f4b plus 1a6c06a (severity 0-4 docs), rebased onto #1582 (9eed3f2d). PR base `main`. Task set Done in layer 4's commit. |
| 4 | TASK-145.4 carve `comms` out of scribe as plugin `incident.comms` | `stack-j/task-145.4-comms-subdomain` | #1581 | in review | ddd2985, PR base layer 3. Also carries the stack's closing planning edits (below). Ids are now `incident.comms.status_update.*`: deploy in a quiet window, open modals stop responding. Task set Done in this layer's commit. |

## Position

- Checked out: `stack-j/task-145.4-comms-subdomain`. `main` has #1579 and #1582 (records rename and postmortem planning).
- Uncommitted, all going into layer 4 as a second commit (layer 4 is the vehicle that lands the closing planning edits on `main`): this doc; TASK-145.2, 145.3, 145.4 set to Done; dependencies added to TASK-145.7 (TASK-103), 145.8 (TASK-27.2), 145.9 (TASK-25.10), 145.11 (TASK-134), 145.12 (TASK-121); a note on TASK-27.2.
- Never stage: `backlog/docs/doc-6*`, `backlog/docs/doc-8*`, `CDS Incident Management Handbook.md`, `Incident Response Runbook.md` (working files, not kept in the repo).
- Gates on layer 4 last run 2026-10-09 (code unchanged since; the rebase onto #1582 touched docs only).
- No background agents.

## Next actions

1. **human**: commit the closing edits on layer 4 and push the stack:
   ```
   backlog task edit 145.2 --status Done
   git add "backlog/docs/stacks/doc-10 - Stack-J-handoff.md" backlog/tasks
   git commit -m "Close Stack J and add missing task dependencies"
   gh stack submit
   ```
   Re-approval is needed on #1581.
2. **human**: after #1580 merges: `git checkout main && git pull`, `gh stack checkout stack-j/task-145.4-comms-subdomain`, `gh stack sync`, `gh stack submit`, re-approval of #1581. After #1581 merges: `git checkout main && git pull`, `gh stack sync`. Stack J is then complete; nothing else to commit for it.
3. **agent**: if a review asks for changes, fix them on the layer they belong to (`gh stack checkout <branch>`, then `gh stack rebase`).
4. Next work: TASK-27.4 as a single PR from `main` (doc-2 Wave 0 "Records"), then TASK-27.1 and Stack C.

## Open decisions

None for Stack J.

## Planning queue

Empty for Stack J.
