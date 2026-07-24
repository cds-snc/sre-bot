---
id: TASK-5.1
title: >-
  Idempotency: atomic claim/complete/release primitive, in-memory fake, and
  dedicated settings slice
status: To Do
assignee: []
created_date: '2026-07-24 17:57'
labels:
  - security
  - phase-0
  - reliability
milestone: m-0
dependencies: []
references:
  - decisions/reliability.md
  - decisions/cloud-portability.md
  - decisions/configuration.md
parent_task_id: TASK-5
priority: high
ordinal: 74000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Foundational slice of the TASK-5 decomposition (see TASK-5 for full rationale). Scoped to app/infrastructure/idempotency/ only; does NOT touch any caller.

Aligns with decisions/reliability.md (Idempotency), decisions/cloud-portability.md (contract 4 - in-memory fake as standing second provider), decisions/configuration.md (Ownership + incremental-migration clause).

Steps:
1. Define IdempotencyStore Protocol + ClaimResult (NEW/COMPLETED/IN_PROGRESS) in app/infrastructure/idempotency/protocol.py. No DynamoDB vocabulary (no ConditionExpression parameters) in the Protocol surface.
2. Rewrite app/infrastructure/idempotency/dynamodb.py's claim using PutItem with ConditionExpression attribute_not_exists(pk), status IN_PROGRESS with a bounded in-progress TTL. ConditionalCheckFailed branches: COMPLETED -> return recorded outcome; IN_PROGRESS unexpired -> concurrent duplicate, reject/defer; IN_PROGRESS expired -> claimant crashed, take over and re-execute. complete() records the outcome; release() deletes so redelivery retries.
3. New key format: plain f"{feature}:{intent}:{idempotency_id}" string formatting. No hashing utility of any kind.
4. New in-memory fake implementing the same Protocol (the standing second provider per decisions/cloud-portability.md contract 4).
5. Migrate idempotency settings NOW, in this same change: new app/infrastructure/idempotency/settings.py (IdempotencySettings + get_idempotency_settings()); delete app/infrastructure/configuration/infrastructure/idempotency.py and its exports from that package's __init__.py. This is not TASK-24 scope - it is an orphaned legacy-settings-home instance that decisions/configuration.md's incremental-migration rule requires to move with whatever work touches the domain.
6. Delete app/infrastructure/idempotency/key_builder.py and IdempotencyKeyBuilder - verified dead code (grep shows zero real call sites, only self-export and its own docstring). Remove its export from infrastructure/idempotency/__init__.py.
7. Shared Protocol-conformance test suite run against both the DynamoDB implementation (moto) and the fake, covering: the concurrency case (two concurrent identical claims -> exactly one NEW and one IN_PROGRESS/COMPLETED, asserted via the conditional-write path not timing) and the key-format rule.

Explicit exclusion: do NOT touch callers yet. Old IdempotencyService/DynamoDBIdempotencyService/cache.py/service.py/factory.py's get_idempotency_service() stay in place untouched so existing callers (job_runner.py, platform_lock.py, interactions/http.py, interactions/slack.py, interactions/ingress.py, integrations/slack/utils.py) keep working unmodified until their own subtasks land. This is the one deliberate exception to 'no dead code left behind' in this decomposition - it is transitional and closed out by the job-status-extraction subtask.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 IdempotencyStore Protocol exists in app/infrastructure/idempotency/protocol.py with claim/complete/release and ClaimResult (NEW/COMPLETED/IN_PROGRESS); no vendor types or vendor query syntax in its signatures
- [ ] #2 DynamoDB implementation's claim() uses ConditionExpression attribute_not_exists(pk); grep shows no get-then-put pattern remains in app/infrastructure/idempotency/dynamodb.py
- [ ] #3 Concurrency test: two concurrent identical claims yield exactly one NEW and one IN_PROGRESS/COMPLETED outcome, asserted via the conditional-write path, not timing
- [ ] #4 In-memory fake implements the same Protocol and passes the shared conformance test suite alongside the DynamoDB implementation (moto)
- [ ] #5 Keys follow {feature}:{intent}:{idempotency_id}; no payload hash, no truncation (key-format test); IdempotencyKeyBuilder and key_builder.py are deleted
- [ ] #6 IdempotencySettings/get_idempotency_settings() live in app/infrastructure/idempotency/settings.py; app/infrastructure/configuration/infrastructure/idempotency.py and its exports are deleted
- [ ] #7 Old IdempotencyService/DynamoDBIdempotencyService/cache.py/service.py/factory.py/get_idempotency_service() remain untouched and functional for existing callers (transitional exception, closed out by the job-status-extraction subtask)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Shared Protocol-conformance suite passes against both the DynamoDB implementation (moto) and the in-memory fake
- [ ] #2 No caller migrations included in this PR; existing callers of get_idempotency_service() continue to pass their current tests unmodified
- [ ] #3 PR references decisions/reliability.md, decisions/cloud-portability.md, decisions/configuration.md
<!-- DOD:END -->
