---
id: doc-13
title: Stack K handoff
type: guide
created_date: 2026-10-14 22:27
updated_date: '2026-11-04T17:27:00Z'
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
| 0 | Planning edits (tasks and docs) | `stack-k/plan` | #1594 | merged | 2026-10-15. |
| 1 | TASK-152 IAM `/index/*` grants | `stack-k/task-152-iam-index-grants` | #1595 | merged | Done; simulation recorded. |
| 2 | TASK-145.5.1 incidents GSIs, timeline table | `stack-k/task-145.5.1-incidents-gsis` | #1597 | merged | Done. |
| 3 | TASK-145.5.2 ServiceScopeOpener | `stack-k/task-145.5.2-service-scope-opener` | #1598 | merged | Done. |
| 4 | TASK-153 + TASK-145.5.3 record, references, core settings, tenant ids | `stack-k/task-145.5.3-incident-record` | #1599 | merged | Done. |
| P2 | Planning edits of 2026-10-15 | `stack-k/task-145.5.4-incident-store` | #1721 | merged | Planning layer despite its name. |
| 5 | TASK-145.5.4 IncidentStore end-state reads | `stack-k/task-145.5.4-end-state-reads` | #1722 | merged | Done. |
| 6 | TASK-145.5.8 legacy item bridge | `stack-k/task-145.5.8-legacy-item-bridge` | #1723 | merged | Done. |
| 7 | TASK-145.5.9 configured-systems read | `stack-k/task-145.5.5-cutover` | #1728 | merged | Done. |
| 8 | TASK-145.5.10 IncidentStore builder | `stack-k/task-145.5.10-incident-store-builder` | #1730 | merged | 2026-10-20 17:18 UTC. |
| 9 | TASK-145.5.5 cutover | `stack-k/task-145.5.5-incident-cutover` | #1734 | merged | 2026-10-20 18:52 UTC, deployed and checked. Task Done. |
| 10 | TASK-145.5.6 StatusUpdateStore onto RecordStore | `stack-k/task-145.5.6-status-update-store` | #1735 | in review | Base `main`, last push 2026-10-20: built before the TASK-111 chain (its `common/settings.py` hunk still uses BaseSettings aliases), so it needs a rebase onto `main` before layer 11 stacks on it. Task file still says To Do. It merges only once layer 11a is submitted above it. |
| 11a | TASK-145.5.7.1 host TenantVerifier in contracts/workplace (server/ implementation reusing TASK-157's check_slack_tenant) and the lease_ttl keyword on the feature job registry | `stack-k/task-145.5.7.1-host-tenant-verifier-and-lease` | - | plan approved | ~170 LOC, 7 files, host only. Full plan in the subtask. Implement after TASK-157 is deployed with its smoke recorded. |
| 11b | TASK-145.5.7.2 incident core upgrade runner: bounded read, guarded writes, report with unmatched_status/unreadable/dropped, AC8 warning | `stack-k/task-145.5.7.2-upgrade-runner` | - | planned | ~245 LOC, 7 files. Outline; OQ12 decided (integral Decimal as int). 2026-11-04: legacy teams no longer mapped to product (product unset, teams kept); scenario matrix in the parent plan. |
| 11c | TASK-145.5.7.3 incident.response becomes a plugin and registers the job (mode off) | `stack-k/task-145.5.7.3-response-registers-upgrade` | - | planned | ~140 LOC, 8 files. Outline; OQ11 decided (entry module response/plugin.py). |
| 12 | TASK-145.6 core resource interfaces | - | - | planned | 2026-10-09 plan stale; re-plan after layer 11. ProductCatalog is out of scope (2026-11-04, option C: built with the catalogue in TASK-165.1, never over Drive folders). |

TASK-27.5 left the stack (doc-11 R6, human 2026-10-20) and merged as #1736. A planning-only refinement is normally an earlier commit on the layer it refines; a large planning sync goes on its own planning layer (`stack-k/plan-<n>`, labelled P<n>).

## Position

- Checked out: `task-145.5.7-plan` (merged as #1818; identical to `main`). The Stack K planning work is on `main`; uncommitted on this tree are only the coordinated-incidents direction edits of a parallel session (not Stack K) and this doc. Previously uncommitted, now merged: the task files of TASK-145.5.7 and 145.5.7.1 to 145.5.7.3, the notes on TASK-64, 145.7, 145.8, 145.9, 145.12, 145.13 and 147.6, the four amended ADRs (`decisions/workplace-systems.md`, `incident-management.md`, `reliability.md`, `cloud-portability.md`) and this doc.
- Open PRs: #1735 (layer 10), pre-TASK-111 base, needs a rebase onto `main`. TASK-157 (#1817) merged 2026-11-04 13:28 UTC (dc79aa33); its deploy and smoke are not yet recorded.
- `gh stack` is not installed in the devcontainer: `gh extension install github/gh-stack`.
- Never stage: `backlog/docs/doc-6*`, `doc-8*`, `doc-9*`, `doc-11*`, `doc-15*`, `CDS Incident Management Handbook.md`, `Incident Response Runbook.md`, `large-scale-incident-analysis.md`, `access-vs-team-analysis.md`, the untracked `task-165.*`, `task-178`, `task-179` files.
- Production data facts (scans, 2026-10-15): 323 incident items; 30 `closed` and 1 `reviewed` lowercase; security_incident absent on 316; every created_at an epoch string. Production `[slack.tenant]` names team_id only. Production cannot run bin scripts (no ECS Exec, no RunTask), hence the in-app job.
- No background agents.

## Next actions

1. **human**: record TASK-157's deploy: `bin/deploy-checks.zsh post` and the Slack smoke (`/sre help` plus a button or modal; `slack_tenant_mismatch` = 0). **agent**: write them into TASK-157's notes. The smoke also settles the auth.test assumption (D10): no enterprise id arrives inbound with the team_id-only entry.
2. Done 2026-11-04: OQ11 and OQ12 answered.
3. Done 2026-11-04: the planning commit merged on `main` as its own PR (#1818), not on layer 11a (the stack was not rebased, and the cherry-pick onto the 2026-10-20 base conflicted in every file). The local 11a branch `stack-k/task-145.5.7.1-host-tenant-verifier-and-lease` exists, empty, at #1735's old tip `cdb41d28`.
4. **agent** (next session, before 11a): rebase #1735 onto `main`. `git merge-tree` shows 8 conflicts: `app/features/incident/README.md`, `common/settings.py`, `comms/entrypoints/slack.py`, `core/adapters/status_updates.py`, `tests/unit/features/incident/common/test_incident_common_settings_load.py`, `tests/unit/features/incident/core/test_incident_core_status_update_store.py` (deleted by #1735, modified on main), and the TASK-145.5.6 and TASK-152 task files. The agent resolves them onto the TASK-111 settings shape and re-runs 145.5.6's gates; the **human** runs:
   ```
   gh stack checkout stack-k/task-145.5.6-status-update-store
   gh stack rebase
   gh stack submit
   ```
   then re-requests review of #1735. The 11a branch is rebased with it and then holds the #1818 task files from `main`.
5. Once 11a is submitted above it, #1735 may merge (`gh stack sync`, `gh stack submit`). Then 11b (`gh stack add stack-k/task-145.5.7.2-upgrade-runner`) and 11c.
6. The job runs (per environment, dry run then apply) only after TASK-145.8 deploys, before TASK-145.9 merges, and again after TASK-145.12. TASK-145.7 adds the binding step before that first run.

## Open decisions

- None open for layer 11. 2026-11-04 (human): OQ11 approved (entry module `features.incident.response.plugin`, contract (m) protects it; plugins.md Changes line); OQ12 approved (integral Decimal guarded as int, non-integral unreadable, `ExpectedValue` not widened); 145.5.7.1 plan approved.
- Recorded at task level: TASK-145.7 dual-write, source_alert shape and the binding step; TASK-145.8 partial updates of items without record_version (must keep the job's guard meaningful); TASK-154 status lifecycle.

## Planning queue

- TASK-145.5.7.2 and 145.5.7.3: outlines with OQ11 and OQ12 decided; full plans at their pickup.
- TASK-145.6: re-plan after layer 11.
