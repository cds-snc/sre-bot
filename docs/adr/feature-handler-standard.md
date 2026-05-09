---
title: "Feature Handler Standard"
status: Accepted
type: Standard
tier: Tier-2
governance_domain: [application]
concerns: [api, architecture, plugins]
constrained_by: [layered-architecture.md, dependency-injection.md, type-boundaries.md, plugin-registration-discovery.md, multi-transport-architecture.md, feature-package-structure.md, cross-channel-correlation.md, logging-observability.md, operation-result-pattern.md, api-design-error-mapping.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Feature Handler Standard

## Context and Problem Statement

A feature ships small functions — *handlers* — that run when a specific inbound interaction arrives: an HTTP request to a route, a Slack slash command, a Teams card-action submission, a future platform's category-specific event. The handler is the single feature-side entry point per interaction; it sits between the host's inbound dispatch and the feature's service layer. Its discipline determines whether the handler is a thin adapter that translates platform-specific shapes into service calls and back — or a place where business logic, vendor-SDK calls, and ad-hoc state mutation accumulate.

The problem this record addresses: **what shape should every feature's handler functions take, regardless of which platform invoked them, so that handlers stay thin, testable, and free of cross-cutting concerns the host has already established?** The answer determines:

1. Whether a developer reading any handler in any feature sees the same overall shape (parse inputs → call service → render result), or whether each handler reinvents an entry-point structure.
2. Whether business logic stays in the feature's service layer (where it is testable in isolation) or leaks into handlers (where each handler must be tested with platform-specific machinery).
3. Whether vendor-SDK calls happen behind Protocol boundaries (where they can be substituted in tests and where the layered architecture is preserved) or directly inside handlers (which violates the import contract and couples handlers to vendor types).
4. How a handler converts the feature service's `OperationResult` envelope into the platform's outbound response without each handler reimplementing the conversion.
5. How handlers relate to platform-specific runtime constraints — particularly the platforms whose acknowledgement deadline is shorter than the work the handler must do (e.g., Slack's 3-second `ack`).

**Constraints:**

- Per-request cross-cutting state — the correlation `request_id`, the inbound adapter's verification of the payload, the platform-specific runtime context — has already been established by the host before the handler runs. The handler does not re-derive any of those.
- The host's plugin manager dispatches inbound interactions to handlers via per-platform hookspecs. The hookspecs themselves are owned by per-platform records; this record specifies what the *handler functions* registered through those hookspecs look like.
- Feature service layers return `OperationResult` envelopes. The handler does not branch on internal exceptions to produce business outcomes; the service contract is the canonical error vehicle.
- Per-platform `OperationResult` rendering is owned by the platform's record (HTTP renderer is governed by the API design and error-mapping decision; Slack and Teams renderers are governed by their respective transport records). The handler calls the per-platform rendering helper rather than constructing platform-specific outbound shapes inline.

**Non-goals:**

- This record does not enumerate hookspec names or per-platform handler signatures. Platform-specific signatures live in each platform's own record; the discipline this record establishes applies regardless of signature.
- This record does not redefine plugin registration mechanics, the inbound adapter, the correlation context, or the `OperationResult` envelope. Those are owned by other records and are inputs to this discipline.
- This record does not specify the testing approach for handlers (test layering, fixtures, dependency overrides). That belongs in the testing-standards record.
- This record does not define handler idempotency or retry semantics; those are owned by the handler-idempotency record.

## Considered Options

**Option 1 — Free-form handler conventions.** No prescribed shape; reviewers verify against general "thin controller" principles case by case. Discipline drifts; new contributors lack a template.

**Option 2 — Strict, identical handler template per platform.** Every handler is structured identically across platforms regardless of platform-specific shape. Forces platform-specific runtime concerns (Slack's `ack`, Teams' invoke response) into a synthetic shared template; loses platform fidelity.

**Option 3 — One discipline, expressed as a small set of handler-function rules, with platform-specific patterns layered on inside platform records.** The discipline names what every handler does and does not do (thin, no business logic, no vendor SDKs, OperationResult-to-response via a helper); platforms add their own constraints (Slack ack timing, HTTP idempotency keys, Teams card refresh) on top of that base.

## Decision Outcome

**Chosen: Option 3 — one discipline, expressed as a small set of handler-function rules.**

The discipline is platform-agnostic at the level of "what belongs inside a handler" and "what does not." Per-platform constraints (Slack acknowledgement deadlines, HTTP request-scope semantics, Teams card-update mechanics) are layered on inside platform-specific records and feature handlers honour them on top of the base discipline. The handler is a *thin adapter* in the hexagonal-architecture sense: it sits at the application's boundary, translates inbound platform-specific shapes into domain language, calls the application's service layer, and translates the service's `OperationResult` envelope back into a platform-specific response.

### What a handler does

Every feature handler — across HTTP, Slack, Teams, and any future platform — performs the same five-step sequence:

1. **Receive the platform's inbound shape and the host-injected dependencies.** The platform's runtime context (a `Request`, a Slack `command` payload, a Teams `TurnContext`) arrives as an argument from the platform's dispatch. Protocol-typed dependencies (the feature's service layer, infrastructure-service Protocols the feature consumes) arrive via dependency injection per the dependency-injection record.
2. **Translate the platform's inbound shape into the service's argument types.** Pull the fields the service needs out of the platform payload; convert them into `dataclass` value types or scalar arguments per the type-boundaries decision. The handler is the only place this translation happens.
3. **Call the feature's service.** A single service-method invocation per handler is the steady state. Multiple service calls within one handler are an immediate signal that the orchestration belongs in the service layer.
4. **Receive the `OperationResult`.** The service returns an `OperationResult` envelope per the operation-result-pattern record's closed-status contract. On `SUCCESS`, the envelope's `payload` field carries the operation's success value; the handler reads it from the envelope rather than expecting a different return shape per status. The handler does not catch exceptions to produce business outcomes — adapter-level exception-to-`OperationResult` translation happens beneath the service.
5. **Render the result via the platform's rendering helper.** Each platform provides one helper (HTTP's `operation_result_to_response()`; Slack's and Teams' equivalents specified by their respective records); the handler calls the helper and either returns the helper's value (HTTP) or invokes the platform's outbound API with the helper's output (Slack `chat.postMessage`, Teams card update).

