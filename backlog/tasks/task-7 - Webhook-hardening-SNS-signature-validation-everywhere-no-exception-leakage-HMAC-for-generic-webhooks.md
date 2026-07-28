---
id: TASK-7
title: >-
  Webhook hardening (Phase 0): SNS signature validation everywhere, no exception
  leakage, body-size cap
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-28 17:58'
labels:
  - security
  - phase-0
milestone: m-0
dependencies:
  - TASK-1
references:
  - decisions/security.md
  - 'https://github.com/cds-snc/sre-bot/issues/1261'
priority: high
ordinal: 7000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/security.md (Webhooks, amended 2026-07-24). Scope re-narrowed to Phase-0 non-behaviour-change hardening only; the generic-webhook HMAC requirement that was originally step 2 / AC#2 here is a behaviour change (it can reject senders accepted today) and has moved to Phase 4 - see TASK-47 (HMAC verification + secure-by-default issuance) and TASK-48 (monitor-then-enforce migration), enabled by TASK-46 (Phase-1 origin observability). The legacy unsigned population is risk-accepted in writing per the amended Webhooks clause until TASK-48 migrates it.

Today: /hook/{webhook_id} in app/api/v1/routes/webhooks.py authenticates by existence + active flag only; app/modules/webhooks/aws_sns.py:84-85 returns early without SNS signature validation when not app_settings.is_production; 5xx responses interpolate the exception into the body at aws_sns.py:108 and :120 (detail=f"... {e.__class__.__qualname__}: {e}") (SEC-6, OWASP API2:2023).

Steps (Phase 0, non-behaviour-change):
1. SNS: validate the message signature in ALL environments - delete the early-return branch at aws_sns.py:84-85. (SNS is provider-signed, so this hardens a known signed source and does not affect arbitrary senders.)
2. Replace every f-string that embeds the exception (class name or str(e)) in a 5xx response body with a generic message; log the full exception server-side instead.
3. Cap webhook body size.

Deferred to Phase 4 (m-4): per-webhook HMAC signature requirement, secure-by-default secret issuance, and monitor-then-enforce migration of known senders (TASK-46/47/48).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 SNS signature validation runs unconditionally; a test covers an invalid-signature rejection
- [ ] #2 grep -rn "e.__class__" and f-string exception interpolation in webhook 5xx paths return zero hits; a forced exception yields a generic 500 body (test)
- [ ] #3 Oversized webhook bodies are rejected (test)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Tests pass; existing legitimate webhook flows still succeed against the new auth (documented manual check or smoke test)
- [ ] #2 PR references SEC-6 and decisions/security.md
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Implementation plan (Phase 0 scope only; HMAC/secure-by-default issuance and monitor-then-enforce migration are explicitly out of scope here - see TASK-46/47/48).

Reassessed against decisions/security.md (Webhooks clause, amended 2026-07-24, tiered trust model) and current code: the task description's own line ("app_settings.is_production", "aws_sns.py:84-85/108/120") is stale - TASK-1.2.1 already migrated aws_sns.py off is_production. Current code (verified by reading the file) is:
- app/modules/webhooks/aws_sns.py:86-87 `if app_settings.ENVIRONMENT != "production": return awsSnsPayload` (the gate to delete)
- app/modules/webhooks/aws_sns.py:98,110,118,122 four separate f-strings interpolating `{e.__class__.__qualname__}: {e}` (not just two as the stale description says)
Repo-wide grep confirms `e.__class__` appears ONLY in this one file (an ADR review doc reference aside) - no other webhook 5xx path leaks exceptions; app/api/v1/routes/webhooks.py's HTTPException(500, "Failed to send message") is already generic. No body-size cap exists anywhere in the app today (grep for max_body/Content-Length enforcement: zero hits) or at the ALB/WAF layer (terraform/alb.tf, terraform/waf.tf: no size constraint found). TASK-1 (dependency) is Done, so this task is unblocked.

