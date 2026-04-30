---
adr_id: ADR-0065
title: "Type-Model Boundaries Canonical Principle"
status: Accepted
decision_type: Principle
tier: Tier-1
primary_domain: Dependency and Composition
secondary_domains:
  - Transport and API
  - Configuration and Secrets
  - Data and Persistence
owners:
  - SRE Team
date_created: 2026-04-30
last_updated: 2026-04-30
last_reviewed: 2026-04-30
next_review_due: 2026-08-28
constrained_by:
  - ADR-0044
  - ADR-0045
  - ADR-0048
impacts:
  - ADR-0050
  - ADR-0055
  - ADR-0056
  - ADR-0059
  - ADR-0060
  - ADR-0061
  - ADR-0062
  - ADR-0063
  - ADR-0064
  - ADR-0077
supersedes:
  - ADR-0040
superseded_by: []
review_state: current
related_records:
  - ADR-0046
  - ADR-0047
  - ADR-0076
  - ADR-0078
related_packages:
  - app/packages/access
  - app/infrastructure
---

# Type-Model Boundaries Canonical Principle

## Context

- Problem statement: The prior ADR-0040 was classified as Tier-4 Feature Decision but contained foundational type-model boundary principles that constrain all layers of the application. It mixed Tier-1 principles (which type construct to use at which boundary) with Tier-2 implementation guidance (code examples, specific usage patterns, scenario-based recipes). This tier mismatch left the type-model boundary authority ambiguous: downstream ADRs (ADR-0045 P6, ADR-0048 B2/B7, ADR-0055, ADR-0060, ADR-0063, ADR-0077) each addressed fragments of the type-model question without a unifying Tier-1 principle to anchor them.
- Business/operational drivers:
  - Establish a single Tier-1 principle record that governs which Python type construct is appropriate at each architectural boundary.
  - Unify the type-model rules fragmented across Waves 3 and 4 ADRs into a coherent principle hierarchy.
  - Codify the type-model conventions that emerged organically in the codebase before the ADR program — the codebase already follows these patterns; this ADR makes them normative and enforceable.
  - Prevent type-model drift where Pydantic models propagate into service logic, or where internal types leak into API contracts.
- Constraints:
  - Python 3.12+ runtime target.
  - PEP 544 (`typing.Protocol`) for structural subtyping.
  - PEP 557 (`dataclasses`) for value types.
  - Pydantic V2 for validation-capable types.
  - Principles must complement ADR-0045 P6 (Protocol-driven contracts) without duplicating its authority.
  - All implementation-level rules (code patterns, migration steps, scenario recipes) are delegated to Tier-2 standards.
- Non-goals:
  - This record does not prescribe specific field names, naming conventions, or code-level patterns.
  - This record does not define Protocol migration priorities (governed by ADR-0077).
  - This record does not define settings type patterns (governed by ADR-0055).
  - This record does not define API schema conventions (governed by ADR-0060, ADR-0063).

## Decision

- Chosen approach: Establish five foundational type-model boundary principles that govern which Python type construct is appropriate at each architectural boundary. Each principle identifies one type construct, its boundary, and its governing rationale. Implementation specifics are delegated to existing Tier-2 standards.
- Why this approach: The codebase already exhibits clean type-model separation (Protocol for service contracts, frozen dataclasses for domain values, Pydantic at HTTP boundaries, TypedDict constrained to adapter internals). Elevating these organic patterns to Tier-1 principles makes them enforceable, prevents regression, and provides a single authoritative reference that unifies the type-model fragments across Waves 3–4 ADRs.

### Principle 1: Boundary-Determined Type Selection

The correct Python type construct is determined by the architectural boundary at which data or behavior is defined — not by the data's shape or the developer's familiarity with a particular library. Each boundary has exactly one preferred type construct. Using a type construct outside its designated boundary requires explicit justification and must be documented as a pragmatic exception.

The boundary-to-type mapping is:

