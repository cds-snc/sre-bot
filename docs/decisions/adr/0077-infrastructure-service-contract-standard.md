---
adr_id: ADR-0077
title: "Infrastructure Service Contract Standard"
status: Accepted
decision_type: Standard
tier: Tier-2
primary_domain: Dependency and Composition
secondary_domains:
 - Package and Plugin Architecture
 - Testing and Quality Gates
owners:
 - SRE Team
date_created: 2026-04-29
last_updated: 2026-04-29
last_reviewed: 2026-04-29
next_review_due: 2026-08-29
constrained_by:
 - ADR-0044
 - ADR-0045
 - ADR-0048
impacts:
 - ADR-0056
 - ADR-0059
 - ADR-0061
 - ADR-0065
supersedes: []
superseded_by: []
review_state: current
related_records:
 - ADR-0045
 - ADR-0048
 - ADR-0050
 - ADR-0056
 - ADR-0076
related_packages:
 - app/infrastructure/services
 - app/infrastructure/directory
 - app/infrastructure/storage
 - app/infrastructure/identity
 - app/infrastructure/resilience
---

# Infrastructure Service Contract Standard

## Context

- Problem statement: ADR-0045 Principle 6 mandates that infrastructure services consumed by feature packages must be defined by Protocol contracts, enabling backing-service substitution without modifying feature code. ADR-0048 Boundary 7 requires the injection surface to expose Protocol types. However, no Tier-2 standard defines WHICH services require Protocol contracts, HOW Protocol contracts must be structured, or the migration path for existing concrete-only services. Currently, 5 of 14 feature-facing infrastructure services have Protocol contracts (DirectoryProvider, RetryStore, RetryProcessor, ResponseChannel, BackgroundJobRegistry). The remaining 9 are concrete classes exposed directly through the injection boundary. The architecture was originally inspired by Backstage's shared service layer model (ServiceRef + ServiceFactory), where every service has an interface type and a swappable factory. The Python/FastAPI equivalent is Protocol + `@lru_cache` provider function. This standard codifies the contract requirements for the sre-bot infrastructure layer.
- Business/operational drivers:
 - Enable backing-service substitution (e.g., DynamoDB -> RDS, Google Workspace -> Entra ID) without modifying feature code.
 - Provide clear classification of infrastructure services: which need Protocol contracts, which are shared utilities, which are implementation details.
 - Define the Protocol -> Implementation -> Provider pattern as the canonical service architecture.
 - Establish migration priorities for existing concrete-only services.
 - Codify the client-layer boundary: when direct client access is acceptable vs. when domain-level services should be used.
- Constraints:
 - ADR-0045 Principle 6 mandates Protocol contracts for feature-facing services.
 - ADR-0048 Boundary 2 requires Protocol types at the injection surface where applicable.
 - ADR-0048 Boundary 7 requires features to depend on Protocols, not concrete classes.
 - ADR-0056 Standard 3 centralizes infrastructure providers in `providers.py`.
 - ADR-0076 Standard 1 permits shared value types across infrastructure packages.
 - Existing services are deployed and in use; migration must be incremental.
- Non-goals:
 - This record does not define specific Protocol method signatures for individual services.
 - This record does not define the interaction provider architecture (governed by ADR-0059).
 - This record does not define settings structure or provider composition mechanics (governed by ADR-0055 and ADR-0056).

## Decision

- Chosen approach: Classify all infrastructure services into three tiers (contract-required, shared utility, implementation detail), define the canonical Protocol contract pattern, codify the client-layer boundary, and establish migration priorities.
- Why this approach: Classification provides clear guidance for each service. The Protocol contract pattern is already proven in the codebase (DirectoryProvider, RetryStore). Migration priorities allow incremental adoption without disrupting active development.

### Standard 1: Infrastructure Service Classification

Every infrastructure service falls into one of three categories:

#### Category A: Contract-Required Services

Services that abstract over backing services and are consumed by feature packages through the injection boundary. These MUST have Protocol contracts.

**Criteria for Category A:**
- The service abstracts over an external backing service (database, API, cloud provider).
- Feature packages depend on the service and would need to change if the backing service changed.
- The service has at least one plausible alternative implementation (even if not currently built).

**Current Category A services:**

