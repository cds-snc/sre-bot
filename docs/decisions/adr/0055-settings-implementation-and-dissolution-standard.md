---
adr_id: ADR-0055
title: "Settings Implementation and Dissolution Standard"
status: Accepted
decision_type: Standard
tier: Tier-2
primary_domain: Configuration and Secrets
secondary_domains:
  - Dependency and Composition
  - Package and Plugin Architecture
owners:
  - SRE Team
date_created: 2026-04-29
last_updated: 2026-04-29
last_reviewed: 2026-04-29
next_review_due: 2026-08-27
constrained_by:
  - ADR-0044
  - ADR-0045
  - ADR-0046
  - ADR-0047
impacts:
  - ADR-0056
supersedes:
  - ADR-0008
superseded_by: []
review_state: current
related_records:
  - ADR-0040
  - ADR-0048
  - ADR-0049
  - ADR-0052
  - ADR-0053
related_packages:
  - app/packages/access
---

# Settings Implementation and Dissolution Standard

## Context

- Problem statement: `app/infrastructure/configuration/settings.py` defines a single `Settings(BaseSettings)` root that nests 22 sub-settings classes, each of which independently inherits from `BaseSettings`. The `Settings.__init__` manually pre-instantiates every sub-class via a `settings_map` dict to work around pydantic-settings v2's double-initialization warning for `BaseSettings`-in-`BaseSettings`. This aggregator pattern violates ADR-0047 Principles 1 (single source per domain), 2 (ownership follows code), and 4 (narrow-slice injection). It also violates pydantic-settings v2 best practices: nested settings sections should use `BaseModel`, not `BaseSettings`. The aggregator forces every feature and integration to register in one infrastructure-owned file, inflates test surface, and creates a single point of failure where one invalid environment variable blocks all 22 domains.
- Business/operational drivers:
  - Dissolve the centralized `Settings` aggregator into independent, domain-owned singleton settings classes.
  - Enforce correct pydantic-settings v2 type boundaries: `BaseSettings` for root-level env-sourced classes, `BaseModel` for nested sections.
  - Establish a three-way ownership split for settings classes across infrastructure, integrations, and feature packages.
  - Define a transitional posture for feature settings that cannot yet migrate because their owning module is still in `app/modules/`.
  - Subsume and supersede ADR-0008 (JSON blob override pattern) as a section within this broader standard.
- Constraints:
  - All settings must be validated and frozen before traffic is accepted (ADR-0045 P4, ADR-0046 Inv 1, ADR-0047 P3).
  - Settings must be injectable through the DI system (ADR-0045 P2, ADR-0047 P4).
  - Environment-variable-first configuration (ADR-0047 P5).
  - Feature package settings must live in their package directories when the package exists in `app/packages/` (ADR-0047 P2).
  - No import-time side effects in package init files (ADR-0049 S8).
  - Type boundary selection follows ADR-0040 (pending promotion to ADR-0065): `BaseSettings` for env-var-sourced config, `BaseModel` for nested sections, `@dataclass(frozen=True)` for runtime config documents.
- Non-goals:
  - This record does not define the provider composition model (delegated to ADR-0056).
  - This record does not define specific environment variable names or prefixes for individual settings classes.
  - This record does not define runtime configuration document loading patterns (loader protocols, cache invalidation, document schema). Those are governed by the runtime config concept in each package.
  - This record does not prescribe the migration schedule for individual feature settings. Each migration is tracked by its own Tier-5 ADR.

## Decision

- Chosen approach: Dissolve the `Settings` aggregator into independent singleton settings classes with a three-way ownership model, enforcing pydantic-settings v2 type boundaries and preserving the JSON blob override pattern as a documented operational capability.
- Why this approach: The aggregator is explicitly identified as transitional in the now-superseded ADR-0007 ("End state: Settings dissolves entirely"). ADR-0047 mandates this change through all five principles. The `app/packages/access/common/settings.py` reference implementation demonstrates the target pattern is proven and deployed.

### Standard 1: Independent Singleton per Settings Domain

Each settings domain must have its own `BaseSettings` subclass with its own `@lru_cache(maxsize=1)` provider function. Settings classes must not be nested inside other `BaseSettings` classes. Each singleton provider is the sole constructor for its settings class.

```python
# Correct: independent singleton
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class AwsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AWS_", env_file=".env", extra="ignore")
    AWS_REGION: str = "ca-central-1"
    # ...

@lru_cache(maxsize=1)
def get_aws_settings() -> AwsSettings:
    return AwsSettings()
```

