---
id: TASK-60
title: >-
  Extract the generic human-approval workflow engine into the
  app/capabilities/approvals/ capability
status: To Do
assignee: []
created_date: '2026-07-28 14:33'
updated_date: '2026-09-24 20:07'
labels:
  - infrastructure
  - phase-4
  - approvals
  - plugin-architecture
milestone: m-7
dependencies:
  - TASK-27
  - TASK-58
  - TASK-106
  - TASK-108
  - TASK-109
  - TASK-110
  - TASK-113
  - TASK-114
references:
  - decisions/approvals.md
  - 'https://github.com/cds-snc/sre-bot/issues/1368'
  - decisions/plugin-architecture.md
priority: high
ordinal: 90000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ON HOLD, rescoped 2026-09-24 (decisions/plugin-architecture.md Migration: 'hold TASK-60 and rescope it to capabilities/approvals/'). The approval engine is a capability at app/capabilities/approvals/, not app/infrastructure/approvals/. It is a domain-agnostic engine that features extend, not hosting code (decisions/approvals.md). The hold is encoded as dependencies: contracts (TASK-106), the storage contract (TASK-108), the service registry (TASK-109), entry-point loading (TASK-110), the extension-point phase (TASK-113, which lands in this series as its first consumer), the package generator (TASK-114), the coordination contract (TASK-58) and the storage redesign (TASK-27).

Target shape (decisions/approvals.md):
- api.py exposes start, submit_decision, get_state and cancel, plus their domain types; everything else is private.
- hookspecs.py is the extension point. Each workflow type registers one ApprovalPolicy (pure, deterministic, no I/O) and one EffectHandler (idempotent, keyed by request id), collected once at startup.
- The engine persists through the storage contract resolved from the registry and never imports infrastructure. Once-only transitions go through the coordination contract. Cross-package continuation arrives over the queue contract (TASK-34), never an in-process event.

The original description follows for context; where it names app/infrastructure/approvals/ or an ApprovalWorkflowService provider import, the target above wins.

Aligns with decisions/approvals.md. Extract the domain-agnostic human-approval workflow machinery out of app/packages/access/request into a shared capability at app/infrastructure/approvals/, behind an ApprovalWorkflowService Protocol with an in-memory fake (Path A per layers.md / cloud-portability.md). This is the enabling change for every future approval workflow (access grants, SaaS subscription requests, AI gateway API keys) and must not embed any access-specific policy.

Desired end state:
1. app/infrastructure/approvals/ owns the generic engine: the state machine (pending_approval -> approved -> completed, plus rejected / cancelled / expired / failed and failed -> retry), N-of-M approval thresholds, separation-of-duties enforcement, immutable audit trail, and TTL/expiry.
2. ApprovalWorkflowService Protocol is capability-shaped (submit / approve / reject / cancel / advance / query), with an in-memory fake exercised by the test suite and a DynamoDB-backed implementation via StorageService (TASK-27).
3. Automatic once-only transitions ride the conditional-write / ConditionalWriteStore primitive (TASK-58) so parallel replicas (desired_count=2) never double-advance.
4. Cross-package effect steps are handed off over the outbox / QueueService (TASK-34), never executed inline.
5. Features inject their own ApprovalPolicy (who must approve, thresholds, SoD) and EffectHandler (what to do once approved) strategies; the engine holds no domain logic.
6. ApprovalsSettings is a partitioned settings slice owned by the capability; the service receives only its slice.

Behavior-preserving for the existing access-request flow. The task-planner agent must assess whether this ships as one PR or is decomposed into safe incremental subtasks that keep access/request working throughout the migration.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/capabilities/approvals/ owns the generic engine (state machine, N-of-M thresholds, separation of duties, per-transition audit, expiry) with no access-specific logic; its README states the classification and feature consumers
- [ ] #2 api.py exposes start, submit_decision, get_state and cancel with their domain types; an in-memory fake of the approval store is exercised by tests, and the store persists through the storage contract resolved from the registry
- [ ] #3 Once-only automatic transitions use the coordination contract (ConditionalWriteStore), so parallel replicas never double-advance (test: two concurrent threshold-meeting approvals produce one effect)
- [ ] #4 Cross-package effect continuations are handed off over the queue contract, never executed inline and never through an in-process event
- [ ] #5 Features register ApprovalPolicy and EffectHandler strategies through app/capabilities/approvals/hookspecs.py, collected once at startup; a boot test fails when a workflow type lacks either
- [ ] #6 ApprovalsSettings is a partitioned settings slice at capabilities/approvals/settings.py; the service receives only its slice
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Existing access-request flow behavior is preserved end to end with tests green
- [ ] #2 PR references decisions/approvals.md
<!-- DOD:END -->
