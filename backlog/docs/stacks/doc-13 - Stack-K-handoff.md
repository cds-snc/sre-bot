---
id: doc-13
title: Stack K handoff
type: guide
created_date: '2026-10-14 22:27'
updated_date: '2026-10-20 19:30'
---
# Stack K handoff

## Stack

- Name: Stack K, incident core: the IAM and table layout, the service scope opener, the incident record, its end-state store over the records contract and the legacy item bridge, the cutover, the status-update store move and the incident legacy upgrade job, then the core resource interfaces. TASK-27.5 (full-table read) and TASK-157 (Slack tenant guard) are single PRs from main that layer 11 waits on. Trunk: `main`.
- doc-2 line: "Legacy rebuild by surface": Stack K, started 2026-10-14 from `main` after TASK-109 (#1593). TASK-145.5 is the coordinator of TASK-145.5.1 to TASK-145.5.10; its plan lists the layer order and the subtask descriptions hold the decisions.
- Branch names: `stack-k/<task-id>-<slug>`; the planning layer is `stack-k/plan`.
- Merges: squash, bottom-up, a re-approval per layer after its rebase (approve-latest-push rule). Review is requested once two layers are stacked, and at least two PRs stay open before any closes (human, 2026-10-14); a lone PR is not a stack. gh stack closes the stack once every layer has merged (later branches become independent PRs), so new layers are built on lower layers still in review, and a layer merges only when a higher layer is already submitted (human, 2026-10-14). Review changes to a lower layer are made on its branch, then `gh stack rebase`.
- Standalone merges inside the stack: TASK-152 and TASK-145.5.1 (Terraform, merged and applied), TASK-145.5.5 (behaviour change, deployed on its own; layers 5 to 8 must be merged first). TASK-145.5.7 ships switched off and is run after TASK-145.8 deploys, before TASK-145.9 merges, and again after TASK-145.12.
- Merge order with the P2 side PRs (human, 2026-10-19; also in the TASK-145.5.5 description): TASK-24.4 (Google settings move, edits `server/configured_systems.py`) follows the #1728 merge; TASK-24.5 (Google and Slack tenant entries, deletes `infrastructure/configuration/integrations/`) merges only after the TASK-145.5.5 cutover has deployed and been checked, never in the cutover's deploy.
- Decisions of 2026-10-15 (in decisions/incident-management.md, The incident record and Migration, and cloud-portability.md contract 4): stored attributes use the record's own names; one reference map per kind ({system, tenant, vendor_id, url}), replaced whole; `channel_id` top-level as the by_channel lookup copy, filtered by system and tenant; `record_version` marks end-state items; security flag is a required bool (missing legacy value is false); status is strict (legacy values matched ignoring case, anything else unreadable and fixed by hand); the legacy data upgrade rule set (one shared upgrade function, one in-app leased job runner, version marker, legacy attributes left on items).
- Decisions of 2026-10-20 (TASK-27.5 planning and the SLACK_TEAM_ID review, human): TASK-27.5 ships as a single PR from main, not a stack layer (it builds on no layer; doc-2 parallel single PRs). The full-table read is RecordStore.read_all(table, *, max_items): all or RECORD_READ_LIMIT_EXCEEDED, strongly consistent, unordered, never a lookup or listing (cloud-portability.md contract 4, written in TASK-27.5's first commit). SLACK_TEAM_ID is kept as the expected tenant and must be verified: TASK-157 adds the per-request guard (refuse and log slack_tenant_mismatch) and the optional SLACK_ENTERPRISE_ID (the Enterprise org id is the tenant when set); TASK-145.5.7 checks auth.test before apply and logs a warning for a by_channel candidate dropped for its tenant. References keep the tenant because vendor ids are scoped by their issuer (workplace-systems.md rules 3 and 4). No change to layers 9 and 10: nothing persists a tenant before TASK-145.5.7 and TASK-145.7.
- Decisions of 2026-10-20 (TASK-145.5.6 planning, checked against the ADRs and doc-11): a status-update append at a taken sequence and a transition whose guard no longer holds are conflicts, also on a repeat of a write that landed (records contract and decisions/reliability.md; the comms callers re-read once, as IncidentStore.update_field will in TASK-145.8); `store` is a required argument of the comms services (decisions/dependency-injection.md); every store over the records contract in incident core lives in core/store.py, one store.py per package (decisions/feature-packages.md, enforced by the TASK-114 shape check), not one module per store.
- Decisions of 2026-10-19 (TASK-145.5.5 planning): TASK-145.5.5 split into TASK-145.5.9 (configured-systems read, layer 7), TASK-145.5.10 (store builder, layer 8) and the cutover (layer 9). The new-incident policy resolves only on the declare path at startup (decisions/incident-management.md amended; TASK-145.7 AC9), because production configures Slack and Google with the policy unset and the feature-wide skip would have removed every incident command. The entry point builds the ConversationReference and passes it with the IncidentStore to comms. Skip events fire once at startup. The configured-systems implementation is host code in app/server/configured_systems.py, and the read is tenants() -> Mapping[WorkplaceSystem, str].

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 0 | Planning edits (tasks and docs) | `stack-k/plan` | #1594 | merged | Merged 2026-10-15 13:09 UTC. |
| 1 | TASK-152 IAM `/index/*` grants | `stack-k/task-152-iam-index-grants` | #1595 | merged | Task Done. AC 2 still unchecked: post-apply simulation output not recorded (next action 5). |
| 2 | TASK-145.5.1 incidents GSIs, timeline table | `stack-k/task-145.5.1-incidents-gsis` | #1597 | merged | Merged 2026-10-15 16:32 UTC (tf_apply ran). Post-apply evidence pending (next action 7). |
| 3 | TASK-145.5.2 ServiceScopeOpener | `stack-k/task-145.5.2-service-scope-opener` | #1598 | merged | Task Done. |
| 4 | TASK-153 ADRs, then TASK-145.5.3 vocabulary, record, references, core settings, tenant ids | `stack-k/task-145.5.3-incident-record` | #1599 | merged | Tasks 153 and 145.5.3 Done. |
| P2 | Planning edits of 2026-10-15 | `stack-k/task-145.5.4-incident-store` | #1721 | merged | A planning layer despite its branch name. |
| 5 | TASK-145.5.4 IncidentStore end-state reads | `stack-k/task-145.5.4-end-state-reads` | #1722 | merged | Task Done. |
| 6 | TASK-145.5.8 legacy item bridge | `stack-k/task-145.5.8-legacy-item-bridge` | #1723 | merged | Task Done. |
| 7 | TASK-145.5.9 configured-systems read | `stack-k/task-145.5.5-cutover` | #1728 | merged | Branch keeps its pre-split name. Task Done. |
| 8 | TASK-145.5.10 IncidentStore builder | `stack-k/task-145.5.10-incident-store-builder` | #1730 | merged | Merged 2026-10-20 17:18 UTC (fd90c402). Task Done. |
| 9 | TASK-145.5.5 cutover: entry points build IncidentStore and the ConversationReference; comms on IncidentStore and the bool security flag; legacy_incidents and IncidentSecurityFlag deleted | `stack-k/task-145.5.5-incident-cutover` | #1734 | merged | Merged 2026-10-20 18:52 UTC (a2b65676), with its planning commit answering the review question (Slack tenant ADR edits, TASK-157). Task Done. Post-deploy check pending (next action 4). |
| 10 | TASK-145.5.6 status-update store on RecordStore: Protocol and RecordStatusUpdateStore in core/store.py, item layout in core/adapters/status_updates.py, STATUS_UPDATES_TABLE setting, build_status_update_store in core/api.py, comms `store` required and built in every Slack listener's scope | `stack-k/task-145.5.6-status-update-store` | #1735 | in review | Rebased on main after #1734: 339c3d0b (feature), c3a43f9c (task Done), cde5e21e (handoff). Review required. Merges once layer 11 is submitted above it (the stack keeps an open layer). |
| 11 | TASK-145.5.7 incident legacy upgrade job | - | - | planned | Built on layer 10 after TASK-27.5 and TASK-157 merge (single PRs from main). Re-plan at pickup with a size-gate check. AC6 (2026-10-20): read_all with INCIDENT_CORE__FULL_READ_MAX_ITEMS (default 10000), added in this layer; AC7: auth.test tenant check before apply; AC8: by_channel tenant-drop warning. |
| 12 | TASK-145.6 core resource interfaces | - | - | planned | 2026-10-09 plan stale; re-plan at pickup. |

A planning-only refinement (ADR text, no code) is normally an earlier commit on the layer it refines (human, 2026-10-15); a large planning sync goes on its own planning layer (`stack-k/plan-<n>`, labelled P<n> here so task layer numbers stay stable), as P2 did.

## Position

- Stack K top: `stack-k/task-145.5.6-status-update-store` (layer 10, #1735). Layer 11 (TASK-145.5.7) waits on two single PRs from main: TASK-27.5 (implemented on `task-27.5-records-read-all`, gates green, PR to open) and TASK-157 (to plan). The stack pauses until both merge; #1735 stays open as the top layer (doc-2 pause rule).
- This doc is updated from the TASK-27.5 session and committed on layer 10 (next action 1).
- Open PRs: #1735 (layer 10, review required).
- Never stage: `backlog/docs/doc-6*`, `doc-8*`, `doc-11*`, `CDS Incident Management Handbook.md`, `Incident Response Runbook.md`.
- Records contract note (from layer 10): `RecordStore.update` returns NOT_FOUND for a missing item without an error code and for a missing table with the backend's code; RecordStatusUpdateStore relies on that difference. TASK-145.8 (IncidentStore.update_field) meets the same case.
- Records contract note (TASK-27.5): `RecordStore.read_all(table, *, max_items)` returns every item or PERMANENT_ERROR with RECORD_READ_LIMIT_EXCEEDED; layer 11 passes INCIDENT_CORE__FULL_READ_MAX_ITEMS (its AC6).
- Production data facts (scans, 2026-10-15): 323 incident items; status values include 30 `closed` and 1 `reviewed` in lowercase; security_incident absent on 316 items; every created_at is an epoch string. Production configures Slack and Google; INCIDENT_CORE__NEW_INCIDENT_SYSTEM is not set anywhere. SLACK_TEAM_ID lives in sre-bot-config-infrastructure.
- Local DynamoDB has the incidents GSIs and the timeline table.
- No background agents.

## Next actions

1. **human**: commit this doc on layer 10 (the file is prepared in the session scratchpad; see the session's hand-over), then `gh stack submit`; request review of #1735.
2. **human**: TASK-27.5 single PR (commands in the session hand-over): ADR commit, feature commit, open the PR, then its Done commit as the last commit before merge.
3. **human**: run `auth.test` with the production bot token and report whether it returns `enterprise_id` (decides whether production sets SLACK_ENTERPRISE_ID under TASK-157).
4. **human**: check `/sre incident status-update` in an incident channel and in a non-incident channel on the #1734 deploy; TASK-24.5 (doc-11 row 8a) waits for that check. Rollback: revert the squash commit.
5. **agent** (next session, doc-11 row 10a): plan TASK-157 on its own branch from an up-to-date main; stop for approval.
6. **agent** (after TASK-27.5 and TASK-157 merge): `gh stack checkout stack-k/task-145.5.6-status-update-store`, `gh stack add stack-k/task-145.5.7-legacy-upgrade-job` (human), then re-plan TASK-145.5.7 with a size-gate check.
7. **human**: run the TASK-152 post-apply simulation and paste the output:
   ```
   aws iam simulate-principal-policy --policy-source-arn <sre-bot-ecs-role ARN> --action-names dynamodb:Query --resource-arns <audit trail table ARN>/index/correlation_id-index <incidents table ARN>/index/by_channel <webhooks table ARN>/index/x
   ```
   **agent**: record it in the TASK-152 notes and check AC 2 (expect allowed, allowed, then implicitDeny).
8. **human**: confirm the #1597 tf_apply log shows the two GSI creations and `aws dynamodb describe-table --table-name incidents` shows both indexes ACTIVE; paste for the TASK-145.5.1 notes. **agent**: record the evidence (skip if its notes already carry it).

## Open decisions

- Recorded at task level for their planning: TASK-145.7 chooses dual-write with `extra="ignore"` on the legacy model or shipping with TASK-145.8, and the source_alert shape; TASK-145.8 decides whether a security flag flip triggers actions and how a partial update treats an item without record_version; TASK-154 redesigns the status lifecycle and close.
- No task owns aligning the status-update store's guard-lost result (a STATUS_UPDATE_CONFLICT error) with IncidentStore.update_field's non-error guard-lost result (TASK-145.8); raise it when TASK-145.8 is planned.

## Planning queue

- TASK-157 (single PR, doc-11 row 10a): created 2026-10-20, next to plan (next action 5).
- TASK-145.5.7 (layer 11): re-plan after TASK-27.5 and TASK-157 merge, with a size-gate check (its AC6 to AC8 were added 2026-10-20).
- TASK-145.6 (layer 12): 2026-10-09 plan stale; re-plan at pickup.
