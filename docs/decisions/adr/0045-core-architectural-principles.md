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
last_updated: 2026-04-30
last_reviewed: 2026-04-30
next_review_due: 2026-08-28
constrained_by:
 - ADR-0044
impacts:
 - ADR-0047
 - ADR-0048
 - ADR-0049
 - ADR-0050
 - ADR-0052
 - ADR-0054
 - ADR-0055
 - ADR-0056
 - ADR-0059
 - ADR-0065
 - ADR-0077
 - ADR-0079
 - ADR-0083
supersedes:
 - ADR-0001
superseded_by: []
review_state: current
related_records:
 - ADR-0044
 - ADR-0046
 - ADR-0047
 - ADR-0048
 - ADR-0056
 - ADR-0076
 - ADR-0077
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

- Chosen approach: Establish seven foundational architectural principles as the governing constraints for all downstream ADRs, standards, and patterns.
- Why this approach: Separating principles from implementation allows Tier-2 standards to evolve (e.g., new async libraries, new DI frameworks) without requiring a Tier-1 amendment.

### Principle 1: Stateless Process Design

Each application process must be stateless and share-nothing. No in-memory state may be shared across requests or across ECS tasks. All durable state must reside in external backing services (databases, caches, queues). Process-scoped singletons (e.g., configuration, service instances) are permitted only when they represent immutable or read-only state that is identical across all tasks.

### Principle 2: Explicit Dependency Injection

All services must receive their dependencies through an explicit injection mechanism. No service may self-provision its dependencies by directly importing and instantiating infrastructure components. The dependency graph must be explicit, inspectable, and overridable for testing. The specific injection mechanism (constructor injection, framework-managed resolution) and boundary enforcement rules are governed by ADR-0048.

### Principle 3: Strict Layer Separation

The application is organized into three layers with unidirectional dependency flow:

1. **Application layer** (routes, jobs, event handlers) - consumes services through an injection boundary.
2. **Service layer** (providers, dependency wiring) - assembles infrastructure components and exposes them to the application layer.
3. **Infrastructure layer** (clients, configuration, persistence, operations) - provides reusable, standardized core services through Protocol-based contracts, enabling feature packages to consume capabilities without coupling to specific backing-service implementations.

Application code must never directly import or instantiate infrastructure internals. Infrastructure components must never reference the application layer. Infrastructure services may collaborate internally through the composition root and shared value types - the isolation boundary is between the infrastructure and application layers, not between infrastructure packages.

### Principle 4: Fail-Fast Configuration Validation

All configuration must be loaded, validated, and frozen before the application accepts traffic. Invalid configuration must terminate startup immediately. Configuration must be immutable after validation. Runtime configuration changes require a process restart.

### Principle 5: Security-by-Default Boundaries

Sensitive data (credentials, tokens, API keys) must never appear in logs, error messages, or API responses. Credentials must originate from environment variables or secrets management services, never from source code or configuration files committed to version control. Logging must be structured and must enforce a separation between operational context (safe to log) and sensitive payload (never logged).

### Principle 6: Protocol-Driven Service Contracts

Infrastructure services consumed by feature packages must be defined by Protocol contracts, enabling backing-service substitution without modifying feature code. The type-construct rationale and detailed rules are governed by ADR-0065 Principle 2. Service classifications and migration priorities are governed by ADR-0077.

### Principle 7: Managed Service Delegation Hierarchy

Infrastructure concerns must be served by the highest applicable delegation tier:

1. **Managed cloud service** (preferred) — the cloud provider owns availability, scaling, patching, and monitoring. The application wraps the managed service SDK in a thin facade behind a Protocol contract (Principle 6). Examples: DynamoDB for persistence, SQS for queuing, CloudWatch for metrics.
2. **Industry-standard library** (fallback) — when no managed service covers the concern, a proven, well-maintained library provides battle-tested correctness. The application wraps the library API in a thin adapter. Examples: `schedule` for background job timing, `slowapi` for application-level rate limiting.
3. **Custom implementation** (last resort) — only when neither a managed service nor a proven library is applicable. Custom code must be proportional in scope, must document why higher tiers do not apply, and must be flagged for future delegation when viable alternatives emerge.

