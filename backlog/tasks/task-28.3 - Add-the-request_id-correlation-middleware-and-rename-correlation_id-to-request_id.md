---
id: TASK-28.3
title: >-
  Add the request_id correlation middleware and rename correlation_id to
  request_id
status: To Do
assignee: []
created_date: '2026-09-15 19:39'
labels:
  - infrastructure
  - phase-4
  - observability
milestone: m-4
dependencies: []
references:
  - decisions/observability.md
  - app/infrastructure/logging/context.py
  - app/server/server.py
parent_task_id: TASK-28
priority: high
ordinal: 210000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Carved out of TASK-28 step 1 on 2026-09-15. TASK-28 bundles four independent concerns and exceeds the single-PR size gate. Step 4 is already TASK-28.2. Steps 2 (security headers) and 3 (RFC 9457) stay in TASK-28.

Motivation (production incident 2026-09-15): one failed POST /hook/{webhook_id} produced four log records: legacy_api_endpoint_accessed (api/router.py:29), webhook_posting_error (api/v1/routes/webhooks.py:146), webhook_invocation (:154) and the uvicorn access line. Nothing linked them except timestamps and ip_address, so reconstructing a single request required a time-window search on one log stream.

Scope (decisions/observability.md "Correlation"):
- One ASGI middleware, FIRST in the stack (app/server/server.py). Accept a valid inbound traceparent or X-Request-ID, otherwise generate a UUIDv4. Silently replace malformed inbound IDs.
- Bind the ID to structlog contextvars as request_id and clear it per request, so nothing leaks between requests. Echo X-Request-ID on the response.
- Rename correlation_id to request_id in app/infrastructure/logging/context.py (bind_request_context, get_correlation_id, set_correlation_id; currently :76, :94) and its callers. Re-grep audit/event models for correlation_id and list any remaining use with an owner.

Planning doubt to verify: uvicorn emits access log records outside the ASGI app's contextvars scope, so access lines may not carry request_id even after TASK-28.2 routes them through the pipeline. Confirm empirically. If so, decide between a request-completed log event from the middleware (method, path, status, duration, request_id) and accepting uncorrelated access lines.

Out of scope: security headers and RFC 9457 problem details (TASK-28), and the logging pipeline and ProcessorFormatter (TASK-28.2).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Middleware tests cover generated, echoed (valid X-Request-ID), forwarded (valid traceparent) and malformed-replaced IDs, and every response carries X-Request-ID
- [ ] #2 A log line emitted inside a route carries request_id, and request_id does not leak between sequential requests (test)
- [ ] #3 The correlation middleware is first in the middleware stack (test)
- [ ] #4 rg finds no correlation_id binding left in app/, or each remaining use is listed in notes with an owner
- [ ] #5 The uvicorn access-line correlation question is verified empirically, with the decision recorded in notes
<!-- AC:END -->
