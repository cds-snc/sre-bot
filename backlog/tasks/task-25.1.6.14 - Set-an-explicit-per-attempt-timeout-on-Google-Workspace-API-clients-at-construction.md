---
id: TASK-25.1.6.14
title: >-
  Set an explicit per-attempt timeout on Google Workspace API clients at
  construction
status: To Do
assignee: []
created_date: '2026-09-10 14:56'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies: []
references:
  - decisions/outbound-clients.md
  - app/integrations/google_workspace/client.py
  - app/infrastructure/configuration/integrations/google.py
  - >-
    https://github.com/googleapis/google-api-python-client/blob/main/docs/thread_safety.md
parent_task_id: TASK-25.1.6
priority: medium
ordinal: 165000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/outbound-clients.md requires every client factory to set a per-attempt timeout explicitly instead of inheriting SDK defaults, and it lists "Google factories that inherit the library's 60-second default timeout" as a tolerated divergence. This task closes that divergence.

CURRENT STATE (verified 2026-09-10 against google-api-python-client 2.198.0):
- app/integrations/google_workspace/client.py::_build_service passes `credentials=` to `build()`. The library then creates its own `httplib2.Http` through `googleapiclient.http.build_http()`, which uses `socket.getdefaulttimeout()` or `DEFAULT_HTTP_TIMEOUT_SEC` (60 s).
- Retries are configured once at construction through `requestBuilder` (TASK-25.1.6.13), with `GOOGLE_API_NUM_RETRIES` defaulting to 3. One call can therefore block a worker thread for roughly 4 x 60 s plus backoff. Google's retry loop also retries socket timeouts.
- AWS factories already set connect and read timeouts (app/integrations/aws/client.py, app/integrations/aws/shield.py). Google is the remaining gap.

WHY IT MATTERS: legacy Slack handlers and jobs call Google synchronously on worker threads. An explicit, settings-owned timeout makes worst-case latency a deliberate, testable choice instead of a library default that can change between releases.

CONSTRAINTS FROM THE DECISIONS:
- The timeout is set once at construction, next to the retry default. There are no per-call timeout arguments.
- A Google Resource runs on httplib2.Http, which is not thread-safe. Each built service must keep its own Http, and nothing may cache and share an Http or Resource across threads.

NOT IN SCOPE: changing retry counts; handling non-idempotent writes (separate task); per-call overrides; AWS clients; moving Google settings to app/integrations/google_workspace/settings.py (TASK-24).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every service built by app/integrations/google_workspace/client.py uses an explicit per-attempt HTTP timeout read from typed Google Workspace settings, not the google-api-python-client default
- [ ] #2 The timeout setting has a documented default and rejects non-positive values
- [ ] #3 The construction-time retry default still applies to every built service
- [ ] #4 Each built service gets its own Http instance; no Http or Resource is cached and shared across threads
- [ ] #5 Factory unit tests assert both the configured timeout and the retry request builder on a built service
- [ ] #6 decisions/outbound-clients.md's Migration section no longer lists Google factories inheriting the 60-second default timeout
- [ ] #7 Full test suite, ruff, mypy and app/bin/check_sdk_typing.py pass
<!-- AC:END -->
