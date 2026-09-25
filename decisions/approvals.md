---
status: Accepted
date: 2026-07-28
applies: target
scope: The generic human-approval workflow capability shared by access, SaaS-subscription, and AI-key features.
---

# Approvals

## Context

Several features need the same shape: a human submits a request, one or more approvers decide, and on approval the system performs an effect in a managed system. Access grant and revoke ship this today, built inside `app/packages/access/request`. SaaS-subscription provisioning and AI-API-key issuance (the LiteLLM gateway) need the same lifecycle next.

That package holds two things at once:
- a domain-agnostic approval engine: lifecycle state machine, N-of-M threshold, separation of duties, audit trail, expiry, retry;
- access-specific policy and effect: approver resolution from IDP groups, entitlement rules, the Google Workspace membership write, the Access Sync propagation.

Current code:
- `access/request/store.py` persists the request aggregate through `infrastructure.storage.StorageService`, obtained from `get_storage_service()` in the feature's `providers.py`. Writes are plain puts, so two replicas can both advance the same request.
- `access/request/service.py` emits lifecycle events with `dispatch_background` on the blinker-backed in-process dispatcher. `access/sync` subscribes to `REQUEST_APPROVED`, and `access/request` subscribes to `SYNC_COMPLETED` and `SYNC_FAILED`, each by calling `register_handler` inside its `startup_warmup` hookimpl. A sync result raised on one replica reaches only that replica.
- No `ApprovalPolicy` or `EffectHandler` type exists yet.

Copying that package per workflow would triplicate the engine and its multi-replica bugs. The second and third consumers exist, so the engine becomes a capability ([plugin-architecture.md](plugin-architecture.md)).

## Decision

**The approval engine is a capability at `app/capabilities/approvals/`.** It is a domain-agnostic engine that features extend, not hosting code, so it does not live in `infrastructure/`.

**Public surface.** `api.py` exposes `start`, `submit_decision`, `get_state` and `cancel`, with the domain types they use. The capability's own hookspecs module is its extension point. Everything else in the package is private.

**The engine owns:** the lifecycle state machine (`pending_approval → approved → completed`, plus `rejected`, `cancelled`, `expired`, `failed` and the `failed → retry` loop), N-of-M counting, separation of duties, the per-transition audit trail, and expiry of stale pending requests. It stores an opaque, feature-owned `context` with each request and never interprets it.

**Each feature owns two strategies, registered through the extension point:**
- an `ApprovalPolicy`: who may approve, threshold, auto-approve rules, eligibility. It is pure and deterministic: same request and decisions in, same answer out, no I/O.
- an `EffectHandler`: the write to the managed system on `approved`. It is idempotent, keyed by request id, so a retry or a second replica never applies the effect twice.

The host calls the approvals hookspecs once at startup, before the capability initializes, and collects one policy and one effect handler per workflow type. At runtime the engine awaits their async methods; it never calls a pluggy hook per request.

**Storage.** The engine persists through the storage contract, resolved from the registry ([dependency-injection.md](dependency-injection.md)). It never imports `StorageService` or any `infrastructure` module. The single-partition aggregate (request, decisions and audit read in one query) moves from `access/request` into the engine unchanged.

**Once-only transitions.** Every automatic transition (threshold met → `approved`, effect result → `completed` or `failed`) is a conditional write through the coordination contract: it advances only from the expected prior state ([reliability.md](reliability.md)). Together with idempotent effects, this stops two replicas from provisioning twice.

**Cross-package continuation goes through the queue contract.** When an effect's outcome returns from another package (the Access Sync result advancing an access request), it arrives as a durable message on the queue contract, written with a transactional outbox once that contract is built. It never rides an in-process event: an event reaches only the replica that raised it.

**Settings.** The engine reads its own slice at `capabilities/approvals/settings.py`; per-workflow policy values (thresholds, TTL) are the owning feature's settings ([configuration.md](configuration.md)).

**No external workflow engine yet. Structure is the trigger, not count.** Step Functions (task-token callbacks), Temporal (signals) and Camunda (BPMN user tasks) earn their operational cost when workflows are structurally complex: arbitrary multi-step graphs, per-step SLAs and escalation, visual execution history, replay. The three workflows in hand share one shape (single approval, then effect) with different thresholds and effects. Adopt an engine only when a workflow needs orchestration the in-house state machine cannot cheaply express, and record that as its own decision. The `api.py` surface and the strategy split are shaped so a durable-execution engine such as Temporal or DBOS can replace the state machine without changing any feature.

## Consequences

- One approval engine, tested once. A new workflow is a policy, an effect handler and one hookimpl, not a copied package.
- The access package shrinks to its domain: policy plus the IDP and sync effect.
- Features test against a fake storage contract and pure policies, without DynamoDB.
- Cost: extracting the engine refactors shipped code and must preserve `access/request`'s HTTP surface and audit semantics. It lands as a behaviour-preserving change before the new features build on it.
- Cost: continuation through a queue adds latency and an outbox relay compared with an in-process call.

## Checks

- `capabilities/approvals/` exposes `api.py` and a hookspecs module; features import only `api.py` (import-linter, [plugin-architecture.md](plugin-architecture.md)).
- No state-machine logic (status transitions, threshold counting, separation of duties) remains under `packages/` or `features/`; features contain only `ApprovalPolicy` and `EffectHandler` implementations and transport.
- Test: two concurrent threshold-meeting approvals produce one effect.
- Test: a policy called twice with the same input returns the same result; an effect handler called twice with the same request id applies once.
- grep: no `dispatch_background` or `register_handler` carries the sync-result step.
- Boot test: every registered workflow type has both a policy and an effect handler before the capability initializes.

## Migration

Tickets: TASK-60 to TASK-63 (engine extraction and the three consumers), TASK-58 (coordination contract), TASK-34 (queue contract and outbox).

Tolerated until closed:
- the approval engine inside `packages/access/request` (`service.py`, `store.py`, `policies.py`);
- `access/request/store.py` taking `StorageService` from `infrastructure.storage` through `get_storage_service()`;
- plain puts instead of conditional writes on state transitions;
- request and sync continuation over `dispatch_background` and `register_handler` on the in-process dispatcher.

**Changes:**
- 2026-09-24: Migration names epic tickets only; the engine becomes a capability with strategies collected at startup, storage and coordination contracts, and queue-based continuation.
