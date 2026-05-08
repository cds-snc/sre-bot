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

Application code evolves when feature requirements change. Vendor-specific code (cloud SDKs, platform clients) evolves when operational constraints shift or providers are replaced. When the two are tightly coupled — when feature code imports a cloud SDK directly — changing either axis forces rewrites across the codebase.

The core problem: **changes in vendor connectivity must not cascade into feature code, and feature requirements must not force vendor-specific reimplementation.** This decoupling is achieved through strict layer separation with unidirectional dependency flow, with all crossings expressed through `typing.Protocol` interfaces.

**Constraints:**

- The application is a modular Python FastAPI system where multiple features and cross-cutting concerns coexist.
- Features must be independently testable without external service connectivity.
- Vendor connectivity must be swappable — replacing one provider with another, or one SDK with another, must not require rewrites in feature packages.
- The application is stateless: durable state lives in external backing services (see [cloud-portability.md](cloud-portability.md)).

**Non-goals:**

- This record does not prescribe the internal organization of feature packages — see [feature-package-structure.md](feature-package-structure.md).
- This record does not define the dependency injection mechanism, composition root rules, or `Annotated[Protocol, Depends()]` conventions — see [dependency-injection.md](dependency-injection.md).
- This record does not define the Category A/B/C taxonomy or Protocol exposure rules for shared infrastructure services — see [infrastructure-service-classification.md](infrastructure-service-classification.md).
- This record does not define allowed import directions, barrel-file policy, or static-analysis rules — see [import-governance.md](import-governance.md).
- This record does not define the responsibility boundary between vendor clients (transport) and secondary adapters (domain translation) — see [client-adapter-responsibilities.md](client-adapter-responsibilities.md).
- This record does not decide the physical module placement of vendor clients — see [client-module-placement.md](client-module-placement.md).

## Considered Options

**Option 1: No formal layer separation — features import vendor SDKs directly.**

Feature code calls cloud SDKs and platform clients without abstraction. Vendor-specific concerns are scattered throughout the codebase.

**Option 2: Strict layered architecture with a Protocol-based boundary and two integration paths.**

The codebase is organized into two layers — Application and Infrastructure — sitting above a shared layer of vendor connectivity primitives. Feature code crosses the boundary only through `typing.Protocol` interfaces, by one of two integration paths: a shared service Protocol owned by infrastructure, or a feature-owned Protocol satisfied by a feature-owned adapter.

## Decision Outcome

**Chosen: Option 2 — strict layered architecture with a Protocol-based boundary and two integration paths.**

### The layer model

The codebase has two layers of *behavior*, sitting above a shared layer of *vendor connectivity*:

- **Application layer** — feature packages. Domain models, domain services, request handlers, hookimpls, background tasks. This is the layer where business behavior lives.
- **Infrastructure layer** — composed services that abstract a capability behind a Protocol (e.g. `StorageService`, `DirectoryProvider`). The Protocol is the stable, capability-focused interface; the concrete implementation is a vendor-specific secondary adapter.
- **Vendor connectivity primitives ("clients")** — pre-authenticated, vendor-specific SDK wrappers (e.g. `AWSClients`, `GoogleWorkspaceClients`). Clients are not abstractions; they *are* the concrete vendor layer. They serve composed-service concrete implementations and feature-owned concrete adapters via constructor injection.

Clients are a shared primitive: composed-service implementations and feature-owned adapters both depend on them. They do not belong inside feature packages, and they sit logically below the layer of behavior. Their physical module placement (top-level `app/clients/` vs nested under `app/infrastructure/`) is governed separately in [client-module-placement.md](client-module-placement.md).

### Unidirectional dependency flow

Source-code dependencies point in one direction: **feature → Protocol → secondary adapter → client → external service.** Reverse imports are prohibited. Concrete enforcement (allowed and forbidden import paths, barrel-file policy, static-analysis configuration) is governed by [import-governance.md](import-governance.md).

### Two integration paths

Feature code reaches the outside world through one of two paths, depending on whether the integration is shared or feature-specific.

**Path A — Shared infrastructure service.** For capabilities used by more than one feature (queuing, idempotency, identity, storage, eventing), the infrastructure layer owns the Protocol and at least one vendor-specific concrete implementation. Feature code depends on the Protocol. The provider-swappability boundary lives at the Protocol: replacing the backing provider replaces the concrete implementation and its client; the Protocol and feature code do not change.

**Path B — Feature-owned outbound adapter.** For external systems consumed by a single feature whose integration is domain-specific (Separated Interface, Fowler; Outbound Port + Adapter, Cockburn), the feature package owns both the Protocol and the concrete adapter. The feature defines the operations its domain logic needs; the adapter satisfies them, holding the vendor client received via constructor injection. Domain and service code in the feature operate against the Protocol only.

A feature-owned adapter is promoted to a shared infrastructure service when a second independent feature needs the same external system, or when the integration acquires operational ownership requirements (SLA, monitoring, security) that belong to the platform layer.

### The invariant

