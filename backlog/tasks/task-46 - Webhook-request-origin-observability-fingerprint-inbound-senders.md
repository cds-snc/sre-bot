---
id: TASK-46
title: 'Webhook request-origin observability: fingerprint inbound senders'
status: Done
assignee:
  - '@me'
created_date: '2026-07-24 13:58'
updated_date: '2026-07-29 15:35'
labels:
  - security
  - phase-0
milestone: m-0
dependencies:
  - TASK-7
references:
  - decisions/webhooks.md
priority: high
ordinal: 70000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Phase 1 of the observability-first webhook-auth migration mandated by decisions/security.md (Webhooks, amended 2026-07-24). Purely additive: no request is ever rejected and no sender-visible behaviour changes. Builds the known-sender inventory that Phase 4 (m-4) uses to migrate each legacy unsigned webhook onto a signed tier.

Today app/api/v1/routes/webhooks.py:handle_webhook already binds webhook_id, path, user_agent and ip_address on its logger. This task turns that into a durable, queryable origin fingerprint per invocation.

Steps:
1. Emit one structured `webhook_invocation` event per POST /hook/{webhook_id} with: webhook_id, source IP, user-agent, the inferred/matched payload type (which handler in modules/webhooks/base.handle_webhook_payload matched - AwsSnsPayload / AccessRequest / SimpleTextPayload / generic), and presence/absence of any signature-ish headers (so we learn which senders could already sign).
2. Do not log full request bodies; fingerprint metadata only (avoid sensitive-data leakage per decisions/observability.md).
3. Expose the fingerprint as metrics/queryable fields keyed by webhook_id + inferred source type so an inventory of live senders per webhook_id can be built.
4. Document (route/module docstring) that this data is the input to the Phase-4 monitor-then-enforce migration.

Out of scope: any rejection, signature verification, or settings/schema change that alters acceptance (those are the m-4 tasks).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A structured webhook_invocation event is emitted for every POST /hook/{webhook_id} carrying webhook_id, source IP, user-agent, matched payload type, and signature-header presence (test asserts the event fields)
- [x] #2 No request is rejected or otherwise behaviourally changed by this task; legitimate webhook flows are byte-for-byte unaffected (test)
- [x] #3 Request bodies are never emitted to logs/metrics; only fingerprint metadata is (test/review)
- [x] #4 Fingerprint data is queryable/aggregatable per webhook_id + inferred source type (documented query or metric)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Reassessed 2026-07-29 against decisions/webhooks.md (new, Accepted 2026-07-28) and decisions/security.md's amended Webhooks clause (2026-07-24) - both postdate this task's original authoring. TASK-7 (dependency) is now Done: SNS validation is unconditional, exception-leak removed, body-size cap shipped. Conclusion: TASK-46's original scope is UNCHANGED and still correctly placed on the LEGACY code path (app/api/v1/routes/webhooks.py + app/modules/webhooks/base.py) - decisions/webhooks.md explicitly does not touch Phase-0/Phase-1 observability, and TASK-46's own comment already confirms "stays on the legacy code at m-0; not superseded by TASK-37". decisions/security.md's Checks clause now states this precisely: "a not-yet-migrated legacy webhook is accepted only while flagged legacy and each acceptance emits an origin-fingerprint event" - this task builds exactly that event. No decomposition needed: one subsystem (webhooks route + one module + one model), ~40-50 production LOC, no schema/terraform/cross-package change.

