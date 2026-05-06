---
adr_id: ADR-0085
title: "Infrastructure Import and Barrel Governance"
status: Draft
decision_type: Standard
tier: Tier-2
governance_domain: application
primary_domain: Dependency and Composition
secondary_domains:
  - Package and Plugin Architecture
  - Runtime and Lifecycle
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
  - ADR-0076
impacts:
  - ADR-0086
supersedes:
  - ADR-0056 (partial: Standard 3.2 re-export requirement; Standard 4 ceremony rules C2, C3)
superseded_by: []
review_state: current
related_records:
  - ADR-0046
  - ADR-0048
  - ADR-0056
  - ADR-0076
  - ADR-0077
  - ADR-0086
  - ADR-0087
related_packages:
  - app/infrastructure/services
---

# Infrastructure Import and Barrel Governance

## Context

- Problem statement: `app/infrastructure/services/__init__.py` has grown into a barrel
  module that re-exports approximately 40+ symbols drawn from ~12 unrelated service
  packages. The package owns none of those service domains; it is the Composition Root
  for cross-service wiring (via `providers.py`), not an aggregation point for unrelated
  service public APIs.

  The three-file structure:

  | File | Lines | Role |
  |------|-------|------|
  | `providers.py` | ~700 | `@lru_cache` singleton factories — the Composition Root |
  | `dependencies.py` | ~140 | `Annotated[X, Depends(get_x)]` declarations for every provider |
  | `__init__.py` | ~70 | Re-exports everything from both files plus plugin, security, and i18n symbols |

  ADR-0056 Standard 3 correctly approved `providers.py` as the Composition Root. The
  problem is that the three-file ceremony (ADR-0056 Standard 4) caused `__init__.py`
  to act as a **Service Locator**: any module can obtain any service by importing from
  a single address without declaring a dependency on the owning package.

  **The Composition Root / Service Locator distinction:**

  | Role | Pattern | Location | Status |
  |------|---------|----------|--------|
  | Wires cross-service dependencies for the whole application | Composition Root ✅ | `providers.py` | Legitimate, retain |
  | Exposes every service at a global address for any consumer | Service Locator ❌ | `__init__.py` (current) | Antipattern, dissolve |

  **Concrete import-cost evidence:**

  Every feature package `__init__.py` contains `from infrastructure.services import hookimpl`.
  This single import executes the full `__init__.py`, which imports `providers.py`, which
  imports every infrastructure service module — including heavy SDK wrappers (boto3,
  google-auth, MaxMind). A feature that uses none of these pays the full import cost
  solely to obtain the `hookimpl` decorator.

  **Missing governance identified by cross-ADR analysis:**

  Earlier iterations of barrel governance and service consumption addressed overlapping
  concerns (barrel structure and consumption mechanics) as separate local optimizations
  without:

  1. A composition root placement policy — no decision criterion for when restructuring
     the composition root location is justified vs when depth signals ownership.
  2. An import-time performance contract — no measurable constraint on barrel or
     provider import side effects.
  3. A clear distinction between physical module location and logical composition role.

  These gaps caused recurring review friction where discussions revisited naming and
  location instead of behavior and invariants.

- Business/operational drivers:
  - Eliminate transitive import burden: `from infrastructure.services import hookimpl`
    should not trigger loading of boto3, google-auth, and maxmind SDKs.
  - Align `__init__.py` with Python package conventions: expose only owned public API.
  - Remove the Service Locator structural condition.
  - Establish composition root placement criteria that end recurring location debates.

- Constraints:
  - ADR-0048 Boundary 2: a single, defined injection surface must exist.
  - ADR-0056 Standard 3: cross-service composition providers remain in `providers.py`.
  - ADR-0076 Standard 3: service composition only in `providers.py`.
  - `app/modules/` frozen zone imports from `infrastructure.services` — must not break.
  - Plugin infrastructure symbols (`hookimpl`, `get_plugin_manager`,
    `discover_and_init_features`, `collect_feature_i18n_resources`) are legitimately
    owned by `infrastructure/services/` and must remain importable from it.

