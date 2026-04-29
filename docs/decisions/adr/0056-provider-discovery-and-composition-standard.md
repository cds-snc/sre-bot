---
adr_id: ADR-0056
title: "Provider Discovery and Composition Standard"
status: Accepted
decision_type: Pattern
tier: Tier-2
primary_domain: Dependency and Composition
secondary_domains:
  - Package and Plugin Architecture
  - Configuration and Secrets
owners:
  - SRE Team
date_created: 2026-04-29
last_updated: 2026-04-29
last_reviewed: 2026-04-29
next_review_due: 2026-08-27
constrained_by:
  - ADR-0044
  - ADR-0048
  - ADR-0055
impacts:
  - ADR-0059
supersedes:
  - ADR-0012
superseded_by: []
review_state: current
related_records:
  - ADR-0045
  - ADR-0046
  - ADR-0047
  - ADR-0049
  - ADR-0054
  - ADR-0077
related_packages:
  - app/infrastructure/services
  - app/packages/access
---

# Provider Discovery and Composition Standard

## Context

- Problem statement: The service provider layer in `app/infrastructure/services/providers.py` contains 17 `@lru_cache(maxsize=1)` singleton service providers (18 including `get_settings()`) and 3 non-cached platform provider accessors in a single 700+ line file. This file is the sole location responsible for constructing every infrastructure service. Five providers pass the full `Settings` object to service constructors instead of narrow slices, violating ADR-0047 Principle 4 and ADR-0048 Boundary 3. Every new infrastructure service requires a three-file edit (providers.py + dependencies.py + \_\_init\_\_.py), creating ceremony proportional to service count. The file mixes genuinely shared platform capabilities (AWS clients, storage, identity) with domain-specific services (command, notification, platform) and convenience accessors (get\_slack\_provider, get\_teams\_provider) that don't use `@lru_cache`. Meanwhile, feature packages like `app/packages/access` have independently developed a package-local provider pattern that is proven and deployed but not explicitly permitted by any Tier-1 or Tier-2 ADR. The legacy ADR-0012 (Provider Discovery) defined a rigid load-order model (Groups → Commands → Platforms) that is superseded by the pluggy-based registration model in ADR-0049. The legacy ADR-0025 (Interaction Providers Concept) defined a platform abstraction pattern that remains valid in concept but whose provider-layer governance is outdated.
- Business/operational drivers:
  - Establish the canonical composition model for singleton service providers after ADR-0055 settings dissolution.
  - Enforce narrow-slice injection: no service constructor may accept the full `Settings` object.
  - Explicitly permit and govern package-local providers for feature packages.
  - Define whether infrastructure providers remain centralized or distribute to their service modules.
  - Simplify or govern the three-file DI alias ceremony (providers.py + dependencies.py + \_\_init\_\_.py).
  - Clarify the role and permissibility of non-cached convenience accessors in the provider layer.
  - Define the provider dependency graph shape and composition depth rules.
- Constraints:
  - All provider functions are the sole constructors for their services (ADR-0048 B3: constructor-only dependency receipt).
  - Providers must be consumed through a single injection boundary (ADR-0048 B2).
  - No import-time side effects from provider modules (ADR-0048 B4, ADR-0049 S8).
  - Infrastructure sibling isolation: infrastructure packages must not import from other infrastructure service implementations directly (ADR-0048 B5).
  - Settings dissolution (ADR-0055) replaces the single `get_settings()` call with domain-specific settings providers.
  - Plugin registration and startup ordering follows ADR-0046 and ADR-0049.
  - Dev/prod parity constraints from ADR-0054 apply to provider behavior consistency.
- Non-goals:
  - This record does not define specific service constructor signatures or internal service design.
  - This record does not define plugin registration mechanics (governed by ADR-0049).
  - This record does not define settings class structure or ownership (governed by ADR-0055).
  - This record does not define the HTTP-first interaction pattern for platform providers (that concept from ADR-0025 remains valid as a feature-architecture concern for a future ADR-0059 or equivalent).

## Decision

- Chosen approach: Establish a provider composition standard that enforces narrow-slice injection, retains centralized infrastructure providers, permits package-local providers for feature packages, governs the DI alias ceremony, and defines the provider dependency graph shape.
- Why this approach: The current centralized model works for infrastructure services where the count is stable and the dependency graph is shallow. Distribution would fragment the injection boundary without proportional benefit. Package-local providers for feature packages are already proven (access package) and align with ADR-0047 P2 (ownership follows code). The three-file ceremony, while verbose, provides explicit traceability and should be retained with minor governance improvements rather than replaced with implicit convention.