| Boundary | Type Construct | Rationale |
|----------|---------------|-----------|
| Behavior contracts between services | `typing.Protocol` | Structural subtyping; implementation-agnostic; testable via duck-typed doubles |
| Internal data crossing package/service boundaries | `@dataclass(frozen=True)` | Immutable; framework-independent; lightweight; safe to share |
| Untrusted I/O (HTTP, webhooks, external payloads) | `pydantic.BaseModel` | Validation, coercion, and schema generation at trust boundaries |
| Configuration from environment | `pydantic_settings.BaseSettings` | Typed environment parsing with validation |
| Configuration subsections (nested) | `pydantic.BaseModel` | Structured nesting within a BaseSettings root |
| Dictionary-shaped adapter internals | `typing.TypedDict` | Dict semantics when key presence and dict behavior are intentional |

This principle governs all code in `app/infrastructure`, `app/packages`, `app/server`, and `app/api`. The legacy `app/modules` layer is exempt from new enforcement but must not be used as an architectural reference (ADR-0048 B6).

### Principle 2: Protocol for Behavioral Contracts

Service-layer behavioral contracts must be expressed as `typing.Protocol` (PEP 544). A Protocol type defines what a collaborator can do, not what data it contains or how it is implemented. Protocol types are the canonical mechanism for:

- Defining infrastructure service interfaces consumed by feature packages (ADR-0045 P6).
- Enabling backing-service substitution without modifying consumer code (ADR-0048 B7).
- Providing testability through duck-typed test doubles (ADR-0077 S4).
- Expressing the injection boundary contract — dependency aliases and provider functions expose Protocol types, not concrete classes (ADR-0048 B2).

Protocol types must not carry data fields, validation logic, or serialization behavior. If a contract requires both behavior and data, the Protocol defines the behavior and references dataclass types for the data.

The scope, classification, and migration priorities for Protocol contracts are governed by ADR-0077. This principle establishes the type-construct choice; ADR-0077 establishes which services require it.

### Principle 3: Immutable Value Types for Internal Data

Data that crosses internal boundaries (package-to-package, service-to-service, layer-to-layer within the application) must use framework-independent immutable value types. The canonical construct is `@dataclass(frozen=True)` (PEP 557).

Frozen dataclasses provide:

- **Immutability guarantee** — fields cannot be modified after construction, ensuring safe sharing across components without defensive copying.
- **Framework independence** — no coupling to FastAPI, Pydantic, or any web framework. Internal data remains portable and testable in isolation.
- **Explicit state transitions** — mutations are expressed through `dataclasses.replace()`, producing new instances. This makes state transitions visible and auditable.

Mutable dataclasses (`@dataclass` without `frozen=True`) are permitted for transient, process-local state that does not cross package boundaries (e.g., retry tracking, in-flight event accumulation). Mutable dataclasses must not be used as shared service contract types.

Shared value types (e.g., `OperationResult[T]`, `DirectoryUser`, `AccessRequest`) are governed by this principle. Their specific usage patterns are elaborated in ADR-0050 (OperationResult) and ADR-0077 (service contract data types).

### Principle 4: Validation Types at Trust Boundaries Only

Validation-capable types (`pydantic.BaseModel`) must be used exclusively at trust boundaries — points where data enters the system from untrusted or partially trusted sources. Trust boundaries include:

- HTTP request and response schemas (routes, API handlers).
- Webhook payloads from external systems (Slack, Teams, GitHub, AWS).
- Scheduled job payloads loaded from external JSON.
- Command inputs from platform users.

Validation types are boundary artifacts. They must not propagate into service logic, domain models, or infrastructure contracts. Route handlers and adapter functions convert validated Pydantic models to internal types (frozen dataclasses or primitives) near the boundary, and convert internal types back to Pydantic response models near the boundary.

This principle ensures that:

- Business logic is not coupled to Pydantic's validation, serialization, or schema-generation behavior.
- Internal service interfaces remain framework-independent (Principle 2, Principle 3).
- Validation rules are localized at the boundary, not distributed across service internals.