| Service | Protocol Exists? | Backing Service | Migration Priority |
|---------|-----------------|-----------------|-------------------|
| `DirectoryProvider` | Yes | Google Workspace Directory | - (complete) |
| `RetryStore` | Yes | DynamoDB | - (complete) |
| `RetryProcessor` | Yes | Feature-specific | - (complete) |
| `ResponseChannel` | Yes | Platform-specific | - (complete) |
| `BackgroundJobRegistry` | Yes | Scheduler | - (complete) |
| `StorageService` | **No** | DynamoDB | **P0** - stated design goal is storage-agnostic |
| `IdentityService` | **No** | JWT + platform resolvers | **P1** - identity resolution could have multiple backends |
| `AuditTrailService` | **No** | DynamoDB (via StorageService) | **P1** - audit backend could change |
| `NotificationService` | **No** | GC Notify / platform channels | **P2** - channels are abstracted; dispatcher could follow |
| `IdempotencyService` | **No** | DynamoDB | **P3** - infrastructure concern, lower swap probability |

> **Revision (2026-04-29 - Platform Services Assessment):** `PlatformService` was removed from Category A. Per-platform services (`SlackService`, `TeamsService`) are classified as Category C (infrastructure implementation details) because each platform's API surface is fundamentally different - no shared Protocol is appropriate. See ADR-0078 (Platform Services Architecture).

#### Category B: Shared Utility Services

Services that provide cross-cutting utility functions consumed by both infrastructure and feature code. These are concrete types with no alternative implementation expected. Protocol contracts are NOT required.

| Service | Rationale |
|---------|-----------|
| `OperationResult[T]` / `OperationStatus` | Universal result type - shared vocabulary, not a swappable service |
| `EventDispatcher` | Internal event bus - implementation is fixed |
| `TranslationService` | i18n is internal; unlikely to swap |
| `CommandService` | Command framework is tightly coupled to the registration model |
| `ResilienceService` | Circuit breaker / retry orchestration - infrastructure concern |

#### Category C: Implementation Details

Concrete implementations that should NOT be directly consumed by feature packages. These are internal to the infrastructure layer and accessed only through Category A Protocols or through the composition root.

| Component | Consumed Through | Feature Access |
|-----------|-----------------|----------------|
| `DynamoDBClient` | `StorageService` (Category A) | Should not import directly |
| `GoogleWorkspaceClients` | `DirectoryProvider` (Category A) | Should not import directly |
| `DynamoDBRetryStore` | `RetryStore` Protocol | Should not import directly |
| `GoogleDirectoryProvider` | `DirectoryProvider` Protocol | Should not import directly |
| `SlackService` | Infrastructure-owned (`infrastructure/slack/`) | Category C - concrete, typed wrapper around Slack SDK. No Protocol (platform APIs are asymmetric). Features receive via hookspec injection, not DI alias. See ADR-0078. |
| `TeamsService` | Infrastructure-owned (`infrastructure/teams/`) | Category C - concrete, typed wrapper around Teams Bot Framework SDK. No Protocol. See ADR-0078. |

**Pragmatic exception for client facades:** Feature packages that need domain-specific backing-service operations not covered by a Category A service may import typed client facades (`AWSClients`, `SlackClientFacade`, `TeamsClientFacade`) directly through the injection boundary. This is a documented exception, not the default pattern. Each such usage must be assessed for whether a Category A domain service should be created instead.

### Standard 2: Protocol Contract Pattern

Category A services must follow this canonical pattern:

#### 2.1 Protocol Definition

The Protocol must be defined in the service's package, not in a separate types package:

```python
# infrastructure/storage/protocol.py
from typing import Protocol, runtime_checkable

@runtime_checkable
class StorageService(Protocol):
 """Storage operations abstracted over the backing store."""

 def put(self, table: str, item: dict[str, Any]) -> OperationResult[None]: ...
 def get(self, table: str, key: dict[str, Any]) -> OperationResult[dict[str, Any]]: ...
 def query(self, table: str, **kwargs: Any) -> OperationResult[list[dict[str, Any]]]: ...
 def delete(self, table: str, key: dict[str, Any]) -> OperationResult[None]: ...
```

#### 2.2 Concrete Implementation

The implementation class must satisfy the Protocol structurally (duck typing) or explicitly:

```python
# infrastructure/storage/dynamodb.py
class DynamoDBStorageService:
 """DynamoDB-backed storage implementation."""

 def __init__(self, dynamodb: DynamoDBClient) -> None:
 self._dynamodb = dynamodb

 def put(self, table: str, item: dict[str, Any]) -> OperationResult[None]:
 # DynamoDB-specific implementation
 ...
```

#### 2.3 Provider Function