### Standard 1: Narrow-Slice Injection Enforcement

No service constructor may accept the full `Settings` object or any aggregated settings root. Every constructor must receive only the specific settings slice or values it needs.

**Correct — narrow slice:**

```python
@lru_cache(maxsize=1)
def get_aws_clients() -> AWSClients:
    settings = get_settings()
    return AWSClients(aws_settings=settings.aws)
```

After ADR-0055 dissolution:

```python
@lru_cache(maxsize=1)
def get_aws_clients() -> AWSClients:
    aws_settings = get_aws_settings()
    return AWSClients(aws_settings=aws_settings)
```

**Correct — scalar extraction:**

```python
@lru_cache(maxsize=1)
def get_slack_client() -> SlackClientFacade:
    settings = get_settings()
    return SlackClientFacade(token=settings.slack.SLACK_TOKEN)
```

After ADR-0055 dissolution:

```python
@lru_cache(maxsize=1)
def get_slack_client() -> SlackClientFacade:
    slack_settings = get_slack_settings()
    return SlackClientFacade(token=slack_settings.SLACK_TOKEN)
```

**Prohibited — wide injection:**

```python
# WRONG: full Settings object passed to constructor
@lru_cache(maxsize=1)
def get_notification_service() -> NotificationService:
    settings = get_settings()
    return NotificationService(settings=settings, ...)
```

**Corrected — narrow slice:**

```python
@lru_cache(maxsize=1)
def get_notification_service() -> NotificationService:
    notify_settings = get_notify_settings()
    return NotificationService(
        notify_settings=notify_settings,
        idempotency_service=get_idempotency_service(),
        resilience_service=get_resilience_service(),
    )
```

**Current violations requiring remediation:**

| Provider | Current injection | Required change |
|----------|-------------------|-----------------|
| `get_identity_service()` | `IdentityService(settings=settings)` | Accept identity-relevant slice only |
| `get_maxmind_client()` | `MaxMindClient(settings=settings)` | Accept `MaxMindSettings` |
| `get_idempotency_service()` | `IdempotencyService(settings=settings)` | Accept `IdempotencySettings` |
| `get_resilience_service()` | `ResilienceService(settings=settings)` | Accept `RetrySettings` |
| `get_notification_service()` | `NotificationService(settings=settings, ...)` | Accept `NotifySettings` |
| `get_command_service()` | `CommandService(settings=settings)` | Accept `CommandsSettings` |
| `get_platform_service()` | `PlatformService(settings=settings)` | Accept `PlatformsSettings` |

**Protocol return type requirement (ADR-0077):** In addition to narrow-slice injection, provider functions for Category A services (as classified by ADR-0077) must use the Protocol type as their return type annotation, not the concrete implementation class. After ADR-0077 Protocol migration, the provider return type and the dependency alias type must both reference the Protocol. See ADR-0077 Standard 2 for the full contract pattern.

### Standard 2: Package-Local Provider Permission

Feature packages may define their own `@lru_cache(maxsize=1)` provider functions for:

1. **Package-owned settings** — e.g., `get_access_settings()` in `packages/access/common/settings.py`.
2. **Package-owned runtime config** — e.g., `get_access_runtime_config()` in `packages/access/common/providers.py`.
3. **Package-owned domain services** — e.g., `get_access_sync_coordinator()` in `packages/access/sync/providers.py`.
4. **Package-owned repositories** — e.g., `get_sync_run_repository()` in `packages/access/sync/providers.py`.

Package-local providers are **not** registered in the central `infrastructure/services/providers.py`. They are private to the package and consumed only by code within that package or by the package's plugin hooks.

**Rules for package-local providers:**

| Rule | Rationale |
|------|-----------|
| Provider must use `@lru_cache(maxsize=1)` for singleton semantics | Process-scoped consistency (ADR-0047 P3) |
| Provider must not import from other feature packages | Sibling isolation at the package level (ADR-0048 B5 extended) |
| Provider may import from `infrastructure.services` for shared infrastructure | Unidirectional flow preserved (ADR-0048 B1) |
| Provider must not be imported by infrastructure code | Unidirectional flow: infrastructure never imports from packages |
| Provider function must be a module-level function, not a class method | Consistency with infrastructure provider pattern |
| Provider function name must follow `get_<domain>_<thing>()` convention | Discoverability and grep-ability |

