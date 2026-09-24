---
id: TASK-118
title: >-
  Put the translator contract in app/contracts/ and its implementation, on the
  chosen library, in app/server/i18n/
status: To Do
assignee: []
created_date: '2026-09-24 20:00'
labels:
  - plugin-architecture
  - i18n
milestone: m-7
dependencies:
  - TASK-117
  - TASK-107
  - TASK-109
  - TASK-72
references:
  - decisions/i18n.md
  - decisions/plugin-architecture.md
priority: medium
type: feature
ordinal: 260000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/i18n.md: i18n is a framework service. The translator contract lives in app/contracts/, its implementation is host code in app/server/, and features and capabilities depend only on the contract. Catalogues stay in each feature's locales/ and register at startup through the hookspec in contracts (moved by TASK-107).

Today features import TranslationService, Translator, TranslationKey and Locale from app/infrastructure/i18n/ (access, geolocate, incident_draft, incident_summary), as do integrations/slack (moved by TASK-26.2) and server/lifespan.

Scope:
- define the translator contract;
- implement it in app/server/i18n/ on the library chosen by the decision ticket;
- register it in the service registry;
- repoint every importer;
- delete app/infrastructure/i18n/ with no re-export.
Legacy modules on python-i18n and app/locales/ are untouched; they retire with their surfaces (TASK-41). Depends on TASK-72 so the live memory bug is fixed in the current stack rather than waiting for the rewrite.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The translator contract lives in app/contracts/; no feature, capability or integration imports server.i18n or infrastructure.i18n
- [ ] #2 The implementation in app/server/i18n/ uses the library chosen by the decision ticket; app/infrastructure/i18n/ is deleted with no re-export
- [ ] #3 Every existing feature catalogue loads unchanged and renders the same EN and FR strings (tests)
- [ ] #4 Locale resolves per request from contextvars at the inbound boundary
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
