---
id: doc-13
title: Stack K handoff
type: guide
created_date: '2026-10-14 22:27'
updated_date: '2026-10-14 23:25'
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
| 0 | Planning edits (tasks and docs) | `stack-k/plan` | - | ready | Committed 64e442d. Docs and task files only. |
| 1 | TASK-152 IAM `/index/*` grants (audit trail, retry records, incidents) | `stack-k/task-152-iam-index-grants` | - | ready (uncommitted) | Implemented; AC 1 checked. AC 3 waits on the tf_plan PR comment, AC 2 on the post-apply simulation. |
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

- Checked out: `stack-k/task-152-iam-index-grants`, on top of `stack-k/plan` (64e442d).
- Uncommitted, all for layer 1: `terraform/iam.tf`, `backlog/tasks/task-152 -*` (In Progress, AC 1 checked, notes).
- Never stage: `backlog/docs/doc-6*`, `doc-8*`, `doc-11*`, `CDS Incident Management Handbook.md`, `Incident Response Runbook.md`.
- Local only: an ignored `app/infrastructure/idempotency/__pycache__` directory makes `test_old_idempotency_package_is_not_discoverable` fail; `rm -rf app/infrastructure/idempotency` clears it (cache files only).
- No background agents.

## Next actions

1. **human**: commit layer 1, submit layers 0 and 1, and request review of both together:
   ```
   git add terraform/iam.tf backlog/tasks/task-152\ -* backlog/docs/stacks/doc-13*
   git commit -m "TASK-152 grant DynamoDB index Query"
   gh stack submit
   ```
2. **agent**: read the tf_plan comment on the layer 1 PR; check AC 3 if the plan shows only the sre-botSecretsManagerKeyRetrieval policy document change (the three index ARNs).
3. **agent**: plan layer 2 (TASK-145.5.1) with `/plan-task task-145.5.1`; the human approves it in a task comment.
4. **human**: once the plan is approved, create layer 2: `gh stack add stack-k/task-145.5.1-incidents-gsis`.
5. **human**: after layers 0 and 1 are approved, merge them bottom-up (layer 1 is a standalone Terraform merge; merging runs tf_apply against production). Then run the simulation from TASK-152 plan step 4 and paste the output:
   ```
   aws iam simulate-principal-policy --policy-source-arn <sre-bot-ecs-role ARN> --action-names dynamodb:Query --resource-arns <audit trail table ARN>/index/correlation_id-index <webhooks table ARN>/index/x
   ```
6. **agent**: record the simulation output in the TASK-152 notes and check AC 2 (expect allowed, then implicitDeny).

## Open decisions

- None.

## Planning queue

- TASK-145.5.1 (next, item 3), then TASK-145.5.2 to TASK-145.5.7, TASK-27.5, TASK-145.6: each planned in turn after the layer below is implemented.
