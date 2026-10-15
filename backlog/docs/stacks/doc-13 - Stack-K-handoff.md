---
id: doc-13
title: Stack K handoff
type: guide
created_date: '2026-10-14 22:27'
updated_date: '2026-10-15 13:43'
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
| 0 | Planning edits (tasks and docs) | `stack-k/plan` | #1594 | merged | Merged 2026-10-15 13:09 UTC; stack synced. |
| 1 | TASK-152 IAM `/index/*` grants (audit trail, retry records, incidents) | `stack-k/task-152-iam-index-grants` | #1595 | in review | ACs 1 and 3 checked; tf_plan re-run 2026-10-15 passed (policy update only). AC 2 waits on the post-apply simulation. |
| 2 | TASK-145.5.1 incidents GSIs (ALL), timeline table, devcontainer script run locally | `stack-k/task-145.5.1-incidents-gsis` | #1597 | in review | All 5 ACs checked. tf_plan on 6e67e67 (key_schema GSIs) matches the first plan, no hash_key warning, audit trail and retry records untouched. One apply; post-apply check in next action 6. |
| 3 | TASK-145.5.2 ServiceScopeOpener for Slack and job registrars; dependency-injection.md | `stack-k/task-145.5.2-service-scope-opener` | - | plan approved | Approved 2026-10-15 (task comment). Registrar opener kept over Bolt middleware; mypy type-abstract off repo-wide; contract (l); plugin-architecture.md line. 12 files, judged acceptable. |
| 4 | TASK-145.5.3 vocabulary, record, references, core settings, platform tenant ids | - | - | planned | Plan settles how the Google customer id is validated (no Google enabled flag today). |
| 5 | TASK-145.5.4 IncidentStore over RecordStore (reads), fake, index reads return full items | - | - | planned | |
| 6 | TASK-145.5.5 cutover; narrow Protocols and legacy_incidents deleted | - | - | planned | Standalone merge and deploy after layers 1 and 2 are applied. |
| 7 | TASK-145.5.6 StatusUpdateStore onto RecordStore | - | - | planned | |
| 8 | TASK-27.5 bounded full-table read | - | - | planned | Pulled forward; first consumer is layer 9. |
| 9 | TASK-145.5.7 open-index reconcile, off by default | - | - | planned | Runner tentative (in-app leased job); options and references in the task, re-assessed at planning. |
| 10 | TASK-145.6 core resource interfaces | - | - | planned | 2026-10-09 plan stale; re-plan after layer 6 is implemented. |

## Position

- Checked out: `stack-k/task-145.5.2-service-scope-opener` (created with `gh stack add`, no own commit yet; sits on 4d7f7a0). #1594 merged; #1595 (base `main`) and #1597 (base `stack-k/task-152-iam-index-grants`, head 4d7f7a0) open, review required.
- Uncommitted, layer 3: `backlog/docs/stacks/doc-13*` (this doc), `backlog/tasks/task-145.5.2 -*` (approved plan, ACs 5 and 6 added, approval comment).
- Never stage: `backlog/docs/doc-6*`, `doc-8*`, `doc-11*`, `CDS Incident Management Handbook.md`, `Incident Response Runbook.md`.
- Local DynamoDB has the incidents GSIs and the timeline table.
- Local only: an ignored `app/infrastructure/idempotency/__pycache__` directory makes `test_old_idempotency_package_is_not_discoverable` fail; `rm -rf app/infrastructure/idempotency` clears it (cache files only).
- No background agents.

## Next actions

1. **human**: commit the plan and open layer 3's PR:
   ```
   git add "backlog/docs/stacks/doc-13 - Stack-K-handoff.md" "backlog/tasks/task-145.5.2 - Per-invocation-service-scopes-for-non-HTTP-entry-points-a-ServiceScopeOpener-on-the-Slack-and-background-job-registrars.md"
   git commit -m "TASK-145.5.2 plan"
   gh stack submit
   ```
2. **human**: request review of #1595 and #1597 if not yet done. Merge layer 1 (#1595, standalone Terraform; tf_apply against production) once approved. Then `gh stack sync`, `gh stack submit`, and run the simulation from TASK-152 plan step 4, pasting the output:
   ```
   aws iam simulate-principal-policy --policy-source-arn <sre-bot-ecs-role ARN> --action-names dynamodb:Query --resource-arns <audit trail table ARN>/index/correlation_id-index <webhooks table ARN>/index/x
   ```
3. **agent**: record the simulation output in the TASK-152 notes and check AC 2 (expect allowed, then implicitDeny). Human: `backlog task edit 152 --status Done` (committed with the next layer).
4. **human**: once layer 3 is submitted and #1597 re-approved after the rebase, merge layer 2 (standalone Terraform; tf_apply against production). Confirm the tf_apply log shows the two GSI creations in sequence and `aws dynamodb describe-table --table-name incidents` shows both indexes ACTIVE; paste for the TASK-145.5.1 notes.
5. **agent**: record the apply evidence in the TASK-145.5.1 notes. Human: `backlog task edit 145.5.1 --status Done` (committed with the next layer).
6. **agent**: implement layer 3 (TDD) against the approved plan.

## Open decisions

- None. (`aws_access_requests` is unused today but kept for the access feature enhancements; revisit when that work starts.)

## Planning queue

- TASK-145.5.3 to TASK-145.5.7, TASK-27.5, TASK-145.6: each planned in turn after the layer below is implemented.