**Reference implementation:** `app/packages/access/common/providers.py` and `app/packages/access/sync/providers.py`.

### Standard 3: Infrastructure Provider Centralization

Infrastructure providers remain centralized in `app/infrastructure/services/providers.py`. Distributing providers to individual service modules (e.g., `infrastructure/clients/aws/providers.py`) is not permitted because:

1. **Single injection surface** (ADR-0048 B2) requires one location for all infrastructure providers. Distribution fragments this surface without reducing total code.
2. **Dependency graph visibility** — a single file makes the full composition graph inspectable and reviewable at a glance.
3. **Ceremony parity** — distribution still requires the same three-file edit (now spread across more directories), adding navigation cost without reducing edit count.

**Exceptions:** Infrastructure subsystems that are self-contained and have no cross-service dependencies may define module-level factory functions, but these are internal implementation details, not providers. They must not be exported through `infrastructure.services` and must be called only by the central provider that owns their lifecycle. Example: `build_google_directory_provider()` in `infrastructure/directory/factory.py` is a factory called by `get_directory_provider()`.

### Standard 4: DI Alias Ceremony

The three-file pattern for adding a new infrastructure service remains the canonical approach:

1. **`providers.py`** — Add the `@lru_cache(maxsize=1)` provider function.
2. **`dependencies.py`** — Add the `Annotated[T, Depends(get_X)]` alias.
3. **`__init__.py`** — Export both the provider function and the dependency alias.

This ceremony is retained because:

- It provides explicit traceability from HTTP handler → dependency alias → provider function → service constructor.
- It prevents accidental exposure of internal infrastructure types.
- It keeps the `__init__.py` as a curated public API surface.

**Ceremony rules:**

| # | Rule | Rationale |
|---|------|-----------|
| C1 | Every `@lru_cache` provider in `providers.py` must have a corresponding `Annotated` alias in `dependencies.py` | Completeness — route handlers should never import providers directly |
| C2 | Every alias in `dependencies.py` must be re-exported from `__init__.py` | Discoverability — `from infrastructure.services import XDep` is the canonical import |
| C3 | Every provider in `providers.py` must be re-exported from `__init__.py` | Non-HTTP contexts (jobs, startup, background tasks) import providers directly |
| C4 | Alias naming convention: `<ServiceType>Dep` (e.g., `StorageServiceDep`, `AWSClientsDep`) | Consistency and IDE completion |
| C5 | Provider naming convention: `get_<service_name>()` (e.g., `get_storage_service()`, `get_aws_clients()`) | Consistency with Python getter convention |

**Package-local providers do not follow this ceremony.** Feature packages have no obligation to create `dependencies.py` or alias files. Package-local providers are consumed directly by import within the package.

### Standard 5: Convenience Accessor Posture

Non-cached convenience accessor functions (functions that retrieve a specific provider instance from a registry rather than constructing one) are **permitted** in `providers.py` under the following conditions:

| Condition | Rationale |
|-----------|-----------|
| The accessor must not use `@lru_cache` | The underlying registry already manages instance lifecycle |
| The accessor must delegate to a cached provider (e.g., `get_platform_service()`) | No independent construction — it's a lookup, not a factory |
| The accessor must have a corresponding `Annotated` alias in `dependencies.py` | Same DI contract as cached providers |
| The accessor must be typed with the specific return type (using `cast` if needed) | Type safety for consumers |

**Current convenience accessors conforming to this standard:**

- `get_slack_provider()` → looks up from `get_platform_service()._registry`
- `get_teams_provider()` → looks up from `get_platform_service()._registry`
- `get_discord_provider()` → looks up from `get_platform_service()._registry`

**Accessors must not be created for services that can be obtained via direct provider calls.** The accessor pattern is reserved for registry-backed lookups where the identity of the provider is determined at runtime (e.g., platform provider registry). If a service is always the same concrete instance, use a standard `@lru_cache` provider.

### Standard 6: Provider Dependency Graph Shape

The provider dependency graph must follow these structural rules:

#### 6.1 Maximum Composition Depth

Provider composition must not exceed **three levels** of provider-to-provider dependency:

```
Level 0: Settings providers (get_aws_settings, get_slack_settings, ...)
Level 1: Client/service providers (get_aws_clients, get_slack_client, ...)
Level 2: Composed service providers (get_storage_service → get_aws_clients, ...)
Level 3: High-level service providers (get_audit_trail_service → get_storage_service, ...)
```