In both paths, **feature domain and service code never holds a reference to a concrete vendor type.** In Path A, the Protocol is defined by infrastructure and the concrete implementation is hidden behind it. In Path B, the Protocol is defined by the feature, and the concrete adapter — which does hold the client — is equally hidden from `service.py`. The adapter file (`adapters/<provider>.py`) is the boundary, not a consumer across it. This is the same constraint Clean Architecture states as "source code dependencies can only point inwards" and Cockburn states as "the application core communicates with the outside world only through ports."

## Consequences

**Positive:**

- Vendor swaps (SDK upgrade, provider change, adapter rewrite) do not propagate into feature code.
- Feature code is testable in isolation by substituting Protocol stubs — no cloud credentials, no real clients required.
- The layer model has one rule (unidirectional flow) and one mechanism (Protocol crossings), making compliance verifiable by code review and import-linter.

**Tradeoffs accepted:**

- Every external integration consumed by features requires an explicit Protocol — defined by infrastructure (Path A) or by the feature (Path B). Without it, the boundary is not enforceable.
- Feature developers must determine which path applies for each new integration.

**Risks:**

- Protocols shaped around a specific SDK API (rather than around feature need) leak vendor coupling through the interface itself, defeating the abstraction.
- Without static import analysis, cross-layer violations may go undetected until code review.

## Confirmation

Compliance with this principle is verified by the rules and tooling defined in [import-governance.md](import-governance.md) — feature service and domain code may import only Protocol types and provider functions; concrete vendor types appear only in adapter files; infrastructure modules do not import from `app/packages/`. Test isolation (Path A via dependency overrides, Path B via Protocol-conformant in-process stubs) provides the runtime confirmation that the boundary holds.

## Source References

1. The Clean Architecture — Robert C. Martin
   - URL: <https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html>
   - Accessed: 2026-05-08
   - Relevance: Establishes that "source code dependencies can only point inward" and that outer rings (frameworks, drivers, details) must never leak into inner rings (business logic). Directly maps to the unidirectional flow constraint.

2. Hexagonal Architecture / Ports and Adapters — Alistair Cockburn
   - URL: <https://alistair.cockburn.us/hexagonal-architecture/>
   - Accessed: 2026-05-08
   - Relevance: The application core communicates with external systems through abstract ports; concrete adapters implement those ports. Directly maps to the Protocol-based boundary used in both integration paths.

3. The Twelve-Factor App Methodology
   - URL: <https://12factor.net/>
   - Accessed: 2026-05-08
   - Relevance: Factor IV (Backing Services) — "treat backing services as attached resources." Layer separation with Protocol contracts is the mechanism for treating backing services as attached and swappable without code changes.

4. Domain-Driven Design — Eric Evans
   - URL: <https://www.domainlanguage.com/ddd/>
   - Accessed: 2026-05-08
   - Relevance: Establishes layered architecture as a mechanism for managing complexity in large systems. Each layer focuses on its own concerns without bleeding across boundaries.

5. Vertical Slice Architecture — Jimmy Bogard
   - URL: <https://jimmybogard.com/vertical-slice-architecture/>
   - Accessed: 2026-05-08
   - Relevance: Describes minimizing coupling *between* slices and maximizing coupling *within* a slice. Layering is orthogonal: it prevents coupling between layers across all slices.

6. Separated Interface — Martin Fowler, Patterns of Enterprise Application Architecture
   - URL: <https://martinfowler.com/eaaCatalog/separatedInterface.html>
   - Accessed: 2026-05-06
   - Relevance: "Define an interface in a separate package from its implementation… put the interface in a package the client depends on." Grounds Path B: the feature (client) defines the Protocol; the concrete adapter satisfies it from the outside.

7. Layers, Onions, Ports, Adapters — Mark Seemann
   - URL: <https://blog.ploeh.dk/2013/12/03/layers-onions-ports-adapters-its-all-the-same/>
   - Accessed: 2026-05-06
   - Relevance: Clarifies that adapter files at the boundary are architecturally expected to hold and use concrete infrastructure types — this is their role. The constraint is that inner-layer code (domain, service) never imports the concrete adapter.

## Change Log

- 2026-05-08: Created as placeholder.
- 2026-05-08: Drafted with three-layer model, unidirectional flow, and enforcement rules grounded in Clean Architecture and Ports and Adapters patterns.
- 2026-05-08: Revised. Corrected the conceptual relationship between composed services and raw client facades — composed services are the provider-swappability boundary; clients are the concrete vendor primitives consumed by both composed-service implementations and feature-owned adapters.
- 2026-05-08: Restructured per one-concern-per-record rule. Reduced scope to the layer model, unidirectional flow, and the two integration paths. Feature package internals deferred to feature-package-structure.md; composition root and DI mechanics deferred to dependency-injection.md; Category A/B/C taxonomy deferred to infrastructure-service-classification.md; import rules deferred to import-governance.md; client/adapter responsibility split deferred to new client-adapter-responsibilities.md; client physical placement deferred to new client-module-placement.md.
