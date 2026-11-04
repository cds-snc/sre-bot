---
id: TASK-178
title: Shared provisioned and managed content plumbing
status: To Do
assignee: []
created_date: '2026-11-03T18:59:00Z'
updated_date: '2026-11-03T19:02:00Z'
labels:
  - content
milestone: m-7
dependencies:
  - TASK-145
  - TASK-165.4
  - TASK-167
references:
  - decisions/organisation-content.md
  - decisions/provisioned-content.md
  - decisions/managed-content.md
  - backlog/docs/doc-15 - Coordinated-incidents-delivery-map.md
type: feature
ordinal: 469000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Incident coordination and the other content consumers need one shared path for provisioned content and one validated, authorized managed-write path. No task currently owns the loaders, schema checks, audit/versioning, kill switch, and export compatibility as shared infrastructure. This is a separate task outside TASK-165; build it when the first consumer is ready, without adding consumer-specific policy to the shared plumbing.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Provisioned content is loaded from the agreed content root and validated at boot; the supported schemas are exported and checked in CI.
- [ ] #2 Managed writes are validated, authorized, versioned, audited, and protected by the per-kind kill-switch policy in managed-content.md.
- [ ] #3 Managed content can be exported to the provisioned format, with compatibility tests covering both paths.
- [ ] #4 Targeted tests cover invalid content, authorization, version history, audit, disabled writes, and export compatibility; the task is not closed while consumer-specific duplicate plumbing remains.
<!-- AC:END -->
