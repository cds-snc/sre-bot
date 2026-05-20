---
title: "Slack Transport — Delivery Mode"
status: Draft
type: Standard
tier: Tier-3
governance_domain: [application]
concerns: [architecture, api]
constrained_by: [cross-channel-correlation.md, application-lifecycle.md, configuration-ownership.md]
date: 2026-05-13
decision_makers:
  - SRE Team
---

# Slack Transport — Delivery Mode

## Context and Problem Statement

Slack offers two mutually exclusive delivery modes for inbound events:

- **Socket Mode** — the application opens an outbound persistent WebSocket using an app-level token (`xapp-`). Slack pushes events to the application over this connection. Slack does not need to know the application's URL.
- **HTTP Events API** — Slack POSTs inbound events to a public URL the application exposes. Each POST must be verified against a signing secret using Slack's HMAC-SHA256 scheme. Slack must be configured with a deployment-specific public URL.

The choice affects deployment topology (public URL requirement), per-event security posture (signing-secret verification), and operational maintenance cost (per-environment Slack app URL configuration).

**Constraints:**

- The application's FastAPI surface already exposes public endpoints for other features. The delivery mode decision is about whether the **Slack channel specifically** requires a known public URL — not about whether the application has any public surface at all.
- The mode must be switchable via settings without code changes, to support environments that prefer HTTP Events.
- Both modes must share the same inbound-adapter phase: event verification (HTTP Events only) → correlation context binding → pluggy hookspec dispatch.

## Considered Options

1. **Socket Mode default, HTTP Events supported via settings flag (chosen).** The application initiates the WebSocket outbound using the app-level token. No per-deployment Slack URL configuration, no per-environment Slack app URL maintenance, identical behaviour across local development, staging, and production.
2. **HTTP Events default.** Requires Slack to be configured with a deployment-specific public URL per environment. Adds per-event signing-secret verification overhead. Preferred by some operators who want synchronous request-response at the Slack boundary.
3. **Socket Mode only, HTTP Events unsupported.** Simpler; rejected because it blocks deployments that prefer or require HTTP Events (e.g., environments with a stable, operationally convenient public URL).

## Decision Outcome

**Chosen: Option 1 — Socket Mode default, HTTP Events supported.**

The application sets `socket_mode=true` by default. `socket_mode=false` selects HTTP Events mode. Both modes are fully supported; the default is chosen for operational convenience, not capability.

### Socket Mode

`AsyncSocketModeHandler` is constructed with the `app_token` (`xapp-`) and started during the application lifespan's transport phase. Slack delivers events to the application over the pre-authenticated WebSocket:

- **No per-event signing-secret verification.** The WebSocket connection itself is the authenticated channel; Slack documents this explicitly.
- **One connection per process.** Bolt's `AsyncSocketModeHandler` manages reconnection automatically, including handling Slack's pre-disconnect warning (~10 seconds). The lifecycle module monitors connection state and logs reconnect events.
- **Up to 10 concurrent connections** are supported by Slack at the workspace level. The application runs one connection per process.
- **Correlation context.** Each delivered event opens a fresh correlation context (a new `request_id`) per [cross-channel-correlation.md](cross-channel-correlation.md) before entering the pluggy hookspec dispatch.

### HTTP Events

`SlackRequestHandler` (from `slack_bolt.adapter.fastapi.async_handler`) mounts onto the application's FastAPI app at a configured path (default `/slack/events`):

