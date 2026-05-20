---
title: "Client SDK Shield Pattern"
status: Draft
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

Vendor SDKs (`slack_sdk` / Bolt, boto3, googleapiclient, Microsoft Graph) ship rich typed surfaces that adapter authors legitimately want at the call site — IDE completion, kwarg-level typing, new vendor capabilities as they land. Raw SDK use spreads retry, backoff, and exception-classification concerns across every call site and leaks vendor exception classes upward in violation of [client-adapter-responsibilities.md](client-adapter-responsibilities.md).

The problem: provide a single resilience/classification boundary around vendor SDKs without (a) hand-mirroring the SDK behind a facade that lags upstream and erases the typed surface, (b) decoupling SDK calls from their arguments at the call site, or (c) leaking SDK exceptions into feature code.

**Constraints:**

- The shield is a vendor-client boundary concern, owned by client modules ([client-module-placement.md](client-module-placement.md)).
- All calls crossing the client boundary upward return `OperationResult` ([operation-result-pattern.md](operation-result-pattern.md), [client-adapter-responsibilities.md](client-adapter-responsibilities.md)).
- Retry/backoff/budget follow [outbound-retry-policy.md](outbound-retry-policy.md). The shield composes with SDK-native retry; it does not stack a second layer on top.
- The SDK's typed surface is preserved at the call site.
- The pattern works identically for Path A composed services and Path B feature-owned adapters ([layered-architecture.md](layered-architecture.md)).

**Non-goals:** `OperationResult` shape ([operation-result-pattern.md](operation-result-pattern.md)); retry parameters ([outbound-retry-policy.md](outbound-retry-policy.md)); per-feature adapter behavior ([client-adapter-responsibilities.md](client-adapter-responsibilities.md)); module placement ([client-module-placement.md](client-module-placement.md)); per-vendor authentication/lifecycle (see the relevant transport records).

## Considered Options

1. **Hand-mirrored facade per capability.** Rejected — lags behind the SDK, duplicates argument typing, erases IDE completion.
2. **Shield exposing the typed SDK client + awaitable-wrapping executor (chosen).** Detail below.
3. **Callable + args executor (`execute(method, *args, **kwargs)`).** Rejected — call-site ergonomics regression; executor-level retry it would unlock is unused in practice ([outbound-retry-policy.md](outbound-retry-policy.md) Shape A).
4. **Generic string-keyed pass-through.** Rejected — loses IDE completion and type-checking.
5. **No shield.** Already rejected by [client-adapter-responsibilities.md](client-adapter-responsibilities.md).

## Decision Outcome

**Chosen: a thin per-vendor shield service exposing a typed SDK handle and an awaitable-wrapping executor. Three call-site shapes cover all SDK types.**

### Shape catalogue

| Shape | When | Call site |
| --- | --- | --- |
| **(α) Typed SDK handle + awaitable executor.** The shield exposes the raw SDK client as a typed attribute. The adapter constructs the SDK call expression as vendor docs show it; the resulting awaitable is handed to `shield.execute(aw)`. | Async SDK clients held as instance state (`AsyncWebClient`, async boto3 wrappers, async Google clients). | `result = await shield.execute(shield.web.chat_postMessage(channel=..., text=...))` |
| **(β) Callable + kwargs for per-invocation callables.** When the callable is framework-constructed per request and bound to request context (so the shield cannot hold it as instance state), the adapter passes it to a dedicated shield method. Classification table is per-transport. | Bolt's `say`/`respond`; equivalent per-invocation framework callables. | `result = await shield.execute_say(say, text=..., channel=...)` |
| **(γ) Thunk for sync SDKs.** Where calling the SDK method eagerly would block, the adapter passes a zero-arg callable. | Sync portions of boto3 outside an async context. | `result = ddb.execute(lambda: ddb.api.get_item(TableName=..., Key=...))` |

All three shapes resolve to the same internal pipeline: apply per-call budget → await/invoke → classify exception into the closed five-status set → return `OperationResult`. The shield never raises SDK exceptions above the boundary.

Shape (α) is modeled on `asyncio.shield(aw)` / `asyncio.wait_for(aw, timeout)` — the SDK call expression is written at the call site as the dev would normally write it, and the wrapper adds one boundary concern around the in-flight awaitable.

