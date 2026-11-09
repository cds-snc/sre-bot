---
id: TASK-25.10.1
title: >-
  OpenAI vendor client on the outbound-client contract: classify_openai_error
  returns the standard tuple and the client's retry policy is explicit
status: In Progress
assignee: []
created_date: '2026-11-09T13:40:00Z'
updated_date: '2026-11-09T14:19:00Z'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-106
references:
  - decisions/outbound-clients.md
  - app/integrations/openai/client.py
  - app/integrations/openai/summarizer.py
  - app/integrations/openai/settings.py
parent_task_id: TASK-25.10
priority: medium
ordinal: 492000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
First slice of TASK-25.10 (expand). The vendor package meets decisions/outbound-clients.md before anything moves out of it.

TODAY: classify_openai_error (app/integrations/openai/client.py:37) returns OperationResult with string codes ('UNAUTHORIZED', 'SERVER_ERROR', ...), baselined as operation-result:integrations/openai/client.py (bin/baselines/vendor_package_contract.txt:20). build_openai_client (client.py:21) sets a timeout and no retry policy. client.py still has 'from __future__ import annotations'. The only caller is OpenAISummarizer (summarizer.py:96-108), which returns the classifier's result as is.

TARGET: classify_openai_error returns (OperationStatus, error_code, retry_after) with ErrorCode registry members, as classify_google_error, classify_aws_error and classify_slack_error do. build_openai_client sets its retry policy once at construction with httpx's own primitive: httpx.AsyncHTTPTransport(retries=N), which retries only ConnectError/ConnectTimeout (httpcore 0.28 connection.py:159), so a completion request that reached the endpoint is never re-sent (non-idempotent, billed; outbound-clients.md rule 1). N is [openai] connect_retries (default 2), a transport-tuning key of the vendor slice (configuration.md). OpenAISummarizer builds its OperationResult from the tuple. Nothing leaves the vendor package here: the Summarizer port and implementation move in TASK-25.10.2.

Out of scope: the capability (25.10.2); generation parameters ([openai] max_output_tokens, temperature, tenant model) (25.10.3).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 classify_openai_error returns (OperationStatus, error_code, retry_after) using ErrorCode members: 401 -> (UNAUTHORIZED, UNAUTHENTICATED); 403 -> (UNAUTHORIZED, FORBIDDEN); 404 -> (NOT_FOUND, NOT_FOUND); 429 -> (TRANSIENT_ERROR, RATE_LIMITED, the integer Retry-After or None); 5xx -> (TRANSIENT_ERROR, SERVER_ERROR); other HTTP status -> (PERMANENT_ERROR, HTTP_ERROR); httpx.TimeoutException -> (TRANSIENT_ERROR, TIMEOUT); any other httpx.HTTPError -> (TRANSIENT_ERROR, CONNECTION_ERROR); any other exception propagates unchanged
- [x] #2 The operation-result:integrations/openai/client.py entry is gone from bin/baselines/vendor_package_contract.txt and make check-vendor-package-contract passes
- [x] #3 OpenAISummarizer returns OperationResult.error built from the tuple (status, error_code, retry_after), with the response-body warning log unchanged; its success path and unconfigured path are unchanged
- [x] #4 Classification tests cover each mapped family above, Retry-After present, absent and non-numeric, and one unmapped exception propagating; no 'from __future__ import annotations' remains in app/integrations/openai/
- [x] #5 decisions/outbound-clients.md's OpenAI tolerance keeps only the Summarizer's location (TASK-25.10.2) and gains a dated Changes line; ruff, the targeted tests, mypy, pytest tests --ignore=tests/smoke, make check-vendor-package-contract, make check-settings-key-ownership and make check-import-contracts pass, with output in notes
- [x] #6 build_openai_client builds its transport as httpx.AsyncHTTPTransport(retries=[openai] connect_retries) next to its timeout; connect_retries (int >= 0, default 2) is in OpenAISettings and base.toml's [openai] table; a factory test asserts the transport's retries and the client's timeout (outbound-clients.md Checks)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Planned 2026-11-09 against main 7b0b3810 (production code identical on this checkout; doc-15 read alongside: nothing in it touches the vendor client). Size: 4 production files (client.py, summarizer.py, settings.py, base.toml) plus 1 baseline line and 1 ADR, about 90 production LOC, one subsystem (integrations/openai). Gate not tripped. Domain-model gate: n/a (no entity; a vendor classification table).

