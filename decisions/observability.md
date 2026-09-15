---
status: Accepted
date: 2026-07-06
applies: target
scope: Structured logging, secret redaction, and request correlation.
---

# Observability

## Context

The pieces exist separately today — structlog is configured with UTC timestamps and redaction installed, a correlation helper exists but no middleware calls it, and uvicorn/stdlib logs bypass the pipeline entirely. This record merges the three concerns because they only work as one pipeline.

## Decision

**Logging:** structlog, JSONL to stdout, one processor chain: level filter → `merge_contextvars` → logger name → UTC ISO timestamps → callsite → exception rendering → **redaction** → JSON render. Stdlib/uvicorn logs route through `ProcessorFormatter` with a matching foreign chain — one shape for the whole stream. Levels: DEBUG diagnostics, INFO state changes, WARNING degraded-but-handled, ERROR failed work, CRITICAL boot-fatal.

**Exceptions render once.** A traceback appears only inside the structured event (the JSON `exception` field) — never also as raw multi-line text on stdout/stderr. `ProcessorFormatter` renders `exc_info` into the event once and then clears `record.exc_info`/`exc_text` (`keep_exc_info=False` is the default); a competing root handler that still calls `logging.basicConfig(format="%(message)s")` re-appends `formatException` after the JSON line, producing the duplicate. Closing that gap is folded into the `ProcessorFormatter` migration (TASK-28.2), not a separate pipeline.

**Alerting keys on structured fields, never on free text.** Metric filters and alarms match JSON fields in the log body (`{ ($.level = "error") || ($.level = "critical") }`, `{ $.event = "..." }` — values are case-sensitive and structlog renders levels lowercase), not a substring/regex over the raw line ([CloudWatch Logs filter pattern syntax](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/matching-terms-json-log-events.html)). Level-less raw lines — dangling tracebacks, uvicorn's plain-text access lines — inflate a free-text alarm the moment they slip through. Expected-volume events must not be bumped to WARNING just to make a text filter see them; WARNING still means degraded-but-handled, per the level definitions above.

**Health-check traffic is classified, never dropped.** `/version`/`/health` are polled by the ALB target group and the Route53 health check ([health-checks.md](health-checks.md)), which is expected, already-budgeted background volume — not a defect to silence. Per OWASP's logging guidance, known monitoring traffic must never be excluded from logs, only flagged. Once uvicorn access logs route through the pipeline (TASK-28), a narrow `logging.Filter` on `uvicorn.access` downgrades **exact** liveness-check hits (`GET`, path in `{/version, /health}`, status `200`, no query string) to DEBUG or tags them `event_type=healthcheck`; any other method, status, path, or query string on those routes logs unchanged at INFO+, so probing/fuzzing stays visible.

