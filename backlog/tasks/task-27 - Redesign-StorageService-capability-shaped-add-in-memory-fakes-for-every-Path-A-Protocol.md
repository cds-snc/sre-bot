---
id: TASK-27
title: >-
  Redesign StorageService capability-shaped; add in-memory fakes for every Path
  A Protocol
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-09-24 20:09'
labels:
  - infrastructure
  - phase-4
  - portability
milestone: m-4
dependencies: []
references:
  - decisions/cloud-portability.md
  - 'https://github.com/cds-snc/sre-bot/issues/1281'
  - app/infrastructure/idempotency/factory.py
  - app/infrastructure/storage/protocol.py
  - decisions/plugin-architecture.md
priority: high
ordinal: 27000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
COORDINATOR. Decomposed 2026-09-16 under the single-PR size gate into TASK-27.1, TASK-27.2 and TASK-27.3; this task's acceptance criteria are satisfied by its children. As a single unit it was redesign plus consumer migration plus three fakes plus conformance suites plus a CI check, across infrastructure/storage, infrastructure/audit, infrastructure/directory, packages/access and the test tree - well past the gate. The numbered steps below are kept as the original statement of intent; the slice-to-step mapping is in the plan.

Aligns with decisions/cloud-portability.md contract 4. Today StorageService.query(table, key_condition: str, ...) in app/infrastructure/storage/protocol.py takes DynamoDB KeyConditionExpression strings - vendor query syntax leaking through the Protocol, the exact trap the decisions name. A Protocol that cannot be faithfully faked fails the contract.

Steps:
1. Redesign the StorageService surface in capability terms (typed key/attribute conditions or purpose-named methods like get_items_by_partition) such that an in-memory fake and a future Cosmos/Postgres backend can honor it without consumer changes. Design sketch reviewed before implementation (paste in the task notes).
2. Migrate the DynamoDB implementation and all consumers.
3. Write in-memory fakes for every Path A Protocol currently defined (storage, directory, idempotency - task-5 already delivered idempotency; audit, resilience as applicable) and use them in the integration test suite as the standing second provider.
4. Add a conformance test suite per Protocol run against both fake and real implementation (DynamoDB-Local marked slow).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 StorageService signatures contain no vendor query strings or vendor types; grep KeyConditionExpression appears only inside the DynamoDB implementation (TASK-27.1)
- [ ] #2 The vendor-neutral surface covers what its consumers actually need: a typed key-condition read (TASK-27.1), and an atomic single-attribute update, an atomic numeric increment and a bounded full-table list (TASK-27.2); every operation lands with a real consumer and a two-plausible-provider justification, never speculatively
- [ ] #3 Every hosting contract and every externally facing capability api.py Protocol has an in-memory fake exercised by tests, enforced by the CI fake-coverage check (TASK-27.1 for storage, TASK-27.3 for the check; directory and audit fakes land with their capability moves, TASK-119 and TASK-122)
- [ ] #4 Conformance suites pass against fake and DynamoDB implementations (TASK-27.1, TASK-27.2, TASK-27.3)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 All consumers migrated; tests green
- [ ] #2 PR references decisions/cloud-portability.md
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
COORDINATOR PLAN (2026-09-16). Ground truth read from app/infrastructure/storage/{protocol,service}.py, infrastructure/audit/service.py, packages/access/{request,sync}/store.py, app/tests/unit/infrastructure/storage/, decisions/{cloud-portability,layers,dependency-injection,webhooks}.md and the consumer tasks.

WHY DECOMPOSED (size-gate evidence)
- One PR would span infrastructure/storage, infrastructure/audit, infrastructure/directory, packages/access and the test tree, mixing a Protocol redesign, a consumer migration, three new fakes, conformance suites and a new CI check. Over the two-subsystem limit, and it mixes additive with behaviour-preserving-refactor work.
- The slices have genuinely different readiness: the read redesign has six existing call sites and no live consumer, the write operations have no consumer until TASK-37.1, and the fake coverage blocks nothing at all.

