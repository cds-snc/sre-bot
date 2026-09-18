---
id: TASK-25.7
title: >-
  Bring Sentinel onto the outbound-client contract: signed-request client
  factory and classify_sentinel_error; the audit sink moves out of the vendor
  package
status: To Do
assignee: []
created_date: '2026-09-18 16:51'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies: []
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - decisions/layers.md
  - app/integrations/sentinel/client.py
  - app/infrastructure/audit
parent_task_id: TASK-25
priority: medium
ordinal: 240000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Created 2026-09-18 (human decision: every vendor conforms to decisions/outbound-clients.md).

TODAY (verified 2026-09-18). app/integrations/sentinel/client.py (190 lines):
- It builds the Azure Log Analytics HMAC signature and posts with requests (timeout=60, no retry policy).
- It also holds audit behaviour: send_event, log_to_sentinel and log_audit_event, the last documented as 'never raises; always logs and returns a status bool'.
- It imports infrastructure.audit.models.AuditEvent, which breaks the rule that integrations imports nothing above infrastructure.operations (TASK-18's contract c).
- It reads settings into module constants at import time.
- It has no classify_sentinel_error.

CONSUMERS (re-grep): log_to_sentinel is called from api/v1/routes/webhooks.py, modules/provisioning/entities.py and five modules/incident files (notify_stale_incident_channels, incident, incident_alert, incident_conversation, incident_helper). log_audit_event has its own callers in the audit path.

DESIGN QUESTION FOR THE PLANNER (raise it in chat, do not decide it in the plan). The audit sink is a cross-cutting, business-agnostic capability, and infrastructure/audit already exists. A likely home is a Sentinel implementation of an audit-sink Protocol in infrastructure/audit (Path A, decisions/layers.md), which keeps the never-raise policy there and leaves the vendor package pure. Confirm against layers.md and decisions/workplace-systems.md, since Sentinel is a hosting-type backing service, not a workplace system.

TARGET. The vendor package exports a factory for the signed HTTP client (explicit timeout, retry configured once) and classify_sentinel_error only. The audit policy (never-raise, payload serialization) lives with its owner, and the vendor package no longer imports infrastructure.audit.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/sentinel/ exports only the client factory (explicit timeout, retry configured once) and classify_sentinel_error; it imports nothing from infrastructure above infrastructure.operations and reads no settings at import time
- [ ] #2 The audit-sink behaviour (log_to_sentinel, log_audit_event, never-raise policy) lives in its decided owner, and all current consumers are repointed with behaviour unchanged
- [ ] #3 Classification tests cover each mapped failure family plus one unmapped exception propagating; the signature construction keeps its existing test coverage
- [ ] #4 ruff, mypy, pytest tests --ignore=tests/smoke and make check-vendor-package-contract pass, with output recorded in notes
<!-- AC:END -->
