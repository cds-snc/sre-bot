---
id: TASK-27.2
title: >-
  Storage slice 2: atomic update, numeric increment and bounded list, landing
  with their first consumer
status: To Do
assignee: []
created_date: '2026-09-16 13:58'
updated_date: '2026-09-24 20:11'
labels:
  - infrastructure
  - phase-4
  - portability
milestone: m-4
dependencies:
  - TASK-27.1
references:
  - decisions/webhooks.md
  - app/modules/slack/webhooks.py
  - decisions/plugin-architecture.md
parent_task_id: TASK-27
priority: high
ordinal: 220000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2 of TASK-27 (see the coordinator plan). Adds the write and read operations the storage capability is missing, and lands them WITH their first real consumer rather than ahead of it (decisions/layers.md: Path A capabilities are never built speculatively).

WHY. The Protocol today is put, put_if_not_exists, get, query and delete. TASK-37.1 has to give the WebhookStore increment_invocation and increment_acknowledged, and decisions/webhooks.md forbids doing that as a read-modify-write; it also has to serve list_all_webhooks and lookup_webhooks, which are full-table DynamoDB scans today. None of those has a vendor-neutral operation to sit on. This slice is therefore the actual blocker on TASK-37.1, and is why TASK-37.1 depends on it.

OPERATIONS
- Atomic single-attribute update (set one attribute on an existing item).
- Atomic numeric increment (add a delta to a counter attribute, returning the new value if the caller needs it). Two-provider check: DynamoDB ADD or SET x = x + :inc, Cosmos patch increment, Redis INCR, Postgres UPDATE ... SET x = x + 1. Passes.
- Bounded full-table list, with an explicit item cap and a documented rationale for the cap, for small configuration-sized tables such as webhooks. Client-side filtering belongs to the caller; a vendor filter expression must not appear in the signature.

SEQUENCING. Merge this immediately before TASK-37.1, or in the same PR if the size gate allows, so no operation lands without a consumer. If TASK-37.1 slips, this slice waits with it.

NOT IN SCOPE. Appending to a list attribute (modules/incident/db_operations.py log_activity uses DynamoDB list_append on an incident logs attribute). That is not a capability-shaped operation, it is a data-model problem: activity log entries almost certainly want to be their own items under the incident partition rather than an unbounded list attribute on one item. The decision belongs to TASK-38 planning, not to the storage Protocol. Also out of scope: the atomic multi-item conditional write TASK-83.2 owns.

CONDITIONS FROM SLICE 1. gt and between sort-key conditions are still gated on a real consumer; if TASK-37.1 or a co-landing consumer needs one, add it here with that justification recorded.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 StorageService exposes an atomic single-attribute update and an atomic numeric increment; neither is implemented as a read-modify-write in any backend or in the fake, and decisions/webhooks.md counter rule is satisfied
- [ ] #2 StorageService exposes a bounded full-table list with an explicit documented cap; no vendor filter expression, projection or scan parameter appears in any Protocol signature
- [ ] #3 Each operation added here has a named first consumer merged with it or immediately after it, and the two-plausible-provider justification required by decisions/layers.md is recorded in notes
- [ ] #4 The in-memory fake implements the new operations with the same semantics and the conformance suite covers them against both the fake and the moto-backed DynamoDB implementation, including a concurrent-increment case
- [ ] #5 Appending to a list attribute is explicitly NOT added to the Protocol; the note recording why, and pointing the incident activity log at TASK-38, is on this task
- [ ] #6 ruff, mypy (no new errors) and pytest tests --ignore=tests/smoke pass, with the commands and their output recorded in notes
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-24 20:11
---
2026-09-24 citation fix: decisions/layers.md, capability-packages.md and events.md were deleted and replaced by decisions/plugin-architecture.md (six layers: server, features, capabilities, infrastructure, integrations, contracts). Read those references in this task as plugin-architecture.md. Path A infrastructure capabilities are now split: hosting contracts (storage, coordination, queue, secrets) live in app/contracts/ with implementations in app/infrastructure/; workplace systems and shared business engines live in app/capabilities/. Path B adapters are unchanged (outbound-clients.md).
---
<!-- COMMENTS:END -->
