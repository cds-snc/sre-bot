---
adr_id: ADR-0047
title: "Configuration and Settings Governance Canonical Model"
status: Accepted
decision_type: Principle
tier: Tier-1
primary_domain: Configuration and Secrets
secondary_domains:
  - Dependency and Composition
  - Runtime and Lifecycle
owners:
  - SRE Team
date_created: 2026-04-28
last_updated: 2026-04-28
last_reviewed: 2026-04-28
next_review_due: 2026-08-26
constrained_by:
  - ADR-0044
  - ADR-0045
impacts:
  - ADR-0055
  - ADR-0056
  - ADR-0066
supersedes:
  - ADR-0002
  - ADR-0007
  - ADR-0010
superseded_by: []
review_state: current
related_records:
  - ADR-0044
  - ADR-0045
  - ADR-0046
related_packages:
  - app/packages/access
---

# Configuration and Settings Governance Canonical Model

## Context

- Problem statement: Configuration governance was fragmented across three legacy ADRs: ADR-0002 (Configuration Management) defined the settings singleton and DI consumption pattern, ADR-0007 (Partitioned Settings Model) defined the partitioning strategy and migration path, and ADR-0010 (Settings Singleton Pattern) defined the `@lru_cache` singleton mechanism. All three contained implementation-specific code examples and library-specific patterns, creating Tier-1 scope leakage. The overlap produced conflicting guidance about where configuration belongs, how services consume it, and what constitutes the canonical access pattern.
- Business/operational drivers:
  - Establish a single Tier-1 principle record for configuration governance that constrains all downstream implementation standards.
  - Define clear ownership boundaries for where configuration classes live and who may modify them.
  - Prevent configuration coupling between feature packages and infrastructure layers.
  - Support the ongoing migration from centralized settings aggregator to partitioned domain-owned settings.
- Constraints:
  - Configuration must be validated and frozen before traffic is accepted (ADR-0045 Principle 4, ADR-0046 Invariant 1).
  - Configuration must be injectable through the DI system (ADR-0045 Principle 2).
  - Pydantic-settings is the validation framework; BaseSettings for root-level, BaseModel for nested sections.
  - ECS deployment model: one settings instance per task, immutable after startup.
- Non-goals:
  - This record does not define specific settings class structures, field names, or environment variable conventions.
  - This record does not define the SSM/Secrets Manager migration path (delegated to Tier-5 ADRs).
  - This record does not prescribe code-level patterns for singleton providers or dependency aliases.

## Decision

- Chosen approach: Consolidate configuration governance into one Tier-1 principle that defines configuration invariants and ownership boundaries without prescribing implementation patterns.
- Why this approach: Separating configuration principles from implementation patterns allows the partitioning strategy and provider mechanisms to evolve at Tier-2 without requiring Tier-1 amendments.

### Principle 1: Single Source of Truth per Configuration Domain

Each configuration domain (infrastructure credentials, feature settings, platform parameters) must have exactly one authoritative settings class. No configuration key may be defined in more than one settings class in steady state. Duplication creates ownership ambiguity and silent override risk.

**Migration exception:** Temporary key duplication is permitted during active migration from centralized to partitioned settings, provided the duplication is governed by a Tier-5 migration ADR with explicit retirement criteria and a target retirement date. The duplicating PR must reference the governing Tier-5 ADR. Duplication that exists without a governing migration record is non-compliant.

### Principle 2: Configuration Ownership Follows Code Ownership

Infrastructure configuration classes belong in the infrastructure layer. Feature package configuration classes belong in their respective package directories. Feature packages must not modify infrastructure configuration files to register their settings. Infrastructure configuration must not contain feature-specific settings.

### Principle 3: Singleton Lifecycle with Startup Validation

Each configuration class must be instantiated exactly once per process, validated at instantiation time, and cached for the process lifetime. Invalid configuration must terminate startup immediately (constrained by ADR-0046 Invariant 3). Configuration must be immutable after validation.

### Principle 4: Narrow Slice Injection

Services must receive the narrowest configuration slice they need, not the full configuration tree. This reduces coupling, minimizes test fixture size, and makes service dependencies explicit. The injection boundary (provider layer) is responsible for extracting and passing the appropriate slice.

### Principle 5: Environment-Variable-First Configuration

All configuration must be loadable from environment variables as the primary source. File-based configuration (`.env` files) is a deployment convenience, not an architectural dependency. The application must function correctly when all configuration is provided solely through environment variables.

## Alternatives Considered

