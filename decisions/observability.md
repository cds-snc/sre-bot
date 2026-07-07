---
status: Accepted
date: 2026-07-06
applies: target
scope: Structured logging, secret redaction, and request correlation.
---

# Observability

## Context

The pieces exist separately today — structlog is configured, a redaction function exists but is not installed in the pipeline, a correlation helper exists but no middleware calls it, and uvicorn logs bypass the JSON pipeline entirely. This record merges the three concerns because they only work as one pipeline.

## Decision

**Logging:** structlog, JSONL to stdout, one processor chain: level filter → `merge_contextvars` → logger name → UTC ISO timestamps → callsite → exception rendering → **redaction** → JSON render. Stdlib/uvicorn logs route through `ProcessorFormatter` with a matching foreign chain — one shape for the whole stream. Levels: DEBUG diagnostics, INFO state changes, WARNING degraded-but-handled, ERROR failed work, CRITICAL boot-fatal.

**Redaction:** a deny-list, key-name-based processor (`token`, `secret`, `password`/`passwd`/`pwd`, `authorization`, `api_key`, `credentials`, `signature`, `session*`, `*_token`…) that **recursively** walks nested dicts/lists, replacing values with `***REDACTED***`. Installed in the chain, so it cannot be skipped per-call. Extension via a `redaction_extra_keys` setting. Redaction of key-named fields is the enforceable guarantee; not logging secrets in free-text messages remains a review rule (don't interpolate payloads into message strings).

**Correlation:** one ASGI middleware, first in the stack: accept a valid inbound `traceparent`/`X-Request-ID`, else generate a UUIDv4; **bind it to `contextvars` as `request_id`** (one name, everywhere); echo `X-Request-ID` on responses; include it in problem-details bodies. Malformed inbound IDs are silently replaced (injection defense). Platform transports bind the same key at their inbound boundary; queue messages and outbox events carry it so consumers re-bind it. `request_id` is correlation only — it changes on every redelivered request and is **never** used as an idempotency key ([reliability.md](reliability.md)).

The audit trail for security events (auth failures, dev-bypass use, authz denials) uses the same pipeline with a dedicated logger name — separable downstream without a second stack.

## Consequences

- `grep request_id=<id>` reconstructs a request across HTTP, Slack, events, and queue consumers — the actual payoff of all three pieces landing together.
- Key-name redaction can't catch secrets in prose; we accept that boundary and enforce the half that's enforceable.

## Checks

- Pipeline test: a nested `{"config": {"api_token": "x"}}` logs as redacted; uvicorn access line renders as JSON.
- Middleware tests: generated/echoed/forwarded/malformed `X-Request-ID` cases; `request_id` present on a log line emitted inside a route.
- Timestamps are UTC ISO-8601.

## Migration

Ticket: middleware/edge trio + logging pipeline. Tolerated until closed: uncorrelated HTTP logs, uninstalled redaction, local-time timestamps, `correlation_id` naming in the old helper.
