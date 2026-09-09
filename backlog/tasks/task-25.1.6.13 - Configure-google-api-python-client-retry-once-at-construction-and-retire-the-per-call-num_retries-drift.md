---
id: TASK-25.1.6.13
title: >-
  Configure google-api-python-client retry once at construction and retire the
  per-call num_retries drift
status: To Do
assignee: []
created_date: '2026-09-09 15:25'
labels:
  - clients
  - phase-3
  - cleanup
milestone: m-3
dependencies: []
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/google_workspace/client.py
  - app/infrastructure/directory/google.py
  - app/infrastructure/drive/google.py
parent_task_id: TASK-25.1.6
priority: high
ordinal: 141500
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/outbound-clients.md requires SDK-native resilience 'configured once' at client construction, with no retry decision repeated at call sites. The Google surfaces do the opposite today, and the drift is spreading one provider at a time.

CURRENT STATE (grep + empirically verified against google-api-python-client 2.198.0 on 2026-09-09):
- infrastructure/directory/google.py and infrastructure/drive/google.py each define their OWN _NUM_RETRIES = 3 constant and repeat num_retries=_NUM_RETRIES at 12 .execute() call sites between them. Two copies of the same policy, applied by hand, easy to forget.
- integrations/google_workspace/{sheets,google_docs,google_calendar,meet,google_drive}.py and client.py::execute_google_api_request pass NOTHING, so those surfaces have zero backoff on 429/5xx.
- The next provider to be written (infrastructure/spreadsheets/, TASK-25.1.6.10.2) would be the third copy. That is what triggered this task.

WHAT THE SDK ACTUALLY OFFERS (verified, do not re-derive):
- googleapiclient.http.HttpRequest.execute(self, http=None, num_retries=0) is the built-in retry primitive; googleapiclient.http._retry_request implements randomized exponential backoff over 429/5xx. This IS the 'SDK's own primitive' that decisions/outbound-clients.md names for google-api-client - it is not hand-rolled retry, and it is not the time.sleep antipattern.
- discovery.build(..., num_retries=N) does NOT configure API-call retry. It is threaded only into the discovery-document fetch (discovery.py:439). Passing it at build() would be a silent no-op for every subsequent request - do not use it for this.
- discovery.build(..., requestBuilder=...) IS a real construction-time seam: the callable is stored as Resource._requestBuilder (discovery.py:1442), used to construct every request (discovery.py:1266) and propagated to nested sub-resources (discovery.py:1566).

TARGET: a small HttpRequest subclass in integrations/google_workspace/client.py whose execute() defaults num_retries to a single configured value, passed as requestBuilder from _build_service. Every Google Resource built by every factory then retries by default, once, in the vendor package where outbound-clients.md says resilience belongs. Providers and adapters call .execute() plain and make no retry decision.

THEN REMOVE THE DRIFT: delete _NUM_RETRIES and all 12 per-call num_retries arguments from infrastructure/directory/google.py and infrastructure/drive/google.py. Behavior is preserved (same retry count, now applied uniformly), and the surfaces that had no retry at all gain it.

SETTINGS: make the retry count a typed setting on the existing Google Workspace settings rather than a bare module constant, so it is tunable per deployment and centralized per decisions/configuration.md. Keep the default at 3 to match what directory/drive apply today.

NOT IN SCOPE: timeouts (a separate SDK knob, no consumer has asked), asyncio.to_thread offloading of blocking SDK calls (outbound-clients.md asks for it but it is a much larger change across every provider - register it as its own task if this work makes it tempting), AWS/boto3 retry configuration, and deleting execute_google_api_request (TASK-25.1.6.11).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/google_workspace/client.py configures SDK-native retry once at construction via a requestBuilder passed to discovery.build; no factory passes build(num_retries=...), which is verified to affect only discovery-document fetching
- [ ] #2 The retry count is a typed setting (default 3) rather than a duplicated module constant
- [ ] #3 infrastructure/directory/google.py and infrastructure/drive/google.py define no _NUM_RETRIES and pass no num_retries at any .execute() call site; their retry behavior is unchanged, proven by tests asserting a retried 429/5xx still succeeds through the provider
- [ ] #4 A unit test proves the configured retry count reaches HttpRequest.execute by default for a Resource built through client.py, without any caller passing it
- [ ] #5 No new provider or adapter is required to name a retry policy; the pattern is documented in client.py so the next Google surface inherits it
- [ ] #6 Full test suite, ruff, mypy, and app/bin/check_sdk_typing.py pass
<!-- AC:END -->
