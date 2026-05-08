---
title: "Cross-Channel Correlation"
status: Accepted
type: Standard
tier: Tier-2
governance_domain: [application, operations]
concerns: [observability, architecture]
constrained_by: [layered-architecture.md, application-lifecycle.md, api-design-error-mapping.md, type-boundaries.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Cross-Channel Correlation

## Context and Problem Statement

The application processes inbound work from heterogeneous channels — HTTP requests (including Microsoft Teams events delivered via the Bot Framework HTTP endpoint and Slack events delivered via the HTTP Events API), Slack events delivered over a persistent WebSocket (Slack Socket Mode), scheduled background jobs, and queue consumers — and emits outbound side-effects (logs, traces, error responses, downstream HTTP calls). Each unit of work touches multiple modules: a handler calls a feature service, which calls an infrastructure provider, which calls a vendor client, which (often) emits a domain event consumed elsewhere. Without a single identifier that follows that unit of work end-to-end, an operator investigating a failure must reconstruct the call chain by timestamp, hostname, and guesswork.

The problem this record addresses: **what is the canonical per-request observability identifier, how is it generated and propagated across transport boundaries, and how does it appear in logs, traces, error bodies, and outbound calls?** The answer determines:

1. Whether one log query for a single ID retrieves every record produced while handling one inbound event, or whether operators must stitch records together by adjacent timestamps.
2. Whether the application interoperates with distributed-tracing systems (W3C Trace Context, OpenTelemetry) when those are eventually integrated, or carries a project-private identifier that must be reconciled at the integration point.
3. Whether the `request_id` extension member already required in problem-details error bodies has a definite source, or is left for each route to invent.
4. Whether background work, queue consumers, and outbound HTTP calls participate in the same correlation graph as the inbound request that triggered them.

**Constraints:**

- The application is asynchronous (FastAPI on Uvicorn). Per-request state must be carried through `await` chains and across `asyncio.Task` boundaries without leaking between concurrent requests.
- Logs go to stdout per the cloud-portability contract. Correlation identifiers are useful only if they appear on every log line; any logging configuration that omits them defeats the purpose.
- Problem-details error bodies (`application/problem+json`) carry a `request_id` extension member that callers may report back to operators. The value must be unambiguous and discoverable in logs.
- Inbound channels other than HTTP — Slack events delivered over Socket Mode's persistent WebSocket, scheduled jobs, queue messages — deliver work through the application without any HTTP request envelope; their entry points must establish a correlation context just as HTTP middleware does.
- Caller-supplied identifiers (an `X-Request-ID` from an upstream service, a `traceparent` from a tracing-aware caller) are useful for cross-service correlation but cannot be trusted blindly — malformed or hostile values must be rejected without contaminating internal logs.

**Non-goals:**

- This record does not pick the structured-logging library, log format, or output policy — those belong in a logging/observability decision. It specifies *that* the correlation identifier is bound to the logging context, not how the binding is rendered.
- This record does not adopt OpenTelemetry SDK instrumentation. It pins the identifier format to be **forward-compatible** with W3C Trace Context, but does not enable end-to-end span propagation today.
- This record does not govern **domain correlation identifiers** — durable UUIDs that identify long-lived business entities (e.g., an access request) and travel via Slack `private_metadata`, Teams Adaptive Card action data, or DynamoDB primary keys over hours or days. Those are feature-owned identifiers and carry domain semantics; the per-request correlation ID is shorter-lived and observability-only. The two coexist; one log line may carry both.
- This record does not specify rate-limiting, authentication, or PII-redaction policies. Those are separate concerns that may *consume* the correlation identifier (e.g., for abuse correlation) but do not define it.

## Considered Options

**Option 1 — Custom `X-Request-ID` only (UUID v4).** The host generates a UUID v4 per inbound HTTP request, accepts a caller-supplied `X-Request-ID` if validly formatted, binds it to log context, and echoes it on the response. No relationship to W3C Trace Context. Simple but project-private.

**Option 2 — W3C Trace Context (`traceparent`/`tracestate`) only.** The host parses `traceparent` if present and otherwise generates a fresh `trace-id`/`parent-id` per the W3C specification. Industry-standard, ready for OpenTelemetry adoption. Loses the human-readable UUID convention familiar to operators.

**Option 3 — Hybrid: UUID v4 wire form, W3C-compatible internally.** The host generates a 128-bit identifier formatted as UUID v4 (with hyphens) for log records, error bodies, and `X-Request-ID`. The same 128 bits are equivalent to a W3C `trace-id` (32 hex chars, no hyphens) under a trivial encoding swap. The host accepts both `traceparent` and `X-Request-ID` on inbound, generating fresh when neither is present.

**Option 4 — Inherit caller's identifier verbatim, generate only when absent.** No validation; whatever the caller sends becomes the identifier. Trivial to implement; opens the log stream to caller-controlled values (cardinality, injection, spoofing).

## Decision Outcome

**Chosen: Option 3 — UUID v4 wire form, W3C-compatible internally.**

The application generates a 128-bit random identifier per inbound unit of work and presents it on the wire and in logs as a UUID v4 string (with hyphens). On inbound HTTP it accepts and prefers a valid W3C `traceparent` (extracting the trace-id) or a valid caller `X-Request-ID`, generating a fresh value when neither is present. The chosen format is forward-compatible with W3C Trace Context and OpenTelemetry without requiring their adoption today; the binding mechanism is `contextvars`, which is async-safe and propagates through `asyncio.Task` boundaries.

### Identifier format

- **128-bit random value** generated as **UUID v4** per RFC 9562.
- **Wire form on responses and in error bodies:** standard 8-4-4-4-12 hyphenated hex, e.g., `550e8400-e29b-41d4-a716-446655440000`.
- **Wire form when interoperating with W3C Trace Context:** the same 128 bits with hyphens removed (32 hex chars) becomes a valid `trace-id` segment of a `traceparent` header.
- **One identifier per inbound unit of work.** A single HTTP request, a single Slack event delivery, a single queue-message handling, a single scheduled-job iteration each carry exactly one identifier from entry to exit.

UUID v7 (timestamp-prefixed, RFC 9562) was considered as an alternative for its log-locality benefits. It is acceptable as a future change — the wire format is identical to v4 — but is not chosen as the default because the locality benefit is small for log indexers and the timestamp leak (request start time recoverable from the identifier) is not desired without a deliberate decision.

### Inbound HTTP: header acceptance

A single ASGI middleware runs ahead of any route handler and establishes the correlation context. The acceptance order on each inbound request:

1. **`traceparent` header present and valid** (matches `^[0-9a-f]{2}-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$`). The `trace-id` segment becomes the `request_id` (re-formatted with hyphens). `tracestate` is preserved verbatim for the duration of the request and propagated unchanged on outbound calls.
2. **Otherwise, `X-Request-ID` header present and valid** (matches the UUID 8-4-4-4-12 pattern, case-insensitive). The value becomes `request_id`.
3. **Otherwise**, the host generates a fresh UUID v4.

Malformed `traceparent` or `X-Request-ID` values are **rejected silently** — the middleware logs a warning at the application level and proceeds as if the header were absent (generates a fresh identifier). The application does not echo malformed values into its own log stream.

### `contextvars` binding

The middleware binds the identifier into a module-level `ContextVar`:

```python
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
```

`ContextVar` is the async-safe carrier — each `asyncio.Task` created within the request inherits the value automatically. The variable is set on request entry and reset on request exit (using the token returned by `set()`); the symmetric reset prevents context bleed if a worker reuses the event loop across requests.

For structured logging, the canonical `structlog` integration is used: `structlog.contextvars.merge_contextvars` is configured as the first processor, so every log record emitted within the request automatically includes `request_id` (and any other context-bound fields). At request entry the middleware calls `clear_contextvars()` to ensure a clean slate, then `bind_contextvars(request_id=...)` to publish the identifier.

The middleware also stores the identifier on `request.state.request_id` for places where dependency-injected access is more idiomatic than reading `contextvars` directly (e.g., the error-mapping helper that constructs problem-details bodies).

### Outbound HTTP: response and request propagation

- **Every outbound response** carries `X-Request-ID: <uuid>` regardless of status code. Callers who report a `request_id` from the response body can also produce it from network-level captures.
- **Every outbound HTTP request** initiated within an inbound request carries:
  - `X-Request-ID: <uuid>` (the same value, for downstream services that follow the same convention).
  - `traceparent: 00-<trace-id-no-hyphens>-<parent-id>-01` (W3C compatible). The `parent-id` is a fresh 64-bit random value per outbound call; without a tracing SDK, the application emits a parent-id but does not maintain a span tree.
  - `tracestate` is propagated unchanged if it was received on inbound and is still relevant.

The propagation lives in the application's HTTP-client wrapper — feature code does not manage these headers manually. Calling the wrapper with no per-call configuration produces correctly correlated outbound requests by default.

### Other inbound channels

The HTTP middleware described above is the entry point for two delivery modes that happen to use HTTP: feature HTTP routes, and webhook-style platform deliveries that arrive as inbound HTTPS POSTs (Microsoft Teams events from the Bot Framework, Slack events when configured for the HTTP Events API). Other inbound channels do not pass through that middleware and establish their own correlation context at their respective entry points.

- **Slack Socket Mode.** When the Slack client is configured for Socket Mode, the SDK opens an outbound WebSocket to Slack and receives events on that persistent connection — there is no inbound HTTP request and no HTTP middleware in the path. Each event the SDK dispatches to a handler is one inbound unit of work. The handler's entry-point wrapper generates a fresh `request_id`, binds it to `contextvars`, runs the handler, and unbinds at the end. Slack does not carry a `traceparent` or `X-Request-ID` over Socket Mode; identifiers are always freshly generated. The Slack-supplied `event_id` (and other Slack identifiers like `team_id`, `channel_id`, `user_id`) are bound *additionally* into the log context to aid Slack-side correlation, but the `request_id` itself is the application's own UUID.
- **Background workers (scheduled jobs).** Each iteration of a scheduled loop opens a fresh correlation context. The job's runner generates a `request_id` at the start of the iteration, binds it to `contextvars`, runs the iteration body, and unbinds at the end. Boot does not carry a correlation identifier into the scheduled loop's first iteration.
- **Queue consumers.** Each message processed generates a fresh `request_id` at the start of the handler. If the producer included a `parent_request_id` field in the message metadata (e.g., an enqueue performed inside an HTTP request or a Slack Socket Mode handler), the consumer's middleware records `parent_request_id` as an *additional* context-bound field, bound alongside `request_id`. This preserves the producer→consumer link in logs without making the consumer's `request_id` equal to the producer's.

Outbound calls to Slack (e.g., `chat.postMessage`) always go to Slack's HTTP API, regardless of which inbound mode is in use; outbound HTTP propagation rules (above) apply unchanged.

### Inclusion in error responses

The problem-details error mapping helper reads `request_id` from `request.state.request_id` (or the contextvar as a fallback) and writes it as the `request_id` extension member of every `application/problem+json` body. The error body, the response header (`X-Request-ID`), and the log records all carry the identical value. A caller reporting a failure with the body's `request_id` lets operators retrieve every log line for that request with a single query.

### Identifier scope and lifetime

The correlation identifier is **observability-only**. It is not used as a database key, a cache key, an idempotency key, or a security token. It is not logged in places where personally identifiable information would be (the identifier itself is non-personal and safe to log; this rule is about not putting the identifier where it might be confused with one). Its lifetime is bounded by one inbound unit of work — the moment the response is sent (or the message is acknowledged), the identifier is released.

A separate, **domain-level correlation identifier** (e.g., the UUID of an access-request entity) lives in feature-owned domain models, may be stored in DynamoDB, and may travel through Slack `private_metadata` or Teams Adaptive Card action data over hours or days. The domain identifier and the per-request `request_id` are distinct fields; both appear in logs when both apply.

### Forward compatibility with distributed tracing

Choosing UUID v4 for the wire form keeps logs and error bodies human-readable today. Adopting OpenTelemetry later requires only:

- Generating the 128-bit value via the OTel SDK rather than `uuid.uuid4()` (the format is identical).
- Adding span instrumentation that uses the same `trace-id` (already W3C-compatible because UUID v4 is already 128 bits).
- Activating the OTel exporter for traces.

No wire-format break, no log-format break, no caller-visible change.

## Consequences

**Positive:**

- One identifier ties an inbound unit of work to every log record, every outbound call, every error body, and every operator query. Diagnosing a failure is `grep request_id <uuid>` rather than reconstructing a chain by timestamps.
- The identifier is a UUID — recognized by every operator, every log indexer, and every observability tool — without being project-private.
- W3C Trace Context compatibility is preserved without committing to OpenTelemetry now; if the application is later instrumented, the existing identifier carries forward unchanged.
- `contextvars` binding is async-safe, asyncio-native, and bleeds neither across concurrent requests nor across `asyncio.Task` boundaries within a request.
- Caller-supplied identifiers from upstream services are accepted *when valid* (improving cross-service correlation) and rejected *when malformed* (preventing log pollution and injection).

**Tradeoffs accepted:**

- Generating, validating, and binding the identifier on every inbound request adds a small per-request cost (microseconds). Acceptable given the diagnostic value.
- Producing both `X-Request-ID` and `traceparent` on outbound calls is two headers where one would suffice; downstream services that recognize neither lose nothing, and either header alone is sufficient for downstream correlation. The redundancy is intentional and bounded.
- Generating `parent-id` on outbound `traceparent` without a backing span tree is a "well-formed but informationally thin" `traceparent`. A proper tracing stack would replace this; until one exists, the parent-id is random per call. Acceptable because the trace-id (the field operators actually filter on) is correct.

**Risks:**

- A code path emits a log record from a context where `request_id` is not bound (e.g., a background task forgets to call `bind_contextvars` at its entry). The record lacks the identifier and cannot be correlated. Mitigation: every entry point (HTTP middleware, scheduled-job runner, queue-message handler) is reviewed for `bind_contextvars` setup; logs without `request_id` are flagged in operational dashboards.
- A caller submits a deliberately reused `X-Request-ID` to make multiple unrelated requests appear correlated. The middleware accepts the value (it is well-formed). Mitigation: the application logs additional discriminators (client IP, account/principal, timestamp); cardinality dashboards alert on repeated identifier reuse from one source.
- A future move to OpenTelemetry generates `trace-id` values that don't match the UUID v4 pattern's variant/version bits (OTel uses fully random 128 bits, no version bits). Logs from before and after the cutover would have different shapes for the identifier. Mitigation: the migration accepts this as a one-time transition; operators are notified of the cutover.

## Confirmation

Compliance is verified by:

- **Repository contents.** A single ASGI middleware (under `app/server/` or equivalent) handles inbound correlation. A single HTTP-client wrapper (under `app/clients/_http/` or equivalent) propagates outbound headers. The structured-logging configuration registers `structlog.contextvars.merge_contextvars` as a processor.
- **Code review.** A PR adding a non-HTTP entry point (a scheduled job, a queue consumer) includes the contextvar binding setup at the entry point. A PR that adds a new outbound HTTP call uses the application's HTTP-client wrapper rather than constructing an `httpx.AsyncClient` inline.
- **Tests.** A unit test of the middleware asserts that `traceparent`, `X-Request-ID`, and missing-header cases each produce a valid request_id with the expected source. An end-to-end test asserts that the response body's `request_id` (in a problem-details error), the `X-Request-ID` response header, and a log record produced inside the handler all share the same value.
- **Operational dashboard.** A metric counts log records emitted without a `request_id` field; the steady-state value is zero. A non-zero count points to an entry point that forgot to bind the context.

## Source References

1. W3C Trace Context — Recommendation
   - URL: <https://www.w3.org/TR/trace-context/>
   - Accessed: 2026-05-08
   - Relevance: Defines the `traceparent` header (`version-trace-id-parent-id-flags`) and the `tracestate` header for distributed-tracing correlation. Establishes the rule that a missing or malformed `traceparent` requires the receiver to create a new `trace-id` and `parent-id`. Grounds the wire-format compatibility with W3C Trace Context and the inbound-header acceptance order.

2. RFC 9562 — Universally Unique IDentifiers (UUIDs)
   - URL: <https://www.rfc-editor.org/rfc/rfc9562.html>
   - Accessed: 2026-05-08
   - Relevance: Specifies UUID version 4 (random) and version 7 (timestamp-prefixed) formats, including the 128-bit layout, version/variant bits, and recommended use of v7 for new applications. Grounds the choice of UUID v4 as the canonical wire form (with v7 as an acceptable alternative for log-locality optimization in the future).

3. Python — `contextvars` Module Documentation
   - URL: <https://docs.python.org/3/library/contextvars.html>
   - Accessed: 2026-05-08
   - Relevance: Documents `ContextVar.get()`/`set()`/`reset()`, the rule that variables must be defined at module level (so the runtime can hold strong references), and the asyncio-native context inheritance through `asyncio.Task`. Grounds the binding mechanism for the per-request correlation identifier and the rule that the variable is reset at request exit using the token returned by `set()`.

4. structlog — Context Variables
   - URL: <https://www.structlog.org/en/stable/contextvars.html>
   - Accessed: 2026-05-08
   - Relevance: Documents `structlog.contextvars.merge_contextvars` as the canonical processor for merging context-bound fields into log records, and the `bind_contextvars`/`clear_contextvars`/`unbind_contextvars` lifecycle. Grounds the rule that the correlation identifier appears in every log record without per-call-site work, and that the middleware calls `clear_contextvars()` at request entry to prevent bleed.

5. RFC 9457 — Problem Details for HTTP APIs
   - URL: <https://www.rfc-editor.org/rfc/rfc9457.html>
   - Accessed: 2026-05-08
   - Relevance: Defines the standard error-body shape (`application/problem+json`) and the extension-member mechanism. The `request_id` field used in the application's error bodies is an RFC 9457 extension; this record specifies its source (the `contextvars`-bound identifier) and ensures the body, response header, and log records all carry the same value.

6. RFC 9110 — HTTP Semantics (Header Fields)
   - URL: <https://www.rfc-editor.org/rfc/rfc9110.html>
   - Accessed: 2026-05-08
   - Relevance: Specifies HTTP request and response header semantics. The `X-` prefix convention for non-standard headers (and its formal deprecation per RFC 6648) informs the choice to use `X-Request-ID` only as a widely recognized de-facto convention; the canonical correlation header is `traceparent` (W3C-registered), with `X-Request-ID` retained for backwards compatibility with existing tooling.

7. Slack — Comparing HTTP Events API and Socket Mode
   - URL: <https://docs.slack.dev/apis/events-api/comparing-http-socket-mode>
   - Accessed: 2026-05-08
   - Relevance: Documents that Slack delivers events to apps via two mutually exclusive modes — the HTTP Events API (request-response, short-lived connections, public URL required) or Socket Mode (bi-directional WebSocket, no public URL required, the SDK opens an outbound persistent connection on which events arrive). Establishes that in Socket Mode the application receives no inbound HTTP request envelope; outbound calls to Slack's web API still use HTTP regardless of mode. Grounds the rule that Socket Mode entry points open their own correlation context at the SDK handler-invocation site rather than relying on HTTP middleware.

## Change Log

- 2026-05-08: Created. Establishes a per-request correlation identifier — UUID v4 on the wire, 128-bit value compatible with the W3C Trace Context `trace-id` field — generated per inbound unit of work, bound via Python `contextvars`, surfaced in every log record via `structlog.contextvars.merge_contextvars`, echoed on every response as `X-Request-ID`, included in problem-details error bodies as the `request_id` extension member, and propagated on outbound HTTP via both `X-Request-ID` and `traceparent`. Inbound acceptance order: valid `traceparent` first, valid `X-Request-ID` second, fresh generation otherwise. Malformed caller-supplied values are rejected silently (a fresh identifier is generated). Distinguishes inbound channels by delivery protocol: HTTP middleware handles feature routes, Microsoft Teams events (Bot Framework HTTP), and Slack events when configured for the HTTP Events API; the Slack Socket Mode SDK handler establishes its own correlation context per delivered event because events arrive over a persistent WebSocket with no inbound HTTP envelope. Outbound calls to Slack always use HTTP regardless of inbound mode. Background workers, scheduled jobs, and queue consumers each open their own correlation context per iteration/message; queue consumers may additionally bind a `parent_request_id` from message metadata. The identifier is observability-only and is distinct from domain-level correlation identifiers (durable entity UUIDs that travel through Slack `private_metadata` or Teams Adaptive Card action data over hours or days). The `constrained_by` frontmatter was corrected from the placeholder's backwards listing (`multi-transport-architecture.md`, `logging-observability.md`) — both of those records depend on this one, not the other way around.