The specific API schema patterns and error-mapping conventions are governed by ADR-0060 (response/error mapping) and ADR-0063 (validation/composition). Configuration types (`BaseSettings`, nested `BaseModel`) are governed by ADR-0047 and ADR-0055 — these are a recognized exception to the "validation types at trust boundaries only" rule because environment-variable parsing is itself a trust boundary.

### Principle 5: Constrained Dictionary Typing

Dictionary-typed structures (`typing.TypedDict`) are appropriate only when dictionary semantics are explicitly required — when key presence matters, dict behavior (`__getitem__`, `.get()`, `.keys()`) is intentional, and the structure does not represent a stable domain entity.

Legitimate uses:

- Raw SDK payloads returned by external API clients before conversion to internal types.
- Partial metadata maps where the key set is variable.
- Adapter-internal type hints documenting expected dict shapes.

TypedDict must remain local to the adapter or module that produces or consumes the dictionary. It must not be used for:

- Shared service contracts (use Protocol — Principle 2).
- Cross-package data transfer (use frozen dataclass — Principle 3).
- API request/response schemas (use Pydantic BaseModel — Principle 4).

When a TypedDict is found at a package boundary or in a shared contract, it should be migrated to a frozen dataclass with a dedicated result type.

## Alternatives Considered

1. Retain ADR-0040 at Tier-4 and add cross-references:
   - Pros: No new Tier-1 record; less governance overhead.
   - Cons: A Tier-4 Feature Decision cannot constrain Tier-2 standards (ADR-0055, ADR-0060, ADR-0063, ADR-0077). The type-model boundary question is architectural, not feature-local. Downstream ADRs would continue to address type-model fragments without a unifying authority.
   - Why not chosen: Violates ADR-0044 governance rule — a lower-tier record cannot constrain higher-tier or peer records.

2. Fold type-model principles into ADR-0045 as additional principles:
   - Pros: Single Tier-1 record for all architectural principles.
   - Cons: ADR-0045 already has seven principles spanning process design, DI, layer separation, configuration, security, Protocol contracts, and delegation hierarchy. Adding five type-model principles would exceed the coherent scope of a single record and dilute focus.
   - Why not chosen: ADR-0045 P6 already delegates Protocol specifics to ADR-0077; the type-model boundary scope is broader than Protocol contracts and warrants its own Tier-1 authority.

3. Create a Tier-2 Standard instead of a Tier-1 Principle:
   - Pros: More room for implementation specifics.
   - Cons: A Tier-2 Standard cannot constrain other Tier-2 records. The type-model boundary question spans multiple Tier-2 domains (ADR-0055 settings, ADR-0060 API responses, ADR-0063 validation, ADR-0077 service contracts). A Tier-1 Principle is required to provide unifying authority.
   - Why not chosen: The boundary-to-type mapping is a foundational design intent, not a refinable implementation convention.

4. Prescribe type construct based on data shape rather than boundary:
   - Pros: Simpler mental model for developers ("if it's a user, use dataclass").
   - Cons: The same data shape (e.g., a user) requires different type constructs at different boundaries (Pydantic at HTTP, dataclass internally, Protocol for the service that provides it). Shape-based selection leads to Pydantic models propagating into service logic.
   - Why not chosen: The boundary determines the appropriate type construct; the data shape determines the fields. These are orthogonal concerns.

## Consequences

- Positive impacts:
  - Single authoritative reference for type-model boundary decisions across all layers.
  - Unifies the fragmented type-model rules from Waves 3–4 ADRs under one Tier-1 authority.
  - Codifies conventions already demonstrated in the codebase (particularly `app/packages/access`), making them enforceable rather than implicit.
  - Prevents Pydantic model propagation into service logic — a common drift pattern in FastAPI applications.
  - Clear onboarding reference: one table (Principle 1) maps every boundary to its type construct.
