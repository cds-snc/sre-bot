---
id: TASK-53
title: >-
  Deprecate top-level app/api/ and decide the home for feature-agnostic system
  endpoints
status: To Do
assignee: []
created_date: '2026-07-27 16:07'
labels:
  - architecture
  - layers
milestone: m-5
dependencies: []
references:
  - decisions/layers.md
  - decisions/feature-packages.md
priority: medium
ordinal: 81000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/layers.md sanctions only three tiers under app/ (packages -> infrastructure -> integrations) plus the server/ host and main.py. app/api/ is a fourth, undeclared top-level HTTP surface (api/router.py aggregating landing, system, and versioned v1 routers) that predates features owning their own routers per decisions/feature-packages.md.

Target state: as legacy modules migrate to feature packages (decisions/migration.md) and each feature owns its APIRouter, the feature-specific routes under app/api/v1/routes/ (geolocate, webhooks, ...) move into their owning packages. What remains are genuinely feature-agnostic, system-level endpoints - GET /health, GET /version (api/routes/system.py), the landing page, and favicon - which are not a feature and must not stay in a standalone top-level api/ package.

This task decides and records WHERE those residual app-level/system endpoints live (the host process app/server/ is the leading candidate, since it already owns composition, lifespan, and middleware), and deprecates app/api/ once its feature routes are relocated. A decisions/ note (or an addition to the layers.md non-tier-directories section) must capture the rule so future contributors do not add new endpoints to app/api/.

Needs a human-approved implementation plan (task-planner) before any code, per the single-PR size gate.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A decision record (layers.md non-tier-directories section or a dedicated note) states the target home for feature-agnostic system endpoints (health, version, landing, favicon) and that app/api/ is deprecated once feature routes are relocated
- [ ] #2 Feature-specific routes currently under app/api/v1/routes/ have a named migration destination in their owning feature package (documented, not necessarily executed here)
- [ ] #3 The residual system endpoints (GET /health, GET /version) have a concrete home decided (host app/server/ vs an infrastructure surface) with success + error-path route tests
- [ ] #4 No new top-level app/api/ package remains as a sanctioned location; the layers.md check enumerates api/ as transitional with this ticket
<!-- AC:END -->
