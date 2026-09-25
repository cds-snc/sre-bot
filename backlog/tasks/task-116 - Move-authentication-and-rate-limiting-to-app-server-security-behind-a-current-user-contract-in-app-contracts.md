---
id: TASK-116
title: >-
  Move authentication and rate limiting to app/server/security/ behind a
  current-user contract in app/contracts/
status: To Do
assignee: []
created_date: '2026-09-24 20:00'
labels:
  - plugin-architecture
  - security
milestone: m-7
dependencies:
  - TASK-106
  - TASK-109
  - TASK-24
references:
  - decisions/plugin-architecture.md
  - decisions/security.md
  - decisions/configuration.md
priority: medium
type: task
ordinal: 258000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/plugin-architecture.md: auth is a framework service. Its implementation is host code in app/server/, and features see only the current-user contract in app/contracts/ (one of the core-service Protocols). Today app/infrastructure/security/ holds JWT validation, JWKSManager, get_current_user (a FastAPI dependency) and the rate limiter, imported by packages/access, api/ and server/.

Scope:
- define the current-user contract (an actor type plus a way to resolve it at an entry point) in app/contracts/;
- move the JWT, JWKS, dev-bypass and limiter implementation to app/server/security/, with its SecuritySettings slice (TASK-24);
- register it in the service registry;
- rewrite every importer; routes obtain the current user through the contract.
No behaviour change: issuer, audience, algorithm pinning and the dev-bypass double guard are preserved and covered by the existing tests. No re-export is left in infrastructure/.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A current-user contract and actor type live in app/contracts/; no feature or capability imports server.security or infrastructure.security
- [ ] #2 JWT/JWKS validation, the dev-bypass guard and the rate limiter live in app/server/security/ with the SecuritySettings slice; app/infrastructure/security/ is deleted with no re-export
- [ ] #3 Existing auth tests (issuer, audience, pinned algorithms, dev-bypass double guard, CORS) pass unchanged in behaviour
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