A provider at Level N may depend on providers at Level N-1 or below. A provider must not depend on a provider at the same level or above. If a composition would exceed depth 3, the design should be reviewed for excessive coupling.

#### 6.2 Dependency Direction

Provider dependencies must flow in one direction: higher-level providers depend on lower-level providers. Circular dependencies between providers are prohibited. The `@lru_cache` decorator ensures that circular calls would raise `RecursionError` at startup — this is a fail-fast safety net, not a design mechanism.

#### 6.3 Settings Provider Transition

During ADR-0055 dissolution, providers transition from calling `get_settings()` to calling domain-specific settings providers:

| Phase | Pattern | Example |
|-------|---------|---------|
| Current (pre-dissolution) | `settings = get_settings(); return X(settings.aws)` | `get_aws_clients()` |
| Phase 1 (dissolution) | `aws_settings = get_aws_settings(); return X(aws_settings=aws_settings)` | `get_aws_clients()` |
| Phase 3 (aggregator removed) | Same as Phase 1 — `get_settings()` no longer exists | `get_aws_clients()` |

This transition is mechanical and must not change provider composition depth or dependency direction.

#### 6.4 Current Provider Graph

```
Level 0 — Settings (after dissolution)
├── get_app_settings()
├── get_aws_settings()
├── get_slack_settings()
├── get_google_workspace_settings()
├── get_maxmind_settings()
├── get_server_settings()
├── get_idempotency_settings()
├── get_retry_settings()
├── get_notify_settings()
├── get_commands_settings()
├── get_platforms_settings()
├── get_directory_settings()
└── get_dev_settings()

Level 1 — Clients and Leaf Services
├── get_aws_clients() ← get_aws_settings()
├── get_google_workspace_clients() ← get_google_workspace_settings()
├── get_maxmind_client() ← get_maxmind_settings()
├── get_slack_client() ← get_slack_settings()
├── get_teams_client() ← get_platforms_settings()
├── get_discord_client() [no settings]
├── get_event_dispatcher() [no settings]
├── get_translation_service() [no settings]
├── get_identity_service() ← get_server_settings() (narrow slice)
├── get_jwks_manager() ← get_server_settings() (scalar extraction)
├── get_idempotency_service() ← get_idempotency_settings()
├── get_resilience_service() ← get_retry_settings()
├── get_command_service() ← get_commands_settings()
└── get_platform_service() ← get_platforms_settings()

Level 2 — Composed Services
├── get_storage_service() ← get_aws_clients()
├── get_notification_service() ← get_notify_settings(), get_idempotency_service(), get_resilience_service()
├── get_directory_provider() ← get_directory_settings(), get_google_workspace_clients()
├── get_slack_provider() ← get_platform_service() [convenience accessor]
├── get_teams_provider() ← get_platform_service() [convenience accessor]
└── get_discord_provider() ← get_platform_service() [convenience accessor]

Level 3 — High-Level Services
└── get_audit_trail_service() ← get_storage_service()
```

### Standard 7: Translation Helper Posture

The `t()` function in `providers.py` is a convenience wrapper around `get_translation_service()`. It is not a provider — it is a helper function that provides a safe, fallback-aware translation interface for use in command handlers and feature packages where injecting `TranslationServiceDep` is impractical (e.g., pluggy hook implementations, non-FastAPI contexts).

**Rules:**

| Rule | Rationale |
|------|-----------|
| `t()` must remain in `providers.py` alongside the translation provider it wraps | Colocation with the provider it delegates to |
| `t()` must be exported from `__init__.py` | Feature packages import via `from infrastructure.services import t` |
| `t()` must not use `@lru_cache` | Each call may have different arguments; the underlying service is already cached |
| `t()` must catch all exceptions and return the fallback value | Fail-safe for use in user-facing message construction |

## Alternatives Considered

1. Distribute infrastructure providers to their service modules:
   - Pros: Providers live next to the code they construct; smaller individual files.
   - Cons: Fragments the single injection surface (ADR-0048 B2). Developers must navigate to N directories to understand the full composition graph. The three-file ceremony is not reduced — it is spread across more locations. Import cycles become harder to prevent when provider modules import from sibling infrastructure modules.
   - Why not chosen: The composition graph is shallow (max depth 3) and the provider count is stable (16 cached + 3 accessors). Centralization's navigation cost is lower than distribution's fragmentation cost at this scale.