```python
# Prohibited: BaseSettings nested inside another BaseSettings
class Settings(BaseSettings):
    aws: AwsSettings  # ← AwsSettings is also BaseSettings — WRONG
```

### Standard 2: BaseSettings-in-BaseSettings Prohibition

Nested settings sections within a `BaseSettings` class must use `BaseModel`, never `BaseSettings`. The `BaseSettings`-in-`BaseSettings` pattern triggers pydantic-settings v2 double-initialization warnings, requires manual `__init__` workarounds, and violates the principle that each `BaseSettings` class independently manages its own environment variable source.

| Type | Use case | Example |
|------|----------|---------|
| `BaseSettings` | Root-level settings class that reads from environment variables | `AccessSettings(BaseSettings)`, `AwsSettings(BaseSettings)` |
| `BaseModel` | Nested section within a `BaseSettings` class, populated via `env_nested_delimiter` | `AccessSyncSettings(BaseModel)`, `AccessConfigSettings(BaseModel)` |
| `@dataclass(frozen=True)` | Runtime configuration documents loaded from external sources (DynamoDB, S3, bundles) | `AccessRuntimeConfig` |

This type boundary selection is consistent with ADR-0040. When ADR-0065 is authored, it will generalize these rules across all type boundaries.

### Standard 3: Three-Way Settings Ownership Split

Settings classes are owned by the layer that owns the code they configure:

| Category | Location | Ownership rule | Example classes |
|----------|----------|---------------|-----------------|
| Integration settings | `infrastructure/configuration/integrations/` | Stays in infrastructure. Each class becomes an independent singleton. | `SlackSettings`, `AwsSettings`, `GoogleWorkspaceSettings` |
| Infrastructure settings | `infrastructure/configuration/infrastructure/` | Stays in infrastructure. Each class becomes an independent singleton. | `ServerSettings`, `IdempotencySettings`, `RetrySettings` |
| Feature settings (migrated packages) | `packages/<feature>/settings.py` or `packages/<feature>/common/settings.py` | Owned by the feature package. | `AccessSettings` in `packages/access/common/settings.py` |
| Feature settings (legacy modules) | `infrastructure/configuration/features/` | Transitional — remains in infrastructure until the owning module migrates from `app/modules/` to `app/packages/`. See Standard 4. | `GroupsFeatureSettings`, `CommandsSettings` |
| App-level settings | `infrastructure/configuration/app.py` | Minimal root: `PREFIX`, `LOG_LEVEL`, `GIT_SHA`. | `AppSettings` |

**Ownership Decision Framework for Ambiguous Cases:**

When a settings class does not map cleanly to one of the five categories above, apply this tiebreaker sequence:

1. **Reader-owns rule:** The owner of the code that _reads_ the setting owns the settings class. If only feature code reads the setting, it is a feature setting. If only infrastructure code reads it, it is an infrastructure setting.
2. **If both layers read the setting:** The infrastructure layer owns the canonical settings class, and the feature layer receives the value via dependency injection. The feature must not import the settings class directly.
3. **If the setting configures a cross-cutting capability** (e.g., retry policy, circuit breaker threshold) that is _consumed_ by infrastructure but _parameterized_ by a feature: the infrastructure layer owns the default in its settings class; the feature may override the specific value through its own settings field, which the infrastructure layer accepts as a narrow-slice injection parameter.

### Standard 4: Transitional Posture for Legacy Feature Settings

Feature settings classes that belong to modules still in `app/modules/` remain in `infrastructure/configuration/features/` during the transition period. Each such class:

1. Must become an independent singleton with its own `@lru_cache(maxsize=1)` provider (no longer accessed via the `Settings` aggregator).
2. Must not be moved to `app/packages/` until the owning module has migrated.
3. Must have its migration tracked by a Tier-5 ADR with explicit retirement criteria and a target date.
4. May be temporarily duplicated (per ADR-0047 P1 migration exception) only when a governing Tier-5 ADR exists.

The `Settings` aggregator itself follows a deprecation sequence:

| Phase | Description | Breaking? |
|-------|-------------|-----------|
| Phase 1 | Each domain settings class gets its own singleton provider. `Settings` aggregator delegates to domain singletons internally. | No — backward compatible |
| Phase 2 | All consumers migrated to domain-specific providers. `Settings` aggregator deprecated with runtime warning. | No — backward compatible |
| Phase 3 | `Settings` aggregator and `SettingsDep` removed. | Yes — internal breaking change |

