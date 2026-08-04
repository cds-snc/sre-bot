---
name: settings-singleton
description: Apply partitioned settings and singleton provider patterns; use when adding or refactoring settings and provider wiring.
---

# Settings Singleton and Partitioning

Use this skill when introducing settings for new package domains, adjusting providers, or refactoring legacy settings usage.

## Core Rules

1. New package settings belong in `app/packages/<feature>/settings.py`.
2. Avoid growing root settings aggregators for package-owned concerns.
3. Validate settings at startup through lifecycle hooks.
4. Provider functions should expose cached singletons and inject narrow settings slices.
5. Services should receive only required settings sections.

## Provider Pattern

- Use `@lru_cache(maxsize=1)` for singleton providers.
- Keep providers in assembly/dependency layers, not service constructors.
- Do not call `get_settings()` from within service constructors.

## Migration Safety

When touching legacy settings:

1. Preserve existing runtime behavior first.
2. Introduce package-local settings for new functionality.
3. Migrate consumers incrementally to slice-based constructors.
4. Remove legacy wiring only after full migration and tests.

## Security-Sensitive List Settings (CORS, allow-lists, etc.)

1. Security-sensitive list settings (CORS origins/methods/headers, IP allow-lists, etc.) must default to a safe deny/empty state, never a wildcard.
2. Validate them with `@model_validator(mode="after")` raising `ValueError` for insecure combinations (e.g. `"*"` combined with `allow_credentials=True`) - this fires at settings construction, which is effectively boot time. Enforce in every environment, not just production.
3. Never derive a cross-origin allow-list (or similar externally-facing identity config) from the service's own base URL/domain or from `ENVIRONMENT`/`PREFIX` shape. CORS authorizes a *different* origin than the API itself; same-origin traffic never needs it. Populate real values explicitly via settings/deployment config instead of computing them.

## Environment Identity vs Platform-Presentation Config

1. Runtime environment identity is one typed field, `ENVIRONMENT` (`Literal["local","ci","dev","staging","production"]`), on app settings. It is the sole environment signal and may be read for *legitimate* environment-conditional behavior (dev-only commands, local-service endpoints, prod-only side effects). Never re-derive environment from `PREFIX`, hostname, or `sys.modules`.
2. Platform-presentation config — e.g. Slack command namespacing so a dev and prod bot coexist in one workspace — is orthogonal to environment identity. It lives in the transport's own settings home (`app/infrastructure/<platform>/settings.py`) as an explicit field (`COMMAND_PREFIX`), **never** derived from `ENVIRONMENT`. Transport-agnostic features never read platform settings; the transport applies command naming at registration.
3. The legacy `AppSettings.PREFIX` carries no environment meaning and is not a home for new config — it survives only as the legacy Slack command-namespace read by frozen `app/modules/`, deleted when they are. New code uses `ENVIRONMENT` (identity) or the transport's `COMMAND_PREFIX` (naming). Reference: `decisions/configuration.md`, `decisions/transport-slack.md`.

## Anti-patterns

- Adding new package settings directly to central aggregator by default.
- Passing a broad root settings object into every service.
- Instantiating settings repeatedly in route or service code.
- Branching security-relevant config (CORS, dev-bypass, etc.) on `ENVIRONMENT`/`PREFIX` instead of reading an explicit settings field.
- Putting platform-presentation config (command namespacing / `COMMAND_PREFIX`) in app/root settings or deriving it from `ENVIRONMENT`/`PREFIX`; it is a transport-owned explicit setting.

## Minimum Tests

1. Startup validation passes with valid env.
2. Startup fails deterministically with invalid env.
3. Provider returns singleton instance behavior.
4. Service accepts narrow settings slice and works correctly.
