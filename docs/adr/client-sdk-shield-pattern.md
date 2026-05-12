---
title: "Client SDK Shield Pattern"
status: Accepted
type: Standard
tier: Tier-2
governance_domain: [application]
concerns: [architecture]
constrained_by: [layered-architecture.md, operation-result-pattern.md, client-adapter-responsibilities.md, outbound-retry-policy.md]
date: 2026-05-12
decision_makers:
  - SRE Team
---

# Client SDK Shield Pattern

## Context and Problem Statement

Vendor SDKs (Slack `slack_sdk` / Bolt, boto3, googleapiclient, Microsoft Graph) ship rich, well-typed surfaces that adapter authors legitimately want to reach for: method overloads, kwarg-level typing, IDE completion, and continuous coverage of new vendor capabilities as they land. At the same time, raw SDK use spreads transport concerns (retry, backoff, typed-exception classification, credential wiring) across every call site and leaks vendor exception classes upward into adapters and feature services in violation of [client-adapter-responsibilities.md](client-adapter-responsibilities.md).

Two naive fixes both fail:

- **Mirror the SDK behind hand-written facades that return `OperationResult`.** Solves the leakage but creates a parallel maintenance burden: the wrapper has to keep up with the SDK's surface, lags behind upstream additions, duplicates argument typing by hand, and erases the IDE completion engineers depend on at the call site.
- **Hand the dev a callable plus loose args (`execute(method, *args, **kwargs)`).** Preserves typing through `ParamSpec` but forces every call site to mentally split a single SDK call expression into two pieces. The call no longer looks like the vendor docs show it. Mixing positional and keyword arguments through `*args, **kwargs` is a known footgun, and refactors that rename an SDK kwarg become harder to grep.

The problem this record addresses: **how to provide a single resilience/classification boundary around vendor SDKs without (a) leaking SDK exceptions and retry plumbing upward, (b) trading away the typed, discoverable SDK surface by hand-mirroring it, or (c) introducing call-site error surface by decoupling an SDK call from its arguments.**

**Constraints:**

- The shield is a vendor-client boundary concern, not a feature-domain concern. It lives in client modules ([client-module-placement.md](client-module-placement.md)).
- All calls that cross the client boundary upward return `OperationResult` per [operation-result-pattern.md](operation-result-pattern.md) and [client-adapter-responsibilities.md](client-adapter-responsibilities.md). The shield is where that mapping happens.
- Retry, backoff, and per-call time budget follow [outbound-retry-policy.md](outbound-retry-policy.md). The shield composes with the SDK's native retry primitives where they exist (boto3 `Config(retries=...)`, `slack_sdk.RetryHandler` / `RateLimitErrorRetryHandler`); it does not stack a second retry layer on top of a working one.
- The shield must preserve the SDK's typed surface for adapter authors. Engineers should get IDE completion and type-checking on SDK method arguments at the call site, against the call expression *as it appears in vendor docs*.
- Inbound Slack/Bolt listener constraints (3-second `ack()` timing) still apply and are not relaxed by this pattern; long-running outbound work runs after `ack()` per [transport-slack.md](transport-slack.md) and [background-execution.md](background-execution.md).
- Both Path A composed-service implementations under `app/infrastructure/<service>/` and Path B feature-owned adapters under `app/packages/<feature>/adapters/` consume the shield. The pattern must work identically for both.

**Non-goals:**

- This record does not redefine the `OperationResult` shape or status set — see [operation-result-pattern.md](operation-result-pattern.md).
- This record does not define retry parameters or the retriable-error catalogue — see [outbound-retry-policy.md](outbound-retry-policy.md).
- This record does not define per-feature adapter behavior or domain interpretation of statuses — see [client-adapter-responsibilities.md](client-adapter-responsibilities.md).
- This record does not place the client module in the source tree — see [client-module-placement.md](client-module-placement.md).
- This record does not specify per-vendor authentication/lifecycle wiring — that is governed by the relevant transport record ([transport-slack.md](transport-slack.md), [transport-teams.md](transport-teams.md)) and the application lifecycle ([application-lifecycle.md](application-lifecycle.md)).

## Considered Options

**Option 1 — Curated facade per capability (hand-mirrored SDK surface).**

The client exposes a hand-written method for each operation it supports (`post_message`, `update_message`, `open_modal`, …). Each facade method returns `OperationResult` and internally calls the SDK. Adapters and composed services only ever see the facade.

