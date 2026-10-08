---
id: TASK-90
title: >-
  Fix the test-order state leaks that break the combined pytest run: SNS
  validator instance monkeypatch and cached structlog loggers
status: Done
assignee: []
created_date: '2026-09-11 16:49'
updated_date: '2026-10-08 15:43'
labels:
  - tests
dependencies: []
references:
  - app/tests/integration/webhooks/conftest.py
  - app/tests/modules/webhooks/test_webhooks_aws_sns.py
  - app/tests/unit/infrastructure/directory/test_google.py
  - app/infrastructure/logging/setup.py
  - app/modules/webhooks/aws_sns.py
  - .claude/skills/testing-standards/SKILL.md
priority: medium
type: bug
ordinal: 191000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-09-11 while verifying a tests-only change. The mandated single-process gate `cd app && uv run pytest tests --ignore=tests/smoke` fails 6 tests that pass in isolation and under the CI-shaped splits (`pytest tests/unit tests/integration` and the make test-legacy list are both green), so CI never sees them. Bisected to two independent state leaks; neither is caused by the failing tests themselves.

LEAK 1: tests/modules/webhooks/test_webhooks_aws_sns.py (3 tests: validates_model, signature_verification_failure, rejects_invalid_signature_outside_production) fail with `ValueError: Unable to load PEM file ... MalformedFraming` after tests/integration/webhooks/test_webhook_e2e.py has run. Cause: tests/integration/webhooks/conftest.py's mock_sns_signature_validation_disabled does `monkeypatch.setattr("modules.webhooks.aws_sns.sns_message_validator.validate_message", ...)` on the module-level SNSMessageValidator INSTANCE. monkeypatch reads the existing value through the instance, gets the bound method, and on teardown writes that bound method back as an instance attribute. From then on the instance attribute shadows the class attribute, so the unit tests' `@patch("modules.webhooks.aws_sns.SNSMessageValidator.validate_message")` (class-level) no longer takes effect and the real validator tries to fetch the fake SigningCertURL.

LEAK 2: tests/unit/infrastructure/directory/test_google.py (3 tests asserting `directory_group_skipped` warnings via structlog.testing.capture_logs) find zero captured entries after any suite that starts the app lifespan has run: tests/api/routes/test_landing.py, tests/integration/test_app_state_initialization.py, tests/integration/webhooks/test_webhook_e2e.py. Cause: the lifespan calls infrastructure/logging/setup.py configure_logging, which runs structlog.configure(cache_logger_on_first_use=True). Module-level loggers such as infrastructure/directory/google.py's are then bound with the production processor chain and cached, and capture_logs' processor swap never reaches them (the warning still prints to stderr, as the captured stderr shows).