Every Protocol-backed service (Category A per ADR-0077) must support backend selection through configuration, enabling cloud portability and dev/test fallbacks without code changes. The configurable backend settings pattern is governed by ADR-0047; provider construction and backend-selection logic are governed by ADR-0056; dev/test fallback requirements are governed by ADR-0054. Infrastructure library selections require a Tier-5 ADR per ADR-0044.

## Alternatives Considered

1. Retain principles and implementation guidance in one Tier-1 record:

- Pros: Single reference for both principle and practice.
- Cons: Tier-1 scope leakage; implementation changes force Tier-1 amendments; downstream ADRs cannot distinguish binding principles from refinable guidance.
- Why not chosen: Violates ADR-0044 governance rule of one authority level per record and ADR-0051 taxonomy enforcement.

1. Keep at six principles and handle delegation at Tier-2 only:

- Pros: Fewer Tier-1 constraints; less amendment friction.
- Cons: The delegation hierarchy is a foundational design intent that completes Principle 6. Without a Tier-1 mandate, teams could implement custom infrastructure when managed services or proven libraries exist, accumulating unnecessary operational burden. The pattern parallels Principle 6: Protocol contracts govern the port shape; the delegation hierarchy governs what sits behind the adapter.
- Why not chosen: The preference for managed services over custom code is a core architectural posture aligned with GC Cloud Adoption Strategy, AWS Well-Architected Framework, and Twelve-Factor backing services. It must constrain all downstream standards.

1. Omit Protocol-driven contracts as a principle and handle at Tier-2 only:

- Pros: Fewer Tier-1 constraints; less amendment friction.
- Cons: The swappable service layer is a foundational architectural intent, not an implementation detail. Without a Tier-1 mandate, Protocol adoption would be optional and inconsistent.
- Why not chosen: The ability to swap backing-service implementations without modifying feature code is a core design goal that must constrain all downstream standards.

## Consequences

- Positive impacts:
- Clean Tier-1 record with no implementation leakage.
- Downstream Tier-2 standards can evolve implementation details independently.
- Principle boundaries are reviewable and auditable per ADR-0051 taxonomy enforcement.
- Tradeoffs accepted:
- Developers must consult both this Tier-1 record and relevant Tier-2 standards for complete guidance.
- The seven principles are deliberately abstract; actionable implementation rules live in lower-tier ADRs.
- Principle 7 introduces a delegation evaluation step when selecting infrastructure implementations. This overhead is justified by the long-term reduction in custom code maintenance burden.
- Risks introduced:
- Principles may be too abstract for new team members without accompanying Tier-2 standards.
- Mitigations:
- Each principle has explicit downstream ADR references in the `impacts` metadata.
- Onboarding documentation should reference both Tier-1 principles and their Tier-2 elaborations.

## Compliance and Boundaries

- Package/infrastructure boundary impact: Principle 3 (layer separation) directly governs the boundary between `app/packages`, `app/infrastructure`, and `app/server`. Principle 6 (Protocol contracts) governs the contract surface between infrastructure services and feature packages.
- Type boundary impact: Principle 6 mandates Protocol types for service contracts. Detailed type-boundary rules deferred to ADR-0065 (Type-Model Boundaries Canonical Principle).
- Service contract impact: Principle 6 establishes the Protocol contract requirement; service classification and migration are governed by ADR-0077. Principle 7 requires each Category A service to declare its delegation tier and justify any Tier 3 (custom) choice.
- Managed service delegation impact: Principle 7 governs what sits behind Protocol adapters — managed service wrapper, library delegation, or custom code. Backend-selection settings patterns are governed by ADR-0047 and ADR-0055. Provider construction with backend selection is governed by ADR-0056. Dev/test fallback provision is governed by ADR-0054. Library adoption governance is governed by ADR-0044 (Tier-5 trigger). Queue and messaging delegation is governed by ADR-0079. Event dispatcher delegation (custom → blinker library, with facade-owned error-isolated dispatch and async readiness) is governed by ADR-0083.
- Startup/plugin registration impact: Principle 4 (fail-fast configuration) constrains startup behavior; detailed startup policy is governed by ADR-0046 and ADR-0049.
- Settings partitioning impact: Principle 4 establishes the configuration validation invariant; partitioning rules are governed by ADR-0047.
- Infrastructure composition impact: Principle 3 clarifies that infrastructure services collaborate internally through the composition root - the isolation boundary is between layers, not within the infrastructure layer. Detailed composition governance is provided by ADR-0076 and ADR-0056.

