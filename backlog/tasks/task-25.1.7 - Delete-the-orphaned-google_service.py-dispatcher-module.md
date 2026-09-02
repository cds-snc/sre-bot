---
id: TASK-25.1.7
title: Delete the orphaned google_service.py dispatcher module
status: To Do
assignee: []
created_date: '2026-09-02 13:26'
labels:
  - clients
  - phase-3
  - cleanup
milestone: m-3
dependencies:
  - TASK-25.1.5
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/google_workspace/google_service.py
parent_task_id: TASK-25.1
priority: medium
ordinal: 130000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Delete the now-orphaned legacy Google dispatcher module integrations/google_workspace/google_service.py and its test file tests/integrations/google_workspace/test_google_service.py (482 lines).

OWNERSHIP GAP THIS TASK CLOSES (found 2026-09-02 while planning TASK-25.1.5): no existing task owned this deletion. TASK-23 shipped Done with AC#3 explicitly scoping itself to the _next generation and deferring the non-_next execute_google_api_call plus the get_google_api_command_parameters docstring scraper to TASK-25.1. TASK-25.1's own AC#1 in turn says google_service.py is "slated for TASK-23 deletion" - now stale and circular. TASK-25.1.6 covers the shared execute helpers in client.py, not this module.

PRECONDITION: TASK-25.1.5 lands. At that point google_service.py has zero production importers repo-wide (grep-verified 2026-09-02: google_drive.py is the last one; the only other matches are bin/check_sdk_typing.py's own detection regex and a hasattr assertion in tests/integrations/google_workspace/test_sheets.py:250).

Scope: pure deletion. Delete the module and its test file; prune "integrations/google_workspace/google_service.py" from app/bin/baselines/sdk_typing_antipatterns.txt; confirm decisions/sdk-typing.md's Checks now pass for the Google vendor package (no execute_google_api_call, no getattr string-dispatch, no __doc__-based parameter discovery). Callers of the module's re-exported constants (INCIDENT_TEMPLATE, SRE_BOT_EMAIL, GOOGLE_WORKSPACE_CUSTOMER_ID) must already read them from infrastructure.configuration.integrations.google - TASK-25.1.5 does this for google_drive.py.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/google_workspace/google_service.py and tests/integrations/google_workspace/test_google_service.py are deleted; a repo-wide grep for execute_google_api_call, get_google_api_command_parameters, handle_google_api_errors and get_google_service returns no hits outside bin/check_sdk_typing.py's own detection regex
- [ ] #2 integrations/google_workspace/google_service.py is pruned from app/bin/baselines/sdk_typing_antipatterns.txt and python3 bin/check_sdk_typing.py passes
- [ ] #3 decisions/sdk-typing.md's Google-side Checks are verified green: no string-dispatch and no docstring-based parameter discovery remain anywhere in app/integrations/google_workspace/
- [ ] #4 make test is green with no behavior change; the assertion in tests/integrations/google_workspace/test_sheets.py:250 is updated or removed as appropriate
<!-- AC:END -->
