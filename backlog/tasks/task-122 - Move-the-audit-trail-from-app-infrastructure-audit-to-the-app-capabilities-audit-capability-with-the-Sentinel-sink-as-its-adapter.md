---
id: TASK-122
title: >-
  Move the audit trail from app/infrastructure/audit/ to the
  app/capabilities/audit/ capability, with the Sentinel sink as its adapter
status: To Do
assignee: []
created_date: '2026-09-24 20:00'
labels:
  - plugin-architecture
  - capabilities
  - audit
milestone: m-7
dependencies:
  - TASK-106
  - TASK-108
  - TASK-109
  - TASK-114
references:
  - decisions/plugin-architecture.md
  - decisions/cloud-portability.md
  - decisions/observability.md
priority: medium
type: task
ordinal: 264000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/plugin-architecture.md lists the audit trail among the shared business capabilities (with approvals, notifications, people and workplace systems), and its Migration moves audit to app/capabilities/. Today app/infrastructure/audit/ holds AuditEvent and AuditTrailService on StorageService. integrations/sentinel imports infrastructure.audit.models, one of the integrations -> infrastructure imports import-linter must eventually reject.

Scope:
- create app/capabilities/audit/ with api.py (the Protocol, AuditEvent and the provider function), store.py persisting through the storage contract resolved from the registry, an in-memory fake, and a README with its classification and feature consumers;
- repoint every consumer;
- delete app/infrastructure/audit/ with no re-export.
The Sentinel sink moves out of integrations/sentinel into this capability's adapters/ under TASK-25.7, which depends on this ticket. This takes over the audit part of TASK-27.3.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/capabilities/audit/ exposes api.py and persists through the storage contract; its README states the classification and feature consumers
- [ ] #2 An in-memory fake of the audit Protocol lives in the package and is exercised by tests; the write_audit_event monkeypatch doubles are replaced by it
- [ ] #3 app/infrastructure/audit/ is deleted with no re-export; grep finds no import of the old path
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
