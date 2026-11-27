---
id: TASK-197.2
title: >-
  Field encryption 2: the seal and open contract, its in-memory fake, and the
  Tink envelope implementation
status: To Do
assignee: []
created_date: '2026-11-27T16:46:00Z'
labels:
  - security
  - infrastructure
  - portability
milestone: m-4
dependencies:
  - TASK-197.1
references:
  - decisions/security.md
  - decisions/organisation-content.md
  - decisions/cloud-portability.md
  - decisions/outbound-clients.md
parent_task_id: TASK-197
priority: high
ordinal: 558000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
doc-11 row 22.12b; a single PR from origin/main after 22.12a, before 22.13 (TASK-47).
Scope:
- contracts/: a Protocol with async seal(plaintext: bytes, *, context: Mapping[str, str]) -> bytes and async open(sealed: bytes, *, context: Mapping[str, str]) -> bytes. The sealed bytes are opaque and versioned and name their key; open with a different context fails.
- An in-memory fake (a real local AEAD keyset, never production) and a conformance suite that every implementation runs (make check-fake-coverage).
- infrastructure/: a Tink KMS envelope AEAD implementation. The key URI comes from a typed settings slice in the configuration files (backend chosen by configuration, cloud-portability.md rule 1). The AWS client is built by a factory with an explicit timeout and retries, and the blocking calls run in asyncio.to_thread (outbound-clients.md); check whether Tink accepts that boto3 client, or implement Tink's KMS client interface over it. A plaintext cache with TTL and size settings.
- Registered in the service registry (phase 2, no network call at construction); no consumer yet (TASK-47 and TASK-37.8 consume it).
- tink 1.16.1 (cp314 wheels, released 2026-08-13; the dependency cooldown interim rule holds until row 22.1d).
- ADR edits with this PR: webhooks.md section 9, security.md and organisation-content.md replace 'the AWS Database Encryption SDK or direct KMS, chosen at TASK-47' with this decision; cloud-portability.md names the contract as a hosting contract and records the move path (the sealed value names its key, so a move reads with both keys while a job reseals every value under the new one).
Blast radius: a new service that nothing calls; boot builds it without a network call. Rollback: one revert. Change notice: FYI for plugin authors (a new hosting contract).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The contract's seal and open round-trip through the in-memory fake and the Tink implementation in one conformance suite; open with a different context, a tampered byte or an unknown key fails with a typed error (test)
- [ ] #2 The key URI, the cache TTL and the cache size are typed settings with defaults in the configuration files; the backend is chosen by the key URI (test + check)
- [ ] #3 The AWS KMS calls use a factory-built client with an explicit timeout and retries, offloaded with asyncio.to_thread; boot makes no network call (test)
- [ ] #4 make check-fake-coverage, check-import-contracts and check-settings-key-ownership are green (check)
- [ ] #5 webhooks.md, security.md, organisation-content.md and cloud-portability.md carry the decision with Changes lines (review)
<!-- AC:END -->
