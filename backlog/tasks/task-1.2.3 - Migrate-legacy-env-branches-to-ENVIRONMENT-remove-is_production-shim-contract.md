---
id: TASK-1.2.3
title: >-
  Migrate legacy env branches to ENVIRONMENT; remove is_production shim
  (contract)
status: In Progress
assignee:
  - '@me'
created_date: '2026-07-17 19:47'
updated_date: '2026-07-21 15:39'
labels:
  - phase-0
milestone: m-0
dependencies:
  - TASK-1.2.2
references:
  - decisions/configuration.md
  - decisions/security.md
parent_task_id: TASK-1.2
priority: high
ordinal: 49000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 3 of TASK-1.2 — contract phase. Migrate three legacy modules still using PREFIX-string comparisons for environment decisions, then remove the is_production forwarding shim from AppSettings and Settings. After this slice all environment-conditional code reads ENVIRONMENT directly and the old is_production property no longer exists. dev/platforms/slack.py gates dev commands with PREFIX != dev-; must gate with ENVIRONMENT == dev. incident/core.py derives environment string for DB records from PREFIX == dev-; must read ENVIRONMENT directly. incident_conversation.py sets channel name prefix from PREFIX == dev-; must use ENVIRONMENT == dev. After migrating all callers, remove is_production from infrastructure/configuration/app.py, infrastructure/configuration/settings.py, and clean the is_production parameter from infrastructure/logging/setup.py. Update all test fixtures that still mock is_production (unit/infrastructure/conftest.py, unit/infrastructure/logging/conftest.py, unit/server/conftest.py, test_settings_structure.py).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 modules/dev/platforms/slack.py _require_dev_environment uses ENVIRONMENT == dev; no PREFIX string comparison remains
- [ ] #2 modules/incident/core.py _create_database_record environment string reads app_settings.ENVIRONMENT directly; no PREFIX == dev- comparison remains
- [ ] #3 modules/incident/incident_conversation.py channel name prefix uses ENVIRONMENT == dev; no PREFIX == dev- comparison remains
- [ ] #4 infrastructure/configuration/app.py is_production property removed
- [ ] #5 infrastructure/configuration/settings.py is_production property removed
- [ ] #6 infrastructure/logging/setup.py is_production parameter removed; production mode derives from settings.ENVIRONMENT == production
- [ ] #7 All test fixtures that set settings.is_production = False updated to use ENVIRONMENT explicitly
- [ ] #8 grep -rn is_production app/ --include=*.py returns no hits outside comments or historical strings
- [ ] #9 grep -rn PREFIX app/ --include=*.py returns no environment-derivation hits
- [ ] #10 Full non-smoke test suite passes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## Size Gate

Production files touched: 7 | Production LOC changed: ~35 | Subsystems: modules + infra/configuration + infra/logging (single mechanical concern) | Verdict: FITS one PR.

## Ordered Steps

### Step 1 — Migrate modules/dev/platforms/slack.py (AC#1)
File: `app/modules/dev/platforms/slack.py:42`
Change `if app_settings.PREFIX != "dev-":` → `if app_settings.ENVIRONMENT != "dev":`.
The `app_settings` binding (line 38 `app_settings = get_app_settings()` inside `_require_dev_environment`) already exists. No new import needed.

### Step 2 — Migrate modules/incident/core.py (AC#2, AC#9)
File: `app/modules/incident/core.py`
- Remove module-level variable: `PREFIX = app_settings.PREFIX` (line 20).
- Line 301: `environment = "dev" if PREFIX == "dev-" else "prod"` → `environment = "dev" if app_settings.ENVIRONMENT == "dev" else "prod"`. (`app_settings` is already module-level at line 17.)
- Line 431: same change as line 301 (second occurrence in `initiate_resources_creation`).
- Line 574: `if response.get("ok") and PREFIX == "":` → `if response.get("ok") and app_settings.ENVIRONMENT == "production":`. Semantic preserved: security group users added only in production.

