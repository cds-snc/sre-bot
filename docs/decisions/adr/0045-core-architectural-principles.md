---
adr_id: ADR-0045
title: "Core Architectural Principles (Canonical Rewrite)"
status: Accepted
decision_type: Principle
tier: Tier-1
primary_domain: Dependency and Composition
secondary_domains:
  - Runtime and Lifecycle
  - Security and Access Control
  - Observability and Operations
owners:
  - SRE Team
date_created: 2026-04-28
last_updated: 2026-04-28
last_reviewed: 2026-04-28
next_review_due: 2026-08-26
constrained_by:
  - ADR-0044
impacts:
  - ADR-0047
  - ADR-0048
  - ADR-0049
  - ADR-0050
  - ADR-0065
supersedes:
  - ADR-0001
superseded_by: []
review_state: current
related_records:
  - ADR-0044
  - ADR-0046
  - ADR-0047
  - ADR-0048
related_packages: []
---

# Core Architectural Principles (Canonical Rewrite)

## Context

- Problem statement: The prior ADR-0001 mixed foundational principles with implementation-specific examples (code snippets, library usage patterns, async migration guidance). This caused Tier-1 scope leakage: downstream ADRs inherited both principle authority and implementation detail from a single record, making it unclear which constraints were foundational and which were refinable at lower tiers.
- Business/operational drivers:
  - Establish a clean Tier-1 principle record that constrains all downstream standards and patterns without dictating implementation.
  - Support reliable multi-task ECS deployment with strict boundaries between principle and implementation.
  - Provide a stable foundation that can evolve independently of specific library versions or API patterns.
- Constraints:
  - Python 3.12+ runtime target.
  - FastAPI as the web framework.
  - Multi-task ECS deployment with no shared in-memory state across tasks.
  - All implementation specifics (code examples, library-specific patterns, migration guidance) must be delegated to Tier-2 standards.
- Non-goals:
  - This record does not prescribe specific library versions, API patterns, or code-level conventions.
  - This record does not define async migration strategy or sync/async handler selection criteria.

## Decision

- Chosen approach: Establish five foundational architectural principles as the governing constraints for all downstream ADRs, standards, and patterns.
- Why this approach: Separating principles from implementation allows Tier-2 standards to evolve (e.g., new async libraries, new DI frameworks) without requiring a Tier-1 amendment.

### Principle 1: Stateless Process Design

Each application process must be stateless and share-nothing. No in-memory state may be shared across requests or across ECS tasks. All durable state must reside in external backing services (databases, caches, queues). Process-scoped singletons (e.g., configuration, service instances) are permitted only when they represent immutable or read-only state that is identical across all tasks.

### Principle 2: Explicit Dependency Injection

All services must receive their dependencies through an explicit injection mechanism. No service may self-provision its dependencies by directly importing and instantiating infrastructure components. The dependency graph must be explicit, inspectable, and overridable for testing. The specific injection mechanism (constructor injection, framework-managed resolution) and boundary enforcement rules are governed by ADR-0048.

### Principle 3: Strict Layer Separation

The application is organized into three layers with unidirectional dependency flow:
1. **Application layer** (routes, jobs, event handlers) — consumes services through an injection boundary.
2. **Service layer** (providers, dependency wiring) — assembles infrastructure components and exposes them to the application layer.
3. **Infrastructure layer** (clients, configuration, persistence, operations) — provides platform capabilities with no knowledge of the application layer.

Application code must never directly import or instantiate infrastructure internals. Infrastructure components must never reference the application layer.

### Principle 4: Fail-Fast Configuration Validation

All configuration must be loaded, validated, and frozen before the application accepts traffic. Invalid configuration must terminate startup immediately. Configuration must be immutable after validation. Runtime configuration changes require a process restart.

### Principle 5: Security-by-Default Boundaries

Sensitive data (credentials, tokens, API keys) must never appear in logs, error messages, or API responses. Credentials must originate from environment variables or secrets management services, never from source code or configuration files committed to version control. Logging must be structured and must enforce a separation between operational context (safe to log) and sensitive payload (never logged).

## Alternatives Considered

1. Retain principles and implementation guidance in one Tier-1 record:
   - Pros: Single reference for both principle and practice.
   - Cons: Tier-1 scope leakage; implementation changes force Tier-1 amendments; downstream ADRs cannot distinguish binding principles from refinable guidance.
   - Why not chosen: Violates ADR-0044 governance rule of one authority level per record and ADR-0051 taxonomy enforcement.
