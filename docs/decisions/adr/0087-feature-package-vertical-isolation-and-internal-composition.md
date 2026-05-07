---
adr_id: ADR-0087
title: "Feature Package Vertical Isolation and Internal Composition"
status: Draft
decision_type: Standard
tier: Tier-2
governance_domain: application
primary_domain: Package and Plugin Architecture
secondary_domains:
  - Dependency and Composition
  - Testing and Quality Gates
owners:
  - SRE Team
date_created: 2026-05-06
last_updated: 2026-05-06
last_reviewed: 2026-05-06
next_review_due: 2026-09-03
constrained_by:
  - ADR-0044
  - ADR-0045
  - ADR-0048
  - ADR-0049
  - ADR-0059
  - ADR-0062
  - ADR-0065
  - ADR-0077
  - ADR-0078
impacts:
  - ADR-0048
  - ADR-0049
  - ADR-0059
  - ADR-0062
supersedes: []
superseded_by: []
review_state: current
related_records:
  - ADR-0045
  - ADR-0048
  - ADR-0049
  - ADR-0059
  - ADR-0062
  - ADR-0065
  - ADR-0077
  - ADR-0078
  - ADR-0085
  - ADR-0086
  - ADR-0088
related_packages:
  - app/packages/access
  - app/packages/geolocate
---

# Feature Package Vertical Isolation and Internal Composition

## Context

  No prior ADR defines what "vertically isolated" means for a feature
  package in `app/packages/`. ADR-0048 establishes the Application → Service →
  Infrastructure flow and names `app/packages/` as the canonical home for business
  logic. Neither ADR-0048 nor ADR-0059 defines the *internal* structure of a feature
  package, its permitted imports from siblings, or how its complexity evolves.

  The cross-ADR analysis identified two critical missing governance areas beyond
  basic vertical isolation:

  1. **Feature-internal composition:** When a feature decomposes into sub-packages
     (e.g., `access/request`, `access/sync`, `access/catalog`), no rule governs when to
     extract shared internal services, how to structure an internal shared layer, or what
     belongs in `common/` versus sub-package-local modules. This is distinct from
     inter-package isolation — it is about intra-package DRY without creating entanglement.

  2. **Capability promotion lifecycle:** When a feature-local capability is needed by
     multiple features, no rule defines the decision process, trigger thresholds, or
     extraction workflow for promoting it to infrastructure. Cross-package imports are
     prohibited (Standard 2) but no path forward exists when features legitimately
     share a need.

  **The current package landscape:**

  | Package | Sub-packages | Shared kernel | Hookimpl entry points |
  |---------|-------------|---------------|----------------------|
  | `access` | `request`, `sync`, `catalog`, `common` | `common/` (events, settings, providers) | Per sub-package |
  | `geolocate` | none | none | Single `__init__.py` |

  **The cross-package import gap:**

  No rule today explicitly prohibits `packages/geolocate/` from importing
  `packages/access/domain.py`. ADR-0048 B1 prohibits imports from `app/modules/` but
  does not address peer-to-peer package imports.

  **The intra-package composition gap:**

  The `access` package has three sub-packages sharing `common/`. But no rule defines:
  - What may live in `common/` (value types only? providers? service logic?)
  - When a complex feature should extract an internal service layer
  - How shared concerns (settings, domain models, cross-subfeature protocols) should be
    organized to prevent subfeatures from becoming entangled

  **The capability promotion gap:**

  Platform reconcilers and client adapters are often feature-local first and
  infrastructure-promoted later. Example: `AwsIdentityStoreReconciler` in Access Sync
  is feature-local today. If a Provisioning feature also needs identity-store lifecycle
  control, the reconciler should be extracted to infrastructure. No decision process
  exists for this transition.

- Business/operational drivers:
  - Provide enforceable package boundary rules so new packages are consistent.
  - Prevent peer-to-peer coupling as the `packages/` tree grows.
  - Clarify intra-package composition: when to extract shared internal layers.
  - Define capability promotion triggers so teams neither duplicate excessively nor
    violate boundaries with informal shared modules.

- Constraints:
  - ADR-0045 P3: business logic belongs in `app/packages/<domain>`.
  - ADR-0048 B1: packages must not import from `app/modules/`.
  - ADR-0049: plugin registration via pluggy hookspecs is the governed mechanism.
  - ADR-0062: test layout (`app/tests/unit/packages/...`).
  - ADR-0065: domain data uses `@dataclass(frozen=True)`.