The provider in `providers.py` must return the Protocol type, not the concrete type:

```python
# infrastructure/services/providers.py
@lru_cache(maxsize=1)
def get_storage_service() -> StorageService: # Returns Protocol type
 from infrastructure.storage.dynamodb import DynamoDBStorageService
 return DynamoDBStorageService(dynamodb=get_aws_clients().dynamodb)
```

#### 2.4 Dependency Alias

The alias in `dependencies.py` must use the Protocol type:

```python
# infrastructure/services/dependencies.py
StorageServiceDep = Annotated[StorageService, Depends(get_storage_service)]
```

#### 2.5 Protocol Rules

| # | Rule | Rationale |
|---|------|-----------|
| P1 | Protocols must be `@runtime_checkable` | Enables `isinstance` checks in test assertions and factory validation. **Caveat (PEP 544):** `@runtime_checkable` checks method existence only, not signatures or return types. Static type checking via mypy is the primary enforcement tool for Protocol compliance; `isinstance` is a convenience for test assertions, not a substitute for static analysis. |
| P2 | Protocol methods must use `OperationResult[T]` return types for fallible operations | Uniform error handling (ADR-0050) |
| P3 | Protocol methods must not expose backing-service-specific types (e.g., DynamoDB AttributeValue, Google API Resource) | Implementation agnosticism |
| P4 | Protocol definitions must live in the service's package (e.g., `infrastructure/storage/protocol.py`), not in a shared types package | Ownership follows code; prevents premature abstraction |
| P5 | Protocol names should describe the capability, not the implementation (e.g., `StorageService`, not `DynamoDBService`) | Implementation-agnostic naming |
| P6 | All Protocol methods must have type annotations on all parameters and return types | Type safety and IDE support |

### Standard 3: Client-Layer Boundary

Client packages (`infrastructure/clients/aws/`, `infrastructure/clients/google_workspace/`, `infrastructure/clients/maxmind/`) are Category C implementation details. They wrap external SDK calls and return `OperationResult[T]`.

#### 3.1 Default Rule

Feature packages should consume Category A domain services (StorageService, DirectoryProvider, IdentityService), not raw client facades.

#### 3.2 Pragmatic Exception

Feature packages may import typed client facades through the injection boundary when ALL of the following apply:

1. The operation is domain-specific (e.g., AWS IdentityStore for access sync, GuardDuty for SRE ops).
2. No Category A service exists that covers the operation.
3. Creating a Category A service for this single use would be premature abstraction.

When the pragmatic exception is exercised:
- The feature must document the coupling (a code comment or README note identifying the concrete dependency).
- If a second feature needs the same client operation, a Category A service should be created.
- The client facade must still be obtained through the injection boundary (`AWSClientsDep`), never by direct import.

#### 3.3 Current Client Exposure Assessment

| Client | Current Status | Recommendation |
|--------|---------------|----------------|
| `AWSClients` facade | Exposed via `AWSClientsDep` | Retain - pragmatic exception for domain-specific AWS operations |
| `GoogleWorkspaceClients` facade | Exposed via `GoogleWorkspaceClientsDep` | Phase out - features should use `DirectoryProvider` and any new domain services |
| `MaxMindClient` | Exposed via `MaxMindClientDep` | Retain - single consumer (`geolocate`), pragmatic exception |
| `SlackClientFacade` | Exposed via `SlackClientDep` | Retain - platform-specific operations require direct access |
| `TeamsClientFacade` | Exposed via `TeamsClientDep` | Retain - platform-specific operations require direct access |
| `DiscordClientFacade` | Exposed via `DiscordClientDep` | Retain - platform-specific operations require direct access |

### Standard 4: Test Override Pattern

Protocol contracts enable clean test overrides through FastAPI's dependency override mechanism:

```python
# Test fixture
class FakeStorageService:
 """In-memory storage for testing."""
 def __init__(self) -> None:
 self._data: dict[str, dict[str, Any]] = {}

 def put(self, table: str, item: dict[str, Any]) -> OperationResult[None]:
 key = str(item.get("pk", ""))
 self._data.setdefault(table, {})[key] = item
 return OperationResult.success()

 # ... other Protocol methods

@pytest.fixture
def fake_storage() -> FakeStorageService:
 store = FakeStorageService()
 app.dependency_overrides[get_storage_service] = lambda: store
 yield store
 app.dependency_overrides.pop(get_storage_service, None)
```

