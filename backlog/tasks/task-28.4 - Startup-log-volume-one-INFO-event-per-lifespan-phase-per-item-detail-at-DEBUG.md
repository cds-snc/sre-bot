---
id: TASK-28.4
title: >-
  Startup log volume: one INFO event per lifespan phase, per-item detail at
  DEBUG
status: To Do
assignee: []
created_date: '2026-10-29T16:25:00Z'
labels:
  - observability
  - lifecycle
dependencies:
  - TASK-156
  - TASK-28.2
parent_task_id: TASK-28
priority: medium
ordinal: 461000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A boot writes many INFO lines that describe configuration and registration one step or one item at a time:
- configured_systems_built, initialized_audit_trail_service and initialized_record_store;
- feature_plugins_loaded, slack_commands_registered, event_handlers_registered, feature_routes_registered and feature_startup_warmup_completed;
- registering_legacy_handlers and legacy_slack_commands_registered;
- one line per webhook pattern at import (modules/webhooks: registered_pattern, pattern_registration_success);
- the i18n and security phase lines;
- slack_sdk's own startup lines.

TASK-156 makes configuration_summary and plugin_configuration_summary the record of what configuration a boot used, so the per-step configuration lines carry nothing those two events lack.

decisions/lifecycle.md says each phase is logged with its name, and observability.md says INFO means a state change. No ADR says how many INFO events a boot should emit, or which detail belongs at DEBUG. That is a gap: research current practice (OpenTelemetry, OWASP Logging Cheat Sheet, Spring Boot and ASP.NET Core startup logging) and record the rule in observability.md before changing levels.

Stage:
- Starts after TASK-156 is deployed and its post-deploy summary check passes, so nothing is dropped before its replacement is verified in production.
- Starts with or after TASK-28.2, which routes uvicorn and pre-configuration lines through the pipeline, so foreign startup lines get levels this task can set.
- Webhook pattern registration at import is TASK-168's (webhook pattern discovery), so this task only lowers those lines' level.
- Alarms and deploy checks that match a startup event must keep working: bin/deploy-checks.zsh pre/post, the CloudWatch filters in terraform, and TASK-94.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 An inventory of every event one local boot and one production boot write before the first request, with each event's level and count, recorded in the task notes (production from zsh bin/deploy-checks.zsh output or a Logs Insights query the human runs)
- [ ] #2 observability.md records the startup logging rule (one INFO event per lifespan phase naming the phase, with counts; per-item registration and construction detail at DEBUG; configuration only in the generated summaries), with cited sources
- [ ] #3 Each lifespan phase emits one INFO event with its name and counts; per-item registration, construction and webhook-pattern lines log at DEBUG; no WARNING, ERROR or CRITICAL event changes level
- [ ] #4 No deploy check, alarm filter or test matches a removed or demoted event, verified by rg over bin/, terraform/, .github/ and app/tests
- [ ] #5 A boot test asserts the INFO event count of a ci boot stays at or below the agreed bound
- [ ] #6 ruff, lint-imports, mypy and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
