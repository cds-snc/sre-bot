---
id: TASK-90
title: >-
  Fix the test-order state leaks that break the combined pytest run: SNS
  validator instance monkeypatch and cached structlog loggers
status: To Do
assignee: []
created_date: '2026-09-11 16:49'
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
- [ ] #1 cd app && uv run pytest tests --ignore=tests/smoke passes in a single process, and so do the two CI-shaped splits
- [ ] #2 The webhooks e2e conftest no longer monkeypatches the SNS validator instance; the unit tests' class-level patch is effective after the e2e suite has run (verified by running the e2e file followed by the unit file)
- [ ] #3 structlog log capture works after an app-lifespan fixture has run (verified by running tests/api/routes/test_landing.py followed by tests/unit/infrastructure/directory/test_google.py), achieved by a shared test configuration or reset rather than per-test workarounds
- [ ] #4 The testing-standards skill gains the two rules (no instance-level monkeypatch of module singletons; structlog logger cache off under pytest)
<!-- AC:END -->