2. Eliminate the DI alias ceremony — convention-based aliases:
   - Pros: Each service module exports its own `XDep = Annotated[X, Depends(get_x)]`, eliminating `dependencies.py`.
   - Cons: Breaks the single-import convention (`from infrastructure.services import XDep`). Developers must know which infrastructure module owns which service to find the alias. No curated public API surface.
   - Why not chosen: The ceremony cost (three file edits per new service) is acceptable given the low rate of new infrastructure service additions. The curated `__init__.py` provides significant discoverability value.

3. Allow package-local providers to register in the central providers.py:
   - Pros: Single location for all providers; complete composition graph visibility.
   - Cons: Violates ownership-follows-code (ADR-0047 P2). Feature package lifecycle decisions would require infrastructure file changes. Package removal would require editing infrastructure files.
   - Why not chosen: Feature packages must own their entire lifecycle, including provider construction. Central registration creates a coupling that contradicts the package autonomy model.

4. Prohibit non-cached convenience accessors:
   - Pros: Every function in `providers.py` has consistent `@lru_cache` semantics.
   - Cons: Forces callers into verbose two-step patterns (`get_platform_service().get_provider("slack")`). Eliminates type-safe accessors that provide concrete return types instead of generic `PlatformProvider`.
   - Why not chosen: Convenience accessors add ergonomic value and type safety. The "not cached" nature is documented and intentional — the underlying registry manages lifecycle.

5. Prohibit wide injection without mandating constructor refactoring:
   - Pros: Simpler to implement — only provider code changes, not service constructors.
   - Cons: Providers would extract slices and pass them as kwargs while constructors still accept `Settings`. This creates a false narrow-slice appearance while the constructor contract remains wide.
   - Why not chosen: Narrow-slice enforcement must be end-to-end. Provider changes and constructor signature changes must happen together to maintain honesty in the dependency contract.

## Consequences

- Positive impacts:
  - Narrow-slice enforcement makes service dependencies explicit and testable. Test fixtures construct only the settings slice a service needs, not the full tree.
  - Package-local provider permission formalizes a proven pattern and gives feature packages full lifecycle autonomy over their services.
  - Centralized infrastructure providers preserve the single injection surface and make the composition graph inspectable.
  - Provider graph shape rules prevent unbounded composition depth and make startup ordering predictable.
  - The DI alias ceremony provides explicit traceability from HTTP handler to service constructor.
- Tradeoffs accepted:
  - The three-file ceremony for new infrastructure services is verbose. This is accepted because new infrastructure services are added infrequently (estimated 1-2 per quarter) and the traceability benefit outweighs the edit cost.
  - Infrastructure providers remain centralized, meaning `providers.py` will continue to grow. At 16 cached providers plus 3 accessors, the file is navigable. If the count exceeds 25 cached providers, this standard should be reassessed.
  - Package-local providers are not visible in the central composition graph. This is accepted because package-local services are consumed only within their package boundary.
- Risks introduced:
  - Constructor signature changes for narrow-slice enforcement may break existing tests. Mitigation: TDD approach — write failing tests with narrow signatures first, then refactor constructors.
  - Package-local providers may diverge from infrastructure patterns over time. Mitigation: Standard 2 rules govern structure; code review enforces consistency.
  - Convenience accessors may proliferate beyond the platform registry pattern. Mitigation: Standard 5 conditions restrict usage to registry-backed lookups only.
- Mitigations:
  - Narrow-slice enforcement is executed incrementally as part of ADR-0055 settings dissolution (Action 5e in the implementation plan).
  - Package-local provider pattern is validated by the access package reference implementation.
  - Provider graph shape is documented (Standard 6.4) and reviewable.

## Compliance and Boundaries

- Package/infrastructure boundary impact: Standard 2 explicitly permits and governs package-local providers, closing the gap identified in the decentralization analysis (ADR-0048 B2 gap). Standard 3 confirms infrastructure providers remain centralized. The boundary between package-local and infrastructure providers is clear: infrastructure providers are in `infrastructure/services/providers.py` and exported through `infrastructure/services/__init__.py`; package-local providers are in `packages/<feature>/*/providers.py` and never exported through infrastructure.
- Type boundary impact: Standard 1 enforces narrow-slice types at constructor boundaries. After ADR-0055 dissolution, providers pass domain-specific `BaseSettings` instances or scalar values, not aggregated settings objects. This aligns with ADR-0040 type boundaries.
- Startup/plugin registration impact: Standard 6 (provider graph shape) is compatible with ADR-0046 startup phase ordering. Settings providers (Level 0) are called during Phase 1 (Configuration). Client providers (Level 1) are called during Phase 2 (Client Construction). Composed and high-level providers (Levels 2-3) are called during Phase 3 (Service Wiring). Package-local providers that participate in startup warmup (ADR-0049 S6) are called during the plugin warmup sub-phase.
- Settings partitioning impact: Standard 1 and Standard 6.3 define the transition from `get_settings()` to domain-specific settings providers as part of ADR-0055 dissolution. After dissolution, `get_settings()` is removed and each provider calls the domain-specific settings provider it needs.
- Service contract impact: After ADR-0077 Protocol migration, provider return type annotations for Category A services must use the Protocol type, not the concrete implementation class. The `Annotated[..., Depends(...)]` alias in `dependencies.py` must likewise reference the Protocol type. See ADR-0077 Standard 2 (Protocol Contract Pattern) for the canonical pattern and Standard 5 for migration sequencing.