Maximum boundary discipline, but the facade is a mirror that must be maintained as the SDK grows. New SDK capabilities are unavailable until someone writes a wrapper; argument typing is duplicated by hand and drifts; adapter authors lose IDE completion against the SDK and gain a second, smaller surface to memorize.

**Option 2 — Shield service that exposes the typed SDK client *and* an awaitable-wrapping executor (preferred).**

The shield is a thin service that owns SDK initialization, credential wiring, and the resilience boundary. It exposes:

- `service.api` (or equivalent attribute) — a reference to the raw, fully-typed SDK client (e.g., `AsyncWebClient` for Slack, `boto3.client("dynamodb", ...)` for AWS). Adapter authors call methods on this attribute to **produce** an awaitable; they do not await it directly.
- `service.execute(awaitable) -> OperationResult[R]` — the resilience boundary. The executor awaits the supplied coroutine, applies the per-call time budget from [outbound-retry-policy.md](outbound-retry-policy.md), catches typed SDK exceptions, classifies them into the closed five-status set from [operation-result-pattern.md](operation-result-pattern.md), and returns an `OperationResult`. Retry that requires *re-running* the call lives inside the awaitable (configured on the SDK client) or at a different layer (decorator on a curated facade); the executor does not re-execute.

Adapter call sites look like:

```python
result = await slack.execute(
    slack.api.chat_postMessage(
        channel=channel_id,
        text=message,
        thread_ts=thread,
    )
)
```

The SDK call expression is written exactly as it appears in vendor docs — one expression, with full IDE completion and type-checking on its kwargs. The shield never needs to mirror the SDK surface; the SDK *is* the surface. The pattern is directly modeled on `asyncio.shield(aw)` and `asyncio.wait_for(aw, timeout)` from the Python standard library, which take an in-flight awaitable and add a single boundary concern (cancellation protection, timeout) without changing the call shape.

**Option 3 — Shield with a callable + args executor (`execute(method, *args, **kwargs)`).**

Same shield idea, but the executor accepts an unbound SDK method plus its arguments and invokes it internally. `ParamSpec` preserves typing.

Mechanically works and supports executor-level retry (the executor can re-call the method), but introduces a call-site error surface that the awaitable-wrapping form avoids:

- The SDK call expression is split into two pieces. Copy-pasting from vendor docs requires manual decoupling.
- Mixing positional and keyword arguments through `*args, **kwargs` is a known footgun.
- A kwarg rename in the SDK is harder to grep because the call site no longer holds the call expression as a single unit.

Rejected on call-site ergonomics. The executor-level retry it would unlock is already not used in practice: the SDKs we depend on retry inside the call (Slack `RetryHandler`, boto3 `Config(retries=...)`), per [outbound-retry-policy.md](outbound-retry-policy.md) Shape A — so the retry slot the callable form would buy is empty anyway.

**Option 4 — Generic string-keyed pass-through (`execute("chat.postMessage", **kwargs)`).**

Same shield idea, but the operation is identified by a string. Avoids any SDK-mirror code, but throws away IDE completion and type-checking — every call is dynamically resolved and adapter authors lose the safety net.

**Option 5 — No shield; adapters call the SDK directly and translate inline.**

Each adapter holds an SDK client, owns its own retry/backoff, and maps SDK exceptions to `OperationResult` at the call site. Maximum SDK ergonomics, but duplicates resilience logic across every adapter and re-opens the leakage problem this ADR exists to close. Already rejected at the higher level by [client-adapter-responsibilities.md](client-adapter-responsibilities.md); restated here for completeness.

## Decision Outcome

**Chosen: Option 2 — shield service that exposes the typed SDK client and an awaitable-wrapping executor.**

The shield's value is the *resilience and transport-classification boundary*, not the act of mirroring the SDK. By exposing the raw SDK client as a typed attribute (`service.api`) and accepting the dev's full SDK call expression as an awaitable (`service.execute(coro)`), the shield keeps the boundary tight while leaving the SDK's surface, its typing, and its call-site syntax intact. The dev writes the call as the vendor's documentation shows it; the executor invisibly handles awaiting, budgeting, and classification.

This inverts the previous draft. Curated facade methods (Option 1) become an **optional overlay** for a small set of capabilities where a named method earns its keep — high-frequency operations, compositions of multiple SDK calls behind one capability, or call sites whose argument shape we want to lock down independently of the SDK's. The default is the awaitable-wrapping executor; facades are exceptions justified per case.