### Standard 5: Bootstrap Settings vs. Runtime Configuration Documents

This standard distinguishes two configuration concepts:

| Concept | Source | Type | Lifecycle | Example |
|---------|--------|------|-----------|---------|
| **Bootstrap settings** | Environment variables (`.env`, SSM→env, ECS task definition) | `BaseSettings` | Loaded once at startup, frozen for process lifetime | `AccessSettings`, `AwsSettings`, `ServerSettings` |
| **Runtime config documents** | External sources (DynamoDB, S3 bundles, inline JSON) | `@dataclass(frozen=True)` loaded via Protocol-based loader | Loaded at startup (or on-demand with caching), may be refreshed | `AccessRuntimeConfig` |

ADR-0047 Principle 5 (environment-variable-first) applies to **bootstrap settings** only. Runtime config documents are a separate concept with their own governance:

- Bootstrap settings for a runtime config loader (which source, which ref, refresh interval) are themselves env-var-sourced `BaseModel` sections within the feature's `BaseSettings`. Example: `AccessConfigSettings` (a `BaseModel`) within `AccessSettings` (a `BaseSettings`).
- The runtime config document itself is not env-var-sourced. It is loaded by a Protocol-based loader and validated at load time.
- This two-layer pattern (env-var bootstrap → loader → typed document) is the canonical approach. It does not violate ADR-0047 P5 because the bootstrap layer is env-var-first; the document layer is an application-level data concern, not a configuration source concern.

### Standard 6: Source Ordering and Override Mechanics

This standard supersedes ADR-0008 (Settings JSON Blob Override Pattern) and incorporates its rules.

#### 6.1 Environment Variable Precedence

For all `BaseSettings` classes, the source precedence order is (highest to lowest):

1. Environment variables set in the OS environment
2. `.env` file entries
3. Default values defined in the settings class

This is the pydantic-settings v2 default behavior. No custom source ordering is permitted.

#### 6.2 JSON Blob Override Pattern

When a `BaseSettings` class uses `env_nested_delimiter` with nested `BaseModel` fields, pydantic-settings v2 automatically supports JSON blob environment variables. This is a built-in capability, not a custom implementation.

For a settings class with `env_prefix="ACCESS_"` and a field `sync: AccessSyncSettings`:
- Flat vars: `ACCESS_SYNC_ENABLED=true`, `ACCESS_SYNC_JOB_TTL_SECONDS=3600`
- JSON blob var: `ACCESS_SYNC='{"enabled": true, "job_ttl_seconds": 3600}'`

**Flat vars take precedence over JSON blob values** for any key that appears in both sources. This makes the JSON blob suitable as a base configuration and flat vars as targeted overrides.

#### 6.3 JSON Blob Usage Rules

| Context | Permitted? | Rationale |
|---------|-----------|-----------|
| Local development (`.env` files) | Yes | Bulk initialization convenience |
| CI test matrix overrides | Yes | Compact env block in CI YAML |
| Emergency operational override | Yes (with change-management approval) | Temporary; flat vars are canonical |
| SSM parameters written by `entry.sh` | No | Production uses flat vars exclusively |
| Terraform `environment` blocks in ECS task definitions | No | Production uses flat vars exclusively |
| Production parameter stores | No | Production uses flat vars exclusively |

#### 6.4 JSON Blob Detection Logging

At startup, if a JSON blob variable is detected in `os.environ`, the settings class should emit a structured `info` log event. This makes operational use visible in CloudWatch without blocking startup.

### Standard 7: AppSettings Extraction

Application-level fields (`PREFIX`, `LOG_LEVEL`, `GIT_SHA`) must be extracted from the `Settings` aggregator into a minimal `AppSettings(BaseSettings)` class with its own singleton provider.

```python
class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    PREFIX: str = ""
    LOG_LEVEL: str = "INFO"
    GIT_SHA: str = "Unknown"

    @property
    def is_production(self) -> bool:
        return not bool(self.PREFIX)

@lru_cache(maxsize=1)
def get_app_settings() -> AppSettings:
    return AppSettings()
```

### Standard 8: Settings Class Configuration Requirements

All `BaseSettings` classes must include the following `SettingsConfigDict` entries:

| Field | Required value | Rationale |
|-------|---------------|-----------|
| `env_file` | `".env"` | Ensures `.env` file loading for local development (ADR-0052 delivery model) |
| `extra` | `"ignore"` | Prevents startup failure from unrelated environment variables |