### Step 3 — Migrate modules/incident/incident_conversation.py (AC#3, AC#9)
File: `app/modules/incident/incident_conversation.py`
- Remove module-level variable: `PREFIX = settings.PREFIX` (line 21). (`settings = get_app_settings()` remains at line 19.)
- Line 41: `channel_name_prefix = "incident-dev-" if PREFIX == "dev-" else "incident-"` → `channel_name_prefix = "incident-dev-" if settings.ENVIRONMENT == "dev" else "incident-"`.

### Step 4 — Remove is_production from AppSettings (AC#4)
File: `app/infrastructure/configuration/app.py`
Delete the `is_production` property (lines 21–23):
```python
    @property
    def is_production(self) -> bool:
        """True when ENVIRONMENT is production."""
        return self.ENVIRONMENT == "production"
```
Update the class docstring example that references `app_settings.is_production` to reference `app_settings.ENVIRONMENT == "production"` instead.

### Step 5 — Remove is_production from Settings aggregator (AC#5)
File: `app/infrastructure/configuration/settings.py`
Delete the `is_production` property (lines 127–130):
```python
    @property
    def is_production(self) -> bool:
        ...
        return not bool(self.PREFIX)
```
Update the class docstring example (line ~91) that shows `if app_settings.is_production:` → `if app_settings.ENVIRONMENT == "production":`.

### Step 6 — Remove is_production parameter from configure_logging (AC#6)
File: `app/infrastructure/logging/setup.py`
- Remove the `is_production: bool | None = None` parameter (line 106).
- Remove its documentation from the docstring (lines 120–121).
- Remove the docstring example that passes `is_production=False` (line 134).
- Line 164: `prod_mode = is_production if is_production is not None else settings.is_production` → `prod_mode = settings.ENVIRONMENT == "production"`.

### Step 7 — Update infrastructure/configuration/__init__.py docstring (incidental, AC#8)
File: `app/infrastructure/configuration/__init__.py`
Replace docstring example `if app_settings.is_production:` with `if app_settings.ENVIRONMENT == "production":` to keep the documented example accurate and ensure AC#8 grep passes cleanly.

### Step 8 — Update test conftest fixtures (AC#7)
- `app/tests/unit/infrastructure/conftest.py:14`: remove `settings.is_production = False`; add `settings.ENVIRONMENT = "local"` so the Mock spec remains consistent after AppSettings loses the property.
- `app/tests/unit/infrastructure/logging/conftest.py:14`: remove `settings.is_production = False`; add `settings.ENVIRONMENT = "local"` (configure_logging now reads settings.ENVIRONMENT).
- `app/tests/unit/server/conftest.py:23`: remove `settings.is_production = False`; `settings.ENVIRONMENT = "local"` is already present on line 27.

### Step 9 — Remove is_production shim tests from test_app_settings.py (AC#8)
File: `app/tests/unit/infrastructure/configuration/test_app_settings.py`
Remove five tests that assert the now-deleted property:
- `test_app_settings_is_production_when_environment_production` (lines 20–24)
- `test_app_settings_is_not_production_when_environment_non_production` (lines 26–30)
- `test_is_production_shim_true_when_production` (lines 96–100)
- `test_is_production_shim_false_when_local` (lines 102–106)
- `test_is_production_shim_false_when_ci` (lines 108–112)

### Step 10 — Remove is_production delegation test (AC#8)
File: `app/tests/unit/infrastructure/configuration/test_settings_delegation.py`
Remove `test_is_production_matches_app_settings` (lines 159–162).

### Step 11 — Remove is_production structure test (AC#8)
File: `app/tests/unit/infrastructure/configuration/test_settings_structure.py`
Remove `test_settings_is_production_property` (lines 100–105).

### Step 12 — Replace is_production logging test with ENVIRONMENT-based test (AC#6, AC#8)
File: `app/tests/unit/infrastructure/logging/test_setup.py`
Replace `test_configure_logging_with_is_production` (lines 66–72) with `test_configure_logging_production_mode_from_environment` that verifies configure_logging does not raise when called with a mock settings whose ENVIRONMENT is "production" vs "local".