### How the shield is structured

The shield is a service class — one per vendor client (see [client-module-placement.md](client-module-placement.md) for placement). At a minimum it owns:

- **Initialization.** Acquiring credentials from injected configuration ([configuration-ownership.md](configuration-ownership.md)), constructing the underlying SDK client once with the standard retry primitives wired in (`RetryHandler` / `RateLimitErrorRetryHandler` for Slack, `Config(retries={"mode": "standard"})` for boto3, equivalent for googleapiclient), holding the instance for reuse. Authentication happens at startup, not per call.
- **A typed SDK handle.** A public attribute (commonly `api`, or named after the SDK's primary client object — `bolt`, `s3`, `drive`) that exposes the raw, fully-typed SDK client. Adapter authors call methods on this handle to *produce* awaitables. They do not await directly.
- **The executor.** `async def execute(self, aw: Awaitable[R]) -> OperationResult[R]` (synchronous variant for sync SDKs takes the call expression deferred as a thunk; see "Sync SDKs" below). The executor:
  - Applies the per-call time budget from [outbound-retry-policy.md](outbound-retry-policy.md) using `asyncio.wait_for(aw, timeout=...)`.
  - Awaits the coroutine. The SDK's native retry primitives (if any) run *inside* the awaitable, before it resolves or raises.
  - Catches typed SDK exceptions and classifies them into the closed five-status set from [operation-result-pattern.md](operation-result-pattern.md): `SUCCESS`, `NOT_FOUND`, `TRANSIENT_ERROR`, `PERMANENT_ERROR`, `UNAUTHORIZED`.
  - Honors transport-specific signals on the way out (e.g., `Retry-After` on Slack 429s preserved on the resulting `TRANSIENT_ERROR` envelope).
  - Returns `OperationResult` and never raises SDK exceptions above the client boundary.

The executor is typed `(aw: Awaitable[R]) -> OperationResult[R]`. `R` is inferred from the SDK method's return type, so the `OperationResult[R].payload` carries the SDK's response type end-to-end without manual annotation.

### Why the awaitable shape (and not callable + args)

The awaitable-wrapping shape is the same shape Python's standard library uses for boundary concerns around in-flight async work: `asyncio.shield(aw)` (cancellation protection), `asyncio.wait_for(aw, timeout)` (timeout), `asyncio.gather(*aws)` (concurrent composition). In each case, the call expression is constructed at the call site as the user would normally write it, and the wrapper takes the resulting awaitable and adds one boundary concern around it. The naming parallel with `asyncio.shield` is deliberate — this is the same pattern, applied to the SDK boundary.

The alternative — passing the SDK method as a callable plus its arguments through `*args, **kwargs` (Option 3) — would unlock executor-level retry (the executor could re-invoke the callable to produce a fresh coroutine each attempt). In practice that retry slot is empty:

- Slack's `RetryHandler` and `RateLimitErrorRetryHandler` run inside the SDK call.
- boto3's `Config(retries={"mode": "standard"})` retries inside the SDK call.
- googleapiclient's retry behavior runs inside the SDK call.

[outbound-retry-policy.md](outbound-retry-policy.md) Shape A names this — for SDKs with native retry, the application configures the SDK's retry mode rather than stacking its own loop on top. For HTTP clients without native retry (Shape B, e.g., raw `httpx`), retry is applied with a Tenacity decorator on a curated facade method — the executor still just wraps the resulting awaitable.

The cost of the callable+args form is a real ergonomic regression at every call site; the benefit is a retry capability we deliberately do not use.

### Optional curated facades

A vendor client may also expose hand-written methods that return `OperationResult` directly — `slack.post_message(...)`, `s3.put_object_idempotent(...)`. These are appropriate when:

- The operation is called from many call sites and a stable named method aids review, search, and refactor.
- The capability composes multiple SDK calls into one outcome (e.g., upload + tag + verify) that a single awaitable cannot express.
- The argument shape we want to expose to adapters is intentionally narrower than the SDK's (locking down a kwarg, providing a default, hiding a vendor-specific parameter that should not vary per call site).
- The capability needs application-level retry that does not exist in the SDK (Shape B from [outbound-retry-policy.md](outbound-retry-policy.md)). The facade carries the Tenacity decorator and returns `OperationResult` directly.

Curated facades sit *alongside* the executor, not instead of it. Internally they reuse the resilience boundary — typically by constructing the awaitable themselves and handing it to `self.execute(...)`, or by wrapping in `try`/`except` with the same classification table. They are not required to exist for every capability; engineers do not need to wait on a facade to be added before reaching for a new SDK method.

### Sync SDKs

For synchronous SDKs (e.g., parts of boto3 used outside an async context), the executor cannot take an already-constructed awaitable — calling the SDK method directly would block, defeating the wrapper. In sync code the equivalent shape is a zero-arg callable:

```python
result = ddb.execute(lambda: ddb.api.get_item(TableName=..., Key=...))
```

This is the one place a thunk appears, because there is no awaitable to hand off. The shield's sync variant exposes `execute(func: Callable[[], R]) -> OperationResult[R]`; the call expression still lives in one place (inside the lambda body) for readability and grep-ability.

### What lives where

| Concern | Location |
| --- | --- |
| Credential acquisition, SDK initialization, native-retry wiring | Shield `__init__` / factory |
| Per-call time budget (`asyncio.wait_for`), exception classification | `execute()` |
| Optional named-capability methods, including any Tenacity-decorated retry (Shape B) | Shield (facade methods) |
| Domain interpretation of `OperationResult.status` | Adapter (Path A composed service or Path B feature adapter) |
| Type translation from SDK payload to domain types | Adapter |
| Branching on capability outcomes | Feature service |

This matches the allocation in [client-adapter-responsibilities.md](client-adapter-responsibilities.md) — the shield is the implementation of the "resilient client" half of that contract.

### Slack-specific implications

- The Slack shield is constructed around `slack_bolt.async_app.AsyncApp` (Socket Mode or HTTP, per [transport-slack.md](transport-slack.md)). The SDK client is reached via `bolt_app.client`; the shield exposes `bolt` (for listener registration in feature packages) and `api` (the typed `AsyncWebClient`) alongside `execute(...)`.
- `RetryHandler` and `RateLimitErrorRetryHandler` from `slack_sdk` are composed into `AsyncWebClient` at construction; the executor adds the per-call budget and final classification rather than re-implementing rate-limit handling.
- 429 handling honors `Retry-After` up to the 30-second cap from [outbound-retry-policy.md](outbound-retry-policy.md); longer `Retry-After` values short-circuit to `TRANSIENT_ERROR` with the hint preserved on the envelope.
- The 3-second `ack()` constraint applies to inbound listeners, not to the executor. Feature handlers `ack()` immediately and dispatch the slow work to a background path; the shield's awaitables run there, not under the listener's clock.

### What this pattern is not

- **Not a universal SDK tunnel.** Feature service and domain code must not import `service.api` or call `service.execute(...)`. The shield is reached from adapter modules only — the import-governance check on vendor SDKs in [import-governance.md](import-governance.md) still applies.
- **Not a free pass on classification.** A new SDK exception class that the executor does not recognize falls through to `PERMANENT_ERROR` by default. Adding correct classification for it is part of the change that introduces the call, not a deferred fix-up.
- **Not a retry primitive at the executor level.** The executor does not re-run the awaitable; coroutines are single-use. Retry is below it (SDK-native) or beside it (Tenacity decorator on a curated facade), per [outbound-retry-policy.md](outbound-retry-policy.md).

## Consequences

**Positive:**

- Centralized resilience and exception → status mapping — one place per vendor, regardless of how many capabilities are exercised.
- Adapter authors retain full SDK typing, IDE completion, and the call expression *as written in vendor docs*. There is no cognitive cost at the call site.
- No mirror-maintenance burden: new SDK capabilities are usable through the executor immediately, with no wrapper code in between.
- No call-site decoupling: the SDK method and its arguments stay in one expression, reducing kwarg-typo and positional/keyword-mixup risk.
- Lower adapter duplication; both Path A composed services and Path B feature adapters consume the same shield.
- Replaceability preserved on the SDK/version axis ([client-adapter-responsibilities.md](client-adapter-responsibilities.md)): an SDK upgrade changes the shield internals; adapter call sites change only if the SDK signature changes.

**Tradeoffs accepted:**

- The shield exposes the raw SDK client as a public attribute. This is a deliberate ergonomic choice; the import-governance line is the rule that prevents misuse, not the API shape. Service and domain code that imports `service.api` is rejected at review and by static analysis ([import-governance.md](import-governance.md)).
- The executor cannot re-run an awaitable for retry. Retry must live inside the SDK call (native retry primitives) or in a curated facade with a Tenacity decorator (Shape B). For our current integrations this is the existing policy in [outbound-retry-policy.md](outbound-retry-policy.md), not a new constraint.
- The classification table inside `execute(...)` grows over time as new SDK error shapes are encountered. This is the cost of one canonical mapping per vendor; the benefit is that adapters never repeat it.

**Risks:**

- **Direct `await` of an SDK call in an adapter.** An adapter author writes `await slack.api.chat_postMessage(...)` directly, bypassing the executor and losing budget enforcement + classification. *Mitigation:* code review, a lint rule on `await service.api.<method>(...)` patterns (the expression should appear inside `service.execute(...)`), and a focused unit-test pattern that asserts adapter methods reach the shield's executor.
- **Misclassification in `execute()`.** A 429 is mapped to `PERMANENT_ERROR`, or a validation error becomes `TRANSIENT_ERROR`. *Mitigation:* per-shield executor tests cover each known SDK exception class against its expected `OperationResult` status; new exception types are added to the test grid with the change that introduces them.
- **Double-retry via mis-composition.** A curated facade wraps a Tenacity decorator around an SDK call that already has SDK-native retry, producing multiplicative attempts. *Mitigation:* [outbound-retry-policy.md](outbound-retry-policy.md) Shape A is the binding rule — SDKs with native retry are configured, not wrapped. Code review enforces.
- **`service.api` leakage.** A composed service in `app/infrastructure/` or a feature handler reaches for `service.api` directly. *Mitigation:* import-governance restricts SDK imports to client modules; adapter modules access the shield through dependency injection ([dependency-injection.md](dependency-injection.md)), not by importing the SDK.

## Confirmation

Compliance is verified by:

- **Shield review.** The vendor client exposes (a) a typed SDK handle attribute, (b) an `execute(awaitable) -> OperationResult` method (sync variant: `execute(callable) -> OperationResult`), and optionally (c) curated facade methods that return `OperationResult`. No public method on the shield raises SDK exceptions; every public method returns `OperationResult`.
- **Adapter review.** Adapter call sites pass the SDK call expression *inside* `service.execute(...)` (or call a curated facade) — never `await service.api.<method>(...)` as a top-level expression. Adapters interpret `OperationResult.status` in domain terms ([client-adapter-responsibilities.md](client-adapter-responsibilities.md)); they do not catch SDK exception classes.
- **Import review.** Vendor SDK imports appear only in client modules. Feature service, domain, and handler modules do not import vendor SDK modules ([import-governance.md](import-governance.md)).
- **Tests.**
  - *Executor tests*: for each classified SDK exception class, the executor produces the correct `OperationResult` status, `error_code`, and `message`; `TRANSIENT_ERROR` carries `retry_after`. Per-call timeout enforcement is verified against the budget from [outbound-retry-policy.md](outbound-retry-policy.md).
  - *Adapter tests*: against a shield mock that returns specific `OperationResult` envelopes, the adapter interprets each status correctly in domain terms. Adapter tests do not exercise SDK exception classes — that is the executor's job.
- **Static analysis.** `import-linter` (or equivalent) forbids vendor SDK imports outside client modules. A lint rule flags `await <service>.api.<method>(...)` outside a `<service>.execute(...)` enclosure.

## Source References

1. Python — `asyncio.shield(aw)`
   - URL: <https://docs.python.org/3/library/asyncio-task.html#asyncio.shield>
   - Accessed: 2026-05-12
   - Relevance: Direct precedent for the awaitable-wrapping shape and the "shield" naming. The stdlib pattern takes an in-flight awaitable and adds a single boundary concern (cancellation protection) around it, without changing how the dev writes the call. This ADR applies the same pattern to the SDK transport boundary.

2. Python — `asyncio.wait_for(aw, timeout)`
   - URL: <https://docs.python.org/3/library/asyncio-task.html#asyncio.wait_for>
   - Accessed: 2026-05-12
   - Relevance: Strongest stdlib precedent for the executor's call-site shape. `await asyncio.wait_for(client.fetch_user(id=42), timeout=10)` is structurally identical to `await service.execute(client.fetch_user(id=42))` — the SDK call expression is preserved as written, and the wrapper adds the boundary concern.

3. Python — `asyncio.gather(*aws)`
   - URL: <https://docs.python.org/3/library/asyncio-task.html#asyncio.gather>
   - Accessed: 2026-05-12
   - Relevance: Reinforces the awaitable-wrapping idiom — multiple awaitables produced at the call site, then handed to a wrapper that adds a boundary concern (concurrent composition).

4. PEP 492 — Coroutines with async and await syntax
   - URL: <https://peps.python.org/pep-0492/>
   - Accessed: 2026-05-12
   - Relevance: Defines the awaitable protocol and coroutine semantics that make this pattern work. Explains why a coroutine is single-use (the constraint that informs the "executor does not re-run" rule), and grounds the `Awaitable[T]` parameter typing.

5. Slack Bolt for Python — Acknowledging requests
   - URL: <https://docs.slack.dev/tools/bolt-python/concepts/acknowledge/>
   - Accessed: 2026-05-12
   - Relevance: Confirms the 3-second `ack()` constraint that fixes the listener-side timing budget. The shield's executor runs in the post-ack background path, not under the listener's clock.

6. Slack Web API — Rate limits
   - URL: <https://docs.slack.dev/apis/web-api/rate-limits/>
   - Accessed: 2026-05-12
   - Relevance: Documents 429 behavior and the `Retry-After` header that the executor honors during classification, with the standard 30-second cap from outbound-retry-policy.md.

7. Python Slack SDK — RetryHandler / RateLimitErrorRetryHandler
   - URL: <https://docs.slack.dev/tools/python-slack-sdk/web/#retryhandler>
   - Accessed: 2026-05-12
   - Relevance: Documents the SDK-native retry primitives that compose into the awaitable before the executor sees it. Grounds the rule that the executor does not re-run the call — retry happens *inside* the awaitable, configured at SDK construction time.

8. Boto3 — Retries
   - URL: <https://boto3.amazonaws.com/v1/documentation/api/latest/guide/retries.html>
   - Accessed: 2026-05-12
   - Relevance: Documents SDK-native retry modes (legacy / standard / adaptive) configured via `Config(retries=...)`. The shield composes with these modes per outbound-retry-policy.md Shape A; it does not stack a second retry layer on top.

9. AnyIO — Cancellation and timeouts
   - URL: <https://anyio.readthedocs.io/en/stable/cancellation.html>
   - Accessed: 2026-05-12
   - Relevance: Demonstrates that the awaitable-wrapping idiom is portable across async runtimes (asyncio, trio) — `fail_after()` and friends take in-flight awaitables and add boundary behavior. Confirms the shape is not asyncio-specific quirk but the standard Python async pattern for boundary concerns.

10. The Twelve-Factor App — Backing Services
    - URL: <https://12factor.net/backing-services>
    - Accessed: 2026-05-12
    - Relevance: Supports treating vendor services as attachable resources reached through a stable application-facing boundary. The shield is the application-facing boundary; the SDK is the attached resource.

11. Architecture Patterns with Python — Repository Pattern
    - URL: <https://www.cosmicpython.com/book/chapter_02_repository.html>
    - Accessed: 2026-05-12
    - Relevance: Reinforces dependency inversion and boundary-focused abstractions. The shield is the dependency-inverted boundary for SDK access; the call-site ergonomics (typed call expression handed to an executor) keep the abstraction thin rather than mirror-shaped.

12. Hexagonal Architecture (Ports and Adapters) — Alistair Cockburn
    - URL: <https://alistair.cockburn.us/hexagonal-architecture/>
    - Accessed: 2026-05-12
    - Relevance: Establishes the two-tier adaptation boundary that client-adapter-responsibilities.md formalizes. The shield is the transport-level adapter (SDK semantics → `OperationResult`); the secondary adapter above it is the domain-level adapter.

## Change Log

- 2026-05-12: Created. Defines the Shield Pattern as a thin vendor-client service that exposes (a) a typed SDK handle for call-site type-checking and IDE completion and (b) an awaitable-wrapping executor `execute(awaitable) -> OperationResult` that applies the per-call budget and classifies SDK exceptions into the closed five-status set. The call shape is directly modeled on `asyncio.shield(aw)` / `asyncio.wait_for(aw, timeout)` — the dev writes the SDK call expression as vendor docs show it, and hands the resulting awaitable to the shield. Curated facade methods may be added on top of the executor for high-frequency or composed capabilities (and for HTTP clients needing Tenacity-decorated application-level retry per outbound-retry-policy.md Shape B) but are not the default. The callable + args executor form (`execute(method, *args, **kwargs)`) is rejected on call-site ergonomics — its executor-level retry capability is unused in practice because the SDKs we depend on retry inside the call.