1. Retain three separate configuration ADRs with cross-references:
   - Pros: Smaller individual records; each addresses one aspect.
   - Cons: Overlapping authority creates contradiction risk; developers must consult three records.
   - Why not chosen: Consolidation eliminates duplication.
2. Define configuration patterns (singleton mechanism, alias conventions) at Tier-1:
   - Pros: Complete guidance in one record.
   - Cons: Implementation changes (e.g., replacing `@lru_cache` with a different mechanism) would force Tier-1 amendments.
   - Why not chosen: Implementation patterns belong in Tier-2 standards (ADR-0055).

## Consequences

- Positive impacts:
  - Single configuration governance record eliminates contradictions between ADR-0002, ADR-0007, and ADR-0010.
  - Ownership boundaries prevent feature-infrastructure coupling.
  - Narrow-slice injection reduces test surface and makes dependencies explicit.
- Tradeoffs accepted:
  - Developers must consult both this Tier-1 record and Tier-2 standards for actionable configuration patterns.
  - The migration from centralized settings aggregator to partitioned model is governed by this principle but executed through Tier-2 and Tier-5 records.
- Risks introduced:
  - The "no duplicate keys" principle may create friction during migration when legacy and new settings coexist temporarily.
- Mitigations:
  - Temporary duplication during migration is documented in Tier-5 migration ADRs with explicit retirement criteria.
  - Each migration step is atomic and independently deployable.

## Compliance and Boundaries

- Package/infrastructure boundary impact: Principle 2 (ownership follows code ownership) directly governs the boundary between `app/infrastructure/configuration/` and `app/packages/<name>/settings.py`.
- Type boundary impact: Configuration classes use Pydantic BaseSettings/BaseModel; type boundary rules deferred to ADR-0065.
- Startup/plugin registration impact: Principle 3 (startup validation) aligns with ADR-0046 Invariant 1 (configuration phase first) and ADR-0049 (startup warmup).
- Settings partitioning impact: Principles 1 and 2 are the governing constraints for all partitioning decisions.

## Best-Practice Revalidation

- Revalidation date: 2026-04-28
- Sources rechecked:
  - Twelve-Factor App: Factor III (Config — store config in the environment).
  - Pydantic Settings V2 documentation (BaseSettings, SettingsConfigDict, env_prefix).
  - FastAPI dependency injection documentation (Annotated + Depends pattern for settings).
  - Python 3.12+ typing conventions for configuration classes.
- Alignment summary:
  - Environment-variable-first configuration directly implements Factor III.
  - Singleton lifecycle aligns with pydantic-settings validation-on-instantiation pattern.
  - Narrow-slice injection aligns with FastAPI's dependency injection philosophy.
- Intentional deviations: None.

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: Consolidates ADR-0002, ADR-0007, and ADR-0010 into one configuration governance principle with no implementation leakage.
- Follow-up actions:
  - Mark ADR-0002, ADR-0007, and ADR-0010 as superseded with `superseded_by: [ADR-0047]`.
  - Ensure ADR-0055 references this record in `constrained_by`.

## Source References

1. Source title: Twelve-Factor App — Config
   - URL: https://12factor.net/config
   - Publisher/maintainer: 12factor contributors
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Factor III requires configuration stored in environment variables, not code.
2. Source title: Pydantic Settings V2 Documentation
   - URL: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
   - Publisher/maintainer: Pydantic project
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Confirms validation-on-instantiation, env_prefix, and BaseSettings patterns.
3. Source title: ADR-0002, ADR-0007, ADR-0010 (Legacy)
   - URL: docs/decisions/adr/
   - Publisher/maintainer: SRE Team
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Source records being consolidated; configuration principles extracted and implementation details removed.

## Implementation Guidance

- Required changes:
  - Mark ADR-0002, ADR-0007, ADR-0010 as `status: Superseded` and add `superseded_by: [ADR-0047]`.
  - Ensure downstream standards reference this record in `constrained_by`.
- Validation and quality gates:
  - ADR-0051 taxonomy check: confirm no implementation-level code examples in this record.
  - Metadata completeness check: all 18 fields populated.
- Test strategy and acceptance criteria impact:
  - No direct test changes; configuration principles are validated through downstream standard compliance.

## Change Log

- 2026-04-28: Added migration exception clause to Principle 1, permitting temporary key duplication when governed by a Tier-5 migration ADR. Resolves false non-compliance identified in challenge review.
- 2026-04-28: Created canonical Tier-1 configuration governance principle; supersedes ADR-0002, ADR-0007, ADR-0010. Three source records consolidated into five configuration principles with no implementation detail.
