---
id: TASK-1.2.1
title: >-
  Migrate security/auth and transport env checks to ENVIRONMENT; enforce dual
  dev-bypass guard
status: To Do
assignee: []
created_date: '2026-07-17 19:44'
updated_date: '2026-07-17 19:51'
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

Step 1 — app/infrastructure/security/current_user.py (lines 27, 103–105)
  Replace docstring mention: "Blocked when PREFIX="" (production)" →
    "Blocked when ENVIRONMENT == 'production' or DEV_BYPASS_ENABLED is False."
  Replace single guard at line 103:
    Before: if not app_settings.is_production and server_settings.DEV_BYPASS_TOKEN:
    After:  if (app_settings.ENVIRONMENT != "production"
                and app_settings.DEV_BYPASS_ENABLED
                and server_settings.DEV_BYPASS_TOKEN):
  Inner credential-match check, log.warning, and return User(...) are unchanged.
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
  (settings is module-level get_app_settings() — already has ENVIRONMENT field from TASK-1.1)
  Maps to AC #4.

Step 5 — app/tests/integration/webhooks/conftest.py (lines 211–231)
  Update mock_sns_signature_validation_disabled fixture:
    Remove: type(mock_settings).is_production = PropertyMock(return_value=False)
    Remove: mock_settings = MagicMock()
    Replace with: monkeypatch.setattr("modules.webhooks.aws_sns.app_settings", AppSettings(ENVIRONMENT="local"))
    Add import: from infrastructure.configuration.app import AppSettings
  Maps to AC #5.

Step 6 — app/tests/unit/infrastructure/security/test_current_user_bypass.py (new file)
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
  AC #7 (full suite green) — validated after all steps

Test matrix:
  Bypass guard: 4 scenarios (all 4 combinations of guard state)
  Channel routing: non-production → test channel; production → ops channel
  SNS skip: non-production → early return without validation; production → full validation path
  Revoke gate: non-production → "error" skip log; production → real call

Assumptions and verification:
  1. settings = get_app_settings() in notify/client.py (confirmed: line 15) — already has ENVIRONMENT after TASK-1.1.
  2. app_settings = get_app_settings() already imported and used in aws_sns.py, api_key_detected.py, current_user.py — no import changes needed.
  3. integration/webhooks/conftest.py currently uses PropertyMock on MagicMock — confirmed at line 224. It has no return/yield statement but the fixture works; the replacement uses monkeypatch.setattr which is cleaner and needs no explicit return.
  4. Bypass unit tests require importing get_current_user and mocking three injected dependencies (credentials, jwks_manager, server_settings) via unittest.mock.patch; use real AppSettings for environment/bypass control.

Blast radius and rollback:
  - All four source edits are 1-line replacements; single git revert of this PR restores every call site.
  - conftest.py fixture change breaks only if SNS tests depend on is_production shim still working — it does (shim stays until TASK-1.2.3), but tests must not rely on the PropertyMock path after this change.
  - is_production shim is NOT removed; TASK-1.2.2 and TASK-1.2.3 both depend on it still being present after this PR merges.
  - Full non-smoke suite must be green before merging.
<!-- SECTION:PLAN:END -->
