---
id: doc-13
title: Stack K handoff
type: guide
created_date: '2026-10-14 22:27'
updated_date: '2026-10-14 23:38'
---
# Stack K handoff

## Stack

- Name: Stack K, incident core: the IAM and table layout, the service scope opener, the incident record and its store over the records contract, the cutover, the status-update store move, the full-table read and the open-index reconcile, then the core resource interfaces. Trunk: `main`.
- doc-2 line: "Legacy rebuild by surface": Stack K, started 2026-10-14 from `main` after TASK-109 (#1593). TASK-145.5 is the coordinator of TASK-145.5.1 to TASK-145.5.7; its plan lists the layer order and the subtask descriptions hold the decisions.
- Branch names: `stack-k/<task-id>-<slug>`; the planning layer is `stack-k/plan`.
- Merges: squash, bottom-up, a re-approval per layer after its rebase (approve-latest-push rule). Review is requested once two layers are stacked, and at least two PRs stay open before any closes (human, 2026-10-14); a lone PR is not a stack. gh stack closes the stack once every layer has merged (later branches become independent PRs), so new layers are built on lower layers still in review, and a layer merges only when a higher layer is already submitted (human, 2026-10-14). Review changes to a lower layer are made on its branch, then `gh stack rebase`.
- Standalone merges inside the stack: TASK-152 and TASK-145.5.1 (Terraform; merging to `main` runs tf_apply against production), TASK-145.5.5 (behaviour change, deployed on its own after both Terraform layers are applied). TASK-145.5.7 ships switched off and is run only after TASK-145.8 deploys, before TASK-145.9 merges.

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 0 | Planning edits (tasks and docs) | `stack-k/plan` | #1594 | in review | Docs and task files only. doc-2 rule edit (stack never completed before all layers are stacked) to commit here. |
| 1 | TASK-152 IAM `/index/*` grants (audit trail, retry records, incidents) | `stack-k/task-152-iam-index-grants` | #1595 | in review | ACs 1 and 3 checked (tf_plan shows only the policy statement). AC 2 waits on the post-apply simulation. |
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

- Checked out: `stack-k/task-152-iam-index-grants` (3feded3), stack #1596 submitted (PRs #1594, #1595), review not yet requested.
- Uncommitted:
  - `backlog/docs/doc-2*`: layer 0 (new stack rule);
  - `backlog/docs/stacks/doc-13*` (this doc) and `backlog/tasks/task-152 -*` (AC 3, notes): layer 1.
- Never stage: `backlog/docs/doc-6*`, `doc-8*`, `doc-11*`, `CDS Incident Management Handbook.md`, `Incident Response Runbook.md`.
- Local only: an ignored `app/infrastructure/idempotency/__pycache__` directory makes `test_old_idempotency_package_is_not_discoverable` fail; `rm -rf app/infrastructure/idempotency` clears it (cache files only).
- No background agents.

## Next actions

1. **human**: commit the layer 1 files, put the doc-2 rule on layer 0, rebase and resubmit, then request review of #1594 and #1595 together:
   ```
   git add backlog/docs/stacks/doc-13* backlog/tasks/task-152\ -*
   git commit -m "TASK-152 record tf_plan check"
   gh stack checkout stack-k/plan
   git add "backlog/docs/doc-2 - Delivery-Sequence-and-Stacked-Pull-Requests.md"
   git commit -m "plan: keep stacks open until all layers stack"
   gh stack rebase
   gh stack checkout stack-k/task-152-iam-index-grants
   gh stack submit
   ```
2. **agent**: plan layer 2 (TASK-145.5.1) with `/plan-task task-145.5.1` without waiting for review of layers 0 and 1; the human approves the plan in a task comment.
3. **human**: once the plan is approved, create layer 2: `gh stack add stack-k/task-145.5.1-incidents-gsis`.
4. **agent**: implement layer 2 and run its gates; the human commits it and runs `gh stack submit`.
5. **human**: only after layer 2 is submitted, merge layers 0 and 1 bottom-up (layer 1 is a standalone Terraform merge; merging runs tf_apply against production). Then run the simulation from TASK-152 plan step 4 and paste the output:
   ```
   aws iam simulate-principal-policy --policy-source-arn <sre-bot-ecs-role ARN> --action-names dynamodb:Query --resource-arns <audit trail table ARN>/index/correlation_id-index <webhooks table ARN>/index/x
   ```
6. **agent**: record the simulation output in the TASK-152 notes and check AC 2 (expect allowed, then implicitDeny).

## Open decisions

- None.

## Planning queue

- TASK-145.5.1 (next, item 3), then TASK-145.5.2 to TASK-145.5.7, TASK-27.5, TASK-145.6: each planned in turn after the layer below is implemented.
