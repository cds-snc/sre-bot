---
status: Accepted
date: 2026-07-06
applies: target
scope: How the app calls external services — clients, retry, and exception classification.
---

# Outbound Clients

## Context

Vendor SDKs each have their own retry knobs and exception hierarchies. The legacy executors hand-rolled retry loops (blocking `time.sleep` in an async app, nested retries over SDKs that already retried) — a real antipattern we correctly diagnosed. The correction then over-corrected into a standing wrapper class exposing the raw SDK handle it forbade you to use, stacked under a second adapter tier that mostly passed results through. Two wrapping tiers, both speaking `OperationResult`, is wrapper-around-wrapper. This applies to every **outbound boundary call** (AWS, Google Workspace, MaxMind, Opsgenie, Notify, Sentinel, Trello) — **including a platform's Web API when a feature acts on it as a target** (e.g. Slack usergroup writes; the platform's *inbound transport* is separately governed by [platform-transports.md](platform-transports.md)). In that case `integrations/<platform>/` is the vendor package and the feature's adapter classifies its errors exactly as below.

## Decision

**One adaptation tier. Clients raise; adapters classify.**

**`app/integrations/<vendor>/` provides exactly two things:**

1. **Authenticated client construction** — `get_<vendor>_client()`-style factories that set SDK-native resilience once and explicitly, never by inheriting SDK defaults:
   - **Timeouts.** Every factory sets a per-attempt timeout: boto3 `connect_timeout`/`read_timeout`; for `google-api-python-client`, an `httplib2.Http(timeout=...)` wrapped in the authorized http. Attempts × timeout, plus backoff, must fit the caller's deadline.
   - **Retry.** Use only the SDK's own primitives:
     - boto3: `Config(retries={"mode": "standard", "max_attempts": N})`, always setting `mode`, because the SDK default is still `legacy` ([boto3 retries guide](https://docs.aws.amazon.com/boto3/latest/guide/retries.html)).
     - `google-api-python-client`: `num_retries` is an argument of each `execute()`, so the factory applies a default through `build(requestBuilder=...)`. `build(num_retries=...)` only retries fetching the discovery document. Google's retry loop ignores `Retry-After` and doesn't cap backoff, so keep the count small.
   - **Non-idempotent writes.** Neither SDK checks idempotency before retrying: both re-send writes after 5xx, throttling or timeouts ([AWS Builders' Library](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/)). A write that isn't naturally idempotent (create, copy, send) must either use the vendor's idempotency mechanism (client token, conditional write) or go through a factory variant with retries disabled. See [reliability.md](reliability.md).
   - **No network I/O at construction.** A factory builds the handle and returns. Credentials, including an assumed role, resolve on the first API call and refresh themselves before they expire. For boto3 that is botocore's `DeferredRefreshableCredentials` with an `AssumeRoleCredentialFetcher`, not an `sts.assume_role` call in the factory. Building a client therefore never fails because a vendor or STS is down, and building one at boot is safe. Verifying credentials at boot is an explicit, classified credential check that alerts and never aborts ([lifecycle.md](lifecycle.md)), never a side effect of construction.
   - **Threads.** boto3 clients are generally thread-safe; sessions and resources are not. A Google `Resource` runs on `httplib2.Http`, which is [not thread-safe](https://github.com/googleapis/google-api-python-client/blob/main/docs/thread_safety.md). Share a `Resource` across threads only when each request builds its own `Http`.

   **No hand-rolled retry loops anywhere, ever.** Blocking SDK calls invoked from async code are offloaded with `asyncio.to_thread`, which is where the thread rule matters.
2. **A classification function** — `classify_<vendor>_error(exc) -> tuple[OperationStatus, error_code, retry_after]`, one table per vendor mapping the SDK's *expected* exception families onto the closed status set. Unexpected exceptions (a `KeyError` is a bug, not an outcome) are **not** classified — they propagate and crash loudly.

Clients **raise typed SDK exceptions**. They do not return `OperationResult`, import nothing from the app except the shared types in `contracts/` (`OperationStatus`, needed only for the classification function's return type), and contain no business logic. `integrations/` holds outbound clients only: a platform's inbound runtime (Bolt, Socket Mode) is host code in `server/` ([platform-transports.md](platform-transports.md)), while its Web API client lives here, because a feature may act on the platform as a target.

**The adapter is the boundary.** The Protocol implementation — a file in a feature's or capability's `adapters/`, or a hosting implementation in `infrastructure/` of a `contracts/` Protocol ([plugin-architecture.md](plugin-architecture.md)) — calls the client inside `try/except`, uses the vendor's classification function, and returns `OperationResult`. It also translates payloads into domain types. That is the whole Gateway (Fowler) / Anti-Corruption Layer role, in one tier. `adapters/` files are the only feature or capability files that import `integrations/`. A Path B adapter serves a feature that exists to act on one specific system, so its Protocol may be shaped by that system. An adapter behind a vendor-neutral Protocol (a hosting contract, or a capability's `api.py`) must not leak vendor-only concepts (Google Drive `appProperties`, Drive `q` expressions, SDK field projection strings) through it. Those stay in the implementation. Such a Protocol is portable only when its operation names and models stay meaningful for at least one other plausible provider.

**No standing wrapper class** exposing the SDK handle. Adapters hold the SDK client directly (they are allowed to — the adapter file *is* the boundary), which keeps the vendor's typed surface, IDE completion, and documentation examples intact with zero mirror-maintenance.

**Pure-data SDK model imports** (typed request/response shapes with no I/O) are permitted anywhere payload construction happens — forbidding them would force features back to dict literals.

**How to *type* the SDK handle without wrapping it** — boto3 stubs vs. Google discovery, and the retired dispatcher/facade anti-patterns — is the companion decision [sdk-typing.md](sdk-typing.md).

## Consequences

- One place per vendor answers "how are errors of this vendor interpreted"; adding a call site means adding a `try/except classify` in an adapter, not learning a wrapper API.
- Within one outbound call, retry has exactly one owner: the SDK, configured at construction. Retries above the adapter (job re-runs, redelivered events) still multiply attempts, which is why non-idempotent writes follow the rule above.
- Cost: adapter authors write the `try/except` themselves. That five-line pattern is the price of not maintaining a wrapper layer, and it keeps programmer errors crashing instead of becoming `PERMANENT_ERROR` data.
- `google-api-python-client` is in maintenance mode and still requires `google-auth-httplib2`, which was archived on 2026-02-09 and is no longer maintained. That transport is a known supply-chain risk, watched through [dependency-scanning.md](dependency-scanning.md).

## Checks

- grep: no `time.sleep`/`tenacity`/`backoff` retry loops in `app/integrations/`.
- Each vendor package exports exactly: factories, `classify_<vendor>_error`, settings ([configuration.md](configuration.md)).
- Classification tests per vendor: each mapped exception family → expected status/`error_code`/`retry_after`; one unmapped exception → propagates.
- import-linter: `integrations` imports nothing from the app except the shared types in `contracts/`; features and capabilities import `integrations` only inside `adapters/`.
- Factory tests: building every factory, including a role-bearing AWS client, opens no outbound connection (`socket.connect` spy).
- Factory tests assert explicit resilience settings. For boto3, `Config` sets `mode`, `max_attempts`, `connect_timeout` and `read_timeout`. Google services are built with a `requestBuilder` retry default and an `Http` that has an explicit timeout.
- Review: every non-idempotent write names its idempotency mechanism or uses a retries-disabled handle.
- Review: no Google `Resource` is cached and shared across threads unless each request builds its own `Http`.

## Migration

Tickets: TASK-25 (per-vendor contract), TASK-87 (Google write replay safety) and TASK-98 (lazy, refreshable AWS role credentials). Every vendor diverges as listed. Tolerated until closed:
- `integrations/aws/client.py` assumes a role through STS while building a client and never reuses the credentials, so a role-bearing client costs one STS call per build and fails at construction when STS or credentials fail (TASK-98);
- `integrations/` importing `infrastructure.operations` instead of `contracts/`, plus 11 other `infrastructure` imports (settings under `infrastructure.configuration`, `infrastructure.audit.models`, `infrastructure.i18n`, `infrastructure.slack.settings`); import-linter is not enforced yet, and these become its ignore entries when TASK-18 lands;
- non-idempotent Google writes (Drive create and copy) issued on the retrying handle;
- a per-call `num_retries=0` override at six Google writes (Calendar event insert, Meet space create, incident_draft Drive copy and Docs batchUpdate, incident documents apply_document_edits, Sheets values.append): a call-site exception to "no retry decision repeated at call sites";
- a replayed Directory `members.insert` that returns 409 is not treated as success;
- `MaxMindClient` classifies and returns `OperationResult` inside the vendor package;
- Slack has no `classify_slack_error` and builds its Web client at four sites; its transport modules still live in `integrations/slack/` (TASK-26);
- Opsgenie: business operations in the vendor package, no classifier, no explicit timeout;
- Sentinel: the audit sink lives in the vendor package, which has no classifier and imports `infrastructure.audit`;
- Notify: `revoke_api_key` lives in the vendor package, which has no classifier;
- Trello: ATIP operations in the vendor package, no classifier, no explicit timeout or retry;
- OpenAI: the `Summarizer` port and implementation live in the vendor package, and `classify_openai_error` returns `OperationResult`;
- every vendor's settings except AWS's still live in `infrastructure/configuration/integrations/` (TASK-24).

**Changes:**
- 2026-09-08: adapters must not leak vendor-only concepts through Path A Protocols.
- 2026-09-10: added explicit timeout, non-idempotent write and thread-safety rules, and corrected how Google retries are configured.
- 2026-09-11: Google factories set an explicit per-attempt timeout; recorded the per-call `num_retries=0` override at six non-idempotent Google writes as a tolerated divergence.
- 2026-09-17: removed the closed 'seven baselined deprecated-client consumers' tolerance (TASK-22.5 migrated them; TASK-25.2.5.7 retired the guard).
- 2026-09-24: removed the closed AWS wrapper-class tolerance and references to deleted code; Migration lists every open divergence under its epic ticket; integrations import only `contracts/` shared types, and adapters live in a feature's or capability's `adapters/` or in `infrastructure/`.
- 2026-09-25: factories do no network I/O; assumed-role credentials are deferred and refreshable; boot credential verification is an explicit check.