### What the shield owns

- **Initialization.** Credentials from injected configuration ([configuration-ownership.md](configuration-ownership.md)); SDK client constructed once with native retry primitives (`RetryHandler` for `slack_sdk`; `Config(retries=...)` for boto3).
- **Per-call budget.** `asyncio.wait_for(aw, timeout=...)` per [outbound-retry-policy.md](outbound-retry-policy.md).
- **Classification.** One catalogue per transport, registered once per shield; maps into the closed five-status set from [operation-result-pattern.md](operation-result-pattern.md). Preserves recovery signals (e.g., `Retry-After` on 429s).

The executor is typed `(aw: Awaitable[R]) -> OperationResult[R]`; `OperationResult[R].payload` carries the SDK's response type end-to-end.

### Pure-data SDK imports are exempt from containment

The import-governance rule restricts vendor SDK **transport** imports to client modules. Pure-data model imports — `slack_sdk.models.*`, typed shapes from `mypy_boto3_*`, etc. — are **permitted in any layer** that constructs vendor-shaped payloads. These classes have no I/O, raise only programmer-error classes (e.g., `SlackObjectFormationError`), and their SDK auto-converts them at the wire boundary. Forbidding them forces features back to inline dict literals — the opposite of the goal.

Construction of these objects does not return `OperationResult`. The shield wraps only the eventual wire call that consumes them.

### Optional curated facades

A shield may expose hand-written methods returning `OperationResult` directly. These earn their place when:

- The capability is high-frequency and a named method aids review and refactor.
- Multiple SDK calls compose into one outcome.
- The argument shape should be narrower than the SDK's.
- Application-level retry is needed (Shape B from [outbound-retry-policy.md](outbound-retry-policy.md)); the facade carries the Tenacity decorator.

Curated facades sit *alongside* the executor, not instead of it. They internally call `self.execute(...)`. Authors do not need to wait on a facade to use a new SDK method.

### What lives where

| Concern | Location |
| --- | --- |
| Credential acquisition, SDK initialization, native-retry wiring | Shield `__init__` / factory |
| Per-call budget, exception classification | `execute(...)` / `execute_<name>(...)` |
| Optional named-capability methods (incl. Tenacity-decorated retry for Shape B) | Shield (facade methods) |
| Domain interpretation of `OperationResult.status` | Adapter |
| Type translation SDK payload → domain types | Adapter |
| Branching on capability outcomes | Feature service |

### Slack-specific implementation

The Slack-specific shield construction, `shield_listener_callables` middleware, `ShieldedSay`/`ShieldedRespond` wrappers, and both Slack error-code classification tables are specified in [transport-slack-shield.md](transport-slack-shield.md).

### What this pattern is not

- **Not a universal SDK tunnel.** Vendor SDK transport modules stay in client modules per [import-governance.md](import-governance.md). Pure-data model classes are exempt as above.
- **Not a free pass on classification.** An unrecognized SDK exception falls through to `PERMANENT_ERROR`. Adding correct classification is part of the change that introduces the call.
- **Not a retry primitive at the executor level.** Coroutines are single-use; the executor cannot re-run the awaitable. Retry lives inside the SDK call (native) or in a Tenacity-decorated facade (Shape B).

## Consequences

**Positive:**

- One resilience and classification boundary per vendor, regardless of how many capabilities are exercised.
- Full SDK typing, IDE completion, and vendor-doc call syntax preserved at the call site.
- No mirror-maintenance burden — new SDK capabilities usable through the executor immediately.
- The shape catalogue covers async, per-invocation, and sync SDKs through one internal pipeline.
- Pure-data model imports let features use typed payload construction without weakening the transport boundary.

**Tradeoffs accepted:**

- The shield exposes the raw SDK client as a public attribute. Import-governance, not the API shape, prevents misuse.
- The executor cannot re-run an awaitable. Retry must live inside the SDK call or in a Tenacity-decorated facade.
- Classification tables grow over time — one per vendor, never repeated in adapters.

**Risks:**

