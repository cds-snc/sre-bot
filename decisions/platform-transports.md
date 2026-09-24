---
status: Accepted
date: 2026-07-06
applies: target
scope: How a chat platform (Slack, Teams, …) composes into the host.
---

# Platform Transports

## Context

The app accepts work from HTTP and from chat platforms. Platforms are heterogeneous (Slack: commands, events and actions with a 3-second ack; Teams: activities and invokes; HTTP: routes). A unified `Platform` Protocol would be lossy or bloated, and we reject it. But each platform should follow the same composition shape, so the second platform doesn't reinvent the plumbing.

Only Slack exists today. This pattern is extracted from one platform, so it is a default, not a validated standard. Building Teams is expected to amend it; treat divergence as information, not violation.

Current state: the Slack runtime (`SlackPlatformProvider`, `bootstrap.py`), parser, formatter and help all live in `app/integrations/slack/`. `app/infrastructure/slack/` holds only `settings.py`. `app/server/` has no platform subpackage.

## Decision

A platform is split across layers by what each part is ([plugin-architecture.md](plugin-architecture.md)):

| Part | Home |
| --- | --- |
| **Runtime:** SDK runtime (Bolt app, Socket Mode; later the Teams SDK), connection lifecycle, inbound verification, correlation binding, dispatch to registered handlers | `app/server/<platform>/` (host code) |
| **Handler contract:** registration hookspecs, typed inbound request and reply models, the registrar Protocol features use, the outbound messaging Protocol | `app/contracts/` |
| **Helpers:** parser, formatter, help rendering, the `OperationResult` → platform-message renderer | `app/server/<platform>/`, reached by handlers only through the handler contract |
| **Web API client** and its error classification | `app/integrations/<platform>/` |

Rules:
1. **The runtime is host code.** It is built during lifespan composition, started at the transport phase and closed at shutdown. Features never touch connections or SDK runtime objects.
2. **Verification attaches once, in the runtime,** never per handler.
3. **Hookspecs fire once, at startup, to register handlers.** Per-event routing is the SDK's job.
4. **Handlers render, never build.** A handler calls one service method, gets `OperationResult`, and renders it through the shared renderer.
5. **Outbound calls classify failures.** Calls through the outbound Protocol use SDK-native retry and map failures to `OperationResult` ([outbound-clients.md](outbound-clients.md) rules apply at that Protocol boundary).
6. **No shared abstraction across platforms.** A feature serving two platforms writes two thin handlers over one service, which returns `OperationResult` and doesn't know who asked. A platform-neutral command model was tried and failed on rich dialogs and on concepts the platforms don't share.
7. **No helper wraps the platform SDK.** Shared handler helpers add conventions on top of the SDK's documented calls; they never mirror, re-expose or patch its surface, and never re-implement what it already does ([outbound-clients.md](outbound-clients.md)). Whether each platform gets a standard interaction toolkit is open: [interaction-toolkits.md](interaction-toolkits.md) (Draft).

HTTP is not a platform transport. It is the app's own protocol; its inbound boundary is FastAPI and ASGI middleware in `app/server/`.

### Outbound messages are intents

A feature says what to tell whom (a platform-neutral message intent); each platform renders it natively. A person is reached on the platform they use, resolved by the people capability ([people-and-accounts.md](people-and-accounts.md)). Bridging live conversations between Slack and Teams is out of scope.

### A platform is also a driven dependency

A platform's role is decided by **direction × purpose**, never by the vendor's identity. One technology can sit behind a driving port and a driven port at once. Slack occupies up to three positions:

1. **Inbound transport** (driving): Slack drives the app. The Bolt runtime in `server/<platform>/` is the only Slack object with a lifecycle.
2. **Reply surface** (driven, host-owned): an inbound handler replies (`chat.postMessage`, `views.open`) through the outbound messaging Protocol, backed by a **bot-scoped** Web API client.
3. **Managed system of record** (driven, feature-owned): a feature's purpose is to act on the platform, triggered from elsewhere (e.g. changing Slack usergroup memberships for Backstage). This is an ordinary Path B dependency: a purpose-shaped port (`GroupMembershipWriter`, not the messaging Protocol) with an adapter in the feature's `adapters/`, using an **admin-scoped** Web API client.

Roles 2 and 3 share the Web API client built in `integrations/<platform>/`, but not a port, and they use different least-privilege credentials: the bot token must not carry `usergroups:write` or admin scopes (OWASP API5:2023). The runtime (role 1) is shared by neither.

## Consequences

- A new platform = one `server/<platform>/` runtime, its handler contract in `contracts/`, one decision record, and feature handlers.
- Per-platform handler duplication in features is accepted; platform fidelity (ack deadlines, invoke shapes) survives.
- Until Teams exists, this record is falsifiable only against Slack; it is re-reviewed when the second platform lands.

## Checks

- Each platform's runtime lives only under `app/server/<platform>/`; its Web API client and error classification live in `app/integrations/<platform>/`.
- grep finds no `Platform` Protocol unifying transports.
- Verification code exists only in `app/server/<platform>/`, never in features or capabilities.
- import-linter (see [plugin-architecture.md](plugin-architecture.md)): features never import `server/`; a feature acting on a platform as a target imports the platform's `integrations/` client only from `adapters/`.

## Migration

Tickets: TASK-26 (Slack home consolidation), TASK-33 (async Bolt), TASK-42 and TASK-43 (Teams).

Tolerated until then:
- the Slack runtime, parser, formatter and help in `integrations/slack/`;
- the `register_slack_listeners(app: AsyncApp)` hookspec in `infrastructure/plugins/specs.py`, which hands features the Bolt app;
- handler hookspecs in `infrastructure/plugins/` instead of `contracts/`.

**Changes:**
- 2026-09-24: runtime moves to `server/<platform>/` and the handler contract to `contracts/`, per plugin-architecture.md; no helper wraps the platform SDK, and interaction toolkits are an open Draft.
