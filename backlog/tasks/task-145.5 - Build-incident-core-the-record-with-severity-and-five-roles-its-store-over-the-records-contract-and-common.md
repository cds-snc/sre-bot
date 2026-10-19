---
id: TASK-145.5
title: >-
  Build incident/core: the record with severity and five roles, its store over
  the records contract, and common/
status: To Do
assignee: []
created_date: '2026-10-09 16:43'
updated_date: '2026-10-19 15:27'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-108
  - TASK-145.1
  - TASK-109
references:
  - 'https://github.com/cds-snc/sre-bot/issues/1692'
parent_task_id: TASK-145
priority: medium
type: task
ordinal: 355000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer B1 of TASK-145, delivered as Stack K (handoff doc-13). Coordinator: the work is in subtasks TASK-145.5.1 to TASK-145.5.10, with TASK-152 and TASK-27.5 as layers of the same stack. It builds the incident record and its store in features/incident/core over the records contract, moves the incident lookup and security flag onto it, and moves the status-update store onto the records contract. The legacy module keeps working on the same table.

Split on 2026-10-14 for the single-PR gate (about 950 production lines across about 20 files, spanning app, server/contracts and Terraform, mixing additive work with a cutover).

Out of this task:
- Write operations: create (TASK-145.7, sets open_bucket and opened_at), update (TASK-145.8, removes them on Closed), timeline append (TASK-145.9).
- conversation_is_writable, the second part of the command check (incident-management.md:44), comes with IncidentConversation in TASK-145.6.
- List for a window needs the full-table read and is served with TASK-145.12, not by this store.
- The settings slices for response, comms and postmortem arrive with the layers that consume them.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The incident record, its typed references with system and tenant, and the vocabulary exist in core/domain.py and common/ (TASK-145.5.3)
- [ ] #2 find_incident_for_conversation and the security flag resolve through IncidentStore over RecordStore, obtained through the ServiceScopeOpener; legacy_incidents.py and the narrow lookup Protocols are gone (TASK-145.5.4, TASK-145.5.5)
- [ ] #3 No incident adapter in core/ imports an AWS client (TASK-145.5.6)
- [ ] #4 TASK-152, TASK-145.5.1 to TASK-145.5.6 and TASK-145.5.8 to TASK-145.5.10 are done (TASK-145.5.7 and TASK-27.5 may close after this task; they gate TASK-145.9)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Coordinator plan. Each layer is planned in its own session, after the layer below is implemented. Decisions (human, 2026-10-14 and 2026-10-15) are recorded in the subtask descriptions.

