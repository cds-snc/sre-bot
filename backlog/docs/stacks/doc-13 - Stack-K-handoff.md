---
id: doc-13
title: Stack K handoff
type: guide
created_date: '2026-10-14 22:27'
updated_date: '2026-10-19 19:19'
---
# Stack K handoff

## Stack

- Name: Stack K, incident core: the IAM and table layout, the service scope opener, the incident record, its end-state store over the records contract and the legacy item bridge, the cutover, the status-update store move, the full-table read and the incident legacy upgrade job, then the core resource interfaces. Trunk: `main`.
- doc-2 line: "Legacy rebuild by surface": Stack K, started 2026-10-14 from `main` after TASK-109 (#1593). TASK-145.5 is the coordinator of TASK-145.5.1 to TASK-145.5.10; its plan lists the layer order and the subtask descriptions hold the decisions.
- Branch names: `stack-k/<task-id>-<slug>`; the planning layer is `stack-k/plan`.
- Merges: squash, bottom-up, a re-approval per layer after its rebase (approve-latest-push rule). Review is requested once two layers are stacked, and at least two PRs stay open before any closes (human, 2026-10-14); a lone PR is not a stack. gh stack closes the stack once every layer has merged (later branches become independent PRs), so new layers are built on lower layers still in review, and a layer merges only when a higher layer is already submitted (human, 2026-10-14). Review changes to a lower layer are made on its branch, then `gh stack rebase`.
- Standalone merges inside the stack: TASK-152 and TASK-145.5.1 (Terraform, merged and applied), TASK-145.5.5 (behaviour change, deployed on its own; layers 5 to 8 must be merged first). TASK-145.5.7 ships switched off and is run after TASK-145.8 deploys, before TASK-145.9 merges, and again after TASK-145.12.
- Merge order with the P2 side PRs (human, 2026-10-19; also in the TASK-145.5.5 description): TASK-24.4 (Google settings move, edits `server/configured_systems.py`) follows the #1728 merge; TASK-24.5 (Google and Slack tenant entries, deletes `infrastructure/configuration/integrations/`) merges only after the TASK-145.5.5 cutover has deployed and been checked, never in the cutover's deploy.
- Decisions of 2026-10-15 (in decisions/incident-management.md, The incident record and Migration, and cloud-portability.md contract 4): stored attributes use the record's own names; one reference map per kind ({system, tenant, vendor_id, url}), replaced whole; `channel_id` top-level as the by_channel lookup copy, filtered by system and tenant; `record_version` marks end-state items; security flag is a required bool (missing legacy value is false); status is strict (legacy values matched ignoring case, anything else unreadable and fixed by hand); the legacy data upgrade rule set (one shared upgrade function, one in-app leased job runner, version marker, legacy attributes left on items).
- Decisions of 2026-10-19 (TASK-145.5.5 planning): TASK-145.5.5 split into TASK-145.5.9 (configured-systems read, layer 7), TASK-145.5.10 (store builder, layer 8) and the cutover (layer 9). The new-incident policy resolves only on the declare path at startup (decisions/incident-management.md amended; TASK-145.7 AC9), because production configures Slack and Google with the policy unset and the feature-wide skip would have removed every incident command. The entry point builds the ConversationReference and passes it with the IncidentStore to comms. Skip events fire once at startup. The configured-systems implementation is host code in app/server/configured_systems.py, and the read is tenants() -> Mapping[WorkplaceSystem, str].

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 0 | Planning edits (tasks and docs) | `stack-k/plan` | #1594 | merged | Merged 2026-10-15 13:09 UTC. |
| 1 | TASK-152 IAM `/index/*` grants | `stack-k/task-152-iam-index-grants` | #1595 | merged | Task Done. AC 2 still unchecked: post-apply simulation output not recorded (next action 6). |
| 2 | TASK-145.5.1 incidents GSIs, timeline table | `stack-k/task-145.5.1-incidents-gsis` | #1597 | merged | Merged 2026-10-15 16:32 UTC (tf_apply ran). Post-apply evidence pending (next action 7). |
| 3 | TASK-145.5.2 ServiceScopeOpener | `stack-k/task-145.5.2-service-scope-opener` | #1598 | merged | Merged 2026-10-15 (d1ff7a3c on main). Task Done. |
| 4 | TASK-153 ADRs, then TASK-145.5.3 vocabulary, record, references, core settings, tenant ids | `stack-k/task-145.5.3-incident-record` | #1599 | merged | Merged 2026-10-15 19:07 UTC (12805b0a on main). Tasks 153 and 145.5.3 Done. `IncidentSecurityFlag` predates the stack (#1549) and goes in TASK-145.5.5. |
| P2 | Planning edits of 2026-10-15 (GH-issue task sync, ADR refinement, TASK-145.5.4 split) | `stack-k/task-145.5.4-incident-store` | #1721 | merged | Merged 2026-10-19 16:35 UTC (e2ff8ac1 on main). A planning layer despite its branch name (rename failed in `gh stack modify`). |
| 5 | TASK-145.5.4 IncidentStore end-state reads, incidents RecordTable, fake, full items from index reads | `stack-k/task-145.5.4-end-state-reads` | #1722 | merged | Merged 2026-10-19 17:33 UTC (865b143b on main). Task still In Progress: human sets Done (next action 1). |
| 6 | TASK-145.5.8 legacy item bridge (`legacy_items.py`), store hook, tenants argument, stored-time formatter | `stack-k/task-145.5.8-legacy-item-bridge` | #1723 | merged | Merged 2026-10-19 18:04 UTC (58fde475 on main; the squash took the title of its handoff-doc commit). Task Done. |
| 7 | TASK-145.5.9 configured-systems read: ConfiguredSystems Protocol in contracts/workplace, host implementation in server/configured_systems.py, core service, registry fake | `stack-k/task-145.5.5-cutover` | #1728 | in review | Submitted 2026-10-19 (c8a3a1f4); base is now `main`. Branch keeps its pre-split name (rename failed; a PR comment explains it). The remote branch is already rebased onto `main` (same three patches); the local branch is stale until `gh stack sync` after the layer 8 commit (`gh stack view` shows a warning). Merges once layer 8 is submitted above it; TASK-24.4 follows that merge. |
| 8 | TASK-145.5.10 IncidentStore builder: `build_incident_store(records, systems, settings)` in core/api.py from a resolved RecordStore, the incident core settings and the configured tenants; no policy read | `stack-k/task-145.5.10-incident-store-builder` | - | ready | Plan approved 2026-10-19 (option A: takes the IncidentCoreSettings slice). Implemented 2026-10-19: 4 ACs checked, gates green (5373 passed), 1 prod file (+20/-3 with docstring); tests in `test_incident_core_api_build_incident_store.py` plus the api surface test. Nothing calls it until layer 9 adds the entry-point callers; no behaviour change. Commit and submit pending (next action 1). |
| 9 | TASK-145.5.5 cutover: entry points build the store and the ConversationReference; comms on IncidentStore and the bool security flag; startup registration check; narrow Protocols, legacy_incidents and IncidentSecurityFlag deleted | - | - | planned | Standalone merge and deploy, only after layers 5 to 8 have merged and with layer 10 submitted above it. TASK-24.5 merges only after this has deployed and been checked. ~200 changed, ~260 deleted, ~28 test files edited; size gate to re-check at planning. |
| 10 | TASK-145.5.6 StatusUpdateStore onto RecordStore | - | - | planned | |
| 11 | TASK-27.5 bounded full-table read | - | - | planned | First consumer is layer 12. |
| 12 | TASK-145.5.7 incident legacy upgrade job | - | - | planned | Upgrades every item without record_version through the bridge, sets the open index, unmatched status fails the run with a list. Re-plan at pickup with a size-gate check. |
| 13 | TASK-145.6 core resource interfaces | - | - | planned | 2026-10-09 plan stale; re-plan after layer 9. Depends on 145.5.8. |

A planning-only refinement (ADR text, no code) is normally an earlier commit on the layer it refines (human, 2026-10-15); a large planning sync goes on its own planning layer (`stack-k/plan-<n>`, labelled P<n> here so task layer numbers stay stable), as P2 did.

## Position

- Checked out: `stack-k/task-145.5.10-incident-store-builder` (layer 8), no commits of its own yet. Uncommitted, all for the layer 8 commit: `app/features/incident/core/api.py`, the two api tests, this doc, and the task files of TASK-145.5.10, TASK-145.5.4 (Done) and TASK-145.5.5 (TASK-24 merge order).
- Open PRs: #1728 (layer 7) in review, the only open layer; layer 8 must be submitted before it merges.
- Local branches still carry the pre-squash commits of layers 5 and 6 until `gh stack sync` runs after the layer 8 commit (next action 1).
- Never stage: `backlog/docs/doc-6*`, `doc-8*`, `doc-11*`, `CDS Incident Management Handbook.md`, `Incident Response Runbook.md`.
- Production data facts (scans, 2026-10-15): 323 incident items; status values include 30 `closed` and 1 `reviewed` in lowercase, nothing else outside the five; security_incident absent on 316 items (only stored since #1549, 2026-10-07); every created_at is an epoch string. Production configures Slack (SLACK_TEAM_ID in SSM) and Google (GCP_SRE_SERVICE_ACCOUNT_KEY_FILE, terraform/ecs.tf:30); INCIDENT_CORE__NEW_INCIDENT_SYSTEM is not set anywhere.
- Local DynamoDB has the incidents GSIs and the timeline table.
- No background agents.

## Next actions

1. **human**: commit layer 8, then sync and submit (sync rebases layers 7 and 8 onto `main`, dropping the pre-squash layer 5 and 6 commits; submit opens the layer 8 PR):
   ```
   git add app/features/incident/core/api.py app/tests/unit/features/incident/core/test_incident_core_api_build_incident_store.py app/tests/unit/features/incident/core/test_incident_core_api_surface.py "backlog/docs/stacks/doc-13 - Stack-K-handoff.md" backlog/tasks
   git commit -m "feat: IncidentStore builder"
   gh stack sync
   gh stack submit
   ```
2. **human**: request review of the layer 8 PR; get #1728 re-approved after the sync push and merge it (layer 8 is then the submitted layer above). TASK-24.4 (doc-11 row 6c) follows that merge.
3. The stack pauses for the doc-11 P2 side rows (6a TASK-24.2, 6b TASK-24.3, 6c TASK-24.4); layer 8 stays in review.
4. **human**, when the stack resumes at row 7: `gh stack checkout stack-k/task-145.5.10-incident-store-builder` then `gh stack add stack-k/task-145.5.5-cutover-entry-points` (the old `task-145.5.5-cutover` name is taken by layer 7). **agent**: /plan-task 145.5.5, stopping for approval.
5. Layer 9 merges and deploys alone after layers 7 and 8 have merged; TASK-24.5 waits for that deploy to be checked.
6. **human**: run the TASK-152 post-apply simulation and paste the output:
   ```
   aws iam simulate-principal-policy --policy-source-arn <sre-bot-ecs-role ARN> --action-names dynamodb:Query --resource-arns <audit trail table ARN>/index/correlation_id-index <webhooks table ARN>/index/x
   ```
   **agent**: record it in the TASK-152 notes and check AC 2 (expect allowed, then implicitDeny).
7. **human**: confirm the #1597 tf_apply log shows the two GSI creations and `aws dynamodb describe-table --table-name incidents` shows both indexes ACTIVE; paste for the TASK-145.5.1 notes. **agent**: record the evidence (skip if its notes already carry it).

## Open decisions

- Recorded at task level for their planning: TASK-145.7 chooses dual-write with `extra="ignore"` on the legacy model or shipping with TASK-145.8, and the source_alert shape; TASK-145.8 decides whether a security flag flip triggers actions and how a partial update treats an item without record_version; TASK-154 redesigns the status lifecycle and close.

## Planning queue

- TASK-145.5.5: next to plan, on layer 9 (next action 4); the 2026-10-19 decisions and the TASK-24 merge order are in its description; re-check the size gate (~28 test files move to the in-memory store).
- TASK-145.5.6, TASK-27.5, TASK-145.5.7, TASK-145.6: each planned in turn after the layer below is implemented; re-check the size gate on 145.5.7.
