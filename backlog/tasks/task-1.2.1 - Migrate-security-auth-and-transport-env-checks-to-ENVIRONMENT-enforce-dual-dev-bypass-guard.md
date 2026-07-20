---
id: TASK-1.2.1
title: >-
  Migrate security/auth and transport env checks to ENVIRONMENT; enforce dual
  dev-bypass guard
status: To Do
assignee: []
created_date: '2026-07-17 19:44'
updated_date: '2026-07-20 18:38'
labels:
  - phase-0
milestone: m-0
dependencies:
  - TASK-1.2
references:
  - decisions/configuration.md
  - decisions/security.md
parent_task_id: TASK-1.2
priority: high
ordinal: 47000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 1 of TASK-1.2. Replace is_production with explicit ENVIRONMENT reads in the four highest-priority files: the JWT auth dependency (dual-guard), SNS validation (approved deviation: skip in non-production), notify-channel routing (api_key_detected.py), and notify API key revocation (notify/client.py). Also update the integration/webhooks/conftest.py SNS fixture which currently uses a PropertyMock on is_production. The is_production shim on AppSettings is NOT removed in this slice — that happens in TASK-1.2.3.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 current_user.py dev-bypass guard is ENVIRONMENT != production AND DEV_BYPASS_ENABLED=true AND token matches; either guard alone blocks bypass; each granted bypass logs dev_bypass_token_used
- [ ] #2 aws_sns.py validate_sns_payload uses app_settings.ENVIRONMENT != production for the non-production skip (approved deviation: local/dev/ci are not internet-reachable); no is_production reference remains in the file
- [ ] #3 api_key_detected.py routes to test vs ops channel using ENVIRONMENT != production; no is_production reference remains in the file
- [ ] #4 integrations/notify/client.py revoke_api_key gate uses settings.ENVIRONMENT != production; no is_production reference remains in the file
- [ ] #5 integration/webhooks/conftest.py mock_sns_signature_validation_disabled fixture monkeypatches AppSettings(ENVIRONMENT=local) instead of PropertyMock on is_production
- [ ] #6 New unit tests cover all 4 dev-bypass scenarios: production+enabled+match denied; non-prod+disabled+match denied; non-prod+enabled+mismatch denied; non-prod+enabled+match allowed and logged
- [ ] #7 Full non-smoke test suite passes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Ordered steps — is_production shim stays on AppSettings throughout this slice.

Step 1 — app/infrastructure/security/current_user.py (lines ~29, 105)
  Replace docstring: "Blocked when PREFIX=\"\" (production)."
    After: "Blocked when ENVIRONMENT == 'production' or DEV_BYPASS_ENABLED is False."
  Replace guard at line 105:
    Before: if not app_settings.is_production and server_settings.DEV_BYPASS_TOKEN:
    After:  if (app_settings.ENVIRONMENT != "production"
                and app_settings.DEV_BYPASS_ENABLED
                and server_settings.DEV_BYPASS_TOKEN):
  Inner credential-match check, log.warning, and return User(...) are unchanged.
  Note: this adds DEV_BYPASS_ENABLED as a new required guard — any local setup
  with DEV_BYPASS_TOKEN set must also add DEV_BYPASS_ENABLED=true to preserve bypass.
  Maps to AC #1.

Step 2 — app/modules/webhooks/aws_sns.py (line 84)
  Replace:
    Before: if not app_settings.is_production:
    After:  if app_settings.ENVIRONMENT != "production":
  Add comment above the guard:
    # Approved deviation: local/dev/ci instances are not internet-reachable
    # and never receive real SNS payloads; validation skipped for operational reasons.
  Maps to AC #2.

Step 3 — app/modules/webhooks/patterns/aws_sns_notification/api_key_detected.py (line 20)
  Replace:
    Before: if not app_settings.is_production:
    After:  if app_settings.ENVIRONMENT != "production":
  Maps to AC #3.

Step 4 — app/integrations/notify/client.py (line 116)
  Replace:
    Before: if not settings.is_production:
    After:  if settings.ENVIRONMENT != "production":
  (settings is module-level get_app_settings() at line 15 — already has ENVIRONMENT after TASK-1.1)
  Maps to AC #4.

Step 4b — app/tests/integrations/notify/test_notify_client.py (lines 183, 202, 246, 281)
  Required companion fix: after Step 4 changes the production guard to
  settings.ENVIRONMENT != "production", the 4 tests that mock the production path
  via mock_settings.is_production = True will break. A MagicMock attribute
  compared with != "production" is always True, routing all 4 tests into the
  non-production early-return branch instead of the production code path.
  In each of the 4 test functions: replace
    Before: mock_settings.is_production = True
    After:  mock_settings.ENVIRONMENT = "production"
  Tests affected: test_revoke_api_key_missing_url, test_revoke_api_key_success,
  test_revoke_api_key_failure, test_revoke_api_key_not_found.
  Maps to AC #7.

