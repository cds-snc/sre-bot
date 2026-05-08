---
title: "Layered Architecture"
status: Draft
type: Principle
tier: Tier-1
governance_domain: [application]
concerns: [architecture]
constrained_by: [decision-record-governance.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Layered Architecture

## Context and Problem Statement

Application code evolves when requirements change. Infrastructure choices (which database, which messaging platform, which secrets manager) change as operational constraints shift or as better alternatives emerge. When these two axes of change are tightly coupled — when feature code directly imports cloud provider SDKs or database clients — changing either axis forces rewrites across the codebase.

The core problem: **changes in infrastructure must not cascade into feature code, and feature requirements must not force infrastructure reimplementation.** This decoupling is achieved through strict layer separation with unidirectional dependency flow.

**Constraints:**

- The application is a modular Python FastAPI system where multiple features and cross-cutting concerns coexist.
- Features must be independently testable without external service connectivity.
- Infrastructure components must be swappable — a change from one database to another, or one messaging system to another, must not require rewrites in feature packages.
- The application is stateless: each process handles requests independently with no shared in-memory state between processes. Durable state lives in external backing services.

**Non-goals:**

- This record does not prescribe how infrastructure services are internally organized or what external systems they wrap.
- This record does not define the dependency injection mechanism or type conventions at the Protocol boundary — those are governed by separate decisions.

## Considered Options

**Option 1: No formal layer separation — features import directly from infrastructure**

Features import cloud provider SDKs or raw client facades directly. Infrastructure concerns are scattered throughout the codebase.

**Option 2: Strict layered architecture with a Protocol-based boundary and two distinct integration paths**

The application is organized into two layers — Application and Infrastructure — with a Protocol boundary between them. Infrastructure internally structures: a composition root, composed services, and raw client facades.

Composed services and raw client facades are distinct concepts:

- A **composed service** defines a stable, capability-focused Protocol (`StorageService`, `DirectoryProvider`) and hides a provider-specific concrete implementation behind it. The composed service IS the provider-swappability boundary. Swapping the backing provider (e.g., DynamoDB → Redis for storage) means replacing the concrete implementation and its raw client — neither the Protocol nor any feature code changes.
- A **raw client facade** (`AWSClients`, `GoogleWorkspaceClients`) is vendor-specific connectivity — pre-authenticated SDK access for a specific external platform. Raw client facades are not abstractions; they ARE the concrete vendor layer. They serve composed service concrete implementations and, for domain-specific integrations, feature-owned concrete adapters.

Feature code accesses shared capabilities through shared service Protocols; feature code accesses domain-specific external systems through feature-owned Protocols satisfied by feature-owned adapters. Both paths enforce the same invariant: feature domain and service logic never holds a reference to a concrete infrastructure type.

## Decision Outcome

**Chosen: Option 2 — Strict layered architecture with a Protocol-based boundary and two distinct integration paths.**

### Layer 1: Application

**Responsibility:** Domain logic, request routing, task scheduling, event handling, and platform interaction.

**Composition:** Feature packages under `app/packages/`. Each feature package is an independent vertical slice — it groups its own routes, domain models, domain services, settings, and providers. Feature packages own their own `providers.py` for package-local services (domain services, repositories, runtime configuration).

Feature packages integrate with the outside world through two distinct paths, depending on whether the external system is a shared cross-feature concern or a feature-specific integration:

#### Path A: Shared Infrastructure Services

For capabilities shared across multiple features — queuing, idempotency, identity, storage, eventing — the infrastructure layer owns the Protocol, the implementation, and the composition. Feature code receives these via `Annotated[Protocol, Depends(get_x)]` in HTTP route handlers, or via `get_x()` direct provider calls in pluggy hookimpls and background jobs. The composition root (`app/infrastructure/services/providers.py`) is the source of all shared service providers.

#### Path B: Feature-Owned Outbound Adapters

For external systems that only one feature consumes, and whose integration logic is domain-specific to that feature, the feature package owns the Protocol **and** the concrete adapter. This is the Separated Interface pattern (Fowler) and the Outbound Port + Adapter from Hexagonal Architecture (Cockburn): the consuming package defines what it needs; the adapter satisfies it.

Examples of this pattern: a sync feature provisioning users into a cloud identity store, or a feature reconciling access policies against a platform-specific API. These integrations are too specific and too feature-coupled to be expressed as general-purpose infrastructure services.

**Rules for feature-owned outbound adapters:**

- The feature defines the Protocol in its own `adapters/__init__.py`. This Protocol describes the operations the feature's domain logic needs — not the external API's interface.
- One or more concrete adapter classes implement that Protocol in `adapters/<provider>.py`. Concrete adapters receive infrastructure raw clients via constructor injection, wired by the feature's `providers.py`. Concrete adapters may hold and use raw client types — they *are* the infrastructure boundary for that integration.
- The feature's service layer operates only against the Protocol. Domain and service code must never import a concrete adapter class, a raw infrastructure client, or any cloud SDK type directly.
- Each concrete adapter must be accompanied by an in-process stub implementing the full Protocol, enabling local development and testing without external connectivity.
- A feature-owned adapter is promoted to a shared infrastructure service when a second independent feature needs the same external system, or when the integration gains operational ownership requirements (SLA, monitoring, security) that belong to the platform layer.

**Rules that apply to both paths:**

- Feature packages must not import from other feature packages. Cross-feature coordination uses shared infrastructure services (event dispatcher, queue) or domain events — never direct imports.
- Package-local `providers.py` files are private to the package. Infrastructure code must never import from them.

### Layer 2: Infrastructure

**Responsibility:** Everything the application layer needs to consume — composed services, raw client facades, configuration, platform adapters, and the composition root that wires them together.

Infrastructure is internally structured into three tiers, but this structure is private. Feature code never sees below the Protocol surface.

#### 2a. Composition Root (`app/infrastructure/services/providers.py`)

The single location where cross-service infrastructure dependencies are assembled. Provider functions here compose multiple infrastructure services (e.g., `NotificationService` = `IdempotencyService` + `ResilienceService` + `NotifySettings`). Provider functions for Category A services return Protocol types, not concrete implementations.

Rules:

- Cross-service composition (where one infrastructure service depends on another) must occur here, not scattered across service modules.
- Self-contained infrastructure providers — those that depend only on their own settings — may live in their own service module and be re-exported through `infrastructure/services/__init__.py`.

#### 2b. Composed Services (`app/infrastructure/<service>/`)

Capability abstractions that define a stable, provider-agnostic Protocol and hide a vendor-specific concrete implementation behind it. A composed service answers the question "what capability does this feature need?" — not "which vendor provides it?" Examples: `StorageService` (put, get, query — no DynamoDB semantics visible), `DirectoryProvider` (get_user, list_groups — no Google API semantics visible).

Each composed service has two parts:

- **The Protocol** (`protocol.py`): the stable capability interface that features depend on. The Protocol is defined in terms of what the feature needs, not how the vendor implements it. It does not change when the backing provider changes.
- **The concrete implementation**: the vendor-specific secondary adapter that satisfies the Protocol. It uses raw client facades and applies SDK-specific error handling, type translation, and retry logic. This is the layer that changes when a provider is swapped. Examples: `DynamoDBStorageService` (backing `StorageService`), `GoogleDirectoryProvider` (backing `DirectoryProvider`).

Composed services are the provider-swappability boundary. If the storage backend changes from DynamoDB to Redis: implement `RedisStorageService`, supply a `RedisClient` facade, update one line in `providers.py`. No Protocol changes. No feature code changes.

Category classification applies to how features may access the service:

- Category A: Protocol-required — feature code depends only on the Protocol, never on the concrete implementation. All shared-capability services are Category A.
- Category B: Shared utility where a concrete reference is acceptable in specific construction contexts.
- Category C: Implementation detail — internal to a composed service, never exposed to feature packages.

Rules:

- Category A services must expose `protocol.py` defining the `typing.Protocol` interface. The concrete implementation satisfies this protocol; feature code only sees the protocol type.
- The concrete implementation may import and use raw client facades — it is the infrastructure boundary for that composed service.
- The protocol is the port; the concrete implementation is the secondary adapter (in Ports and Adapters terminology).

#### 2c. Raw Client Facades (`app/infrastructure/clients/`)

Vendor-specific, pre-authenticated SDK wrappers that centralize authentication, session management, and SDK initialization for a specific external platform. `AWSClients` IS AWS — it is not an abstraction over cloud providers; it is the concrete AWS connectivity layer, grouping `DynamoDBClient`, `IdentityStoreClient`, `SsoAdminClient`, and others under one authenticated session. `GoogleWorkspaceClients` IS Google Workspace.

Raw client facades are not classified under Category A/B/C. That classification describes access patterns between features and composed services. Raw clients are not composed services — they are infrastructure primitives that live below the composed service layer and supply the concrete connectivity that concrete implementations depend on.

Raw client facades serve two consumers, both strictly via constructor injection:

1. **Concrete implementations of composed services** (the typical path): `DynamoDBStorageService` receives a `DynamoDBClient` (via `AWSClients`) to back the `StorageService` Protocol. If the provider changes, the concrete implementation and its raw client both change; the Protocol and features are untouched.
2. **Feature-owned concrete adapters (Path B)**: `AwsIdentityCenterAdapter` receives `AWSClients` to make domain-specific Identity Store and SSO Admin API calls for which no shared composed service exists. The raw client plays the same role in both cases — vendor-specific connectivity — regardless of whether it serves infrastructure or a feature adapter.

Rules:

- Raw client facades are never imported by feature domain logic, service functions, or route handlers. The only permitted appearance in feature packages is in concrete adapter files (`adapters/<provider>.py`), received via constructor injection from the feature's `providers.py`.
- Client facades handle authentication, session management, and SDK initialization only. They do not implement domain logic, capability translation, or error normalization — that belongs in the layer above (composed service or feature adapter).

## Unidirectional Dependency Flow

The two integration paths produce two dependency flows, both strictly unidirectional:

**Path A — Shared infrastructure service:**

```
app/packages/<feature>/service.py
  ↓ Annotated[SharedProtocol, Depends(get_x)]
app/infrastructure/services/providers.py       (composition root)
  ↓
app/infrastructure/<service>/service.py        (composed service, implements SharedProtocol)
  ↓
app/infrastructure/<service>/adapters/         (SDK translation)
  ↓
app/infrastructure/clients/                    (raw client facades)
  ↓
External service
```

**Path B — Feature-owned outbound adapter:**

```
app/packages/<feature>/service.py
  ↓ FeatureProtocol (defined by the feature in adapters/__init__.py)
app/packages/<feature>/adapters/<provider>.py  (feature-owned concrete adapter)
  ↓ constructor injection via feature providers.py
app/infrastructure/clients/                    (raw client facades, injected — not imported by service.py)
  ↓
External service (feature-specific)
```

**The invariant in both paths:** Feature *domain and service code* never holds a reference to a concrete infrastructure type. In Path A, the Protocol is defined by infrastructure and the implementation is entirely hidden. In Path B, the Protocol is defined by the feature, and the concrete adapter — which does hold the raw client — is equally hidden from `service.py`. The adapter is the boundary, not a consumer across it.

**Where provider swappability lives:** In Path A, the swappability boundary is the composed service Protocol. If the backing provider changes (e.g., DynamoDB → Redis for storage), only the concrete composed service implementation and its raw client facade change — the Protocol, `providers.py` provider signature, and all feature code remain untouched. Raw client facades are the concrete vendor layer that gets replaced; they are not themselves the abstraction boundary. In Path B, swappability is at the feature's own Protocol (test stub vs. real provider). There is no infrastructure-level provider swappability for domain-specific integrations — the integration is vendor-specific by nature.

**Reverse imports are prohibited at every level:**

- Feature service and domain code must not import concrete infrastructure classes, raw client facades, or cloud SDK types.
- Feature concrete adapters (`adapters/<provider>.py`) may import raw client facades via constructor injection only — they are the infrastructure boundary for that integration.
- Infrastructure code must not import from `app/packages/`.
- Package-local `providers.py` files must not be imported by infrastructure code.

**Promotion rule:** When a second feature needs the same external system currently served by a feature-owned adapter, the Protocol and at least one concrete implementation are extracted to `app/infrastructure/<service>/`, a shared Protocol is defined, and both features consume it via Path A. The integration has become shared infrastructure.

## Consequences

**Positive:**

- Changes to infrastructure internals (backing provider swap, SDK upgrade, adapter rewrite) never propagate into feature code. The Protocol surface is stable.
- Swapping a provider (e.g., replacing `DynamoDBStorageService` with `RedisStorageService`) requires changes only to the concrete composed service implementation and its raw client facade. No Protocol changes. No feature code changes. No test changes at the feature layer.
- Feature code is testable in isolation by substituting Protocol stubs via `app.dependency_overrides[get_x]` — no cloud credentials, no real clients required.
- Raw client facades are reusable across multiple concrete service implementations without code duplication.
- Adding a new shared infrastructure capability requires authoring a Protocol, a concrete implementation, and a provider function — none of which touches any existing feature package.

**Tradeoffs accepted:**

- All infrastructure capabilities consumed by features require an explicit Protocol definition, whether defined by infrastructure (Path A) or by the feature (Path B). This is necessary overhead — without it, the isolation boundary is not enforceable.
- Feature developers must determine which path applies for each external integration: shared capability (Path A) vs. domain-specific integration (Path B).
- Package-local `providers.py` files require `lru_cache` discipline and `cache_clear()` hygiene in tests.
- Feature-owned adapters must include an in-process stub for every Protocol they define. This is required for test isolation and local development.

**Risks:**

- Protocol definitions that are shaped around a specific SDK API (rather than around application need) expose infrastructure coupling through the interface itself, defeating the purpose of the abstraction.
- Without static import analysis tooling, cross-layer violations (feature importing concrete client, infra importing feature code) may go undetected until code review.

## Confirmation

Compliance is verified by:

- Code review (Path A): feature service and domain code imports only Protocol types and provider functions from `infrastructure.services`. No imports from `infrastructure.clients`, concrete service classes, or other feature packages.
- Code review (Path B): feature service and domain code imports only the feature's own Protocol from `adapters/__init__.py`. The concrete adapter file (`adapters/<provider>.py`) may import raw client types, but that type must not appear in `service.py` or `models.py`.
- Code review (both paths): infrastructure modules must not import from `app/packages/`.
- Static analysis: import-linter configured with forbidden import paths (e.g., feature service modules → infrastructure concrete classes; infrastructure modules → feature packages) catches violations automatically.
- Test isolation: each feature's unit tests pass using `app.dependency_overrides` (Path A) or Protocol-conformant in-process stubs (Path B), with no real infrastructure connections or cloud credentials.

## Source References

1. Clean Architecture
   - URL: <https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html>
   - Accessed: 2026-05-08
   - Relevance: Establishes that "source code dependencies can only point inward" and that outer rings (frameworks, drivers, details) must never leak into inner rings (business logic). Directly maps to the unidirectional flow constraint.

2. Hexagonal Architecture / Ports and Adapters — Alistair Cockburn
   - URL: <https://alistair.cockburn.us/hexagonal-architecture/>
   - Accessed: 2026-05-08
   - Relevance: Defines the Ports and Adapters pattern: the application core communicates with external systems through abstract ports; concrete adapters implement those ports for specific technologies. Directly maps to Protocol-based service contracts in the service layer.

3. The Twelve-Factor App Methodology
   - URL: <https://12factor.net/>
   - Accessed: 2026-05-08
   - Relevance: Factor IV (Backing Services) — "treat backing services as attached resources." Layer separation with Protocol contracts is the mechanism for treating backing services as attached and swappable without code changes.

4. Domain-Driven Design — Eric Evans
   - URL: <https://www.domainlanguage.com/ddd/>
   - Accessed: 2026-05-08
   - Relevance: Establishes bounded contexts and layered architecture as mechanisms for managing complexity in large systems. Layering enables each layer to focus on its own concerns (application logic, service composition, infrastructure integration) without bleeding across boundaries.

5. Vertical Slice Architecture — Jimmy Bogard
   - URL: <https://jimmybogard.com/vertical-slice-architecture/>
   - Accessed: 2026-05-08
   - Relevance: Describes minimizing coupling between slices (features) and maximizing coupling within a slice. Layering is orthogonal: it prevents coupling *between* layers across all slices. Vertical slices contain application code; horizontal layers are shared infrastructure.

6. Separated Interface — Martin Fowler, Patterns of Enterprise Application Architecture
   - URL: <https://martinfowler.com/eaaCatalog/separatedInterface.html>
   - Accessed: 2026-05-06
   - Relevance: "Define an interface in a separate package from its implementation... put the interface in a package the client depends on." Directly grounds the Path B pattern: the feature (client) defines the Protocol in its own `adapters/__init__.py`; the concrete adapter satisfies it from the outside.

7. Architecture Patterns with Python (Cosmic Python) — Percival and Gregory
   - URL: <https://www.cosmicpython.com/book/chapter_02_repository.html>
   - Accessed: 2026-05-06
   - Relevance: Establishes the Repository pattern as a domain-defined Protocol (`AbstractRepository`) satisfied by a concrete secondary adapter (`SqlAlchemyRepository`) that is permitted to import concrete storage clients directly. The adapter IS the infrastructure boundary; domain and service code only see the Protocol. Directly models the composed service Pattern (2b) and Path B's adapter responsibility boundary.

8. Architecture Patterns with Python — Swapping Out the Infrastructure (Appendix C) — Percival and Gregory
   - URL: <https://www.cosmicpython.com/book/appendix_csvs.html>
   - Accessed: 2026-05-08
   - Relevance: Demonstrates that the Protocol is the stable boundary and the concrete implementation is replaceable. Swapping `SqlAlchemyRepository` for `CsvRepository` leaves the domain model, service layer, and all tests untouched. This is the provider-swappability property of composed services: the Protocol is stable; the secondary adapter (concrete implementation) and its raw client are the parts that change.

9. Architecture Patterns with Python — Service Layer and Secondary Adapters (Chapter 4) — Percival and Gregory
   - URL: <https://www.cosmicpython.com/book/chapter_04_service_layer.html>
   - Accessed: 2026-05-08
   - Relevance: Defines "secondary adapters" (driven adapters) as the concrete implementations that live behind Ports. Explicitly distinguishes between primary adapters (entrypoints, e.g., FastAPI routes) and secondary adapters (infrastructure implementations, e.g., `SqlAlchemyRepository`). Grounds the naming used in 2b for composed service concrete implementations.

10. Layers, Onions, Ports, Adapters — Mark Seemann

- URL: <https://blog.ploeh.dk/2013/12/03/layers-onions-ports-adapters-its-all-the-same/>
- Accessed: 2026-05-06
- Relevance: Clarifies that adapter files at the infrastructure boundary are architecturally expected to hold and use concrete infrastructure types — this is their role. The constraint is that inner-layer code (domain, service) never imports the concrete adapter. Grounds the rule that Path B adapter files may hold raw client references without violating the layer boundary.

## Change Log

- 2026-05-08: Created as placeholder.
- 2026-05-08: Drafted with three-layer model, unidirectional flow, and enforcement rules grounded in Clean Architecture and Ports and Adapters patterns.
- 2026-05-08: Revised. Corrected the conceptual relationship between composed services and raw client facades. Composed services are now explicitly the provider-swappability boundary (Protocol is stable; concrete implementation and raw client are the vendor-specific parts that change). Raw client facades are no longer described as Category B utilities or as restricted to composed services only — they are vendor-specific infrastructure primitives that serve both composed service concrete implementations and feature-owned concrete adapters via constructor injection. Source References expanded with Cosmic Python Appendix C (provider swapping) and Chapter 4 (secondary adapters).
