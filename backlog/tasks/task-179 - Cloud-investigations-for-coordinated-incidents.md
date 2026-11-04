---
id: TASK-179
title: Cloud investigations for coordinated incidents
status: To Do
assignee: []
created_date: '2026-11-03T18:59:00Z'
updated_date: '2026-11-03T19:02:00Z'
labels:
  - incident
  - investigations
milestone: m-7
dependencies:
  - TASK-145
references:
  - large-scale-incident-analysis.md
  - decisions/security.md
  - backlog/docs/doc-15 - Coordinated-incidents-delivery-map.md
type: feature
ordinal: 472000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Cloud investigations are a downstream, nice-to-have sibling to TASK-165. Start with a standalone investigation capability that can run outside an incident, then add incident engagement hooks only after the standalone boundary is proven. Keep agents read-only and use only confirmed, unclassified briefs; findings are reviewed inputs, never automatically published.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A new decisions/investigations.md records the security and data-classification boundary, supported provider choice, and human review requirements before implementation.
- [ ] #2 A standalone investigation can be initiated outside an incident and reports progress and findings through its typed capability contract.
- [ ] #3 The first provider is AWS DevOps Agent only where account coverage and security approval exist; future providers remain out of scope until their APIs and controls are assessed.
- [ ] #4 Agents cannot mutate cloud resources, and findings are never relayed or published as-is without human review.
- [ ] #5 An incident can optionally reference an investigation and relay permitted milestones across its bound surfaces without weakening embargo or membership checks.
<!-- AC:END -->