- Non-goals:
  - This record does not govern *how* consumers call provider functions at each call
    context (governed by ADR-0086).
  - This record does not move or dissolve `providers.py`.
  - This record does not change service constructor signatures or Protocol definitions.
  - This record does not govern feature package structure (governed by ADR-0087).

## Decision

The `infrastructure/services/__init__.py` barrel is dissolved to re-export only symbols
that `infrastructure/services/` owns. Consumers use deep import paths. The Composition
Root (`providers.py`) is retained with a placement policy. An import-time performance
contract prevents regression.

### Standard 1: Barrel Scope Reduction — Owned Symbols Only

`infrastructure/services/__init__.py` may re-export only symbols that the
`infrastructure/services/` package itself defines or directly owns.

**Symbols retained in `__init__.py` (owned by this package):**

| Symbol | Source Module | Ownership Rationale |
|--------|--------------|---------------------|
| `hookimpl` | `infrastructure.services.plugins` | Plugin lifecycle owned by this package |
| `get_plugin_manager` | `infrastructure.services.plugins` | Plugin lifecycle owned by this package |
| `discover_and_init_features` | `infrastructure.services.plugins` | Feature discovery owned by this package |
| `collect_feature_i18n_resources` | `infrastructure.services.plugins` | Feature discovery owned by this package |
| `register_feature_integrations` | `infrastructure.services.plugins` | Feature integration registration owned by this package |

**Symbols removed (not owned — must use deep imports):**

All provider functions, all DI aliases, all Protocol types, all client facades, and all
utility functions originating in sibling packages.

Notable migration targets for widely used non-owned symbols:

| Current Barrel Import | Deep Import Target |
|---|---|
| `from infrastructure.services import get_event_dispatcher` | `from infrastructure.services.providers import get_event_dispatcher` |
| `from infrastructure.services import t` | `from infrastructure.services.providers import t` |
| `from infrastructure.services import get_current_user` | `from infrastructure.security.current_user import get_current_user` |
| `from infrastructure.services import get_limiter` | `from infrastructure.security.rate_limiter import get_limiter` |

**Constraints:**

- S1.1: `__init__.py` must declare `__all__` listing only retained symbols.
- S1.2: No new symbols may be added unless defined within `infrastructure/services/`
  itself (not re-exported from elsewhere).
- S1.3: If plugin infrastructure is later extracted to its own package (e.g.,
  `infrastructure/plugins/`), `__init__.py` becomes empty.

### Standard 2: Consumer Import Path — Deep Imports Required

Consumers must import provider functions, Protocol types, and service facades from their
defining modules, not from the barrel.

```python
# CORRECT — deep import from the defining module
from infrastructure.services.providers import get_event_dispatcher
from infrastructure.services.providers import get_storage_service
from infrastructure.events.protocol import EventDispatcherProtocol
from infrastructure.storage.protocol import StorageService

# PROHIBITED — barrel re-export of non-owned symbols
from infrastructure.services import get_event_dispatcher
from infrastructure.services import get_storage_service
```

**Exception:** Plugin infrastructure symbols remain importable from the barrel because
they are owned by that package:

```python
# CORRECT — owned symbol, barrel import is canonical
from infrastructure.services import hookimpl
```

**Constraints:**

- S2.1: New code must use deep import paths for all provider functions and service types.
- S2.2: Existing code is migrated as files are touched. The barrel retains backward-
  compatibility re-exports temporarily, marked deprecated.
- S2.3: The frozen zone (`app/modules/`) is exempt from migration. Compatibility
  re-exports are retained as long as the frozen zone exists.

### Standard 3: `dependencies.py` Dissolution

The centralized `infrastructure/services/dependencies.py` file is dissolved. DI type
aliases (`Annotated[Protocol, Depends(get_x)]`) are owned by their consumers, not
declared centrally.

**Constraints:**

