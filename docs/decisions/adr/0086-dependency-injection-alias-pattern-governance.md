---
adr_id: ADR-0086
title: "Infrastructure Service Consumption Boundary Standard"
status: Draft
decision_type: Standard
tier: Tier-2
governance_domain: application
primary_domain: Dependency and Composition
secondary_domains:
  - Transport and API
  - Testing and Quality Gates
  - Package and Plugin Architecture
owners:
  - SRE Team
date_created: 2026-05-05
last_updated: 2026-05-06
last_reviewed: 2026-05-06
next_review_due: 2026-09-02
constrained_by:
  - ADR-0044
  - ADR-0045
  - ADR-0048
  - ADR-0049
  - ADR-0056
  - ADR-0063
  - ADR-0065
impacts:
  - ADR-0048
  - ADR-0049
  - ADR-0056
  - ADR-0063
supersedes: []
superseded_by: []
review_state: current
related_records:
  - ADR-0048
  - ADR-0049
  - ADR-0056
  - ADR-0063
  - ADR-0065
  - ADR-0077
  - ADR-0085
  - ADR-0087
  - ADR-0088
related_packages:
  - app/infrastructure/services
  - app/api
  - app/packages/access
  - app/packages/geolocate
---

# Infrastructure Service Consumption Boundary Standard

## Context

- Problem statement: There is no ADR that defines how feature packages, route handlers,
  and plugin hook implementations should consume infrastructure services. Three governing
  rules exist in adjacent ADRs (ADR-0048 B2: single injection surface; ADR-0048 B7:
  Protocol types at the surface; ADR-0056 S4: three-file DI alias ceremony), but they
  describe *where* infrastructure services come from, not *how* call sites receive and
  use them. The absence of this rule has led to three independent, inconsistent
  consumption patterns coexisting in the codebase, none of which was deliberately chosen.

  **The three call contexts and their current patterns:**

  | Call context | Current pattern | FastAPI DI used? |
  |---|---|---|
  | HTTP route handler (`app/api/`, `packages/*/interactions/http.py`) | Direct `get_x()` provider call at module level or inside handler body | No |
  | Pluggy hookimpl (`packages/*/__init__.py`) | Direct `get_x()` call inside hook function body | No (not applicable) |
  | Background job (`packages/*/` via `register_background_job`) | Direct `get_x()` call inside job function | No (not applicable) |

  **HTTP route handlers — no use of `Depends()` for infrastructure services:**

  The `packages/access/sync/interactions/http.py` route handlers call provider
  functions directly inside the handler body:

  ```python
  # access/sync/interactions/http.py — service obtained by direct call, not DI parameter
  from infrastructure.services import get_idempotency_service, t
  service = get_idempotency_service()
  ```

  By contrast, the same handlers *do* use FastAPI `Depends()` for their own
  package-local settings providers:

  ```python
  # access/sync/interactions/http.py — package-local settings via Depends()
  settings: Annotated[_AccessSyncSettingsPort, Depends(get_access_sync_settings)]
  ```

  This creates an asymmetry with no governing rationale: `Depends()` for own settings,
  direct call for infrastructure services. The asymmetry is present in every feature
  package that has HTTP interactions.

  **Pluggy hookimpl boundaries — DI is structurally inapplicable:**

  All feature package `__init__.py` files register hookimpls (Slack commands, route
  registration, startup warmup, event handler registration). These are plain Python
  functions called by the pluggy plugin manager — they have no FastAPI request context
  and `Depends()` cannot be used:

  ```python
  # access/sync/__init__.py — hookimpl calls provider directly; no alternative
  @hookimpl
  def startup_warmup(logger) -> None:
      dispatcher = get_event_dispatcher()   # must be a direct call
      dispatcher.register_handler(REQUEST_APPROVED, on_access_request_approved)
  ```

  There is no ADR that explicitly acknowledges this boundary, names it, or states
  whether direct provider calls are the canonical pattern for hookimpl contexts or a
  workaround that should eventually be replaced.

  **The `*Dep` aliases — speculative infrastructure never adopted:**

  ADR-0056 Standard 4 created `XDep = Annotated[X, Depends(get_x)]` aliases for every
  infrastructure service in `dependencies.py` on the assumption that HTTP route handlers
  would consume them. No handler ever did. The complete alias usage audit:

  | Alias | Defined in | Used by a real handler? |
  |-------|-----------|------------------------|
  | `StorageServiceDep` | `dependencies.py` | No — only in docstring examples in `providers.py` |
  | `AuditTrailServiceDep` | `dependencies.py` | No — only in docstring examples in `providers.py` |
  | `EventDispatcherDep` | `dependencies.py` | No — only in docstring examples in `providers.py` |
  | `AWSClientsDep` | `dependencies.py` | No — only in a `TYPE_CHECKING` guard in `clients/aws/__init__.py` |
  | All others | `dependencies.py` | No |

  This means the question of *whether* FastAPI `Depends()` should be used for
  infrastructure services in HTTP route handlers has never been answered. The aliases
  were created before the question was posed.

  **The technical distinction that makes this decision material:**

  | Mechanism | Lifecycle | Test substitution | Request scope |
  |---|---|---|---|
  | `Annotated[X, Depends(get_x)]` as route parameter | FastAPI resolves per-request; cached via `@lru_cache` inside `get_x` | `app.dependency_overrides[get_x] = lambda: stub` — per-test, no cache clearing | Yes — sub-dependency graph is explicit in the route signature |
  | `service = get_x()` inside handler body | Process-scoped singleton (lru_cache); caller ignores FastAPI | Requires `get_x.cache_clear()` in test teardown; easy to forget | No — dependency is hidden inside the handler |

  Both work for process-scoped singleton services. The difference is testability
  (explicit `dependency_overrides` vs manual cache clearing), discoverability (visible
  in the route signature vs hidden in the body), and alignment with FastAPI conventions.

  **The pluggy hookimpl pattern — compliance with pluggy best practices unknown:**

  Pluggy was adopted without prior experience (ADR-0049 governs startup reliability but
  not the *usage* pattern in feature packages). The current hookimpl pattern in feature
  `__init__.py` files has not been validated against pluggy best practices: whether
  hookimpl functions should be pure (no side effects) or may call provider functions,
  whether the hookspec signatures are structured correctly for the access patterns they
  serve, and whether the `hookimpl` import path (`from infrastructure.services import
  hookimpl`) is the intended or accidental coupling to the services barrel.

  **Relationship to ADR-0085 and ADR-0087:**

  ADR-0085 governs what the `infrastructure.services` barrel exports (structural).
  ADR-0087 governs what a vertically isolated feature package looks like and what it
  may import. This ADR governs the call-site mechanics: given that a feature package
  is allowed to consume an infrastructure service, *how* must it do so at each of the
  three call contexts (HTTP route, hookimpl, background job)?

