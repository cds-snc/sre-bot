---
id: TASK-25.8
title: >-
  Bring Notify onto the outbound-client contract: JWT-authenticated client
  factory and classify_notify_error; revoke_api_key moves to its webhook caller
status: Done
assignee: []
created_date: 2026-09-18 16:51
updated_date: '2026-11-27T21:21:00Z'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies: []
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/notify/client.py
  - app/modules/webhooks/patterns/aws_sns_notification/api_key_detected.py
  - decisions/plugin-architecture.md
  - https://github.com/cds-snc/sre-bot/issues/1604
parent_task_id: TASK-25
priority: medium
ordinal: 241000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Created 2026-09-18 (human decision: every vendor conforms to decisions/outbound-clients.md).

TODAY (verified 2026-09-18). app/integrations/notify/client.py (167 lines) holds:
- JWT creation (create_jwt_token, create_authorization_header);
- a raw requests.post helper (post_event, timeout=60, no retry policy);
- a business operation, revoke_api_key(api_key, api_type, github_repo, source).
It reads settings at import time (notify_settings = get_notify_settings()) and also imports infrastructure.configuration.app. It has no classify_notify_error.

CONSUMER (re-grep): modules/webhooks/patterns/aws_sns_notification/api_key_detected.py, the only one. TASK-37 (webhooks rearchitecture) later rewrites that caller, so keep its change minimal.

TARGET. The vendor package exports a factory for an authenticated HTTP client (JWT auth, explicit timeout, retry configured once) and classify_notify_error. revoke_api_key moves next to its caller as an adapter-shaped function that does try/except + classify. Revoking a key is idempotent at the provider (verify and record this); if it is not, name the replay protection.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 integrations/notify/ exports only the client factory (JWT auth, explicit timeout, retry configured once) and classify_notify_error; no business operation and no import-time settings read remain
- [x] #2 revoke_api_key lives with its caller, calls the client inside try/except + classify_notify_error, and its replay behaviour is recorded
- [x] #3 Classification tests cover each mapped failure family plus one unmapped exception propagating; JWT header construction keeps its test coverage
- [x] #4 ruff, mypy, pytest tests --ignore=tests/smoke and make check-vendor-package-contract pass, with output recorded in notes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLAN v2 (2026-11-27; program-scope assessment A1-A8 below, awaiting human approval; supersedes v1). Single PR on branch task-25.8-notify-outbound-client from origin/main 776ba97d (doc-11 row 22.1a). Must merge before W4 (TASK-37.3, row 22.4), whose Notify handler awaits this client. First commit f91e343f closes TASK-37.2.1 and TASK-37.2.4.

DESCRIPTION CORRECTIONS (verified 2026-11-27 against origin/main)
- client.py is 140 lines and no longer reads settings at import or imports infrastructure.configuration (TASK-111 moved it to integrations/notify/settings.py, read at use). AC #1's import-time clause is pinned by a test, not changed by code.
- The legacy log.bind(api_key=...) is masked by the redaction processor (observability.md: key name api_key). The leak is free text: api_key_detected.py logs the raw SNS Message (which holds the token) as message= when its regex fails.

CALL SITES (path:line, origin/main 776ba97d; re-grep at start)
- app/integrations/notify/client.py:16 epoch_seconds, :21 create_jwt_token, :59 create_authorization_header, :86 post_event (requests.post), :97 revoke_api_key.
- app/integrations/notify/__init__.py:3-17 re-exports the five; settings.py:37-68 NotifySettings (timeout_seconds only); app/config/base.toml:161-165 [notify].
- app/modules/webhooks/patterns/aws_sns_notification/api_key_detected.py:6 import, :41 parse-failure log with message=, :66 notify.revoke_api_key (the only consumer).
- Caller chain is sync: api/v1/routes/webhooks.py:45 def handle_webhook (FastAPI threadpool, no running loop) -> modules/webhooks/base.py:103 -> aws_sns.py:52 -> aws_sns_notification.py:249 -> handle_api_key_detected.
- Tests: tests/integrations/notify/test_notify_client.py (JWT, header, post_event, revoke cases); tests/modules/webhooks/patterns/aws_sns_notifications/test_api_key_detected.py:39-102 (patch integrations.notify.revoke_api_key); tests/integration/legacy_surface/test_webhook_route_aws_sns_surface.py:130-221 (Notify faked with requests_mock at the HTTP edge; 201/200/500 parametrised).
- Unchanged importers of the slice: server/configuration/host_configuration.py:42, the settings tests and the lifespan vendor-slice tests.