A handler that follows the five-step sequence is, by construction, a thin adapter: its body length is bounded by the input-translation and result-rendering steps; the business logic resides in the service.

### What a handler does not contain

The following do **not** belong inside a handler:

- **Business logic.** Any conditional branching on domain state, any calculation that affects the outcome of the operation, any combination of multiple service calls — these belong in the service layer. A handler with branching logic beyond "did the result indicate success or error" is failing the discipline; the branching belongs in the service.
- **Vendor-SDK construction.** A handler does not instantiate `boto3.client(...)`, `WebClient(...)`, `BotFrameworkAdapter(...)`, or any vendor SDK. Vendor clients arrive via providers per the dependency-injection rules. The vendor-import contract enforces this statically.
- **Direct vendor-SDK calls.** A handler does not call `chat.postMessage` directly on a `WebClient`; it calls the feature's `SlackService` Protocol method, which in turn (inside the infrastructure layer) calls the SDK. The handler holds no concrete vendor types.
- **State mutation.** Handlers do not mutate module-level state, write to caches outside transactional boundaries, or hold per-handler state across calls. State lives in the application's data store (per the cloud-portability statelessness contract); handlers are stateless transformation functions.
- **Try/except for business outcomes.** A handler does not wrap a service call in `try/except` to convert exceptions into responses. The service returns an `OperationResult`; exceptions reaching the handler are programmer errors or unhandled infrastructure failures (caught by the host's central exception handler per the API design and error-mapping rules, or per platform records for non-HTTP).
- **Cross-feature imports.** Per the import contract, no feature handler imports from another feature's package. Cross-feature coordination uses shared infrastructure or domain events.

### Async / sync rules

- **Default async.** All handlers are `async` functions. FastAPI, Slack Bolt's async client, and the Microsoft 365 Agents SDK all support async handlers natively; defaulting to async lets the handler call infrastructure Protocols that are themselves async without `asyncio.run` boundaries inside the handler.
- **Sync only when the work is genuinely synchronous and short.** A handler may be sync only when (a) the called service method is sync, (b) the platform supports sync handlers in its dispatch, and (c) no infrastructure call inside the handler chain is async. The default is async; sync is the deliberate exception, justified per case.

### Platform-specific runtime constraints

Some platforms enforce runtime constraints that handlers must honour. The discipline is uniform; the constraints' specifics are owned by per-platform records. Examples handlers must accommodate:

- **Slack acknowledgement deadline.** Slack expects an `ack()` within three seconds of receiving the interaction. Handlers whose work cannot complete in three seconds call `ack()` early (with a placeholder message if needed) and continue the work in a way that does not block the ack. The pattern is owned by the Slack transport record; the handler's discipline is to honour it.
- **HTTP request scope.** HTTP handlers run inside a single request scope; the response must be returned synchronously (from the handler's perspective). Long-running work that exceeds reasonable HTTP timeouts is enqueued via a queue or deferred via `202 Accepted` semantics — the handler returns promptly.
- **Teams invoke responses.** Teams' invoke activities expect specific response shapes; the handler's rendering helper produces the right shape per the Teams transport record's rules.

The handler's discipline is the same in all three cases: thin adapter that calls the service and renders. Platform-specific timing or shape constraints are honoured *through* the helper or *via* the platform's runtime API (e.g., `ack()`); the handler does not embed platform-specific business workarounds into its own logic.

### Logging inside the handler

The inbound adapter has already established the correlation `request_id` and bound it to `contextvars` per the cross-channel-correlation record. The handler therefore does not initialize correlation context. What the handler may do:

- **Bind handler-relevant context fields** at entry (the `feature` name, the `operation` name, perhaps the platform-specific identifier for the inbound interaction such as a Slack `event_id`). These additional fields appear on every log record produced inside the handler's call chain via `structlog.contextvars.merge_contextvars`.
- **Emit one info-level entry/exit log record** for the handler if the operation is significant. Routine handlers may not need an entry/exit pair; the inbound adapter's request log already names the inbound interaction. A handler that performs noteworthy business orchestration may log an entry record naming the operation; a handler whose service returns an error logs the result at the appropriate level (`warning` for transient, `error` for permanent) per the logging-observability conventions.
- **Use `log.exception(...)` for unexpected exceptions** that escape the service layer. The exception will also propagate to the host's central exception handler; the handler's logging is for diagnosis, not for masking.

What the handler does not do for logging:

- It does not duplicate the request log the inbound adapter already produced.
- It does not log every service-call argument or response body at `info`; that's `debug`-level diagnostic output.
- It does not construct ad-hoc free-text messages containing sensitive values; per the data-redaction-policy rules, sensitive content goes in named structured fields that the redaction processor handles automatically.

### Error semantics: what the service returns vs. what the handler does

The service's `OperationResult` is the canonical error vehicle. The handler's behaviour by status:

| `OperationStatus` | Handler behaviour |
| --- | --- |
| `SUCCESS` | Render the success body via the platform's helper; emit a single business-level info log if the operation merits one. |
| `NOT_FOUND` | Render the platform's `404`-equivalent via the helper. No retry. |
| `UNAUTHORIZED` | Render the platform's `401`/`403`-equivalent via the helper. No retry from the handler. |
| `PERMANENT_ERROR` | Render the platform's `4xx`-equivalent via the helper. The error is the service's; the handler does not embellish it. |
| `TRANSIENT_ERROR` | Render the platform's `503`-equivalent via the helper, including `Retry-After` (HTTP) or platform-equivalent guidance per the platform record. The handler does not retry inline; retry is the caller's concern. |

**Programmer errors and unhandled exceptions** (anything that escapes the service layer as a raised exception, not as an `OperationResult`) propagate from the handler to the host's central exception handler per the API design and error-mapping record (HTTP) or per the platform record (non-HTTP). The handler does not catch them.

### Handler size as a smell

A handler whose body exceeds roughly 20–30 lines is a smell. The five-step sequence (receive, translate, call, receive, render) is mechanical; if a handler is long, the cause is almost always logic that belongs in the service layer or platform-specific shape construction that belongs in a helper. The exact threshold is not a hard rule; the principle is that handlers stay thin.

### Hookimpl vs handler

A note on the registration-time/runtime distinction: a feature's `__init__.py` declares one or more `@hookimpl` functions (e.g., `register_slack_command`) that the host calls *once* at the lifespan's feature-activation phase. The hookimpl's job is plumbing — register the platform's runtime decorators (e.g., Bolt's `@app.command("/...")`) against the feature's actual handler functions. The hookimpl is *not* a handler; it has no per-interaction logic and no business content. **This record's discipline applies to the runtime handler, not the registration-time hookimpl.** The hookimpl is governed by the plugin-registration-discovery and feature-package-structure rules.

## Consequences

**Positive:**

- Every handler in every feature on every platform reads the same way: receive, translate, call the service, render. New contributors learn one shape; reviewers spot deviations immediately.
- Business logic stays where it can be tested in isolation. The service layer is testable without platform machinery; the handler is testable with thin shims for platform shapes.
- The vendor-import contract is trivially satisfied because handlers do not import from `app/clients/`. The static contract catches violations automatically.
- Errors flow through one channel: the service returns `OperationResult`, the handler renders. There are no scattered try/except blocks producing ad-hoc error responses.
- Platform-specific timing constraints (Slack `ack`, HTTP timeouts, Teams invoke shapes) are honoured through the per-platform rendering helper, not by handler-internal heuristics.

**Tradeoffs accepted:**

- A handler that is "obviously" a one-liner (call a service, return its result) still pays the structural cost of the five-step shape. The cost is low; the benefit is uniform structure across the codebase.
- Handlers cannot directly access vendor SDKs even when "it would be simpler." That simplification is a known anti-pattern: it leaks vendor types into handlers, breaks testability, and violates the import contract.
- Some platform-specific patterns (Slack ack-then-work, HTTP `202 Accepted` deferral) require the handler to coordinate timing carefully. The discipline does not eliminate that coordination; it scopes it to the platform record's prescribed pattern, not to handler-by-handler ad-hoc solutions.

**Risks:**

- A handler grows past the size threshold over time as the feature evolves; business logic creeps in. Mitigation: code review against the five-step shape; periodic refactoring lifts logic into the service layer.
- A new platform with an unusual runtime model (e.g., long-polling with manual heartbeats) does not fit the handler shape cleanly. Mitigation: the per-platform record names the runtime constraints; the handler discipline is the base, and the per-platform record extends it for that platform's needs.
- Feature authors substitute "the helper does too much" for "I'll do it in the handler." Mitigation: per-platform helpers are the right place to grow shape-rendering logic, including platform-quirk handling; the handler discipline pushes complexity to the right home.

## Confirmation

Compliance is verified by:

- **Code review.** A PR introducing a new handler is reviewed against the five-step shape and the "what does not belong inside a handler" list. PRs that include business logic, vendor-SDK construction, or direct vendor-API calls inside a handler are rejected.
- **Static analysis.** The import contract enforces that feature code (and therefore handlers) does not import from `app/clients/`; the contract catches the most-damaging violations automatically.
- **Tests.** Handlers are tested by exercising their input-translation and result-rendering steps with the service layer substituted; service-layer tests cover business logic without involving handler machinery. The testing-standards record will pin the layering pattern.
- **Handler size.** A handler whose body exceeds ~30 lines (excluding decorators, type hints, and docstrings) is flagged at review for a "what business logic snuck in?" check. The rule is a smell threshold, not a hard limit.

## Source References

1. Hexagonal Architecture (Ports and Adapters) — Alistair Cockburn
   - URL: <https://alistair.cockburn.us/hexagonal-architecture/>
   - Accessed: 2026-05-08
   - Relevance: Establishes the principle that adapters at the application's boundary translate between external shapes and the application's domain language. Grounds the rule that the handler is a thin adapter — its responsibility is translation, not business logic.

2. Vertical Slice Architecture — Jimmy Bogard
   - URL: <https://jimmybogard.com/vertical-slice-architecture/>
   - Accessed: 2026-05-08
   - Relevance: Establishes that each inbound interaction owns its end-to-end path and that cross-slice coupling is minimized. Grounds the rule that one handler corresponds to one inbound interaction and calls the feature's service layer rather than reaching into other features.

3. Architecture Patterns with Python (Cosmic Python), Chapter 4 — Bob Gregory and Harry Percival
   - URL: <https://www.cosmicpython.com/book/chapter_04_service_layer.html>
   - Accessed: 2026-05-08
   - Relevance: Documents the Service Layer pattern in Python: the entry-point function (the handler) is responsible for "standard web stuff" — parsing inputs and constructing responses — while orchestration and business logic live in the service layer. The text states that controllers should "extract user input, delegate orchestration to the service layer, and construct appropriate HTTP responses." Grounds the five-step handler shape and the rule that handlers do not contain business logic.

4. Patterns of Enterprise Application Architecture — Martin Fowler (Service Layer pattern)
   - URL: <https://martinfowler.com/eaaCatalog/serviceLayer.html>
   - Accessed: 2026-05-08
   - Relevance: The canonical reference for the Service Layer pattern: a layer that "defines an application's boundary with a layer of services that establishes a set of available operations and coordinates the application's response in each operation." Grounds the rule that handlers delegate to the service layer for orchestration; the service layer is the boundary where the application's intent surfaces.

5. The Twelve-Factor App — Processes (Factor VI)
   - URL: <https://12factor.net/processes>
   - Accessed: 2026-05-08
   - Relevance: Establishes that the application runs as stateless processes, with state externalized to backing services. Grounds the rule that handlers do not hold per-handler state across calls and do not mutate module-level state; handlers are stateless transformation functions.

## Change Log

- 2026-05-08: Created as placeholder under the title "Platform Interaction Handlers."
- 2026-05-08: Renamed to `feature-handler-standard.md`. The previous filename's "Platform" prefix carried the unified-platform abstraction the corpus has rejected; "feature-handler-standard" centers the function being written and applies regardless of which platform invoked it.
- 2026-05-08: Finalized. Establishes a single per-handler discipline that applies to every feature handler on every platform: a five-step shape (receive inputs and DI, translate to service arguments, call the service, receive `OperationResult`, render via the per-platform helper); a closed list of what does not belong inside a handler (business logic, vendor-SDK construction, direct vendor-API calls, state mutation, business-outcome try/except, cross-feature imports); async-by-default with sync as the deliberate exception; entry-time context binding for log enrichment; deferral of platform-specific runtime constraints (Slack `ack`, HTTP deferral, Teams invoke shape) to per-platform records and helpers. Pins the handler-size smell threshold at roughly 20–30 lines of body. Distinguishes the runtime handler (this record's subject) from the registration-time hookimpl (governed by the plugin-registration-discovery and feature-package-structure rules).
