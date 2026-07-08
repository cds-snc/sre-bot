# Decisions

This folder is the architectural source of truth. It supersedes `docs/adr/` (kept temporarily for history; do not update it).

**Reading order for a new contributor** (~30 minutes):

1. [layers.md](layers.md) — the three-tier model and the one import rule.
2. [feature-packages.md](feature-packages.md) — how to build a feature (this is where you'll spend your time).
3. [operation-result.md](operation-result.md) — the one return contract you must know.
4. [dependency-injection.md](dependency-injection.md) — how you get your dependencies.
5. [transport-slack.md](transport-slack.md) — if your feature talks to Slack.
6. [outbound-clients.md](outbound-clients.md) — if your feature calls an external service.
7. [testing.md](testing.md) — before you open a PR.

Everything else is reference: read it when the topic comes up.

## The vision in three sentences

The app is a modular monolith that started as a Slack bot and is becoming platform-agnostic. **Features** (`app/packages/`) contain business logic and depend only on Protocol interfaces. **Infrastructure** (`app/infrastructure/`) provides those Protocols — portable capabilities (storage, queue, identity) that must survive a cloud move, and platform transports (Slack, later Teams) that the host owns end-to-end. **Integrations** (`app/integrations/`) are thin outbound clients for third-party services.

## Record index

| Record | Scope | Applies |
| --- | --- | --- |
| [governance.md](governance.md) | How decisions are written and changed | now |
| [layers.md](layers.md) | Three tiers, import direction, Path A/B, transports vs clients | target |
| [cloud-portability.md](cloud-portability.md) | The four portability contracts | target |
| [platform-transports.md](platform-transports.md) | How a chat platform composes into the host | target |
| [transport-slack.md](transport-slack.md) | Slack: verification, delivery mode, handlers, errors | target |
| [outbound-clients.md](outbound-clients.md) | Gateway pattern, retry, exception classification | target |
| [operation-result.md](operation-result.md) | The boundary return envelope | target |
| [errors-and-http.md](errors-and-http.md) | RFC 9457 mapping at the HTTP edge | target |
| [dependency-injection.md](dependency-injection.md) | Providers, Depends, composition at startup | target |
| [plugins.md](plugins.md) | Feature registration via pluggy | now |
| [events.md](events.md) | In-process domain events | target |
| [feature-packages.md](feature-packages.md) | Feature layout and handler discipline | now |
| [configuration.md](configuration.md) | Settings ownership, environments, secrets | target |
| [security.md](security.md) | AuthN/Z, CORS, rate limiting, webhooks | target |
| [observability.md](observability.md) | Logging, redaction, correlation | target |
| [reliability.md](reliability.md) | Idempotency, queuing, background jobs | target |
| [lifecycle.md](lifecycle.md) | Phased startup and shutdown | now |
| [toolchain.md](toolchain.md) | uv, Python version, lint, types, CI gates | target |
| [testing.md](testing.md) | Test layers, doubles, coverage | target |
| [i18n.md](i18n.md) | EN/FR translation | target |
| [migration.md](migration.md) | The strangler plan for `app/modules/` | now |

`Applies: now` means the record's Checks pass on `main` today. `Applies: target` means the record describes the destination and names its migration ticket — the code is allowed to diverge *only* in the ways the record's Migration section lists.