- Non-goals:
  - This record does not define call-site mechanics for consuming infrastructure
    services (governed by ADR-0086).
  - This record does not define multi-transport adapter patterns (governed by ADR-0088).
  - This record does not define barrel structure (governed by ADR-0085).
  - This record does not govern `app/modules/` (frozen zone).

## Decision

A feature package in `app/packages/<domain>` is a **vertical slice**: it owns its domain
model, service logic, transport adapters, settings, and provider wiring. Cross-package
coupling is prohibited. Intra-package shared libraries are governed. Feature-internal
composition and capability promotion have explicit rules and triggers.

### Standard 1: Canonical Feature Package Structure

Every feature package must conform to this directory layout:

```
packages/<feature>/
    __init__.py          # @hookimpl functions only; for complex features, THIS IS the
                         # sole registration entry point (governs all sub-capabilities)
    providers.py         # Package-local @lru_cache singleton providers
    settings.py          # Package-local BaseSettings + provider function
    service.py           # Core business logic (or domain/ for complex packages)
    interactions/        # Multi-transport adapters (governed by ADR-0088)
        __init__.py
        ingress.py       # Transport-agnostic orchestration
        http.py          # FastAPI route adapter
        slack.py         # Slack interaction adapter (if applicable)
        teams.py         # Teams interaction adapter (if applicable)
    models.py            # Domain dataclasses (@dataclass(frozen=True))
```

**Constraints:**

- S1.1: `__init__.py` must contain only `@hookimpl` functions and the imports required
  to implement them. No business logic, no service instantiation, no class definitions.
- S1.1a (for simple features): `__init__.py` has all hookimpls for the feature.
- S1.1b (for complex multi-sub-capability features): The umbrella `__init__.py` is the
  **sole** registration entry point. Sub-capability `__init__.py` files are empty.
  Settings-based gating for sub-capabilities is performed inside umbrella hookimpls
  using `@lru_cache` settings providers (see Standard 3).
- S1.2: `providers.py` is the package-local composition point. It provides `@lru_cache`
  singleton factories for package-internal services and settings.
- S1.3: A package may omit files it does not need. The structure is additive.
- S1.4: Additional sub-directories (`adapters/`, `domain/`, `mappers/`) are permitted
  when complexity warrants internal decomposition.

### Standard 2: Cross-Package Import Prohibition

Feature packages must not import from sibling feature packages. The only permitted
dependency direction from a feature package is downward into `app/infrastructure/`.

| Import Direction | Permitted? | Rationale |
|-----------------|-----------|-----------|
| `packages/X` → `infrastructure/*` | ✅ Yes | Vertical consumes horizontal services |
| `packages/X` → `packages/Y` (any symbol) | ❌ No | Violates slice isolation |
| `packages/X` → `app/modules/*` | ❌ No | Frozen zone (ADR-0048 B1) |
| `infrastructure/*` → `packages/X` | ❌ No | Reverse dependency direction |

**Constraints:**

- S2.1: No feature package may import any symbol from another feature package at runtime.
- S2.2: `TYPE_CHECKING` imports from sibling packages are prohibited. If a package needs
  a type from another package's domain, the packages must communicate through
  infrastructure-mediated mechanisms (events, storage, hookspec-driven orchestration).
- S2.3: Cross-package communication must occur through infrastructure-mediated mechanisms,
  never through direct import.

### Standard 3: Sub-Package Boundaries and Shared Kernels

A top-level feature package may decompose into sub-packages when the domain has distinct
operational sub-domains. Sub-packages within the same parent are **independent verticals**
that share a bounded intra-package kernel.

**Rules for sub-packages:**

| Rule | Description |
|------|-------------|
| S3.1 | For complex multi-sub-capability features, the umbrella `packages/<feature>/__init__.py` is the **sole** registration entry point. It holds all `@hookimpl` functions for the module. Sub-capability `__init__.py` files are empty — they mark directories as Python packages but contain no hookimpls. |
| S3.1a | Sub-capability gating: Settings-based feature gating for individual sub-capabilities is performed inside the umbrella hookimpl, using `@lru_cache` settings providers, **before** any `include_router` or command registration call. This is the only mechanism that guarantees disabled routes are absent from the FastAPI route table and OpenAPI schema. |
| S3.1b | Import discipline: The umbrella `__init__.py` imports sub-capability providers and routers at module level. Lazy imports inside hookimpl bodies are only permitted when a sub-capability module has a documented heavy import cost; they must include a comment explaining the reason. |
| S3.2 | Sub-packages must not import from each other's internal modules. `access/sync` must not import from `access/request/service.py`. |
| S3.3 | A `common/` (or `_shared/`) sub-package is permitted as an intra-bounded-context shared kernel. |
| S3.4 | The shared kernel may contain only: value types (dataclasses, enums), event definitions, settings classes, and provider functions. It must never contain service implementations. |
| S3.5 | Only sub-packages within the same parent may import from `common/`. No external package may import from another package's `common/`. |

