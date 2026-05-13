---
title: "Slack Transport — Shield Implementation"
status: Draft
type: Standard
tier: Tier-3
governance_domain: [application]
concerns: [architecture, api]
constrained_by: [transport-slack.md, client-sdk-shield-pattern.md, outbound-retry-policy.md, operation-result-pattern.md, configuration-ownership.md]
date: 2026-05-13
decision_makers:
  - SRE Team
---

# Slack Transport — Shield Implementation

## Context and Problem Statement

[client-sdk-shield-pattern.md](client-sdk-shield-pattern.md) defines the cross-cutting shield pattern and its three call-site shapes (α awaitable executor, β per-invocation callable, γ sync thunk). This record pins the **Slack-specific implementation** of that pattern:

- How `SlackShield` is constructed and which SDK-native retry handlers are wired in.
- How the Bolt listener-injected callables (`say`, `respond`, `client`) are replaced with shielded equivalents before handlers run.
- The two error-classification tables (Web API path and webhook path) that are the single source of truth for Slack exception → `OperationResult.status` mapping.
- The escape hatch for Slack Web API methods not yet on the `SlackService` Protocol surface.

This record does not redefine the shield pattern itself — see [client-sdk-shield-pattern.md](client-sdk-shield-pattern.md) for that.

**Constraints:**

- `SlackShield` lives in `app/integrations/slack/` per [client-module-placement.md](client-module-placement.md).
- No project-local retry loop wraps Slack calls — retry is configured on `AsyncWebClient` using Slack SDK-native handlers per [outbound-retry-policy.md](outbound-retry-policy.md) Shape A.
- All Slack outbound wire calls return `OperationResult` — no `SlackApiError` or `asyncio.TimeoutError` propagates above the shield boundary.

## Decision Outcome

### `SlackShield` construction

`SlackShield` wraps a pre-configured `AsyncWebClient`. Three SDK-native retry handlers are wired at construction time:

| Handler | Purpose |
| --- | --- |
| `AsyncConnectionErrorRetryHandler` | Transport-level connection failures (DNS, TLS, socket reset). |
| `AsyncRateLimitErrorRetryHandler` | `ratelimited` responses, honoring `Retry-After` up to the 30-second cap from [outbound-retry-policy.md](outbound-retry-policy.md). |
| `AsyncServerErrorRetryHandler` | HTTP 5xx responses with jittered exponential backoff. Not in `AsyncWebClient`'s defaults; added explicitly for Shape A parity. |

The shield exposes:
- `shield.web` — the pre-configured `AsyncWebClient` (shape α handle)
- `shield.execute(aw)` — awaitable-wrapping executor: applies per-call wall-clock budget via `asyncio.wait_for`, catches `SlackApiError` and `asyncio.TimeoutError`, classifies into `OperationResult`
- `shield.execute_say(say, **kwargs)` — shape β entry point for `say`; delegates to `execute(say(...))` since `AsyncSay.__call__` produces a `chat_postMessage` coroutine
- `shield.execute_respond(respond, **kwargs)` — shape β entry point for `respond`; uses webhook-aware classification (HTTP status, not `SlackApiError`)

Both classification tables live in `app/integrations/slack/shield.py` and are the single source of truth for Slack exception → status mapping.

### Error classification — Web API path

Applies to: all `AsyncWebClient` calls (`shield.execute(...)`) and `say` (`shield.execute_say(...)`).

| `SlackApiError.response.data["error"]` | `OperationResult.status` |
| --- | --- |
| `channel_not_found`, `user_not_found`, `message_not_found`, `view_not_found` | `NOT_FOUND` |
| `not_authed`, `invalid_auth`, `account_inactive`, `token_revoked`, `token_expired`, `missing_scope` | `UNAUTHORIZED` |
| `ratelimited` (post-retry exhaustion) | `TRANSIENT_ERROR` with `retry_after` from `RateLimitedError` |
| `fatal_error`, `internal_error`, `service_unavailable` (post-retry exhaustion) | `TRANSIENT_ERROR` |
| Any other Slack error code | `PERMANENT_ERROR` with the Slack code in `error_code` |
| `asyncio.TimeoutError` (per-call budget exceeded) | `TRANSIENT_ERROR` |
| Any other exception | `PERMANENT_ERROR` |