Step 5 — app/tests/integration/webhooks/conftest.py (lines 10, 213–231)
  Update mock_sns_signature_validation_disabled fixture:
    Remove: mock_settings = MagicMock()
    Remove: type(mock_settings).is_production = PropertyMock(return_value=False)
    Remove: return mock_settings
    Replace body with: monkeypatch.setattr("modules.webhooks.aws_sns.app_settings", AppSettings(ENVIRONMENT="local"))
    Add import at top: from infrastructure.configuration.app import AppSettings
    Remove PropertyMock from the existing import on line 10
      (MagicMock stays — used by two other fixtures in the same file at lines 177, 200)
  Note: no return value needed — confirmed that all 3 test consumers (test_webhook_e2e.py:28,69,129)
  use the fixture for its side effect only; none capture the return value.
  Maps to AC #5.

Step 6 — app/tests/unit/infrastructure/security/test_current_user_bypass.py (new file)
  Place in existing directory app/tests/unit/infrastructure/security/ (alongside test_current_user_helper.py).
  4 behavior tests for the dual-guard, each using MagicMock for server_settings
  and real AppSettings for app_settings to confirm guard semantics:
  - test_bypass_denied_when_environment_is_production:
      AppSettings(ENVIRONMENT="production", DEV_BYPASS_ENABLED=True)
      + matching token → function does not return bypass User
  - test_bypass_denied_when_bypass_disabled:
      AppSettings(ENVIRONMENT="local", DEV_BYPASS_ENABLED=False)
      + matching token → function does not return bypass User
  - test_bypass_denied_when_token_mismatch:
      AppSettings(ENVIRONMENT="local", DEV_BYPASS_ENABLED=True)
      + wrong token → function does not return bypass User
  - test_bypass_allowed_and_logged:
      AppSettings(ENVIRONMENT="local", DEV_BYPASS_ENABLED=True)
      + matching token → returns User with user_id="dev@local" and logger warns dev_bypass_token_used
  Maps to AC #6.

AC traceability:
  AC #1 (dual guard) — Steps 1, 6
  AC #2 (SNS env check) — Step 2
  AC #3 (api_key_detected env check) — Step 3
  AC #4 (notify/client env check) — Step 4
  AC #5 (conftest fixture update) — Step 5
  AC #6 (bypass unit tests) — Step 6
  AC #7 (full suite green) — Steps 4b, 5, 6 plus validation after all steps

Test matrix:
  Bypass guard: 4 scenarios (all 4 combinations of guard state)
  Channel routing: non-production → test channel; production → ops channel
  SNS skip: non-production → early return without validation; production → full validation path
  Revoke gate (unit): non-production → "error" skip log; production → real call
  Revoke gate (integration mock): mock_settings.ENVIRONMENT = "production" keeps 4 existing tests on the production path

Assumptions and verification (all verified during planning):
  1. settings = get_app_settings() in notify/client.py (confirmed: line 15) — already has ENVIRONMENT after TASK-1.1.
  2. app_settings = get_app_settings() already imported and used at module level in aws_sns.py (line 18), api_key_detected.py (line 15), current_user.py — no new imports needed in those files.
  3. integration/webhooks/conftest.py fixture returns mock_settings (confirmed: line 231); tests at test_webhook_e2e.py:28,69,129 list it as a fixture parameter but never capture the return value — safe to drop the return.
  4. PropertyMock import at conftest.py line 10 becomes unused after Step 5 — must be removed to keep linting green. MagicMock import stays (used by fixtures at lines 177, 200).
  5. Bypass unit tests require mocking three injected FastAPI dependencies (credentials, jwks_manager, server_settings) via unittest.mock.patch; use real AppSettings for ENVIRONMENT/DEV_BYPASS_ENABLED control.
  6. DEV_BYPASS_ENABLED already present on AppSettings (app/infrastructure/configuration/app.py line 16, default False). ENVIRONMENT already present (line 15). No model changes needed.

Blast radius and rollback:
  - 4 production source edits are 1-line replacements; single git revert of this PR restores every call site.
  - 4 test edits in test_notify_client.py are 1-line attribute replacements — revert together with production code.
  - conftest.py fixture change: the 3 SNS integration tests must not rely on the PropertyMock path after this change; they do not — confirmed.
  - Behavior tightening: adding DEV_BYPASS_ENABLED to the bypass guard means local/dev setups currently relying on DEV_BYPASS_TOKEN alone will silently lose bypass after deploy unless DEV_BYPASS_ENABLED=true is added to their .env. Flag in PR description.
  - is_production shim is NOT removed; TASK-1.2.2 and TASK-1.2.3 both depend on it still being present after this PR merges.
  - Full non-smoke suite must be green before merging.
<!-- SECTION:PLAN:END -->