**Rules:**
- Test doubles must satisfy the Protocol (verified by `isinstance` check if `@runtime_checkable`).
- Test doubles must be minimal - only the methods exercised by the test under coverage need real implementations.
- Test doubles must not import the concrete implementation they replace.

### Standard 5: Migration Path

Existing Category A services that lack Protocol contracts must be migrated incrementally. Each migration follows these steps:

1. **Create Protocol** - define `protocol.py` in the service's package with the current public interface.
2. **Rename implementation** - rename the current class to indicate its backing service (e.g., `StorageService` -> `DynamoDBStorageService`).
3. **Update provider** - change return type annotation to the Protocol.
4. **Update dependency alias** - change the `Annotated` type to use the Protocol.
5. **Verify** - ensure all feature code compiles against the Protocol type, not the concrete class. Run full test suite.
6. **Create test double** - add in-memory or fake implementation for test fixtures.

**Migration priority and sequencing:**

| Priority | Service | Sequencing Notes |
|----------|---------|-----------------|
| P0 | StorageService | Foundational - other services (AuditTrailService, IdempotencyService) depend on storage |
| P1 | IdentityService | Independent - can be migrated in parallel with P0 |
| P1 | AuditTrailService | Depends on StorageService Protocol being complete first |
| P2 | NotificationService | Independent - channels already partially abstracted |
| P3 | IdempotencyService | Depends on StorageService Protocol being complete first |

> **Note (2026-04-29):** `PlatformService` was removed from migration priorities. Per-platform services are Category C and do not require Protocol contracts. See Category A table revision note.

**Migration constraint:** Each migration must be an independently deployable change. No migration may break existing tests or require simultaneous changes across multiple services.

## Alternatives Considered

1. Require Protocol contracts for ALL infrastructure services (Categories A, B, and C):
 - Pros: Maximum uniformity; every service is swappable.
 - Cons: Premature abstraction for services with no plausible alternative implementation (EventDispatcher, TranslationService). Increases ceremony without proportional benefit.
 - Why not chosen: Protocol contracts add value only when the service abstracts over a swappable backing service. Shared utilities (Category B) are concrete by nature.

2. No service classification - let each service team decide:
 - Pros: Maximum flexibility; no governance overhead.
 - Cons: Inconsistent contract surfaces; some services have Protocols, others don't, with no principled reason. Features can't rely on swappability.
 - Why not chosen: ADR-0045 P6 mandates Protocol contracts. A standard without classification provides no actionable guidance.

3. Create a single `infrastructure/protocols/` package containing all Protocol definitions:
 - Pros: Single import location for all service contracts; easy to discover.
 - Cons: Separates the Protocol from its implementation, creating ownership ambiguity. Changes to a Protocol require editing a package that doesn't own the service. Violates ownership-follows-code (ADR-0047 P2).
 - Why not chosen: Protocols must live in the service's own package. A separate protocols package would create the same problems as a shared types package.

4. Use abstract base classes (ABC) instead of Protocol:
 - Pros: Enforcement at inheritance time; explicit subclass relationship.
 - Cons: Requires `isinstance` type hierarchy; couples implementations to the base class. Python community convention has moved toward structural subtyping (Protocol) for service contracts. ABCs are appropriate for shared implementation (mixins), not for service interfaces.
 - Why not chosen: Protocol (PEP 544) is the modern Python pattern for service interfaces. ABCs create unnecessary coupling between the contract and its implementations.

5. Defer all Protocol migration until modules are migrated to packages:
 - Pros: Avoids intermediate states; clean cut when modules migrate.
 - Cons: Blocks the primary architectural goal (swappable services) on an unrelated migration (modules -> packages). StorageService Protocol doesn't depend on module migration.
 - Why not chosen: Protocol migration and module migration are independent concerns. Protocol contracts should be added as soon as the service interface is stable.

## Consequences

- Positive impacts:
 - Every feature-facing infrastructure service will have an explicit, swappable contract.
 - Features depend on stable Protocol interfaces, not volatile implementation details.
 - Test doubles are clean Protocol satisfiers, not mock-heavy patches of concrete classes.
 - The classification (A/B/C) provides clear guidance for new infrastructure services.
 - Client-layer boundary with pragmatic exception balances purity with practicality.
- Tradeoffs accepted:
 - Category B services (shared utilities) do not get Protocol contracts. This is accepted because they have no plausible alternative implementations.
 - The pragmatic exception for client facades means some features will have direct concrete dependencies. This is accepted because the alternative (creating domain services for every possible operation) is premature abstraction.
 - Protocol migration is incremental, meaning the codebase will temporarily have a mix of Protocol-backed and concrete-only services. This is accepted because incremental migration is safer than a big-bang rewrite.