PROVIDER FACTS (read 2026-11-27 from the public source)
- POST /sre-tools/api-key-revoke (cds-snc/notification-api app/api_key/rest.py revoke_api_keys): 400 on a bad payload; 200 {"result":"ok"} when no key matches (any lookup exception); 201 after expire_api_key, update_compromised_api_key_info and send_api_key_revocation_email.
- Replay: get_api_key_by_secret (app/dao/api_key_dao.py) does not filter expired keys, so a replay answers 201 again, moves expiry_date to the replay time, overwrites compromised_key_info (time_of_revocation, url, source) and emails the service owners again. The key's revoked state is idempotent; the side effects are not. Notify offers no idempotency key.
- SNS (https://docs.aws.amazon.com/sns/latest/dg/SendMessageToHttp.prepare.html, https://docs.aws.amazon.com/sns/latest/dg/sns-message-delivery-retries.html): an HTTP/S delivery times out after about 15 s; a timeout, a 5xx or a 429 is retried, by default up to three times 20 s apart. The legacy route answers 500 when a Slack post fails, so one notification can revoke up to four times.
- Notify's own SDK (alphagov notifications-python-client base.py:71, _create_request_objects) mints a JWT per request; it is sync on requests and built for service API keys, so it is not adopted (A3).
- Auth: requires_sre_auth -> decode_jwt_token (notifications-python-client authentication.py): HS256, iss = the SRE client id, iat within +/-30 s (__bound__ = 30). A JWT is valid for about 30 s, so it is minted per request.

DECISIONS
D1 Factory. build_notify_client(settings=None, *, timeout_seconds=None, connect_retries=None) -> httpx.AsyncClient: base_url = tenant.api_url, auth = a private httpx.Auth subclass whose auth_flow signs a fresh JWT per request (typ JWT, alg HS256, iss = sre_user_name, iat = now) and sets Authorization: Bearer, timeout = the override or [notify] timeout_seconds (per attempt), transport = httpx.AsyncHTTPTransport(retries = the override or [notify] connect_retries). The optional per-call overrides are built ahead for TASK-37.3, whose handler runs under the inbox's deadline and owns the durable retry (the one-retry-point rule W2b adds to outbound-clients.md; Slack precedent); every other caller keeps the configured values. Tenant None raises ValueError (programmer-error guard; the caller checks the tenant first, TASK-25.6 D5). No network I/O at construction; the caller opens the client per call with async with. Basis: outbound-clients.md item 1 (httpx retries only connections that never opened), TASK-25.6 and 25.10.1 precedents, httpx custom auth (https://www.python-httpx.org/advanced/authentication/#custom-authentication-schemes). The JWT helper is private, not exported: the package exports factories, the classifier and settings only.
D2 Setting. [notify] connect_retries (int, ge=0, default 2) in settings.py (Keys docstring) and base.toml, mirroring [opsgenie] and [openai] (configuration.md: tuning is a typed setting with a default). timeout_seconds keeps its 60.0 default, so the legacy path's timing is unchanged.
D3 Classifier. classify_notify_error(exc) -> (OperationStatus, error_code, retry_after), the Opsgenie table: 401 UNAUTHORIZED/UNAUTHENTICATED, 403 UNAUTHORIZED/FORBIDDEN, 404 NOT_FOUND, 429 TRANSIENT/RATE_LIMITED with Retry-After seconds or None, 5xx TRANSIENT/SERVER_ERROR, other 4xx (Notify's 400 invalid payload) PERMANENT/HTTP_ERROR, httpx.TimeoutException TRANSIENT/TIMEOUT, other httpx.HTTPError TRANSIENT/CONNECTION_ERROR, json.JSONDecodeError PERMANENT/INVALID_RESPONSE; anything else re-raised. No new ErrorCode member.
D4 revoke_api_key moves to its caller, api_key_detected.py (kept in that module, not a new file: the patterns directory is walked and imported at boot). A sync revoke_api_key(api_key, api_type, github_repo, source) -> Literal["revoked", "not_found", "error"] runs a module-local async helper with one asyncio.run (the route is sync and runs in the threadpool, as modules/incident/on_call.py does for Opsgenie). The helper checks the tenant (None -> "error", warning revoke_api_key_not_configured), then posts {token, type, url, source} to /sre-tools/api-key-revoke inside try/except (httpx.HTTPError) with raise_for_status -> classify_notify_error -> "error" and an error log with status and error_code; 201 -> "revoked", 200 -> "not_found", any other 2xx -> "error" with the status code. Unexpected exceptions propagate. The handler's three messages are unchanged. Marked TODO(TASK-37.5) (migration.md rule 7): deleted with the legacy patterns; TASK-37.3 writes the registered handler on the same client.
D5 Logging (OWASP Logging Cheat Sheet, data to exclude; observability.md review rule and "Failure logs carry diagnostic shape, not payloads"). The revocation logs bind api_key_name, service_id, api_type, github_repo and source, never the token (key-name redaction stays the backstop, not the mechanism). The parse-failure warning logs message_length instead of message. Q-A (recommended: fix here): modules/webhooks/base.py:60 (ERROR, the whole payload of a webhook that validates as no known type) and :76 (DEBUG, every payload; production logs at INFO) log raw payloads, which observability.md forbids and its Migration does not tolerate. Fix in this PR as a plan-named legacy edit (migration.md rule 1, TODO(TASK-37.5)): both log the payload's shape (top-level keys, serialised size) instead. Alternative: tolerate under observability.md Migration until TASK-37.5 deletes the module.
D6 Replay behaviour (AC #2), recorded in outbound-clients.md and the task notes: the transport retries only a connection that never opened, so the client never re-sends a revocation; Notify's endpoint is not side-effect idempotent (facts above). Legacy path: SNS redelivers a notification that failed or timed out, up to three times (facts above), and each redelivery revokes again (owner email repeated, revocation time moved). Q-B (recommended: tolerate and record): reliability.md requires every mutating webhook handler to be idempotent through a conditional claim, and its Migration does not list the legacy route, which repeats its Slack posts as well as the revocation on a redelivery: this PR adds that tolerance to reliability.md Migration until the cutover (TASK-37.4.3), naming the replay protection that ends it (the inbox's conditional insert keyed on the SNS MessageId, W3, and the handler acting once per delivery id, TASK-37.3). Alternative: an IdempotencyStore claim keyed on the MessageId in the legacy handler now (about 40 LOC and tests, discarded at the cutover); not recommended: the key stays revoked on a replay, the harm is extra owner emails and a later revocation time, and leaks with a redelivery are rare. Replay protection: TASK-37.3's handler runs from the inbox item and acts once per delivery id (webhooks.md); this PR adds to webhooks.md that the once-per-delivery rule is what keeps a redelivery from emailing the owners again.
D8 Timeout (A4). [notify] timeout_seconds stays 60 s although outbound-clients.md asks attempts x timeout to fit the caller's deadline (SNS's 15 s): a revocation that lands late still revokes the key (the sync handler keeps running after SNS gives up), whereas a 10 s abort leaves a live key and an answer SNS does not retry. Recorded under outbound-clients.md Migration as the legacy revocation's tolerated divergence until the cutover; TASK-37.3's handler passes its own timeout under [webhooks] inline_processing_deadline_seconds through the D1 overrides, and the inbox sweeper is its retry point.
D7 Program scope. cloud-portability.md: Notify is a Path B vendor client, not a hosting contract, so no contract or in-memory fake here; TASK-37.3's handler port gets its fake. sdk-typing.md: httpx is typed; no wrapper module (the Auth subclass is httpx's documented extension point, not a wrapper around the handle). W2b (#1896) also edits outbound-clients.md (one-retry-point paragraph and a Changes line) and integrations/slack/client.py (not touched here): whichever merges second rebases and keeps both Changes lines. No terraform, IAM, SSM or env-name change, so no deploy-checks.

STEPS (TDD: failing tests first for each)
1. integrations/notify/settings.py and config/base.toml: connect_retries (D2).
2. integrations/notify/client.py: only build_notify_client, classify_notify_error and private helpers (JWT auth flow, Retry-After); requests, the logger, epoch_seconds, create_jwt_token, create_authorization_header, post_event and revoke_api_key deleted. __init__.py exports build_notify_client, classify_notify_error, NotifySettings, NotifyTenant, get_notify_settings.
3. modules/webhooks/patterns/aws_sns_notification/api_key_detected.py: D4 and D5.
4. decisions/outbound-clients.md: factory item 1 gains a short-lived-credentials line (a token valid for seconds is minted per request by the client's auth hook, never fixed in its headers; httpx custom auth, GC Notify's 30 s bound and its SDK cited); Migration: the Notify line removed, the legacy revocation's 60 s timeout added (D8); Changes 2026-11-27 (TASK-25.8). decisions/reliability.md: Migration gains the legacy webhook route's non-idempotent redelivery tolerance (Q-B) and a Changes line. decisions/webhooks.md: one sentence at the handlers-by-id rule (D6). With Q-A's alternative only: decisions/observability.md Migration gains the base.py tolerance.
4b. With Q-A as recommended: modules/webhooks/base.py:60 and :76 log the payload's shape (D5), with a test that no payload value reaches the log.
5. Task notes: provider facts, replay record, gate output; doc-11 row 22.1a and row 22.4's hand-off (the overrides, once per delivery id, no token in logs, TASK-161 absorbed, A7).

TESTS (app/tests; httpx.MockTransport at the HTTP edge; async tests with the repo's asyncio marker)
- tests/unit/integrations/notify/test_notify_client_build.py: base_url; timeout and AsyncHTTPTransport retries from settings and from the overrides (recording stand-in, as for Opsgenie); tenant None -> ValueError; no socket opened at construction; JWT: Authorization Bearer token decodes with the secret, header typ JWT and alg HS256, claims iss and iat, and a second request gets a fresh token (time stepped). AC #1, #3.
- tests/unit/integrations/notify/test_notify_client_classify_error.py: 401, 403, 404, 429 with and without Retry-After, 400, 500, timeout, connect error, JSONDecodeError, and a KeyError propagating. AC #3.
- tests/unit/integrations/notify/test_notify_package_exports.py: __all__ is the allowed set; importing the package reads no settings (get_notify_settings not called). AC #1.
- tests/unit/integrations/notify/test_notify_settings_load.py: connect_retries default and ge=0 validation. AC #1.
- tests/modules/webhooks/patterns/aws_sns_notifications/test_api_key_detected.py: patch target moves to the module's revoke_api_key; new cases for revoke_api_key over MockTransport (behind a stand-in for build_notify_client): 201 revoked, 200 not_found, 202 error, 400, 500 and timeout classified to error, tenant None -> error with no request, unexpected exception propagates, the request body and path, and no log event carries the token (structlog capture, the parse-failure warning included). AC #2.
- tests/integration/legacy_surface/test_webhook_route_aws_sns_surface.py and its conftest: the Notify edge fake moves from requests_mock to an httpx.MockTransport recorder installed at httpx.AsyncHTTPTransport (an edge target for check-test-seams); assertions unchanged (one POST to /sre-tools/api-key-revoke; 201/200/500 messages). AC #2.
- tests/integrations/notify/test_notify_client.py deleted (cases moved above).

AC TRACE: #1 steps 1-2, build, exports and settings tests; #2 steps 3-4, D6, revoke and surface tests; #3 classify and build (JWT) tests; #4 gates.
GATES: ruff and targeted tests during; make check-vendor-package-contract, check-import-contracts, check-settings-key-ownership, check-package-shape, check-test-seams (unlocked); at the end, once each and in sequence under /tmp/sre-bot-heavy-gates.lock: mypy, then pytest tests --ignore=tests/smoke in the background. Output recorded in notes.

SIZE: 9 production files (client.py, __init__.py, settings.py, base.toml, api_key_detected.py, modules/webhooks/base.py with Q-A, outbound-clients.md, reliability.md, webhooks.md), about 180 production LOC; one vendor, its one consumer and two legacy log lines. Within the gate.

ASSUMPTIONS AND HOW TO VERIFY
- No running loop on the legacy path: handle_webhook is a sync def (verified); a test drives revoke_api_key from sync code.
- The surface pin's Notify fake can move to httpx without a new seam entry: check-test-seams treats httpx (outside features/capabilities/modules) as an edge; run it.
- No other importer of the removed names: rg at start (only the caller and the old test today).
- PyJWT and httpx are existing direct dependencies (pyproject: PyJWT>=2.15.1, httpx>=0.28.1): no new dependency, so the cooldown rule does not apply.

BLAST RADIUS AND ROLLBACK
- Live path: a GitHub-reported leaked Notify key arriving by SNS. Ships wrong: the revocation answers "error", the leak channel reads "could not be revoked" with the on-call group cc'd, and the key stays live until revoked by hand. The request Notify receives is unchanged (same path, body and Bearer JWT). The behaviour changes: up to 2 retries of a connection that never opened, httpx instead of requests, and no token in the parse-failure log. One git revert restores it, with no ordering constraint; no data, settings or infrastructure change.
- Change notice: none. An internal refactor: no caller, operator or contributor sees or acts on it (change-notice.md "changes that don't count"); the Notify team receives the same request.

PROGRAM-SCOPE ASSESSMENT (2026-11-27, human-requested; ADRs, doc-11, doc-15, doc-17, doc-18, doc-19, both checkouts' tasks; doc-16 is in neither checkout)
A1 Per-call overrides (D1). ADR: W2b's "one retry point" paragraph (outbound-clients.md on #1896, not yet on main): a caller owning durable retry builds its handles with its own per-attempt timeout. Prior: TASK-37.2.3 gave the Slack factories optional timeout_seconds and retries (human, 2026-11-26). Upcoming: TASK-37.3's handler runs under W3's [webhooks] inline_processing_deadline_seconds with the sweeper's backoff as its retry (TASK-37.2.2 D4, AC #7). Settled: the overrides are built ahead; not a question.
A2 Per-request JWT (D1). ADR: outbound-clients.md item 1 says credentials refresh themselves before they expire, but names only AWS and Google; a self-issued token valid for seconds is a gap of wording, not of rule. Prior: TASK-180's credential_source refreshes Google tokens. Practice: httpx custom auth_flow (https://www.python-httpx.org/advanced/authentication/); Notify's SDK mints per request. Fix: step 4's line.
A3 SDK or httpx. sdk-typing.md and outbound-clients.md prefer the vendor's SDK primitives and async ports for async consumers. Notify's SDK is sync on requests and parses service API keys, not the SRE client id; httpx is already a direct dependency (no cooldown issue). Settled: httpx.
A4 Timeout (D8). Conflict with outbound-clients.md's "fit the caller's deadline" on the legacy path, resolved in favour of revoking the key; recorded as a tolerated divergence until the cutover.
A5 Legacy idempotency (Q-B). Gap: reliability.md's idempotency rule has no Migration entry for the legacy webhook route. Upcoming: W3's inbox insert on the SNS MessageId and TASK-37.3's handler close it at TASK-37.4.3. Practice: SNS is at-least-once and subscribers dedupe on a key (AWS SNS retries docs; Powertools idempotency, https://docs.aws.amazon.com/powertools/python/latest/utilities/idempotency/), which the inbox implements (reliability.md "The webhook inbox is a use of the conditional write").
A6 Payload logs (Q-A). Gap: observability.md forbids payload text in logs and tolerates no exception; base.py logs it. Upcoming: TASK-37.5 deletes the module (row 22.9); TASK-95 (legacy route Slack-failure diagnostics, "never log payload text") has no doc-11 row. OWASP and the ADR agree, so the code is what is wrong.
A7 Owner of the revocation. TASK-161 (To Do, no doc-11 row) carves the leak response into a feature package registered through the webhooks extension point with its [notify_api_key_leak] settings class: the same package TASK-37.3 AC #5 and #11 creates. Hand-off (doc-11 row 22.4, added at 37.3's planning since W3 edits that task file): TASK-37.3 absorbs TASK-161's AC #2 (the settings class moves into the feature, still reading [notify_api_key_leak]) and TASK-161 is archived as superseded. This PR keeps revoke_api_key in the legacy module (migration.md rules 1 and 6). TASK-95: assessed at TASK-37.4.2's planning (shadow-mode diagnostics) or archived with TASK-37.5; noted in doc-11.
A8 Lane A. No Lane A task or doc touches integrations/notify; doc-15 and doc-19 have no Notify, replay or JWT item; doc-17's replay item is the Calendar's. Shared file: outbound-clients.md with W2b (#1896); keep both sides on rebase.

DOMAIN-MODEL EVOLUTION: not applicable (no entity added or reshaped; one setting).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-27: plan v2 approved (human) with both recommendations: Q-A fix base.py's raw payload logs here (rule-1 legacy edit, TODO(TASK-37.5)); Q-B tolerate the legacy route's non-idempotent redelivery under reliability.md Migration until TASK-37.4.3.

2026-11-27 implementation (plan v2):
- AC #1: integrations/notify/ exports build_notify_client, classify_notify_error, NotifySettings, NotifyTenant, get_notify_settings (test_notify_package_exports.py). The factory signs a fresh HS256 JWT per request in a private httpx.Auth flow, sets the per-attempt timeout and AsyncHTTPTransport(retries=connect_retries) once, takes optional per-call timeout_seconds and connect_retries, and opens no connection (test_notify_client_build.py). [notify] connect_retries (default 2, ge=0) in settings.py and base.toml. No import-time settings read: pinned by tests/unit/server/test_server_app_import_vendor_settings_lazy.py, which imports the package and the legacy caller.
- AC #2: revoke_api_key lives in modules/webhooks/patterns/aws_sns_notification/api_key_detected.py (TODO(TASK-37.5)), one asyncio.run from the sync handler; httpx errors go through classify_notify_error; 201 revoked, 200 not_found, other 2xx error; no tenant sends nothing; unexpected exceptions propagate (test_webhooks_notify_revocation_revoke.py). Replay recorded in the docstring, outbound-clients.md, reliability.md Migration and webhooks.md: the transport never re-sends a sent request; Notify's revoke endpoint answers a repeat with 201, re-emails the service owners and moves the revocation time (no idempotency key; cds-snc/notification-api app/api_key/rest.py and app/dao/api_key_dao.py); the legacy route's SNS redelivery is tolerated until TASK-37.4.3; replay protection is the inbox's insert on the SNS MessageId and TASK-37.3's handler acting once per delivery id.
- AC #3: classify tests cover 401, 403, 404, 429 with and without Retry-After, 400, 418, 5xx, timeout, connect error, JSONDecodeError and a propagating KeyError; JWT coverage: header alg HS256 and typ JWT, iss and iat claims, signature checked against the secret and refused with another, a fresh token per request.
- Logging (D5, Q-A): the revocation logs name the key by api_key_name and service_id, never its value; the parse-failure warning logs message_length; modules/webhooks/base.py's three payload logs (payload_validation_success DEBUG, payload_validation_failure ERROR, processing_webhook_payload DEBUG) log payload_keys and payload_bytes instead of the payload (the success line was not named in the plan; same defect, fixed with the other two). Tests assert no token or payload value reaches the events.
- Legacy pin: the SNS surface pin's Notify edge moved from requests_mock to an httpx.MockTransport recorder installed at httpx.AsyncHTTPTransport; assertions unchanged (one POST to /sre-tools/api-key-revoke with the same body; 201/200/500 messages). tests/integrations/notify/test_notify_client.py deleted (cases moved). test_configuration_files_vendors.py pins the new base.toml key.
- ADRs: outbound-clients.md (short-lived-credentials rule; Notify Migration line replaced by the legacy revocation's 60 s timeout divergence; Changes), reliability.md (legacy webhook route's missing dedupe tolerated until TASK-37.4.3; Changes), webhooks.md (once-per-delivery is load-bearing for the Notify handler; Changes), configuration.md ([notify] connect_retries; Changes).
- Pre-existing, not fixed: tests/modules/webhooks/test_webhooks_aws_sns_notification.py registers dummy patterns on the module-global NOTIFICATION_HANDLERS without removing them, so the SNS surface pin fails (400) when that file runs before it in one session; the full suite's order (tests/integration before tests/modules) hides it. Deleted with the legacy patterns by TASK-37.5.
- Gates during the work: ruff check and format clean; make check-vendor-package-contract (OK, 13 baselined), check-import-contracts (16 kept, 0 broken), check-settings-key-ownership (OK), check-package-shape (OK, 2 baselined), check-test-seams (OK, 47 strict and 12 legacy baselined); targeted tests 1577 passed. Full mypy under the lock: Found 33 errors in 11 files (checked 495 source files), all pre-existing in files this PR does not touch.

Full pytest under the lock: cd app && flock /tmp/sre-bot-heavy-gates.lock uv run pytest tests --ignore=tests/smoke -> 8495 passed, 224 warnings in 271.10s (exit 0). AC #4 checked: ruff, mypy (33 pre-existing, none in touched files), pytest and make check-vendor-package-contract pass. No human post-merge check: Done is set by the closing commands with this PR.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-24 20:11

---

2026-09-24 citation fix: decisions/layers.md, capability-packages.md and events.md were deleted and replaced by decisions/plugin-architecture.md (six layers: server, features, capabilities, infrastructure, integrations, contracts). Read those references in this task as plugin-architecture.md. Path A infrastructure capabilities are now split: hosting contracts (storage, coordination, queue, secrets) live in app/contracts/ with implementations in app/infrastructure/; workplace systems and shared business engines live in app/capabilities/. Path B adapters are unchanged (outbound-clients.md). revoke_api_key moves to its caller. Today that is the modules/webhooks SNS pattern. When TASK-37 rebuilds webhooks as a capability, the key-revocation reaction belongs to the feature that registers a handler through the webhooks extension point (TASK-37.5), not the capability core.

---

created: 2026-11-25T20:53:00Z

---

2026-11-25 (TASK-168 re-cut, human-approved): TASK-37.3 now depends on this task. 37.3 ports the api_key_detected Notify key revocation into a registered webhooks handler in its own package (async httpx, run from the inbox item and keyed on the delivery id), and that handler calls this task's Notify contract client, not the legacy one, so this lands first (queued ahead in Lane B). No dependency change here.

---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Notify on the outbound-client contract: integrations/notify exports build_notify_client (httpx.AsyncClient, per-request HS256 JWT through httpx.Auth, per-attempt timeout, connect-only retries from [notify] connect_retries, optional per-call overrides) and classify_notify_error; revoke_api_key moved to the legacy SNS api_key_detected caller (one asyncio.run, same outcomes); the leaked key and raw webhook payloads no longer reach logs; replay recorded (Notify's revoke re-emails owners on a repeat; the legacy route's SNS redelivery is tolerated until TASK-37.4.3; the inbox acts once per delivery id). ADRs: outbound-clients, reliability, webhooks, configuration.
<!-- SECTION:FINAL_SUMMARY:END -->
