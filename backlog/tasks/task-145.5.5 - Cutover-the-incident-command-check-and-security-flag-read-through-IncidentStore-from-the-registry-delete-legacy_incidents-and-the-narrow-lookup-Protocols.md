---
id: TASK-145.5.5
title: >-
  Cutover: the incident command check and security flag read through
  IncidentStore from the registry; delete legacy_incidents and the narrow lookup
  Protocols
status: To Do
assignee: []
created_date: '2026-10-14 23:09'
updated_date: '2026-10-19 15:26'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.5.10
  - TASK-145.5.9
  - TASK-145.5.8
  - TASK-145.5.2
  - TASK-145.5.1
  - TASK-152
references:
  - decisions/dependency-injection.md
  - decisions/incident-management.md
  - 'https://github.com/cds-snc/sre-bot/issues/1694'
parent_task_id: TASK-145.5
priority: medium
type: task
ordinal: 391000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 9 of Stack K (handoff doc-13). The behaviour change of TASK-145.5: incident lookups move from a full-table scan to the by_channel index. Standalone merge and deploy, only after layers 5 and 6 (TASK-145.5.4, TASK-145.5.8) and layers 7 and 8 (TASK-145.5.9 configured-systems read, TASK-145.5.10 store builder) have merged, and TASK-152 and TASK-145.5.1 are applied. Split 2026-10-19 (human): the configured-systems read and the store builder moved to TASK-145.5.9 and TASK-145.5.10.

THIS SLICE
- Comms entry points: each handler that reads an incident opens a scope through the ServiceScopeOpener (TASK-145.5.2), resolves RecordStore, builds the IncidentStore with the TASK-145.5.10 builder, and builds the ConversationReference (Slack, the configured Slack tenant from the configured-systems read, the channel id). It passes the store and the reference to the service (human, 2026-10-19: the entry point builds the reference, so when writers take the tenant from the event payload, TASK-145.7 on, and when Teams arrives, only entry points change). No get_record_store import and no import-linter ignore entry (contract (k)).
- Startup skip (human, 2026-10-19): the comms entry points register only when Slack is in the configured-systems read; otherwise one startup event names SLACK_TEAM_ID. No per-invocation skip.
- core/api.py: find_incident_for_conversation takes the IncidentStore and the ConversationReference and calls IncidentStore.find_by_conversation. get_incident_lookup, get_incident_security_reader (lru_cache providers, which dependency-injection.md:37 forbids across layers) and the IncidentLookup and IncidentSecurityReader Protocols are deleted (human, 2026-10-14: one Protocol per core resource, as TASK-145.6 does for the report).
- comms/service.py and form.py: the lookup and security-reader fallbacks that resolve a service mid-function (service.py:106,178,257,361,498) go; the functions take the IncidentStore and the ConversationReference as required parameters.
- Comms tests move from their local lookup fakes to the in-memory IncidentStore fake (TASK-145.5.4).
- Security flag (human, 2026-10-15): comms moves from IncidentSecurityFlag to the bool returned by IncidentStore.read_security_flag (security_incident on the record). A missing legacy flag reads as false (the bridge, TASK-145.5.8), so the comms confirmation gate no longer fires for old incidents; the human accepted this.
- core/adapters/legacy_incidents.py is deleted; in the same PR the IncidentSecurityFlag enum (core/domain.py) and its tests are deleted.
- The new-incident policy is not read here (decisions/incident-management.md, amended 2026-10-19: resolved only by the declare path, TASK-145.7).
- Rollback: one revert restores the scan.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 find_incident_for_conversation and the security flag resolve through IncidentStore, built at the entry point with the TASK-145.5.10 builder from a RecordStore resolved through the ServiceScopeOpener
- [ ] #2 comms services take the IncidentStore and the ConversationReference as required parameters and resolve nothing themselves
- [ ] #3 No get_record_store import and no new import-linter ignore entry; lint-imports passes
- [ ] #4 Entry-point tests cover success and the not-an-incident, ambiguous and store-failure error mappings
- [ ] #5 The entry point builds the ConversationReference from the configured Slack tenant (configured-systems read) and the channel id; find_incident_for_conversation passes it to IncidentStore.find_by_conversation
- [ ] #6 core/adapters/legacy_incidents.py, IncidentLookup, IncidentSecurityReader, the IncidentSecurityFlag enum, their providers and tests are deleted; rg finds no reference in app/
- [ ] #7 comms reads the security flag as the bool from IncidentStore.read_security_flag; a missing legacy flag reads as false and the confirmation gate does not fire (tested)
- [ ] #8 A legacy item without record_version resolves end to end in the entry-point tests
- [ ] #9 The comms entry points register only when Slack is in the configured-systems read; otherwise one startup event names SLACK_TEAM_ID (tested)
- [ ] #10 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-19 15:26
---
Split 2026-10-19 (human) after the size gate tripped (~12 prod files, ~375-500 LOC, platform and feature): TASK-145.5.9 configured-systems read (layer 7), TASK-145.5.10 store builder (layer 8), this task the cutover (layer 9). Decisions: the new-incident policy is resolved only by the declare path (ADR amended; old AC5 policy part dropped); the entry point builds the ConversationReference (old AC8 reworded); skip events fire once at startup. Old AC9 (store built with the tenants mapping) moved to TASK-145.5.10.
---
<!-- COMMENTS:END -->