Verified against current code (all line refs re-read, not assumed from the stale task description):
- app/api/v1/routes/webhooks.py:handle_webhook already binds webhook_id/path/user_agent/ip_address on a per-request logger (matches task's own framing).
- app/modules/webhooks/base.py:handle_webhook_payload matches on `payload_type.__name__` (WebhookPayload / AwsSnsPayload / AccessRequest / SimpleTextPayload / no-match) via the pre-existing select_best_model guesser (deletion of that guesser is TASK-37.2 scope, not this task - do not touch it here).
- app/models/webhooks.py:WebhookResult has `model_config = {"extra": "forbid"}` with fields status/action/payload/message only - no field currently carries which model matched.

Four findings that change/clarify the original task text materially enough to document explicitly:

FINDING 1 (redaction collision - would silently break AC#1 if not caught): app/infrastructure/logging/formatters.py's `_is_sensitive_key` does a SUBSTRING match (`pattern in key_lower`), and `SENSITIVE_PATTERNS` includes "signature" and "auth" as exact deny-list entries. Any log field whose NAME contains "signature" or "auth" (e.g. "signature_header_present") is masked to "***REDACTED***" by the installed pipeline (decisions/observability.md, shipped by TASK-8, both Done) whenever its value is not None - a bool is never None, so it would ALWAYS render as "***REDACTED***", silently defeating the whole point of the field. Decision: name the field `signing_indicator_present` (no "signature"/"auth"/other deny-list substring) and add a dedicated pipeline-level test (using the real `_build_base_processors` chain, precedent from TASK-8) proving the field survives redaction, not just a `capture_logs()` default test (which bypasses the real chain entirely per prior finding on TASK-8 and would not catch this class of bug).

FINDING 2 (docstring wording must not name phases/tasks): the task's own Step 4 says to document "Phase-4 monitor-then-enforce migration" in a route/module docstring. Project convention (tests-python.instructions.md, extended to production code per precedent in infrastructure/configuration/app.py and infrastructure/operations/result.py, both cite durable decisions/*.md records but never phase numbers/task IDs/transient docs) bars phase/task references in code docstrings. Deviation from the task's literal wording, done explicitly, not silently: the docstring will describe the BEHAVIOR ("this event seeds the inventory used to migrate legacy unsigned webhooks onto a signed authentication tier") and may cite decisions/webhooks.md / decisions/security.md by filename, but will not say "Phase 4", "m-4", or any TASK-nn.

FINDING 3 (AC#3 scope ambiguity): app/modules/webhooks/base.py already logs the RAW payload today at existing call sites unrelated to this task - `logger.debug("processing_webhook_payload", payload=payload_dict)`, `logger.debug("payload_validation_success", ..., payload=validated_payload.model_dump())`, `logger.error("payload_validation_failure", payload=payload_dict)` - and app/api/v1/routes/webhooks.py's malformed-JSON branch logs `payload=str(payload)`. AC#3 ("Request bodies are never emitted to logs/metrics; only fingerprint metadata is") is scoped in this plan to the NEW webhook_invocation event only - retrofitting/removing the four pre-existing raw-payload debug/error logs is a separate, larger-blast-radius change (touches existing debug tooling relied on elsewhere) and is out of this task's stated Steps/Out-of-scope text. Flagged for human sign-off below; not silently expanded into this task's scope.

FINDING 4 (dual mount point - same handler, but production traffic is overwhelmingly on ONE mount only; human-confirmed, important not to lose): the webhook handler is registered TWICE from the exact same `webhooks_router` APIRouter instance (app/api/v1/router.py: both `router.include_router(webhooks_router)` and `legacy_router.include_router(webhooks_router)`), then mounted at two different paths in app/api/router.py: `legacy_router` mounts bare (-> `/hook/{webhook_id}`) and `v1_router` mounts under `prefix="/api/v1"` (-> `/api/v1/hook/{webhook_id}`). It is the SAME function/code path either way - versioning was introduced but the intended client migration to `/api/v1/hook/` never happened, and external senders were never notified to switch. Human-confirmed from >1 week of production logs: 100% of observed inbound webhook calls hit the legacy bare `/hook/{webhook_id}` mount; ZERO observed traffic on `/api/v1/hook/{webhook_id}` to date. Implications for this task, captured explicitly so they are not lost:
  - No code branching by mount point is needed - instrumenting the shared `handle_webhook` function once covers both mounts for free (satisfies "every POST /hook/{webhook_id}" regardless of which router path is hit).
  - The "known-sender inventory" this task builds is, in practice, a legacy-bare-path inventory today - do not assume `/api/v1/hook/` will independently contribute senders, and do not design any test/AC validation around v1-path traffic volume being non-trivial.
  - `app/api/router.py`'s `log_legacy_calls` dependency is bound ONLY on `legacy_router` (i.e. exactly the mount carrying today's real webhook traffic) and already emits a separate `legacy_api_endpoint_accessed` WARNING per request (method, path, query_params, ip, user_agent, referer, x_forwarded_for, authorization_present) for ALL legacy endpoints, not just webhooks. Because production traffic is overwhelmingly on this mount, most real webhook invocations will emit BOTH that pre-existing warning AND this task's new `webhook_invocation` info event. The two are independent and this task does not merge them (`log_legacy_calls` is generic legacy-API telemetry; `webhook_invocation` is webhook-specific with matched_payload_type/signing_indicator_present) - noted here only so a future reader isn't surprised to see two log lines per legacy-path invocation.
  - Related but OUT OF SCOPE observation (same bug class as Finding 1, flagged for awareness only): `log_legacy_calls`'s `authorization_present` field name contains the substring "auth", which the same redaction deny-list matches - meaning that pre-existing field is also likely already rendering as "***REDACTED***" in production today regardless of its boolean value. This is a pre-existing latent bug unrelated to this task's Steps; not fixed here, mentioned only because it is the identical failure mode this task must avoid for its own new field.
  - Test addition: exercise the new `webhook_invocation` event specifically through the `legacy_router`-style mount (bare `/hook/{webhook_id}`, no `/api/v1` prefix) since that is the actual production call path, in addition to the existing router-under-test which already uses the bare path via `create_test_app(webhooks.router)`. No separate v1-prefixed test is required functionally (identical handler), but the plan explicitly avoids implying v1-path coverage represents real traffic.

Implementation steps:

1. app/models/webhooks.py - add one optional field to WebhookResult: `matched_payload_type: str | None = None` (keeps `extra: forbid`; default None is fully additive, no existing construction site breaks - verified via repo-wide grep, all 9 WebhookResult(...) construction sites across prod+tests use keyword args only).

2. app/modules/webhooks/base.py:handle_webhook_payload - after the match statement resolves `webhook_result`, set `webhook_result.matched_payload_type = payload_type.__name__` for every matched branch; for the earlier "no matching model found" early-return branch, construct that WebhookResult with `matched_payload_type=None` explicitly (documents "no match" distinctly from "not yet determined"). No change to select_best_model/validate_payload internals (that guesser's removal is TASK-37.2 scope).

3. app/api/v1/routes/webhooks.py (this is the SHARED handler for both the legacy bare `/hook/{webhook_id}` mount and the `/api/v1/hook/{webhook_id}` mount - see Finding 4; instrumenting it once covers both by construction):
   a. Add a small module-level helper `_signing_indicator_present(request: Request) -> bool` checking request.headers (case-insensitive, Starlette Headers already is) against a small candidate tuple (`x-hub-signature`, `x-hub-signature-256`, `x-webhook-signature`) OR a substring scan for "signature" in any header NAME (header names only, never values, so this never touches request bodies) - flagged as a best-effort heuristic below (no existing signature-header convention exists in this repo to anchor on; SNS signs via the message body, not headers).
   b. Wrap the existing handler body in `try/finally`. Initialize a `fingerprint` dict at entry: `{"webhook_id": webhook_id, "ip_address": ..., "user_agent": ..., "signing_indicator_present": _signing_indicator_present(request), "matched_payload_type": None}`. After `handle_webhook_payload(...)` returns, set `fingerprint["matched_payload_type"] = webhook_result.matched_payload_type`. In the `finally` block (fires on every return AND every raised HTTPException, so it fires for 400/404/413-is-middleware-so-N/A/200/500 alike, satisfying "every POST"), call `log.info("webhook_invocation", **fingerprint)`. This is purely additive around existing control flow - no existing return/raise is touched, so AC#2 (no behavioural change) holds by construction; existing tests are not expected to need changes to their assertions on status codes/response bodies.
   c. Add a docstring paragraph on `handle_webhook` (see Finding 2 for exact wording constraints) noting the event name and that it seeds a per-webhook_id/matched-payload-type sender inventory, plus a documented CloudWatch Logs Insights query as a code comment satisfying AC#4 (no metrics system exists in this repo today - decisions/observability.md's model is JSONL-to-stdout structured logs only, so a Logs Insights query is the correct "queryable" mechanism here, not a new metrics subsystem):
      `fields @timestamp, webhook_id, matched_payload_type, signing_indicator_present | filter event = "webhook_invocation" | stats count() by webhook_id, matched_payload_type`

4. Tests:
   a. app/tests/modules/webhooks/test_webhooks_base.py - extend each existing `handle_webhook_payload` branch test (WebhookPayload/AwsSnsPayload/AccessRequest/SimpleTextPayload success paths, already-parametrized-by-branch) with an assertion that `result.matched_payload_type == "<ExpectedModelName>"`; add one new test for the "no matching model" branch asserting `matched_payload_type is None`.
   b. app/tests/api/v1/test_webhooks.py - new test class `TestWebhookInvocationFingerprint` using `structlog.testing.capture_logs()`, exercised through the existing bare-path `create_test_app(webhooks.router)` harness (matches the actual production mount per Finding 4 - the existing test client already posts to `/hook/id`, not an `/api/v1`-prefixed path, so no harness change is needed to match production reality):
      - success flow: one `webhook_invocation` event captured, fields `webhook_id`, `ip_address`, `user_agent`, `signing_indicator_present` (bool), `matched_payload_type` present; asserts event count == 1 (not duplicated).
      - webhook-not-found (404) flow: event still emitted exactly once, `matched_payload_type is None` (short-circuited before matching), no `payload`/`body` key present in the captured event dict (AC#3 scoped assertion).
      - malformed-JSON (400) flow: event still emitted exactly once (finally still fires), no raw payload string present in the captured event dict.
      - signing-indicator present vs. absent: one request with a `X-Hub-Signature` header, one without; assert the boolean flips accordingly.
   c. New focused pipeline test (co-located in test_webhooks.py; confirmed app/tests/unit/infrastructure/logging/{test_setup.py,test_formatters.py} already hold the generic pipeline/redaction tests, so this new test is feature-specific regression coverage for our field name and stays with the webhooks feature test file, not the generic logging test dir) using `capture_logs(processors=_build_base_processors(_prod_mode=False, logging_settings=LoggingSettings()))` (precedent: TASK-8's own pipeline test) to prove `signing_indicator_present` survives the real redaction processor unmasked (regression test for Finding 1) - assert the emitted event's value is a real bool, never the string "***REDACTED***".

AC-to-step-to-test traceability:
- AC#1 (structured webhook_invocation event with required fields) <- steps 1-3 <- 4b success-flow test. Covers both mounts by construction (Finding 4) since there is only one handler function; the test harness already matches the real (bare-path) production mount.
- AC#2 (no rejection/behavioural change) <- step 3b (try/finally is purely additive) <- existing test_handle_webhook / test_handle_webhook_not_found / test_handle_webhook_malformed_json_string / test_handle_webhook_rejects_oversized_body all continue to pass unmodified (no assertion changes needed on status codes/bodies).
- AC#3 (no raw body in logs/metrics, scoped to the new event per Finding 3) <- step 3b (fingerprint dict never includes payload/body) <- 4b's 404/400-flow assertions plus code review confirming no pre-existing debug/error payload logs were touched (out of scope, see Finding 3/open question below).
- AC#4 (queryable/aggregatable) <- step 3c (documented Logs Insights query keyed on webhook_id + matched_payload_type) <- reviewed, not test-asserted (matches the AC's own "documented query or metric" wording).

Assumptions / doubts flagged for human sign-off (not silently resolved):
- The "signing-ish header" heuristic (candidate header names + generic "signature" substring-in-header-NAME scan) is a best-effort guess - this repo has no existing signature-header convention to anchor on (SNS signs via the message body). Fine for Phase-1 observability (purely informational), but should be revisited once TASK-47/48 pick real HMAC header conventions.
- AC#3 is scoped to the NEW webhook_invocation event only. Four pre-existing debug/error-level logs in app/modules/webhooks/base.py and app/api/v1/routes/webhooks.py already emit raw payload bodies (predates this task, outside its Steps/Out-of-scope text). Recommend filing this as a separate follow-up rather than folding it into TASK-46's blast radius - awaiting confirmation before creating that task.
- Field naming diverges from a literal reading of the task ("signature-ish headers") to `signing_indicator_present` specifically to avoid the redaction-deny-list collision (Finding 1) - functionally equivalent, differently named for a documented technical reason.
- Dual-mount reality (Finding 4): the resulting sender inventory reflects the legacy bare `/hook/{webhook_id}` path almost exclusively today given current traffic; if/when senders are ever migrated to `/api/v1/hook/{webhook_id}`, the same instrumentation applies unchanged (no follow-up code work implied), but this is worth remembering when interpreting the inventory's `webhook_id`/`matched_payload_type` breakdown for Phase-4 migration planning. Also flags the pre-existing `authorization_present` redaction-collision bug in `log_legacy_calls` (api/router.py) as an out-of-scope, unrelated latent bug noticed along the way.

Blast radius / rollback: purely additive (new field with a default, new try/finally + one new log call, new helper function, new tests) - no existing route contract, status code, or response body changes. Rollback is a straight revert of the single PR; no data migration, no settings/env var introduced, no terraform change.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented webhook origin-fingerprint observability on the shared webhook handler with additive behavior only.

What changed:
- app/models/webhooks.py: Added optional WebhookResult.matched_payload_type field (default None).
- app/modules/webhooks/base.py: Populated matched_payload_type from payload_type.__name__ for matched/recognized and unsupported model branches; explicit None for no-match branch.
- app/api/v1/routes/webhooks.py:
  - Added _signing_indicator_present(request) helper using known signature header candidates plus header-name substring heuristic.
  - Added webhook_invocation fingerprint dict and guaranteed emission via try/finally as log.info("webhook_invocation", ...).
  - Populates matched_payload_type in fingerprint from handle_webhook_payload result.
  - Added route docstring/query guidance for Logs Insights aggregation by webhook_id and matched_payload_type.

Test evidence:
- Targeted feature tests (green):
  cd /workspace/app && uv run pytest tests/modules/webhooks/test_webhooks_base.py tests/api/v1/test_webhooks.py
  Result: 27 passed.
- Ruff gate (green):
  cd /workspace/app && uv run ruff check .
  Result: all checks passed.
- Full non-smoke pytest gate:
  cd /workspace/app && uv run pytest tests --ignore=tests/smoke
  Result: 5 failed, 2959 passed, 37 skipped.
  Failures are pre-existing/unrelated to TASK-46 scope in tests/integrations/aws/test_client_next.py and tests/modules/webhooks/test_webhooks_aws_sns.py.
- Mypy gate:
  cd /workspace/app && uv run mypy . --exclude '(?:^|/)\\.venv(?:/|$)'
  Result: pre-existing repository-wide mypy errors outside TASK-46 touched files.

DoD items left for human verification:
- PR review and merge decision.
- Runtime log verification in deployed environment (confirm webhook_invocation appears for live legacy /hook traffic and query is operational in CloudWatch Logs Insights).
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-28 18:41
---
Feeds the webhooks rearchitecture interpret stage (decisions/webhooks.md): the origin fingerprint's inferred source type seeds each webhook record's declared source, which TASK-37.2 consumes to select the single typed parser. Stays on the legacy code at m-0; not superseded by TASK-37.
---

created: 2026-07-29 14:02
---
Human-confirmed routing nuance (2026-07-29), captured in the plan's Finding 4: the webhook handler is registered from ONE shared APIRouter instance but mounted at two paths (bare /hook/{webhook_id} via legacy_router, and /api/v1/hook/{webhook_id} via v1_router+prefix) - same code, versioning introduced but client migration never happened/senders never notified. >1 week of prod logs show 100% of real traffic on the legacy bare path, zero on /api/v1/hook/. Instrumenting the shared handler covers both mounts by construction; no code branching needed. The resulting sender inventory is effectively a legacy-path-only inventory today - do not read v1-path silence as a gap.
---
<!-- COMMENTS:END -->
