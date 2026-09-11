---
id: TASK-25.1.6.14
title: >-
  Set an explicit per-attempt timeout on Google Workspace API clients at
  construction
status: In Progress
assignee: []
created_date: '2026-09-10 14:56'
updated_date: '2026-09-11 13:31'
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
- [x] #1 Every service built by app/integrations/google_workspace/client.py uses an explicit per-attempt HTTP timeout read from typed Google Workspace settings, not the google-api-python-client default
- [x] #2 The timeout setting has a documented default and rejects non-positive values
- [x] #3 The construction-time retry default still applies to every built service
- [x] #4 Each built service gets its own Http instance; no Http or Resource is cached and shared across threads
- [x] #5 Factory unit tests assert both the configured timeout and the retry request builder on a built service
- [x] #6 decisions/outbound-clients.md's Migration section no longer lists Google factories inheriting the 60-second default timeout
- [ ] #7 Full test suite, ruff, mypy and app/bin/check_sdk_typing.py pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## Decisions settled with the human (2026-09-10)
1. Default timeout is 10.0 s, the same as the AWS factories (app/integrations/aws/client.py:43-44). The number is NOT written into decisions/outbound-clients.md: the record states rules, the AWS default isn't recorded there either, and a number in the record would go stale whenever the setting changes. The default is documented on the settings field.
2. The setting is a float.
3. Passing `http=` to build() loses no capability in use today (see Seam).
4. The new settings tests go in test_client.py, next to the existing retry-count settings test.

## Seam (verified empirically, google-api-python-client 2.198.0)
- build_from_document (discovery.py:543-553) raises ValueError when `http=` and `credentials=` are both passed. So `_build_service` stops passing `credentials=` and builds the authorized http itself.
- The library's own path when http is None is `_auth.authorized_http(creds)` -> `google_auth_httplib2.AuthorizedHttp(creds, http=build_http())`. `build_http()` is `httplib2.Http(timeout=socket.getdefaulttimeout() or 60)` plus `redirect_codes -= {308}`, which Drive resumable uploads need (guarded by try/except AttributeError for old httplib2).
- The replacement does the same with an explicit timeout: `httplib2.Http(timeout=settings.GOOGLE_API_TIMEOUT_SECONDS)`, the same 308 adjustment, then `AuthorizedHttp(creds, http=...)`, passed as `build(http=...)`. Verified: `AuthorizedHttp(...).http is` the wrapped Http, `.http.timeout` is the value set, and `.credentials` exists.
- What `http=` skips is the `if http is None:` block (discovery.py:592-719). With this repo's inputs it changes nothing:
  - Credential acquisition and scoping: `_build_service` already scopes and delegates the credentials itself.
  - `always_use_jwt_access`: an opt-in build() argument that defaults to False and exists only inside googleapiclient. `_build_service` has never passed it, so the branch never ran.
  - mTLS client certificate and endpoint selection: driven by GOOGLE_API_USE_CLIENT_CERTIFICATE and GOOGLE_API_USE_MTLS_ENDPOINT (default "auto", which switches only when a client cert exists). A repo-wide search, including deploy config and excluding .venv/backlog, finds zero references, so the endpoint stays the standard one.
  - The universe-domain compatibility check still runs on the else branch (discovery.py:720-723) through `http.credentials`.
- Rejected: `socket.setdefaulttimeout` is process-global and would change every socket in the process.

