---
id: TASK-60
title: >-
  Extract the generic human-approval workflow capability into
  app/infrastructure/approvals/
status: To Do
assignee: []
created_date: '2026-07-28 14:33'
updated_date: '2026-07-28 14:40'
labels:
  - infrastructure
  - phase-4
  - approvals
milestone: m-4
dependencies:
  - TASK-27
  - TASK-58
references:
  - decisions/approvals.md
  - decisions/layers.md
  - 'https://github.com/cds-snc/sre-bot/issues/1368'
priority: high
ordinal: 90000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
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
- [ ] #1 app/infrastructure/approvals/ owns the generic engine (state machine, N-of-M thresholds, separation-of-duties, immutable audit, TTL/expiry) with no access-specific logic
- [ ] #2 ApprovalWorkflowService Protocol has an in-memory fake exercised by the test suite and a DynamoDB-backed implementation via StorageService
- [ ] #3 Once-only automatic transitions use the ConditionalWriteStore primitive so parallel replicas never double-advance
- [ ] #4 Cross-package effect steps are handed off over the outbox/QueueService, never executed inline
- [ ] #5 Features inject ApprovalPolicy + EffectHandler strategies; the engine holds no domain logic
- [ ] #6 ApprovalsSettings is a partitioned settings slice; the service receives only its slice
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Existing access-request flow behavior is preserved end to end with tests green
- [ ] #2 PR references decisions/approvals.md
<!-- DOD:END -->
