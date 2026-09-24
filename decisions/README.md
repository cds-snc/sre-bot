# Decisions

**Reading order for a new contributor** (~30 minutes):

1. [plugin-architecture.md](plugin-architecture.md) — the six layers, what each holds, and what each may import.
2. [feature-packages.md](feature-packages.md) — the one package shape for features and capabilities (this is where you'll spend your time).
3. [dependency-injection.md](dependency-injection.md) — how your plugin gets core services.
4. [plugins.md](plugins.md) — how a plugin is declared, enabled and registered.
5. [operation-result.md](operation-result.md) — the one return contract you must know.
6. [platform-transports.md](platform-transports.md) and [transport-slack.md](transport-slack.md) — if your feature talks to Slack.
7. [outbound-clients.md](outbound-clients.md) — if your feature calls an external service ([sdk-typing.md](sdk-typing.md) covers typing its SDK).
8. [testing.md](testing.md) — before you open a PR.

Everything else is reference: read it when the topic comes up.

## The vision in three sentences

The app is a platform that other teams extend: a host (`app/server/`) loads feature and capability plugins at startup, and plugins build only against a small public API (`app/contracts/`). **Features** (`app/features/`) hold business logic, **capabilities** (`app/capabilities/`) hold engines and shared business services such as approvals, notifications, people and workplace systems, and neither ever imports the host or the hosting code. **Infrastructure** (`app/infrastructure/`) implements the hosting contracts (storage, queue, coordination, secrets) so the app can move between clouds, and **integrations** (`app/integrations/`) are thin clients for third-party services.

## Record index

| Record | Scope | Applies |
| --- | --- | --- |
| [governance.md](governance.md) | How decisions are written and changed | now |
| [plugin-architecture.md](plugin-architecture.md) | The six layers, their import rules, the service registry, extension points and plugin enablement | target |
| [workplace-systems.md](workplace-systems.md) | Draft: hosting services vs workplace systems, records of truth in storage | target |
| [people-and-accounts.md](people-and-accounts.md) | Draft: people, linked accounts across systems, person kinds, conversation origin | target |
| [platform-entrypoints.md](platform-entrypoints.md) | Draft: chat platforms split into server entry points, handler contracts and outbound messaging | target |
| [interaction-toolkits.md](interaction-toolkits.md) | Draft: a per-platform toolkit for rich chat interactions that never wraps the SDK | target |
| [cloud-portability.md](cloud-portability.md) | The four portability contracts | target |
| [platform-transports.md](platform-transports.md) | How a chat platform composes into the host | target |
| [transport-slack.md](transport-slack.md) | Slack: verification, delivery mode, handlers, errors | target |
| [outbound-clients.md](outbound-clients.md) | Gateway pattern, retry, exception classification | target |
| [service-accounts.md](service-accounts.md) | When a feature needs a dedicated non-human identity inside a SaaS | target |
| [sdk-typing.md](sdk-typing.md) | Typing rich vendor SDKs without a wrapper tier (boto3 stubs, Google discovery) | target |
| [operation-result.md](operation-result.md) | The boundary return envelope | target |
| [errors-and-http.md](errors-and-http.md) | RFC 9457 mapping at the HTTP edge | target |
| [dependency-injection.md](dependency-injection.md) | Core services from a type-keyed registry, constructor injection, eager validation | target |
| [plugins.md](plugins.md) | Plugin declaration, per-environment enablement and registration via pluggy | target |
| [feature-packages.md](feature-packages.md) | The one package shape for features and capabilities, handler discipline | target |
| [configuration.md](configuration.md) | Settings slices, per-environment TOML files, secrets | target |
| [security.md](security.md) | AuthN/Z, CORS, rate limiting, webhooks | target |
| [dependency-scanning.md](dependency-scanning.md) | Dependency-vulnerability CI gate ownership and enforcement | target |
| [hookspec-deprecation.md](hookspec-deprecation.md) | How a hookspec is deprecated and removed | target |
| [webhooks.md](webhooks.md) | Incoming-webhook capability: pipeline, source-declared parsing, handler extension point | target |
| [observability.md](observability.md) | Logging, redaction, correlation | target |
| [health-checks.md](health-checks.md) | Container, ECS, ALB, and Route53 health-check layering | target |
| [reliability.md](reliability.md) | Idempotency, queuing, background jobs | target |
| [approvals.md](approvals.md) | Generic human-approval workflow capability | target |
| [lifecycle.md](lifecycle.md) | Phased startup and shutdown across replicas | target |
| [toolchain.md](toolchain.md) | uv, Python version, lint, types, CI gates | target |
| [testing.md](testing.md) | Test layers, doubles, coverage | target |
| [i18n.md](i18n.md) | EN/FR translation | target |
| [migration.md](migration.md) | The strangler plan for `app/modules/`: rebuild by surface, non-layer directories | now |

`Applies: now` means the record's Checks pass on `main` today. `Applies: target` means the record describes the destination and names its migration ticket — the code is allowed to diverge *only* in the ways the record's Migration section lists.
