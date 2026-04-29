---
adr_id: ADR-0048
title: "Dependency and Import Boundary Constitution"
status: Accepted
decision_type: Principle
tier: Tier-1
primary_domain: Dependency and Composition
secondary_domains:
  - Package and Plugin Architecture
  - Testing and Quality Gates
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
  - ADR-0049
  - ADR-0056
  - ADR-0059
  - ADR-0063
supersedes:
  - ADR-0003
  - ADR-0004
superseded_by: []
review_state: current
related_records:
  - ADR-0044
  - ADR-0045
  - ADR-0047
  - ADR-0049
related_packages: []
---

# Dependency and Import Boundary Constitution

## Context

- Problem statement: Dependency injection rules and import conventions were split across two legacy ADRs (ADR-0003 and ADR-0004), both containing implementation-level code examples at Tier-1. ADR-0003 defined the three-layer DI architecture and provider patterns. ADR-0004 defined import hierarchy rules and anti-patterns. Both records duplicated guidance about what application code may and may not import, creating ambiguity about the authoritative source for boundary rules. Additionally, neither record addressed the legacy `app/modules` directory or its relationship to the target architecture.
- Business/operational drivers:
  - Establish a single Tier-1 principle record for dependency injection boundaries and import rules.
  - Define the authoritative import hierarchy as a governance constraint, not implementation guidance.
  - Explicitly address the `app/modules` legacy layer and its posture in the target architecture.
  - Prevent circular dependencies and layer violations through enforceable boundary rules.
- Constraints:
  - Three-layer architecture is established (ADR-0045 Principle 3).
  - DI must be explicit and overridable for testing (ADR-0045 Principle 2).
  - FastAPI `Annotated[T, Depends(...)]` is the framework-level DI mechanism.
  - `app/modules` exists as a legacy layer and must not be used as an architectural reference.
- Non-goals:
  - This record does not define specific provider function implementations or dependency alias conventions.
  - This record does not define plugin registration mechanics (delegated to ADR-0049).

## Decision

- Chosen approach: Consolidate dependency injection and import boundary authority into one Tier-1 constitution that defines boundary invariants and the legacy-module posture.
- Why this approach: Merging DI boundaries and import rules into one record eliminates duplication and provides a single, enforceable boundary reference for all layers.

### Boundary 1: Unidirectional Import Flow

Imports must flow in one direction only: Application → Service/Injection Boundary → Infrastructure. No reverse imports are permitted. Infrastructure code must never import from the application layer. Application code must never import infrastructure internals directly.

### Boundary 2: Single Injection Surface

All infrastructure services must be consumed through a single, defined injection boundary. Application code imports only from this boundary — never from infrastructure internals, client packages, or configuration modules directly. The injection boundary provides:
- Provider functions for service construction (used by jobs, background tasks, and non-HTTP contexts).
- Dependency aliases for framework-managed injection (used by HTTP route handlers).

### Boundary 3: Constructor-Only Dependency Receipt

Services must receive all dependencies through their constructor. No service may call provider functions or access global state to self-provision its dependencies. This ensures the dependency graph is explicit, inspectable, and testable through simple constructor injection.

### Boundary 4: No Import-Time Side Effects

Module imports must not trigger side effects: no registration, no state mutation, no external calls, no global dictionary modification. All such actions must occur during explicit startup phases (constrained by ADR-0046). The `@hookimpl` decorator is permitted as a metadata marker because it stores metadata on the function object without executing side effects.

### Boundary 5: Infrastructure Sibling Isolation

Infrastructure packages must not import from other infrastructure service implementations directly. Each infrastructure package is a peer that communicates through the provider/injection boundary. This prevents hidden coupling between infrastructure components and ensures each can be tested independently.

### Boundary 6: Legacy Module Posture

The `app/modules` directory is a legacy layer that is being retired through migration to `app/packages`. New code must not be added to `app/modules`. Existing `app/modules` code must not be used as an architectural reference for new packages. The legacy module layer follows the same import boundary rules as the application layer.

## Alternatives Considered

1. Retain two separate DI and import ADRs:
   - Pros: Smaller individual records.
   - Cons: Overlapping authority; developers consult two records for the same boundary question.
   - Why not chosen: The concerns are inseparable — import rules exist to enforce DI boundaries.
2. Include implementation-level patterns (provider examples, alias conventions) at Tier-1:
   - Pros: Complete guidance in one record.
   - Cons: Implementation changes force Tier-1 amendments; violates one-authority-level-per-record.
   - Why not chosen: Implementation patterns belong in Tier-2 standards.
