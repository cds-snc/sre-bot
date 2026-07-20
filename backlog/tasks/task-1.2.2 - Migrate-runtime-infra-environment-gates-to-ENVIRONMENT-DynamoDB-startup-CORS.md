---
id: TASK-1.2.2
title: >-
  Migrate runtime infra environment gates to ENVIRONMENT (DynamoDB, startup,
  CORS)
status: In Progress
assignee:
  - '@me'
created_date: '2026-07-17 19:44'
updated_date: '2026-07-20 21:33'
labels:
  - phase-0
milestone: m-0
dependencies:
  - TASK-1.2.1
references:
  - decisions/configuration.md
parent_task_id: TASK-1.2
priority: high
ordinal: 48000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2 of TASK-1.2. Replace PREFIX-based environment derivation in AWS DynamoDB client selection, scheduled-task startup gate, and CORS allow-origins selection. Three DynamoDB paths are independent entry-points that all set local endpoint when PREFIX is truthy; each must check ENVIRONMENT in (local, dev, ci) instead. Scheduled tasks currently skip when PREFIX != ''; must check ENVIRONMENT == production instead. server.py CORS currently uses not bool(PREFIX); must use ENVIRONMENT. is_production shim still NOT removed — that happens in TASK-1.2.3.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 integrations/aws/dynamodb.py local endpoint set only when ENVIRONMENT in (local, dev, ci); no PREFIX reference remains for environment decisions
- [x] #2 integrations/aws/client_next.py get_aws_client DynamoDB local endpoint set only when ENVIRONMENT in (local, dev, ci); no PREFIX reference remains for environment decisions
- [x] #3 modules/aws/aws_access_requests.py _get_dynamodb_client uses ENVIRONMENT in (local, dev, ci) for local endpoint; no PREFIX reference remains for environment decisions
- [x] #4 server/server.py CORS allow_origins computed from ENVIRONMENT == production not from bool(PREFIX); wildcard is returned for non-production, explicit list for production
- [x] #5 Unit tests cover DynamoDB endpoint matrix: local/dev/ci get local URL; staging/production get None
- [x] #6 Full non-smoke test suite passes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Ordered steps — is_production shim stays on AppSettings throughout this slice; PREFIX field is also retained.

Step 1 — app/integrations/aws/dynamodb.py (line 20)
  Replace module-level endpoint guard:
    Before: if app_settings.PREFIX:
    After:  if app_settings.ENVIRONMENT in ("local", "dev", "ci"):
  app_settings = get_app_settings() is already imported at line 14 — no new imports.
  Maps to AC #1.

Step 2 — app/integrations/aws/client_next.py (line 197)
  In function get_aws_client (line 176), settings is get_aws_settings() — it has no ENVIRONMENT field.
  Add import and module-level singleton after existing settings line (line 46):
    Add: from infrastructure.configuration.app import get_app_settings
    Add: app_settings = get_app_settings()
  Replace the DynamoDB endpoint guard:
    Before: if service_name == "dynamodb" and settings.PREFIX:
    After:  if service_name == "dynamodb" and app_settings.ENVIRONMENT in ("local", "dev", "ci"):
  Maps to AC #2.

Step 3 — app/modules/aws/aws_access_requests.py (line 20)
  Inside _get_dynamodb_client(), app_settings is obtained via get_app_settings() at line 16.
  Replace inline ternary:
    Before: "http://dynamodb-local:8000" if app_settings.PREFIX != "" else None
    After:  "http://dynamodb-local:8000" if app_settings.ENVIRONMENT in ("local", "dev", "ci") else None
  No new imports needed.
  Maps to AC #3.

Step 4 — app/server/lifespan.py (line 105)
  Replace scheduled-task skip guard in _start_scheduled_tasks():
    Before: if app_settings.PREFIX != "":
              logger.info("scheduled_tasks_skipped", reason="prefix_not_empty")
    After:  if app_settings.ENVIRONMENT == "production":
              logger.info("scheduled_tasks_skipped", reason="environment_is_production")
  BEHAVIORAL NOTE: this is an intentional semantic reversal. Old logic skipped in non-production
  (PREFIX != "") and ran in production (PREFIX=""). New logic skips in production and runs in
  local/dev/ci/staging. This aligns with the expectation that in-process scheduled tasks are used for
  local/dev testing and a cloud scheduler (ECS/EventBridge) drives production. Confirm with human reviewer.
  Maps to AC #4.

Step 5 — app/server/server.py (line 23)
  Replace CORS allow_origins guard:
    Before: if not bool(app_settings.PREFIX)
    After:  if app_settings.ENVIRONMENT != "production"
  SECURITY NOTE: this is a required behavior reversal. Old code returned ["*"] wildcard for production
  (PREFIX="") and localhost list for non-production — a security bug. New code returns ["*"] for
  non-production (local/dev/ci/staging) and explicit list for production, matching security.md.
  Maps to AC #5.

Step 6 — app/tests/integration/server/test_lifespan.py (lines 164-210)
  Update two existing scheduled-tasks tests to assert the ENVIRONMENT-based condition.
  Test 1 — test_lifespan_start_scheduled_tasks_skips_when_prefix_not_empty:
    Rename to: test_lifespan_start_scheduled_tasks_skips_when_environment_is_production
    Update docstring accordingly.
    Replace: mock_settings.PREFIX = "dev"
    With:    mock_settings.ENVIRONMENT = "production"
    Replace logger.info assertion:
      Before: reason="prefix_not_empty"
      After:  reason="environment_is_production"
  Test 2 — test_lifespan_start_scheduled_tasks_runs_when_prefix_empty:
    Rename to: test_lifespan_start_scheduled_tasks_runs_when_environment_not_production
    Update docstring accordingly.
    Replace: mock_settings.PREFIX = ""
    With:    mock_settings.ENVIRONMENT = "local"
  Maps to AC #7.

