---
status: Accepted
date: 2026-07-06
applies: target
scope: Settings ownership, environment identity, and secrets.
---

# Configuration

## Context

Settings are split across ~47 classes with two homes per vendor (`integrations/<vendor>/settings.py` and `infrastructure/configuration/integrations/<vendor>.py`), the security domain reads its config from `ServerSettings`, and "is this production?" is derived from `PREFIX == ""` — one overloaded bit driving prod detection, CORS shape, dev-bypass, and SNS validation.

## Decision

**Ownership: settings live with the code they configure.** Each domain defines one `pydantic_settings.BaseSettings` slice next to its service, with a cached `get_<domain>_settings()` provider:

- Vendor credentials → `app/integrations/<vendor>/settings.py` (single home; the `infrastructure/configuration/integrations/` twins are deleted). A system reached in more than one role holds **one least-privilege credential per role**, not one shared login: e.g. Slack's inbound bot token + Socket Mode app token (transport) are distinct from an admin/`usergroups:write` token used by a feature that mutates Slack (per [platform-transports.md](platform-transports.md); OWASP API5 BFLA).
- Transport settings → `app/infrastructure/<platform>/settings.py`.
- Capability/service settings → with the service; feature settings → in the feature package.
- The security domain owns a `SecuritySettings` slice covering its own config — allowed issuers/JWKS, CORS allow-list, rate-limit storage backend, and the dev-bypass flag — rather than borrowing fields from a shared server-settings object.
- One env var has exactly one owning class. Namespaced env names (`SLACK__…`, `AWS__…`) via `env_nested_delimiter`.

**Environment identity:** one typed field, `ENVIRONMENT: Literal["local","ci","dev","staging","production"]`, on the app settings. All environment-conditional behavior reads it; deriving environment from `PREFIX`, hostname, or `sys.modules` is prohibited. Security-relevant toggles (dev-bypass) additionally require their own explicit boolean that defaults off — two independent guards.

**Fail fast:** settings validate at import of their provider during lifespan phase 2; a missing required credential fails boot with a message naming the variable.

**Secrets:** secret material resolves through the `SecretsService` port ([cloud-portability.md](cloud-portability.md)) or is platform-injected at deploy time (ECS task-definition `secrets:` → Secrets Manager); plain env-var secrets are a **tolerated divergence, not the target** — OWASP's Secrets Management guidance recommends against env vars where a managed alternative exists. Secrets never appear in defaults, logs ([observability.md](observability.md)), or repr. Rotation contract: JWKS refreshes at runtime; static secrets rotate by redeploy.

**Consumers receive slices,** not a god-settings object: a service constructor takes its own `BaseSettings` class, nothing wider.

## Consequences

- "Where is this configured?" has one answer per domain; deleting a feature deletes its config.
- The typed environment enum turns the current one-character-typo security hazard into an enum validation error at boot.
- Migration is mechanical but wide (many import edits); do it per-domain alongside other work in each area.

## Checks

- CI script: each env var referenced by exactly one `BaseSettings` class.
- grep: no `PREFIX ==`/`is_production` environment derivation; no `os.environ` reads outside settings classes.
- Boot test: missing required credential → clean failure naming the variable.

## Migration

Ticket: settings consolidation. Tolerated until closed: dual vendor settings homes; security config still carried on a shared server-settings object rather than its own `SecuritySettings` slice.