**When to decompose into sub-packages:**

1. Distinct operational sub-domains with independent lifecycles exist.
2. The umbrella `__init__.py` will register all sub-capabilities conditionally (see S3.1a).
3. The sub-domains share value types and events but not service implementations.

If sub-domains require shared service instances (not just value types), they are too
tightly coupled for sub-package separation and must remain a single package.

**Practical example (umbrella registration with gating):**

For `packages/access/` with sub-capabilities `sync`, `request`, and `catalog`:

```python
# packages/access/__init__.py (sole hookimpl entry point)

from infrastructure.services import hookimpl
from packages.access.sync.interactions.http import router as sync_router
from packages.access.sync.providers import get_access_sync_settings
from packages.access.request.interactions.http import router as request_router
from packages.access.request.providers import get_access_request_settings
from packages.access.catalog.interactions.http import router as catalog_router
from packages.access.catalog.providers import get_catalog_settings

@hookimpl
def register_routes(app) -> None:
    # Settings-gating before include_router ensures disabled routes are not registered
    if get_access_sync_settings().enabled:
        app.include_router(sync_router, prefix="/api/v1")
    if get_access_request_settings().enabled:
        app.include_router(request_router, prefix="/api/v1")
    if get_catalog_settings().enabled:
        app.include_router(catalog_router, prefix="/api/v1")

@hookimpl
def startup_warmup(logger) -> None:
    # Warm providers for enabled sub-capabilities only
    if get_access_sync_settings().enabled:
        _warmup_sync(logger)
    # ... etc for other sub-capabilities
```

```python
# packages/access/sync/__init__.py (empty — no hookimpls)
# packages/access/request/__init__.py (empty)
# packages/access/catalog/__init__.py (empty)
```

### Standard 4: Feature-Internal Composition

When a feature package grows in complexity, it may extract internal shared layers. This
is distinct from the shared kernel (`common/`) — it covers internal service organization.

**When to extract an internal shared layer:**

| Trigger | Description |
|---------|-------------|
| T1 | 2+ sub-packages exist with defined, maintainable boundaries |
| T2 | Shared concerns emerge: settings, domain models, cross-subfeature protocols |
| T3 | Sub-feature teams should not need to coordinate imports of utility modules |

**What belongs in the internal shared layer (`common/` or `_shared/`):**

| Allowed | Not Allowed |
|---------|-------------|
| Feature-scoped settings classes | Service implementations |
| Domain value types (dataclasses, enums) | Business logic functions |
| Event definitions and constants | HTTP/platform-specific types |
| Provider functions for feature-scoped services | Infrastructure protocol definitions |
| Cross-subfeature Protocol contracts | Concrete adapters or reconcilers |

**Constraints:**

- S4.1: Internal shared layers must contain only value types, contracts, settings, and
  provider functions. Service implementations stay in sub-package-local modules.
- S4.2: If a shared concern evolves into service logic, it must be refactored into the
  sub-package that owns the behavior, or promoted to infrastructure (Standard 6).
- S4.3: The shared layer must not grow into a "second service layer" that duplicates the
  sub-packages' responsibilities. If it does, the sub-packages should be consolidated
  into a single package.

### Standard 5: Test Scope and Layout

Tests for feature packages reside in the top-level `app/tests/` tree, mirroring the
package path.

**Constraints:**

- S5.1: Unit tests for `packages/X/` reside in `app/tests/unit/packages/X/`.
- S5.2: Integration tests for `packages/X/` reside in `app/tests/integration/packages/X/`.
- S5.3: Test fixtures specific to one package must be in that package's test `conftest.py`.
- S5.4: A package's test suite must not import from another package's test fixtures.

**Rationale:** The application is a single deployed unit, not extractable libraries.
Top-level aggregation is preferred per Cosmic Python project structure recommendations
and pytest "Good Integration Practices" documentation.

### Standard 6: Capability Promotion Lifecycle

When a feature-local capability is needed by multiple features, it must be promoted to
infrastructure through a governed workflow, not through cross-package imports.

**Promotion triggers (all three must be satisfied):**