Additional fields (`env_prefix`, `env_nested_delimiter`, `case_sensitive`, `env_nested_max_split`) are class-specific and determined by the settings domain's environment variable naming convention.

## Alternatives Considered

1. Retain the Settings aggregator with BaseModel-only nesting:
   - Pros: Minimal code change; fixes the pydantic-settings v2 warning.
   - Cons: Preserves the monolithic single-point-of-failure. Feature settings still registered in infrastructure. Violates ADR-0047 P1 and P2.
   - Why not chosen: Fixes the symptom (type mismatch) but not the root cause (centralized ownership).

2. Split into ADR-0055 (dissolution) + ADR-0070 (source ordering):
   - Pros: Narrower scope per ADR.
   - Cons: Source ordering is a subsection of the dissolution standard, not a peer concern. ADR-0047 already declares `impacts: [ADR-0055]`; splitting would require a new ID not in the dependency graph.
   - Why not chosen: Expansion keeps the dependency graph intact and avoids an unnecessary new ADR.

3. Migrate all feature settings to packages immediately:
   - Pros: Clean end state achieved in one step.
   - Cons: Feature modules in `app/modules/` cannot be migrated without broader refactoring. Forced migration creates circular import risk and ownership ambiguity.
   - Why not chosen: Incremental migration with transitional posture is safer and independently deployable.

## Consequences

- Positive impacts:
  - Each settings domain validates independently at startup. A misconfigured integration setting no longer blocks unrelated feature settings from loading.
  - Test fixtures become narrow: tests needing AWS settings construct only `AwsSettings`, not the full tree.
  - Feature package settings live alongside their business logic, making ownership explicit.
  - The pydantic-settings v2 `BaseSettings`-in-`BaseSettings` workaround is eliminated.
  - JSON blob override pattern is preserved and documented as an operational capability.
- Tradeoffs accepted:
  - Multiple `@lru_cache` providers instead of one. The configuration phase (ADR-0046 Inv 2) now calls N providers instead of one. This is an acceptable startup cost for the isolation benefit.
  - The transitional phase requires maintaining both the aggregator (as a thin wrapper) and domain singletons. This adds temporary complexity.
  - Each independent `BaseSettings` reads from the same `.env` file independently. This is correct behavior (same source, same values) but is a change from the single-load pattern.
- Risks introduced:
  - Environment variable loading order changes when settings classes are independent. Mitigation: each `BaseSettings` reads from `.env` independently — same source, same values. `entry.sh` writes all params to `.env` before Python starts.
  - Circular imports during provider reorganization. Mitigation: maintain unidirectional import flow. Providers import settings, not the reverse.
  - Feature settings migration creates orphaned env vars. Mitigation: track via Tier-5 migration ADRs with explicit retirement criteria.
- Mitigations:
  - Incremental dissolution (Standard 4 phases) ensures each step is independently deployable and testable.
  - Existing test suite validates settings behavior at each phase.
  - SSM parameter organization is unchanged — `entry.sh` writes all params to `.env` before Python starts.

## Compliance and Boundaries

- Package/infrastructure boundary impact: Standard 3 directly governs where settings classes live. Feature settings migrate to `app/packages/<feature>/` when the owning module migrates. Infrastructure and integration settings remain in `app/infrastructure/configuration/`.
- Type boundary impact: Standard 2 enforces `BaseSettings` vs `BaseModel` vs `@dataclass(frozen=True)` boundaries. Consistent with ADR-0040; will be generalized by ADR-0065.
- Startup/plugin registration impact: Standard 1 (independent singletons) aligns with ADR-0049 Standard 6 (fail-fast warmup) — each feature package validates its own settings during `startup_warmup`. Standard 5 (bootstrap vs runtime config) preserves the startup-phase ordering from ADR-0046 Inv 2.
- Settings partitioning impact: This is the authoritative implementation standard for ADR-0047's five configuration governance principles.

## Best-Practice Revalidation

- Revalidation date: 2026-04-29
- Sources rechecked:
  - Pydantic Settings V2 documentation: BaseSettings nesting, env_nested_delimiter, SettingsConfigDict, field value priority.
  - Twelve-Factor App: Factor III (Config — store config in the environment).
  - FastAPI dependency injection documentation: Annotated + Depends for settings.
  - Python 3.12+ functools.lru_cache singleton pattern.
