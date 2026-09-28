---
id: TASK-105.3
title: >-
  Clear the mypy errors from the optional OperationResult message and float
  retry_after at call sites
status: To Do
assignee: []
created_date: '2026-09-28 15:36'
updated_date: '2026-09-28 15:52'
labels:
  - plugin-architecture
  - operation-result
milestone: m-7
dependencies:
  - TASK-105.1
references:
  - decisions/operation-result.md
parent_task_id: TASK-105
priority: medium
ordinal: 289000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TASK-105 widened OperationResult.message to str | None (optional on SUCCESS) and retry_after to float | None, per decisions/operation-result.md. It left 29 new mypy errors in 16 files it did not touch. CI does not block on them because lint-ci runs mypy with || true, but the repo got worse. Every error comes from forwarding an upstream result's message or retry_after into a narrower type:
- 27 are message: str | None passed to OperationResult.error(message=...) or to exception constructors that take str: infrastructure/{directory,drive,spreadsheets}/google.py, packages/incident_draft/service.py (these four are also edited by TASK-105.1, which may remove some of the sites), packages/access/{catalog/service.py, request/interactions/http.py, sync/desired_state.py, sync/adapters/aws_identity_center.py, sync/adapters/fake_platform.py}, modules/{aws/identity_center.py, incident/incident_folder.py, permissions/handler.py, provisioning/groups.py, provisioning/users.py}.
- 2 are retry_after: float | None passed to IncidentStoreUnavailableError / WebhookStoreUnavailableError typed int | None: modules/incident/db_operations.py, modules/slack/webhooks.py.
Measure the list again after TASK-105.1 lands, then fix each site at its own boundary without changing runtime behaviour on error paths.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 mypy reports no arg-type error caused by OperationResult.message being str | None or retry_after being float | None, checked by diffing mypy output against the pre-TASK-105 baseline
- [ ] #2 Runtime behaviour on error paths is unchanged: the fallback text is used only where message is None
- [ ] #3 ruff, lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-09-28, measured after TASK-105.1: 26 errors remain in 13 files. TASK-105.1 cleared infrastructure/{directory,drive,spreadsheets}/google.py and packages/incident_draft/service.py. Remaining: modules/{aws/identity_center.py (1), incident/db_operations.py (1, retry_after), incident/incident_folder.py (4), permissions/handler.py (1), provisioning/groups.py (2), provisioning/users.py (2), slack/webhooks.py (1, retry_after)}, packages/access/{catalog/service.py (1), request/interactions/http.py (1), sync/adapters/aws_identity_center.py (2), sync/adapters/fake_platform.py (1), sync/desired_state.py (8)}. 12 production files, 2 subsystems (legacy modules/, packages/access).
<!-- SECTION:NOTES:END -->
