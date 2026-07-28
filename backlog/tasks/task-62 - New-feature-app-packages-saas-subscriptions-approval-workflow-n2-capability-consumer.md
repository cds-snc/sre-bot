---
id: TASK-62
title: >-
  New feature: app/packages/saas-subscriptions approval workflow (n=2 capability
  consumer)
status: To Do
assignee: []
created_date: '2026-07-28 14:33'
labels:
  - packages
  - approvals
  - phase-4
milestone: m-4
dependencies:
  - TASK-60
references:
  - decisions/approvals.md
  - decisions/feature-packages.md
priority: medium
ordinal: 92000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/approvals.md and decisions/feature-packages.md. New feature package app/packages/saas-subscriptions that manages manual SaaS subscription requests as an approval workflow, built entirely on the generic ApprovalWorkflowService capability (infrastructure/approvals). This is the n=2 consumer that validates the capability generalizes beyond access grants.

Desired end state:
1. app/packages/saas-subscriptions is a plugin-registerable feature (pyproject entry-point, lifespan/hookspec registration; no import-time side effects).
2. It provides only its ApprovalPolicy (who approves a subscription request, thresholds, separation-of-duties) and EffectHandler (record/provision the approved subscription); it adds NO generic workflow machinery.
3. Pydantic models only at the HTTP/webhook boundary; frozen dataclasses for internal entities; infrastructure reached via provider/dependency aliases, never concrete imports.
4. Route coverage includes success and error-mapping paths per the fastapi-api-patterns and testing standards.

Depends on the approvals capability extraction. The task-planner agent must scope this to a single reviewable PR or decompose it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/packages/saas-subscriptions is plugin-registerable via pyproject entry-point with no import-time side effects
- [ ] #2 It provides only its ApprovalPolicy + EffectHandler; no generic workflow machinery is added
- [ ] #3 Pydantic only at the I/O boundary, frozen dataclasses internally, infrastructure reached via provider/dependency aliases
- [ ] #4 Route coverage includes success and error-mapping paths
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 The approvals capability is consumed unchanged (validates n=2 generalization)
- [ ] #2 PR references decisions/approvals.md
<!-- DOD:END -->