## Files touched
1. app/infrastructure/configuration/integrations/google.py: add next to GOOGLE_API_NUM_RETRIES:
   GOOGLE_API_TIMEOUT_SECONDS: float = Field(default=10.0, alias="GOOGLE_API_TIMEOUT_SECONDS", gt=0, description="Per-attempt HTTP timeout in seconds for every Google Workspace API client, configured once at service construction.")
   `gt=0` rejects non-positive values without a hand-written validator (AC#2). Add the variable to the class docstring's Environment Variables list. Any comment on the field describes when to revisit (the move to a per-vendor Google Workspace settings module), never a task id.
2. app/integrations/google_workspace/client.py:
   - Import httplib2 and google_auth_httplib2.
   - Add `_build_authorized_http(credentials, timeout_seconds: float)` next to `_build_request_builder`. It builds a new `httplib2.Http(timeout=...)`, applies the 308 adjustment the way build_http does, and returns `AuthorizedHttp(credentials, http=...)`. It is a plain, uncached function, so each call returns a new Http (AC#4). A future retries-disabled factory variant can reuse it without restructuring `_build_service`.
   - `_build_service`: after delegation and scoping, call `build(api, version, http=_build_authorized_http(creds, settings.GOOGLE_API_TIMEOUT_SECONDS), cache_discovery=False, static_discovery=True, requestBuilder=_build_request_builder(settings.GOOGLE_API_NUM_RETRIES))`. The requestBuilder is unchanged (AC#3).
   - Extend the existing comment above build() so it covers both the timeout and the retry default, and says each built service owns its Http (httplib2 is not thread-safe).
   - Add no caching anywhere (no lru_cache, no module-level Http or Resource).
3. app/pyproject.toml: add "google_auth_httplib2" to the existing mypy ignore_missing_imports override next to googleapiclient.* (the package ships no py.typed or stubs). httplib2 needs no override because its stubs are installed.
4. decisions/outbound-clients.md: remove the Migration bullet "Google factories that inherit the library's 60-second default timeout (TASK-25.1.6.14)" (AC#6). Add one short dated sentence to Changes, dated the day it lands, e.g. "- <date>: Google factories set an explicit per-attempt timeout." Leave the rest of the record unchanged.

## Worst-case latency at the defaults
GOOGLE_API_NUM_RETRIES=3 means up to 4 attempts. `_retry_request` sleeps `rand() * 2**n` before retry n (verified), so at most 2+4+8 = 14 s of backoff, and it also retries socket timeouts. Worst case per call is about 4 x 10 + 14 = 54 s, down from about 4 x 60 + 14 = 254 s today.

## Tests (extend app/tests/unit/integrations/google_workspace/test_client.py)
Reuse the existing fake_build / _install_fake_build capture (captured["build_kwargs"]). The SimpleNamespace settings doubles gain GOOGLE_API_TIMEOUT_SECONDS=10.0.
- test_build_service_sets_explicit_http_timeout: build_kwargs["http"] is an AuthorizedHttp, its .http.timeout equals the configured value, 308 is not in .http.redirect_codes, and "credentials" is not among the build kwargs (AC#1).
- test_build_service_applies_timeout_and_retry_builder_together: one built service carries both the timed http and the requestBuilder retry default (AC#3, AC#5).
- test_build_service_creates_a_new_http_per_call: two builds capture two `http` objects that are not the same object, and neither are their wrapped Http objects (AC#4).
- test_google_workspace_settings_timeout_defaults_and_reads_environment: default 10.0; monkeypatch.setenv("GOOGLE_API_TIMEOUT_SECONDS", "2.5") is read as 2.5. Mirrors the retry-count settings test in the same file.
- test_google_workspace_settings_timeout_rejects_non_positive: parametrized over "0" and "-1"; constructing the settings raises pydantic.ValidationError (AC#2).
Docstrings describe observable behaviour, the stub strategy and why the assertion matters, per testing-standards.
Order: write the tests first and see them fail, then change settings and client.py.

## AC traceability
- AC#1 -> _build_authorized_http plus the _build_service change; test_build_service_sets_explicit_http_timeout.
- AC#2 -> Field(gt=0, default=10.0) plus docstring; the two settings tests.
- AC#3 -> unchanged requestBuilder; test_build_service_applies_timeout_and_retry_builder_together.
- AC#4 -> uncached per-call construction; test_build_service_creates_a_new_http_per_call.
- AC#5 -> test_build_service_applies_timeout_and_retry_builder_together.
- AC#6 -> ADR Migration bullet removed.
- AC#7 -> Verification.

## Blast radius and rollback
_build_service is the only place Google services are built, so every Google Workspace service (Directory, Calendar, Meet, Docs, Drive, Sheets) gets the timeout; there are no per-call overrides. Risk: a call that used to succeed after more than 10 s now times out and is retried, and if it still fails it surfaces as a socket timeout. Mitigation: the setting can be changed through the environment without a code change. A single revert restores the library default.

## Verification (from app/)
uv run ruff check .
uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'
uv run pytest tests/unit/integrations/google_workspace tests/unit/infrastructure/directory tests/unit/infrastructure/drive tests/unit/infrastructure/spreadsheets
uv run pytest tests --ignore=tests/smoke
uv run python bin/check_sdk_typing.py
uv run python bin/check_vendor_package_contract.py

## Size gate
2 production files (client.py, settings), 1 mypy override line, 1 ADR bullet, roughly 40-60 production LOC, one subsystem, a single behaviour change. Within the single-PR gate; no decomposition needed.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Implementation
- client.py: `_build_authorized_http(credentials, timeout_seconds)` builds a new `httplib2.Http(timeout=...)`, drops 308 from `redirect_codes` (as `googleapiclient.http.build_http` does), and wraps it in `google_auth_httplib2.AuthorizedHttp`. `_build_service` passes `http=` instead of `credentials=`; `requestBuilder` is unchanged. Nothing is cached.
- The library's `AttributeError` guard around `redirect_codes` was not copied: google-api-python-client>=2.190 requires an httplib2 version that has the attribute, and the stubs type it.
- settings: `GOOGLE_API_TIMEOUT_SECONDS: float`, default 10.0, `gt=0`, documented on the field and in the class docstring.
- pyproject: `google_auth_httplib2` added to the mypy `ignore_missing_imports` override.
- decisions/outbound-clients.md: Migration bullet removed; one dated line added under Changes.
- tests/unit/infrastructure/spreadsheets/test_google_spreadsheet_provider.py: settings double gains `GOOGLE_API_TIMEOUT_SECONDS`, since construction now reads it.

## AC #7 left unchecked: pre-existing gate failures
Checked by running both gates with this change temporarily reverted:
- mypy: 88 errors in 32 files, output identical line for line with and without the change; none in touched files.
- pytest: 6 failures present with and without the change (3 in tests/modules/webhooks/test_webhooks_aws_sns.py, 3 in tests/unit/infrastructure/directory/test_google.py). The directory ones pass when run alone, so they depend on test order.
- ruff, check_sdk_typing.py and check_vendor_package_contract.py pass.

## Environment fix (.vscode/settings.json)
The mypy VS Code extension ran its bundled mypy 1.15.0 against the same app/.mypy_cache as the pinned CLI mypy 1.19.1. The CLI gate crashed with `KeyError: 'setter_type'` and gave inconsistent results. The workspace settings now point the extension at app/.venv (`importStrategy: fromEnvironment`) and give it its own `--cache-dir=.mypy_cache/vscode`.
<!-- SECTION:NOTES:END -->