## Best-Practice Revalidation

- Revalidation date: 2026-04-28
- Sources rechecked:
- Twelve-Factor App: Factor III (Config), Factor IV (Backing Services), Factor VI (Processes), Factor IX (Disposability).
- Python 3.12+ typing and dependency injection conventions.
- FastAPI dependency injection documentation (Annotated + Depends pattern).
- OWASP secure logging and credential management guidance.
- Python `typing.Protocol` documentation (PEP 544) for structural subtyping contracts.
- Backstage backend services architecture (service interfaces, service factories, service references) as the original inspiration for the shared service layer model.
- AWS Well-Architected Framework — Operational Excellence pillar (managed service preference).
- GC Cloud Adoption Strategy (2018/2023) — Principle 8 (portability), service model priority (SaaS > PaaS > IaaS).
- Hexagonal Architecture / Ports and Adapters (Cockburn) — governance of what sits behind the adapter.
- Alignment summary:
- All seven principles align with Twelve-Factor methodology and current Python/FastAPI best practices.
- Stateless process design directly implements Factor VI.
- Fail-fast configuration validation aligns with Factor III and pydantic-settings validation patterns.
- Security-by-default boundaries align with OWASP logging and secrets management guidance.
- Protocol-driven service contracts align with PEP 544 structural subtyping, the Ports and Adapters pattern, and Backstage's ServiceRef + ServiceFactory model adapted for Python.
- Managed service delegation hierarchy aligns with Twelve-Factor Factor IV (backing services as attached resources, swappable via config), AWS Well-Architected ("use managed services to reduce undifferentiated heavy lifting"), GC Cloud Adoption Strategy Principle 8 (portability and interoperability), and Hexagonal Architecture (governance of adapter implementations behind port contracts).
- Intentional deviations:
- The original Backstage mental model included plugin-to-plugin isolation (no code-level communication between plugins). This rule applies correctly to feature packages (`app/packages`) but was incorrectly applied to infrastructure services in early ADRs. Infrastructure services are shared utilities that compose freely - analogous to Backstage's core services, not to Backstage's plugins. This deviation from the original mental model is intentional and corrective.

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: Canonical rewrite of ADR-0001 with implementation examples removed and principle scope enforced per ADR-0044 and ADR-0051. P7 amendment adds managed service delegation hierarchy as a foundational principle.
- Follow-up actions:
- Ensure all downstream Tier-2 standards reference this record in `constrained_by`.
- Mark ADR-0001 as superseded with `superseded_by: [ADR-0045]`.
- Cascade P7 delegation hierarchy into ADR-0077 (Category A delegation tier declaration), ADR-0047 (backend settings pattern), ADR-0056 (provider backend selection), ADR-0054 (dev/test fallback), ADR-0055 (backend settings dissolution), ADR-0044 (Tier-5 library adoption trigger), ADR-0079 (queue/messaging rework).

## Source References

1. Source title: Twelve-Factor App Methodology

- URL: <https://12factor.net/>
- Publisher/maintainer: 12factor contributors
- Accessed date (YYYY-MM-DD): 2026-04-28
- Relevance summary: Factors III, VI, IX directly inform principles 1, 4, and 5.

1. Source title: FastAPI Dependency Injection Documentation

- URL: <https://fastapi.tiangolo.com/tutorial/dependencies/>
- Publisher/maintainer: Sebastian Ramirez / FastAPI
- Accessed date (YYYY-MM-DD): 2026-04-28
- Relevance summary: Confirms framework support for explicit DI pattern (Principle 2).

1. Source title: OWASP Logging Cheat Sheet

- URL: <https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html>
- Publisher/maintainer: OWASP Foundation
- Accessed date (YYYY-MM-DD): 2026-04-28
- Relevance summary: Confirms security-by-default logging boundaries (Principle 5).