- Risks introduced:
 - Protocol method signatures may not perfectly match the current concrete class interfaces, requiring minor refactoring during migration.
 - New team members may skip Protocol creation for new Category A services. Mitigation: code review checklist item.
 - The pragmatic exception for clients may be overused. Mitigation: the "two consumers" trigger for creating a Category A service.

## Compliance and Boundaries

- Package/infrastructure boundary impact: Standard 1 classifies which services require Protocol contracts. Standard 3 defines the client-layer boundary. Together they determine what feature packages may and may not import from infrastructure.
- Type boundary impact: Standard 2 mandates Protocol types for Category A services. This is a type-boundary decision that ADR-0065 should reference.
- Provider composition impact: Standard 2.3 requires provider return types to use Protocol types. ADR-0056 Standard 1 should be amended to reference this requirement.
- Testing impact: Standard 4 defines the test override pattern using Protocol-based test doubles. This replaces mock-heavy patterns with structural subtyping.

## Best-Practice Revalidation

- Revalidation date: 2026-04-29
- Sources rechecked:
 1. PEP 544 (Protocols: Structural subtyping): Defines `typing.Protocol` as the mechanism for structural subtyping in Python. `@runtime_checkable` enables isinstance checks. This is the Python-native way to define service interfaces.
 2. Backstage Backend Services Architecture: ServiceRef (typed reference) + ServiceFactory (construction) + DI container (backend instance) is the direct TypeScript analog. Python equivalent: Protocol + `@lru_cache` provider + composition root. Every Backstage core service has an interface type (ServiceRef) - our standard mirrors this for Python.
 3. Hexagonal Architecture / Ports and Adapters (Cockburn): Application core depends on port interfaces (Protocols), not adapter implementations (concrete classes). Adapters are constructed at the composition root and injected through ports. Directly supports Standards 1-3.
 4. Cosmic Python - Repository Pattern (Chapter 2): Defines repository Protocols for persistence, with concrete implementations (SQLAlchemy, in-memory) assembled at bootstrap. Exactly the StorageService pattern we're implementing.
 5. FastAPI Dependency Overrides: `app.dependency_overrides[provider_function] = lambda: fake_impl` is the framework-native mechanism for swapping service implementations in tests. Directly supports Standard 4.
 6. Martin Fowler - "Role Interface" (2006): Clients should depend on role interfaces tailored to their needs, not broad service interfaces. Supports P5 (capability-named Protocols) and narrow-slice injection.
- Alignment summary:
 - Protocol for service contracts aligns with PEP 544, Hexagonal Architecture ports, Backstage ServiceRef, and Cosmic Python repository pattern.
 - `@runtime_checkable` aligns with Python testing conventions and FastAPI dependency override patterns.
 - Service classification (A/B/C) aligns with Hexagonal Architecture's distinction between ports (Category A), application services (Category B), and adapters (Category C).
 - Client-layer boundary aligns with Ports and Adapters - clients are adapters that should be hidden behind ports.
- Intentional deviations:
 - Category B services (shared utilities) do not get Protocol contracts. This deviates from Backstage (where even logging has a ServiceRef) because Python's `structlog` and similar libraries are not meaningfully swappable - the abstraction cost exceeds the swap probability.

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: New Tier-2 standard implementing ADR-0045 Principle 6 and ADR-0048 Boundary 7. Classifies infrastructure services, defines the Protocol contract pattern, codifies the client-layer boundary, and establishes the migration path.
- Follow-up actions:
 - Amend ADR-0056 to reference Protocol return type requirement (Standard 2.3 of this ADR).
 - Execute P0 migration: StorageService Protocol.
 - Update migration map with ADR-0077 row.
 - Add code review checklist item for Protocol contract requirement on new Category A services.

## Source References

1. Source title: PEP 544 - Protocols: Structural subtyping (static duck typing)
 - URL: https://peps.python.org/pep-0544/
 - Publisher/maintainer: Python Software Foundation
 - Accessed date (YYYY-MM-DD): 2026-04-29
 - Relevance summary: Defines the language mechanism for service contracts used throughout this standard.

