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

1. **Authenticated client construction** — `get_<vendor>_client()`-style factories that set SDK-native resilience once and explicitly, never by inheriting SDK defaults:
   - **Timeouts.** Every factory sets a per-attempt timeout: boto3 `connect_timeout`/`read_timeout`; for `google-api-python-client`, an `httplib2.Http(timeout=...)` wrapped in the authorized http. Attempts × timeout, plus backoff, must fit the caller's deadline.
   - **Retry.** Use only the SDK's own primitives:
     - boto3: `Config(retries={"mode": "standard", "max_attempts": N})`, always setting `mode`, because the SDK default is still `legacy` ([boto3 retries guide](https://docs.aws.amazon.com/boto3/latest/guide/retries.html)).
     - `google-api-python-client`: `num_retries` is an argument of each `execute()`, so the factory applies a default through `build(requestBuilder=...)`. `build(num_retries=...)` only retries fetching the discovery document. Google's retry loop ignores `Retry-After` and doesn't cap backoff, so keep the count small.
   - **Non-idempotent writes.** Neither SDK checks idempotency before retrying: both re-send writes after 5xx, throttling or timeouts ([AWS Builders' Library](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/)). A write that isn't naturally idempotent (create, copy, send) must either use the vendor's idempotency mechanism (client token, conditional write) or go through a factory variant with retries disabled. See [reliability.md](reliability.md).
   - **Threads.** boto3 clients are generally thread-safe; sessions and resources are not. A Google `Resource` runs on `httplib2.Http`, which is [not thread-safe](https://github.com/googleapis/google-api-python-client/blob/main/docs/thread_safety.md). Share a `Resource` across threads only when each request builds its own `Http`.

   **No hand-rolled retry loops anywhere, ever.** Blocking SDK calls invoked from async code are offloaded with `asyncio.to_thread`, which is where the thread rule matters.
2. **A classification function** — `classify_<vendor>_error(exc) -> tuple[OperationStatus, error_code, retry_after]`, one table per vendor mapping the SDK's *expected* exception families onto the closed status set. Unexpected exceptions (a `KeyError` is a bug, not an outcome) are **not** classified — they propagate and crash loudly.

Clients **raise typed SDK exceptions**. They do not return `OperationResult`, do not import feature or infrastructure code (except the `infrastructure.operations` shared kernel, needed only for the classification function's return type), and contain no business logic.

**The adapter is the boundary.** The Protocol implementation — a Path A composed service in `infrastructure/`, or a Path B feature adapter in `packages/<feature>/adapters/` — calls the client inside `try/except`, uses the vendor's classification function, and returns `OperationResult`. It also translates payloads into domain/capability types. That is the whole Gateway (Fowler) / Anti-Corruption Layer role, in one tier. The adapter must not leak vendor-only concepts (Google Drive `appProperties`, Drive `q` expressions, SDK field projection strings) through a vendor-neutral Path A Protocol. Those stay in the provider implementation, or in a Path B adapter whose feature explicitly depends on them. A Path A contract is portable only when its operation names and models stay meaningful for at least one other plausible provider ([layers.md](layers.md)).

**No standing wrapper class** exposing the SDK handle. Adapters hold the SDK client directly (they are allowed to — the adapter file *is* the boundary), which keeps the vendor's typed surface, IDE completion, and documentation examples intact with zero mirror-maintenance. The term "shield" is retired.

**Pure-data SDK model imports** (typed request/response shapes with no I/O) are permitted anywhere payload construction happens — forbidding them would force features back to dict literals.

**How to *type* the SDK handle without wrapping it** — boto3 stubs vs. Google discovery, and the retired dispatcher/facade anti-patterns — is the companion decision [sdk-typing.md](sdk-typing.md).

## Consequences

- One place per vendor answers "how are errors of this vendor interpreted"; adding a call site means adding a `try/except classify` in an adapter, not learning a wrapper API.
- Within one outbound call, retry has exactly one owner: the SDK, configured at construction. Retries above the adapter (job re-runs, redelivered events) still multiply attempts, which is why non-idempotent writes follow the rule above.
- Cost: adapter authors write the `try/except` themselves. That five-line pattern is the price of not maintaining a wrapper layer, and it keeps programmer errors crashing instead of becoming `PERMANENT_ERROR` data.
- The existing `AWSShield` is refactored into a classification function + factory config; `_next.py` twins resolve into this shape.
- `google-api-python-client` is in maintenance mode and still requires `google-auth-httplib2`, which was archived on 2026-02-09 and is no longer maintained. That transport is a known supply-chain risk, watched through [dependency-scanning.md](dependency-scanning.md).

## Checks

- grep: no `time.sleep`/`tenacity`/`backoff` retry loops in `app/integrations/`.
- Each vendor package exports exactly: factories, `classify_<vendor>_error`, settings ([configuration.md](configuration.md)).
- Classification tests per vendor: each mapped exception family → expected status/`error_code`/`retry_after`; one unmapped exception → propagates.
- import-linter: `integrations` imports nothing above `infrastructure.operations`.
- Factory tests assert explicit resilience settings. For boto3, `Config` sets `mode`, `max_attempts`, `connect_timeout` and `read_timeout`. Google services are built with a `requestBuilder` retry default and an `Http` that has an explicit timeout.
- Review: every non-idempotent write names its idempotency mechanism or uses a retries-disabled handle.
- Review: no Google `Resource` is cached and shared across threads unless each request builds its own `Http`.

## Migration

Ticket: client-layer convergence (delete `infrastructure/clients/`, resolve `_next` twins, refactor `AWSShield`). Tolerated until closed:
- the seven baselined deprecated-client consumers;
- the shield-shaped AWS client;
- Google factories that inherit the library's 60-second default timeout (TASK-25.1.6.14);
- non-idempotent Google writes (Drive create and copy) issued on the retrying handle (TASK-25.1.6.15).

**Changes:**
- 2026-09-08: adapters must not leak vendor-only concepts through Path A Protocols.
- 2026-09-10: added explicit timeout, non-idempotent write and thread-safety rules, and corrected how Google retries are configured.
