---
adr_id: ADR-0085
title: "Infrastructure Services Barrel Dissolution"
status: Draft
decision_type: Standard
tier: Tier-2
governance_domain: application
primary_domain: Dependency and Composition
secondary_domains:
  - Package and Plugin Architecture
owners:
  - SRE Team
date_created: 2026-05-05
last_updated: 2026-05-05
last_reviewed: 2026-05-05
next_review_due: 2026-09-02
constrained_by:
  - ADR-0044
  - ADR-0045
  - ADR-0048
  - ADR-0056
  - ADR-0076
impacts:
  - ADR-0056
supersedes: []
superseded_by: []
review_state: current
related_records:
  - ADR-0048
  - ADR-0056
  - ADR-0076
  - ADR-0086
related_packages:
  - app/infrastructure/services
---

# Infrastructure Services Barrel Dissolution

## Context

- Problem statement: After Phase 1 and Phase 2 of the infrastructure refactoring
  programme, `app/infrastructure/services/__init__.py` has grown into a single barrel
  module that re-exports approximately 40+ symbols drawn from ~12 unrelated service
  packages (`storage`, `audit`, `events`, `notifications`, `platforms`, `directory`,
  `clients/aws`, `clients/google_workspace`, `clients/maxmind`, `i18n`, `idempotency`,
  `resilience`, plus plugin infrastructure and security primitives). The package owns
  none of those service domains; it is the Composition Root for cross-service wiring
  (via `providers.py`), not an aggregation point for unrelated service public APIs.

  The three-file structure that produced this state:

  | File | Lines | Role |
  |------|-------|------|
  | `providers.py` | ~700 | `@lru_cache` singleton factories — the Composition Root |
  | `dependencies.py` | ~140 | `Annotated[X, Depends(get_x)]` declarations for every provider |
  | `__init__.py` | ~70 | Re-exports everything from both files plus plugin, security, and i18n symbols |

  ADR-0056 Standard 3 explicitly approved `providers.py` as the Composition Root and
  justified centralization of cross-service wiring there. That role is architecturally
  sound and is not challenged by this ADR.

  The problem is that ADR-0056 Standard 4 (the three-file ceremony) caused every new
  service to be registered in `providers.py`, declared in `dependencies.py`, and
  re-exported from `__init__.py`. The cumulative effect is that `infrastructure.services`
  now acts as a **Service Locator**: any module in the codebase can obtain any service by
  importing from this single address, without declaring a dependency on the package that
  defines the service. This is the pattern explicitly distinguished from and opposed to
  the Composition Root by Mark Seemann's original formulation (cited in ADR-0056's own
  source references).

  **The Composition Root / Service Locator distinction:**

  | Role | Pattern | Location | Status |
  |------|---------|----------|--------|
  | Wires cross-service dependencies on behalf of the whole application | Composition Root ✅ | `providers.py` | Legitimate, retain |
  | Exposes every service at a global address for any consumer to query | Service Locator ❌ | `__init__.py` (as currently structured) | Antipattern, dissolve |

  **Concrete evidence of the Service Locator symptom:**

  Every feature package `__init__.py` contains:

  ```python
  from infrastructure.services import hookimpl
  ```

  This single import causes Python to execute the full `infrastructure/services/__init__.py`,
  which in turn imports `providers.py`, which imports every infrastructure service module
  at the top level — including heavy SDK client wrappers (`AWSClients` via boto3,
  `GoogleWorkspaceClients` via google-auth, `MaxMindClient` via the maxmind reader).
  A feature package that uses none of these services pays the full import cost solely
  to obtain the `hookimpl` decorator, a symbol that has no relationship to any of them.

  **Ownership violation:**

  The purpose of a Python package's `__init__.py` is to expose the public API of that
  package. `infrastructure/services/` owns: the plugin lifecycle (`hookimpl`,
  `get_plugin_manager`, etc.), the Composition Root (`providers.py` and its cross-service
  wiring), and cross-cutting security primitives (`get_current_user`, `get_limiter`).
  It does not own storage, audit, events, notifications, platforms, or any other service
  domain. Re-exporting those symbols from `__init__.py` is a violation of the ownership
  principle (ADR-0047 P2: ownership follows code).

  **Relationship to ADR-0086:**

  This ADR governs only the barrel structure: what `infrastructure/services/__init__.py`
  is permitted to re-export, and whether `dependencies.py` should exist as an
  aggregation file. Whether `*Dep = Annotated[X, Depends(get_x)]` pre-declarations
  should exist at all — and if so, where — is a separate governance question addressed
  in ADR-0086. This ADR does not prejudge that outcome: the barrel can be narrowed
  regardless of whether aliases survive, are colocated, or are eliminated entirely.

- Business/operational drivers:
  - Eliminate the transitive import burden: a feature package that imports only
    `hookimpl` should not trigger loading of boto3 and google-auth SDK clients.
  - Align `infrastructure/services/__init__.py` with the Python package convention:
    a package's public API should reflect what that package owns.
  - Remove the structural condition that lets any module obtain any service without
    declaring a dependency on the package that defines it.
  - Stop the incremental growth: every new infrastructure service currently requires
    three file edits (`providers.py`, `dependencies.py`, `__init__.py`), adding to the
    barrel regardless of whether the barrel consumer set grows.

- Constraints:
  - ADR-0048 Boundary 2 requires a single, defined injection surface. This constrains
    what the dissolution can look like: the result must still provide a stable,
    discoverable import path for each service — it just does not have to be a single
    address for all services simultaneously.
  - ADR-0056 Standard 3 (two-tier location rule, amended 2026-05-04): cross-service
    composition providers must remain defined in `providers.py`. This constraint is
    not altered; the question is only what the barrel re-exports on top of that.
  - ADR-0076 Standard 3: service composition only in `providers.py`. Retained.
  - The `app/modules/` frozen zone imports from `infrastructure.services` (9 files using
    `get_settings()`). Any dissolution must not break these consumers. Re-export bridges
    or backward-compat stubs are required for frozen zone paths.
  - Plugin infrastructure symbols (`hookimpl`, `get_plugin_manager`,
    `discover_and_init_features`, `collect_feature_i18n_resources`) are legitimately
    owned by `infrastructure/services/` and must remain re-exported from it. The barrel
    dissolution must not break the `from infrastructure.services import hookimpl` pattern
    used by every feature package `__init__.py`.

- Non-goals:
  - This record does not decide whether `*Dep` alias pre-declarations should exist, be
    colocated, or be eliminated (governed by ADR-0086).
  - This record does not move or dissolve `providers.py` as the Composition Root.
  - This record does not redistribute Level 2 or Level 3 (cross-service composition)
    providers away from `providers.py`.
  - This record does not change service constructor signatures or Protocol definitions.
  - This record does not govern the DI alias adoption pattern in route handlers or
    feature packages (governed by ADR-0086).

## Decision

_TBD — pending Context review and author approval._

## Alternatives Considered

_TBD_

## Consequences

_TBD_

## Compliance and Boundaries

_TBD_

## Best-Practice Revalidation

_TBD_

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: Draft record. Context under author review. Decision not yet written.
- Follow-up actions:
  - Confirm Context with author.
  - Proceed to Decision section once Context is approved.
  - Challenge review (Round 1) after Decision section is complete.

## Source References

_TBD_

## Implementation Guidance

_TBD_

## Change Log

- 2026-05-05: Created as Draft. Split from ADR-00XX (Infrastructure Services Barrel Export Dissolution). Scoped to the structural barrel problem only: `infrastructure/services/__init__.py` as Service Locator. DI alias adoption pattern separated into ADR-0086.
