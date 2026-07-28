---
id: TASK-63
title: >-
  New feature: app/packages/ai-keys LiteLLM gateway key-request approval
  workflow (n=3 consumer)
status: To Do
assignee: []
created_date: '2026-07-28 14:33'
updated_date: '2026-07-28 14:41'
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
  - 'https://github.com/cds-snc/sre-bot/issues/1371'
priority: medium
ordinal: 93000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/approvals.md and decisions/feature-packages.md. New feature package app/packages/ai-keys that manages AI gateway (LiteLLM) API-key issuance requests as an approval workflow, built on the generic ApprovalWorkflowService capability (infrastructure/approvals). This is the n=3 consumer confirming the capability is genuinely domain-agnostic; its EffectHandler integrates with the internally managed LiteLLM AI gateway.

Desired end state:
1. app/packages/ai-keys is a plugin-registerable feature (pyproject entry-point, lifespan/hookspec registration; no import-time side effects).
2. It provides only its ApprovalPolicy (who approves an AI key request, thresholds, SoD) and EffectHandler (provision/rotate/revoke the key via the LiteLLM gateway through a thin app/integrations client); no generic workflow machinery lives here.
3. The LiteLLM gateway is reached through a thin outbound integration client (integrations layer) behind the effect strategy, never called directly from route/business code.
4. Pydantic only at the I/O boundary; frozen dataclasses internally; route coverage includes success and error-mapping paths.

Depends on the approvals capability extraction. The task-planner agent must scope this to a single reviewable PR or decompose it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/packages/ai-keys is plugin-registerable via pyproject entry-point with no import-time side effects
- [ ] #2 It provides only its ApprovalPolicy + EffectHandler; no generic workflow machinery is added
- [ ] #3 The LiteLLM gateway is reached through a thin integrations-layer client behind the effect strategy, never from route/business code
- [ ] #4 Pydantic only at the I/O boundary, frozen dataclasses internally; route coverage includes success and error-mapping paths
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 The approvals capability is consumed unchanged (validates n=3 generalization)
- [ ] #2 PR references decisions/approvals.md
<!-- DOD:END -->
