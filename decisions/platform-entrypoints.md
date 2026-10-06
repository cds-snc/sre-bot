---
status: Accepted
date: 2026-09-25
applies: target
scope: Where chat-platform entry points, handler contracts and outbound platform messaging live, split by direction the way HTTP already is.
---

# Platform Entry Points

## Context

[plugin-architecture.md](plugin-architecture.md) puts transport runtimes in the host (`app/server/`) and the public plugin API in `app/contracts/`. HTTP already works this way: its inbound boundary is in `app/server/`. [people-and-accounts.md](people-and-accounts.md) needs every inbound caller resolved to a person, and only the host may call a capability on a caller's behalf before a feature runs.

Ports and adapters separates the two directions:
- Cockburn distinguishes primary (driving) adapters from secondary (driven) ones ([Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/)).
- Cosmic Python keeps `entrypoints/` (the Flask app, event consumers) apart from `adapters/` ([project structure](https://github.com/cosmicpython/book/blob/master/appendix_project_structure.asciidoc)).

A primary adapter speaks its device's own technology. Netflix Dispatch's Slack plugin handles modals with Bolt's `ack`, `body` and `client` and calls a platform-free incident service ([interactive.py](https://github.com/Netflix/dispatch/blob/main/src/dispatch/plugins/dispatch_slack/incident/interactive.py), archived 2025). Normalized multi-platform models stop at rich interactions: Chat SDK supports modals on Slack and Teams only, marks some components Slack-only and hands submits a `raw` platform payload ([modals](https://chat-sdk.dev/docs/modals), read 2026-10-06). A platform-neutral command model was tried here and failed on rich dialogs ([interaction-toolkits.md](interaction-toolkits.md)).

Current state:

- The Slack runtime lives in `integrations/slack/` (`provider.py::SlackPlatformProvider`, `bootstrap.py`), started from `server/lifespan.py`. `infrastructure/slack/` holds only `settings.py`.
- Feature handlers import Slack models and the argument parser from `integrations.slack`.
- Features register Slack commands through the `SlackCommandRegistrar` Protocol (`contracts/slack/registrar.py`); no hookspec hands out the Bolt app. Packages cannot register block actions or view submissions; legacy modules call `bot.action` and `bot.view` on the app.
- Teams is not built (TASK-42, TASK-43).

## Decision

**A chat platform is split by direction, not bundled into one service.**

| Part | Home |
| --- | --- |
| **Entry point:** SDK runtime and connection lifecycle, inbound verification, dispatch to registered handlers, in-request replies for commands (ack, respond, open a view) | `app/server/<platform>/`, beside HTTP |
| **Handler contract:** the command request and response models, the in-request reply Protocol, the registrar Protocol features use (commands, block actions, view submissions), registration hookspecs | `app/contracts/`, with no runtime and no I/O |
| **Messaging people or channels outside a request** (notify someone, post to an incident channel) | A capability ([plugin-architecture.md](plugin-architecture.md)) with one adapter per platform, or a feature's Path B adapter |
| **Authenticated Web API client** and `classify_<platform>_error` | `app/integrations/<platform>/` (unchanged) |

Rules:

1. **Callers are resolved at the entry point.** The entry point resolves the caller's platform account through the people capability, then passes handlers the resolved person, or an unlinked marker, with the request (for a native listener, in the SDK's request context, Bolt's `context`). An unlinked caller isn't refused here; the feature's access policy decides (TASK-129). `app/server/` may import capabilities because it is the composition root. Handlers and services don't resolve callers themselves.
2. **The host owns registration.** Registration hookspecs take the platform's registrar Protocol from the handler contract, never the Bolt `App` or a Bot Framework adapter. Registration happens at startup and each id is registered once.
3. **Business code is platform-neutral; a platform entry point speaks its platform's SDK.** Services, `core/` and `common/` import no platform SDK. A feature's `entrypoints/<platform>.py` handles its platform's interactions (block actions, modals, the acknowledgement deadline) with the SDK's listener arguments and models (for Slack, Bolt's `ack`, `body`, `client`, `respond` and `slack_sdk` models), not a host-made normalized model, parses the payload into domain values and calls the service. It never imports `app/server/`. Commands keep the contract's command model until TASK-141 decides.
4. **Platforms stay independent.** There is no unified `Platform` Protocol. A feature serving Slack and Teams writes two thin handlers over one service. A conversation is handled on the platform it started on ([people-and-accounts.md](people-and-accounts.md)).
5. **Credentials stay separated.** The entry point uses bot-scoped credentials. Admin-scoped credentials belong only to the adapters that need them ([platform-transports.md](platform-transports.md)).

## Consequences

- HTTP, Slack and Teams inbound traffic all enter through the host, so authentication and caller resolution happen once per request, in one place.
- `infrastructure/` holds no inbound runtime, which matches its hosting-only role.
- Handler code changes little: it imports the handler contract instead of `integrations.slack`.
- Cost: `app/server/` gains one subpackage per platform, and its lifecycle code must stay free of business logic.
- Cost: the registrar Protocol stands in for Bolt's registration API, so matcher options (regex ids, constraints, middleware) arrive only when a feature needs them. Handling is not wrapped: an entry point has the whole SDK.
- Cost: a feature serving Slack and Teams writes its interaction code twice, and entry points written for sync Bolt change signature with async Bolt (TASK-33). Keeping entry points thin keeps that small.
- Deciding this before TASK-26 runs means the Slack runtime moves once.

## Checks

- Review: each platform's runtime, verification and dispatch live only under `app/server/<platform>/`.
- import-linter (with TASK-18): features and capabilities never import `server`; `contracts` imports no SDK runtime (`slack_bolt`, Bot Framework).
- grep: platform hookspecs in `contracts/` reference no SDK runtime types.
- import-linter: in features and capabilities, `slack_bolt` is imported only by `entrypoints/slack.py`, and `slack_sdk` only by `entrypoints/slack.py` and `adapters/`.
- Boot test: registering one action or view id twice aborts boot.
- Review: messaging outside a request lives in a capability or a Path B adapter, never in the handler contract.

## Migration

Tickets: TASK-26 (Slack runtime to `app/server/slack/`, handler contract to `app/contracts/`), TASK-33 (async Bolt in the new home), TASK-140 (action and view-submission registration), TASK-141 (commands under rule 3), TASK-42 and TASK-43 (Teams follows this split).

Tolerated until then:
- the Slack runtime in `integrations/slack/`;
- handlers importing `integrations.slack` models and parser;
- `server/bot_middleware.py` attaching the bot to request state;
- packages unable to register block actions and view submissions until the registrar grows them (TASK-140).

**Changes:**
- 2026-09-24: the handler contract moves to `app/contracts/`, per plugin-architecture.md.
- 2026-09-25: Accepted; an unlinked caller reaches the feature's access policy instead of being refused at the entry point.
- 2026-10-01: `register_slack_listeners` is deleted (TASK-26.1); its tolerated item is closed.
- 2026-10-06: business code stays platform-neutral and a platform entry point handles interactions with its native SDK; the registrar covers block actions and view submissions (TASK-140.1).
