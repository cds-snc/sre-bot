---
title: "Logging and Observability"
status: Accepted
type: Standard
tier: Tier-2
governance_domain: [application, operations]
concerns: [observability]
constrained_by: [cloud-portability.md, layered-architecture.md, application-lifecycle.md, cross-channel-correlation.md, api-design-error-mapping.md, configuration-ownership.md, data-redaction-policy.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Logging and Observability

## Context and Problem Statement

The application emits log records from many places: lifespan-phase boundaries, route handlers, infrastructure providers, vendor-client wrappers, background workers, third-party libraries it imports, and the ASGI server (Uvicorn) itself. Operators need every record to be discoverable, parseable, and correlatable to one inbound unit of work. Without a single canonical record shape, an operator looking at a failure must reconcile records that came from different libraries, different formatters, and different fields named differently for the same concept.

The problem this record addresses: **what is the canonical structured-logging stack — library, output, format, field schema, and level conventions — that every record produced by the application conforms to?** The answer determines:

1. Whether log records from different code paths share a single shape (and so can be parsed by one log indexer with one schema), or whether each library renders its own.
2. Whether records produced by third-party libraries and the ASGI server are reshaped into the application's record format, or appear as a separate stream that operators must unify downstream.
3. Whether log levels carry consistent meaning across the application (so an `ERROR` level alarm is a real signal), or each subsystem invents its own level convention.

**Constraints:**

- Logs are an event stream written to `stdout` per the cloud-portability contract. The application does not write log files, configure cloud-provider logging APIs, or manage log routing/aggregation/retention. The execution environment owns those concerns.
- A correlation identifier (`request_id`) is bound per inbound unit of work via Python `contextvars`. Every log record produced inside that context must carry the identifier.
- Error responses produced via the problem-details mapper carry a `request_id` extension member. The body's identifier and a log record produced during the same request must match exactly.
- The application is asynchronous (FastAPI on Uvicorn); the logging stack must be safe under concurrent `asyncio.Task`s without bleeding context between requests.
- Configuration (log level, format selection between human-readable and machine-parseable) is read from environment variables at startup per the configuration-ownership contract; no runtime reconfiguration.

**Non-goals:**

- This record does not specify metrics collection, custom counters/gauges, or histogram aggregation. Metrics are a separate signal type and a separate decision.
- This record does not adopt distributed tracing (OpenTelemetry SDK with span instrumentation, exporters, sampling). The correlation-identifier decision keeps the door open for later adoption; this record covers logs only.
- This record does not specify log aggregation, retention, search infrastructure, or alerting. Per the cloud-portability contract, those are owned by the execution environment.
- This record does not define sampling policies for high-volume routes. If a high-volume code path requires sampling, the policy is added through a follow-up decision when the need materializes.
- This record does not pick which fields each individual feature logs in its `event` records. It defines the *envelope* (mandatory and conditional fields, naming convention, types) and the *processor pipeline* that produces the envelope.
- This record does not define the catalogue of sensitive field names or the redaction algorithm applied to log records. Those rules are owned by the data-redaction-policy decision and operate uniformly across every structured-record egress channel; this record names where the redaction processor is *placed* in the logging pipeline and refers out for the policy itself.

## Considered Options

**Option 1 — `logging` (stdlib) with a JSON formatter.** Use Python's standard `logging` module everywhere; configure a JSON formatter (e.g., `python-json-logger`) on the root handler. Familiar to every Python developer; the library's API uses string-formatted messages with positional/keyword args. Context-binding (per-request `request_id` injection) requires a custom filter or a per-thread-local mechanism, which is awkward under `asyncio`.

**Option 2 — `loguru`.** A modern logging library with a simpler API, built-in JSON output, and async support. Library-specific API (deviates from stdlib `logging`); third-party libraries that use stdlib `logging` need an interceptor handler to flow through `loguru`. Smaller ecosystem than `structlog` for FastAPI-based services.

**Option 3 — `structlog` with stdlib integration via `ProcessorFormatter`.** A library purpose-built for structured logging in Python: events are dictionaries, processors transform them in a pipeline, the renderer at the end of the pipeline produces the wire form. First-class `contextvars` integration. Records produced via stdlib `logging.getLogger(...)` (uvicorn access logs, third-party libraries, FastAPI's own internals) flow through the same processor pipeline via `structlog.stdlib.ProcessorFormatter`, so every log line — application or not — comes out in one shape.

**Option 4 — OpenTelemetry SDK (logs signal).** Adopt OpenTelemetry as the unified observability framework: logs, metrics, traces all flow through one SDK with exporters to an OTel-compatible backend. Largest infrastructure surface; appropriate when the rest of the OTel stack is in place; premature for an application that has not yet adopted distributed tracing.

## Decision Outcome

**Chosen: Option 3 — `structlog` with stdlib integration via `ProcessorFormatter`.**

`structlog` is the structured-logging library best aligned with the codebase's needs: events are dictionaries (no implicit `printf` formatting), the processor pipeline is composable and explicit (each step is a function with a well-defined input and output), `contextvars` integration is first-class (`merge_contextvars` puts bound fields into every record automatically), and stdlib log records are routed through the same pipeline via `ProcessorFormatter` so the wire shape is uniform regardless of which library produced the record.

### Output and format

- **Destination.** `stdout` for all log records, regardless of level. `stderr` is reserved for fatal startup failures emitted *before* the logging stack is initialized (a small bootstrap window where `print(..., file=sys.stderr)` is the only safe option). After the lifespan's configuration phase, all output goes to `stdout`.
- **Buffering.** Output is unbuffered. Python's stdout buffering is forced off so log records are visible to the execution environment immediately and are not lost on process termination. This is set at process start (e.g., `PYTHONUNBUFFERED=1` env var or `sys.stdout.reconfigure(line_buffering=True)` in the bootstrap).
- **Wire format in production.** **JSON Lines (NDJSON)**: one JSON object per line, separated by `\n`, UTF-8 encoded. One log record is one line. Pipeline-friendly; parseable by every log indexer.
- **Wire format in development.** A human-readable colored format (`structlog.dev.ConsoleRenderer`) when running interactively. Selected by an environment variable (e.g., `LOG_FORMAT=console` overrides the default `json`); production deployments do not set the override.

### Processor pipeline

The pipeline runs in this order. Order matters: each processor sees the event dict produced by the previous one, and certain processors must run before others to produce correct output.

| # | Processor | Why it runs at this position |
| --- | --- | --- |
| 1 | `structlog.stdlib.filter_by_level` | Drops records below the configured level early. Avoids cost of downstream processors for filtered records. |
| 2 | `structlog.contextvars.merge_contextvars` | Merges `contextvars`-bound fields (notably `request_id`) into the event dict. Runs before per-call kwargs so an explicit kwarg can override a bound field if intentional. |
| 3 | `structlog.stdlib.add_logger_name` | Adds the `logger` field (the calling module's dotted name). |
| 4 | `structlog.stdlib.add_log_level` | Adds the `level` field as a lowercase string (`debug`, `info`, `warning`, `error`, `critical`). |
| 5 | `structlog.processors.TimeStamper(fmt="iso", utc=True)` | Adds the `timestamp` field as ISO 8601 with millisecond precision in UTC. |
| 6 | `structlog.processors.CallsiteParameterAdder([...])` | Adds `code.file.path`, `code.function.name`, `code.line.number` (OpenTelemetry semantic-convention attribute names). |
| 7 | `structlog.processors.StackInfoRenderer()` | Renders stack info when explicitly requested via `stack_info=True`. |
| 8 | `structlog.processors.format_exc_info` | Renders exception traceback into the `exception` field when `exc_info=True` or when `log.exception(...)` is used. |
| 9 | (project) redaction processor | Applies the catalogue and algorithm defined by [data-redaction-policy.md](data-redaction-policy.md) to the event dict. Placed after all field-injecting processors so it sees the complete record, and immediately before the renderer so no field can be injected after redaction. |
| 10 | Renderer: `structlog.processors.JSONRenderer()` (production) or `structlog.dev.ConsoleRenderer()` (dev) | Emits the final wire form. Last in the pipeline. |

For records originating in the stdlib `logging` module (uvicorn access logs, third-party libraries), the same pipeline is the formatter's `processors=` chain via `structlog.stdlib.ProcessorFormatter`, with the application's processors as `foreign_pre_chain=`. The output shape is identical regardless of origin.

### Field schema

**Mandatory fields on every record:**

| Field | Type | Source |
| --- | --- | --- |
| `timestamp` | string (ISO 8601, UTC, ms precision) | `TimeStamper` processor |
| `level` | string (`debug` \| `info` \| `warning` \| `error` \| `critical`) | `add_log_level` processor |
| `event` | string (snake_case, lowercase, stable) | the call site's positional argument |
| `logger` | string (dotted module name) | `add_logger_name` processor |
| `code.file.path` / `code.function.name` / `code.line.number` | string / string / int | `CallsiteParameterAdder` |

**Conditional fields, present when applicable:**

- `request_id` — UUID v4 from the `contextvars` binding (every record produced inside an inbound request has this).
- `parent_request_id` — the upstream request that enqueued this work (queue consumers).
- `error_code` — application error code from `OperationResult.error_code` when an error is being logged.
- `exception` — formatted traceback string when `log.exception(...)` is used or `exc_info=True` is passed.
- `feature` / `operation` — feature name and operation name when the call site identifies a feature operation.
- Channel-specific bound fields (`event_id`, `team_id`, `channel_id`, `user_id` for Slack; analogous fields for Teams) — bound by the channel handler at its entry point.

**Naming convention:**

- Field names are **snake_case** for application-defined fields (`request_id`, `error_code`, `parent_request_id`).
- OpenTelemetry semantic-convention attributes use **dot.notation** (`code.file.path`, `code.function.name`, `code.line.number`). The convention follows OTel's own naming rules and is preserved verbatim.
- The `event` field's *value* is a snake_case verb-or-state phrase (`request_completed`, `feature_activated`, `slack_event_received`). It is stable for a given call site; rich data goes in fields, not in `event`.

### Log level conventions

Every level has a defined operational meaning. A record's level is chosen by the rules in this table, not by the developer's mood.

| Level | Meaning | Example |
| --- | --- | --- |
| `debug` | Developer-only diagnostics. Produced under `LOG_LEVEL=debug`. Off in production. | "Cache lookup hit", "request body parsed" |
| `info` | Routine, expected, business-relevant events. One per inbound unit of work plus lifecycle records. | "request_completed", "feature_activated", "lifespan_phase_complete" |
| `warning` | Recoverable problem; the application kept working. Often paired with a transient retry. | "external_api_retry", "settings_deprecated_value", "rate_limited_by_upstream" |
| `error` | The handled failure outcomes — `OperationStatus.PERMANENT_ERROR` and `TRANSIENT_ERROR` reported by the application. | "operation_failed", with `error_code` in the record |
| `critical` | An unrecoverable failure. Typically followed by process exit (lifespan boot failure) or an unhandled exception escaping a route handler. | "lifespan_phase_failed", "unhandled_exception" |

**Operational rule:** the steady-state production level is `info`. A high rate of `warning` is a signal worth investigating; any rate of `error` and `critical` is paged on. `debug` is enabled only during a focused investigation.

### Stdlib logging integration

Uvicorn, FastAPI, third-party libraries, and any code that does `logging.getLogger(...)` produce log records that are *not* `structlog` calls. The integration:

- The root `logging.Logger` has one handler whose formatter is `structlog.stdlib.ProcessorFormatter`. The formatter's `foreign_pre_chain` is the application's processor pipeline (steps 2–9 above; level filtering is handled by stdlib's logging level on the root logger).
- Uvicorn's access log is configured to flow through the same root handler — no separate Uvicorn formatter, no double-output.
- Third-party libraries' loggers are not silenced or reconfigured per-library; they inherit the root handler. A noisy library is handled by setting its specific logger's level (`logging.getLogger("noisy_lib").setLevel(...)`) at boot, not by suppressing or reformatting.

The result: every log record on `stdout` — whether produced by `structlog.get_logger()` in feature code or `logging.getLogger()` in a vendor SDK — is one JSON Lines record with the same field schema.

### Exception handling

- Exceptions are logged with `log.exception(...)` (which sets `exc_info=True` automatically) or `log.error(..., exc_info=True)`. Both produce an `exception` field with the full traceback rendered to a string.
- The `exception` field is full-traceback in *every* environment (development and production). The redaction policy on user-facing error responses (the problem-details `5xx` rule) is a separate concern: error bodies are redacted; log records are not. Operators see the full exception in logs; callers see the redacted body.
- Unhandled exceptions caught by the central exception handler (the one that produces the `500` problem-details body) are logged at `critical` with the full exception and the request's bound `request_id`.

### Performance and lazy filtering

- The `filter_by_level` processor is the first processor in the pipeline so records below the configured level are dropped without running the rest of the chain.
- structlog's `make_filtering_bound_logger(level)` is configured at boot from `LOG_LEVEL`; the level is fixed for the process lifetime.
- Event values are computed lazily where structlog supports it (e.g., `log.info("event", expensive=lazy_value)` evaluates `lazy_value` only if the record passes the level filter).
- The renderer (JSON or console) is the only step that does string formatting; intermediate processors operate on dicts.

### Scope boundaries (explicit deferrals)

- **Metrics** (counters, gauges, histograms): out of scope. A metrics decision will pick the library and the export path separately.
- **Distributed traces** (spans, span links, sampling): out of scope. The correlation-identifier decision keeps the wire format compatible; SDK adoption is a separate decision.
- **Sampling for high-volume logs**: out of scope. If a code path becomes high-volume enough to warrant sampling, the policy is added at that point.
- **Log aggregation, retention, search infrastructure**: owned by the execution environment per the cloud-portability contract.

## Consequences

**Positive:**

- One log shape across the entire stream regardless of which library produced the record. An indexer parses one schema; an operator reads one format.
- The correlation identifier is on every record automatically (via `merge_contextvars`); operators investigate by `grep request_id <uuid>` rather than reconstructing chains.
- Levels carry stable operational meaning. An alarm on `error` records is a real signal; warnings and infos do not pollute paging.
- Stdlib `logging` integration is a one-time configuration, not a per-call concern. Vendor SDKs and Uvicorn produce records that look like the application's own.
- The redaction policy is decoupled from the logging library: changing the redaction catalogue, adding a new sensitive key category, or applying redaction to a future egress channel does not require editing this record or the logging pipeline beyond the boundary placement.

**Tradeoffs accepted:**

- The pipeline runs on every record (after the level filter). The cost is bounded — each processor is a small function on a small dict — but is non-zero. Acceptable given the diagnostic value of uniform records.
- JSON Lines is verbose compared to a compact text format. The cost is bytes; the benefit is machine-readable structure that survives every pipeline. The tradeoff favours machine-readability.

**Risks:**

- A code path emits a log record outside any request context (e.g., a background task forgets `bind_contextvars`). The record lacks `request_id`. Mitigation: the correlation-identifier decision documents the entry-point binding rule; an operational dashboard counts log records emitted without `request_id` and the steady-state value is zero.
- A processor in the pipeline raises an exception while rendering a record, which would normally lose the record. Mitigation: structlog's pipeline catches and reports such failures via a fallback path; the pipeline is built once at boot and not edited at runtime.

## Confirmation

Compliance is verified by:

- **Repository contents.** A single `app/server/logging.py` (or equivalent infrastructure module) configures structlog and the stdlib `logging` integration at boot. The pipeline order matches this record's table. The redaction pattern list is a named constant.
- **Boot integration.** Logging configuration runs at the lifespan's configuration phase; it is the first phase in the boot sequence so subsequent phases produce conformant records. `PYTHONUNBUFFERED=1` (or equivalent) is set in the runtime environment.
- **Field schema.** A unit test asserts that a record produced via `structlog.get_logger()` and a record produced via `logging.getLogger()` both contain the mandatory fields (`timestamp`, `level`, `event`, `logger`, `code.*`) and the same shape on the wire.
- **Levels.** A code review check verifies that a PR using `error` or `critical` levels is logging a real failure path, not a routine event. New `info` records are reviewed for whether they are business-relevant or developer noise (the latter goes to `debug`).
- **No file output.** A static check forbids `FileHandler`, `RotatingFileHandler`, or any handler other than `StreamHandler(sys.stdout)` in logging configuration code.

## Source References

1. structlog — Standard Library Integration
   - URL: <https://www.structlog.org/en/stable/standard-library.html>
   - Accessed: 2026-05-08
   - Relevance: Documents `structlog.stdlib.ProcessorFormatter` and the `foreign_pre_chain` mechanism for routing stdlib `logging` records through structlog's processor pipeline. Documents the canonical processor ordering (filter_by_level first, renderer last) and the `wrap_for_formatter` rule. Grounds the chosen library, the stdlib integration, and the processor pipeline order.

2. structlog — Context Variables
   - URL: <https://www.structlog.org/en/stable/contextvars.html>
   - Accessed: 2026-05-08
   - Relevance: Documents `structlog.contextvars.merge_contextvars` as the canonical processor for merging context-bound fields into log records. Grounds the rule that the correlation identifier appears in every log record automatically.

3. The Twelve-Factor App — Logs (Factor XI)
   - URL: <https://12factor.net/logs>
   - Accessed: 2026-05-08
   - Relevance: Establishes that logs are an event stream and that "a twelve-factor app never concerns itself with routing or storage of its output stream." Applications write unbuffered to stdout; the execution environment captures, routes, and stores. Grounds the rule that the application emits to stdout only and does not configure log files, cloud-provider logging APIs, or aggregation paths.

4. JSON Lines (NDJSON) Specification
   - URL: <https://jsonlines.org/>
   - Accessed: 2026-05-08
   - Relevance: Defines the JSON Lines format: one JSON value per line separated by `\n`, UTF-8 encoded. Pipeline-friendly and parseable line-by-line. Grounds the production wire format choice.

5. OpenTelemetry — General Logs Semantic Conventions
   - URL: <https://opentelemetry.io/docs/specs/semconv/general/logs/>
   - Accessed: 2026-05-08
   - Relevance: Specifies the OpenTelemetry attribute-naming convention (dot.notation, snake_case for multi-word segments) and standard log-record attributes (`code.file.path`, `code.function.name`, `code.line.number`). Grounds the field-naming rules and the choice of OTel-aligned attribute names for callsite parameters; preserves forward compatibility with full OTel adoption.

6. Python — `logging` Module Documentation (Logging Cookbook)
   - URL: <https://docs.python.org/3/howto/logging-cookbook.html>
   - Accessed: 2026-05-08
   - Relevance: Documents the stdlib `logging` module's handler/formatter/level architecture. Grounds the rule that the root handler is a single `StreamHandler(sys.stdout)` whose formatter is `structlog.stdlib.ProcessorFormatter`, and that third-party loggers inherit through the standard propagation rules.

## Change Log

- 2026-05-08: Created. Selects `structlog` (with stdlib `logging` integration via `ProcessorFormatter`) as the canonical structured-logging stack. Pins output to `stdout` only, unbuffered, in JSON Lines format in production and human-readable colored format in development (selected by env var). Establishes a named processor pipeline with explicit order: `filter_by_level` → `merge_contextvars` → `add_logger_name` → `add_log_level` → `TimeStamper(iso, utc)` → `CallsiteParameterAdder` (OTel-named attributes) → `StackInfoRenderer` → `format_exc_info` → redaction processor → renderer. Defines mandatory record fields (`timestamp`, `level`, `event`, `logger`, `code.*`) and conditional fields (`request_id`, `parent_request_id`, `error_code`, `exception`, channel-specific identifiers). Pins log-level operational meanings: `debug` (developer-only), `info` (routine business events), `warning` (recoverable problems), `error` (handled failures with `error_code`), `critical` (unrecoverable). Routes stdlib logging records (uvicorn access logs, third-party libraries) through the same pipeline so the wire shape is uniform regardless of origin. Defers metrics, distributed tracing, and high-volume sampling to separate decisions.
- 2026-05-08: Sensitive-field redaction extracted into [data-redaction-policy.md](data-redaction-policy.md). This record now names where the redaction processor is *placed* in the logging pipeline (step 9, after all field-injecting processors and immediately before the renderer); the catalogue, algorithm, replacement value, recursion semantics, and extension hook are owned by the data-redaction-policy decision and apply uniformly to every structured-record egress channel. The `concerns` frontmatter narrowed from `[observability, security]` to `[observability]` to reflect the scope split; `data-redaction-policy.md` is added to `constrained_by`.
