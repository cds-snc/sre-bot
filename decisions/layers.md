---
status: Accepted
date: 2026-07-06
applies: target
scope: The three-tier layer model, import direction, and the two integration paths.
---

# Layers

## Context

Feature code changes when business requirements change; vendor code changes when providers or SDKs change. When the two are coupled, either change forces rewrites of the other. We also need one more distinction the old corpus missed: **some external systems are the app's front door** (Slack today, Teams likely tomorrow — the platform runtime lives *in our process* and drives the application), while **others are services we call at a boundary** (AWS, Google Workspace, MaxMind — invoked outbound, sometimes). Conflating these two produced the contradictory "shield" decisions.

Current state: `app/integrations/` is the current client layer and still contains `_next.py` twins; `integrations/slack/` contains a full transport (Bolt runtime, parser, formatter), most of which belongs in `infrastructure/slack/` while the Web API client stays as the `integrations/` primitive; `integrations/` imports upward into `infrastructure` ~38 times.

## Decision

Three tiers under `app/`, with **one import rule: dependencies point downward only.**

```text
app/packages/         Features. Business logic, domain models, handlers.
        │  imports Protocols from ↓
app/infrastructure/   Capabilities and platform transports, behind typing.Protocol.
        │  imports clients from ↓
app/integrations/     Outbound clients. Thin, vendor-specific, raise SDK exceptions.
```

**`app/integrations/` holds outbound boundary clients only** — authenticated construction of a vendor SDK client plus that vendor's exception-classification table (see [outbound-clients.md](outbound-clients.md)). Nothing else. A platform's *inbound runtime* (Bolt, Socket Mode) does **not** live here — but a platform's *Web API client* does, because a feature may act on the platform as an outbound target (see [platform-transports.md](platform-transports.md), "a platform is also a driven dependency"). Roles are decided by **direction × purpose**, never by the vendor's identity: the same system can be a driving transport *and* a driven dependency at once, behind different ports sharing one client.

**`app/infrastructure/` holds two kinds of services**, both exposed as `typing.Protocol` + provider function:

- *Portable capabilities* (storage, queue, idempotency, directory, events, approvals…): the Protocol is capability-shaped and vendor-neutral; the implementation uses an integrations client and is swappable per deployment. This is the cloud-portability mechanism.
- *Platform transports* (`infrastructure/slack/`, later `infrastructure/teams/`): first-class, in-process services that own the platform's **inbound runtime** — SDK runtime (Bolt), Socket Mode connection, verification, dispatch — plus the formatting/parsing helpers and the outbound Protocol (`SlackService`) inbound handlers use to reply. A transport is not an "integration we sometimes call"; it is part of the host. The platform's authenticated **Web API client** is a separate connectivity primitive in `integrations/<platform>/` that both the transport and any outbound feature share. See [platform-transports.md](platform-transports.md).

**Shared kernel.** `infrastructure/operations/` (`OperationResult`, `OperationStatus`) is a declared leaf: any tier may import it. Nothing else in `infrastructure/` is importable from `integrations/`. This legalizes the one upward import every layer genuinely needs and forbids the rest.

**Two integration paths for features** (unchanged from the original vision, by *purpose* not consumer count):

- **Path A — portable capability.** The feature asks in vendor-neutral language ("store this object"). Infrastructure owns the Protocol; the vendor is a deployment detail. Lives in `app/infrastructure/<service>/`.
- **Path B — the external system *is* the point.** The feature exists to act on a specific system (provision AWS Identity Center, post to Slack). The Protocol is shaped by that system. Feature-owned Path B adapters live at `app/packages/<feature>/adapters/<provider>.py` and are the only feature files that may import from `app/integrations/`. Promotion to shared infrastructure happens when a second feature needs the same adapter — then, in one PR, it moves to `app/infrastructure/<service>/`.

**The invariant:** feature domain and service code never names a concrete vendor type. Protocols in, adapters at the edge.

**Non-tier top-level directories.** The only sanctioned top-level entries under `app/` are the three tiers above, the `server/` host process (composition root, lifespan, middleware), and `main.py` (the ASGI entrypoint). Every other current top-level directory is transitional and carries an explicit disposition and ticket — none is a new sanctioned home:

| Directory | Disposition | Ticket |
| --- | --- | --- |
| `modules/` | Legacy Slack bot; strangled into feature packages, then deleted. | [migration.md](migration.md) |
| `jobs/` | Scheduler registry — a vendor-neutral, clock-driven host capability (composed like a transport); relocate into `infrastructure/` once its pull-hub is strangled to the `register_background_jobs` push model. | TASK-52 |
| `api/` | Legacy top-level HTTP surface; feature routes move to their owning packages, feature-agnostic system endpoints (health, version, landing) move to the host. | TASK-53 |
| `bin/` | Operator/dev tooling — **not app runtime code**, exempt from the import rule; kept, but `entry.sh`'s boot-time secret fetch retires once a secret service exists. | TASK-54 |
| `models/` | Shared boundary DTOs; relocate to owning packages/tiers (live non-module consumers exist), then delete the top-level bag. | TASK-55 |
| `utils/` | Grab-bag helpers; relocate to the owning tier without introducing upward imports, then delete. | TASK-56 |
| `locales/` | Legacy `python-i18n` catalogues; deleted at strangler completion, superseded by per-feature catalogues ([i18n.md](i18n.md)). | [migration.md](migration.md), TASK-41 |
| `geodb/` | AWS/CI-coupled, image-baked MaxMind DB; rearchitect to a configurable, cloud-agnostic, OSS-reusable source. | TASK-57 |

## Consequences

- Vendor swaps and SDK upgrades don't propagate into features; features are testable with Protocol stubs.
- The transport/client split ends the "is Slack a vendor SDK?" debate: Slack is a transport; its Web API is reached through the transport's Protocol.
- Cost: every feature-consumed integration needs an explicit Protocol, and contributors must pick a path (the litmus test — vendor-neutral question or not — takes seconds).

## Checks

- import-linter (see [toolchain.md](toolchain.md)): `packages → infrastructure → integrations` layer contract; `integrations` may import nothing from upper tiers except `infrastructure.operations`; `packages/**` may import `integrations` only inside `adapters/`.
- No directory named `clients/` exists under `app/`.
- Every top-level directory under `app/` other than `packages/`, `infrastructure/`, `integrations/`, `server/`, and `main.py` has a disposition row in the non-tier-directories table above (grep the tree against the table when adding one).

## Migration

Ticket: architecture epic. Tolerated divergences until closed: `_next.py` twins, Slack content still in `integrations/slack/`, the upward imports from `integrations/` into `infrastructure/`, and the non-tier top-level directories listed above (each held by its own ticket).
