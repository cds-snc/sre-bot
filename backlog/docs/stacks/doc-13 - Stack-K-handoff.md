---
id: doc-13
title: Stack K handoff
type: guide
created_date: '2026-10-14 22:27'
updated_date: '2026-10-15 17:06'
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
| 3 | TASK-145.5.2 ServiceScopeOpener for Slack and job registrars; dependency-injection.md | `stack-k/task-145.5.2-service-scope-opener` | #1598 | in review | Rebased as 42c6e34 after #1597 merged; submitted. All 6 ACs checked, gates green (4901 passed). |
| 4 | TASK-153 vendor enablement ADRs (earlier commit), then TASK-145.5.3 vocabulary, record, references, core settings, platform tenant ids | `stack-k/task-145.5.3-incident-record` | #1599 | in progress | 03f00e9 (TASK-153 + plan) and f88a231 (TASK-153 Done) submitted. TASK-145.5.3 implemented 2026-10-15 (uncommitted): all 9 ACs checked, gates green (ruff clean, lint-imports 12 kept, mypy 0 in touched files, 4998 passed); In Progress. Deploy needs SLACK_TEAM_ID and the real GOOGLE_WORKSPACE_CUSTOMER_ID in sre-bot-config SSM first (next action 5). |
| 5 | TASK-145.5.4 IncidentStore over RecordStore (reads), fake, index reads return full items | `stack-k/task-145.5.4-incident-store` | - | planned | Tolerant WorkplaceSystem read of stored values (synced by TASK-153). Tenant ids passed in at construction. |
| 6 | TASK-145.5.5 configured-systems read; cutover; narrow Protocols and legacy_incidents deleted | - | - | planned | Standalone merge and deploy after layers 1 and 2 are applied. Builds the configured-systems read and checks the new-incident policy against it; size gate to re-check at planning. |
| 7 | TASK-145.5.6 StatusUpdateStore onto RecordStore | - | - | planned | |
| 8 | TASK-27.5 bounded full-table read | - | - | planned | Pulled forward; first consumer is layer 9. |
| 9 | TASK-145.5.7 open-index reconcile, off by default | - | - | planned | Runner tentative (in-app leased job); options and references in the task, re-assessed at planning. |
| 10 | TASK-145.6 core resource interfaces | - | - | planned | 2026-10-09 plan stale; re-plan after layer 6 is implemented. |

A planning-only refinement (ADR text, no code) is not its own layer: it is an earlier commit on the layer it refines (human, 2026-10-15).

## Position

- Checked out: `stack-k/task-145.5.3-incident-record` at f88a231, submitted as #1599 (base #1598's branch). #1595 and #1597 merged; #1598 and #1599 open, review required.
- Uncommitted, layer 4: the TASK-145.5.3 implementation under app/ (contracts/workplace/, features/incident/common/, core/domain.py and api.py, Slack and Google settings, server/lifespan.py, pyproject.toml, README, tests), decisions/workplace-systems.md, TASK-145.5.3/145.5.4/145.5.5 task files, this doc.
- Never stage: `backlog/docs/doc-6*`, `doc-8*`, `doc-11*`, `CDS Incident Management Handbook.md`, `Incident Response Runbook.md`.
- Local DynamoDB has the incidents GSIs and the timeline table. A local .env with Slack on or the Google key set needs SLACK_TEAM_ID and a real GOOGLE_WORKSPACE_CUSTOMER_ID, or the app no longer boots.
- No background agents.

## Next actions

1. **human**: commit the TASK-145.5.3 implementation on layer 4, submit, request review of #1599 together with #1598, then create layer 5:
   ```
   git add app decisions/workplace-systems.md backlog/tasks "backlog/docs/stacks/doc-13 - Stack-K-handoff.md"
   git commit -m "TASK-145.5.3 incident record and tenant ids"
   gh stack submit
   gh stack add stack-k/task-145.5.4-incident-store
   ```
2. **agent**: plan TASK-145.5.4 with /plan-task on `stack-k/task-145.5.4-incident-store` (tenant ids passed in at construction; tolerant WorkplaceSystem, IncidentStatus and Severity reads); **human** approves in chat.
3. **human**: run the TASK-152 post-apply simulation and paste the output:
   ```
   aws iam simulate-principal-policy --policy-source-arn <sre-bot-ecs-role ARN> --action-names dynamodb:Query --resource-arns <audit trail table ARN>/index/correlation_id-index <webhooks table ARN>/index/x
   ```
   **agent**: record it in the TASK-152 notes and check AC 2 (expect allowed, then implicitDeny).
4. **human**: confirm the #1597 tf_apply log shows the two GSI creations in sequence and `aws dynamodb describe-table --table-name incidents` shows both indexes ACTIVE; paste for the TASK-145.5.1 notes. **agent**: record the evidence; human: `backlog task edit 145.5.1 --status Done` (committed with the next layer).
5. **human**: before #1599 merges, add SLACK_TEAM_ID (Slack auth.test team_id) and the real GOOGLE_WORKSPACE_CUSTOMER_ID (Admin console, Account settings > Profile) to the sre-bot-config SSM parameter in every account that runs the bot; ECS injects GCP_SRE_SERVICE_ACCOUNT_KEY_FILE, so Google counts as in use there.

## Open decisions

- Persisted-enum rule lives only in cloud-portability.md (contract 4); workplace-systems.md rule 4 points to it. Move it if preferred.
- None else. (`aws_access_requests` is unused today but kept for the access feature enhancements; revisit when that work starts.)

## Planning queue

- TASK-145.5.4: next, planned on its own branch (next action 2).
- TASK-145.5.5 to TASK-145.5.7, TASK-27.5, TASK-145.6: each planned in turn after the layer below is implemented; TASK-145.5.5 now also builds the configured-systems read, so re-check its size gate.
