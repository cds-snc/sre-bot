---
status: Accepted
date: 2026-07-06
applies: target
scope: How a chat platform (Slack, Teams, …) composes into the host.
---

# Platform Transports

## Context

The app accepts work from HTTP and from chat platforms. Platforms are heterogeneous (Slack: commands/events/actions with a 3-second ack; Teams: activities and invokes; HTTP: routes) — a unified `Platform` Protocol would be lossy or bloated, and we reject it. But each platform integration should follow the same *composition shape* so the second platform doesn't reinvent the plumbing.

Honesty note: only Slack exists today. This pattern is extracted from n=1 and is a **default, not a validated standard**; building Teams is expected to amend it, and the Teams work should treat divergence as information, not violation.

## Decision

A platform transport is **one infrastructure service** at `app/infrastructure/<platform>/` that owns, in full:

1. **Runtime & lifecycle** — the platform SDK runtime (Bolt app, Bot Framework adapter), constructed at the lifespan's composition phase, started at the transport phase, closed at shutdown. Features never touch connections.
2. **Inbound boundary** — verification (signatures, JWT), correlation binding, and dispatch of inbound payloads to feature handlers registered at startup. Verification attaches once here, never per-handler.
3. **Outbound Protocol** — a platform-shaped Protocol (`SlackService`, `TeamsService`) naming the operations features use against the platform. Outbound calls made through it apply SDK-native retry and classify failures into `OperationResult` ([outbound-clients.md](outbound-clients.md) rules apply *at this Protocol boundary*, not as a separate wrapper layer — the transport is in-process, first-class functionality, not a boundary SDK).
4. **Helpers** — parsing, formatting, help rendering, and the `OperationResult` → platform-message renderer. Handlers call the renderer; they never build platform response shapes inline.
5. **Registration hookspecs** — platform-shaped hookspecs (see [plugins.md](plugins.md)) that features implement to attach handlers at startup. Hookspecs fire **once at startup to register handlers**; per-event routing is the SDK's job. (The old corpus described per-event hookspec dispatch; that was wrong.)

The transport *runtime* is not mirrored in `integrations/` (the Bolt/Socket Mode inbound machinery is transport-only); the platform's Web API *client* does live in `integrations/<platform>/` (see below). There is no shared abstraction across platforms: a feature that serves two platforms writes two thin handlers; the shared logic lives in its service layer, which returns `OperationResult` and doesn't know who asked.

HTTP is not a platform transport — it is the app's own protocol; its inbound boundary is FastAPI + ASGI middleware in `app/server/`.

### A platform is also a driven dependency

A platform's role is decided by **direction × purpose**, not by its identity (hexagonal: one technology can sit behind a *driving* port and a *driven* port at once). Slack occupies up to three positions:

1. **Inbound transport** (driving) — Slack drives the app. The Bolt/Socket Mode **runtime** lives in `infrastructure/<platform>/` and is the only Slack object with a lifespan (opens/closes the connection).
2. **Reply surface** (driven, transport-owned) — an inbound handler replies (`chat.postMessage`, `views.open`). The `SlackService` Protocol, backed by a **bot-scoped** Web API client.
3. **Managed system-of-record** (driven, feature-owned) — a feature's *purpose* is to act on the platform, triggered from elsewhere (e.g. an HTTP feature changing Slack usergroup memberships for Backstage). This is an ordinary Path B outbound dependency: a domain-shaped port (`GroupMembershipWriter`, *not* `SlackService`) with a feature adapter, using an **admin-scoped** Web API client. If the port is vendor-neutral ("group membership", Slack as one backend) it's Path A instead.

**What's shared vs. separate.** Roles 2 and 3 share the authenticated **Web API client** — a plain, no-lifecycle `AsyncWebClient` built by `integrations/<platform>/` and consumed downward by both. They do **not** share a port, and they use **different, least-privilege credentials** (different attached resources per 12-factor IV; segregated per OWASP API5:2023 BFLA — the inbound bot token must not carry `usergroups:write`/admin scopes). The inbound runtime (role 1) is transport-only and shared by neither. So: runtime → `infrastructure/<platform>/`; Web API client + error classification → `integrations/<platform>/`; each outbound port → shaped by its purpose, wherever its consumer lives.

## Consequences

- A new platform = one new infrastructure service + one decision record + feature handlers. The pattern names the slots; the platform fills them natively.
- Per-platform handler duplication in features is accepted; platform fidelity (ack deadlines, invoke shapes) survives.
- Until Teams exists, this record is falsifiable only against Slack; it stays `target` and gets re-reviewed when platform #2 lands.

## Checks

- Each platform's inbound runtime lives in exactly one `app/infrastructure/<platform>/`; its Web API client + error classification live in `app/integrations/<platform>/`.
- grep finds no `Platform` Protocol attempting to unify transports.
- Verification code exists only in transport services, never in `app/packages/`.
- A feature acting on a platform as a target imports the platform's `integrations/` Web client (in an `adapters/` file), never `infrastructure/<platform>/`.

## Migration

Ticket: Slack home consolidation — inbound runtime/dispatch/helpers to `infrastructure/slack/`; the authenticated Web API client + `classify_slack_error` to `integrations/slack/`; shim for legacy imports. Tolerated until then: Slack content mixed under `integrations/slack/`.
