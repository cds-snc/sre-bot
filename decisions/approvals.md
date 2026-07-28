---
status: Accepted
date: 2026-07-28
applies: target
scope: The generic human-approval workflow capability shared by access, SaaS-subscription, and AI-key features.
---

# Approvals

## Context

Several features need the same shape: a human submits a request, one or more approvers decide, and on approval the system performs an effect in a managed system. Access grant/revoke ships this today, built *inside* `app/packages/access/request`; SaaS-subscription provisioning and AI-API-key issuance (the new LiteLLM gateway) need the identical lifecycle imminently. That package accidentally holds two things at once: a **domain-agnostic approval engine** (lifecycle state machine, N-of-M threshold, separation-of-duties, immutable audit trail, TTL/expiry, retry) and **access-specific policy + effect** (approver resolution from IDP groups, entitlement rules, the Google Workspace membership write, the Access Sync propagation). Copying that package per new workflow would triplicate the engine and its latent multi-replica bugs. The second and third consumers have now arrived, so the promotion rule in [feature-packages.md](feature-packages.md) fires — the generic part belongs in infrastructure.

## Decision

**A generic approval-workflow capability in `app/infrastructure/approvals/`**, exposed as an `ApprovalWorkflowService` Protocol with a provider function and an in-memory fake — a Path A capability under [cloud-portability.md](cloud-portability.md) #4. The engine owns the vendor-neutral machinery; each feature owns what its requests *mean* and *do*.

- **The engine owns (domain-agnostic):** the lifecycle state machine (`pending_approval → approved → completed`, plus `rejected` / `cancelled` / `expired` / `failed` and the `failed → retry` loop), N-of-M approval counting, separation-of-duties, the immutable per-transition audit trail, and TTL/expiry of stale pending requests. It stores an **opaque, feature-owned `context`** alongside the generic record and never interprets it.
- **Each feature owns (injected strategy Protocols):** an `ApprovalPolicy` (who may approve, threshold, auto-approve rules, eligibility) and an `EffectHandler` (the write to the managed system on `approved`). These live in the feature package; the access effect (IDP write + sync) is a Path B adapter per [layers.md](layers.md).
- **Persistence:** DynamoDB via `StorageService`; the single-partition aggregate (request + decisions + audit read in one query) already in `access/request` moves into the engine unchanged.
- **Once-only transitions:** every *automatic* transition (threshold-met `→ approved`, effect result `→ completed` / `failed`) is a **conditional write** on the coordination store ([reliability.md](reliability.md)) — advance only from the expected prior state — and the effect is idempotent, so two replicas cannot double-provision. This closes a latent double-effect bug that today's plain `put` hides at low volume.
- **Cross-package steps ride the queue.** Where an effect's outcome returns from another package (the Access Sync result advancing the request), it arrives as a **durable step over the outbox / `QueueService`** ([reliability.md](reliability.md)), not the in-process dispatcher ([events.md](events.md)) — the step is workflow continuation, not a notification.
- **Registration & settings:** each consuming feature registers via pluggy ([plugins.md](plugins.md)); the engine reads a partitioned `ApprovalsSettings` ([configuration.md](configuration.md)); per-workflow policy (thresholds, TTL) is feature settings.

**No external workflow engine yet — and count is not the trigger, structure is.** Step Functions (wait-for-callback task token), Temporal (signals), and Camunda (BPMN user tasks) are the managed-service category for durable human approval, and they earn their operational cost when workflows are *structurally* complex: arbitrary multi-step DAGs, per-step SLAs / escalation, visual execution history, or replay. The three workflows in hand are the **same single-approval-then-effect shape** at different thresholds and effects — not three different orchestrations. Adopt an engine only when a workflow needs orchestration the in-house state machine cannot cheaply express, and record *that* as its own decision (with the Path A fake tradeoff — a faithful in-memory fake of Temporal/Step Functions semantics is not cheap, and a port thin enough to fake discards most of what the engine is for).

## Consequences

- One approval engine, tested once; a new workflow is a policy + effect + one entry-point line, not a copied package.
- The access package shrinks to its actual domain — policy plus the IDP/sync effect — and the two new features start on a proven capability.
- The engine is a genuine Path A capability with an in-memory fake, so new workflows' tests seed it instead of standing up DynamoDB.
- Cost, accepted: extracting the engine is a real refactor of shipped code that must preserve `access/request`'s HTTP surface and audit semantics; it lands as its own behavior-preserving PR *before* the two new features build on it.

## Checks

- `app/infrastructure/approvals/` exposes an `ApprovalWorkflowService` Protocol + provider + in-memory fake exercised by tests (Path A fake contract, [cloud-portability.md](cloud-portability.md)).
- No approval state-machine logic (status transitions, threshold counting, separation-of-duties) remains under `app/packages/` — features contain only `ApprovalPolicy` / `EffectHandler` implementations and transport.
- Automatic transitions go through the conditional-write path (test: two concurrent threshold-meeting approvals → one effect); effects are idempotent.
- grep: no `dispatch_background` for the sync-result → advance step; it rides the queue/outbox.

## Migration

Tickets: extract the generic engine to `infrastructure/approvals/` behind `ApprovalWorkflowService` + fake; refactor `access/request` onto `ApprovalPolicy` / `EffectHandler` strategies (behavior-preserving); route the Access Sync result step onto the outbox / `QueueService` (this folds in the events-review `SYNC_COMPLETED` reclassification); then build `saas-subscriptions` and `ai-keys` on the capability. Tolerated until closed: the approval machinery living inside `access/request`; the sync-result advance on `dispatch_background`.
