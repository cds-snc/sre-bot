---
id: TASK-5.2
title: >-
  Idempotency: migrate Slack legacy_slack_listener dedup onto
  claim/complete/release
status: To Do
assignee: []
created_date: '2026-07-24 17:57'
updated_date: '2026-07-24 19:29'
labels:
  - security
  - phase-0
  - reliability
milestone: m-0
dependencies:
  - TASK-5.1
references:
  - decisions/reliability.md
  - 'https://github.com/cds-snc/sre-bot/issues/1349'
parent_task_id: TASK-5
priority: high
ordinal: 75000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Second slice of the TASK-5 decomposition (see TASK-5 for full rationale). Depends on TASK-5.1 (the claim/complete/release primitive and in-memory fake).

Aligns with decisions/reliability.md (Idempotency - true redelivery dedup is the canonical claim/complete/release use case).

Scope: app/integrations/slack/utils.py::legacy_slack_listener currently does get-then-set on the racy IdempotencyService (the TOCTOU bug). Rewrite it to: claim() on receipt, complete(outcome) on success, release() on failure, using the IdempotencyStore from TASK-5.1.

generate_slack_idempotency_key (same file) has a fallback branch slack:generic:{sha256(payload)} for events with no trigger_id/action/view - a payload hash, prohibited by decisions/reliability.md. Remove this fallback branch. Do NOT silently decide its replacement (reject the unrecognized shape vs. some other stable id) - flag this as an open product question for human/product decision during implementation, and leave the decision unresolved rather than guessing.

Update the tests for legacy_slack_listener and generate_slack_idempotency_key accordingly.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 legacy_slack_listener claims on receipt, completes(outcome) on success, and releases() on failure using the IdempotencyStore from TASK-5.1; no more get-then-set
- [ ] #2 The slack:generic:{sha256(payload)} fallback branch in generate_slack_idempotency_key is removed; behavior for requests with no trigger_id/action/view is called out as an explicit open product decision, not silently resolved
- [ ] #3 Existing unit tests for legacy_slack_listener and generate_slack_idempotency_key are updated to assert against the new claim/complete/release calls
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Tests pass
- [ ] #2 PR references decisions/reliability.md and documents the open question about the no-trigger_id/action/view fallback for human/product follow-up
<!-- DOD:END -->
