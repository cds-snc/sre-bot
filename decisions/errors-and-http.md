---
status: Accepted
date: 2026-07-06
applies: target
scope: How OperationResult and exceptions become HTTP responses.
---

# Errors at the HTTP Edge

## Context

Routes currently raise bare `HTTPException` with ad-hoc detail strings, including 5xx responses that leak exception class names and messages to callers. The design goal: one total mapping, one wire format, no internals on the wire.

## Decision

**Wire format:** RFC 9457 `application/problem+json` for every non-2xx, with `type` (`urn:problem:<slug>`), `title`, `status`, `detail`, and `request_id` (from [observability.md](observability.md) correlation).

**One helper:** `operation_result_to_response(result, request_id)` in `app/server/`, used by every HTTP handler. The status map is total:

| OperationStatus | HTTP |
| --- | --- |
| `SUCCESS` | 200/201/204 per route |
| `NOT_FOUND` | 404 |
| `TRANSIENT_ERROR` | 503 + `Retry-After` when `retry_after` present |
| `PERMANENT_ERROR` | 400 (or 409/422 per `error_code`) |
| `UNAUTHORIZED` | 401 (`UNAUTHENTICATED`) / 403 (`FORBIDDEN`) |

**Exception handlers registered once** on the app: validation errors → 422 problem details; uncaught exceptions → 500 with a generic body (`detail` says nothing about the exception) and a full server-side log with traceback. 4xx `detail` is actionable for the caller; 5xx `detail` is generic, always.

Rate-limit rejections follow the same format: 429 problem details with `Retry-After` ([security.md](security.md)).

## Consequences

- Callers get one error grammar; dashboards key on `type` + `request_id`.
- The webhook routes' current `f"...{e}"` 500s are eliminated by the uncaught-exception handler — leaking becomes impossible rather than discouraged.

## Checks

- Tests: each status maps as tabled; an injected exception yields a 500 whose body contains no exception text; 429 carries `Retry-After`.
- grep: no `HTTPException(status_code=5` with interpolated exception text.

## Migration

Ticket: middleware/edge trio (with correlation + security headers). Tolerated until closed: bare `HTTPException` in existing routes; new routes must use the helper from day one.
