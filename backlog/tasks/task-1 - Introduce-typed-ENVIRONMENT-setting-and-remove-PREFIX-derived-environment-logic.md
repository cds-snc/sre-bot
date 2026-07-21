---
id: TASK-1
title: >-
  Introduce typed ENVIRONMENT setting and remove PREFIX-derived environment
  logic
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-21 18:57'
labels:
  - security
  - phase-0
milestone: m-0
dependencies: []
references:
  - decisions/configuration.md
  - decisions/security.md
  - 'https://github.com/cds-snc/sre-bot/issues/1254'
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
- [ ] #5 CI guardrail enforces that AppSettings.PREFIX is read only by its definition and the explicitly whitelisted legacy readers (app/modules/** command registration plus documented pre-existing exceptions), with a committed regression test (TASK-1.3)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
This task is decomposed into two subtasks due to the single-PR size gate (3 subsystems crossed: app Python code + terraform + CI; additive change mixed with behavior change).

Subtask execution order (enforced by dependency wiring):
1. TASK-1.1 — Add ENVIRONMENT + DEV_BYPASS_ENABLED to AppSettings; update all deployment configs (purely additive, no behavior change)
2. TASK-1.2 — Migrate all environment checks from PREFIX/is_production to ENVIRONMENT; enforce dual dev-bypass guard; remove is_production shim

TASK-1 ACs are satisfied when both subtasks are done:
- AC #1 → TASK-1.1 (field added, validation enforced)
- AC #2 → TASK-1.2 (all PREFIX env-derivation replaced)
- AC #3 → TASK-1.2 (dual guard enforced in current_user.py)
- AC #4 → TASK-1.1 + TASK-1.2 (unit tests in both slices)
- DoD #2 → TASK-1.1 (manifests updated)
- DoD #3 → TASK-1.2 PR description must reference SEC-10 and decisions/configuration.md
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @planner
created: 2026-07-17 16:15
---
AC #2 grep scope is narrower than the actual call-site surface. Current grep target (PREFIX ==) misses: PREFIX !=, bool(PREFIX), if app_settings.PREFIX: (truthy check). TASK-1.2 will target all four forms. Suggest widening AC #2 to: grep -rn 'PREFIX' app/ --include='*.py' and manually excluding URL-prefix uses, OR replacing with: grep -rn 'is_production' app/ --include='*.py' returns no hits (TASK-1.2 AC #1 already covers this). Human approval needed before AC #2 wording is changed.
---

author: @planner
created: 2026-07-21 18:57
---
Residual gap found while closing out TASK-1: after TASK-1.2.3, AppSettings.PREFIX carries no environment meaning but is unbounded/undocumented and unverifiable in CI, so AC #2 could not close cleanly (a grep-based one-off check isn't regression-proof). Verified via grep -rn PREFIX app/ --include=*.py and grep -rn is_production app/ --include=*.py: is_production is fully gone; PREFIX now only read by app/infrastructure/configuration/app.py (definition), its pre-existing mirror in app/infrastructure/configuration/settings.py, a diagnostic log in app/server/lifespan.py, and the 6 frozen Slack command-namespace readers in app/modules/{atip,aws,incident,role,secret,sre} (plus a stale docstring in app/modules/dev/__init__.py). Created TASK-1.3 (parent TASK-1, depends on TASK-1.2) to: annotate PREFIX's field description, add a committed CI/grep guardrail script enforcing this whitelist, and add a regression test. Added TASK-1 AC #5 below to track closure. Plan written to TASK-1.3 via --plan; awaiting human review before implementation. Out of scope for TASK-1.3 (deferred to the follow-up Slack COMMAND_PREFIX task per decisions/transport-slack.md): COMMAND_PREFIX, app/infrastructure/slack/settings.py, retiring platforms.py.
---
<!-- COMMENTS:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 All existing tests plus new tests pass locally
- [ ] #2 Deployment manifests (terraform/, CI) set ENVIRONMENT explicitly for each environment
- [ ] #3 PR references SEC-10 and decisions/configuration.md
<!-- DOD:END -->