Step 7 — app/tests/unit/server/conftest.py (line 31)
  Required companion fix: mock_settings fixture sets PREFIX = "" at line 31. Since code after this
  slice no longer reads PREFIX in the affected code paths, update the fixture to set ENVIRONMENT
  instead to keep it semantically aligned:
    Remove: settings.PREFIX = ""
    Add:    settings.ENVIRONMENT = "local"
  Maps to AC #8 (prevents inadvertent breakage in tests that receive mock_settings).

Step 8 — app/tests/unit/integrations/aws/test_dynamodb_local_endpoint.py (new file)
  5 unit tests covering the DynamoDB endpoint matrix across all three call sites.
  Since all three paths use app_settings.ENVIRONMENT, each test monkeypatches the module-level
  app_settings in the respective module:
  - test_dynamodb_endpoint_set_for_local: ENVIRONMENT="local" → endpoint_url == "http://dynamodb-local:8000"
  - test_dynamodb_endpoint_set_for_dev: ENVIRONMENT="dev" → endpoint_url present
  - test_dynamodb_endpoint_set_for_ci: ENVIRONMENT="ci" → endpoint_url present
  - test_dynamodb_endpoint_not_set_for_staging: ENVIRONMENT="staging" → endpoint_url absent/None
  - test_dynamodb_endpoint_not_set_for_production: ENVIRONMENT="production" → endpoint_url absent/None
  These 5 tests cover the matrix for integrations/aws/dynamodb.py (the module-level client_config dict).
  client_next.py and aws_access_requests.py endpoint logic is functionally identical; matrix
  coverage via the dynamodb.py path is sufficient for the 5-environment gate.
  Maps to AC #6.

AC traceability:
  AC #1 (dynamodb.py ENVIRONMENT) — Step 1
  AC #2 (client_next.py ENVIRONMENT) — Step 2
  AC #3 (aws_access_requests.py ENVIRONMENT) — Step 3
  AC #4 (lifespan skip ENVIRONMENT) — Step 4
  AC #5 (server.py CORS ENVIRONMENT) — Step 5
  AC #6 (DynamoDB endpoint matrix tests) — Step 8
  AC #7 (lifespan test updated) — Step 6
  AC #8 (full suite) — validated after all steps (Steps 7 and 8 required for green)

Test matrix:
  DynamoDB endpoint: local/dev/ci → "http://dynamodb-local:8000"; staging/production → None
  Scheduled tasks: ENVIRONMENT="production" → skip (return None); ENVIRONMENT="local" → run
  CORS: ENVIRONMENT="production" → explicit list; ENVIRONMENT="local" → wildcard

Assumptions and verification (all confirmed during planning):
  1. integrations/aws/dynamodb.py: app_settings = get_app_settings() at line 14 — no new import (confirmed).
  2. integrations/aws/client_next.py: settings is get_aws_settings() (line 46), has no ENVIRONMENT field —
     new import from infrastructure.configuration.app import get_app_settings required (confirmed: line 41 already imports from infrastructure.configuration.integrations.aws; new import goes after).
  3. modules/aws/aws_access_requests.py: get_app_settings() called inside _get_dynamodb_client() at line 16 — no new import (confirmed).
  4. server/lifespan.py: AppSettings already imported at line 12; app_settings is the function parameter, not a module-level singleton — change is safe (confirmed: _start_scheduled_tasks signature at line 96).
  5. server/server.py: app_settings = get_app_settings() at module level (line 11) — no new import (confirmed).
  6. mock_settings in tests/unit/server/conftest.py is a MagicMock with explicit PREFIX = "" (line 31) — changing to ENVIRONMENT = "local" keeps the fixture semantically correct for all test consumers.
  7. The two lifespan tests at lines 164-210 use mock_settings from the server conftest.py fixture; they set PREFIX explicitly, so changing mock_settings.PREFIX → mock_settings.ENVIRONMENT covers both the fixture and the override.
  8. No existing tests cover the DynamoDB endpoint decision in dynamodb.py, client_next.py, or aws_access_requests.py — confirmed by searching tests/unit/integrations/aws/ and tests/integrations/aws/.

Blast radius and rollback:
  - 5 production source edits are 1-2 line replacements; single git revert restores all call sites.
  - Behavioral reversals (Steps 4 and 5) are the highest risk: confirm before merging that cloud scheduled tasks are not in-process in production, and that the production CORS allow list is complete.
  - CORS allow list values (localhost URLs) are unchanged in this slice — the explicit production list still contains localhost entries. A follow-on task should replace them with real production origins from settings.
  - is_production shim and PREFIX field are NOT removed; TASK-1.2.3 handles that.
  - Full non-smoke suite must be green before merging (Step 7 conftest fix is required for this).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Scope adjusted per follow-up decision: removed lifespan-related AC items from this task. Implemented and verified code updates for DynamoDB ENVIRONMENT gating across three call sites and CORS ENVIRONMENT production guard; DynamoDB endpoint matrix tests are present in app/tests/unit/integrations/aws/test_dynamodb_local_endpoint.py. Remaining AC is full non-smoke suite pass, currently blocked in this environment by missing dependency (ModuleNotFoundError: pydantic) when loading tests/conftest.py.

Validation complete: uv run pytest tests --ignore=tests/smoke passed (2875 passed, 37 skipped). AC #6 satisfied. Lifespan behavior remains aligned with current branch tests; task scope remains limited to DynamoDB ENVIRONMENT gates and CORS ENVIRONMENT guard as agreed.
<!-- SECTION:NOTES:END -->