Step 1 - SNS validation unconditional (AC#1):
1. app/modules/webhooks/aws_sns.py: delete lines 86-87 (the ENVIRONMENT != "production" early return) and its two preceding comment lines (83-84, "Approved deviation..."), so validate_sns_payload always calls sns_message_validator.validate_message.
2. app/tests/modules/webhooks/test_webhooks_aws_sns.py: add test_validate_sns_payload_rejects_invalid_signature_outside_production - construct default/ENVIRONMENT="local" AppSettings (no force_production_app_settings override), mock SNSMessageValidator.validate_message to raise SignatureVerificationFailureException, assert HTTPException with status 500 is still raised (proves the skip is gone). Existing force_production_app_settings-based tests (7 tests) keep passing unmodified (production is a strict subset of "always validate now").
3. app/tests/integration/webhooks/conftest.py: mock_sns_signature_validation_disabled (line ~212-224) currently monkeypatches modules.webhooks.aws_sns.app_settings to force ENVIRONMENT="local" to skip validation - this mechanism stops working once the gate is deleted (fake test signatures like "test-signature-base64" would now hit the real validator and 500). Change it to monkeypatch modules.webhooks.aws_sns.sns_message_validator.validate_message to a no-op MagicMock(return_value=None) instead - same test intent (let fake payloads through), same fixture name/call sites, remove the now-unused "from infrastructure.configuration.app import AppSettings" import at line 14 (no other use in this file, confirmed by grep).
4. app/tests/integration/webhooks/test_webhook_e2e.py: test_webhook_handler_with_subscription_confirmation (~line 85) sends an AwsSnsPayload-shaped fixture (sns_subscription_confirmation_payload, fake Signature) through process_aws_sns_payload -> validate_sns_payload but is currently missing the mock_sns_signature_validation_disabled fixture (it only worked because validation used to be skipped by default-non-production). Add that fixture to its parameter list so it keeps returning non-500 after the gate is removed.

Step 2 - No exception leakage (AC#2):
5. app/modules/webhooks/aws_sns.py, four sites - replace every f-string embedding e.__class__/{e} with a fixed generic string, since AC#2's grep for e.__class__ is unscoped (not just the HTTP response body) and this identifier appears nowhere else in the two except blocks:
   - line 98 (default log_message before the isinstance elif chain overwrites it for all 4 caught types - currently dead code but still a literal grep hit): log_message = "Failed to validate AWS event message".
   - line 110 (HTTPException(status_code=500, detail=f"...")): detail="Failed to validate AWS event message".
   - line 118 (log_ops_message(f"Error parsing AWS event due to {e.__class__...}: ```{awsSnsPayload}```")): drop the exception interpolation, keep the payload context: f"Error parsing AWS event message: ```{awsSnsPayload}```".
   - line 122 (HTTPException(status_code=500, detail=f"...")): detail="Failed to parse AWS event message".
   The existing logger.exception(..., error=str(e)) calls (lines 96, 113-116) already put the full exception server-side (structlog captures the traceback) - unchanged, satisfies "log the full exception server-side instead".
6. app/tests/modules/webhooks/test_webhooks_aws_sns.py: extend the existing test_validate_sns_payload_signature_verification_failure (and add one assertion each to the other three known-exception-type tests, plus test_validate_sns_payload_unexpected_exception) to assert e.value.detail == "Failed to validate AWS event message" (known-type branch) / "Failed to parse AWS event message" (generic-exception branch), and that the exception class name string never appears in e.value.detail.
7. Verification grep before calling this AC done: grep -rn "e\.__class__" app/ returns zero hits.

Step 3 - Cap webhook body size (AC#3):
8. app/infrastructure/configuration/app.py: add one field to AppSettings - WEBHOOK_MAX_BODY_BYTES: int = Field(default=262_144, alias="WEBHOOK_MAX_BODY_BYTES") (262144 = 256 KiB = AWS SNS's own hard per-message size limit, so no legitimate SNS notification can ever be rejected; generous enough for the existing simple-text/generic/access-request payloads which are a few hundred bytes to a few KB). Placed on the AppSettings root deliberately, not infrastructure/security/settings.py's SecuritySettings - that model's get_security_settings() has zero callers repo-wide today (dead/orphaned mid-migration scaffold per its own docstring "while SecuritySettings migration is pending"); reviving it as the first live consumer for an unrelated field is out of scope for this task and flagged as a doubt below.
9. New file app/server/body_size_middleware.py: MaxBodySizeMiddleware(BaseHTTPMiddleware) (mirrors the existing single-class-per-file style of app/server/bot_middleware.py). __init__(self, app, max_bytes: int, path_prefixes: tuple[str, ...] = ("/hook/", "/api/v1/hook/")) (both mount points the webhook route is actually exposed at - /hook/* via api/v1/router.py's legacy_router and /api/v1/hook/* via its v1_router, confirmed by reading app/api/router.py and app/api/v1/router.py). dispatch(): if the request path starts with one of path_prefixes, read the content-length header (no await request.body() call, so a rejected request's body is never buffered/read off the ASGI receive channel); if present, parseable as int, and greater than max_bytes, return JSONResponse(status_code=413, content={"detail": "Request body too large"}) directly without calling call_next (matches the detail key convention used throughout webhooks.py/aws_sns.py, not the rate limiter's differently-shaped message key). Otherwise call call_next(request) unchanged. Explicitly out of scope/accepted limitation: a request with NO content-length header (chunked transfer-encoding) is not capped by this check - flagged below.
10. app/server/server.py: import MaxBodySizeMiddleware and register it via handler.add_middleware(MaxBodySizeMiddleware, max_bytes=app_settings.WEBHOOK_MAX_BODY_BYTES) alongside the existing CORSMiddleware registration.
11. New file app/tests/unit/server/test_max_body_size_middleware.py (mirrors test_bot_middleware.py's MagicMock-request/AsyncMock-call_next style): unit tests for dispatch() - oversized /hook/... request short-circuits to 413 without calling call_next; request under the cap on /hook/... calls call_next and returns its response; a request to a non-/hook path is never capped regardless of content-length; missing/non-integer content-length header does not raise and falls through to call_next (fail-open on a malformed header, not fail-closed - documented behavior).
12. app/tests/unit/server/test_server.py: add test_max_body_size_middleware_configured, mirroring test_cors_middleware_configured - asserts a MaxBodySizeMiddleware entry exists in server.handler.user_middleware with kwargs["max_bytes"] == server.app_settings.WEBHOOK_MAX_BODY_BYTES.
13. app/tests/api/v1/test_webhooks.py: add test_handle_webhook_rejects_oversized_body using create_test_app(webhooks.router, middlewares=[(MaxBodySizeMiddleware, {"max_bytes": <small threshold>})]) (per the documented middlewares= parameter already supported by app/utils/tests.py::create_test_app), POST a body exceeding the threshold, assert 413 and that mock_get_webhook/downstream processing were never invoked; add a companion small-body-still-succeeds test with the same middleware wired in, to prove no regression for legitimate payloads.

AC-to-step-to-test traceability:
- AC#1 (SNS validation unconditional + invalid-signature test) <- steps 1-2 <- test_validate_sns_payload_rejects_invalid_signature_outside_production (new) + existing test_validate_sns_payload_signature_verification_failure (still green).
- AC#2 (zero e.__class__/f-string exception-interpolation hits, forced exception -> generic 500) <- steps 5-7 <- extended assertions on test_validate_sns_payload_signature_verification_failure/_invalid_message_type/_invalid_signature_version/_invalid_signature_url/_unexpected_exception + repo-wide grep check.
- AC#3 (oversized bodies rejected) <- steps 8-10 <- test_max_body_size_middleware.py (new, unit) + test_handle_webhook_rejects_oversized_body (new, route-level) + test_max_body_size_middleware_configured (wiring).
- DoD#1 (tests pass; legitimate flows still succeed) <- steps 3-4 (e2e fixtures kept green) + step 13's companion small-body test + a full uv run pytest tests run.
- DoD#2 (PR references SEC-6 and decisions/security.md) <- PR description, not code.

Test matrix:
- Happy path: valid small webhook body under the cap -> 200 (existing test_handle_webhook + new companion test).
- Boundary: body size exactly at max_bytes -> allowed; one byte over -> 413 (unit test on middleware).
- Failure/security: invalid SNS signature rejected in a non-production environment (new); forced validator exception yields a generic detail with no exception class/message text (extended existing tests); malformed/missing content-length header fails open to call_next rather than crashing (unit test).
- Non-regression: all 3 existing non-SNS e2e payload-variety cases (simple_text, access_request, generic_webhook) untouched by both changes; SNS-shaped e2e cases (cloudwatch alarm, budget, subscription confirmation) all keep the disabled-validation fixture so they still hit their Slack-posting code path in tests.

Assumptions and doubts (each with how to verify):
- Assumes AWS SNS's actual publish size ceiling is 256 KiB, so a 262144-byte default cap cannot reject a real SNS notification - verify against current AWS SNS publish-limits documentation before merge (limits can change between AWS documentation revisions).
- Assumes the two webhook mount points (/hook/* bare and /api/v1/hook/*) found by reading app/api/router.py and app/api/v1/router.py are the only two paths serving this route today - verify with grep -rn "webhooks_router" app/api if any router wiring changes land before this merges.
- Assumes reviving infrastructure/security/settings.py::SecuritySettings/get_security_settings() (currently zero callers repo-wide) is out of scope and the new field belongs on the live, already-wired AppSettings instead - flagging for human confirmation; if the team wants security-domain settings consolidated there instead, this step should move before merge, not after.
- Accepts as a known, documented limitation that a request with no content-length header (e.g. chunked transfer-encoding) is not body-size-capped by this middleware (Starlette/FastAPI already fully buffers the body before any dependency can inspect it, so only a pre-body ASGI-layer check like this middleware's content-length inspection works at all without a bigger streaming-receive-wrapper change) - acceptable for Phase 0 given AWS SNS and this app's own webhook callers always send content-length; a true streaming byte-counting guard is out of scope here and would be its own follow-up if ever needed.
- Assumes no terraform/CI change is required (no new required env var - WEBHOOK_MAX_BODY_BYTES has a safe default and is not deployment-blocking); verified by confirming AppSettings' other defaulted fields (e.g. LOG_LEVEL) are not set explicitly in terraform/templates either.

Blast radius and rollback:
- All changes are additive-safe or purely subtractive-of-information; a single git revert of the PR fully restores prior behavior (env-gated SNS skip, verbose exception detail, no body cap) with no data migration, no terraform change, and no required env var - safe to revert at any time.
- Worst case if shipped wrong: (a) SNS-everywhere - if AWS ever changes/rotates in a way sns_message_validator can't yet validate, real CloudWatch/budget alerts could start 500ing in all environments instead of only production; mitigated by DoD#1's manual/smoke check of a real webhook post-deploy. (b) Body cap - a legitimate sender occasionally posting a body over 256 KiB would start getting 413s; extremely unlikely given SNS's own ceiling and this bot's simple JSON payloads, and instantly revertible. (c) Generic 500 detail - pure information reduction, no functional risk.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-24 14:00
---
Restructured per human direction (2026-07-24): the day-1-infeasible 'reject any generic webhook without a valid HMAC' requirement (former AC#2) removed from this Phase-0 task and re-homed to Phase 4 as TASK-47 (HMAC + secure-by-default issuance) and TASK-48 (monitor-then-enforce migration), with TASK-46 adding Phase-1 origin observability in m-0. decisions/security.md Webhooks clause amended to a tiered trust model; the generic-webhook gap is now risk-accepted in writing (m-0 exit) until TASK-48 closes it. This task remains a single manageable PR: SNS-everywhere + exception-leak removal + body-size cap on the webhook ingress path.
---
<!-- COMMENTS:END -->