1. Source title: ADR-0001 (Legacy - Core Architectural Principles)

- URL: docs/decisions/adr/superseded/0001-core-architectural-principles.md
- Publisher/maintainer: SRE Team
- Accessed date (YYYY-MM-DD): 2026-04-28
- Relevance summary: Source record being superseded; principles extracted and implementation details removed.

1. Source title: PEP 544 - Protocols: Structural subtyping (static duck typing)

- URL: <https://peps.python.org/pep-0544/>
- Publisher/maintainer: Python Software Foundation
- Accessed date (YYYY-MM-DD): 2026-04-29
- Relevance summary: Defines Python's Protocol mechanism for structural subtyping, providing the language-level foundation for Principle 6 service contracts.

1. Source title: Backstage Backend Services Architecture

- URL: <https://backstage.io/docs/backend-system/architecture/services>
- Publisher/maintainer: Backstage / CNCF
- Accessed date (YYYY-MM-DD): 2026-04-29
- Relevance summary: Original inspiration for the shared service layer mental model. Service interfaces (ServiceRef) + service factories (createServiceFactory) + DI container (backend instance) map to Protocol + provider function + composition root in Python.

1. Source title: AWS Well-Architected Framework — Operational Excellence Pillar

- URL: <https://docs.aws.amazon.com/wellarchitected/latest/operational-excellence-pillar/>
- Publisher/maintainer: Amazon Web Services
- Accessed date (YYYY-MM-DD): 2026-04-30
- Relevance summary: "Use managed services to reduce operational burden" — directly informs Principle 7's preference for managed cloud services over custom implementations.

1. Source title: Government of Canada Cloud Adoption Strategy

- URL: <https://www.canada.ca/en/government/system/digital-government/digital-government-innovations/cloud-services/government-canada-cloud-adoption-strategy.html>
- Publisher/maintainer: Treasury Board of Canada Secretariat
- Accessed date (YYYY-MM-DD): 2026-04-30
- Relevance summary: Principle 8 (portability and interoperability) and service model priority (SaaS > PaaS > IaaS) directly inform Principle 7's delegation hierarchy and configurable backend requirement.

1. Source title: Twelve-Factor App — Factor IV: Backing Services

- URL: <https://12factor.net/backing-services>
- Publisher/maintainer: 12factor contributors
- Accessed date (YYYY-MM-DD): 2026-04-30
- Relevance summary: "Treat backing services as attached resources" — swap between local and third-party services via configuration. Directly supports Principle 7's configurable backend model.

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

- 2026-04-30: Added Principle 7 (Managed Service Delegation Hierarchy). Every infrastructure concern must be served by the highest applicable delegation tier: managed cloud service → industry library → custom implementation. Completes the governance gap identified during ADR-0079 R2 review: Principle 6 governs the port shape (Protocol contracts); Principle 7 governs what sits behind the adapter. Updated alternatives, consequences, compliance, revalidation, and source references. Triggers cascade amendments to ADR-0077, ADR-0047, ADR-0056, ADR-0054, ADR-0055, ADR-0044, ADR-0079. See managed-services-delegation-adr-review-tracker-2026-04-30.md.
- 2026-04-29: Added Principle 6 (Protocol-Driven Service Contracts). Amended Principle 3 to clarify infrastructure layer's role as a shared service platform with internal collaboration. Updated alternatives, consequences, compliance, and revalidation sections. Root cause: Backstage's plugin isolation rule ("plugins must never communicate through code") was misapplied to the infrastructure service layer via ADR-0048 B5. In Backstage, core services freely compose through declared deps; only plugins are isolated. The correct analogy for `app/infrastructure` is Backstage core services (shared utilities), not Backstage plugins. This amendment codifies Protocol-driven contracts as the Python/FastAPI equivalent of Backstage's ServiceRef pattern.
- 2026-04-28: Revised Principle 2 to remove mechanism-specific language (constructor injection) and delegate boundary mechanics to ADR-0048, resolving dual-authority overlap identified in challenge review.
- 2026-04-28: Created canonical Tier-1 principle record; supersedes ADR-0001. Implementation examples removed; five principles distilled to foundational invariants.