- Tradeoffs accepted:
  - Developers must perform explicit conversions between Pydantic and dataclass types at route boundaries. This adds boilerplate but ensures clean separation. The conversion pattern is well-established in the codebase.
  - Five principles are deliberately abstract; actionable implementation rules live in Tier-2 standards (ADR-0055, ADR-0060, ADR-0063, ADR-0077).
  - The codebase predates this ADR program. Some existing code may not conform to these principles. Non-conforming code is not retroactively non-compliant — it represents the organic conventions from which these principles were derived. New code and actively modified code must conform.
- Risks introduced:
  - Principle 4 (validation types at trust boundaries only) may be challenged when Pydantic models are convenient for intermediate transformations. The principle intentionally restricts this to maintain clean boundaries.
  - The configuration exception (BaseSettings/BaseModel for settings) may be misread as permission to use Pydantic everywhere that data needs validation. The exception is scoped: environment-variable parsing is itself a trust boundary.
- Mitigations:
  - Each principle has explicit downstream ADR references for implementation-level guidance.
  - The boundary-to-type mapping table (Principle 1) provides an unambiguous lookup.
  - The `type-model-boundaries` Copilot skill encodes these principles for IDE-time guidance.

## Compliance and Boundaries

- Package/infrastructure boundary impact: Principle 2 (Protocol) and Principle 3 (frozen dataclass) govern the type surface between `app/infrastructure` and `app/packages`. Feature packages depend on Protocol types and receive/return frozen dataclasses — never on concrete implementation classes or Pydantic models from infrastructure internals.
- Type boundary impact: This is the governing record for all type-model boundary decisions. It provides the Tier-1 authority that ADR-0045 P6, ADR-0048 B2, and ADR-0048 B7 delegate to for the full type-construct spectrum.
- Service contract impact: Principle 2 establishes Protocol as the behavior-contract type; ADR-0077 governs which services require Protocol contracts and the migration path. Principle 3 establishes frozen dataclasses as the canonical data type within Protocol method signatures.
- Settings impact: Configuration types (BaseSettings root, BaseModel nested) are a scoped exception to Principle 4 per ADR-0047 and ADR-0055. The exception is justified: environment-variable parsing is a trust boundary.
- API response/validation impact: Principle 4 mandates Pydantic at HTTP trust boundaries. The specific schema patterns, error mapping, and validation conventions are governed by ADR-0060 and ADR-0063.
- OperationResult impact: `OperationResult[T]` (ADR-0050) is a shared value type governed by Principle 3. It serves as the canonical return type for fallible Protocol methods (Principle 2).
- Legacy module posture: `app/modules` is exempt from new enforcement per ADR-0048 B6. Existing TypedDict usage in `modules/groups/domain/types.py` is legacy; new code in `app/packages` must prefer frozen dataclasses per Principle 5.

## Current State Assessment

The codebase predates this ADR program. The following assessment documents observed patterns against these principles. Conforming patterns were the basis for deriving these principles; non-conforming patterns are opportunities for future alignment, not retroactive violations.

| Principle | Observed Conformance | Notable Exceptions |
|-----------|---------------------|-------------------|
| P1 (Boundary-determined selection) | Strong. Access package demonstrates clean separation: schemas.py (Pydantic), domain.py (frozen dataclass), service.py (Protocol). | Some `app/models/` files mix boundary concerns (legacy). |
| P2 (Protocol for behavior) | 14 Protocol classes. Category A services with Protocols: DirectoryProvider, RetryStore, RetryProcessor, ResponseChannel, BackgroundJobRegistry. | 5 Category A services lack Protocols (StorageService, IdentityService, AuditTrailService, NotificationService, IdempotencyService). Migration governed by ADR-0077 S5. |
| P3 (Immutable value types) | ~20 frozen dataclasses for domain entities (AccessRequest, DirectoryUser, etc.). State transitions use `dataclasses.replace()`. | ~25 mutable dataclasses exist for transient state — this is within the principle's allowance. |
| P4 (Validation at trust boundaries) | Pydantic models concentrated in schemas.py, API routes, webhook handlers. No Pydantic in service logic. | `User` in identity/models.py uses Pydantic despite no HTTP boundary — justified by multi-source validation. `AuditEvent` uses Pydantic for SIEM serialization — justified by `model_dump()` flattening. |
| P5 (Constrained dict typing) | 4 TypedDict definitions, all in `modules/groups/domain/types.py`. Local to orchestration layer. | Legacy location (`app/modules`); new packages use frozen dataclasses per this principle. |

