---
id: doc-13
title: Stack K handoff
type: guide
created_date: '2026-10-14 22:27'
updated_date: '2026-10-14 23:20'
---
# Stack K handoff

## Stack

- Name: Stack K, incident core: the IAM and table layout, the service scope opener, the incident record and its store over the records contract, the cutover, the status-update store move, the full-table read and the open-index reconcile, then the core resource interfaces. Trunk: `main`.
- doc-2 line: "Legacy rebuild by surface": Stack K, started 2026-10-14 from `main` after TASK-109 (#1593). TASK-145.5 is the coordinator of TASK-145.5.1 to TASK-145.5.7; its plan lists the layer order and the subtask descriptions hold the decisions.
- Branch names: `stack-k/<task-id>-<slug>`; the planning layer is `stack-k/plan`.
- Merges: squash, bottom-up, a re-approval per layer after its rebase (approve-latest-push rule). Review is requested once two layers are stacked, and at least two PRs stay open before any closes (human, 2026-10-14); a lone PR is not a stack.
- Standalone merges inside the stack: TASK-152 and TASK-145.5.1 (Terraform; merging to `main` runs tf_apply against production), TASK-145.5.5 (behaviour change, deployed on its own after both Terraform layers are applied). TASK-145.5.7 ships switched off and is run only after TASK-145.8 deploys, before TASK-145.9 merges.

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 0 | Planning edits (tasks and docs below) | `stack-k/plan` | - | ready | Uncommitted. Docs and task files only. |
| 1 | TASK-152 IAM `/index/*` grants (audit trail, retry records, incidents) | `stack-k/task-152-iam-index-grants` | - | plan approved | Plan approved 2026-10-14 (task comment). |
| 2 | TASK-145.5.1 incidents GSIs (ALL), timeline table, devcontainer script run locally | - | - | planned | |
| 3 | TASK-145.5.2 ServiceScopeOpener for Slack and job registrars; dependency-injection.md | - | - | planned | Bolt middleware alternative recorded in the task. |
| 4 | TASK-145.5.3 vocabulary, record, references, core settings, platform tenant ids | - | - | planned | Plan settles how the Google customer id is validated (no Google enabled flag today). |
| 5 | TASK-145.5.4 IncidentStore over RecordStore (reads), fake, index reads return full items | - | - | planned | |
| 6 | TASK-145.5.5 cutover; narrow Protocols and legacy_incidents deleted | - | - | planned | Standalone merge and deploy after layers 1 and 2 are applied. |
| 7 | TASK-145.5.6 StatusUpdateStore onto RecordStore | - | - | planned | |
| 8 | TASK-27.5 bounded full-table read | - | - | planned | Pulled forward; first consumer is layer 9. |
| 9 | TASK-145.5.7 open-index reconcile, off by default | - | - | planned | Runner tentative (in-app leased job); options and references in the task, re-assessed at planning. |
| 10 | TASK-145.6 core resource interfaces | - | - | planned | 2026-10-09 plan stale; re-plan after layer 6 is implemented. |

## Position

- Checked out: `main` at d2a61f13, no stack branch yet.
- Uncommitted, all for layer 0 (`stack-k/plan`):
  - `backlog/docs/doc-2*`, `backlog/docs/stacks/doc-13*` (this doc);
  - `backlog/drafts/draft-3 -*`, `backlog/drafts/draft-4 -*` (tenant rename);
  - tasks 27.5, 58, 140.11, 145, 145.5, 145.6, 145.7, 145.9, 145.12 (modified) and 145.5.1 to 145.5.7, 152 (new).
- Never stage: `backlog/docs/doc-6*`, `doc-8*`, `doc-11*` (updated this session, still a working file), `CDS Incident Management Handbook.md`, `Incident Response Runbook.md`.
- No background agents.

## Next actions

1. **human**: create the stack with the planning layer and layer 1, commit layer 0, and switch to layer 1:
   ```
   gh stack init stack-k/plan stack-k/task-152-iam-index-grants
   gh stack checkout stack-k/plan
   git add "backlog/docs/doc-2 - Delivery-Sequence-and-Stacked-Pull-Requests.md" backlog/docs/stacks/doc-13* backlog/drafts/draft-3\ -* backlog/drafts/draft-4\ -* backlog/tasks/task-27.5\ -* backlog/tasks/task-58\ -* backlog/tasks/task-140.11\ -* backlog/tasks/task-145\ -* backlog/tasks/task-145.5\ -* backlog/tasks/task-145.5.*\ -* backlog/tasks/task-145.6\ -* backlog/tasks/task-145.7\ -* backlog/tasks/task-145.9\ -* backlog/tasks/task-145.12\ -* backlog/tasks/task-152\ -*
   git commit -m "plan: split TASK-145.5 into Stack K layers"
   gh stack rebase
   gh stack checkout stack-k/task-152-iam-index-grants
   ```
2. **agent**: implement layer 1 (TASK-152), run the gates, check ACs 1 and 3, write notes; AC 2 waits for the post-apply simulation.
3. **human**: `gh stack submit`, then request review of layers 0 and 1 together.

## Open decisions

- None.

## Planning queue

- TASK-145.5.1 to TASK-145.5.7, TASK-27.5, TASK-145.6: each planned in turn after the layer below is implemented.