| Trigger | Description | Test |
|---------|-------------|------|
| T1: Multi-consumer demand | ≥2 independent feature packages require the same capability | Count distinct consuming packages |
| T2: Operational centralization | Policy, SLA, audit, or security requirements mandate central ownership | Platform/infrastructure team must own versioning and compliance |
| T3: Contract stabilization | The capability's contract has stabilized as domain-neutral | The interface does not reference feature-specific domain types |

**Promotion workflow:**

```
1. Duplicate    → Feature B copies the capability from Feature A (temporary duplication)
2. Stabilize    → Both features converge on a shared contract (Protocol interface)
3. Extract      → Move implementation to infrastructure/<service>/ with Protocol
4. Provide      → Register provider in infrastructure/services/providers.py
5. Migrate      → Both features consume via infrastructure DI (ADR-0086)
```

**Constraints:**

- S6.1: Cross-package imports are never justified by shared need. Duplication is
  preferred until all three promotion triggers are met.
- S6.2: Promotion requires a new ADR (Tier-4 or Tier-5) documenting the extraction,
  the new Protocol, and the migration path for existing consumers.
- S6.3: The promoted capability must be owned by the infrastructure/platform team, not
  by either consuming feature team.
- S6.4: Promotion does not occur for feature-domain-specific logic. A capability that
  references feature-specific types (e.g., `AccessRequest`) is not promotable — it is
  a feature service that happens to be useful to another feature, and the features must
  communicate through events or hookspecs instead.

**Example:** Access Sync has `AwsIdentityStoreReconciler` (feature-local). If a
Provisioning feature also needs identity-store lifecycle control, the reconciler is
a promotion candidate only when: (a) both features need it, (b) the platform team
must own the AWS Identity Store integration centrally, and (c) the reconciler contract
does not reference Access-specific types.

### Standard 7: Package Registration Contract

Each feature package participates in the application through pluggy hookimpls exclusively.

**Constraints:**

- S7.1: For simple features, `__init__.py` is the sole entry point. For complex features,
  the umbrella `__init__.py` is the sole entry point; sub-capability `__init__.py` files
  contain no hookimpls.
- S7.2: Packages must not be imported directly by other application code outside plugin
  discovery. No module may write `from packages.access.sync.service import SyncService`.
- S7.3: HTTP route, platform command, event handler, and background job registration
  must each occur through their respective hookspec implementations, invoked from the
  umbrella (for complex features) or package-level (for simple features) `__init__.py`.
- S7.4: `auto_discover_plugins` continues to walk the full package tree recursively.
  Sub-capability `__init__.py` files without hookimpls are discovered but contribute
  nothing to the hook call loop — they are implementation details, not plugins.

## Alternatives Considered

1. **No cross-package import rule (rely on convention):**
   As the package count grows, undocumented cross-imports create invisible coupling.
   The `app/modules/` legacy tree demonstrates this failure mode.
   Why not chosen: convention alone failed to prevent coupling in `app/modules/`.

2. **No promotion lifecycle (promote ad hoc):**
   Without triggers and workflow, teams either duplicate excessively or create informal
   shared modules that violate boundaries. Promotion decisions are relitigated.
   Why not chosen: objective triggers and a phased workflow prevent both extremes.

3. **Colocated tests (tests inside each package):**
   Packages are not independently distributable. Fixture sharing requires cross-package
   test imports. Inconsistent with pytest "tests outside" recommendation for applications.
   Why not chosen: packages are internal decomposition, not reusable libraries.

4. **No shared kernel — sub-packages communicate only through infrastructure:**
   Forces domain events and value types into infrastructure where they don't belong.
   Creates artificial indirection for sub-packages in the same bounded context.
   Why not chosen: DDD Shared Kernel is the established pattern for intra-bounded-context
   shared types (Evans 2003).

5. **Sub-packages may freely import each other within the same parent:**
   Sub-packages lose independence. Changes to one can break another through internal
   imports. The benefit of decomposition (independent change cadence) is lost.
   Why not chosen: if sub-packages freely import internals, they are effectively one
   monolithic package.

## Consequences

**Positive:**

- Clear, enforceable package boundaries enable automated lint rules.
- Intra-package composition has explicit triggers and content constraints, eliminating
  ambiguity about `access/common/`.
- Capability promotion has a governed workflow, preventing both boundary violations
  and excessive duplication.
- New packages are created with a known template; code review has explicit criteria.

**Negative:**

- Cross-package communication requires infrastructure mediation, adding indirection.
  Intentional tradeoff.
- Capability promotion is deliberately friction-heavy (three triggers, ADR requirement).
  This is by design — premature extraction is worse than temporary duplication.