- **Direct `await` of an SDK call** (`await shield.web.<method>(...)`) bypasses budget and classification. Mitigation: lint rule; unit tests asserting adapter methods reach the executor.
- **Misclassification** — a 429 mapped to `PERMANENT_ERROR`. Mitigation: per-shield executor tests cover each known exception class; new types are added with the change that introduces them.
- **Double-retry** — Tenacity facade around an SDK call that already has native retry. Mitigation: [outbound-retry-policy.md](outbound-retry-policy.md) Shape A is the binding rule.
- **SDK transport leakage into feature code.** Mitigation: import-governance; DI ([dependency-injection.md](dependency-injection.md)).

## Confirmation

- **Shield review.** Exposes (a) typed SDK handle (shape α), (b) `execute(awaitable) -> OperationResult` and `execute_<name>(callable, **kwargs) -> OperationResult` (shape β), (c) sync `execute(callable) -> OperationResult` (shape γ), (d) optional curated facades. No public method raises SDK exceptions.
- **Adapter review.** Call sites pass SDK call expressions inside `shield.execute(...)` or a curated facade — never `await shield.<handle>.<method>(...)` as a top-level expression.
- **Import review.** Vendor SDK transport imports only in client modules. Pure-data model imports permitted broadly ([import-governance.md](import-governance.md)).
- **Tests.** Executor tests: each classified exception → correct status, `error_code`, `retry_after`; timeout enforcement verified. Adapter tests: shield mock returning `OperationResult` envelopes; no SDK exception classes exercised.
- **Static analysis.** `import-linter` forbids vendor transport imports outside client modules; lint rule flags `await <shield>.<handle>.<method>(...)` outside `execute(...)`.

## Source References

1. Python — `asyncio.shield` / `asyncio.wait_for` / `asyncio.gather`
   - URLs: <https://docs.python.org/3/library/asyncio-task.html#asyncio.shield>, <https://docs.python.org/3/library/asyncio-task.html#asyncio.wait_for>
   - Accessed: 2026-05-12
   - Relevance: Direct precedent for shape (α) — stdlib wraps an in-flight awaitable with one boundary concern without changing the call expression.

2. PEP 492 — Coroutines with async and await syntax
   - URL: <https://peps.python.org/pep-0492/>
   - Accessed: 2026-05-12
   - Relevance: Coroutines are single-use — grounds the "executor does not re-run" rule and `Awaitable[T]` parameter typing.

3. Slack Python SDK — `RetryHandler` / `RateLimitErrorRetryHandler`
   - URL: <https://docs.slack.dev/tools/python-slack-sdk/web/#retryhandler>
   - Accessed: 2026-05-12
   - Relevance: SDK-native retry primitives run inside the awaitable before the executor sees it. Grounds Shape A from [outbound-retry-policy.md](outbound-retry-policy.md).

4. Boto3 — Retries
   - URL: <https://boto3.amazonaws.com/v1/documentation/api/latest/guide/retries.html>
   - Accessed: 2026-05-12
   - Relevance: SDK-native retry via `Config(retries=...)`; shield composes with the mode, does not stack on top.

5. Slack Python SDK — `slack_sdk.models` (Block Kit and view classes)
   - URL: <https://docs.slack.dev/tools/python-slack-sdk/reference/models/blocks/>
   - Accessed: 2026-05-13
   - Relevance: Typed pure-data classes; `AsyncWebClient` auto-converts instances at the boundary. Grounds the pure-data import carve-out.

6. Hexagonal Architecture — Alistair Cockburn
   - URL: <https://alistair.cockburn.us/hexagonal-architecture/>
   - Accessed: 2026-05-12
   - Relevance: Two-tier adaptation boundary — the shield is the transport-level adapter; the secondary adapter above it handles domain translation.

## Change Log

- 2026-05-12: Created. Shield exposes a typed SDK handle and `execute(awaitable) -> OperationResult`; curated facades optional. Callable+args and string-keyed forms rejected.
- 2026-05-13: Added shape catalogue (α awaitable, β per-invocation callable, γ sync thunk); excluded `ack()` from shield; carved `slack_sdk.models.*` out of vendor-import containment. Slack-specific implementation delegated to [transport-slack-shield.md](transport-slack-shield.md).