STEPS (TDD: tests first, red, then code)
1. tests/unit/integrations/openai/test_openai_client.py: rewrite TestClassifyOpenAIError to assert the tuple per family (AC #1, #4). 401 -> (UNAUTHORIZED, ErrorCode.UNAUTHENTICATED, None); 403 -> (UNAUTHORIZED, FORBIDDEN, None); 404 -> (NOT_FOUND, NOT_FOUND, None); 429 with Retry-After '42' -> (TRANSIENT_ERROR, RATE_LIMITED, 42); 429 without it -> retry_after None; 429 with an HTTP-date -> None; 503 -> (TRANSIENT_ERROR, SERVER_ERROR, None); 400 -> (PERMANENT_ERROR, HTTP_ERROR, None); httpx.TimeoutException -> TIMEOUT; httpx.ConnectError -> CONNECTION_ERROR; KeyError propagates. Add TestBuildOpenAIClient.test_sets_explicit_timeout_and_connect_retries (AC #6): spy on httpx.AsyncHTTPTransport (an external edge) and assert retries == settings.connect_retries and client.timeout == timeout_seconds. Drop 'from __future__ import annotations' from this file.
2. tests/unit/integrations/openai/test_openai_summarizer.py: the 401 case asserts (UNAUTHORIZED, UNAUTHENTICATED) and the 429 case keeps (TRANSIENT_ERROR, RATE_LIMITED, 7) (AC #3). Add a 5xx case asserting the response-body warning is still logged (structlog capture as the file already does, or capture_logs).
3. tests/unit/integrations/openai/test_openai_settings_load.py and tests/unit/infrastructure/configuration/test_configuration_files_openai.py:54: connect_retries loads from [openai] and defaults to 2; a negative value fails validation; base.toml's [openai] key set includes connect_retries (AC #6).
4. app/integrations/openai/settings.py: connect_retries: int = Field(default=2, ge=0) with a comment: retries cover connection failures only, never a sent request. Update the class docstring's key list.
5. app/config/base.toml [openai]: connect_retries = 2, and the table comment names it.
6. app/integrations/openai/client.py (AC #1, #4, #6): remove the __future__ import and the OperationResult import. classify_openai_error(exc) -> tuple[OperationStatus, str | None, int | None] with the table of AC #1, using ErrorCode members. Retry-After is parsed with int(), and a non-numeric value gives None (PEP 758 'except TypeError, ValueError'). No default of 60 any more: no consumer schedules on retry_after, and the Google classifier returns None the same way. build_openai_client passes transport=httpx.AsyncHTTPTransport(retries=settings.connect_retries) beside timeout. The docstring states that httpcore retries only ConnectError/ConnectTimeout, so a completion that reached the endpoint is never re-sent.
7. app/integrations/openai/summarizer.py (AC #3): in the except branch, status, error_code, retry_after = classify_openai_error(exc), then return OperationResult.error(status, f'OpenAI request failed ({error_code})', error_code=error_code, retry_after=retry_after). The warning log is unchanged. Messages are only logged by consumers (scribe and comms entry points log result.message; none render it), so the wording change is invisible to users.
8. app/bin/baselines/vendor_package_contract.txt: delete 'operation-result:integrations/openai/client.py' (AC #2). summarizer.py's two entries stay until 25.10.2.
9. decisions/outbound-clients.md (AC #5): the OpenAI tolerated-divergence line keeps only 'the Summarizer port and implementation live in the vendor package (TASK-25.10.2)'. Add a Changes line: '2026-11-xx: classify_openai_error returns the standard tuple; the OpenAI client retries connection failures only, set at construction ([openai] connect_retries) (TASK-25.10.1).'
10. Gates: ruff and the targeted test files during TDD. At the end, full mypy, then full pytest, once each, sequentially, then make check-vendor-package-contract, check-settings-key-ownership and check-import-contracts. Record the output in notes (AC #5).

AC -> STEP -> TEST
#1 -> 6 -> test_openai_client.py TestClassifyOpenAIError (per family)
#2 -> 8 -> make check-vendor-package-contract
#3 -> 7 -> test_openai_summarizer.py (401, 429, 5xx log)
#4 -> 1, 6 -> test_openai_client.py (Retry-After present/absent/date, KeyError propagates); rg 'from __future__' app/integrations/openai is empty
#5 -> 9, 10 -> gate output in notes
#6 -> 3, 4, 5, 6 -> test_openai_client.py factory test; settings load and files tests

TEST MATRIX
happy: each status family maps; the factory sets retries and timeout; the summarizer success path is unchanged (existing tests).
boundary: Retry-After absent, non-numeric (HTTP-date) or 0; connect_retries 0 is allowed.
failure: an unmapped exception propagates; connect_retries -1 fails validation; a 5xx still logs the body.
authorization: 401 and 403 map to OperationStatus.UNAUTHORIZED with distinct codes.

ASSUMPTIONS AND DOUBTS
- No consumer branches on the old string codes ('UNAUTHORIZED', 'SERVER_ERROR', ...) or on a 401's PERMANENT_ERROR status. Verified: rg over features/incident/{scribe,comms} shows only their own codes compared; the only literal OpenAI codes are in tests/unit/integrations/openai. Re-check at implementation with rg.
- httpx 0.28.1 / httpcore: retries apply only to ConnectError/ConnectTimeout (httpcore/_async/connection.py:159), with httpcore's exponential backoff. Re-verify against the locked version at implementation.
- 401/403 move from PERMANENT_ERROR to UNAUTHORIZED. A caller treating any non-transient failure alike sees no difference: scribe and comms pass the status through to their logs.

BLAST RADIUS AND ROLLBACK
On merge, production gets connection retries (at most 2 extra connect attempts, never a re-sent completion) and new error codes in logs. Drafting, summaries and comms AI drafting behave as before. One git revert restores it. No terraform, IAM, SSM or environment-name change, so no deploy checks. base.toml gains a key with a code default, so no environment file changes.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-09 (human): plan approved. Implemented in the working tree from main 7b0b3810 (branch task-25.10.1-openai-client-contract to be cut by the human).

2026-11-09 implementation (working tree from main 7b0b3810):
- client.py: classify_openai_error returns (OperationStatus, ErrorCode, retry_after): 401 (UNAUTHORIZED, UNAUTHENTICATED); 403 (UNAUTHORIZED, FORBIDDEN); 404 NOT_FOUND; 429 RATE_LIMITED with integer Retry-After, else None (the 60-second default is gone); 5xx SERVER_ERROR; other status HTTP_ERROR; timeout TIMEOUT; other httpx.HTTPError CONNECTION_ERROR; anything else propagates. build_openai_client passes transport=httpx.AsyncHTTPTransport(retries=connect_retries). The __future__ import is gone.
- settings.py and base.toml: [openai] connect_retries = 2 (ge=0; a negative value fails boot naming the key).
- summarizer.py: OperationResult.error built from the tuple; the warning log is unchanged.
- The operation-result:integrations/openai/client.py baseline entry is deleted.
- outbound-clients.md: the OpenAI tolerance keeps only the Summarizer location; the httpx retry primitive is added to rule 1 (docs: retries only on ConnectError/ConnectTimeout, python-httpx.org/advanced/transports); 2026-11-09 Changes line.
- Tests: test_openai_client.py rewritten (tuple per family, Retry-After 42/0/absent/HTTP-date, unmapped propagates, factory asserts retries and timeout through a recording AsyncHTTPTransport); summarizer 401/429/400 assert the new codes; settings load (connect_retries loads, defaults to 2, negative fails); base [openai] key set. __future__ removed from the touched test files.
Gates: ruff 'All checks passed!'; targeted 62 passed. mypy 'Found 41 errors in 14 files (checked 422 source files)': all pre-existing in legacy modules/ (same count as the TASK-36.3 session), none in touched files. It was invoked twice, the second run only to filter touched files. pytest tests --ignore=tests/smoke: '1 failed, 6550 passed': test_bin_test_seams_check.py::test_the_repository_tests_match_their_baselines, pre-existing on main. make check-test-seams lists 51 strict entries, all under tests/**/features/incident/comms/, which are TASK-186's moved paths that the re-key PR #1836 fixes; unrelated, not fixed here. make check-vendor-package-contract 'OK: no net-new vendor-package contract violations (15 baselined entry(ies) remain)'; make check-settings-key-ownership OK; make check-import-contracts 'Contracts: 13 kept, 0 broken'.
<!-- SECTION:NOTES:END -->