- S3.1: No new DI aliases may be added to `dependencies.py`.
- S3.2: Existing aliases are migrated to consumer-owned declarations (per ADR-0086 S1.4).
- S3.3: Once all consumers are migrated, `dependencies.py` is deleted.
- S3.4: During migration, `dependencies.py` may remain with a deprecation comment.

**Rationale:** Centralized alias declarations create the Service Locator symptom. Every
import from `dependencies.py` triggers the full barrel load. Consumer-owned aliases import
only the specific provider function needed.

### Standard 4: Composition Root Placement Policy

`infrastructure/services/providers.py` is retained as the Composition Root. Its location
is governed by placement criteria, not path brevity.

**Placement criteria (must all be satisfied to justify relocation):**

| Criterion | Test |
|-----------|------|
| Ownership clarity | The new location must unambiguously signal "this module composes cross-service dependencies" |
| Change isolation | Moving must not increase the blast radius of provider changes on consumers |
| Import graph impact | Moving must produce a measurable reduction in import graph complexity or startup time |
| Migration safety | A codemod plan and import-compatibility bridge must exist before any relocation |

**Constraints:**

- S4.1: `providers.py` remains the canonical home for all `@lru_cache` provider
  functions that compose infrastructure services.
- S4.2: Consumers import provider functions from `providers.py` using deep imports:
  `from infrastructure.services.providers import get_x`.
- S4.3: `providers.py` is permitted to import from any infrastructure package at the
  top level (it is the Composition Root — this is its job).
- S4.4: Relocation of the Composition Root requires a new ADR or amendment to this one,
  satisfying all four placement criteria with evidence. Path brevity alone is not
  sufficient justification.

### Standard 5: Frozen Zone Backward Compatibility

The `app/modules/` frozen zone uses barrel imports. These must not break.

**Constraints:**

- S5.1: Barrel re-exports used exclusively by frozen zone code are retained in
  `__init__.py` until the frozen zone is thawed.
- S5.2: These re-exports are marked: `# COMPAT: frozen zone — remove when app/modules/ is migrated`.
- S5.3: No non-frozen-zone code may import these compatibility re-exports.

### Standard 6: Import-Time Performance Contract

The barrel dissolution must not regress import-time performance, and must establish
a measurable baseline to prevent future regression.

**Constraints:**

- S6.1: Importing `from infrastructure.services import hookimpl` must not trigger
  loading of SDK client modules (boto3, google-auth, maxmind).
- S6.2: Provider functions in `providers.py` that construct heavy clients must use
  lazy initialization inside the `@lru_cache` function body, not at module import time.
- S6.3: No module in `infrastructure/services/` may execute network calls, file I/O,
  or SDK client construction at import time.
- S6.4: These constraints complement ADR-0046 startup phase ordering. Provider
  functions that trigger heavy initialization at import time would bypass the
  lifespan's managed startup sequence (ADR-0046 Invariant 2). S6.1–S6.3 ensure
  service construction occurs during lifespan execution, not during module loading.

## Alternatives Considered

1. **Retain the current barrel (status quo):**
   Every `from infrastructure.services import hookimpl` triggers loading of all SDKs.
   The barrel grows with every new service. Ownership principle is violated.
   Why not chosen: Service Locator antipattern is well-documented (Seemann 2011).

2. **Full dissolution including plugin symbols (empty `__init__.py`):**
   Forces every feature package to change `from infrastructure.services import hookimpl`
   to a deeper path. High churn for no architectural benefit — plugin symbols are
   legitimately owned.
   Why not chosen: dissolving owned symbols violates Python conventions.

3. **Split `providers.py` into per-service provider modules:**
   Distributes the Composition Root across multiple files. Loses single-assembly-point
   visibility. Violates ADR-0076 S3.
   Why not chosen: Composition Root is architecturally correct at current size.

4. **Lazy imports in `__init__.py`:**
   Retains barrel API while eliminating import cost. Violates PEP 8 import conventions.
   Makes IDE tooling unreliable. Does not address the ownership violation.
   Why not chosen: solves the performance symptom but not the architectural problem.