## Best-Practice Revalidation

- Revalidation date: 2026-04-29
- Sources rechecked:
  - FastAPI Dependency Injection documentation: `Annotated[T, Depends(...)]` pattern, dependency overrides for testing, sub-dependencies.
  - Python 3.12+ `functools.lru_cache(maxsize=1)` for process-scoped singletons.
  - Twelve-Factor App: Factor IV (Backing Services) — treat backing services as attached resources, provisioned via configuration.
  - Martin Fowler, "Inversion of Control Containers and the Dependency Injection pattern" — constructor injection as the preferred DI mechanism.
  - pydantic-settings v2 documentation — independent `BaseSettings` per domain.
- Alignment summary:
  - Centralized provider file aligns with FastAPI's documented pattern of a single dependency injection module.
  - `@lru_cache(maxsize=1)` singleton pattern is the Python standard library mechanism for process-scoped instances.
  - Constructor-only injection (Standard 1) aligns with Fowler's constructor injection recommendation.
  - Narrow-slice settings align with Factor IV's resource-specific configuration binding.
  - Package-local providers align with Python package autonomy conventions.
- Intentional deviations: None.

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: New Tier-2 pattern implementing ADR-0048 dependency composition rules and governing the provider layer post-ADR-0055 settings dissolution. Supersedes ADR-0012 (Provider Discovery — rigid load ordering replaced by ADR-0049 pluggy-based discovery). ADR-0025 (Interaction Providers Concept) is **not** superseded by this record — ADR-0025 mixed provider-layer governance (covered here) with the interaction provider domain concept (HTTP-first interaction pattern, capability abstraction, channel isolation). The domain concept portion is governed by ADR-0059 (Interaction Provider and Feature Integration Standard, Wave 4), which will supersede ADR-0025 along with ADR-0018 and ADR-0028.
- Follow-up actions:
  - Mark ADR-0012 as `status: Superseded` and add `superseded_by: [ADR-0056]`.
  - Execute narrow-slice enforcement as part of settings dissolution Action 5e.
  - Review provider count after dissolution completes; reassess centralization if count exceeds 25.

## Source References

1. Source title: FastAPI — Dependencies
   URL: https://fastapi.tiangolo.com/tutorial/dependencies/
   Access date: 2026-04-29
   Key takeaway: `Annotated[T, Depends(callable)]` is the canonical DI mechanism. Sub-dependencies compose automatically. `dependency_overrides` enables test-time replacement.

2. Source title: Python 3.12 functools.lru_cache
   URL: https://docs.python.org/3.12/library/functools.html#functools.lru_cache
   Access date: 2026-04-29
   Key takeaway: `@lru_cache(maxsize=1)` ensures a single cached return value — suitable for process-scoped singletons when combined with deterministic input (no arguments).

3. Source title: Twelve-Factor App — IV. Backing Services
   URL: https://12factor.net/backing-services
   Access date: 2026-04-29
   Key takeaway: Backing services are attached resources, each configured independently. Aligns with narrow-slice injection — each service receives only its resource configuration.

4. Source title: Martin Fowler — Inversion of Control Containers and the Dependency Injection Pattern
   URL: https://martinfowler.com/articles/injection.html
   Access date: 2026-04-29
   Key takeaway: Constructor injection makes dependencies explicit, inspectable, and overridable for testing. Preferred over setter injection and interface injection.

5. Source title: pydantic-settings v2 — Settings Management
   URL: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
   Access date: 2026-04-29
   Key takeaway: Each `BaseSettings` class independently loads from environment. Multiple independent settings classes per process is the intended usage pattern.