- **Per-event signing-secret verification.** The inbound adapter verifies every POST against the signing secret using Slack's HMAC-SHA256 scheme before Bolt dispatch. Requests that fail verification are rejected with `401`.
- **Verification scheme.** Signature is `v0=HMAC-SHA256(signing_secret, "v0:{timestamp}:{raw_body}")`. The `X-Slack-Request-Timestamp` header is checked against a 5-minute window to prevent replay attacks. ([Slack verification docs](https://docs.slack.dev/authentication/verifying-requests-from-slack))
- **Correlation context.** Identical to Socket Mode — each verified POST opens a fresh correlation context before dispatch.

### Shared inbound-adapter phase

Regardless of delivery mode, the inbound path is:

```
[event arrives] → verification (HTTP only) → correlation context open
               → Bolt middleware pipeline → hookspec dispatch
               → listener handler
```

The hookspec dispatch and all downstream handler code are identical in both modes. Switching modes via `socket_mode` is a configuration change with no handler-code impact.

### Settings

Both modes are gated by `SlackSettings` in `app/infrastructure/slack/settings.py`:

| Field | Purpose |
| --- | --- |
| `enabled` (bool, default `false`) | Gates the entire Slack platform. |
| `socket_mode` (bool, default `true`) | `true` → Socket Mode; `false` → HTTP Events. |
| `app_token` (`xapp-…`) | Required for Socket Mode only. |
| `signing_secret` (hex string) | Required for HTTP Events only. |

Missing required values when `enabled=true` cause fail-fast at the configuration phase per [configuration-ownership.md](configuration-ownership.md).

## Consequences

**Positive:**

- Socket Mode default removes the public URL requirement for Slack specifically. The same codebase runs in local development, CI, and production without any Slack app URL configuration.
- Switching delivery modes is a settings change, not a code change. No handler code is aware of which mode is active.
- HTTP Events mode is available for operators who prefer synchronous request-response at the Slack boundary or who already have a stable public URL.

**Tradeoffs accepted:**

- Socket Mode's pre-authenticated WebSocket means no per-event signing-secret verification. This is intentional; the WebSocket connection is the trust boundary.
- Socket Mode adds a persistent outbound connection to the application's operational profile. Connection drops are handled by Bolt's reconnect logic.

**Risks:**

- Socket Mode connection drops if Slack's pre-disconnect warning is not handled in time. Mitigation: Bolt's `AsyncSocketModeHandler` handles reconnect by default; the lifecycle module logs reconnect events for observability.
- HTTP Events mode requires the public URL to be stable — a URL change requires updating the Slack app configuration. Mitigation: this is an operational concern, not a code concern; environments that cannot maintain a stable URL should use Socket Mode.

## Confirmation

- `SlackSettings` defines `socket_mode`, `app_token`, and `signing_secret`. Missing `app_token` when `socket_mode=true` and `enabled=true` causes fail-fast. Missing `signing_secret` when `socket_mode=false` and `enabled=true` causes fail-fast.
- Boot test asserts that `AsyncSocketModeHandler` is started in Socket Mode and absent in HTTP Events mode, and vice versa for `SlackRequestHandler`.
- Integration test asserts that an HTTP Events inbound POST with an invalid signature returns `401`.
- Both modes produce an identical handler invocation — same parameters, same `BoltContext` fields.

## Source References

1. Slack — Comparing HTTP Events API and Socket Mode
   - URL: <https://docs.slack.dev/apis/events-api/comparing-http-socket-mode>
   - Accessed: 2026-05-08
   - Relevance: Canonical comparison of the two modes; documents that Socket Mode "allows your app to use the Events API without exposing a public HTTP Request URL."

2. Slack — Using Socket Mode
   - URL: <https://docs.slack.dev/apis/events-api/using-socket-mode>
   - Accessed: 2026-05-08
   - Relevance: `xapp-` token, `apps.connections.open`, up-to-10-concurrent-connections, and the "no need to verify or validate inbound events" guarantee on a pre-authenticated WebSocket.

3. Slack — Verifying Requests from Slack
   - URL: <https://docs.slack.dev/authentication/verifying-requests-from-slack>
   - Accessed: 2026-05-08
   - Relevance: HMAC-SHA256 signing-secret verification scheme for HTTP Events mode; `X-Slack-Request-Timestamp` header; 5-minute replay-protection window.

## Change Log

- 2026-05-13: Created by splitting delivery-mode content out of [transport-slack.md](transport-slack.md). Decision unchanged; record is a focused extraction.
