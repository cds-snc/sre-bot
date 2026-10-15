---
id: doc-13
title: Stack K handoff
type: guide
created_date: '2026-10-14 22:27'
updated_date: '2026-10-15 16:36'
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
| 1 | TASK-152 IAM `/index/*` grants (audit trail, retry records, incidents) | `stack-k/task-152-iam-index-grants` | #1595 | merged | Merged and task Done. AC 2 still unchecked: the post-apply simulation output was never recorded (next action 4). |
| 2 | TASK-145.5.1 incidents GSIs (ALL), timeline table, devcontainer script run locally | `stack-k/task-145.5.1-incidents-gsis` | #1597 | merged | Merged 2026-10-15 16:32 UTC (tf_apply ran). All 5 ACs checked. Post-apply evidence pending (next action 4); task not Done yet. |
| 3 | TASK-145.5.2 ServiceScopeOpener for Slack and job registrars; dependency-injection.md | `stack-k/task-145.5.2-service-scope-opener` | #1598 | in review | Committed 2f0a3cf and submitted. All 6 ACs checked, gates green (4901 passed). |
| 4 | TASK-153 vendor enablement ADRs (earlier commit), then TASK-145.5.3 vocabulary, record, references, core settings, platform tenant ids | `stack-k/task-145.5.3-incident-record` | #1599 | planned | Commit 398d311 (TASK-153 + plan) submitted as #1599. TASK-153 set Done by the human (task-file edit uncommitted, goes in the implementation commit). TASK-153 implemented 2026-10-15: 7 ADRs amended, TASK-24/112/145.5.4/145.5.5 descriptions synced, all 6 ACs checked, gates green (ruff clean, 4901 passed); In Progress. Follow-up the same day: a transport switched on without its vendor entry fails boot; an absent vendor is never a failure; the new-incident policy is unset by default and resolves to the only configured system. TASK-145.5.3 plan revised with the human's decisions (opaque tenant ids, my_customer rejected, closed WorkplaceSystem, policy unset by default, Severity unset is None, named roles, api exports); awaiting explicit approval. Deploy needs SLACK_TEAM_ID and the real GOOGLE_WORKSPACE_CUSTOMER_ID in sre-bot-config SSM first. |
| 5 | TASK-145.5.4 IncidentStore over RecordStore (reads), fake, index reads return full items | - | - | planned | Tolerant WorkplaceSystem read of stored values (synced by TASK-153). |
| 6 | TASK-145.5.5 cutover; narrow Protocols and legacy_incidents deleted | - | - | planned | Standalone merge and deploy after layers 1 and 2 are applied. Checks the new-incident policy against the configured systems. |
| 7 | TASK-145.5.6 StatusUpdateStore onto RecordStore | - | - | planned | |
| 8 | TASK-27.5 bounded full-table read | - | - | planned | Pulled forward; first consumer is layer 9. |
| 9 | TASK-145.5.7 open-index reconcile, off by default | - | - | planned | Runner tentative (in-app leased job); options and references in the task, re-assessed at planning. |
| 10 | TASK-145.6 core resource interfaces | - | - | planned | 2026-10-09 plan stale; re-plan after layer 6 is implemented. |

A planning-only refinement (ADR text, no code) is not its own layer: it is an earlier commit on the layer it refines (human, 2026-10-15).

## Position

- Checked out: `stack-k/task-145.5.3-incident-record` at 398d311 (TASK-153 vendor enablement; TASK-145.5.3 plan), submitted as #1599 (base #1598's branch). #1595 and #1597 merged; #1598 and #1599 open, review required.
- Uncommitted, layer 4: TASK-153 task file (status Done, set by the human).
- Never stage: `backlog/docs/doc-6*`, `doc-8*`, `doc-11*`, `CDS Incident Management Handbook.md`, `Incident Response Runbook.md`.
- Local DynamoDB has the incidents GSIs and the timeline table.
- No background agents.

## Next actions

1. **human**: approve the revised TASK-145.5.3 plan in chat. **agent**: record the approval as a task comment, set TASK-145.5.3 In Progress, then implement it with TDD (failing tests first) and run the gates.
2. **human**: commit the TASK-145.5.3 implementation (with the TASK-153 Done edit and this doc) on the same branch and `gh stack submit`; request review of #1599 together with #1598.
3. **human**: run the TASK-152 post-apply simulation and paste the output:
   ```
   aws iam simulate-principal-policy --policy-source-arn <sre-bot-ecs-role ARN> --action-names dynamodb:Query --resource-arns <audit trail table ARN>/index/correlation_id-index <webhooks table ARN>/index/x
   ```
   **agent**: record it in the TASK-152 notes and check AC 2 (expect allowed, then implicitDeny).
4. **human**: confirm the #1597 tf_apply log shows the two GSI creations in sequence and `aws dynamodb describe-table --table-name incidents` shows both indexes ACTIVE; paste for the TASK-145.5.1 notes. **agent**: record the evidence; human: `backlog task edit 145.5.1 --status Done` (committed with the next layer).
5. **human**: before layer 4 deploys, add SLACK_TEAM_ID (Slack auth.test team_id) and the real GOOGLE_WORKSPACE_CUSTOMER_ID (Admin console, Account settings > Profile) to sre-bot-config SSM for every environment.

## Open decisions

- Persisted-enum rule lives only in cloud-portability.md (contract 4); workplace-systems.md rule 4 points to it. Move it if preferred.
- None else. (`aws_access_requests` is unused today but kept for the access feature enhancements; revisit when that work starts.)

## Planning queue

- TASK-145.5.3: revised plan waiting on approval.
- TASK-145.5.4 to TASK-145.5.7, TASK-27.5, TASK-145.6: each planned in turn after the layer below is implemented.