5. **Flatten composition root to `infrastructure/providers.py`:**
   Simpler path. But loses the ownership signal that `services/` communicates and
   violates the placement criteria (no measurable import graph improvement, increased
   blast radius from being at a higher directory level).
   Why not chosen: path brevity does not justify relocation when ownership clarity
   decreases.

## Consequences

**Positive:**

- `from infrastructure.services import hookimpl` no longer triggers full SDK loading.
- Ownership principle restored: `__init__.py` exposes only what the package owns.
- Service Locator symptom eliminated.
- New services no longer require `__init__.py` edits.
- IDE "go to definition" navigates to the actual module.
- Composition root location debates have objective criteria.

**Negative:**

- Migration effort: existing imports must be updated (mechanical, search-and-replace).
- Frozen zone compatibility re-exports add temporary `__init__.py` complexity.
- Deep imports are slightly more verbose. Intentional tradeoff.

**Neutral:**

- `providers.py` unchanged. Composition Root pattern preserved.
- Service contracts and Protocol definitions unchanged.
- Test infrastructure unaffected.

## Compliance and Boundaries

**This ADR governs:**

- Content of `infrastructure/services/__init__.py` (what it may re-export).
- Canonical import path for provider functions and service types.
- Dissolution of `infrastructure/services/dependencies.py`.
- Composition root placement criteria.
- Import-time performance constraints.
- Backward compatibility for the frozen zone.

**Supersession of ADR-0056 provisions:**

This ADR partially supersedes ADR-0056. Specifically:

- ADR-0056 Standard 3.2 required self-contained providers to be re-exported through
  `infrastructure.services.__init__.py` for ADR-0048 B2 compliance. This ADR's
  Standard 1 replaces that requirement: `__init__.py` re-exports only owned symbols.
  The evidence (PEP 8 explicit imports, Google Style Guide §2.2.4, Seemann's
  Composition Root pattern) supports deep imports over barrel re-exports.
