---
id: TASK-168
title: >-
  Design session: reassess the webhooks architecture end to end and re-cut
  TASK-37
status: To Do
assignee: []
created_date: '2026-10-26T14:02:00Z'
labels:
  - architecture
  - webhooks
dependencies:
  - TASK-167
references:
  - decisions/webhooks.md
  - decisions/security.md
  - decisions/reliability.md
  - decisions/platform-transports.md
priority: medium
type: spike
ordinal: 443000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Human-led design session (2026-10-26, human decision). The inbound webhook surface (app/modules/webhooks/, app/modules/slack/webhooks*.py, api/v1/routes/webhooks.py) is to be fully reassessed, as the incident and access features are, rather than refactored slice by slice under the current decisions/webhooks.md. TASK-37.1 to 37.5 and TASK-47, 48 and 49 are not planned until this session lands; their current text is input, not scope.

Inputs: the antipatterns decisions/webhooks.md Context lists (payload guessing, import-time filesystem-walk registries, Slack coupling, raw DynamoDB shapes, business logic in the route, no idempotency); the organisation-content decision from TASK-167, since sender mappings and message templates are organisation content; security.md Webhooks (authenticity, rate limit, body cap); reliability.md (idempotency, queues); the TASK-36.2 pins of today's behaviour.

Questions the session answers with current practice (Standard Webhooks, CloudEvents, managed gateways such as Svix and Hookdeck, PagerDuty and incident.io alert sources): is inbound webhooks a capability, a transport or a feature; how a sender is identified and its payload typed (declared per webhook, never guessed); where sender mappings and templates live (TASK-167); authenticity and secret issuance; idempotency and retries; fan-out to features (alerts into incidents) and to channels; the migration path for existing senders.

Invariants carried over (not reopened): nothing registers at import time and nothing is discovered by walking a directory or resolving import strings; boot fails on a bad registration; no payload guessing; ingest is idempotent under redelivery.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 decisions/webhooks.md is rewritten (or superseded) from the session, with cited sources, and is consistent with the TASK-167 organisation-content decision
- [ ] #2 TASK-37 and its subtasks, and TASK-47, 48 and 49, are rewritten, superseded or archived to match, each remaining slice a single PR under the size gate
- [ ] #3 The re-cut slices are placed in the doc-11 work queue ahead of the rows that wait on TASK-37 (TASK-88, TASK-40)
<!-- AC:END -->