Fix at the source, not by reordering or skipping: patch the class attribute (or patch.object on the class) in the webhooks conftest; give the test session a structlog configuration with the cache disabled (or reset structlog after any app-lifespan fixture) so capture_logs works regardless of order. Then promote both lessons into the testing-standards skill per the skill-promotion rule: never monkeypatch an attribute on a module-level singleton instance; structlog's logger cache must be off under pytest.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 cd app && uv run pytest tests --ignore=tests/smoke passes in a single process, and so do the two CI-shaped splits
- [x] #2 The webhooks e2e conftest no longer monkeypatches the SNS validator instance; the unit tests' class-level patch is effective after the e2e suite has run (verified by running the e2e file followed by the unit file)
- [x] #3 structlog log capture works after an app-lifespan fixture has run (verified by running tests/api/routes/test_landing.py followed by tests/unit/infrastructure/directory/test_google.py), achieved by a shared test configuration or reset rather than per-test workarounds
- [x] #4 The testing-standards skill gains the two rules (no instance-level monkeypatch of module singletons; structlog logger cache off under pytest)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## Survey (worktree off origin/main 2ae430d1)
- pytest: `[tool.pytest.ini_options]` in app/pyproject.toml (asyncio_mode=auto, pytest-env). No pytest-randomly, no xdist. 27 conftest.py files; app lifespan is started by TestClient/lifespan in ~25 test modules (tests/api/**, tests/integration/server/**, tests/integration/webhooks/test_webhook_e2e.py, tests/integration/test_app_state_initialization.py, several unit route tests).
- structlog.configure in production code: only infrastructure/logging/setup.py configure_logging (test branch L180, real branch L216), both `cache_logger_on_first_use=True`. Tests: test_setup.py restores via `structlog.configure(**saved_config)` / `structlog.reset_defaults()`.
- Patches of attributes on module-level singleton instances (scripted scan of every string-target patch/monkeypatch.setattr and object-form patch.object against the 9 module-level `name = Class(...)` instances in app code):
  - tests/integration/webhooks/conftest.py -> `modules.webhooks.aws_sns.sns_message_validator.validate_message` (method on instance): IN SCOPE (LEAK 1).
  - tests/api/routes/test_system.py -> `api.routes.system.settings.GIT_SHA` (data field already in the instance __dict__; patch restores the same instance attribute, no shadowing): out of scope.
  - patch.object(client, ...) hits in incident/aws_platform tests target per-test local botocore clients; permissions handler hit targets a module. Out of scope.

## Reproduction (clean main)
- Full run: 6 failed, 3946 passed (/tmp/t90-pytest-base.txt) = 3 aws_sns + 3 directory google.
- LEAK 1: test_webhook_e2e.py then test_webhooks_aws_sns.py -> 3 failed, 24 passed; `ValueError: Unable to load PEM file ... MalformedFraming`.
- LEAK 2: test_landing.py then directory/test_google.py -> 3 failed, 106 passed; `assert 0 == 1` on captured entries.

## Root causes
- LEAK 1: the e2e fixture monkeypatches `validate_message` through the module-level SNSMessageValidator instance. monkeypatch saves the value read through the instance (a bound method) and on teardown setattr's it back onto the instance, leaving an instance attribute that shadows the class. Later class-level `@patch("modules.webhooks.aws_sns.SNSMessageValidator.validate_message")` is bypassed and the real validator fetches the fake cert URL.
- LEAK 2 (confirmed with a diagnostic plugin outside the repo): every lifespan calls configure_logging, whose pytest branch builds a NEW processors list with cache_logger_on_first_use=True. The module-level logger in infrastructure/directory/google.py is first used during an earlier lifespan and cached holding processors list A; later lifespans reconfigure with list B. capture_logs mutates the currently configured list (B) in place, so the cached logger (still on A) never reaches LogCapture. Diagnostic: cached procs id != get_config()["processors"] id, cached procs = [add_log_level, wrap_for_formatter].

## Fix
- LEAK 1: in tests/integration/webhooks/conftest.py, patch the class attribute: `monkeypatch.setattr("modules.webhooks.aws_sns.SNSMessageValidator.validate_message", mock)`. The class attribute is restored on teardown and the instance carries no attribute. The mock is a MagicMock (not a descriptor-bound function) so calls through the instance still hit it with the same args; existing e2e assertions are unaffected.
- LEAK 2: in infrastructure/logging/setup.py, set `cache_logger_on_first_use=False` in the `_is_test_environment()` branch only. That branch is the shared test configuration every lifespan applies; it only executes when pytest is in sys.modules, so production logging behaviour is unchanged (the real branch keeps caching on). With caching off, every log call resolves the current config, so capture_logs works regardless of prior lifespans. No conftest reset needed: a reset cannot un-cache a proxy that is already cached, so the fix must stop caching at the source. Add one regression test to tests/unit/infrastructure/logging/test_setup.py: configure_logging (test branch) twice with a logger used in between, then capture_logs captures that logger's event.
- AC #4: add two short rules to .claude/skills/testing-standards/SKILL.md (patch the class, never an attribute on a module-level singleton instance; structlog logger cache stays off under pytest, so configure_logging's test branch must keep cache_logger_on_first_use=False).

## Files touched
1. app/tests/integration/webhooks/conftest.py (1 line)
2. app/infrastructure/logging/setup.py (1 line)
3. app/tests/unit/infrastructure/logging/test_setup.py (+~20 lines, one test)
4. .claude/skills/testing-standards/SKILL.md (+2 rules)
Size gate: 4 files, ~2 production LOC, one subsystem (test infra + logging test branch), no mechanical refactor mixed in: passes.

## Verification (from app/, worktree pytest invocation with sys.path.append('/workspace/app'))
- AC #2: ordered run test_webhook_e2e.py then test_webhooks_aws_sns.py -> 0 failed.
- AC #3: ordered run test_landing.py then directory/test_google.py -> 0 failed; new regression test passes and fails with cache=True.
- AC #1: full `tests --ignore=tests/smoke` -> 0 failed; `tests/unit tests/integration` and the test-legacy list (tests/api tests/modules tests/integrations tests/utils tests/test_factory_validation.py) -> 0 failed.
- AC #4: skill diff reviewed.
- Gates: ruff check, ruff format --check, lint-imports, mypy error list identical to /tmp/t90-mypy-base.txt (57 errors in 20 files).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Changes
- app/tests/integration/webhooks/conftest.py: mock_sns_signature_validation_disabled patches `modules.webhooks.aws_sns.SNSMessageValidator.validate_message` (class) instead of the attribute on the module-level `sns_message_validator` instance, so teardown no longer leaves a shadowing instance attribute.
- app/infrastructure/logging/setup.py: configure_logging's pytest-only branch (`_is_test_environment()`) now uses `cache_logger_on_first_use=False`. The real/production branch is unchanged (still True). Cached module loggers held the processor list from an earlier lifespan, so capture_logs (which mutates the current list in place) never reached them.
- app/tests/unit/infrastructure/logging/test_setup.py: regression test `test_capture_logs_reaches_a_logger_used_before_a_reconfigure` (logger used, configure_logging re-run, capture_logs still captures). Fails with the cache on (1 failed), passes with it off.
- .claude/skills/testing-standards/SKILL.md: two anti-pattern rules (no monkeypatch of attributes on module-level singleton instances; structlog logger cache off under pytest).

## Evidence (worktree pytest invocation, from app/)
- Baseline clean main: 6 failed, 3946 passed. After: 3953 passed, 0 failed.
- Ordered LEAK 1 (test_webhook_e2e.py -> test_webhooks_aws_sns.py): before 3 failed / 24 passed; after 27 passed.
- Ordered LEAK 2 (test_landing.py -> directory/test_google.py): before 3 failed / 106 passed; after 109 passed.
- `tests/unit tests/integration`: 3170 passed. test-legacy list: 783 passed.
- ruff check: All checks passed; ruff format --check: 825 files already formatted; lint-imports: 10 kept, 0 broken.
- mypy: Found 57 errors in 20 files, error list identical to baseline (pre-existing, unrelated).
<!-- SECTION:NOTES:END -->
