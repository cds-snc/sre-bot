---
id: TASK-5.4
title: >-
  Access Sync: extract job-status polling into its own store; delete legacy
  IdempotencyService
status: To Do
assignee: []
created_date: '2026-07-24 17:58'
labels:
  - security
  - phase-0
  - reliability
milestone: m-0
dependencies:
  - TASK-5.1
references:
  - decisions/reliability.md
parent_task_id: TASK-5
priority: high
ordinal: 77000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Fourth slice of the TASK-5 decomposition (see TASK-5 for full rationale). Depends on TASK-5.1 (the claim/complete/release primitive); may run in parallel with TASK-5.2/TASK-5.3, but is the slice that finally deletes the legacy get/set-shaped module once nothing else references it.

Aligns with decisions/reliability.md's new clause: querying the current state of a long-running job for a poller is a different capability from idempotency dedup/locking - a plain keyed record store that is read many times and overwritten as state progresses - and must not be modeled as a get/set cache smuggled in under the idempotency name.

Scope: app/packages/access/sync/job_runner.py writes running/completed/failed job-status records keyed by job_id via idempotency.set(); app/packages/access/sync/interactions/http.py (~line 213, get_idempotency_service().get(job_id) for GET /sync-runs/{job_id}) and app/packages/access/sync/interactions/slack.py (~line 357, same pattern for the Slack status command) poll them via idempotency.get(). This is not idempotency - it is job-status polling.

Introduce a small, package-owned Protocol (e.g. JobStatusStore, get/put-shaped) under app/packages/access/sync/ - confirm exact placement against .github/instructions/packages-python.instructions.md's package-boundary rules. Migrate all three call sites off get_idempotency_service(). Once nothing references infrastructure/idempotency/{cache.py,service.py,factory.py}'s IdempotencyService/DynamoDBIdempotencyService/get_cache/get_idempotency_service, delete those files - this is where TASK-5's original 'delete the get-then-put path' finally fully closes.

Note: if TASK-5.2 and/or TASK-5.3 have not yet migrated their own call sites off get_idempotency_service() at the time this subtask ships, the legacy-file deletion step must wait until they have; land the new JobStatusStore first and defer only the final deletion if needed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A small, package-owned Protocol (e.g. JobStatusStore) exists under app/packages/access/sync/ for job-status records (running/completed/failed); placement confirmed against .github/instructions/packages-python.instructions.md
- [ ] #2 app/packages/access/sync/interactions/http.py (~line 213), interactions/slack.py (~line 357), and job_runner.py's status writes are migrated off get_idempotency_service()/IdempotencyService onto the new store
- [ ] #3 Once nothing references infrastructure/idempotency/{cache.py,service.py,factory.py}'s IdempotencyService/DynamoDBIdempotencyService/get_cache/get_idempotency_service, those files are deleted
- [ ] #4 grep confirms no remaining get-then-put job-status pattern anywhere in app/packages/access/sync
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Tests pass; dependency ordering with TASK-5.2/TASK-5.3 documented if legacy-file deletion must wait for all callers to move
- [ ] #2 PR references decisions/reliability.md (job-status vs idempotency clause)
<!-- DOD:END -->