SLICES
1. TASK-27.1 (pull forward, run in parallel with TASK-25.2.5 - disjoint files): the typed key-condition read, the six existing call sites, the storage fake moved into the package. Covers original steps 1 and 2 for the read path, and step 3 for storage. About 165 production LOC.
2. TASK-27.2 (lands with TASK-37.1): atomic single-attribute update, atomic numeric increment, bounded full-table list. This is the slice that actually unblocks TASK-37.1 and TASK-38; both depend on it.
3. TASK-27.3 (after .1, blocks nothing): the directory and audit fakes, the CI fake-coverage check, and the storage package shape (factory.py, settings.py). Covers the rest of steps 3 and 4.

SEQUENCING RATIONALE
- .1 first and now. Its two consumer families are not live in production: infrastructure/audit's service has no importer outside its own package, and packages/access is not enabled. Six call sites is the smallest this migration will ever be, and TASK-32, TASK-60, TASK-83, TASK-83.2, TASK-37.1 and TASK-38 all add consumers to the leaky signature if they land first.
- .2 is deliberately NOT pulled forward. decisions/layers.md bars building Path A surface speculatively, so the write operations wait for TASK-37.1 rather than being added blind.
- .3 last, so every fake is written against the final surface.

EXPLICIT NON-GOALS ACROSS THE SERIES
- Appending to a list attribute (incident log_activity) is a data-model question owned by TASK-38, not a Protocol operation.
- The atomic multi-item conditional write stays with TASK-83.2.
- No compatibility overload of the raw-string query signature is retained at any point (2026-07-28 review decision).

VERIFICATION (every child PR, from app/): uv run ruff check . ; uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' ; uv run pytest tests --ignore=tests/smoke
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-24 17:59
---
TASK-5 was decomposed on 2026-07-24 (single-PR size gate) into TASK-5.1..TASK-5.4. The in-memory idempotency fake this task's description refers to ('idempotency - task-5 already delivered idempotency') now lands specifically in TASK-5.1 (Idempotency: atomic claim/complete/release primitive, in-memory fake, and dedicated settings slice). If this task ends up needing an explicit dependency on the idempotency fake, point it at TASK-5.1, not TASK-5.
---

created: 2026-07-28 13:20
---
Scope confirmation from a 2026-07-28 architecture review: this task is the single HIGHEST-LEVERAGE portability fix - StorageService.query(key_condition: str) leaking KeyConditionExpression is the only 'high effort to reback' seam and it also poisons audit/ (which rides StorageService and has no own fake). Reinforcing the existing ACs: (a) the capability-shaped replacement should be a small vendor-neutral query spec (partition key + optional typed sort-key condition: eq/begins_with/between/gt/lt, limit, forward flag) that the audit time-range read can honor; (b) the Path-A fakes explicitly include directory/ (DirectoryProvider - currently has NO in-memory fake, a cloud-portability.md contract gap) and audit/ (after the query redesign), in addition to storage; (c) cloud-portability.md now states the 'every Path A Protocol has a fake' contract is CI-ENFORCED - wire that check as part of this task. Full-end-state: delete the raw-string query signature outright, no compat overload retained.
---

author: @claude
created: 2026-09-16 13:59
---
2026-09-16: decomposed into TASK-27.1/.2/.3 following the TASK-25.2.5 review. The review question was whether the legacy DynamoDB callers in TASK-25.2.5 should move onto the storage capability instead of onto a provisional adapter; the answer was no (they need vendor-specific scan, counter and list-append behaviour that decisions/layers.md keeps out of a Path A contract, and their downstream callers read raw AttributeValue shapes), but it surfaced that TASK-37.1 and TASK-38 were both planned against a Protocol that cannot serve them. Both now depend on TASK-27.2. TASK-27.1 is pulled forward because its blast radius is currently zero and only grows.
---

created: 2026-09-24 20:09
---
2026-09-24 alignment with decisions/plugin-architecture.md: the StorageService Protocol moves to app/contracts/ after TASK-27.1 (TASK-108). The fake contract now covers hosting contracts and capability api.py Protocols. Former AC#5 (storage package shape with a cached factory.py provider) is dropped, because the service registry (TASK-109) replaces cached provider functions. decisions/layers.md references in the children read as decisions/plugin-architecture.md.
---
<!-- COMMENTS:END -->
