---
id: TASK-145.5.8
title: >-
  Legacy incident item bridge: one pure upgrade function from legacy items to
  the end-state shape, applied by IncidentStore to items without record_version
status: To Do
assignee: []
created_date: '2026-10-15 18:17'
updated_date: '2026-10-15 18:25'
labels:
  - incident
  - features
  - records
dependencies:
  - TASK-145.5.4
references:
  - decisions/incident-management.md
  - decisions/cloud-portability.md
  - 'https://github.com/cds-snc/sre-bot/issues/1719'
parent_task_id: TASK-145.5
priority: medium
type: task
ordinal: 396000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 6 of Stack K (handoff doc-13). Split out of TASK-145.5.4 (human, 2026-10-15): TASK-145.5.4 reads end-state items only and returns INCIDENT_RECORD_UNREADABLE for an item without record_version; this layer lets the store read legacy items. It follows the legacy data upgrade rule set in decisions/incident-management.md (Migration, rules 2, 4 and 7): one pure upgrade function shared by the read bridge and the backfill, applied only to items without record_version, never guessing.

THIS SLICE
- features/incident/core/adapters/legacy_items.py: one pure function taking a legacy item dict and the tenants mapping (the configured tenant per WorkplaceSystem, passed in; no settings import) and returning an end-state item dict, which the end-state parser (core/adapters/incident_items.py, TASK-145.5.4) then reads unchanged. The end-state parser gains no legacy branch.
- Mapping:
  - name to title; user_id to declared_by; created_at (epoch seconds or ISO-8601) to declared_at.
  - teams[0] to product; "Unknown" or blank is not recorded.
  - severity: sev-0 to sev-4, ignoring case and spaces, to 0 to 4; none or missing is unset; any other value is unset and logged with the incident id.
  - status: the five IncidentStatus values matched ignoring case and surrounding spaces (production holds 30 `closed` and 1 `reviewed` in lowercase); any other value is unreadable.
  - A missing security_incident is false (it was only stored from 2026-10-07).
  - Times: "Unknown" or blank are not recorded.
  - incident_commander and operations_lead become roles when present.
  - channel_id becomes the Slack conversation reference with the configured Slack tenant.
  - report_url becomes the Google report reference, the document id taken from /document/d/<id>.
  - meet_url becomes the Google video call reference with the meet code as vendor id; "TBC" or "" is no reference.
  - retrospective_url is skipped.
- Stored times: core/store.py gains the stored-time formatter (fixed-width ISO-8601 UTC, isoformat(timespec="microseconds"), +00:00, the 2026-10-14 key-format decision), used here for declared_at and the optional times and reused by TASK-145.5.7, TASK-145.7 and TASK-145.8.
- Pure and never raising: an unmatched required value (status, declared_by, declared_at) is a classified unreadable result naming the incident id and field, which the store returns as INCIDENT_RECORD_UNREADABLE.
- RecordIncidentStore gains the tenants constructor argument (TASK-145.5.4 takes none, because end-state maps carry their own tenant) and a one-line hook that runs items without record_version through the function before parsing. TASK-145.5.5 passes the tenants from the configured-systems read where it builds the store.
- Tests over every legacy item shape, including the production lowercase statuses, epoch and ISO created_at, "Unknown" and blank values, TBC meet URLs, malformed report URLs and missing optional attributes.

LIFECYCLE
- Reused unchanged by the TASK-145.5.7 upgrade job, so the legacy mapping exists once.
- Deleted by TASK-145.13 once a production run of that job reports nothing pending.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 legacy_items.py maps name, user_id, created_at (epoch or ISO), teams[0], severity (sev-0 to sev-4 ignoring case and spaces; none or missing unset; others unset and logged), status (the five values ignoring case and surrounding spaces), a missing security_incident (false), "Unknown" or blank times and products (not recorded), incident_commander and operations_lead (roles), channel_id, report_url (document id from /document/d/<id>) and meet_url (meet code; "TBC" or "" no reference) to the end-state shape, and skips retrospective_url; times are written with the stored-time formatter this layer adds to core/store.py (fixed-width ISO-8601 UTC, +00:00), tested for width and offset
- [ ] #2 The tenants mapping is passed in by the caller; legacy_items.py imports no settings and no vendor settings slice
- [ ] #3 The function is pure and never raises: an unmatched required value (status, declared_by, declared_at) is a classified unreadable result naming the incident id and field
- [ ] #4 RecordIncidentStore takes the tenants mapping and reads items without record_version through the function (a one-line hook); items with record_version bypass it; the end-state parser has no legacy branch; tests cover every legacy item shape against InMemoryRecordStore
- [ ] #5 ruff, lint-imports, mypy (no errors in touched files) and pytest tests --ignore=tests/smoke pass, with commands and output recorded in notes
<!-- AC:END -->
