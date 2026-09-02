---
id: TASK-75
title: >-
  oncall_sync: durable suppression + configurable interval for repeated
  unapproved-domain alerts
status: To Do
assignee: []
created_date: '2026-09-02 20:25'
labels:
  - oncall-sync
  - slack
  - configuration
  - observability
dependencies:
  - TASK-74
references:
  - decisions/reliability.md
  - decisions/observability.md
  - app/packages/access/sync/job_status_store.py
  - app/packages/oncall_sync/adapters/slack.py
  - app/packages/oncall_sync/settings.py
  - app/packages/oncall_sync/providers.py
ordinal: 144000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow-up to TASK-74. TASK-74 adds approved-domain filtering and a single per-tick INFO-level structured event (Slack handle + privacy-safe SHA-256 email fingerprint, no raw email) whenever an on-call participant's email domain is not approved. That is enough to stop the recurring ERROR-level Slack users_not_found noise, but it still logs one INFO line every sync tick (default every 5 minutes) for as long as the source-data mismatch persists.

This task adds a durable, feature-owned alert-suppression record so a first-occurrence event is actionable and duplicates are suppressed until a configurable interval expires, then a fresh event can fire again. Reuse the existing packages/access/sync/job_status_store.py::JobStatusStore shape (wrap infrastructure.storage.StorageService, share the sre_bot_idempotency DynamoDB table, store a JSON payload with expires_at to avoid DynamoDB attribute-type round-trip issues) as the precedent for a small, package-owned keyed record store -- do not build a shared/generic cross-feature primitive as part of this task.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A feature-owned suppression-interval setting is added to OnCallSyncSettings with a cached provider; no directory or legacy setting is reused.
- [ ] #2 A durable, feature-owned suppression record keyed by Slack handle and SHA-256 email fingerprint (DynamoDB via StorageService) suppresses duplicate unapproved-domain-mismatch events until the configured interval expires.
- [ ] #3 The first occurrence within a suppression window still emits the structured mismatch event from TASK-74; duplicates within the window are suppressed and a new event can be emitted once the interval expires.
- [ ] #4 Focused tests cover suppression-interval settings parsing and durable suppression/expiry behavior (fresh key, unexpired key, expired key).
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Mypy and ruff are clean for changed files, and focused oncall_sync tests pass.
- [ ] #2 A human verifies the suppression-interval deployment value before enabling the behavior in production.
<!-- DOD:END -->