**Redaction:** a deny-list, key-name-based processor (`token`, `secret`, `password`/`passwd`/`pwd`, `authorization`, `api_key`, `credentials`, `signature`, `session*`, `*_token`…) that **recursively** walks nested dicts/lists, replacing values with `***REDACTED***`. Installed in the chain, so it cannot be skipped per-call. Extension via a `redaction_extra_keys` setting. Redaction of key-named fields is the enforceable guarantee; not logging secrets in free-text messages remains a review rule (don't interpolate payloads into message strings).

**Failure logs carry diagnostic shape, not payloads.** When an outbound call fails on a payload we built or rewrote (for example a Slack `invalid_blocks` rejection), log the provider's error code/details plus the payload's shape — counts, offending index, field lengths, before/after our own transformations — never the payload text itself. This is the same boundary as the review rule above, applied to failure paths specifically: diagnose from shape, not content.

**Correlation:** one ASGI middleware, first in the stack: accept a valid inbound `traceparent`/`X-Request-ID`, else generate a UUIDv4; **bind it to `contextvars` as `request_id`** (one name, everywhere); echo `X-Request-ID` on responses; include it in problem-details bodies. Malformed inbound IDs are silently replaced (injection defense). Platform transports bind the same key at their inbound boundary; queue messages and outbox events carry it so consumers re-bind it. `request_id` is correlation only — it changes on every redelivered request and is **never** used as an idempotency key ([reliability.md](reliability.md)).

The audit trail for security events (auth failures, dev-bypass use, authz denials) uses the same pipeline with a dedicated logger name — separable downstream without a second stack.

## Consequences

- `grep request_id=<id>` reconstructs a request across HTTP, Slack, events, and queue consumers — the actual payoff of all three pieces landing together.
- Key-name redaction can't catch secrets in prose; we accept that boundary and enforce the half that's enforceable.

## Checks

- Pipeline test: a nested `{"config": {"api_token": "x"}}` logs as redacted; uvicorn access line renders as JSON.
- Middleware tests: generated/echoed/forwarded/malformed `X-Request-ID` cases; `request_id` present on a log line emitted inside a route.
- Timestamps are UTC ISO-8601 on every line, structlog-native and foreign (stdlib/uvicorn); UTC is set explicitly (`TimeStamper(fmt="iso", utc=True)`), not inherited from the library default ([`structlog.processors.TimeStamper`](https://www.structlog.org/en/stable/api.html#structlog.processors.TimeStamper) defaults `utc=True`, but the default must not be relied on silently).
- An exception logged in production mode (JSON renderer) yields exactly one line across stdout and stderr — no raw `formatException` text trailing the structured event (the stdlib root handler writes to stderr, where the duplicate was reproduced).

## Migration

Ticket: middleware/edge trio + logging pipeline (TASK-28), with logging split out into TASK-28.1 (lifespan `slack_provider_start_skipped` fix) and TASK-28.2 (route stdlib/uvicorn/`slack_sdk` logs through structlog's `ProcessorFormatter`; TASK-28.2 now also owns the duplicate-traceback fix as its AC#6). TASK-28.3 carves the `request_id` correlation middleware out of TASK-28's step 1. TASK-94 moves the SRE Bot's CloudWatch error/warning alarms from free-text regex to JSON field matching, and depends on TASK-28.2 (a stdlib/uvicorn line has no JSON body to match until it routes through the pipeline). TASK-95 adds provider-error and payload-shape diagnostics to webhook Slack posting failures. Tolerated until closed: uncorrelated HTTP logs, `correlation_id` naming in the old helper, uvicorn access logs unclassified (health-check hits not yet distinguished from real traffic), stdlib/uvicorn lines emitted outside the pipeline — `logging.basicConfig(format="%(message)s")` instead of a `ProcessorFormatter` with matching `foreign_pre_chain` ([structlog stdlib guide](https://www.structlog.org/en/stable/standard-library.html)) — since uvicorn installs its own `uvicorn`/`uvicorn.access` handlers with `propagate=False` by default ([uvicorn `config.py`](https://github.com/encode/uvicorn/blob/master/uvicorn/config.py)), so those lines carry no timestamp, level, or logger name; duplicate raw tracebacks alongside the structured `exception` field; and CloudWatch alarms still matching on free text.

**Changes:**
- 2026-09-15: corrected Context and Migration to state redaction is installed (TASK-8); Checks now require UTC to be set explicitly, not inherited from the `TimeStamper` default; Migration's tolerated list swaps "uninstalled redaction"/"local-time timestamps" for the real remaining gap — stdlib/uvicorn logs bypassing the pipeline (TASK-28.2); TASK-28.1 tracks the separate lifespan start-log bug.
- 2026-09-15: added three rules — exceptions render once (JSON `exception` field only, not also a raw trailing traceback), alerting keys on structured JSON fields rather than free text, and failure logs carry provider-error/payload-shape diagnostics rather than payload content. Extended Migration: TASK-28.2 also owns the duplicate-traceback fix; TASK-28.3 carves out the `request_id` middleware; TASK-94 moves CloudWatch alarms to JSON field matching; TASK-95 adds Slack posting-failure diagnostics. Verified against structlog and AWS CloudWatch Logs docs (see Checks/Migration links); no existing rule was overridden.
