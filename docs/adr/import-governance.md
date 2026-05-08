---
title: "Import Governance"
status: Accepted
type: Standard
tier: Tier-2
governance_domain: [application]
concerns: [architecture]
constrained_by: [layered-architecture.md, client-module-placement.md, dependency-injection.md, configuration-ownership.md, application-lifecycle.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Import Governance

## Context and Problem Statement

The application has accepted a set of architectural boundary rules: a three-position layer model with strict downward dependency flow ([layered-architecture.md](layered-architecture.md)); a per-service vertical-slice structure inside infrastructure ([dependency-injection.md](dependency-injection.md)); a strict purity rule for vendor-client modules ([client-module-placement.md](client-module-placement.md)); per-domain configuration ownership ([configuration-ownership.md](configuration-ownership.md)); a no-module-level-side-effects rule for boot-time work ([application-lifecycle.md](application-lifecycle.md)). Each of those rules constrains *which Python modules may import which other Python modules*. Without static enforcement, the rules are advisory: they are restated at code review, drift across the codebase, and require human attention every time a new module is added.

The problem this record addresses: **how are the codebase's import rules expressed and enforced as a static contract that runs in CI on every change?** The answer determines:

1. Whether a violation of the layer model is caught before merge (static analysis) or after merge (code review or runtime surprise).
2. Whether the rules are written in one place that authors and reviewers can read, or scattered across review comments and tribal knowledge.
3. Whether refactors that move modules between layers are validated mechanically against the architectural intent.

**Constraints:**

- The rules being enforced are already decided by the peer ADRs listed in `constrained_by`. This record does not introduce new architectural rules; it encodes existing rules into static contracts.
- The toolchain is Python; the static analyzer must integrate with the existing CI (currently runs `pytest`, type checking, formatters).
- The contract format must be reviewable: human-readable, version-controlled, with a clear failure message when a violation occurs.
- Test code has slightly different requirements from production code (e.g., tests may instantiate concrete implementations directly), and the contract must accommodate this without watering down the production rules.

**Non-goals:**

- This record does not define the architectural rules themselves — those live in the peer ADRs that constrain this one.
- This record does not pick the file format for the contract configuration in detail (e.g., the exact `pyproject.toml` keys); the configuration's content is what matters.
- This record does not enumerate every allowed and forbidden edge in the import graph; it specifies the *categories* of contract that must exist and the rule each category encodes.

## Considered Options

**Option 1 — Static enforcement via `import-linter`.** A dedicated tool runs a set of declarative contracts against the import graph. Contracts are version-controlled in the repository, described in a config file, and evaluated by the tool in CI. Violations fail the build with a message naming the offending modules and the contract they violate.

**Option 2 — Code review only.** Reviewers verify boundary rules manually on every change. No tooling; rules are documented in ADRs and CONTRIBUTING.md.

**Option 3 — Custom AST-based linting.** Write project-specific scripts (e.g., a pytest plugin or a pre-commit hook) that walk the AST and assert boundary rules.

## Decision Outcome

**Chosen: Option 1 — static enforcement via `import-linter`.**

`import-linter` is a Python static-analysis tool whose only job is enforcing import-graph contracts. It supports the contract types this codebase needs (`layers`, `forbidden`, `independence`), it integrates with `pyproject.toml` and CI, and its failure messages name the violating import edges. The codebase's boundary rules are encoded as a set of contracts described below; each contract corresponds directly to a rule already accepted in a peer ADR.

### Contract: top-level layer ordering

The codebase has three top-level layers under `app/`. Imports flow downward only.

- **Layers contract** (`import-linter` `layers` type): `app.packages` → `app.infrastructure` → `app.clients`. No reverse imports.
- A module in `app.packages` may import from `app.infrastructure` and `app.clients`. A module in `app.infrastructure` may import from `app.clients`. A module in `app.clients` imports from neither.
- This is the static expression of the unidirectional flow rule from [layered-architecture.md](layered-architecture.md).

### Contract: vendor-client purity

`app.clients` modules import only vendor SDKs and the Python standard library; they do not import application code or domain-side cross-cutting types.

- **Forbidden contract**: `app.clients` → `app.infrastructure`, `app.clients` → `app.packages`. Already implied by the layers contract above; restating as a forbidden rule produces a clearer error message ("vendor client tried to import from infrastructure").
- **Forbidden contract**: `app.clients` → `OperationResult` and any module under `app.shared` (or wherever cross-layer return types live). Vendor clients raise typed SDK exceptions; they do not produce or import the application's return envelope per [client-adapter-responsibilities.md](client-adapter-responsibilities.md).
- This is the static expression of the rules in [client-module-placement.md](client-module-placement.md) and [client-adapter-responsibilities.md](client-adapter-responsibilities.md).

### Contract: per-service consumption surface

Each infrastructure service is a vertical slice at `app/infrastructure/<service>/` with `__init__.py` re-exporting the Protocol and the provider function. Consumers reach the service through that surface only.

- **Forbidden contract**: any module outside `app.infrastructure.<service>` may not import from `app.infrastructure.<service>.protocol`, `app.infrastructure.<service>.providers`, or any concrete-implementation module inside the service. Imports go through `app.infrastructure.<service>` (the `__init__.py` surface).
- The per-service surface re-exports two things: the Protocol type and `get_<service>()`. Consumers receive both from one import.
- This is the static expression of the per-service consumption surface rule from [dependency-injection.md](dependency-injection.md).

### Contract: sibling-service imports scoped to provider modules

Inside the infrastructure layer, services may compose with each other — but only at the provider-module level, not in domain code.

- **Forbidden contract**: `app.infrastructure.<service>.protocol` and `app.infrastructure.<service>.<concrete>` modules may not import from `app.infrastructure.<other_service>` (or any module inside it). Cross-service imports are permitted only in `app.infrastructure.<service>.providers`, which is the place where one service's provider may call another service's `get_<other>()` for composition.
- This keeps the dependency graph between services visible at exactly one location per service: that service's `providers.py`.

### Contract: feature-package isolation

Feature packages do not import from each other. Cross-feature coordination uses shared infrastructure (events, queues) or domain events.

- **Independence contract** (`import-linter` `independence` type): the set of `app.packages.<feature>` modules. No two features may import from each other; each feature is an isolated vertical slice.
- A feature's `app.packages.<feature>.providers` is private to the feature: infrastructure code does not import from it, and other features do not import from it. (The infrastructure → feature direction is already forbidden by the layers contract; the feature → other-feature direction is what the independence contract adds.)
- This is the static expression of the feature-isolation rule.

### Contract: feature service code does not import vendor types

A feature's domain and service code (route handlers, hookimpls, presenters, services, models, settings) holds Protocol types only — never a concrete vendor client type.

- **Forbidden contract**: `app.packages.<feature>` modules other than `adapters/<provider>.py` may not import from `app.clients` or from the concrete-implementation files of `app.infrastructure.<service>` packages.
- Feature-owned outbound adapters (`app.packages.<feature>.adapters.<provider>`) are the only feature-side files permitted to import vendor clients; they are the boundary at which vendor types are received via constructor injection.
- This encodes the invariant from [layered-architecture.md](layered-architecture.md) and [client-adapter-responsibilities.md](client-adapter-responsibilities.md).

### Contract: no module-level boot work

Provider functions and `BaseSettings()` constructors must be invoked from inside functions called by the lifespan or by request handlers — never at module import time.

- This rule is harder to encode purely as an import-graph contract. The complementary mechanism is a CI lint step (e.g., a small AST-based check or a `pytest` boot-time test) that asserts:
  - No top-level call to a `get_<x>()` provider function exists in any application module.
  - No top-level instantiation of a `BaseSettings` subclass exists.
  - No top-level `boto3.client(...)` (or equivalent vendor SDK constructor) exists.
- This complements [application-lifecycle.md](application-lifecycle.md): boot work happens inside the lifespan, not at import.

### Barrel-file policy

`__init__.py` files are reserved for the per-service public surface (Protocol + provider re-exports for an infrastructure service; feature public exports for a feature package). They are not used as catch-all aggregators or for "convenience" star imports.

- An `__init__.py` re-exports only the names declared in `__all__`; the list is short and explicit.
- An `__init__.py` does not perform side effects (no provider calls, no logging configuration, no module-level state mutation).
- Wildcard imports (`from x import *`) are not used in application code.

### Test exemptions

Tests live under `tests/` (or an equivalent location outside `app/`). The contracts above apply to application code; tests have a narrower exemption:

- Tests may import a concrete implementation directly when **constructing a test double for it** or **asserting parsing behavior of a `BaseSettings` class**. Tests do not exercise application logic against a concrete reference; they substitute via `app.dependency_overrides` or `cache_clear()` per [configuration-ownership.md](configuration-ownership.md) and [dependency-injection.md](dependency-injection.md).
- A test that instantiates `DynamoDBStorageService` directly is acceptable when the test's purpose is "verify `DynamoDBStorageService`'s mapping of SDK exceptions to `OperationResult`." That same instantiation in application code is forbidden.
- The contracts described above are scoped to `app/` (or the equivalent application root). The `tests/` tree is outside that scope and does not need to satisfy the per-service-surface or the no-vendor-import rules.

### Contract evolution

When a new ADR adds a boundary rule that is statically enforceable, the import-governance contract set is amended to encode it. The contract file lives in the repository alongside the code; an ADR change that adds a forbidden edge is paired with a contract change in the same PR. Adding a contract is a normal change; relaxing or removing a contract requires explicit ADR justification (the rule the contract encodes must change first).

## Consequences

**Positive:**

- Boundary violations are caught at CI, not at code review or runtime. The cost of an architectural violation is bounded to the time of the test run, not the time it takes to ship and observe.
- The contract file is a single, version-controlled document of the architecture's static expression. New contributors can read it to understand the boundary rules.
- Refactors that move code between layers are validated mechanically — a misplaced `from …` jumps out as a contract violation rather than passing review unnoticed.
- The contract's failure messages name the offending edge, which makes diagnosis trivial.

**Tradeoffs accepted:**

- A second file (`pyproject.toml` section or `.importlinter` config) is the canonical static-rules document, separate from the prose ADRs. The two must be kept in sync; an ADR change that adds a rule includes the contract update.
- Some rules (no module-level boot work) are not pure import-graph rules and need a complementary AST-based check. The CI step is small but is real additional code.

**Risks:**

- A contract that is too permissive lets a violation through silently. Mitigation: every accepted boundary rule corresponds to a named contract; periodic review confirms the mapping is complete.
- A contract that is too strict forces shape changes to legitimate code (e.g., a new pattern that hasn't been considered). Mitigation: contracts are amended through normal PR review when the architectural intent justifies it; "the contract said no" is not the final word, but the rationale must be documented in an ADR change.

## Confirmation

Compliance is verified by:

- **CI step.** `import-linter` runs against the application source tree on every PR. Contract violations fail the build.
- **Complementary AST check.** A small lint step asserts no module-level provider calls, no module-level `BaseSettings()` instantiation, no module-level vendor-SDK constructor invocation.
- **Code review.** Reviewers do not need to re-derive the boundary rules; the contract file is the source of truth. PRs that change the contract file get scrutiny on whether the rule change is justified by an ADR change in the same PR.

## Source References

1. import-linter — Documentation
   - URL: <https://import-linter.readthedocs.io/>
   - Accessed: 2026-05-08
   - Relevance: Documents the `layers`, `forbidden`, and `independence` contract types this record uses to encode the codebase's boundary rules. Establishes that the tool integrates with `pyproject.toml` and runs in CI as a separate step.

2. The Clean Architecture — Robert C. Martin
   - URL: <https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html>
   - Accessed: 2026-04-29
   - Relevance: The Dependency Rule — "source code dependencies can only point inwards" — is the principle this record's layers contract encodes. The contract is the static-analysis expression of that rule for this codebase's three-layer model.

3. PEP 8 — Imports
   - URL: <https://peps.python.org/pep-0008/#imports>
   - Accessed: 2026-04-29
   - Relevance: Establishes that imports are explicit, ordered, and at the top of files. Grounds the rule that `__init__.py` re-exports are explicit (`__all__`) rather than wildcard, and that side-effecting imports are avoided.

4. Google Python Style Guide §2.2.4 — Imports
   - URL: <https://google.github.io/styleguide/pyguide.html#224-decision>
   - Accessed: 2026-05-06
   - Relevance: Industry guidance preferring explicit imports of names, with each cross-module dependency traceable to a specific name. Grounds the deep-import rule (consumers import from the per-service surface or definition site, not via barrels).

5. Composition Root — Mark Seemann
   - URL: <https://blog.ploeh.dk/2011/07/28/CompositionRoot/>
   - Accessed: 2026-04-29
   - Relevance: Establishes that wiring happens at the application's entry point, not in arbitrary consumer modules. Grounds the rule that the only place sibling-service imports may appear inside infrastructure is in provider modules — that is the local composition surface for each service.

6. Speeding Up the JavaScript Ecosystem, Part 7: Barrel Files — Marvin Hagemeister
   - URL: <https://marvinh.dev/blog/speeding-up-javascript-ecosystem-part-7/>
   - Accessed: 2026-05-06
   - Relevance: Documents the operational and performance costs of broad barrel-file re-exports (eager submodule loading, dependency-graph noise) that motivate the rule of keeping `__init__.py` re-exports narrow and intentional. The reasoning translates to Python's `__init__.py` semantics.

7. Vertical Slice Architecture — Jimmy Bogard
   - URL: <https://jimmybogard.com/vertical-slice-architecture/>
   - Accessed: 2026-05-06
   - Relevance: Establishes that features are organized as vertical slices isolated from each other; cross-slice coupling goes through shared infrastructure or events, not direct imports. Grounds the feature-package independence contract.

## Change Log

- 2026-05-08: Created. Establishes `import-linter` as the static enforcement tool for the codebase's import-graph rules; encodes the three-layer ordering (`packages → infrastructure → clients`), per-service consumption surface, sibling-service imports scoped to `providers.py`, feature-package independence, vendor-client purity, and no-feature-imports-vendor-types invariants as named contracts. Establishes a complementary AST-based check for the no-module-level-boot-work rule. Tests are exempt from the production rules within their own tree, with the rationale that test substitution still goes through provider/dependency-override mechanisms when exercising application logic. Contract evolution is paired with ADR changes in the same PR.
