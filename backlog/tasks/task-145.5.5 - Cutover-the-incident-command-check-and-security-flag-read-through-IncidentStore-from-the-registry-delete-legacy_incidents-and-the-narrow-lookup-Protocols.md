---
id: TASK-145.5.5
title: >-
  Cutover: the incident command check and security flag read through
  IncidentStore from the registry; delete legacy_incidents and the narrow lookup
  Protocols
status: To Do
assignee: []
created_date: '2026-10-14 23:09'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-152
  - TASK-145.5.1
  - TASK-145.5.2
  - TASK-145.5.4
references:
  - decisions/dependency-injection.md
  - decisions/incident-management.md
parent_task_id: TASK-145.5
priority: medium
type: task
ordinal: 391000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 6 of Stack K (handoff doc-13). The behaviour change of TASK-145.5: incident lookups move from a full-table scan to the by_channel index. Standalone merge and deploy, only after TASK-152 and TASK-145.5.1 are applied.

THIS SLICE
- core/api.py: a provider that builds the IncidentStore from a resolved RecordStore and the incident core settings; find_incident_for_conversation takes the store. get_incident_lookup, get_incident_security_reader (lru_cache providers, which dependency-injection.md:37 forbids across layers) and the IncidentLookup and IncidentSecurityReader Protocols are deleted (human, 2026-10-14: one Protocol per core resource, as TASK-145.6 does for the report).
- comms/service.py: the lookup and security-reader fallbacks that resolve a service mid-method (service.py:106,178,257,361,498) go; the service takes IncidentStore as a required parameter.
- comms entry points: each handler opens a scope through the ServiceScopeOpener (TASK-145.5.2), resolves RecordStore, builds the IncidentStore and passes it to the service. No get_record_store import and no import-linter ignore entry (contract (k)).
- Comms tests move from their local lookup fakes to the in-memory IncidentStore fake (TASK-145.5.4).
- core/adapters/legacy_incidents.py is deleted.
- Rollback: one revert restores the scan.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 find_incident_for_conversation and the security flag resolve through IncidentStore, built at the entry point from a RecordStore resolved through the ServiceScopeOpener
- [ ] #2 comms services take IncidentStore as a required parameter and resolve nothing themselves
- [ ] #3 core/adapters/legacy_incidents.py, IncidentLookup, IncidentSecurityReader and their providers are deleted; rg finds no reference in app/
- [ ] #4 No get_record_store import and no new import-linter ignore entry; lint-imports passes
- [ ] #5 Entry-point tests cover success and the not-an-incident, ambiguous and store-failure error mappings
<!-- AC:END -->