## Best-Practice Revalidation

- Revalidation date: 2026-04-30
- Sources rechecked:
  - §1: PEP 544 — Protocol classes for structural subtyping. Confirms Protocol as the standard mechanism for behavior contracts in Python 3.12+. `@runtime_checkable` permits isinstance checks but does not verify signatures (static analysis via mypy is primary enforcement).
  - §2: PEP 557 — Data classes. Confirms `@dataclass(frozen=True)` as the standard immutable value type. `dataclasses.replace()` as the canonical mutation pattern.
  - §3: Pydantic V2 documentation — BaseModel for validation and serialization at I/O boundaries. Pydantic frames itself around "type hints powering schema validation" (Pydantic V2 docs, Why use Pydantic). Its strengths — coercion, JSON Schema generation, OpenAPI integration — are boundary concerns, not internal modeling concerns.
  - §4: FastAPI dependency injection documentation — `Annotated[Protocol, Depends(provider)]` pattern for Protocol-typed injection.
  - §5: Python typing module official documentation — TypedDict for typed dictionaries with string keys. PEP 589 confirms TypedDict as a dict-subtype hint, not a general-purpose data container.
  - §6: Hexagonal Architecture (Ports and Adapters) — Protocol types as ports, concrete implementations as adapters. The boundary-determined type selection aligns with the ports-and-adapters principle of keeping domain logic framework-free.
  - §7: Domain-Driven Design tactical patterns — Value Objects as immutable, identity-less types. Frozen dataclasses are the Python implementation of DDD value objects.

## Source References

| # | Source | Relevance |
|---|--------|-----------|
| §1 | [PEP 544 – Protocols: Structural subtyping](https://peps.python.org/pep-0544/) | Principle 2 authority for Protocol contracts |
| §2 | [PEP 557 – Data Classes](https://peps.python.org/pep-0557/) | Principle 3 authority for frozen dataclasses |
| §3 | [Pydantic V2: Why use Pydantic](https://docs.pydantic.dev/latest/why/) | Principle 4 scoping — validation library, not modeling library |
| §4 | [FastAPI Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/) | Protocol-typed injection at route boundaries |
| §5 | [PEP 589 – TypedDict](https://peps.python.org/pep-0589/) | Principle 5 — TypedDict is a dict-subtype hint |
| §6 | Hexagonal Architecture (Alistair Cockburn, 2005) | Boundary-determined type selection; ports and adapters |
| §7 | Domain-Driven Design (Eric Evans, 2003) — Value Objects | Frozen dataclasses as Python value objects |

## Migration

This ADR supersedes ADR-0040. No code changes are required — the principles codify patterns already demonstrated in the codebase. The supersession is a governance action (Tier-4 → Tier-1 elevation), not a behavioral change.

### Supersession Actions

1. Set ADR-0040 `status: Superseded`, `superseded_by: [ADR-0065]`.
2. Move ADR-0040 to `adr/superseded/`.
3. Update cross-references in ADR-0045 (type boundary impact references this ADR).

### Forward Compliance

- New code in `app/packages` and `app/infrastructure` must conform to all five principles.
- Actively modified code should be aligned opportunistically when the modification scope overlaps with a type-model boundary.
- The `type-model-boundaries` Copilot skill (`/.github/skills/type-model-boundaries/SKILL.md`) encodes these principles for IDE-time enforcement.
