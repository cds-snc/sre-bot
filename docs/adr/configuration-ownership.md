---
title: "Configuration Ownership and Settings"
status: Draft
type: Standard
tier: Tier-2
governance_domain: [application]
concerns: [configuration, architecture]
constrained_by: [layered-architecture.md, type-boundaries.md, cloud-portability.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Configuration Ownership and Settings

## Context and Problem Statement

The application reads its configuration from environment variables (per [cloud-portability.md](cloud-portability.md) Contract 1). Different parts of the codebase consume different slices of that configuration: a feature package needs its own behavioral switches and credentials; a composed infrastructure service needs the connection parameters for its backing provider; a small set of values (environment label, log level, deployment identifier) genuinely spans the whole process. Each consumer needs only the slice relevant to it, validated at startup, and constructed once per process.

The problem this record addresses: **how is configuration partitioned, who owns each slice, and how is each slice made available to its consumers?** The answer determines three things at once:

1. Whether changing one slice (a new setting for a single feature) requires touching code outside the feature that owns it.
2. Whether two consumers of the same env var share one definition or drift independently.
3. Whether settings instances are constructed and validated once at startup, or recomputed (and re-validated) at each access.

**Constraints:**

- All configuration is sourced from environment variables ([cloud-portability.md](cloud-portability.md) Contract 1). Runtime fetches from external configuration stores during request handling are out of scope.
- The type construct at the configuration boundary is `pydantic_settings.BaseSettings`; nested sections use `BaseModel`; `BaseSettings` is never nested inside another `BaseSettings` ([type-boundaries.md](type-boundaries.md)).
- Settings are validated at construction time. Invalid configuration must halt startup before the process accepts traffic.
- The application is otherwise stateless, but settings are process-lifetime singletons. They are derived from the environment at boot, not from request flow, so the singleton property does not violate the statelessness invariant.

**Non-goals:**

- This record does not define the type construct used at the configuration boundary — see [type-boundaries.md](type-boundaries.md).
- This record does not govern how configuration values reach the process at deploy time (Terraform, container task definitions, secret managers) — that is an operations concern.
- This record does not govern *runtime* configuration (values fetched on demand from external systems during request handling) — only env-var-sourced settings read at startup.

## Considered Options

**Option 1 — Single application-wide Settings class.** One `BaseSettings` aggregates every env var the application reads; consumers depend on the global Settings instance and pick out the fields they need.

**Option 2 — One `BaseSettings` per domain, co-located with the code that consumes it.** Each feature package has its own `settings.py`; each infrastructure service has its own; a small `AppSettings` carries truly cross-cutting values. Each settings class has a cached provider function; consumers depend on the provider for their slice.

**Option 3 — Per-call construction with no caching.** Settings classes are constructed and validated on each access. There are no singletons.

## Decision Outcome

**Chosen: Option 2 — one `BaseSettings` per domain, co-located with the code that consumes it.**

The unit of ownership is the *domain*: a feature package, a composed infrastructure service, or a single explicitly cross-cutting app-level concern. Each owns its own `BaseSettings` class. There is no application-wide Settings aggregator. Consumers depend on the provider for their own slice, not on a god object.

### Partitioning and ownership

- A feature package owns a `settings.py` (or `settings/` module) inside the package: `app/packages/<feature>/settings.py`. The feature's `BaseSettings` declares only the env vars the feature consumes.
- A composed infrastructure service owns a settings module co-located with the service: `app/infrastructure/<service>/settings.py`. The service's `BaseSettings` declares only the env vars the service consumes.
- A single `AppSettings` at `app/settings.py` declares truly cross-cutting values — values that have no single owning domain (e.g., environment label, deployment identifier, base log level).
- No env var is declared in more than one `BaseSettings` class. When two domains read the same value, one owns it and the other calls that domain's provider to read it. The most common case for shared reads is `AppSettings`, which any domain may consume.

### Provider: `@lru_cache(maxsize=1)`

Each `BaseSettings` class is paired with a provider function whose only job is to construct (and therefore validate) the class once and cache the result for the process lifetime:

```python
@lru_cache(maxsize=1)
def get_my_feature_settings() -> MyFeatureSettings:
    return MyFeatureSettings()
```

The provider is the only public way to obtain a settings instance. Direct instantiation of a `BaseSettings` class is reserved for tests that need to assert parsing behavior of the class itself.

### Narrow-slice injection

Consumers depend on the provider for the slice they need, not on a wider settings root:

- **HTTP route handlers** receive settings through FastAPI's dependency injection: `Annotated[MyFeatureSettings, Depends(get_my_feature_settings)]`.
- **Background jobs, hookimpls, and startup code** call the provider directly: `settings = get_my_feature_settings()`.
- **An infrastructure service or feature provider that composes multiple slices** (e.g., a notification service needing its own settings and `AppSettings`) calls each provider in its own provider function. Composition is explicit at the construction site governed by [dependency-injection.md](dependency-injection.md).

A consumer does not depend on a settings class outside its own domain except for `AppSettings`, which any domain may read.

### Validation timing: fail-fast at startup

Settings classes are constructed during application startup. Construction performs Pydantic validation; a missing required env var or a value that fails type checks raises an error and halts boot before the process accepts traffic. Lazy validation (deferring first construction to first request) is not permitted: configuration errors must be visible at the deployment-readiness boundary, not at first traffic.

### `SettingsConfigDict` baseline

Every `BaseSettings` class declares at minimum:

- `env_file=".env"` so a developer-supplied `.env` is read in local development.
- `extra="ignore"` so the presence of unrelated env vars (which always exist on real hosts) does not fail validation.

Domain-specific options (`env_prefix`, aliases, validators) are added by the domain as needed.

### Test substitution

Two patterns are supported, depending on consumer type:

- **HTTP route consumers.** Tests register an override before the test client invokes the route and clear it afterwards: `app.dependency_overrides[get_my_feature_settings] = lambda: MyFeatureSettings(field=...)`.
- **Direct-call consumers** (background jobs, hookimpls, startup code). Tests call the provider's `cache_clear()` method, set the desired env vars (typically via `monkeypatch`), and call the provider, which constructs and validates against the test environment. Setup clears caches; teardown clears them again.

Tests must not bypass the provider by constructing settings classes directly when exercising domain logic — substitution always goes through the provider so the production injection path is what is tested.

## Consequences

**Positive:**

- A new feature can be added with its own settings without modifying any other package. A removed feature deletes its settings cleanly.
- Two domains using the same env var either name the owning domain explicitly (and the other calls its provider) or the var belongs in `AppSettings` because it genuinely is cross-cutting. There is no third option to accumulate ad-hoc.
- Each settings class has exactly one validation point (the provider's first call) and one source of truth (the class declaration co-located with the consumer).
- Test substitution is local to the slice the test exercises; a feature test does not need to construct the entire application's configuration.

**Tradeoffs accepted:**

- A consumer that legitimately needs values from two domains calls two providers. Composition is more explicit than reaching into a single global Settings.
- The application accumulates many small `BaseSettings` classes rather than one large one. Each is small; the count is the price of ownership locality.

**Risks:**

- A developer may declare the same env var in two settings classes (one in the owning domain, one in a module that happens to need it). Mitigation: code review and a CI check confirm each env var name appears in exactly one `BaseSettings` subclass.
- A developer may forget to clear the provider cache between tests, getting stale settings. Mitigation: a shared test fixture clears all registered providers in setup.

## Confirmation

Compliance is verified by:

- **Code review.** Each new settings class lives co-located with its consumer (in the feature package or in the infrastructure service module). A `@lru_cache(maxsize=1)` provider function accompanies it. No application-wide aggregator class is added.
- **Static analysis / CI check.** No env var name is declared in more than one `BaseSettings` subclass.
- **Tests.** Settings overrides go through `app.dependency_overrides` for HTTP consumers and `cache_clear()` + env injection for direct-call consumers. Tests for invalid configuration assert that startup fails at provider construction, not at first request.

## Source References

1. The Twelve-Factor App — Config (Factor III)
   - URL: <https://12factor.net/config>
   - Accessed: 2026-04-29
   - Relevance: Establishes "store config in the environment." Settings classes are the application-side typed access path to that environment; the partitioning rule organizes that access so each consumer reads only the slice it owns.

2. Pydantic Settings V2 — Configuration
   - URL: <https://docs.pydantic.dev/latest/concepts/pydantic_settings/>
   - Accessed: 2026-04-29
   - Relevance: Documents `pydantic_settings.BaseSettings`: env-var sourcing, validation at instantiation, `env_file`, `env_prefix`, `extra="ignore"`. Grounds the construction-time validation rule and the `SettingsConfigDict` baseline.

3. FastAPI — Dependencies
   - URL: <https://fastapi.tiangolo.com/tutorial/dependencies/>
   - Accessed: 2026-04-29
   - Relevance: Defines `Annotated[T, Depends(...)]` for declarative injection and `app.dependency_overrides` for test-time substitution. Grounds the HTTP-route consumer pattern and the corresponding override approach.

4. Python 3.12 — `functools.lru_cache`
   - URL: <https://docs.python.org/3.12/library/functools.html#functools.lru_cache>
   - Accessed: 2026-04-29
   - Relevance: Documents `@lru_cache(maxsize=1)` semantics and the `cache_clear()` method. Grounds the singleton-provider pattern and the test cache-clearing approach for direct-call consumers.

5. Composition Root — Mark Seemann
   - URL: <https://blog.ploeh.dk/2011/07/28/CompositionRoot/>
   - Accessed: 2026-05-04
   - Relevance: Establishes that dependencies (including configuration) are constructed at a single composition point and injected into the consumers that need them. Grounds the rule that settings reach consumers through providers and dependency injection, not through global access.

## Change Log

- 2026-05-08: Created. Establishes per-domain partitioning of `BaseSettings` (one settings class per feature package, per composed infrastructure service, plus a single cross-cutting `AppSettings`), `@lru_cache(maxsize=1)` providers as the only public access path, narrow-slice injection through providers (FastAPI `Depends` for HTTP consumers; direct calls for background and startup code), startup-time validation, and a uniform test-substitution pattern using dependency overrides or cache-clearing depending on consumer type.
