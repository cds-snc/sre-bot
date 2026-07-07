---
status: Accepted
date: 2026-07-06
applies: target
scope: How the app calls external services — clients, retry, and exception classification.
---

# Outbound Clients

## Context

Vendor SDKs each have their own retry knobs and exception hierarchies. The legacy executors hand-rolled retry loops (blocking `time.sleep` in an async app, nested retries over SDKs that already retried) — a real antipattern we correctly diagnosed. The correction then over-corrected into a "shield" layer: a standing wrapper class exposing the raw SDK handle it forbade you to use, stacked under a second adapter tier that mostly passed results through. Two wrapping tiers, both speaking `OperationResult`, is wrapper-around-wrapper. This applies to every **outbound boundary call** (AWS, Google Workspace, MaxMind, Opsgenie, Notify, Sentinel, Trello) — **including a platform's Web API when a feature acts on it as a target** (e.g. Slack usergroup writes; the platform's *inbound transport* is separately governed by [platform-transports.md](platform-transports.md)). In that case `integrations/<platform>/` is the vendor package and the feature's adapter classifies its errors exactly as below.

## Decision

**One adaptation tier. Clients raise; adapters classify.**

**`app/integrations/<vendor>/` provides exactly two things:**

1. **Authenticated client construction** — `get_<vendor>_client()`-style factories with SDK-native resilience configured once: timeouts, and retry via the SDK's own primitives (boto3 `Config(retries={"mode": "standard"})`, `google-api-client` `num_retries`, per-SDK equivalents). **No hand-rolled retry loops anywhere, ever.** Blocking SDK calls invoked from async code are offloaded (`asyncio.to_thread`).
2. **A classification function** — `classify_<vendor>_error(exc) -> tuple[OperationStatus, error_code, retry_after]`, one table per vendor mapping the SDK's *expected* exception families onto the closed status set. Unexpected exceptions (a `KeyError` is a bug, not an outcome) are **not** classified — they propagate and crash loudly.

Clients **raise typed SDK exceptions**. They do not return `OperationResult`, do not import feature or infrastructure code (except the `infrastructure.operations` shared kernel, needed only for the classification function's return type), and contain no business logic.

**The adapter is the boundary.** The Protocol implementation — a Path A composed service in `infrastructure/`, or a Path B feature adapter in `packages/<feature>/adapters/` — calls the client inside `try/except`, uses the vendor's classification function, and returns `OperationResult`. It also translates payloads into domain/capability types. That is the whole Gateway (Fowler) / Anti-Corruption Layer role, in one tier.

**No standing wrapper class** exposing the SDK handle. Adapters hold the SDK client directly (they are allowed to — the adapter file *is* the boundary), which keeps the vendor's typed surface, IDE completion, and documentation examples intact with zero mirror-maintenance. The term "shield" is retired.

**Pure-data SDK model imports** (typed request/response shapes with no I/O) are permitted anywhere payload construction happens — forbidding them would force features back to dict literals.

## Consequences

- One place per vendor answers "how are errors of this vendor interpreted"; adding a call site means adding a `try/except classify` in an adapter, not learning a wrapper API.
- Retry has exactly one owner (the SDK, configured at construction). No double-retry stacks are possible by construction.
- Cost: adapter authors write the `try/except` themselves. That five-line pattern is the price of not maintaining a wrapper layer, and it keeps programmer errors crashing instead of becoming `PERMANENT_ERROR` data.
- The existing `AWSShield` is refactored into a classification function + factory config; `_next.py` twins resolve into this shape.

## Checks

- grep: no `time.sleep`/`tenacity`/`backoff` retry loops in `app/integrations/`.
- Each vendor package exports exactly: factories, `classify_<vendor>_error`, settings ([configuration.md](configuration.md)).
- Classification tests per vendor: each mapped exception family → expected status/`error_code`/`retry_after`; one unmapped exception → propagates.
- import-linter: `integrations` imports nothing above `infrastructure.operations`.

## Migration

Ticket: client-layer convergence (delete `infrastructure/clients/`, resolve `_next` twins, refactor `AWSShield`). Tolerated until closed: the seven baselined deprecated-client consumers; shield-shaped AWS client.
