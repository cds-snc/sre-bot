---
status: Draft
date: 2026-09-10
applies: target
scope: Shared business capabilities as packages in a layer below features: what qualifies, their shape, import direction and enforcement.
---

# Capability Packages

## Context

[feature-packages.md](feature-packages.md) forbids features from importing each other, and [layers.md](layers.md) sends shared needs to infrastructure on the second consumer. That works for business-agnostic services. It breaks for shared needs that carry organization policy, such as:
- resolving a person across Google and Microsoft accounts;
- finding a meeting time across both calendars;
- reaching someone on the platform they actually use ([workplace-systems.md](workplace-systems.md)).

Such a need isn't one feature's business, and putting it in infrastructure would make infrastructure hold identity and routing policy.

Options considered:

- **A router in infrastructure** behind a neutral Protocol. Features stay unchanged, but infrastructure absorbs identity and policy and stops being business-agnostic.
- **Relaxing feature-to-feature imports.** Direct calls are a legitimate integration style in a modular monolith ([Grzybek](https://www.kamilgrzybek.com/blog/posts/modular-monolith-integration-styles)). But peer imports spread one feature's vocabulary into others and turn the plugin graph into a web.
- **A new top-level tier.** Same effect as a lower layer inside `app/packages/`, with one more directory and no stronger enforcement.
- **Capability packages in a lower layer of `app/packages/`.** Chosen.

Current state: no capability packages exist, no feature package imports another, and import-linter is not yet in CI (TASK-18).

## Decision

**A capability package is a package under `app/packages/` that sits in a lower layer than features and provides a shared business capability.** A package qualifies only when all three hold:

1. At least one feature needs it now. Capability packages are never built speculatively.
2. It carries organization policy or routes across external systems, so it is neither hosting infrastructure nor one feature's business.
3. Its vocabulary is feature-free: no incident, retro, talent-role or access-request terms in its names or models.

**Shape.** The [feature-packages.md](feature-packages.md) layout applies:
- `service.py` holds the policy;
- `domain.py` holds frozen models;
- `store.py` persists through hosting Protocols;
- `adapters/` holds one adapter per external system, under Path B and [outbound-clients.md](outbound-clients.md) rules.

Each adapter port has an in-memory fake, as [cloud-portability.md](cloud-portability.md) contract 4 requires of backing-service ports. A complex capability uses the umbrella rule. Capability packages register through plugins, exactly like features ([plugins.md](plugins.md)).

**Public surface.** Each capability package exposes one public module, `api.py`, exporting its Protocol, domain types and provider function. Everything else in the package is private.

**Import direction.**

- Features may import a capability package's `api.py`, and nothing else from it.
- Capability packages never import features.
- A capability package may import another capability package's `api.py` only when that package sits lower in the declared order. Cycles are forbidden.
- Features still never import each other.
- Handler discipline is unchanged: handlers call one service method, and features reach capabilities from their service layer.

**Declaration, not naming.** Membership in the capability layer is declared in an import-linter `layers` contract over `packages`, with `exhaustive = true`. Every new top-level package must then be classified as a feature or a capability ([import-linter layers contract](https://import-linter.readthedocs.io/en/latest/contract_types/layers/)). Whether capability packages sit flat under `app/packages/` or under a named umbrella is decided when the second one exists. The name must not assume every capability is workplace-related.

**Promotion.**
- When a second feature needs the same cross-system operation, or the same adapter to a workplace system, the shared part moves into a capability package in one PR.
- A shared single-vendor adapter with no organization policy and no workplace concern still promotes to infrastructure per [layers.md](layers.md).

## Consequences

- Features stay independent of each other, and organization policy for shared needs lives in one visible place.
- Infrastructure stays business-agnostic.
- Cost: one more layer to learn and one more contract to maintain.
- Risk: a capability package becomes a grab-bag. Mitigations: the three qualifying tests, the feature-free vocabulary rule, and the umbrella rule's limits on `common/`.
- Enforcement depends on import-linter (TASK-18); until it lands, the import rules are checked in review.

## Checks

- import-linter: a `layers` contract over `packages` declares features above capability packages, with `exhaustive = true` (review until TASK-18 lands).
- Review until expressible as an import-linter contract: features import a capability package only through its `api.py`.
- Review: capability package names and models contain no feature vocabulary.
- Review: every capability package has at least one feature consumer.

## Migration

Tickets are created on acceptance:
- amend [feature-packages.md](feature-packages.md) (dependency rules, layout table, `api.py`) and [layers.md](layers.md) (promotion);
- add the packages layer contract to TASK-18's scope;
- build the first capability package, people and accounts ([people-and-accounts.md](people-and-accounts.md), TASK-83.4).

Tolerated until then: no capability packages exist.