Stack K layers, bottom first:
1. TASK-152: IAM /index/* grants for the audit trail, retry records and incidents tables. Terraform. Standalone merge, tf_apply.
2. TASK-145.5.1: the incidents by_channel and open GSIs (projection ALL), the timeline table, and the devcontainer script, run locally. Terraform. Standalone merge, tf_apply before layer 9.
3. TASK-145.5.2: ServiceScopeOpener for the Slack and background-job registrars, and the dependency-injection.md update (Bolt middleware alternative recorded).
4. TASK-153 then TASK-145.5.3, one layer: TASK-153 amends the ADRs for vendor enablement (a configured tenant entry enables a vendor client; the new-incident policy names a system) in an earlier commit, then TASK-145.5.3: vocabulary, record, references, incident core settings, platform tenant ids (SLACK_TEAM_ID required when Slack is enabled; the Google customer id is not the my_customer alias when Google is configured).
5. TASK-145.5.4: IncidentStore over RecordStore (end-state reads only; an item without record_version is INCIDENT_RECORD_UNREADABLE), its in-memory fake, the key-format decision, and index reads returning full items in the records contract.
6. TASK-145.5.8: the legacy item bridge: legacy_items.py, one pure upgrade function, applied by the store to items without record_version (split out of TASK-145.5.4, human 2026-10-15).
7. TASK-145.5.9: the configured-systems read (contracts/workplace Protocol, infrastructure provider from the vendor slices, core service). No behaviour change. Split out of TASK-145.5.5 (human, 2026-10-19).
8. TASK-145.5.10: the IncidentStore builder from a resolved RecordStore, the incident core settings and the configured tenants; it does not read the new-incident policy, which only the declare path resolves (TASK-145.7). Unused until layer 9.
9. TASK-145.5.5: cutover of the lookup and security flag; the entry point builds the ConversationReference; narrow Protocols and legacy_incidents deleted. Standalone merge and deploy, after layers 5 to 8 have merged.
10. TASK-145.5.6: StatusUpdateStore onto RecordStore through the registry.
11. TASK-27.5: bounded full-table read (pulled forward; first consumer TASK-145.5.7).
12. TASK-145.5.7: the incident legacy upgrade job (legacy_items.py from TASK-145.5.8 over every item without record_version: end-state attributes, reference maps, security_incident, the open index, record_version), an in-app leased job, off by default. Run after TASK-145.8 deploys, before TASK-145.9 merges, and again after TASK-145.12. Re-planned at pickup.
13. TASK-145.6: core resource interfaces, re-planned after layer 9.

Review cadence: review is requested once two layers are stacked, and at least two PRs stay open before any closes.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-13 re-plan before pickup: IncidentStore is built over RecordStore (the records contract: TASK-27.4, TASK-27.1, TASK-108), not an interim adapter over get_aws_client; the plan's step 4 and AC #5 are rewritten at re-plan. The incident record also carries the postmortem facts that TASK-147.2 builds on.

2026-10-14 wiring (rewritten after TASK-109 merged): IncidentStore gets its RecordStore through the svcs registry (app/server/services.py, TASK-109) under import-linter contract (k); it does not import get_record_store and adds no import-linter ignore entry. TASK-109 is a dependency.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-13 18:00
---
2026-10-13 (TASK-27.1 implemented): the plan still builds DynamoDbIncidentStore over get_aws_client with a channel_id scan (steps 3, 4, 6 and the Stubber tests); the re-plan already recorded in notes should target RecordStore with a module-level RecordTable for incidents, RecordQuery reads, InMemoryRecordStore-backed fake tests, and decide find-by-conversation (GSI declared in RecordTable.indexes vs TASK-27.2 bounded list).
---

created: 2026-10-13 18:59
---
2026-10-13: supersedes the earlier comment's 'module-level RecordTable': after the TASK-27.1 review, table names come from the owning package's settings with the provisioned table as default (see access request/sync stores and infrastructure/audit/settings.py). This also applies to the status-updates and legacy incidents adapters' hardcoded table names when they move onto RecordStore.
---

created: 2026-10-13 19:59
---
2026-10-13 records/incidents layout decision: incidents table keeps partition key id and gains two GSIs declared as RecordTable.indexes: by_channel (partition channel_id) for find_by_conversation, and a sparse open index (partition open_bucket, constant OPEN; sort opened_at) set only while an incident is open and removed on close. Never a GSI on status. find_by_conversation queries by_channel with RecordQuery(index=...) and handles zero, one or several results (index reads may be eventually consistent and are not unique); no bounded-list fallback. This task owns Terraform for the GSIs and for a new timeline table keyed (incident_id, 'ts#entry_id'), declared as its RecordTable with the store (the description already puts append of a timeline entry in IncidentStore); TASK-145.9 wires the writes. It also owns a one-shot backfill of open_bucket and opened_at for existing open incidents (idempotent, dry run first) (superseded 2026-10-15: TASK-145.5.7 is the incident legacy upgrade job). Index queries need no Protocol change (TASK-27.1). A plan refresh is needed to fold this in; AC5 (write operations absent) still holds for update, which arrives with TASK-27.2 and TASK-145.8.
---
<!-- COMMENTS:END -->