2. Split into more than five principles:
   - Pros: Finer-grained authority for each concern.
   - Cons: Excessive Tier-1 churn; some concerns (e.g., async strategy) are implementation-level, not principle-level.
   - Why not chosen: Five principles cover the foundational invariants; further decomposition belongs at Tier-2.

## Consequences

- Positive impacts:
  - Clean Tier-1 record with no implementation leakage.
  - Downstream Tier-2 standards can evolve implementation details independently.
  - Principle boundaries are reviewable and auditable per ADR-0051 taxonomy enforcement.
- Tradeoffs accepted:
  - Developers must consult both this Tier-1 record and relevant Tier-2 standards for complete guidance.
  - The five principles are deliberately abstract; actionable implementation rules live in lower-tier ADRs.
- Risks introduced:
  - Principles may be too abstract for new team members without accompanying Tier-2 standards.
- Mitigations:
  - Each principle has explicit downstream ADR references in the `impacts` metadata.
  - Onboarding documentation should reference both Tier-1 principles and their Tier-2 elaborations.

## Compliance and Boundaries

- Package/infrastructure boundary impact: Principle 3 (layer separation) directly governs the boundary between `app/packages`, `app/infrastructure`, and `app/server`.
- Type boundary impact: Deferred to ADR-0065 (Type-Model Boundaries Canonical Principle).
- Startup/plugin registration impact: Principle 4 (fail-fast configuration) constrains startup behavior; detailed startup policy is governed by ADR-0046 and ADR-0049.
- Settings partitioning impact: Principle 4 establishes the configuration validation invariant; partitioning rules are governed by ADR-0047.

## Best-Practice Revalidation

- Revalidation date: 2026-04-28
- Sources rechecked:
  - Twelve-Factor App: Factor III (Config), Factor VI (Processes), Factor IX (Disposability).
  - Python 3.12+ typing and dependency injection conventions.
  - FastAPI dependency injection documentation (Annotated + Depends pattern).
  - OWASP secure logging and credential management guidance.
- Alignment summary:
  - All five principles align with Twelve-Factor methodology and current Python/FastAPI best practices.
  - Stateless process design directly implements Factor VI.
  - Fail-fast configuration validation aligns with Factor III and pydantic-settings validation patterns.
  - Security-by-default boundaries align with OWASP logging and secrets management guidance.
- Intentional deviations: None.

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: Canonical rewrite of ADR-0001 with implementation examples removed and principle scope enforced per ADR-0044 and ADR-0051.
- Follow-up actions:
  - Ensure all downstream Tier-2 standards reference this record in `constrained_by`.
  - Mark ADR-0001 as superseded with `superseded_by: [ADR-0045]`.

## Source References

1. Source title: Twelve-Factor App Methodology
   - URL: https://12factor.net/
   - Publisher/maintainer: 12factor contributors
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Factors III, VI, IX directly inform principles 1, 4, and 5.
2. Source title: FastAPI Dependency Injection Documentation
   - URL: https://fastapi.tiangolo.com/tutorial/dependencies/
   - Publisher/maintainer: Sebastián Ramírez / FastAPI
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Confirms framework support for explicit DI pattern (Principle 2).
3. Source title: OWASP Logging Cheat Sheet
   - URL: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
   - Publisher/maintainer: OWASP Foundation
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Confirms security-by-default logging boundaries (Principle 5).
4. Source title: ADR-0001 (Legacy — Core Architectural Principles)
   - URL: docs/decisions/adr/0001-core-architectural-principles.md
   - Publisher/maintainer: SRE Team
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Source record being superseded; principles extracted and implementation details removed.

## Implementation Guidance

- Required changes:
  - Mark ADR-0001 as `status: Superseded` and add `superseded_by: [ADR-0045]`.
  - Ensure all Tier-2 standards that implement these principles include `constrained_by: [ADR-0045]`.
- Validation and quality gates:
  - ADR-0051 taxonomy check: confirm this record contains no implementation-level code examples or library-specific patterns.
  - Metadata completeness check: all 18 fields populated.
- Test strategy and acceptance criteria impact:
  - No direct test changes; principles are validated through downstream standard compliance.

## Change Log

- 2026-04-28: Revised Principle 2 to remove mechanism-specific language (constructor injection) and delegate boundary mechanics to ADR-0048, resolving dual-authority overlap identified in challenge review.
- 2026-04-28: Created canonical Tier-1 principle record; supersedes ADR-0001. Implementation examples removed; five principles distilled to foundational invariants.