- The shared kernel constraint (value types only) may occasionally require refactoring.

**Neutral:**

- `app/modules/` is unaffected (frozen zone).
- Infrastructure services continue to be shared horizontally.

## Compliance and Boundaries

**This ADR governs:**

- Internal structure of feature packages in `app/packages/`.
- Cross-package import rules.
- Sub-package decomposition and shared kernel constraints.
- Feature-internal composition triggers and content rules.
- Capability promotion lifecycle.
- Test layout for feature packages.
- Package registration contract.

**This ADR does not govern:**

- `app/infrastructure/` structure (ADR-0076, ADR-0077).
- `app/modules/` structure (frozen zone).
- Infrastructure service consumption mechanics (ADR-0086).
- Multi-transport adapter patterns (ADR-0088).
- Barrel structure (ADR-0085).

**Enforcement:**

- Import-linter rules should detect `packages/X → packages/Y` imports in CI.
- Code review must verify Standard 3 constraints when sub-packages are modified.
- Promotion decisions (Standard 6) require an ADR before implementation.

## Best-Practice Revalidation

| Source | Claim Validated | Alignment |
|--------|----------------|-----------|
| Bogard, "Vertical Slice Architecture" (2018) | "Minimize coupling between slices, maximize coupling in a slice" | ✅ Standards 2, 3 |
| Jovanović, "Vertical Slice Architecture" | "All files for a single use case grouped inside one folder" | ✅ Standard 1 |
| Evans, *Domain-Driven Design* (2003) | Shared Kernel for intra-bounded-context shared types | ✅ Standard 3 permits `common/` with constraints |
| Cosmic Python (Percival & Gregory) | Tests in separate `tests/` tree for applications | ✅ Standard 5 |
| Pytest "Good Integration Practices" | "Tests outside application code" for non-distributable apps | ✅ Standard 5 |
| FastAPI "Bigger Applications" | `APIRouter` per feature with `include_router()` | ✅ Standard 7 + hookimpl registration |
| Pluggy documentation | Plugin discovery; opt-in hookimpl arguments | ✅ Standard 7 |
| Fowler, "Sacrifice one of a pair" principle | Duplication is cheaper than wrong abstraction | ✅ Standard 6 (duplicate before promote) |

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: Draft record. Pending challenge review.
- Follow-up actions:
  - Challenge review pending.

## Source References

| # | Source | URL | Key Insight |
|---|--------|-----|-------------|
| 1 | Jimmy Bogard, "Vertical Slice Architecture" (2018) | <https://jimmybogard.com/vertical-slice-architecture/> | Minimize coupling between slices; maximize within |
| 2 | Milan Jovanović, "Vertical Slice Architecture" | <https://www.milanjovanovic.tech/blog/vertical-slice-architecture> | High cohesion per use case |
| 3 | Eric Evans, *Domain-Driven Design* (2003) | — (book, ISBN 978-0321125217) | Shared Kernel pattern; bounded context |
| 4 | Pytest, "Good Integration Practices" | <https://docs.pytest.org/en/stable/explanation/goodpractices.html> | Tests outside application code |
| 5 | Percival & Gregory, *Architecture Patterns with Python* | <https://www.cosmicpython.com/book/appendix_project_structure.html> | Separate `tests/` tree |
| 6 | FastAPI, "Bigger Applications" | <https://fastapi.tiangolo.com/tutorial/bigger-applications/> | `APIRouter` per feature; `include_router()` |
| 7 | Pluggy Documentation | <https://pluggy.readthedocs.io/en/stable/> | Plugin discovery; opt-in hookimpl arguments |
| 8 | Martin Fowler, "Yagni" | <https://martinfowler.com/bliki/Yagni.html> | Duplication cheaper than wrong abstraction; extract when proven |

## Implementation Guidance

1. **New packages:** Must follow Standard 1 from creation. No grandfather clause.
2. **Existing packages:** Verify Standard 2 (cross-package imports) via import-linter
   or manual audit.
3. **Shared kernel audit:** Verify `access/common/` contains only value types, events,
   settings, and providers — no service classes. Violations must be refactored.
4. **Enforcement tooling:** Add import-linter configuration forbidding
   `packages.X → packages.Y` import paths in CI pipeline.

## Change Log

- 2026-05-06: Created. Scope includes cross-package isolation (Standard 2),
  sub-package boundaries (Standard 3), feature-internal composition (Standard 4),
  and capability promotion lifecycle (Standard 6). Addresses cross-ADR governance
  gaps identified in the 0085-0088 conflict analysis.