3. Ignore the legacy module posture:
   - Pros: Simpler record.
   - Cons: New developers may use `app/modules` as a reference, perpetuating legacy patterns.
   - Why not chosen: Explicit legacy posture prevents architectural regression.

## Consequences

- Positive impacts:
  - Single authoritative boundary record eliminates contradictions between ADR-0003 and ADR-0004.
  - Boundary rules are governance-enforceable rather than advisory.
  - Legacy module posture is explicitly documented, preventing new code from entering the legacy layer.
- Tradeoffs accepted:
  - Six boundaries are deliberately abstract; implementation-level guidance requires consulting Tier-2 standards.
  - The legacy posture statement creates a migration obligation that must be tracked.
- Risks introduced:
  - Strict boundaries may create friction when legacy modules need urgent fixes before migration.
- Mitigations:
  - Legacy modules may be maintained (bug fixes, security patches) but not extended.
  - Migration progress is tracked in Tier-5 migration ADRs.

## Compliance and Boundaries

- Package/infrastructure boundary impact: Boundaries 1, 2, and 5 directly govern the relationship between `app/packages`, `app/infrastructure`, and `app/server`.
- Type boundary impact: Deferred to ADR-0065.
- Startup/plugin registration impact: Boundary 4 (no import-time side effects) directly constrains ADR-0049 plugin registration mechanics.
- Settings partitioning impact: Boundary 2 (single injection surface) constrains how settings are consumed, complementing ADR-0047 Principle 4 (narrow-slice injection).

## Best-Practice Revalidation

- Revalidation date: 2026-04-28
- Sources rechecked:
  - Python PEP 8 and PEP 20 (Zen of Python: "Explicit is better than implicit").
  - FastAPI Dependency Injection documentation (Annotated + Depends).
  - Twelve-Factor App: Factor III (Config), Factor IV (Backing Services).
  - Clean Architecture / Hexagonal Architecture principles (dependency rule: inner layers do not depend on outer layers).
  - Pluggy documentation (hookimpl as metadata marker, no side effects at import time).
- Alignment summary:
  - Unidirectional import flow aligns with Clean Architecture dependency rule.
  - No import-time side effects aligns with Python best practices and pluggy's design philosophy.
  - Constructor-only dependency receipt aligns with standard DI patterns across frameworks.
- Intentional deviations: None.

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: Consolidates ADR-0003 and ADR-0004 into one DI/import boundary constitution with explicit legacy-module posture and no implementation leakage.
- Follow-up actions:
  - Mark ADR-0003 and ADR-0004 as superseded with `superseded_by: [ADR-0048]`.
  - Ensure downstream standards (ADR-0049, ADR-0059) reference this record in `constrained_by`.

## Source References

1. Source title: FastAPI Dependency Injection
   - URL: https://fastapi.tiangolo.com/tutorial/dependencies/
   - Publisher/maintainer: Sebastián Ramírez / FastAPI
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Confirms Annotated + Depends as the framework DI mechanism.
2. Source title: Clean Architecture — The Dependency Rule
   - URL: https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html
   - Publisher/maintainer: Robert C. Martin
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Dependency rule (inner layers independent of outer layers) directly informs Boundary 1.
3. Source title: Pluggy Documentation — Hook Implementation Markers
   - URL: https://pluggy.readthedocs.io/en/stable/
   - Publisher/maintainer: pytest-dev / pluggy
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Confirms @hookimpl is a metadata marker with no import-time side effects.
4. Source title: ADR-0003, ADR-0004 (Legacy)
   - URL: docs/decisions/adr/
   - Publisher/maintainer: SRE Team
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Source records being consolidated; boundary invariants extracted and implementation details removed.

## Implementation Guidance

- Required changes:
  - Mark ADR-0003 and ADR-0004 as `status: Superseded` and add `superseded_by: [ADR-0048]`.
  - Ensure downstream standards reference this record in `constrained_by`.
- Validation and quality gates:
  - ADR-0051 taxonomy check: confirm no implementation-level code examples in this record.
  - Import boundary compliance can be partially automated via import linting tools.
  - Metadata completeness check: all 18 fields populated.
- Test strategy and acceptance criteria impact:
  - No direct test changes; boundary invariants are validated through code review and downstream standard compliance.

## Change Log

- 2026-04-28: Created canonical Tier-1 dependency and import boundary constitution; supersedes ADR-0003 and ADR-0004. Two source records consolidated into six boundary invariants with explicit legacy-module posture and no implementation detail.