- Business/operational drivers:
  - Establish canonical consumption patterns for each call context so that new features
    and route handlers are written consistently.
  - Resolve the asymmetry between `Depends()` usage for package-local settings and
    direct calls for infrastructure services in the same route handler.
  - Determine whether `app.dependency_overrides` or `@lru_cache` cache-clearing is the
    standard test substitution mechanism for infrastructure services.
  - Validate the pluggy hookimpl usage pattern against pluggy best practices and name
    whether direct provider calls in hookimpls are the canonical or fallback pattern.
  - Establish the correct posture for new features before ADR-0087 (vertical isolation)
    codifies the package boundary rules.

- Constraints:
  - ADR-0048 Boundary 2: the consumption surface must be stable and bounded — features
    must not import from infrastructure implementation modules.
  - ADR-0048 Boundary 7: Protocol types at the injection surface for Category A services.
    The call-site type annotation must use the Protocol, not the concrete class,
    regardless of whether the mechanism is `Depends()` or direct call.
  - ADR-0049: pluggy hookspecs and hookimpl semantics are governed. Any change to how
    hookimpls access services must be compatible with ADR-0049 startup phases.
  - ADR-0056 S3: the Composition Root (`providers.py`) is the authoritative source of
    provider functions. This ADR governs *how* those functions are called at the
    consumer side, not where they are defined.
  - ADR-0063: route handlers must be thin adapters (parse → invoke service → map
    response). The consumption pattern must not add ceremony that makes handlers thick.
  - `app/modules/` frozen zone is not modified. Legacy modules continue to use
    `get_settings()` directly regardless of this ADR's outcome.
  - The hookimpl call context is not a FastAPI context — `Depends()` cannot be used
    there. Whatever pattern governs hookimpl boundaries must be compatible with the
    pluggy call model.

- Non-goals:
  - This record does not govern what the `infrastructure.services` barrel exports
    (governed by ADR-0085).
  - This record does not govern the internal structure of feature packages or
    cross-package import rules (governed by ADR-0087).
  - This record does not define transport-agnostic interaction dispatch
    (governed by ADR-0088).
  - This record does not change service constructor signatures or Protocol definitions
    (governed by ADR-0077).
  - This record does not govern the `@lru_cache` singleton provider pattern itself
    (governed by ADR-0056).

- Research required before Decision:
  - **Pluggy best practices for hookimpl bodies:** The hookimpl boundary is a call
    context where FastAPI `Depends()` cannot be used — direct provider calls are the
    only current mechanism available. Before this ADR can decide whether to (a) ratify
    direct provider calls as the canonical hookimpl pattern, or (b) restructure hookspec
    signatures to pass all required services as arguments (eliminating provider calls
    from hookimpl bodies entirely), online research is needed into pluggy authoring
    conventions: how mature pluggy-based Python projects structure hookimpl functions,
    whether hookimpls are expected to be pure (all dependencies injected via args) or may
    perform service lookup internally, and what FastAPI + pluggy integration patterns are
    used in production codebases.
  - **FastAPI Depends() for process-scoped singletons — best practices:** The core
    question of whether FastAPI `Depends()` should be used for infrastructure services
    that are process-scoped singletons (not per-request objects) requires review of the
    FastAPI documentation on `use_cache`, the `Annotated` dependency pattern, and
    community guidance on the `dependency_overrides` testing model vs `lru_cache`
    cache-clearing. This research must precede the Decision section.

## Decision

*TBD — pending Context review and author approval.*

## Alternatives Considered

*TBD*

## Consequences

*TBD*

## Compliance and Boundaries

*TBD*

## Best-Practice Revalidation

*TBD*

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

*TBD*

## Implementation Guidance

*TBD*

## Change Log

- 2026-05-05: Created as Draft. Split from ADR-00XX (Infrastructure Services Barrel Export Dissolution). Scoped to the DI alias pattern governance question only: whether infrastructure services should be consumed via FastAPI `Depends()` or direct provider calls, and what form that consumption should take. Barrel structure separation governed by ADR-0085.
