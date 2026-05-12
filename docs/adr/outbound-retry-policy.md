---
title: "Outbound Retry Policy"
status: Accepted
type: Standard
tier: Tier-2
governance_domain: [application]
concerns: [architecture]
constrained_by: [client-adapter-responsibilities.md, operation-result-pattern.md, handler-idempotency.md, logging-observability.md, configuration-ownership.md, infrastructure-service-classification.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Outbound Retry Policy

## Context and Problem Statement

The application calls many external services: AWS APIs (DynamoDB, SQS, IAM Identity Center), Slack Web API, Microsoft Graph, identity-provider JWKS endpoints, GitHub APIs. Every one of these calls can fail transiently — a brief network blip, a rate-limit response, a load-shed 503, a timed-out TLS handshake — and the right reaction in those cases is to wait briefly and try again. The wrong reaction — failing the request, surfacing the error to the user, returning `TRANSIENT_ERROR` to the handler — turns routine cloud-service noise into user-visible failure.

The problem this record addresses: **what is the standard policy for retrying outbound calls — which errors retry, how many attempts, on what backoff, and where in the architecture the retry happens?** The answer determines:

1. Whether transient infrastructure noise (timeouts, throttling, brief 5xx) becomes user-visible failure or stays absorbed at the boundary.
2. Whether retry is owned at the vendor-client layer (one place per integration), at the adapter layer (one place per Protocol), or at the handler layer (everywhere). The wrong choice produces nested retry loops with multiplicative cost.
3. Which `OperationResult` statuses retry (only `TRANSIENT_ERROR`) and which do not (`PERMANENT_ERROR`, `UNAUTHORIZED`, `NOT_FOUND`).
4. How retry composes with the application's idempotency contract — both the outbound call's upstream idempotency and the inbound idempotency mechanism that already protects handlers.

**Constraints:**

- Vendor clients own transport-level concerns including authentication, pagination, and retry policy ([client-adapter-responsibilities.md](client-adapter-responsibilities.md)). Retries are vendor-transport concerns, not domain concerns.
- Adapters translate vendor exceptions to the closed five-status `OperationResult` envelope ([operation-result-pattern.md](operation-result-pattern.md)). The adapter sees only the final outcome of the call, after the client's retry loop has already run.
- Inbound retry handling — Slack/Teams/SQS redelivery, HTTP retries from upstream senders — is owned by [handler-idempotency.md](handler-idempotency.md). This record is about the *outbound* direction.
- Scheduled background work has its own error-isolation contract ([background-execution.md](background-execution.md)); retry inside a job's body, when applicable, follows this record.
- The application observes user-perceived latency budgets: a Slack interaction's 3-second ack window, an HTTP request's nominal 30-second timeout. The retry budget for any single call must compose inside the surrounding budget.

**Non-goals:**

- This record does not introduce a circuit breaker. Circuit-breaker semantics (open / half-open / closed state machines coordinated across processes) are out of scope; if a future need surfaces, a separate record will introduce them.
- This record does not pick per-feature timeout values. Timeouts are owned by each vendor client's settings ([configuration-ownership.md](configuration-ownership.md)); this record fixes the *shape* and *budget*, not the per-vendor numbers.
- This record does not dictate the retry implementation for SDKs that ship one (boto3, googleapiclient). Those SDKs have their own retry mechanisms; this record names the policy parameters those mechanisms must be configured against, not the mechanism itself.
- This record does not change inbound retry handling, idempotency-key derivation, or queue-DLQ semantics. Those are owned by [handler-idempotency.md](handler-idempotency.md) and [message-queuing.md](message-queuing.md).

## Considered Options

**Option 1 — A standardized policy (max attempts, exponential backoff with full jitter, total time budget, retriable-error catalogue) applied at the vendor-client layer; SDKs with built-in retry are configured against the policy; HTTP clients without built-in retry use Tenacity as the wrapper; adapters are retry-free and see only the final outcome.** Each integration applies the policy once, in one place — its client. The adapter catches whatever exception the client raises after retries are exhausted (or the success it returns when retries succeed) and maps to `OperationResult`.

**Option 2 — Retry at the adapter layer.** The adapter wraps every call site in Tenacity. The vendor client is retry-free.

**Option 3 — Retry at the handler layer.** Each handler decides whether and how to retry calls into its services.

**Option 4 — No standardized policy; per-integration ad hoc.** Each integration's author picks parameters.

## Decision Outcome

**Chosen: Option 1 — a standardized policy applied at the vendor-client layer; SDKs with native retry are configured against the policy; non-SDK HTTP clients use Tenacity; adapters are retry-free.**

Vendor clients are the right home for retry: they sit closest to the failure, they hold the SDK's exception types, and several of them (boto3 in particular) have first-class retry mechanisms that are best-of-breed and not worth duplicating. The adapter's job is domain mapping; adding retry there would either duplicate the client's retry (the multiplicative-cost problem) or contradict it (a partial state where the client gives up but the adapter retries the same SDK call). Handler-level retry (Option 3) is the wrong layer entirely — handlers are bounded in size and code paths and should not contain retry plumbing. Ad hoc per-integration policies (Option 4) leak operational properties (max attempts, backoff shape) into per-feature concerns the operator cannot reason about uniformly.

### The standard policy

Every outbound integration applies the same policy *parameters*. The mechanism that implements the parameters varies (SDK config vs. Tenacity decorator vs. equivalent), but the parameters do not.

| Parameter | Value | Rationale |
| --- | --- | --- |
| Max attempts (initial + retries) | 3 | Two retries after the first attempt. Aligns with the AWS SDK standard mode default and is the broadly-cited "good enough" value for transient cloud-service noise. |
| Backoff strategy | Exponential with full jitter | Two retries on the same backoff schedule across N processes thunder; full jitter spreads them. |
| Backoff base | 1 second | First retry waits 0–1 s; second retry waits 0–2 s. |
| Backoff max delay | 30 seconds | Caps long sleeps for outlier cases (e.g., Slack `Retry-After: 60`); a vendor that asks for longer than 30 s gets one attempt only. |
| Total per-call time budget | 60 seconds | The retry loop returns `TRANSIENT_ERROR` rather than continuing to retry past this wall-clock budget, regardless of attempts remaining. |
| Per-attempt timeout | 10 seconds (default) | Each individual call has its own connect+read timeout, configured at the SDK or HTTP client. The retry loop does not wait indefinitely on a hung call. |

These parameters are the **defaults**. A specific integration may justify an override (a higher per-attempt timeout for a long-running operation; a lower max-attempts for a call that the user's surrounding budget cannot absorb). Overrides are documented at the client; they are not silently introduced.

### What retries

The policy retries on:

- **Network errors** at the transport layer: connection refused, connection reset, DNS resolution failure, TLS handshake timeout, socket read/write timeout.
- **HTTP 5xx responses** from the upstream: 500, 502, 503, 504. (501 is treated as permanent — the upstream has explicitly disclaimed support.)
- **HTTP 429 (Too Many Requests).** The retry honors any `Retry-After` header up to the 30-second cap; absent the header, the standard backoff applies.
- **SDK-typed transient exceptions** for SDKs that classify their errors: `botocore.exceptions.ConnectionError`, `slack_sdk.errors.SlackApiError` whose `error == "ratelimited"`, etc. The client knows which exceptions its SDK considers transient.

The policy does **not** retry on:

- **HTTP 4xx (other than 429).** Validation errors, authentication failures, authorization failures, not-found responses are by definition not "the next attempt will work" cases.
- **`PERMANENT_ERROR`-shaped SDK errors** — e.g., DynamoDB `ValidationException`, `ResourceNotFoundException`, `ConditionalCheckFailedException` (which is a domain outcome, not a failure), Slack `not_authed`, `invalid_auth`, `channel_not_found`.
- **`UNAUTHORIZED`-shaped errors** (401, 403). Re-attempting with the same credentials produces the same answer.
- **Application bugs** — `TypeError`, `KeyError`, `ValueError` arising from inside our own code. These are not transient; they should not be silently absorbed by retry.

The catalogue is implemented as part of the client; the adapter does not see the noise.

### Where retry lives, in three shapes

#### Shape A — SDKs with native retry (boto3, googleapiclient)

The vendor client configures the SDK's built-in retry mode against the standard policy parameters. For boto3:

```python
import boto3
from botocore.config import Config

config = Config(
    retries={"max_attempts": 3, "mode": "standard"},
    connect_timeout=10,
    read_timeout=10,
)
client = boto3.client("dynamodb", config=config)
```

Boto3's "standard" mode implements exponential backoff with full jitter, retries on the documented set of transient errors, and respects throttling responses. The application does not wrap boto3 calls in **any** retry loop on top — neither a Tenacity decorator nor a hand-rolled `for attempt in range(): try: ... except: time.sleep(...)` pattern. Either would stack a second retry layer on top of a working one, producing nested attempts (3 application-level × 3 SDK-level = 9 uncoordinated tries on a single transient failure) and, with non-jittered hand-rolled backoff, correlated retry storms across N processes.

The same rule applies to every SDK that ships native retry primitives. Wire them at construction; do not loop above them.

| SDK | Native retry mechanism | Configured at |
| --- | --- | --- |
| boto3 / botocore | `Config(retries={"max_attempts": N, "mode": "standard"})` | `boto3.client(...)` construction |
| `slack_sdk` (`AsyncWebClient`) | `AsyncConnectionErrorRetryHandler`, `AsyncRateLimitErrorRetryHandler`, `AsyncServerErrorRetryHandler` | `AsyncWebClient(retry_handlers=[...])` construction |
| `google-api-python-client` (Admin SDK, Drive, Calendar, Gmail) | `HttpRequest.execute(num_retries=N)` — retries 429 and 5xx with jittered exponential backoff | Per-call (passed by the client's executor) |
| `google-api-core` (`google-cloud-*` libraries) | `retry=Retry(...)` keyword on each method | Per-call |
| Microsoft Graph (`msgraph-sdk` / kiota) | `RetryHandlerOption(max_retry=N, max_delay=..., should_retry=...)` middleware | `GraphServiceClient` construction |

Where an SDK exposes its retry mechanism at construction (boto3, slack_sdk, kiota), it is wired at construction in the client module and inherited by every call through that client. Where it is exposed per-call (googleapiclient, google-api-core), the client's executor passes the configured value through each `execute()` invocation. In every case, the application's own code contains **no `for attempt in range()`, no `time.sleep`, and no equivalent**.

#### Shape B — HTTP clients without native retry (Slack `slack_sdk`, `httpx`, raw `requests`)

The vendor client wraps the call in a Tenacity decorator configured against the standard policy parameters:

```python
from tenacity import (
    retry, stop_after_attempt, stop_after_delay,
    wait_exponential_jitter, retry_if_exception_type,
)

@retry(
    stop=(stop_after_attempt(3) | stop_after_delay(60)),
    wait=wait_exponential_jitter(initial=1, max=30),
    retry=retry_if_exception_type((TransportError, RateLimitedError)),
    reraise=True,
)
async def post_message(self, ...): ...
```

The decorated method handles retries inline. The adapter calling `client.post_message(...)` sees the post-retry outcome only.

#### Shape C — Async HTTP via `httpx.AsyncClient` transport hooks

For purely-async HTTP clients, the retry is implemented either as a Tenacity decorator (Shape B) or as a transport-level hook on `httpx.AsyncClient`'s `Retry`-like configuration. The chosen primitive is documented per client; both compose with the same policy parameters.

#### All shapes converge at the executor boundary

The three shapes are implementation variations of *where* retry runs (inside the SDK, inside a Tenacity decorator on a curated facade, inside a transport hook). They produce **the same `OperationResult` envelope** from the consumer's perspective: the client's executor awaits the post-retry final state, classifies the typed exception (or success), and returns. The adapter that consumes the envelope cannot tell which shape produced it — by design. The shape is a property of the client; the consumer contract is uniform. This is what lets mature SDKs (boto3, `slack_sdk`, googleapiclient — Shape A) and less mature integrations (GC Notify, Trello, Opsgenie — Shape B/C) coexist behind the same adapter contract from [client-adapter-responsibilities.md](client-adapter-responsibilities.md).

### What the adapter sees

By the contract:

- **A success** returned by the client means the call eventually succeeded, possibly after one or two retries. The adapter maps it to `OperationResult.success(...)` and continues.
- **An exception** raised by the client means retries were exhausted. The adapter maps the (final) exception to the appropriate domain status: `TRANSIENT_ERROR` if the failure was transient (the retries timed out the budget), `PERMANENT_ERROR` for non-retriable cases the SDK lets through, etc.
- **A `Retry-After` hint surviving retries** (e.g., the upstream returned 429 with `Retry-After: 120`, longer than the 30-second cap, so the call short-circuited to "give up") is preserved on the resulting `TRANSIENT_ERROR` envelope so the upstream caller can surface it. The mechanism is documented in [api-design-error-mapping.md](api-design-error-mapping.md).

The adapter does **not** call `result.is_retriable()` and re-attempt. Retry is below the adapter; the adapter's loop count is always 1.

### Composition with idempotency

Some outbound calls are inherently idempotent (GET, idempotent PUT, DELETE, conditional writes); some are not (POST, ad-hoc mutations). Retrying a non-idempotent call risks duplicate side-effects on the upstream.

Rules:

- For SDKs that provide an idempotency token (DynamoDB `ClientRequestToken`, AWS `RequestId` patterns, Stripe `Idempotency-Key`), the application sets it. The token is derived from the inbound `correlation_id` ([cross-channel-correlation.md](cross-channel-correlation.md)) so the same retried call carries the same token; the upstream deduplicates the duplicate attempt.
- For SDKs that do not provide a token, retry is permitted only when the SDK's *typed exception path* indicates the original call did not reach the server (network errors before send, TLS handshake failures). For an exception that may indicate a partial server-side processing (a read timeout after the request was sent), retry is permitted with the explicit acceptance that the upstream may register two operations; the adapter's idempotency contract on the outbound surface (e.g., posting a Slack message twice when both attempts succeed server-side) is the residual risk that documentation-and-monitoring covers.
- The application's *inbound* idempotency mechanism ([handler-idempotency.md](handler-idempotency.md)) protects against this risk at a higher layer: a duplicated outbound call inside one handler invocation is bounded; a duplicated *handler invocation* is absorbed by the dedup record. Outbound retry is therefore safer than it might first appear.

### Observability

Retry activity emits a fixed set of structured log events (formatted per [logging-observability.md](logging-observability.md), with redaction per [data-redaction-policy.md](data-redaction-policy.md)):

- `outbound_call_retry` — emitted on each retry attempt: `vendor`, `operation`, `attempt_number`, `error_type`, `error_message`, `wait_seconds`, `will_retry` (bool), plus standard correlation context.
- `outbound_call_failed` — emitted by the adapter on a final failure: `vendor`, `operation`, `attempts`, `total_duration_seconds`, `final_status` (`TRANSIENT_ERROR` | `PERMANENT_ERROR` | `UNAUTHORIZED`).
- `outbound_call_succeeded_after_retry` — emitted on success that took more than one attempt: `vendor`, `operation`, `attempts`, `total_duration_seconds`. (A success on the first attempt does not emit this; it is implicit in regular service logging.)

These events let an operator distinguish "the upstream is having a noisy hour" (frequent `outbound_call_retry` events that succeed) from "the upstream is down" (frequent `outbound_call_failed` events).

### Settings

Per-client retry overrides live in the client's settings module (`app/integrations/<vendor>/settings.py`) per [configuration-ownership.md](configuration-ownership.md). The application's standardized defaults are constants in `app/infrastructure/<retry-utility>/`; clients import and override only when justified. There is no global "outbound retry settings" provider; the policy is in code (constants), not in environment variables.

### What this record does not change

- The handler shape, the OperationResult envelope, the idempotency mechanism, the queue contract, the observability vocabulary — all remain authoritative.
- Per-vendor timeout numbers and per-vendor rate-limit overrides are vendor-specific configuration; this record fixes the policy *shape*, not the *numbers* unique to each integration.
- The introduction of a circuit breaker is explicitly deferred. The retry budget plus orchestrator-driven process replacement is the application's resilience model today.

## Consequences

**Positive:**

- One place to reason about retry per integration: the vendor client. Adapters are retry-free; handlers are retry-free. Operators read one set of parameters and one set of log events.
- SDK-native retry mechanisms (boto3 standard mode) are used as designed, not duplicated. The application gets best-of-breed cloud retry behavior without writing it.
- Transient infrastructure noise stops at the integration boundary instead of propagating into user-visible failure.
- The observability vocabulary (`outbound_call_retry`, `outbound_call_failed`, `outbound_call_succeeded_after_retry`) gives operators precise signals.

**Tradeoffs accepted:**

- One per-call time budget (60 seconds) means an outbound call can spend up to a minute retrying before returning `TRANSIENT_ERROR`. Acceptable: the inbound caller's surrounding budget bounds this; a 60-second outbound call at the bottom of a 30-second HTTP request returns `TRANSIENT_ERROR` to the inbound timeout, which is the correct outcome.
- Two implementation shapes (SDK-native vs. Tenacity) means readers of the codebase see two patterns. Acceptable: each is the canonical choice for its category, and the underlying *policy* is the same.
- The risk of duplicate side-effects when retrying a non-idempotent SDK call without an upstream idempotency token is real, accepted, and absorbed by the inbound idempotency mechanism plus operator monitoring. There is no perfect alternative short of refusing to retry in that case, which trades a real cost (more user-visible failures) for a smaller cost (rare, observable upstream duplicates).

**Risks and mitigations:**

- **A vendor's SDK changes its retriable-error catalogue.** A previously-transient error becomes permanent (or vice versa). *Mitigation:* per-client tests assert the expected error categories; SDK upgrades are reviewed.
- **A retry decorator misclassifies an exception.** Permanent errors are retried, wasting budget and delaying the failure. *Mitigation:* the catalogue is documented per client; review enforces; retry-failure logs surface unexpected `error_type` values.
- **Tenacity's behaviour changes between releases.** *Mitigation:* `tenacity >= 9.0` is pinned in `pyproject.toml`; breaking-change releases are reviewed.
- **A handler runs many outbound calls in series and the cumulative retry budget exceeds the inbound surrounding budget.** *Mitigation:* the per-call 60-second budget plus the inbound budget set the upper bound; long-fan-out work belongs in a queue-driven path ([message-queuing.md](message-queuing.md)) where the inbound caller is not waiting.

## Confirmation

Compliance is verified by:

- **Code review.** Retry decorators or SDK retry config appear in the vendor client module (`app/integrations/<vendor>/` or `app/infrastructure/clients/<vendor>/`), not in `app/infrastructure/<service>/` adapters and not in `app/packages/<feature>/` handlers. **No retry-on-retry stacking of any kind**: an adapter does not wrap a retry-configured SDK client method in a Tenacity decorator or a hand-rolled loop; a client with SDK-native retry does not have an additional retry loop above the SDK call. Hand-rolled `for attempt in range(): try: ... except: time.sleep(...)` patterns are forbidden under this record — they duplicate SDK behaviour less correctly (typically without jitter, with blocking sleep that stalls async event loops, and with mis-classified exhaustion) and silently nest on top of native retry.
- **Static analysis.** A check forbids `tenacity` imports outside `app/integrations/` (and the small shared retry utility module). A lint rule flags `time.sleep` inside vendor client modules as a likely hand-rolled retry loop pending refactor.
- **Tests.** Per-client tests exercise both success-on-retry and exhaustion paths for the documented retriable-error set. The adapter's tests run against a client mock that returns either success or the final exception — never an intermediate retry; tests rely on the policy rather than re-asserting it at the adapter.
- **Observability checks.** Dashboards visualize `outbound_call_retry` rate per vendor; alarms fire when retries succeed but the rate climbs (signal of upstream degradation) or when `outbound_call_failed` rate climbs (signal of upstream outage).

## Source References

1. Tenacity — Documentation
   - URL: <https://tenacity.readthedocs.io/en/latest/>
   - Accessed: 2026-05-08
   - Relevance: Documents the `@retry` decorator, `stop_after_attempt`, `stop_after_delay`, `wait_exponential_jitter`, `retry_if_exception_type`, and `reraise`. Grounds the implementation shape for non-SDK clients.

2. AWS SDK for Python (boto3) — Retries
   - URL: <https://boto3.amazonaws.com/v1/documentation/api/latest/guide/retries.html>
   - Accessed: 2026-05-08
   - Relevance: Documents boto3's `Config(retries={"max_attempts": ..., "mode": "standard"})` interface, the standard mode's exponential-backoff-with-jitter behaviour, and the documented retriable error set. Grounds Shape A — boto3 clients are configured against the policy rather than wrapped.

3. AWS Architecture Blog — Exponential Backoff and Jitter
   - URL: <https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/>
   - Accessed: 2026-05-08
   - Relevance: Establishes the mathematical case for full-jitter exponential backoff over fixed-interval retries: spreading retries across N clients reduces correlated retries that would otherwise extend an outage. Grounds the choice of full-jitter over plain exponential backoff.

4. RFC 7231 — HTTP/1.1 Semantics, §6.6.4 "503 Service Unavailable" and §6.6.5 "504 Gateway Timeout"
   - URL: <https://www.rfc-editor.org/rfc/rfc7231#section-6.6>
   - Accessed: 2026-05-08
   - Relevance: Defines the semantics of 5xx responses as "the server is *currently* unable to handle the request." Grounds the rule that 5xx responses retry by default.

5. RFC 6585 — Additional HTTP Status Codes (§4 "429 Too Many Requests")
   - URL: <https://www.rfc-editor.org/rfc/rfc6585#section-4>
   - Accessed: 2026-05-08
   - Relevance: Defines 429 and the optional `Retry-After` header. Grounds the rule that 429 retries with `Retry-After` honored, capped at the 30-second wait maximum.

6. Slack — Rate Limits
   - URL: <https://api.slack.com/docs/rate-limits>
   - Accessed: 2026-05-08
   - Relevance: Documents Slack's per-method tier-based rate limits and the `Retry-After` header on 429 responses. Grounds the application of the 429 retry rule to Slack-specific calls.

7. AWS Builders' Library — Timeouts, Retries, and Backoff with Jitter
   - URL: <https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/>
   - Accessed: 2026-05-08
   - Relevance: Argues for bounded retries, per-call timeouts independent of retry budgets, and jittered exponential backoff as the production-grade combination. Grounds the per-attempt timeout, the total time budget, and the rule that retries do not run unbounded.

## Change Log

- 2026-05-08: Created. Establishes a single retry policy applied at the vendor-client layer: max 3 attempts, exponential backoff with full jitter (1 s base, 30 s max), 60-second total per-call budget, 10-second default per-attempt timeout. Defines the retriable-error catalogue (network errors, HTTP 5xx, HTTP 429 with `Retry-After` honored, SDK-typed transient exceptions) and the non-retriable catalogue (4xx other than 429, `PERMANENT_ERROR`/`UNAUTHORIZED`/`NOT_FOUND` SDK shapes, application bugs). Specifies two implementation shapes — SDK-native retry configured against the policy (boto3 standard mode), and Tenacity-decorated methods for HTTP clients without native retry. Names the observability event vocabulary (`outbound_call_retry`, `outbound_call_failed`, `outbound_call_succeeded_after_retry`). Defers circuit-breaker semantics to a future record. Composes with handler-idempotency.md (the inbound dedup mechanism absorbs the residual duplicate-side-effect risk of retrying non-idempotent calls without upstream idempotency tokens).
- 2026-05-12: Strengthened Shape A from "do not wrap boto3 in Tenacity" to "do not wrap any SDK with native retry in any retry loop, including hand-rolled ones." Background: an SDK-capability audit (research-shield-pattern-sdk-capabilities.md) found that the existing Google Workspace and AWS executors hand-roll `for attempt in range(): try: ... except: time.sleep(...)` loops above SDKs that already retry natively — producing nested attempts (worst case 3 × 3 = 9 uncoordinated tries on a single transient failure), correlated retry storms (no jitter on the hand-rolled backoff), blocking sleep that would stall async event loops, and mis-classified exhausted-transient outcomes. The original Shape A wording explicitly forbade Tenacity wrapping but did not foreclose hand-rolled loops; the closure had been read more narrowly than intended. Added an explicit SDK retry mechanism table (boto3 / slack_sdk / googleapiclient / google-api-core / Microsoft Graph kiota) naming where each SDK's retry is configured. Confirmation section updated to explicitly forbid retry-on-retry stacking of any kind and flag `time.sleep` inside vendor client modules as a likely hand-rolled loop pending refactor. No change to retry parameters (max 3, exponential with full jitter, 1s base, 30s max, 60s budget, 10s per-attempt timeout), the retriable/non-retriable catalogue, or the observability vocabulary.
- 2026-05-12: Updated all `app/integrations/` path references that were incorrectly written as `app/clients/`.
