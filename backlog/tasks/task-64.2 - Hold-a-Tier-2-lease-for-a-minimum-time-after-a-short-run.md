---
id: TASK-64.2
title: Hold a Tier-2 lease for a minimum time after a short run
status: To Do
assignee: []
created_date: '2026-11-18T19:00:00Z'
labels:
  - architecture
  - reliability
milestone: m-4
dependencies:
  - TASK-64.1
references:
  - decisions/reliability.md
  - https://github.com/lukas-krecan/ShedLock
parent_task_id: TASK-64
priority: medium
ordinal: 529000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Behavior slice of TASK-64 (approved 2026-11-18). run_if_leased (infrastructure/coordination/lease.py) releases at job end, so a run shorter than the gap between two replicas' ticks lets the second replica run the same tick (the incident legacy upgrade dry run reported twice per interval, 0.7 s apart, 2026-11-17). decisions/reliability.md (2026-11-18) requires a minimum hold, ShedLock's lockAtLeastFor. Design (approved): hold = min(lease TTL, interval - [scheduler] lease_hold_margin_seconds, default 5), so a daily job holds its TTL and the TTL stays the maximum hold; new primitive ConditionalWriteStore.expire_at(key, claim_token, at) (conditional update under the claim token, never a delete; DynamoDB UpdateItem, already granted by IAM), LeaseStore.release(name, claim_token, *, not_before=), run_if_leased(..., min_hold=) holding after a short or failed run and releasing as today when the run ends past the hold. Applies to every Tier-2 job at once (TASK-64.1 put them all on the registry). TASK-145.9.2 and TASK-147.6 wait on it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 ConditionalWriteStore.expire_at sets an in-progress claim held by the token to expire at the given epoch second, never deleting it; a stale token, a missing key or a COMPLETED key returns False and changes nothing; both stores pass the conformance suite for it (parent AC #6)
- [ ] #2 LeaseStore.release takes not_before: a future instant keeps the lease until then through expire_at, None or a past instant deletes as today
- [ ] #3 run_if_leased with min_hold keeps the lease until start plus min_hold after a run that ends earlier, including a failed run, and releases at end after a longer run
- [ ] #4 The registry derives the hold as min(lease TTL, interval - [scheduler] lease_hold_margin_seconds) (daily: the TTL); the margin is a typed setting declared in config/base.toml with default 5
- [ ] #5 A test runs a short Tier-2 job on two simulated replicas over one store, ticks about a second apart, and asserts a single run per tick across several ticks; a control without the hold runs twice per tick (parent AC #6)
- [ ] #6 decisions/reliability.md states the hold formula, expire_at beside acquire and release, and a Checks line for the hold
<!-- AC:END -->