- ADR-0056 Standard 4 ceremony rules C2 ("every alias in `dependencies.py` must be
  re-exported from `__init__.py`") and C3 ("every provider in `providers.py` must be
  re-exported from `__init__.py`") are superseded by Standards 1–3 of this ADR.
  Consumer-owned DI aliases (ADR-0086 S6) replace the centralized ceremony.

ADR-0056 provisions that remain in force: Standard 1 (narrow-slice injection),
Standard 2 (package-local providers), Standard 3.1 (cross-service composition in
`providers.py`), Standard 5 (convenience accessors), Standard 6 (graph shape),
Standard 7 (translation helper), Standard 8 (backend selection).

**Injection surface after dissolution (ADR-0048 B2 evolution):**

ADR-0048 Boundary 2 defines a single injection surface for feature consumers. After
barrel dissolution, the injection surface is redefined as:

| Permitted Import Path | Content | Consumer |
|---|---|---|
| `infrastructure.services` | Owned symbols only: `hookimpl`, `get_plugin_manager`, `discover_and_init_features`, `collect_feature_i18n_resources` | All feature packages |
| `infrastructure.services.providers` | All `@lru_cache` provider functions | Hookimpls, background jobs, feature providers |
| `infrastructure.<domain>.protocol` | Protocol types for Category A services | Route handler DI aliases, type annotations |

Concrete implementation modules (`infrastructure.<domain>.service`,
`infrastructure.<domain>.dynamodb`, etc.) remain **off-limits** for feature consumers.
This redefinition narrows ADR-0048 B2 from "one barrel address" to "three explicit
import categories" — each with clear ownership and purpose.

**This ADR does not govern:**

- How consumers call provider functions (governed by ADR-0086).
- Protocol definitions or service contracts (governed by ADR-0077).
- Intra-layer import rules for infrastructure packages (governed by ADR-0076).
- Feature package structure (governed by ADR-0087).

**Enforcement:**

- Lint rule should flag imports from `infrastructure.services` that reference non-owned
  symbols (anything other than `hookimpl`, `get_plugin_manager`,
  `discover_and_init_features`, `collect_feature_i18n_resources`). This includes
  frozen-zone compatibility re-exports (S5.1) used by non-frozen-zone code.
- Code review must verify deep imports from `providers.py` in new code.

## Best-Practice Revalidation

| Source | Claim Validated | Alignment |
|--------|----------------|-----------|
| Python Language Reference §5.2.1 | `__init__.py` executes on any import of the package | ✅ Dissolution eliminates unnecessary execution |
| Google Python Style Guide §2.2.4 | Prefer explicit module-level imports over barrel shorthand | ✅ Deep imports follow this guidance |
| Google Python Style Guide §2.5 | Avoid mutable global state; barrel files amplify side-effect risk | ✅ Reduced barrel eliminates unnecessary side effects |
| PEP 8 "Imports" | Explicit imports; each import should be traceable | ✅ Deep imports are maximally explicit |
| Mark Seemann (2011) | Service Locator = global registry; Composition Root = single assembly | ✅ S1 dissolves the locator; S4 preserves the root |
| Hagemeister, "Barrel File Debacle" (2023) | Barrel files inflate module graphs and degrade performance | ✅ Dissolution addresses directly |

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
| 1 | Python Language Reference §5.2.1 | <https://docs.python.org/3/reference/import.html#regular-packages> | `__init__.py` executes on any import of the package |
| 2 | Google Python Style Guide §2.2.4 | <https://google.github.io/styleguide/pyguide.html#224-decision> | Prefer explicit module-level imports over barrel shorthand |
| 3 | Google Python Style Guide §2.5 | <https://google.github.io/styleguide/pyguide.html#25-mutable-global-state> | Avoid mutable global state; minimize import-time execution |
| 4 | PEP 8 "Imports" | <https://peps.python.org/pep-0008/#imports> | Explicit imports, no wildcard; each import traceable |
| 5 | Marvin Hagemeister, "Speeding up the JavaScript ecosystem — The barrel file debacle" (2023) | <https://marvinh.dev/blog/speeding-up-javascript-ecosystem-part-7/> | Barrel files inflate module graphs and degrade performance |
| 6 | Mark Seemann, *Dependency Injection in .NET* (2011) | — (book, ISBN 978-1935182504) | Composition Root ≠ Service Locator; the barrel is the latter |

## Implementation Guidance

1. **Phase 1 — Narrow the barrel:** Remove non-owned re-exports from `__init__.py`.
   Add frozen-zone compat re-exports with `# COMPAT` markers. Add `__all__`.
2. **Phase 2 — Migrate active codebase:** Search-and-replace
   `from infrastructure.services import <provider>` →
   `from infrastructure.services.providers import <provider>` in `app/packages/` and
   `app/api/`. Mechanical migration.
3. **Phase 3 — Dissolve `dependencies.py`:** Migrate alias consumers to consumer-owned
   declarations per ADR-0086 S1.4. Delete `dependencies.py` when empty.
4. **Phase 4 — Performance baseline:** Measure import time for
   `from infrastructure.services import hookimpl` before and after dissolution.
   Record baseline for regression detection.

## Change Log

- 2026-05-06: Created. Scope includes barrel dissolution (Standards 1–3), composition
  root placement policy (Standard 4), frozen zone compatibility (Standard 5), and
  import-time performance contract (Standard 6). Addresses cross-ADR governance gaps
  identified in the 0085-0088 conflict analysis.
- 2026-05-06: Challenge review revisions. Declared partial supersession of ADR-0056
  S3.2 and S4 C2/C3 (barrel re-export ceremony). Added injection surface definition
  to Compliance section (ADR-0048 B2 evolution). Added `register_feature_integrations`
  to retained symbols list. Added migration target table for widely used non-owned
  symbols (`t`, `get_current_user`, `get_limiter`). Fixed metadata: removed ADR-0056
  from `constrained_by`, added to `supersedes` (partial).