New error codes are added to this table in the same PR that introduces the call site that surfaces them.

### Error classification — Webhook path

Applies to: `respond` (`shield.execute_respond(...)`), which POSTs to `response_url` via `AsyncWebhookClient`. This transport does not raise `SlackApiError`; classification is HTTP-status-based.

| Condition | `OperationResult.status` |
| --- | --- |
| HTTP 200 | `SUCCESS` |
| HTTP 404 (invalid or expired `response_url`) | `PERMANENT_ERROR` |
| HTTP 429 | `TRANSIENT_ERROR` with `retry_after` from `Retry-After` header |
| HTTP 5xx | `TRANSIENT_ERROR` |
| `asyncio.TimeoutError` | `TRANSIENT_ERROR` |
| `ValueError` (missing `response_url`, wrong `text` type) | `PERMANENT_ERROR` |
| Any other exception | `PERMANENT_ERROR` |

`response_url` is valid for 30 minutes and accepts at most 5 responses per interaction. This multi-call quota is not enforceable per-call by the shield; adapters calling `respond` more than once per interaction are responsible for tracking the quota. ([Slack docs: Handling User Interaction](https://docs.slack.dev/interactivity/handling-user-interaction))

### `shield_listener_callables` middleware

Bolt injects `say`, `respond`, and `client` into listeners using raw, un-shielded callables. These bypass the shield entirely if used unmodified. A Bolt middleware registered at app startup replaces each with a shielded equivalent before any handler runs.

**Mechanism.** `BoltContext` is a plain `dict` subclass ([`base_context.py`](https://github.com/slackapi/bolt-python/blob/main/slack_bolt/context/base_context.py)). Property getters for `say`, `respond`, and `client` check `if "key" not in self` before constructing the default ([`async_context.py` lines 95-114](https://github.com/slackapi/bolt-python/blob/main/slack_bolt/context/async_context.py)). Middleware that writes `context["say"]` before the property fires causes `async_utils.py` line 52 (`request.context.say`) to return the stored shielded value.

```python
# app/infrastructure/slack/middleware.py

async def shield_listener_callables(
    context: BoltContext, next: Callable
) -> None:
    context["say"] = ShieldedSay(          # chat_postMessage; implicit channel from context
        shield, channel=context.channel_id, thread_ts=context.thread_ts
    )
    context["respond"] = ShieldedRespond(  # response_url POST; implicit URL from context
        shield, response_url=context.response_url
    )
    context["client"] = slack_service      # SlackService replaces raw AsyncWebClient
    await next()
```

`ShieldedSay` and `ShieldedRespond` preserve Bolt's native call signatures:
- `ShieldedSay.__call__(text, blocks, thread_ts, ...)` — routes through `shield.execute_say(...)`, returns `OperationResult`
- `ShieldedRespond.__call__(text, replace_original, ...)` — routes through `shield.execute_respond(...)`, returns `OperationResult`

`ack` is **not replaced** — it is a framework-managed in-process signal with no network failure surface. Shielding it would risk silently absorbing Slack's 3-second listener deadline.

### Workflow Step and AI/Assistant callables

Bolt also injects `complete`, `fail`, `set_status`, `set_title`, `set_suggested_prompts`, `get_thread_context`, and `save_thread_context` for Workflow Step and AI/Assistant listeners. These bypass the shield if used unmodified. They follow the same `shield_listener_callables` middleware override pattern. They are not currently in scope; they must be added to `shield_listener_callables` before any Workflow Step or AI/Assistant listener is introduced.

### Escape hatch

For Slack Web API methods not yet on the `SlackService` Protocol surface, adapter code may call through the shield directly as an interim step:

```python
result = await shield.execute(
    shield.web.users_identity()
)
```

This is an escape hatch, not the default path. The method should be promoted to a `SlackService` Protocol method in the next PR.

## Consequences

**Positive:**

- Handlers call `await say(text=...)`, `await respond(text=...)`, `await client.views_open(...)` — native Bolt syntax. The shield is invisible at call sites.
- All three Slack outbound transports (Web API, `say`, `respond`) produce `OperationResult` through one mechanism. Handlers never handle `SlackApiError`.
- One classification table per transport in one file. New error codes are added once and immediately apply everywhere.

**Tradeoffs accepted:**

- `shield_listener_callables` must be updated when Workflow Step or AI/Assistant callables are adopted. Until updated, those callables bypass the shield.
- The escape hatch (`shield.execute(shield.web.<method>(...))`) is available but is a code-smell in handler files. Promote to Protocol methods promptly.

**Risks:**

- A handler uses a Bolt-injected callable before `shield_listener_callables` replaces it (e.g., a `complete` call for a Workflow Step). Mitigation: `shield_listener_callables` is the single registration point; the Confirmation test suite asserts it covers all callables in use.
- Misclassification in the executor (a 429 mapped to `PERMANENT_ERROR`). Mitigation: per-shield executor tests cover each error code in both tables against its expected status; new codes are added with the change that introduces the call.

## Confirmation

- `app/integrations/slack/shield.py` contains both classification tables, the `SlackShield` class with three retry handlers, `ShieldedSay`, and `ShieldedRespond`.
- `app/infrastructure/slack/middleware.py` contains `shield_listener_callables`; it is registered before all feature listeners.
- Shield executor tests cover each row in both classification tables. Timeout enforcement is verified against the budget from [outbound-retry-policy.md](outbound-retry-policy.md).
- Middleware tests assert that after `shield_listener_callables` runs, `context["say"]` is a `ShieldedSay`, `context["respond"]` is a `ShieldedRespond`, and `context["client"]` is a `SlackService`.

## Source References

1. Slack Python SDK — `RetryHandler` / `RateLimitErrorRetryHandler`
   - URL: <https://docs.slack.dev/tools/python-slack-sdk/web/#retryhandler>
   - Accessed: 2026-05-12
   - Relevance: SDK-native retry primitives composed into `AsyncWebClient` at construction. Grounds Shape A — no project-local retry loop.

2. Slack Web API — Rate Limits
   - URL: <https://docs.slack.dev/apis/web-api/rate-limits/>
   - Accessed: 2026-05-08
   - Relevance: 429 with `Retry-After`; 30-second cap; `response_url` shares the per-channel quota.

3. Slack — Handling User Interaction
   - URL: <https://docs.slack.dev/interactivity/handling-user-interaction>
   - Accessed: 2026-05-08
   - Relevance: `response_url` 5-call / 30-minute quota; grounds the multi-call quota note.

4. Slack — Bolt for Python: Listener context source
   - URL: <https://github.com/slackapi/bolt-python/tree/main/slack_bolt/context>
   - Accessed: 2026-05-13
   - Relevance: `BoltContext` is a `dict` subclass; property getters check `if "key" not in self`; middleware override mechanism verified against `async_context.py` lines 95-114 and `async_utils.py` line 52.

5. Slack — Bolt for Python: Listener arguments
   - URL: <https://docs.slack.dev/tools/bolt-python/concepts/listener-arguments/>
   - Accessed: 2026-05-13
   - Relevance: Canonical list of all Bolt-injected parameters; identifies which bypass the shield and require `shield_listener_callables` treatment.

## Change Log

- 2026-05-13: Created by splitting shield-implementation content out of [transport-slack.md](transport-slack.md). Covers `SlackShield` construction, `shield_listener_callables` middleware, both classification tables, and the escape hatch. The cross-cutting shield pattern remains in [client-sdk-shield-pattern.md](client-sdk-shield-pattern.md).
