---
id: TASK-53
title: >-
  Move the system endpoints from app/api/ into app/server/ and route every
  feature endpoint to its owning surface rebuild
status: To Do
assignee: []
created_date: '2026-07-27 16:07'
updated_date: '2026-09-24 20:06'
labels:
  - architecture
  - layers
milestone: m-5
dependencies:
  - TASK-36
  - TASK-92
references:
  - decisions/feature-packages.md
  - 'https://github.com/cds-snc/sre-bot/issues/1357'
  - decisions/migration.md
  - decisions/platform-transports.md
priority: medium
ordinal: 81000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Rescoped 2026-09-24. The architecture decision this ticket used to ask for is made: decisions/migration.md's directory table says app/api/ is the legacy HTTP surface, feature routes move to their owning packages, and system endpoints (health, version, landing) move to server/. HTTP is the app's own protocol and its inbound boundary is FastAPI and ASGI middleware in app/server/ (decisions/platform-transports.md). decisions/layers.md, which the old text cited, is deleted.

Scope:
1. Move the feature-agnostic system endpoints (GET /health, GET /version, the landing page, favicon) into app/server/, with success and error-path route tests. Keep them consistent with the readiness and liveness contract decided by TASK-92 and decisions/health-checks.md.
2. List every feature route under app/api/v1/routes/ with the rebuild ticket that moves it (for example the webhook routes with TASK-37.4). The TASK-36 inventory carries this; routes are not moved ahead of their surface.
3. Delete app/api/ once the last route has moved.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Health, version, landing and favicon endpoints are served from app/server/ with success and error-path route tests
- [ ] #2 Every remaining app/api/ route is assigned to a rebuild ticket in the TASK-36 inventory
- [ ] #3 app/api/ is deleted once its last route has moved, and api is removed from the import-linter root packages
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
