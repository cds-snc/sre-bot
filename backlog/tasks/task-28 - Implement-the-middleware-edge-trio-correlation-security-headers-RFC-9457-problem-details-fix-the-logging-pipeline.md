---
id: TASK-28
title: >-
  Implement the middleware/edge trio: correlation, security headers, RFC 9457
  problem details; fix the logging pipeline
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-09-15 14:08'
labels:
  - infrastructure
  - phase-4
  - observability
milestone: m-4
dependencies:
  - TASK-8
references:
  - decisions/observability.md
  - decisions/errors-and-http.md
  - decisions/security.md
  - 'https://github.com/cds-snc/sre-bot/issues/1282'
priority: high
ordinal: 28000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/observability.md and decisions/errors-and-http.md. Today app/server/server.py has only CORS middleware: no correlation, no security headers, no problem-details; the correlation helper binds correlation_id (wrong name) and nothing calls it; uvicorn logs bypass the JSON pipeline; timestamps are local time.

Steps:
1. Correlation middleware, FIRST in the stack: accept valid inbound traceparent/X-Request-ID else generate UUIDv4; bind to contextvars as request_id (rename from correlation_id everywhere - one name); echo X-Request-ID on responses; silently replace malformed inbound IDs.
2. Security-headers middleware on every response: Strict-Transport-Security (max-age >= 1 year, includeSubDomains), X-Content-Type-Options: nosniff, Content-Security-Policy: default-src none, frame-ancestors none, Referrer-Policy, restrictive Permissions-Policy (exact set in decisions/security.md Headers).
3. RFC 9457: operation_result_to_response(result, request_id) helper in app/server/ with the total status map from decisions/errors-and-http.md; app-level exception handlers: validation -> 422 problem details; uncaught -> 500 generic body + full server-side traceback log. No exception text on the wire.
4. Logging pipeline: ProcessorFormatter foreign chain for stdlib/uvicorn, UTC ISO timestamps, logger names, redaction already installed (task-8).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Middleware tests: generated/echoed/forwarded/malformed X-Request-ID cases; request_id present on a log line emitted inside a route
- [ ] #2 Every response carries the five security headers (test)
- [ ] #3 Each OperationStatus maps per the table; an injected exception yields a 500 whose body contains no exception text; 429/503 carry Retry-After when applicable (tests)
- [ ] #4 A uvicorn access line renders as JSON through the pipeline; timestamps are UTC ISO-8601
- [ ] #5 grep: no HTTPException(status_code=5 with interpolated exception text; no correlation_id binding remains
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Tests green; new routes documented to use the helper from day one
- [ ] #2 PR references decisions/observability.md and decisions/errors-and-http.md
<!-- DOD:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-29 20:03
---
decisions/observability.md now documents a health-check log classification nuance relevant to this ticket's step 4 (uvicorn->pipeline unification): per OWASP, health-check/monitoring traffic (ALB + Route53 hits on /version, /health) must be classified (event_type=healthcheck or downgraded to DEBUG), never dropped from access logs. Only exact liveness-check matches (GET, path, 200, no query string) qualify; anything else on those routes stays at INFO+ so probing/fuzzing remains visible. See decisions/health-checks.md for the infra-side layering this traffic comes from.
---

created: 2026-09-15 14:08
---
2026-09-15: investigation of odd local-dev startup logs, recorded as subtasks so planning starts from the findings:
- TASK-28.1: lifespan.py:305-313 logs slack_provider_start_skipped reason=test_environment after every SUCCESSFUL Slack start, in all environments (misplaced else). Independent of the middleware trio.
- TASK-28.2: step 4 of this task (ProcessorFormatter foreign chain for stdlib/uvicorn/slack_sdk, logger names), with root causes, uvicorn 0.41.0 logger config, launch-path options and test starting points.
Corrections to this description: timestamps are already UTC (structlog 25.5.0 TimeStamper defaults to utc=True; output ends in Z), so "timestamps are local time" is stale. Steps 1-3 (correlation middleware, security headers, RFC 9457) still need their own decomposition under the size gate.
Local-dev "Invalid HTTP request received" / "HEAD / 405" were investigated and are not app defects (VS Code port-forward / browser TLS probe to the plain-HTTP port). Human decision: leave as is.
---
<!-- COMMENTS:END -->
