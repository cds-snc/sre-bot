---
id: TASK-148
title: Move the lease duration onto the conditional-write claim call
status: To Do
assignee: []
created_date: 2026-10-14 18:57
updated_date: '2026-11-18T19:00:00Z'
labels:
  - infrastructure
  - reliability
  - plugin-architecture
milestone: m-7
dependencies:
  - TASK-58.2
references:
  - decisions/reliability.md
  - decisions/dependency-injection.md
  - https://github.com/cds-snc/sre-bot/issues/1715
priority: medium
ordinal: 382000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Decided 2026-10-14 (human, while planning TASK-109): the svcs registry holds one ConditionalWriteStore per contract (registered at the settings-default in-progress TTL), and consumers build LeaseStore and IdempotencyStore themselves with their own read-failure policy. The lease TTL is still a store-construction parameter: infrastructure/coordination/factory.py build_lease_store(in_progress_ttl_seconds) and the per-TTL @cache get_lease_store(ttl_seconds). A type-keyed registry cannot hold one store per TTL, so non-default-TTL leases cannot come from the registered store.

Consumers with their own TTL today: Access Sync's platform/user lock (lock_stale_seconds, 14400 s, packages/access/sync/providers.py get_access_sync_lock_store) and the scheduler's Tier-2 leases (DEFAULT_TIER2_LEASE_TTL_SECONDS via get_lease_store in jobs/scheduled_tasks.py _tier2).

Target: the duration travels with the call, as in Kubernetes Lease and etcd leases. ConditionalWriteStore.claim gains a keyword-only optional in-progress TTL override (default: the store's configured TTL); LeaseStore.acquire takes the lease duration; run_if_leased passes it through; both stores (DynamoDB, in-memory) honour it, and the conformance suite covers it. Then build_lease_store(ttl) and get_lease_store(ttl) are deleted and every lease comes from the one registered store. IdempotencyStore keeps the default TTL.

Blocks TASK-124.1 (Access Sync resolves the store from the registry when it moves) and TASK-64 (the scheduler registry declares a per-job lease TTL). Does not block TASK-109 or TASK-37.2 (dedup uses the default TTL).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 ConditionalWriteStore.claim accepts a keyword-only optional in-progress TTL override, honoured by both stores and covered by the conformance suite
- [ ] #2 LeaseStore.acquire and run_if_leased take the lease duration; no lease TTL is a store-construction parameter
- [ ] #3 build_lease_store and get_lease_store are deleted; Access Sync and the scheduler acquire with their own durations from one store
- [ ] #4 decisions/reliability.md describes per-call lease duration, with a dated change entry
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-18 (TASK-64 planning, human approved): TASK-64 no longer depends on this task; its per-job TTL is met by get_lease_store(ttl) since TASK-145.5.7.1. TASK-64.2 adds ConditionalWriteStore.expire_at (a per-call expiry under the claim token); when the claim's duration moves onto the call here, expire_at stays and the conformance suite keeps covering it.
<!-- SECTION:NOTES:END -->
