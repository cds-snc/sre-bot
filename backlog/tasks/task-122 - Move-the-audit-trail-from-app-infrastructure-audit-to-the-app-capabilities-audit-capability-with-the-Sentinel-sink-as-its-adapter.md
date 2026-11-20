---
id: TASK-122
title: >-
  Move the audit trail from app/infrastructure/audit/ to the
  app/capabilities/audit/ capability, with the Sentinel sink as its adapter
status: To Do
assignee: []
created_date: 2026-09-24 20:00
updated_date: '2026-11-20T22:05:00Z'
labels:
  - plugin-architecture
  - capabilities
  - audit
milestone: m-7
dependencies:
  - TASK-106
  - TASK-108
  - TASK-109
  - TASK-114.2
references:
  - decisions/plugin-architecture.md
  - decisions/cloud-portability.md
  - decisions/observability.md
  - https://github.com/cds-snc/sre-bot/issues/1665
priority: medium
type: task
ordinal: 264000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/plugin-architecture.md lists the audit trail among the shared business capabilities (with approvals, notifications, people and workplace systems), and its Migration moves audit to app/capabilities/. Today app/infrastructure/audit/ holds AuditEvent and AuditTrailService on RecordStore. integrations/sentinel imports infrastructure.audit.models, one of the integrations -> infrastructure imports import-linter must eventually reject.

Scope:
- create app/capabilities/audit/ with api.py (the Protocol, AuditEvent and the provider function), store.py persisting through the records contract resolved from the registry, an in-memory fake, and a README with its classification and feature consumers;
- repoint every consumer;
- delete app/infrastructure/audit/ with no re-export.
The Sentinel sink moves out of integrations/sentinel into this capability's adapters/ under TASK-25.7, which depends on this ticket. This takes over the audit part of TASK-27.3.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/capabilities/audit/ exposes api.py and persists through the records contract; its README states the classification and feature consumers
- [ ] #2 An in-memory fake of the audit Protocol lives in the package and is exercised by tests; the write_audit_event monkeypatch doubles are replaced by it
- [ ] #3 app/infrastructure/audit/ is deleted with no re-export; grep finds no import of the old path
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
- [ ] #5 The adapter and the in_memory.py fake explicitly subclass the api.py Protocol; the AuditTrailService line is removed from app/bin/baselines/fake_coverage.txt and make check-fake-coverage passes
- [ ] #6 If no earlier cross-area capability built it, this task adds the [plugins.shared] enablement table (plugins.md, product-scope.md, 2026-11-06) and puts the audit capability's key there
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-20T22:04:00Z

---

2026-11-20 (human, TASK-145.10 program-scope rulings): the AuditEvent shape this capability exposes follows the new audit event catalogue task (which events, actor/action/target/outcome/time/request_id). Consumers to repoint include features/incident/response/adapters/sentinel.py and features/incident/postmortem/adapters/sentinel.py.

---

created: 2026-11-20T22:05:00Z

---

2026-11-20: the audit event catalogue task is TASK-191 (depends on TASK-171); this task's AuditEvent adopts its shape.

---
<!-- COMMENTS:END -->
