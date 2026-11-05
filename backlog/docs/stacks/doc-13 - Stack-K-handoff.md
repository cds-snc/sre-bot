---
id: doc-13
title: Stack K handoff
type: guide
created_date: 2026-10-14 22:27
updated_date: '2026-11-05T01:00:00Z'
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
| 10 | TASK-145.5.6 StatusUpdateStore onto RecordStore | `stack-k/task-145.5.6-status-update-store` | #1735 | merged | 2026-11-04 20:35 UTC. |
| 11a | TASK-145.5.7.1 host TenantVerifier and lease_ttl | `stack-k/task-145.5.7.1-host-tenant-verifier-and-lease` | #1820 | merged | 5deb8406. |
| 11b | TASK-145.5.7.2 incident core upgrade runner | `stack-k/task-145.5.7.2-upgrade-runner` | #1821 | in review | Base `main`. Merges once re-reviewed (11c sits above it). |
| 11c | TASK-145.5.7.3 incident.response becomes a plugin and registers the job (mode off) | `stack-k/task-145.5.7.3-response-registers-upgrade` | #1822 | in review | Top of the stack: stays open until 12a is submitted above it. |
| 12a | TASK-145.6.1 verbatim move of documents/, drive/ and scribe's section writer into core/adapters/google_docs.py; every importer repointed | `stack-k/task-145.6.1-google-docs-move` | - | plan approved | 2026-11-05; ~16 files, mechanical only; full plan in the task. |
| 12b | TASK-145.6.2 IncidentReport Protocol and adapter on the gateway factories; infrastructure.drive ignores deleted; [incident_core] ids required on register | `stack-k/task-145.6.2-incident-report` | - | planned | Full plan proposed 2026-11-05, ~295 LOC, 12 files; corrections C1-C4 await approval; AC #5 waits on the C4 host task. |
| 12c | TASK-145.6.3 IncidentConversation with is_writable; reader takes a ConversationReference; IncidentReportLinkLookup deleted | `stack-k/task-145.6.3-incident-conversation` | - | planned | ~9 files, ~380 LOC. |

TASK-27.5 left the stack (doc-11 R6, human 2026-10-20) and merged as #1736. A planning-only refinement is normally an earlier commit on the layer it refines; a large planning sync goes on its own planning layer (`stack-k/plan-<n>`, labelled P<n>).

## Position

- Checked out: `task-169-google-credential-model` (#1823, TASK-169 planning PR from `main`, open), not a stack branch. This session made no code change; it edited TASK-145.6, created 145.6.1-145.6.3, commented TASK-120, 165, 165.1 (retitled), amended decisions/incident-management.md and organisation-content.md, this doc and the untracked doc-11 and doc-15.
- Open stack PRs: #1821 (11b, base `main`), #1822 (11c, top).
- Never stage: `backlog/docs/doc-6*`, `doc-8*`, `doc-9*`, `doc-11*`, `doc-15*`, `CDS Incident Management Handbook.md`, `Incident Response Runbook.md`, `large-scale-incident-analysis.md`, `access-vs-team-analysis.md`, `coordinated-incidents-executive-briefing.md`.
- Production data facts (scans, 2026-10-15): 323 incident items; 30 `closed` and 1 `reviewed` lowercase; security_incident absent on 316; every created_at an epoch string. Production cannot run bin scripts (no ECS Exec, no RunTask), hence the in-app job.
- No background agents.

## Next actions

1. **human** (2026-11-05): the TASK-145.6 planning edits are a second commit on #1823 (`task-169-google-credential-model`), because they build on TASK-169's task and ADR edits; further planning-only edits may follow there until it merges.
2. **human**, after #1823 merges: `gh stack checkout stack-k/task-145.5.7.3-response-registers-upgrade`, `gh stack rebase`, `gh stack submit`, `gh stack add stack-k/task-145.6.1-google-docs-move`.
3. **agent**: implement TASK-145.6.1 with TDD; submit 12a so #1822 can merge.
4. **human**: re-review and merge #1821; then `gh stack sync`, `gh stack submit`. #1822 merges only after 12a is submitted above it.
5. The job runs (per environment, dry run then apply) only after TASK-145.8 deploys, before TASK-145.9 merges, and again after TASK-145.12. TASK-145.7 adds the binding step before that first run.

## Open decisions

- None open. 2026-11-05 (human): TASK-145.6 plan and split approved, OQ1-OQ5 as recommended; ProductCatalog's default source is the bot's own product list (TASK-165.1).
- TASK-145.6.2 corrections C1-C4 and the D1 fallback (in its plan), proposed 2026-11-05.
- Recorded at task level: TASK-145.7 dual-write, source_alert shape and the binding step; TASK-145.8 partial updates of items without record_version; TASK-154 status lifecycle.

## Planning queue

- TASK-145.6.1 (12a): plan approved.
- TASK-145.6.2 (12b): full plan proposed, awaiting approval.
- TASK-145.6.3 (12c): outline (narrowed by C3); full plan at pickup.
