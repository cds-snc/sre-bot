---
id: TASK-145.10.5
title: 'M4a Dark: core incident-role check for changes to the postmortem meeting'
status: To Do
assignee: []
created_date: '2026-11-20T22:05:00Z'
updated_date: '2026-11-26T19:33:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-145.10.4
parent_task_id: TASK-145.10
priority: medium
ordinal: 536000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack M layer M4a. Dark. A check in core/api.py: changes to the postmortem meeting (reschedule, cancel, follow-up) are allowed to the incident commander, operations lead or postmortem owner on the record, falling back to declared_by when no role is set; a refusal is answered privately with an explicit error code. The first booking stays open to any channel member. ADR: incident-management.md rule (authorization.md: object-level checks stay in the feature; feature-packages.md rule 4). Branch stack-m/145.10.5-meeting-role-check.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 core/api.py exposes the role check with an explicit refusal error code; roles read from the record with declared_by fallback
- [ ] #2 Tests cover each allowed role, the fallback, a non-role member refused, and an incident with no roles
- [ ] #3 incident-management.md rule amended; ruff, mypy, the four make checks and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Grounded outline (plan in full at pickup). Depends on M3.
Grounding: Incident roles on the record (core/domain.py: incident_commander, operations_lead, postmortem_owner; declared_by); core/api.py command checks (find_incident_for_conversation :655, conversation_is_writable :666) are the pattern; error codes registry in contracts/operations/codes.py (add an explicit code, e.g. forbidden-for-role, via the registry); authorization.md: object-level checks stay in the feature; feature-packages.md rule 4 (check every subdomain applies lives in core). Steps: role-check function and refusal code in core/api.py; tests for each role, fallback to declared_by when no role set, non-role member refused, no roles; ADR rule in incident-management.md. Dark: nothing calls it until M4b. Size about 80 LOC. Blast radius: none; revert trivial.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-26T19:33:00Z

---

2026-11-26 (TASK-145.7.10 OQ4, open product question, no ADR covers it): declare sets incident_commander to the declarer unconditionally (TASK-145.7.10 comment #4). Should the incident-role rule ever make the on-call person or the alert's acknowledger the commander (incident.io assigns the lead by workflow: on-call schedule, escalation acknowledger, or by hand; docs.incident.io/incidents/roles)? Decide when this task is planned; until then nobody but the declarer is commander at create.

---
<!-- COMMENTS:END -->
