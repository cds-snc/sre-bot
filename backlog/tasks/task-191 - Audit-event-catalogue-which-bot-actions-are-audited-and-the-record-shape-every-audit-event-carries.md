---
id: TASK-191
title: >-
  Audit event catalogue: which bot actions are audited and the record shape
  every audit event carries
status: To Do
assignee: []
created_date: '2026-11-20T22:05:00Z'
labels:
  - audit
  - observability
  - security
dependencies:
  - TASK-171
priority: medium
type: feature
ordinal: 538000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Created 2026-11-20 (human, TASK-145.10 OQ2): the Sentinel events the bot sends today carry little (legacy {event, message} envelope; few actions emit). TASK-122 moves the audit trail into a capability and TASK-25.7 fixes the transport; neither defines the content. TASK-171 (row Z2) rules whether the bot keeps writing to Sentinel and where.

Scope (decision + catalogue, small code):
- The catalogue of auditable actions: incident declare, severity/status/role changes, close/archive, postmortem meeting scheduled/rescheduled/cancelled, access grants and revocations, webhook receipts, plugin/admin actions; each with its event name.
- The record shape: actor, action, target (type and id, e.g. incident id), outcome, occurred-at time, request_id, source surface; never a request body or secret (OWASP Logging Cheat Sheet when/where/who/what; OWASP Logging Vocabulary).
- observability.md amended (audit events section; replaces the interim minimal-fields rule at observability.md:20 once TASK-122 lands).
- TASK-122's AuditEvent adopts the shape; TASK-25.7 sends it.

Sources: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html, https://cheatsheetseries.owasp.org/cheatsheets/Logging_Vocabulary_Cheat_Sheet.html, https://docs.aws.amazon.com/prescriptive-guidance/latest/logging-monitoring-for-application-owners/event-attributes.html
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 observability.md records the audit event catalogue (event names per auditable action) and the record shape (actor, action, target, outcome, occurred-at, request_id, source; no bodies or secrets)
- [ ] #2 TASK-122's AuditEvent and TASK-25.7's sink are re-scoped against the catalogue (comments on both)
- [ ] #3 Every existing emitter (legacy log_to_sentinel callers, response/ and postmortem/ Sentinel adapters) is mapped to a catalogue entry or marked for removal
<!-- AC:END -->
