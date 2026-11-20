---
id: TASK-168
title: >-
  Design session: reassess the webhooks architecture end to end and re-cut
  TASK-37
status: To Do
assignee: []
created_date: '2026-10-26T14:02:00Z'
updated_date: '2026-11-20T15:23:00Z'
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
- [ ] #4 Webhook sender kinds (match, extract, template) are provisioned content and webhook instances managed content (decisions/organisation-content.md, provisioned-content.md, managed-content.md); the session chooses the matching and template engine for every content kind: declarative matching, logic-light templates over a fixed data model with an undefined name an error, size and count limits; the re-cut slices delete the per-sender Python in modules/webhooks/patterns/ and its import-time walk
- [ ] #5 bin/deploy-checks.zsh post: the Non-JSON section's webhook pattern exclusion (added by TASK-28.2) is removed and any non-JSON line FAILs once import-time pattern discovery is gone
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-03: AC added from TASK-28.2's approved plan; 28.2 leaves the import-time webhook pattern lines plain (unconfigured structlog, local-time stamp) and excludes them in deploy-checks.

2026-11-03 (from TASK-28.4's approved plan): TASK-28.4 lowers the import-time webhook pattern lines (registered_pattern, registered_notification_pattern, no_handlers_found_in_module) to DEBUG and deletes the dead modules/webhooks/patterns/examples.py (pattern_registration_success had no caller); they still print plain at import because structlog is unconfigured then, so AC #5's exclusion removal stays this task's.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-20T14:47:00Z

---

2026-11-20 inputs from TASK-36.2 planning (human-approved): (1) modules/webhooks/aws_sns.py:41,47 interpolate the builtin id ('<built-in function id>' in the ops text) and :36 logs the topic ARN as webhook_id: recorded legacy bug, kind (a) candidate, no pin asserts it. (2) SNS SignatureVersion 2 (SHA256, AWS-recommended: https://docs.aws.amazon.com/sns/latest/dg/sns-verify-signature-of-message.html) is rejected today (installed sns_message_validator accepts only '1'); pinned legacy_only; rule whether the rebuilt verifier accepts 1 and 2 (TASK-37.2 AC) and record it in security.md Webhooks. (3) duplicate _get_bot_client in modules/webhooks/base.py:21 and api/v1/routes/webhooks.py:27. (4) /api/v1/hook retention and the CRS scope-down covering only /hook/ (TASK-37.4 AC #6; decide on a production access-log check since 2026-11-03; record the bare /hook/{webhook_id} durable-URL statement in webhooks.md). (5) per-IP rate-limit bucket shared across webhook ids (legacy_only, ended by TASK-49). (6) bot-built SNS layouts are pinned by identifying facts only, so provisioned templates (organisation-content.md) may change layout without rewriting the pin.

---

created: 2026-11-20T15:18:00Z

---

2026-11-20 (TASK-36.2 implementation findings): F-A the email regex in integrations/slack/users.py:207 (replace_users_emails_with_mention) backtracks quadratically (32 KB of 'a' 1.2 s; ~80 s CPU for a body under the 256 KiB cap) on an unauthenticated synchronous route: follow-up fix proposed ahead of the rebuild. F-B rate-limit bucket is per sender address and path (TASK-49 comment). F-E/F-F on TASK-37.2.

---

created: 2026-11-20T15:23:00Z

---

2026-11-20: F-A is fixed ahead of the rebuild by TASK-190 (doc-11 row 20a).

---
<!-- COMMENTS:END -->