### Step 13 — Update test_logging.py is_production call sites (AC#8)
File: `app/tests/unit/infrastructure/test_logging.py`
Lines 76–77 call `configure_logging(settings=mock_settings, is_production=True/False)`. After step 6, the parameter no longer exists. Replace those calls with `configure_logging(settings=mock_settings)` and ensure mock_settings carries `ENVIRONMENT` instead.

### Step 14 — Update integration test (AC#8)
File: `app/tests/integration/test_app_state_initialization.py`
Remove lines 53–54 that assert `hasattr(settings, "is_production")` and `isinstance(settings.is_production, bool)`. Replace with equivalent assertions on `ENVIRONMENT` if needed for completeness (assert hasattr(settings, "ENVIRONMENT") and settings.ENVIRONMENT in {"local","ci","dev","staging","production"}).

### Step 15 — Verify ACs (AC#8, AC#9, AC#10)
Run:
```
grep -rn is_production app/ --include="*.py"
grep -rn PREFIX app/ --include="*.py" | grep -E "(== |!= )" | grep -v "test_.*PREFIX ==\|settings\.PREFIX\|app\.PREFIX\|prefix.*=.*PREFIX"
pytest app/tests --ignore=app/tests/smoke -x
```
All three must pass clean.

## AC-to-Step Traceability

| AC | Steps |
|---|---|
| #1 slack.py dev gate | Step 1 |
| #2 core.py environment string | Step 2 |
| #3 incident_conversation.py channel prefix | Step 3 |
| #4 AppSettings.is_production removed | Step 4 |
| #5 Settings.is_production removed | Step 5 |
| #6 configure_logging is_production param removed | Steps 6, 12, 13 |
| #7 test fixture mocks updated | Step 8 |
| #8 grep is_production returns no hits | Steps 4–14, 15 |
| #9 grep PREFIX no env-derivation hits | Steps 2–3, 15 |
| #10 non-smoke suite passes | Step 15 |

## Test Matrix

| Test file | New/Changed tests | Cases |
|---|---|---|
| test_setup.py | replace test_configure_logging_with_is_production | mock ENVIRONMENT="production" → JSON renderer selected; mock ENVIRONMENT="local" → console renderer selected |
| test_logging.py | remove is_production kwarg from call | no-kwarg call does not raise |
| test_app_state_initialization.py | remove is_production assertions; add ENVIRONMENT assertion | settings.ENVIRONMENT in valid set |
| conftest fixtures | switch mock attribute | downstream tests remain green |

## Blast Radius and Rollback

- `is_production` is fully internal; no external API, terraform, or CI YAML references found (verified: grep returned no hits).
- The `configure_logging` `is_production` parameter is only used by tests; production call site (`server/lifespan.py:59`) already omits it.
- Single `git revert` of this PR restores all removed properties and comparisons; the app continues to function with the shim.
- Ordering: all steps are independent within the PR; Steps 4–6 (removals) should be committed after Steps 1–3 (callers migrated) to keep the branch green if reviewed incrementally.
- No terraform or environment-variable changes needed; ENVIRONMENT is already set in all environments from TASK-1.2.1.

## Assumptions and Doubts

1. Assumed TASK-1.2.2 is Done (verified: status = Done, ENVIRONMENT landed in all infra paths).
2. Assumed `PREFIX == ""` at core.py:574 means "production only" per the comment. Verify: the comment says "if we are testing, ie PREFIX is 'dev' then don't add the security group users." Migrating to `ENVIRONMENT == "production"` matches this intent. If staging should also add security users, the condition should be `ENVIRONMENT not in ("dev", "local", "ci")` — flag for reviewer.
3. Assumed `PREFIX` in `incident.py`, `secret.py`, `role.py` is only used for Slack command name construction (f"/{PREFIX}command") and not for environment derivation — verified by grep, no comparison operators found.
4. Assumed the `is_production` docstring example in `__init__.py` (line 23) counts as a comment/string for AC#8; the grep would still surface it, so updating it is necessary to make AC#8's grep pass clean.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-21 15:11
---
Reviewer confirmed: core.py:574 PREFIX == "" → ENVIRONMENT == "production" is correct. Staging (if ever added) should also NOT add real security group users. Assumption #2 resolved — no alternative condition needed.
---
<!-- COMMENTS:END -->
