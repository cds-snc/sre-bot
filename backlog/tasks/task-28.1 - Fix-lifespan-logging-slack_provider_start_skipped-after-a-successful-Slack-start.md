---
id: TASK-28.1
title: >-
  Fix lifespan logging slack_provider_start_skipped after a successful Slack
  start
status: To Do
assignee: []
created_date: '2026-09-15 14:08'
labels:
  - infrastructure
  - phase-4
  - observability
milestone: m-4
dependencies: []
references:
  - app/server/lifespan.py
  - app/tests/integration/server/test_lifespan.py
parent_task_id: TASK-28
priority: medium
ordinal: 207000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Carved out of TASK-28 (logging correctness, independent of the middleware trio). Findings recorded 2026-09-15 from a local `make dev` startup; re-verify line numbers before planning.

SYMPTOM
Local dev startup logs `slack_provider_start_skipped reason=test_environment`, immediately followed by slack_sdk "A new session has been established", so Slack did start.

ROOT CAUSE (app/server/lifespan.py:305-313)
    if not _is_test_environment():
        start_slack_result = app.state.slack_provider.start()
        if not start_slack_result.is_success:
            logger.warning("slack_provider_start_failed", error=start_slack_result.message)
        else:
            logger.info("slack_provider_start_skipped", reason="test_environment")
The `else` is attached to `if not start_slack_result.is_success` instead of `if not _is_test_environment()`. The "skipped" event is therefore logged on every SUCCESSFUL start, in every environment including production (entrypoint bin/entry.sh runs the same lifespan). The real test-environment skip logs nothing. Probably a leftover from the lifespan refactor. Cosmetic but misleading: it hides whether Slack started.

WHY TESTS MISSED IT
The block only runs when `_is_test_environment()` (lifespan.py:55-57, `"pytest" in sys.modules`) is False, so it never runs under pytest. tests/integration/server/test_lifespan.py covers only the helpers (_is_test_environment, _get_logger_from_app, _list_configs_from_sections, _register_legacy_handlers, _start/_stop_scheduled_tasks, _initialize_directory_provider). Nothing drives lifespan() through the Slack start. Existing precedent for flipping the gate: test_lifespan_is_test_environment_detects_non_pytest (test_lifespan.py:34-45), which monkeypatches the module. Easiest seam: extract the start block into a small helper, e.g. `_start_slack_provider(slack_provider, logger)`, testable like `_start_scheduled_tasks`, or patch `_is_test_environment` plus a fake provider whose start() returns OperationResult success/error.

OTHER CANDIDATES IN THE SAME FILE (fix-bugs-in-touched-files policy, keep simple)
- lifespan.py:184 `_initialize_translation_service` has an empty docstring `""""""`, and binds `log = logger.bind(phase=...)` at :186 but logs phase-1 events through the unbound `logger` at :189 and :193. The phase context is lost.
- `_is_test_environment` is duplicated verbatim in infrastructure/logging/setup.py:98-104. Note only; consolidating it is a refactor, not part of this bug fix.

NOT THIS TASK
Mixed plain/structured log formats (uvicorn `INFO:` lines, bare slack_sdk messages) belong to TASK-28.2. Local-dev `WARNING: Invalid HTTP request received.` / `HEAD / 405` are not app bugs (see TASK-28.2 notes).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 When not in a test environment and slack_provider.start() succeeds, no slack_provider_start_skipped event is logged; an info event confirming the start is logged instead
- [ ] #2 When slack_provider.start() returns a non-success result, slack_provider_start_failed is logged at warning with the result message (unchanged behaviour)
- [ ] #3 When running in a test environment, slack_provider.start() is not called and slack_provider_start_skipped reason=test_environment is logged
- [ ] #4 The three branches are covered by tests that force the test-environment gate (no reliance on pytest being absent)
<!-- AC:END -->
