---
id: TASK-5.4
title: >-
  Access Sync: extract job-status polling into its own store; delete legacy
  IdempotencyService
status: Done
assignee: []
created_date: '2026-07-24 17:58'
updated_date: '2026-07-28 12:24'
labels:
  - security
  - phase-0
  - reliability
milestone: m-0
dependencies:
  - TASK-5.1
  - TASK-5.2
references:
  - decisions/reliability.md
  - 'https://github.com/cds-snc/sre-bot/issues/1351'
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
- [x] #1 A small, package-owned Protocol (e.g. JobStatusStore) exists under app/packages/access/sync/ for job-status records (running/completed/failed); placement confirmed against .github/instructions/packages-python.instructions.md
- [x] #2 app/packages/access/sync/interactions/http.py (~line 213), interactions/slack.py (~line 357), and job_runner.py's status writes are migrated off get_idempotency_service()/IdempotencyService onto the new store
- [x] #3 Once nothing references infrastructure/idempotency/{cache.py,service.py,factory.py}'s IdempotencyService/DynamoDBIdempotencyService/get_cache/get_idempotency_service, those files are deleted
- [x] #4 grep confirms no remaining get-then-put job-status pattern anywhere in app/packages/access/sync
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Tests pass; dependency ordering with TASK-5.2/TASK-5.3 documented if legacy-file deletion must wait for all callers to move
- [x] #2 PR references decisions/reliability.md (job-status vs idempotency clause)
<!-- DOD:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-27 14:00
---
TASK-5.2 was re-scoped (2026-07-27) from migrating the dead legacy_slack_listener onto claim/complete/release to simply DELETING app/integrations/slack/utils.py (zero callers; wrong layer; obsoleted by the async-Bolt direction). That deletion removes the last app/integrations/ reference to the legacy get_idempotency_service, so it is now a prerequisite for this task's deletion of the legacy IdempotencyService stack - added TASK-5.2 to dependencies alongside TASK-5.1.
---

created: 2026-07-27 18:53
---
Decomposed 2026-07-27 per the single-PR size gate (implementation-planning skill): the full scope (new JobStatusStore + 5 consumer rewires + deleting 4 legacy files/protocols + ~9 test files, ~13 production/test files touched) exceeds the ~10-file single-PR threshold. Split into:
- TASK-5.4.1 (expand+migrate): new package-owned JobStatusStore built on infrastructure.storage.StorageService (DRY reuse of the same generic capability SyncRunRepository already uses; confirmed with the human citing 12factor.net "backing services as attached resources"), reusing the existing sre_bot_idempotency table (no terraform change). Migrates ALL 5 legacy get_idempotency_service()/IdempotencyService call sites in app/packages/access/sync, including platform_lock.py's holder-info reporting (added by TASK-5.3; not named in this task's original Scope paragraph but confirmed in scope with the human since it blocks 5.4.2's deletion step).
- TASK-5.4.2 (contract, depends on 5.4.1): deletes infrastructure/idempotency/cache.py + service.py, removes DynamoDBCache from dynamodb.py and the IdempotencyService Protocol from protocol.py, prunes factory.py/__init__.py, and removes the now-obsolete tests. Closes this task's AC#3/DoD#1.

This coordinator task's own ACs/DoD are unchanged - they remain the "all children done" bar. Do not implement against this task's description directly; see TASK-5.4.1 for the approved, fully-grounded implementation plan.
---
<!-- COMMENTS:END -->
