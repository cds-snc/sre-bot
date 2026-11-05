---
id: doc-13
title: Stack K handoff
type: guide
created_date: 2026-10-14 22:27
updated_date: '2026-11-05T20:26:00Z'
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
| 11b | TASK-145.5.7.2 incident core upgrade runner | `stack-k/task-145.5.7.2-upgrade-runner` | #1821 | merged | 2026-11-05 (33511c15), deployed (new task started; `/sre help` and the alert buttons work; the deploy script was not run, none required). |
| 11c | TASK-145.5.7.3 incident.response becomes a plugin and registers the job (mode off) | `stack-k/task-145.5.7.3-response-registers-upgrade` | #1822 | merged | 2026-11-05. Task still In Progress: the human sets Done (edit rides in 12c's commit).
| 12a | TASK-145.6.1 verbatim move of documents/, drive/ and scribe's section writer into core/adapters/google_docs.py; every importer repointed | `stack-k/task-145.6.1-google-docs-move` | #1825 | in review | Base `main` since #1822 merged (GitHub retarget); the local branches were not yet synced with main at 2026-11-05 (12c session). ACs #1-#5 checked, In Progress. The four document section types moved to core/domain.py (pulled forward from 12b). |
| 12b | TASK-145.6.2 IncidentReport Protocol, Google Docs adapter and fake; Drive on the gateway (infrastructure.drive ignores deleted); scribe drafts from the record's report; [incident_core] ids required on register | `stack-k/task-145.6.2-incident-report` | #1826 | in review | Committed 8704abdd, submitted above #1825. ACs #1-#10 checked, In Progress. Production SSM INCIDENT_CORE folder and template ids confirmed non-empty (human, 2026-11-05). |
| 12c | TASK-145.6.3 IncidentConversation with is_writable; conversation_is_writable; the transcript reader takes a ConversationReference | `stack-k/task-145.6.3-incident-conversation` | #1827 | plan approved | 2026-11-05: plan commit 4d61cb56 submitted as #1827 (stack synced onto main). Plan revised after the program-scope assessment and approved (human, 2026-11-05): ~9 production files, ~410 LOC. Next: TDD. |

TASK-27.5 left the stack (doc-11 R6, human 2026-10-20) and merged as #1736. A planning-only refinement is normally an earlier commit on the layer it refines; a large planning sync goes on its own planning layer (`stack-k/plan-<n>`, labelled P<n>).

## Position

- Branch `stack-k/task-145.6.3-incident-conversation` (12c) checked out, on top of 12b (9c3b4389) per `gh stack view`; no rebase in progress; synced onto main (contains origin/main); one commit, the plan (4d61cb56), submitted as #1827.
- Uncommitted on it: the revised and approved TASK-145.6.3 plan, ACs and comment; comments on TASK-145.7 and 145.9 (145.9 AC #8); decisions/incident-management.md, outbound-clients.md and transport-slack.md; this doc. Commit them as a planning commit on 12c (commands in the session hand-off). The untracked planning docs were restored from the stash by the human.
- Open stack PRs: #1825 (12a, base `main`), #1826 (12b), #1827 (12c, plan only). #1822 merged; TASK-145.5.7.3 Done.
- Never stage: `backlog/docs/doc-6*`, `doc-8*`, `doc-9*`, `doc-11*`, `doc-15*`, `CDS Incident Management Handbook.md`, `Incident Response Runbook.md`, `large-scale-incident-analysis.md`, `access-vs-team-analysis.md`, `coordinated-incidents-executive-briefing.md`.
- Production data facts (scans, 2026-10-15): 323 incident items; 30 `closed` and 1 `reviewed` lowercase; security_incident absent on 316; every created_at an epoch string. 2026-11-05: 2 of 330 items have no report_url, both open test incidents (D1 accepted). Production cannot run bin scripts (no ECS Exec, no RunTask), hence the in-app job.
- No background agents.

## Next actions

1. **human**: commit the approved planning edits on 12c and `gh stack submit` (commands in the session hand-off).
2. **agent**: implement TASK-145.6.3 (12c) with TDD per the approved plan (steps 1-10), then the gates (ruff and targeted tests during; full mypy then full pytest once at the end), check ACs one by one, keep In Progress.
3. **human**: #1825 (12a) may merge now that two layers are above it; then `gh stack sync`. 12b merges once 12c is submitted with its implementation.
4. The job runs (per environment, dry run then apply) only after TASK-145.8 deploys, before TASK-145.9 merges, and again after TASK-145.12. TASK-145.7 adds the binding step before that first run.

## Open decisions

- TASK-145.6.3 (12c) plan, revised 2026-11-05 after a program-scope assessment (ADRs, doc-11, doc-15), approved (human, 2026-11-05): OQ1 no create here, 145.7 adds it with the first working-surface binding (E1); OQ2 not-writable codes join the Slack classification table, unknown codes propagate (outbound-clients.md); OQ3 invite takes chat account ids (people-and-accounts.md); OQ4 conversation_is_writable(conversations, conversation | None), callers pass incident.conversation now, the primary binding after E1; OQ5 the reader returns OperationResult (operation-result.md), callers keep today's replies; OQ6 summarize keeps behaviour, 145.9 gains the command-check AC; G1 rate-limit-only Slack write handle (non-idempotent write rule); G2 IncidentConversation async (transport-slack.md), reader sync tolerated. ~9 production files, ~410 LOC.
- None open for the stack. 2026-11-05 (human): TASK-145.6 plan and split approved (OQ1-OQ5); TASK-145.6.2 C1-C4 and D1 approved; TASK-184 plan approved (OQ1-OQ3), merged as #1824 and deployed 2026-11-05.
- 2026-11-05 (12b, agent, within the approved plan): the section reader and draft writer stay module functions in core/adapters/google_docs.py behind GoogleDocsIncidentReport (the writer's tests stay as pinned); a new report's tenant is read at call time from the Google Workspace entry, so get_incident_report() takes no argument; scribe's two bookmark-lookup log events go with the lookup (C3). Recorded in TASK-145.6.2 notes and decisions/incident-management.md.
- 2026-11-05 (12a, agent, within the approved plans): the four document section types moved to core in 12a instead of 12b, because core cannot import scribe. Recorded on TASK-145.6.1 notes, TASK-145.6.2 and in decisions/incident-management.md.
- 2026-11-05 (human, 12a review): the section writer's draft rules leave core/adapters/google_docs.py for postmortem in TASK-145.11 (step 3a, AC #6). 12a stays a pure move; 12b keeps its write_draft_copy signature.
- Recorded at task level: TASK-145.7 dual-write, source_alert shape and the binding step; TASK-145.8 partial updates of items without record_version; TASK-154 status lifecycle.

## Planning queue

- None: 12c's plan is approved and 12c is Stack K's last planned layer. TASK-145.7 onward is Stack L (doc-11 row 18, re-planned with the E1 bindings after A1, row 17a).
