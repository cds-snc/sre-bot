---
id: TASK-1
title: >-
  Introduce typed ENVIRONMENT setting and remove PREFIX-derived environment
  logic
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
labels:
  - security
  - phase-0
milestone: m-0
dependencies: []
references:
  - decisions/configuration.md
  - decisions/security.md
priority: high
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/configuration.md (Environment identity). Today "is this production?" is derived as is_production = not bool(self.PREFIX) at app/infrastructure/configuration/app.py:17-20, and that one bit drives prod detection, CORS shape, dev-bypass, and SNS validation (SEC-10).

Steps:
1. Add ENVIRONMENT: Literal["local","ci","dev","staging","production"] to the app settings class in app/infrastructure/configuration/app.py, read from the ENVIRONMENT env var, no default that maps to production behavior in dev (default "local" is acceptable; deployment manifests must set it explicitly).
2. Find every place that derives environment from PREFIX (grep -rn "PREFIX" app/ --include="*.py") and replace each conditional with a read of the typed ENVIRONMENT field.
3. Add DEV_BYPASS_ENABLED: bool = False. Any dev-bypass code path must require BOTH environment != "production" AND DEV_BYPASS_ENABLED is true, and must log each use.
4. Set ENVIRONMENT in CI, local compose/env examples, and the ECS task definition (terraform/) so every runtime declares itself.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 App settings expose ENVIRONMENT as a Literal["local","ci","dev","staging","production"]; an invalid value fails boot with a pydantic validation error
- [ ] #2 grep -rn "PREFIX ==" app/ --include=*.py returns no environment-derivation hits (PREFIX may still exist for URL prefixing only)
- [ ] #3 Dev-bypass requires the two independent guards (non-production ENVIRONMENT and DEV_BYPASS_ENABLED=true) and logs each use
- [ ] #4 Unit tests cover: valid values accepted, invalid value rejected at boot, dev-bypass denied when either guard is off
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 All existing tests plus new tests pass locally
- [ ] #2 Deployment manifests (terraform/, CI) set ENVIRONMENT explicitly for each environment
- [ ] #3 PR references SEC-10 and decisions/configuration.md
<!-- DOD:END -->
