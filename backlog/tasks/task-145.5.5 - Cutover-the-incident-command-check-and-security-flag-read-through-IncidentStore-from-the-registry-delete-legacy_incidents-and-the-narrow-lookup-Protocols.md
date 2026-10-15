---
id: TASK-145.5.5
title: >-
  Cutover: the incident command check and security flag read through
  IncidentStore from the registry; delete legacy_incidents and the narrow lookup
  Protocols
status: To Do
assignee: []
created_date: '2026-10-14 23:09'
updated_date: '2026-10-15 18:19'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-152
  - TASK-145.5.1
  - TASK-145.5.2
  - TASK-145.5.8
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
Layer 7 of Stack K (handoff doc-13). The behaviour change of TASK-145.5: incident lookups move from a full-table scan to the by_channel index. Standalone merge and deploy, only after TASK-152 and TASK-145.5.1 are applied.

THIS SLICE
- Configured-systems read (decisions/workplace-systems.md rule 3, human 2026-10-15): a small platform read that returns each configured WorkplaceSystem (contracts/workplace/, TASK-145.5.3) with its tenant id. Its Protocol lives in contracts/workplace/ and its provider in app/infrastructure/, built from the vendor slices (Slack: SLACK_TEAM_ID when present; Google: the customer id when the service-account key file is set) and registered as a core service. The incident provider reads it; no feature imports a vendor settings slice.
- core/api.py: a provider that builds the IncidentStore from a resolved RecordStore, the incident core settings and the tenants mapping for the legacy item bridge (TASK-145.5.8), taken from the configured-systems read; the new-incident policy (a system, unset by default) is resolved against the configured systems where the store is built: a set policy resolves to that system's single configured tenant, an unset one to the only configured system; the incident feature is skipped with an event naming the key when the named system is unconfigured, when none is configured, or when the policy is unset and several are (decisions/incident-management.md); find_incident_for_conversation takes the store. IncidentStore.find_by_conversation takes a ConversationReference (system, tenant, conversation id), not a bare id, so find_incident_for_conversation(conversation_id) builds that reference from the configured Slack tenant returned by the configured-systems read. get_incident_lookup, get_incident_security_reader (lru_cache providers, which dependency-injection.md:37 forbids across layers) and the IncidentLookup and IncidentSecurityReader Protocols are deleted (human, 2026-10-14: one Protocol per core resource, as TASK-145.6 does for the report).
- comms/service.py: the lookup and security-reader fallbacks that resolve a service mid-method (service.py:106,178,257,361,498) go; the service takes IncidentStore as a required parameter.
- comms entry points: each handler opens a scope through the ServiceScopeOpener (TASK-145.5.2), resolves RecordStore, builds the IncidentStore and passes it to the service. No get_record_store import and no import-linter ignore entry (contract (k)).
- Comms tests move from their local lookup fakes to the in-memory IncidentStore fake (TASK-145.5.4).
- Security flag (human, 2026-10-15): comms moves from IncidentSecurityFlag to the bool returned by IncidentStore.read_security_flag (security_incident on the record). A missing legacy flag reads as false (the bridge, TASK-145.5.8), so the comms confirmation gate no longer fires for old incidents; the human accepted this.
- core/adapters/legacy_incidents.py is deleted; in the same PR the IncidentSecurityFlag enum (core/domain.py) and its tests are deleted.
- Rollback: one revert restores the scan.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 find_incident_for_conversation and the security flag resolve through IncidentStore, built at the entry point from a RecordStore resolved through the ServiceScopeOpener
- [ ] #2 comms services take IncidentStore as a required parameter and resolve nothing themselves
- [ ] #3 No get_record_store import and no new import-linter ignore entry; lint-imports passes
- [ ] #4 Entry-point tests cover success and the not-an-incident, ambiguous and store-failure error mappings
- [ ] #5 The configured-systems read returns each configured system with its tenant id from the vendor slices; the new-incident policy resolves through it (set, unset with one system) and the feature is skipped with an event naming the key when the named system is unconfigured, none is configured, or the policy is unset with several; no feature module imports a vendor settings slice
- [ ] #6 core/adapters/legacy_incidents.py, IncidentLookup, IncidentSecurityReader, the IncidentSecurityFlag enum, their providers and tests are deleted; rg finds no reference in app/
- [ ] #7 comms reads the security flag as the bool from IncidentStore.read_security_flag; a missing legacy flag reads as false and the confirmation gate does not fire (tested)
- [ ] #8 find_incident_for_conversation builds a ConversationReference from the configured Slack tenant and passes it to IncidentStore.find_by_conversation
- [ ] #9 The IncidentStore is built with the tenants mapping from the configured-systems read, so legacy items without record_version read through the bridge (TASK-145.5.8); a legacy item resolves end to end in the entry-point tests
<!-- AC:END -->