- Alignment summary:
  - Independent singleton per domain aligns with pydantic-settings v2's intended one-`BaseSettings`-per-domain model.
  - `BaseModel` for nested sections is the documented pydantic-settings v2 recommendation.
  - Environment-variable-first aligns with Factor III.
  - `@lru_cache(maxsize=1)` singleton aligns with the Python standard library caching pattern.
  - JSON blob override behavior is a built-in pydantic-settings v2 capability, not a custom implementation.
- Intentional deviations: None.

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: New Tier-2 standard implementing ADR-0047 configuration governance principles. Supersedes ADR-0008 JSON blob override pattern. Defines dissolution plan for the Settings aggregator antipattern.
- Follow-up actions:
  - Mark ADR-0008 as `status: Superseded` and add `superseded_by: [ADR-0055]`.
  - Author ADR-0056 (Provider Discovery and Composition Standard) which depends on the dissolution model defined here.
  - Create Tier-5 migration ADRs for each feature settings migration from `infrastructure/configuration/features/` to `packages/<feature>/settings.py`.

## Source References

1. Source title: Pydantic Settings V2 — Parsing Environment Variable Values
   - URL: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
   - Publisher/maintainer: Pydantic project
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Confirms BaseSettings nesting rules, env_nested_delimiter behavior, JSON blob support, and field value priority.

2. Source title: Twelve-Factor App — Config
   - URL: https://12factor.net/config
   - Publisher/maintainer: 12factor contributors
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Factor III requires configuration stored in environment variables. Underpins Standard 6 source ordering.

3. Source title: FastAPI Dependency Injection Documentation
   - URL: https://fastapi.tiangolo.com/tutorial/dependencies/
   - Publisher/maintainer: Sebastián Ramírez / FastAPI
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Confirms Annotated + Depends pattern for settings injection.

4. Source title: ADR-0008 (Legacy — Settings JSON Blob Override Pattern)
   - URL: docs/decisions/adr/0008-settings-json-blob-override.md
   - Publisher/maintainer: SRE Team
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Source record being superseded. JSON blob rules incorporated into Standard 6.

5. Source title: Infrastructure Configuration & Services Decentralization Analysis
   - URL: tmp/infrastructure-configuration-and-services-decentralization-analysis-2026-04-28.md
   - Publisher/maintainer: SRE Team
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Technical analysis identifying the Settings aggregator antipattern, boundary violations, and dissolution plan.

6. Source title: app/packages/access/common/settings.py (Reference Implementation)
   - URL: app/packages/access/common/settings.py
   - Publisher/maintainer: SRE Team
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Canonical example of the target pattern — independent BaseSettings with BaseModel nested sections, @lru_cache singleton, env_nested_delimiter.

## Implementation Guidance

- Required changes:
  - Mark ADR-0008 as `status: Superseded` and add `superseded_by: [ADR-0055]`.
  - Extract `AppSettings(BaseSettings)` for `PREFIX`, `LOG_LEVEL`, `GIT_SHA` with its own `@lru_cache` provider.
  - Make each infrastructure and integration settings class an independent singleton with its own `@lru_cache` provider.
  - Update providers that currently call `get_settings()` to call domain-specific settings providers.
  - Refactor service constructors that accept the full `Settings` object to accept narrow slices.
  - Fix boundary violations (direct `Settings` imports in infrastructure modules).
  - Deprecate and eventually remove the `Settings` aggregator.
- Validation and quality gates:
  - Each dissolution step must pass: `mypy`, `flake8`, `black --check .`, `pytest app/tests --ignore=app/tests/smoke`.
  - Each step must be independently deployable — no step may break existing consumers.
  - ADR-0051 taxonomy check: confirm this is a Tier-2 Standard with implementation guidance, not Tier-1 Principle.
  - Metadata completeness check: all 18 fields populated.
- Test strategy and acceptance criteria impact:
  - Each new singleton settings provider must have a unit test confirming it loads from environment variables and validates correctly.
  - Existing tests that construct `Settings()` must continue working during the transitional phase (Settings delegates to domain singletons).
  - After aggregator removal, tests must use domain-specific settings constructors.

## Change Log

- 2026-04-29: Created canonical Tier-2 settings implementation standard. Supersedes ADR-0008. Defines eight standards for settings dissolution, type boundaries, ownership split, transitional posture, bootstrap vs runtime config, source ordering, AppSettings extraction, and configuration requirements. Scope expanded from original "Configuration Source Ordering and Overrides Standard" to cover full settings dissolution per Action 1a decision.
