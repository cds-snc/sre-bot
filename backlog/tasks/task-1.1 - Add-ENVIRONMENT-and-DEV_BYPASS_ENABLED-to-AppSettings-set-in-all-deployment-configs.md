---
id: TASK-1.1
title: >-
  Add ENVIRONMENT and DEV_BYPASS_ENABLED to AppSettings; set in all deployment
  configs
status: To Do
assignee: []
created_date: '2026-07-17 16:14'
updated_date: '2026-07-17 16:15'
labels:
  - phase-0
milestone: m-0
dependencies: []
references:
  - decisions/configuration.md
  - decisions/security.md
parent_task_id: TASK-1
priority: high
ordinal: 45000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Expand phase for TASK-1. Purely additive: add ENVIRONMENT: Literal["local","ci","dev","staging","production"] = "local" and DEV_BYPASS_ENABLED: bool = False to AppSettings. Keep is_production as a forwarding shim (return self.ENVIRONMENT == "production") so all existing callers compile. Set ENVIRONMENT in terraform/templates/sre-bot.json.tpl (production) and .github/workflows/ci_code.yml (ci). No behavior change; shim preserves all existing logic.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 AppSettings.ENVIRONMENT is Literal["local","ci","dev","staging","production"] with default "local"; AppSettings(ENVIRONMENT="uat") raises pydantic ValidationError at construction
- [ ] #2 AppSettings.DEV_BYPASS_ENABLED: bool = False by default
- [ ] #3 is_production property kept as forwarding shim: return self.ENVIRONMENT == "production"
- [ ] #4 terraform/templates/sre-bot.json.tpl has ENVIRONMENT=production entry in environment array
- [ ] #5 .github/workflows/ci_code.yml has ENVIRONMENT: ci in the test step env block
- [ ] #6 All existing tests pass; new unit tests cover valid enum values accepted, invalid value rejected at boot, DEV_BYPASS_ENABLED default, shim correctness
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Ordered steps — all changes are purely additive; is_production shim preserves every existing caller.

Step 1 — app/infrastructure/configuration/app.py
  - Add `from typing import Literal` import
  - Add field: ENVIRONMENT: Literal["local","ci","dev","staging","production"] = "local"
  - Add field: DEV_BYPASS_ENABLED: bool = False
  - Update is_production property body: return self.ENVIRONMENT == "production"
  - No other changes; lru_cache singleton provider unchanged
  - Maps to AC #1, AC #2, AC #3

Step 2 — terraform/templates/sre-bot.json.tpl
  - In the "environment" JSON array (currently only BACKEND_URL), append:
    {"name": "ENVIRONMENT", "value": "production"}
  - No terraform variable needed — value is the literal string "production"
  - Maps to AC #4

Step 3 — .github/workflows/ci_code.yml
  - In the Test step's env: block, add:
    ENVIRONMENT: ci
  - Maps to AC #5

Step 4 — app/tests/unit/infrastructure/configuration/test_app_settings.py
  - Add TestAppSettingsEnvironment class (or extend existing TestAppSettings):
    - test_environment_default_is_local: AppSettings().ENVIRONMENT == "local"
    - test_environment_all_valid_values: parametrize ["local","ci","dev","staging","production"] — each constructs without error
    - test_environment_invalid_value_raises_validation_error: AppSettings(ENVIRONMENT="uat") raises ValidationError
    - test_dev_bypass_enabled_default_false: AppSettings().DEV_BYPASS_ENABLED is False
    - test_dev_bypass_enabled_can_be_set_true: AppSettings(DEV_BYPASS_ENABLED=True).DEV_BYPASS_ENABLED is True
    - test_is_production_shim_true_when_production: AppSettings(ENVIRONMENT="production").is_production is True
    - test_is_production_shim_false_when_local: AppSettings(ENVIRONMENT="local").is_production is False
    - test_is_production_shim_false_when_ci: AppSettings(ENVIRONMENT="ci").is_production is False
  - Maps to AC #6

AC traceability:
  AC #1 (ENVIRONMENT field + validation) — Steps 1, 4
  AC #2 (DEV_BYPASS_ENABLED default) — Steps 1, 4
  AC #3 (is_production shim) — Steps 1, 4
  AC #4 (terraform manifest) — Step 2
  AC #5 (CI env) — Step 3
  AC #6 (tests pass) — Step 4

Test matrix:
  Happy: AppSettings() constructs with defaults; each of the 5 valid ENVIRONMENT values accepted
  Boundary: ENVIRONMENT="staging" accepted (future-proofing; not currently deployed)
  Failure: ENVIRONMENT="uat" raises pydantic ValidationError at construction time
  Default: DEV_BYPASS_ENABLED=False; ENVIRONMENT="local"
  Shim: is_production=True only when ENVIRONMENT=="production"; False for all other 4 values
  Regression: existing PREFIX and LOG_LEVEL tests continue to pass unchanged

Assumptions and verification:
  1. `from typing import Literal` is not yet imported in app.py — verify with read before editing
  2. terraform/ecs.tf does NOT need a new variable for ENVIRONMENT; the template uses a hardcoded literal "production" value which is correct since this template only runs for prod — verify by checking ecs.tf for existing variable bindings
  3. .devcontainer/docker-compose.yml already has ENVIRONMENT: 'dev' — confirmed; no change needed
  4. The `lru_cache` on get_app_settings means ENVIRONMENT is read once at startup; tests that use AppSettings() directly bypass the cache and are unaffected

Blast radius and rollback:
  - Change is purely additive; is_production shim returns identical results to current PREFIX-based logic (for any real deployment: prod sets ENVIRONMENT=production → is_production=True; all others have PREFIX != "" → is_production was False → shim returns False)
  - CRITICAL ordering: app code and terraform/CI changes must ship in the same PR so production never sees ENVIRONMENT defaulting to "local" (which would make is_production=False)
  - Single git revert of this PR fully restores previous state; TASK-1.2 cannot compile without TASK-1.1 (ENVIRONMENT and DEV_BYPASS_ENABLED fields would be missing)
  - No routing or security logic changes; any revert is clean
<!-- SECTION:PLAN:END -->
