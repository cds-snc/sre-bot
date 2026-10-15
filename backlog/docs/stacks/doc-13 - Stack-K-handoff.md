---
id: doc-13
title: Stack K handoff
type: guide
created_date: '2026-10-14 22:27'
updated_date: '2026-10-15 19:48'
---
# Stack K handoff

## Stack

- Name: Stack K, incident core: the IAM and table layout, the service scope opener, the incident record, its end-state store over the records contract and the legacy item bridge, the cutover, the status-update store move, the full-table read and the incident legacy upgrade job, then the core resource interfaces. Trunk: `main`.
- doc-2 line: "Legacy rebuild by surface": Stack K, started 2026-10-14 from `main` after TASK-109 (#1593). TASK-145.5 is the coordinator of TASK-145.5.1 to TASK-145.5.8; its plan lists the layer order and the subtask descriptions hold the decisions.
- Branch names: `stack-k/<task-id>-<slug>`; the planning layer is `stack-k/plan`.
- Merges: squash, bottom-up, a re-approval per layer after its rebase (approve-latest-push rule). Review is requested once two layers are stacked, and at least two PRs stay open before any closes (human, 2026-10-14); a lone PR is not a stack. gh stack closes the stack once every layer has merged (later branches become independent PRs), so new layers are built on lower layers still in review, and a layer merges only when a higher layer is already submitted (human, 2026-10-14). Review changes to a lower layer are made on its branch, then `gh stack rebase`.
- Standalone merges inside the stack: TASK-152 and TASK-145.5.1 (Terraform, merged and applied), TASK-145.5.5 (behaviour change, deployed on its own; layers 5 and 6 must be merged first). TASK-145.5.7 ships switched off and is run after TASK-145.8 deploys, before TASK-145.9 merges, and again after TASK-145.12.
- Decisions of 2026-10-15 (in decisions/incident-management.md, The incident record and Migration, and cloud-portability.md contract 4): stored attributes use the record's own names; one reference map per kind ({system, tenant, vendor_id, url}), replaced whole; `channel_id` top-level as the by_channel lookup copy, filtered by system and tenant; `record_version` marks end-state items; security flag is a required bool (missing legacy value is false); status is strict (legacy values matched ignoring case, anything else unreadable and fixed by hand); the legacy data upgrade rule set (one shared upgrade function, one in-app leased job runner, version marker, legacy attributes left on items).

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 0 | Planning edits (tasks and docs) | `stack-k/plan` | #1594 | merged | Merged 2026-10-15 13:09 UTC. |
| 1 | TASK-152 IAM `/index/*` grants | `stack-k/task-152-iam-index-grants` | #1595 | merged | Task Done. AC 2 still unchecked: post-apply simulation output not recorded (next action 4). |
| 2 | TASK-145.5.1 incidents GSIs, timeline table | `stack-k/task-145.5.1-incidents-gsis` | #1597 | merged | Merged 2026-10-15 16:32 UTC (tf_apply ran). Post-apply evidence pending (next action 5); task not Done yet. |
| 3 | TASK-145.5.2 ServiceScopeOpener | `stack-k/task-145.5.2-service-scope-opener` | #1598 | merged | Merged 2026-10-15 (d1ff7a3c on main); stack synced, layer 4 rebased. Task Done. |
| 4 | TASK-153 ADRs, then TASK-145.5.3 vocabulary, record, references, core settings, tenant ids | `stack-k/task-145.5.3-incident-record` | #1599 | merged | Merged 2026-10-15 19:07 UTC (12805b0a on main); stack already synced (P2 #1721 based on main). Tasks 153 and 145.5.3 Done. `IncidentSecurityFlag` predates the stack (#1549) and goes in TASK-145.5.5. |
| P2 | Planning edits of 2026-10-15: the human's GH-issue task sync, ADR refinement (incident-management.md stored form and legacy data upgrade, cloud-portability.md contract 4), task sync (TASK-145.5.4 split into 145.5.8, TASK-154, dependencies, renames) | `stack-k/task-145.5.4-incident-store` | #1721 | in review | A planning layer despite its name: the branch was created for TASK-145.5.4 before the split, and renaming failed in `gh stack modify` (human kept the name, 2026-10-15; a PR comment explains it). Three commits: f3f3aefd GH-issue task sync, ADRs, tasks and docs. |
| 5 | TASK-145.5.4 IncidentStore end-state reads, incidents RecordTable, fake, full items from index reads | `stack-k/task-145.5.4-end-state-reads` | #1722 | in review | Committed 030ad9b and submitted 2026-10-15; review requested with P2. 8 ACs checked, gates green (5174 passed). ~514 prod lines with docstrings (~345 executable), above the plan's ~390; recorded in the task notes. |
| 6 | TASK-145.5.8 legacy item bridge (`legacy_items.py`), store hook, tenants argument, stored-time formatter | `stack-k/task-145.5.8-legacy-item-bridge` | #1723 | ready | Implemented 2026-10-15: 6 ACs checked, gates green (5300 passed), ~323 prod lines with docstrings (~200 executable). Plan approved 2026-10-15 with four decisions (task comment). Commit and `gh stack submit` are next action 1; PR #1723 then carries the handoff-doc commit 03f6fe3 and the layer. |
| 7 | TASK-145.5.5 configured-systems read; cutover; comms to the bool security flag; narrow Protocols, legacy_incidents and IncidentSecurityFlag deleted | - | - | planned | Standalone merge and deploy; passes the tenants to `RecordIncidentStore` from the configured-systems read. Built on layer 6 and submitted before layers 5 and 6 merge (a higher layer must be open), then merged and deployed alone. Builds the ConversationReference from the configured Slack tenant; size gate to re-check at planning. |
| 8 | TASK-145.5.6 StatusUpdateStore onto RecordStore | - | - | planned | |
| 9 | TASK-27.5 bounded full-table read | - | - | planned | First consumer is layer 10. |
| 10 | TASK-145.5.7 incident legacy upgrade job | - | - | planned | Retitled 2026-10-15 (was the open-index reconcile): upgrades every item without record_version through the bridge, sets the open index, unmatched status fails the run with a list. Re-plan at pickup with a size-gate check. |
| 11 | TASK-145.6 core resource interfaces | - | - | planned | 2026-10-09 plan stale; re-plan after layer 7. Now depends on 145.5.8. |

A planning-only refinement (ADR text, no code) is normally an earlier commit on the layer it refines (human, 2026-10-15); a large planning sync goes on its own planning layer (`stack-k/plan-<n>`, labelled P<n> here so task layer numbers stay stable), as P2 did (its branch kept a task name). No parallel PR or reorder was needed for the split: the bridge needs layer 5's end-state shape and must merge before the layer 7 cutover, so it sits directly above layer 5.

## Position

- Checked out: `stack-k/task-145.5.8-legacy-item-bridge` (layer 6, PR #1723, on top of layer 5 #1722). Open PRs, all review required: #1721 (P2, based on main), #1722 (layer 5), #1723 (layer 6).
- Uncommitted: layer 6 (app/features/incident/core and its tests), this doc, the task files of 145.5.8, 145.5.7, 145.7 and the new TASK-155; all go in the layer 6 commit (next action 1).
- Never stage: `backlog/docs/doc-6*`, `doc-8*`, `doc-11*`, `CDS Incident Management Handbook.md`, `Incident Response Runbook.md`.
- Production data facts (scans, 2026-10-15): 323 incident items; status values include 30 `closed` and 1 `reviewed` in lowercase, nothing else outside the five; security_incident absent on 316 items (only stored since #1549, 2026-10-07); every created_at is an epoch string.
- Local DynamoDB has the incidents GSIs and the timeline table.
- No background agents.
- The stack pauses after layer 6: doc-11 Work queue rows 2 (TASK-103) and 3 (TASK-36.1) are side PRs cut from `main`; the stack's open layers stay in review. It resumes at row 4 (layer 7, TASK-145.5.5).

## Next actions

1. **human**: commit and submit layer 6, then request review on #1723:
   ```
   cd /workspace
   git add app/features/incident/core app/tests/unit/features/incident/core backlog/tasks backlog/docs/stacks
   git commit -m "feat: legacy incident item bridge"
   gh stack submit
   ```
2. **human**: run the TASK-152 post-apply simulation and paste the output:
   ```
   aws iam simulate-principal-policy --policy-source-arn <sre-bot-ecs-role ARN> --action-names dynamodb:Query --resource-arns <audit trail table ARN>/index/correlation_id-index <webhooks table ARN>/index/x
   ```
   **agent**: record it in the TASK-152 notes and check AC 2 (expect allowed, then implicitDeny).
3. **human**: confirm the #1597 tf_apply log shows the two GSI creations and `aws dynamodb describe-table --table-name incidents` shows both indexes ACTIVE; paste for the TASK-145.5.1 notes. **agent**: record the evidence (TASK-145.5.1 is already Done; skip if its notes already carry it).
4. **human**, when the stack resumes (doc-11 row 4): put the next layer on top of the stack:
   ```
   gh stack sync
   gh stack checkout stack-k/task-145.5.8-legacy-item-bridge
   gh stack add stack-k/task-145.5.5-cutover
   ```
   **agent**: /plan-task 145.5.5 on that branch (re-check the size gate), then stop for approval.

## Open decisions

- None blocking. Recorded at task level for their planning: TASK-145.7 chooses dual-write with `extra="ignore"` on the legacy model or shipping with TASK-145.8, and the source_alert shape; TASK-145.8 decides whether a security flag flip triggers actions and how a partial update treats an item without record_version; TASK-154 redesigns the status lifecycle and close.

## Planning queue

- TASK-145.5.5: next to plan, on `stack-k/task-145.5.5-cutover` when the stack resumes (next action 4); re-check the size gate.
- TASK-145.5.6, TASK-27.5, TASK-145.5.7, TASK-145.6: each planned in turn after the layer below is implemented; re-check the size gate on 145.5.7.
