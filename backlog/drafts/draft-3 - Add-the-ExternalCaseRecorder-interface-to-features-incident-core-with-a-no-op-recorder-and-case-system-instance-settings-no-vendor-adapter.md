---
id: DRAFT-3
title: >-
  Add the ExternalCaseRecorder interface to features/incident/core with a no-op
  recorder and case-system instance settings; no vendor adapter
status: Draft
assignee: []
created_date: '2026-10-02 16:44'
labels:
  - incident
  - later-wave
dependencies:
  - TASK-38.8
references:
  - decisions/incident-management.md
  - decisions/outbound-clients.md
parent_task_id: TASK-97
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
EXPANSION (after doc-2). decisions/incident-management.md, "The optional external platform". This task builds the seam only:
- ExternalCaseRecorder in core/api.py: open a case for an incident and return an ExternalCaseReference; update it (status, severity, title); add an entry (timeline, note, report link); close it. All return OperationResult.
- A no-op recorder returned by the provider when no case-system instance is configured; the record's external-case reference stays empty and nothing is rendered.
- Settings: common/settings.py lists zero or more case-system instances (system, instance name, base URL, secret reference) and the new-incident policy names which instance new incidents use (default: the only one).
- lifecycle calls the recorder at declare, on status change and on close; retrospective adds an entry when a retro is scheduled. With the no-op recorder every call succeeds without I/O.
No vendor client, no adapter, no inbound path. Those are the next drafts.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 ExternalCaseRecorder is exposed by core/api.py with OperationResult returns; the provider returns the no-op recorder when no instance is configured, and a boot test proves the feature works in full that way
- [ ] #2 Case-system instances are configuration with per-instance secret references; nothing selects a platform by a global flag; which instance an incident uses is its stored reference
- [ ] #3 lifecycle and retrospective call the recorder at the points listed; with the no-op recorder no outbound call is made
<!-- AC:END -->