2. Source title: Backstage Backend Services Architecture
 - URL: https://backstage.io/docs/backend-system/architecture/services
 - Publisher/maintainer: Backstage / CNCF
 - Accessed date (YYYY-MM-DD): 2026-04-29
 - Relevance summary: Original mental model for the shared service layer. ServiceRef + ServiceFactory = Protocol + provider function. Every core service has an interface type.

3. Source title: Hexagonal Architecture (Ports and Adapters)
 - URL: https://alistair.cockburn.us/hexagonal-architecture/
 - Publisher/maintainer: Alistair Cockburn
 - Accessed date (YYYY-MM-DD): 2026-04-29
 - Relevance summary: Ports (Protocols) define the application's required interfaces; adapters (concrete implementations) satisfy them. Adapters are assembled at the composition root.

4. Source title: Architecture Patterns with Python - Chapter 2: Repository Pattern
 - URL: https://www.cosmicpython.com/book/chapter_02_repository.html
 - Publisher/maintainer: Harry Percival, Bob Gregory
 - Accessed date (YYYY-MM-DD): 2026-04-29
 - Relevance summary: Demonstrates the Protocol -> concrete implementation -> bootstrap assembly pattern for persistence services in Python. Directly analogous to our StorageService migration.

5. Source title: FastAPI - Testing Dependencies with Overrides
 - URL: https://fastapi.tiangolo.com/advanced/testing-dependencies/
 - Publisher/maintainer: Sebastian Ramirez / FastAPI
 - Accessed date (YYYY-MM-DD): 2026-04-29
 - Relevance summary: `app.dependency_overrides` is the framework-native mechanism for swapping service implementations in tests, directly supporting Standard 4.

6. Source title: Martin Fowler - Role Interface
 - URL: https://martinfowler.com/bliki/RoleInterface.html
 - Publisher/maintainer: Martin Fowler
 - Accessed date (YYYY-MM-DD): 2026-04-29
 - Relevance summary: Clients should depend on role-specific interfaces, not broad service classes. Supports Protocol naming conventions (P5) and narrow interface design.

7. Source title: ADR-0045 - Core Architectural Principles (Principle 6)
 - URL: docs/decisions/adr/0045-core-architectural-principles.md
 - Publisher/maintainer: SRE Team
 - Accessed date (YYYY-MM-DD): 2026-04-29
 - Relevance summary: Parent Tier-1 principle mandating Protocol contracts for feature-facing infrastructure services.

8. Source title: ADR-0048 - Dependency and Import Boundary Constitution (Boundaries 2, 7)
 - URL: docs/decisions/adr/0048-dependency-and-import-boundary-constitution.md
 - Publisher/maintainer: SRE Team
 - Accessed date (YYYY-MM-DD): 2026-04-29
 - Relevance summary: Parent Tier-1 constitution requiring Protocol types at the injection surface and features depending on Protocols, not concrete classes.

## Implementation Guidance

- Required changes:
 - Amend ADR-0056 Standard 1 or add new standard referencing Protocol return type requirement.
 - Execute Protocol migrations in priority order (P0: StorageService first).
 - Add migration Tier-5 ADRs for each Protocol migration (similar to ADR-0070 through ADR-0075 pattern).
- Validation and quality gates:
 - `mypy --strict` should verify that feature code depends on Protocol types, not concrete classes.
 - `isinstance(service, ProtocolType)` checks in provider functions validate structural conformance.
 - Each Protocol migration must pass full test suite before and after.
- Test strategy and acceptance criteria impact:
 - Each Protocol migration must include a test double (in-memory or fake implementation).
 - Existing tests using mock patches of concrete classes should be migrated to Protocol-based test doubles.

## Change Log

- 2026-04-29: Created. Establishes service classification (A/B/C), Protocol contract pattern, client-layer boundary, test override pattern, and migration priorities. Root cause: Backstage mental model reconciliation identified that the infrastructure layer lacked Protocol contracts for 9 of 14 feature-facing services, and no ADR articulated the layer's role as a swappable service platform. Backstage's ServiceRef + ServiceFactory pattern maps to Python Protocol + @lru_cache provider; this ADR codifies that mapping. See ADR-0045 P6 for the governing principle and ADR-0076 for the companion intra-layer import standard.
- 2026-04-29: Platform Services Assessment update. `PlatformService` removed from Category A (was P2). Per-platform services (`SlackService`, `TeamsService`) added to Category C - each platform's API surface is fundamentally different; no shared Protocol is appropriate. Migration priority table updated (P2 PlatformService removed). See the 2026-04-29 Platform Services Assessment findings and ADR-0078 (Platform Services Architecture).
