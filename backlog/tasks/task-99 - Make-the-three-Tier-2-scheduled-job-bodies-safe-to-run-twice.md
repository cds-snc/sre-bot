---
id: TASK-99
title: Make the three Tier-2 scheduled job bodies safe to run twice
status: To Do
assignee: []
created_date: '2026-09-17 20:39'
updated_date: '2026-09-17 20:47'
labels:
  - infrastructure
  - reliability
  - phase-4
milestone: m-4
dependencies: []
references:
  - decisions/reliability.md
  - app/jobs/scheduled_tasks.py
  - app/modules/incident/notify_stale_incident_channels.py
priority: high
ordinal: 227000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Precondition for flipping the conditional-claim re-read policy to fail-open (the follow-up task created alongside this one). Found while planning TASK-25.2.5.4 on 2026-09-17.

decisions/reliability.md states that a Tier-2 lease is "a duplication optimization, never a correctness mechanism: the job body must be idempotent regardless", and that over-run takeover is acceptable. That is a mandate, not a description of the code. Verified 2026-09-17 that at least one Tier-2 body is not safe to run twice, which is why the lease currently carries correctness it was never supposed to carry.

THE THREE TIER-2 JOBS (app/jobs/scheduled_tasks.py:101-109, wrapped by _tier2/run_if_leased):
- scheduler:notify_stale_incident_channels -> app/modules/incident/notify_stale_incident_channels.py:14-35. Posts a nag message with interactive Archive / Schedule-Retro buttons into EVERY stale incident channel. No idempotency key, no dedup, no marker. A second concurrent run double-posts into live incident channels, and the duplicate buttons are independently clickable. This is the clearest failure and the one to fix first.
- scheduler:provision_aws_identity_center -> app/modules/aws/identity_center.py. Provisioning writes; convergent in shape, but not verified replay-safe.
- scheduler:spending_generate_spending_data -> app/modules/aws/spending.py.

Also in scope for the same reason, because they take the same lease primitive: the Access Sync platform and user sync jobs (app/packages/access/sync/job_runner.py run_platform_sync_job / run_user_sync_job, locked via platform_lock.py).

RELATED, NOT DUPLICATE: TASK-87 covers non-replay-safe Google Workspace writes at the SDK-retry level (one call resent by the client library). This task covers the coarser hazard: the whole job body running twice concurrently on two replicas. A body can be safe under TASK-87 and still unsafe here.

Approach is for the planner to settle. Options that exist in this codebase already: a per-run idempotency claim on the shared conditional-write primitive keyed by job name plus period; a persisted "last notified" marker per channel; or making the write itself convergent. Do not assume the lease will protect the body - that is precisely the assumption being removed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each of the three Tier-2 job bodies, plus the Access Sync platform and user sync jobs, is documented as safe to run twice concurrently, with the mechanism named per job
- [ ] #2 notify_stale_incident_channels does not post a duplicate nag into an incident channel when the body runs twice in the same period, covered by a test
- [ ] #3 Any body that cannot be made duplicate-safe is called out explicitly, with the residual exposure recorded, rather than left implicitly relying on the lease
- [ ] #4 decisions/reliability.md's idempotent-job-body mandate is either satisfied by the code or amended to match what the code actually guarantees
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-17 20:47
---
SEQUENCING NOTES 2026-09-17 (checked while auditing the dependency wiring; none of these is a blocker, and none is wired as a dependency on purpose).

- TASK-100 DEPENDS ON THIS TASK. It flips the contended-claim re-read to fail-open, which is only safe once these bodies are duplicate-safe. This task is the gate on that flip - do not close it with bodies still unsafe just to unblock it.
- TASK-38 (migrate modules/incident to a feature package) will relocate notify_stale_incident_channels; its candidate split puts it under alerts/. NOT a dependency in either direction. This task fixes live duplicate posting into incident channels and must not wait on a package migration; the migration then carries the fix along mechanically. TASK-38's planner should be told this landed.
- TASK-65 (strangle the scheduler pull-hub, m-5) moves these three jobs' REGISTRATION into feature register_background_jobs hookimpls and eventually deletes the _tier2 wrapper in app/jobs/scheduled_tasks.py. It changes where a job is registered and where its lease TTL comes from, not whether the body is safe to run twice. Independent; no dependency.
- TASK-87 (non-replay-safe Google Workspace writes) is the finer-grained sibling: one SDK call resent by the client library, versus this task's whole-body concurrent duplicate. A body can be fixed under TASK-87 and still unsafe here, and vice versa. No dependency; cross-check the write call sites so the two fixes do not collide.

Evidence that made this task high priority (verified 2026-09-17): app/modules/incident/notify_stale_incident_channels.py:14-35 posts a nag with interactive Archive / Schedule-Retro buttons into every stale incident channel, with no idempotency key and no marker. Two concurrent runs double-post into live incident channels and the duplicate buttons are independently clickable.
---
<!-- COMMENTS:END -->
