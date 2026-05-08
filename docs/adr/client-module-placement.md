---
title: "Client Module Placement"
status: Draft
type: Selection
tier: Tier-2
governance_domain: [application]
concerns: [architecture]
constrained_by: [layered-architecture.md, import-governance.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Client Module Placement

## Context and Problem Statement

Vendor clients are a shared primitive consumed by both **composed-service concrete implementations** in the infrastructure layer (Path A in [layered-architecture.md](layered-architecture.md)) and **feature-owned outbound adapters** inside feature packages (Path B). Both consumers depend on the same client to reach the same external system: `AWSClients` is consumed by a DynamoDB-backed storage service (Path A) and by an AWS Identity Center adapter inside the access-sync feature (Path B), in each case via constructor injection.

The problem this record addresses: **at what physical location in the source tree do vendor client modules live?** The placement decides whether a feature-owned adapter depending on a vendor client is an ordinary same-tree dependency on a shared primitive, or a layer-boundary crossing that requires an exception to the import rules.

**Constraints:**

- Vendor clients serve both composed services and feature-owned adapters; they are not owned by either layer.
- Feature domain and service code must not depend on vendor clients — only adapter files do (the invariant in [layered-architecture.md](layered-architecture.md)).
- The placement rule must be expressible as a static import-analysis contract.

**Non-goals:**

- This record does not define what clients vs adapters are responsible for — see [client-adapter-responsibilities.md](client-adapter-responsibilities.md).
- This record does not enumerate allowed import directions in general — see [import-governance.md](import-governance.md). It resolves only the placement-dependent rule that import governance must encode.

## Considered Options

**Option 1 — Top-level sibling: `app/clients/`.** Vendor clients sit alongside `app/infrastructure/` and `app/packages/`. Both consumers import from `app.clients.<vendor>`; neither is treated as crossing into a layer that owns the client.

**Option 2 — Nested under infrastructure: `app/infrastructure/clients/`.** Composed-service implementations import freely from siblings. Feature-owned adapter files require a documented exception to import from `app.infrastructure.clients`, since feature packages otherwise cannot import from infrastructure.

**Option 3 — Per-vendor under infrastructure: `app/infrastructure/aws/clients/`, `app/infrastructure/google/clients/`, …** Co-locates vendor-specific code under one tree per vendor. Mixes "client" with "composed-service implementation" inside the same vendor folder, removing the architectural distinction between connectivity primitive and capability implementation.

## Decision Outcome

**Chosen: Option 1 — top-level `app/clients/`.**

Vendor clients are neither part of the behavior layer (where features live) nor part of the capability layer (where composed services live). They are vendor connectivity primitives consumed by both. Placing them at `app/clients/` makes that relationship structural: a feature-owned adapter importing a vendor client is not crossing a layer boundary — it is depending on a shared primitive that sits below both layers.

This layout follows the canonical project structure in *Architecture Patterns with Python* (Percival and Gregory), where adapters and connectivity primitives live at project boundary level rather than nested under a service subdirectory. It also tracks Mark Seemann's framing that layered-architecture constraints apply *between* layers; modules within the same boundary tier may depend on each other without restriction.

### Rules implied by this placement

- `app/clients/<vendor>/` contains only vendor SDK wrapping. It does not import domain types, `OperationResult`, or Protocols, and it does not import from `app/infrastructure/` or `app/packages/`.
- Composed-service implementations under `app/infrastructure/<service>/` and feature-owned adapter files at `app/packages/<feature>/adapters/<provider>.py` both import from `app.clients`. This is an ordinary downward dependency for both.
- Feature service, domain, model, route, hook, and presentation modules do not import from `app/clients/`. The boundary remains the adapter file.
- `app/infrastructure/` and `app/packages/` do not import each other. `app/clients/` is the only directory both layers may depend on.

## Consequences

**Positive:**

- No "permitted exception" is needed for feature-owned adapters to consume vendor clients; the dependency is structural.
- The three-position layer model declared in [layered-architecture.md](layered-architecture.md) is visible in the source tree: three top-level directories under `app/`, each with one role.
- The placement is statically enforceable by a single import-linter `layers` contract (`clients < infrastructure < packages`), accompanied by a narrower contract restricting `app.clients` imports inside `app/packages/` to adapter files.

**Tradeoffs accepted:**

- A fourth top-level directory under `app/` (alongside `infrastructure/`, `packages/`, and the application server module). Structural cost: one extra entry. Structural benefit: one fewer rule exception, one fewer special case for code review to remember.
- Imports of the form `from app.infrastructure.clients.<vendor> import …` are expressed instead as `from app.clients.<vendor> import …`. The rename is mechanical and verifiable by tooling.

**Risks:**

- Domain or capability logic could accumulate inside `app/clients/` over time, eroding the connectivity-only boundary the placement is meant to enforce. Mitigation: an import-linter contract forbids `app.clients` from importing `app.infrastructure`, `app.packages`, or `OperationResult`; code review confirms that client modules only wrap vendor SDKs.

## Confirmation

Compliance is verified by:

- **Static import analysis.** An import-linter `layers` contract enforces the ordering `clients < infrastructure < packages`. A `forbidden` contract restricts `app.clients` imports inside `app/packages/` to files matching `**/adapters/*.py`.
- **Code review (clients).** Modules under `app/clients/` import only vendor SDKs and the Python standard library. They do not import from `app/infrastructure/`, `app/packages/`, or any domain or `OperationResult` type.
- **Code review (features).** Outside of `app/packages/<feature>/adapters/<provider>.py`, no module inside a feature package imports from `app.clients`.

## Source References

1. Architecture Patterns with Python (Cosmic Python) — Dependency Injection and Bootstrapping (Chapter 13) — Percival and Gregory
   - URL: <https://www.cosmicpython.com/book/chapter_13_dependency_injection.html>
   - Accessed: 2026-04-29
   - Relevance: Establishes the canonical project layout — adapters and connectivity primitives live at project boundary level alongside repository implementations, not nested inside a "services" subdirectory. Direct support for top-level `app/clients/`.

2. Architecture Patterns with Python (Cosmic Python) — Repository Pattern (Chapter 2) — Percival and Gregory
   - URL: <https://www.cosmicpython.com/book/chapter_02_repository.html>
   - Accessed: 2026-04-29
   - Relevance: Establishes that adapter files at the project boundary import concrete storage clients directly, with the application core depending only on Protocols. Confirms that the boundary is the adapter file, not a directory hierarchy of nested infrastructure subdirectories.

3. Layers, Onions, Ports, Adapters — Mark Seemann
   - URL: <https://blog.ploeh.dk/2013/12/03/layers-onions-ports-adapters-its-all-the-same/>
   - Accessed: 2026-04-29
   - Relevance: Layered-architecture constraints apply *between* layers; modules within the same boundary tier may depend on each other freely. Grounds the rule that both composed-service implementations and feature-owned adapters may depend on `app/clients/` without an exception.

4. The Clean Architecture — Robert C. Martin
   - URL: <https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html>
   - Accessed: 2026-04-29
   - Relevance: All concrete SDK dependencies belong in the outermost "Frameworks & Drivers" ring. The Dependency Rule applies inter-ring, not intra-ring: clients and secondary adapters share the same ring, with no Clean-Architecture-imposed sub-hierarchy between them.

5. Hexagonal Architecture (Ports and Adapters) — Alistair Cockburn
   - URL: <https://alistair.cockburn.us/hexagonal-architecture/>
   - Accessed: 2026-04-29
   - Relevance: Adapters at the boundary are architecturally expected to hold concrete dependencies (vendor clients, SDKs). The constraint applies to source-code dependencies of the application core, not to the directory layout of the adapter and the connectivity primitives it consumes.

6. import-linter — Layers Contract
   - URL: <https://import-linter.readthedocs.io/en/stable/contract_types.html#layers>
   - Accessed: 2026-05-08
   - Relevance: Defines the `layers` contract type for enforcing strict ordering between Python packages. Confirms that the rule `clients < infrastructure < packages` is expressible as a single contract — the placement is statically enforceable.

7. PEP 8 — Imports
   - URL: <https://peps.python.org/pep-0008/#imports>
   - Accessed: 2026-04-29
   - Relevance: Python imports should be explicit and traceable. A top-level path (`from app.clients.aws import AWSClients`) is decodable from the path alone, without resolving an internal subdirectory of a parent module.

## Change Log

- 2026-05-08: Created. Selects top-level `app/clients/` placement for vendor connectivity primitives, making them a sibling of `app/infrastructure/` and `app/packages/` consistent with the three-position layer model in layered-architecture.md. Removes the need for a "permitted exception" in import rules for feature-owned adapters; the placement is enforceable by a single import-linter `layers` contract.
