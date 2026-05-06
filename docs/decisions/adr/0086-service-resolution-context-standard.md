---
adr_id: ADR-0086
title: "Service Resolution Context Standard"
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
date_created: 2026-05-06
last_updated: 2026-05-06
last_reviewed: 2026-05-06
next_review_due: 2026-09-03
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

# Service Resolution Context Standard

## Context

- Problem statement: Three call contexts exist in the codebase (HTTP route handlers,
  pluggy hookimpls, background jobs) that consume infrastructure services. Each context
  has a structurally different relationship to dependency injection, but no ADR provides
  a single, table-driven standard that developers can apply without reading multiple
  records.

  The previous drafts of ADR-0085 and ADR-0086 addressed barrel structure and consumption
  mechanics as separate local optimizations. The cross-ADR analysis found that developers
  could not consistently determine the correct resolution mechanism for a given context
  because guidance was fragmented across two ADRs. Some developers interpreted any direct
  `get_x()` call as always acceptable (reading old 0086 S2/S3), while others treated it
  as always prohibited (reading old 0086 S1). Neither interpretation is correct; the
  answer depends on the call context.

  **The structural asymmetry:**

  | Call Context | FastAPI DI Available? | Why |
  |---|---|---|
  | HTTP route handler | ✅ Yes | Runs inside FastAPI request lifecycle |
  | Pluggy hookimpl | ❌ No | Runs during startup or plugin invocation; no request context |
  | Background job | ❌ No | Runs in-process on a timer; no request context |
  | Module-level code | ❌ No | Runs at import time; no application context |

  This asymmetry is **structural and permanent**: FastAPI provides a DI container only
  within the request lifecycle. Hookimpls and background jobs execute outside it. The
  correct DI mechanism is therefore determined by ownership scope and contract stability,
  not by code location.

  **The anti-pattern that must be testable:**

  Developers need a single question to determine if their code is correct:

  > "Am I inside a FastAPI route handler? If yes, use `Depends()`. If no, call the
  > provider directly inside the function body. Never call providers at module level."

  The previous ADRs failed to provide this single-question test.

- Business/operational drivers:
  - Provide one table-driven standard that maps call context → resolution mechanism →
    test override method → prohibited forms.
  - Eliminate the ambiguity where developers apply hookimpl rules to route handlers
    or vice versa.
  - Establish that the asymmetry is intentional architecture, not inconsistency.

- Constraints:
  - ADR-0048 Boundary 7: Protocol types at the injection surface for Category A services.
  - ADR-0049: pluggy hookspecs govern hookimpl invocation semantics.
  - ADR-0056 S3: `providers.py` is the Composition Root.
  - ADR-0063: route handlers must be thin adapters.
  - `app/modules/` frozen zone is not modified.

- Non-goals:
  - This record does not govern what `infrastructure.services` exports (ADR-0085).
  - This record does not govern feature package structure (ADR-0087).
  - This record does not govern transport adapter patterns (ADR-0088).
  - This record does not govern provider function definitions (ADR-0056).

## Decision

Infrastructure services are consumed differently depending on the call context. The
asymmetry is **structural and intentional**: FastAPI provides a DI container; pluggy and
background jobs do not. Each context uses its native mechanism. This is a first-class
architectural principle, not an exception.

### Standard 1: Context Resolution Matrix

This is the canonical, single-source standard for how infrastructure services are
resolved. All other standards in this ADR elaborate on this table.

| Call Context | Resolution Mechanism | Type Annotation | Test Override | Prohibited |
|---|---|---|---|---|
| **HTTP route handler** | `Annotated[Protocol, Depends(get_x)]` as function parameter | Protocol (Cat A) or concrete (Cat B) | `app.dependency_overrides[get_x] = lambda: stub` | Direct `get_x()` call in handler body |
| **Pluggy hookimpl** | `get_x()` call inside function body | Protocol (Cat A) or concrete (Cat B) | `get_x.cache_clear()` + monkeypatch/mock | `Depends()` (no FastAPI context); module-level `get_x()` |
| **Background job** | `get_x()` call inside function body | Protocol (Cat A) or concrete (Cat B) | `get_x.cache_clear()` + monkeypatch/mock | `Depends()` (no FastAPI context); module-level `get_x()` |
| **Module-level code** | ❌ Prohibited | — | — | Any `get_x()` call at import time |

**The single-question test:**

> Am I in a FastAPI route handler? → Use `Depends()`.
> Am I in a hookimpl or background job? → Call provider in function body.
> Am I at module level? → Do not call providers.

### Standard 2: HTTP Route Handlers — FastAPI `Depends()` Required

All HTTP route handler functions (in `app/api/` and `packages/*/interactions/http.py`)
must receive infrastructure services as `Annotated[Protocol, Depends(get_x)]` function
parameters.

```python
# CORRECT — infrastructure service as explicit DI parameter
from infrastructure.services.providers import get_event_dispatcher
from infrastructure.events.protocol import EventDispatcherProtocol

EventDispatcherDep = Annotated[EventDispatcherProtocol, Depends(get_event_dispatcher)]

@router.post("/sync")
async def trigger_sync(
    dispatcher: EventDispatcherDep,
    settings: AccessSyncSettingsDep,
) -> SyncResponse:
    ...
```

```python
# PROHIBITED — hidden dependency inside handler body
@router.post("/sync")
async def trigger_sync() -> SyncResponse:
    dispatcher = get_event_dispatcher()  # ❌ bypasses DI
    ...
```

**Constraints:**

- S2.1: The type annotation must use the Protocol type (not concrete class) for
  Category A services. Category B services (shared utilities) may use concrete types.
- S2.2: The `Depends()` callable must be the `@lru_cache` provider function from
  `providers.py` — not a wrapper, lambda, or intermediate function.
- S2.3: Test substitution uses `app.dependency_overrides[get_x] = lambda: stub`. No
  `cache_clear()` is required or permitted in route handler tests.
- S2.4: The `Annotated[X, Depends(get_x)]` type alias may be defined at the module
  level of the consuming file or in a package-local `dependencies.py` file. There is
  no centralized `dependencies.py` requirement.

**Rationale:** FastAPI's dependency system makes dependencies explicit in the function
signature, enables `dependency_overrides` for clean per-test substitution without cache
manipulation, and surfaces the dependency graph in OpenAPI documentation. Bypassing it
creates hidden dependencies that violate the "thin adapter" principle (ADR-0063).

### Standard 3: Pluggy Hookimpls — Direct Provider Calls Canonical

Pluggy hookimpl functions obtain infrastructure services by calling provider functions
directly inside the function body. This is the canonical pattern, not a workaround.

```python
# CORRECT — direct provider call in hookimpl body
@hookimpl
def startup_warmup(logger) -> None:
    dispatcher = get_event_dispatcher()
    dispatcher.register_handler(REQUEST_APPROVED, on_access_request_approved)
```

**Constraints:**

- S3.1: Hookimpls may call `@lru_cache` provider functions from
  `infrastructure.services.providers` to obtain process-scoped singletons.
- S3.2: If the hookspec signature already provides a dependency as an argument (e.g.,
  `register_slack_commands(provider)`), the hookimpl must use the argument — not
  re-obtain it via provider call.
- S3.3: Hookimpls must not call provider functions at module level (import-time side
  effects). Provider calls must be inside the function body.
- S3.4: Test substitution uses `get_x.cache_clear()` in test teardown combined with
  monkeypatch or mock at the provider function level.

**Rationale:** Pluggy has no dependency injection mechanism. Its design philosophy places
the burden on the host to decide which objects hookimpls receive via arguments (pluggy
documentation: "puts the burden on the designer of the host program to think carefully
about which objects are really needed"). For process-scoped singletons not provided by
the hookspec, direct provider calls are the conventional pattern used in pytest, tox,
and other mature pluggy-based projects.

### Standard 4: Background Jobs — Direct Provider Calls Canonical

Background job functions (registered via `register_background_job` hookspec) follow the
same rules as hookimpls.

**Constraints:**

- S4.1: Same rules as Standard 3 (S3.1–S3.4) apply.
- S4.2: Background jobs must not depend on request-scoped state. All services obtained
  must be process-scoped singletons.

### Standard 5: Module-Level Provider Calls — Universally Prohibited

No module in `app/packages/` or `app/api/` may call a provider function at module level
(outside a function body).

```python
# PROHIBITED — module-level provider call (import-time side effect)
from infrastructure.services.providers import get_event_dispatcher
dispatcher = get_event_dispatcher()  # ❌ executes at import time

# CORRECT — provider call inside function body
def startup_warmup(logger) -> None:
    dispatcher = get_event_dispatcher()  # ✅ executes at call time
```

**Constraints:**

- S5.1: Module-level assignments from provider functions are prohibited in all contexts.
- S5.2: Module-level constants derived from settings (`SOME_VALUE = get_settings().key`)
  are prohibited. Use the settings provider inside the function that needs the value.

**Rationale:** Module-level provider calls execute at import time, before the application
lifecycle has initialized services. This violates ADR-0046 (startup phases) and causes
unpredictable initialization ordering.

### Standard 6: DI Alias Declarations — Colocated, Not Centralized

`Annotated[Protocol, Depends(get_x)]` type aliases are declared by the consumer, not
in a centralized file.

**Constraints:**

- S6.1: DI aliases are owned by the consumer, not by infrastructure. A feature package
  that needs `EventDispatcherDep` declares it in its own `interactions/http.py` or in a
  package-local `dependencies.py`.
- S6.2: There is no global registry of all DI aliases.
- S6.3: The centralized `infrastructure/services/dependencies.py` is deprecated and
  scheduled for removal per ADR-0085 S3.
- S6.4: Duplicate alias declarations across files are acceptable and intentional — each
  file is self-describing.

### Standard 7: Anti-Pattern Identification

These patterns are prohibited regardless of context:

| Anti-Pattern | Description | Why Prohibited |
|---|---|---|
| **Global service variable** | `SERVICE = get_x()` at module level | Import-time side effect; bypasses startup ordering |
| **Hidden route dependency** | `get_x()` inside handler body when `Depends()` is available | Invisible to OpenAPI; untestable via `dependency_overrides` |
| **Lambda wrapper in Depends** | `Depends(lambda: get_x())` | Breaks `dependency_overrides` lookup by identity |
| **Cross-context pattern leak** | Using `cache_clear()` in route handler tests | Route tests should use `dependency_overrides`; `cache_clear()` is for hookimpl/job tests only |
| **Settings at module level** | `config = get_settings()` outside function | Import-time execution; masks dependency; `@lru_cache` not yet warm |

## Alternatives Considered

1. **Mandatory `Depends()` everywhere (including hookimpls and jobs):**
   Technically impossible. Pluggy and background jobs execute outside FastAPI request
   context. Would require building a custom DI container.
   Why not chosen: the asymmetry is structural and cannot be papered over.

2. **Direct provider calls everywhere (no `Depends()` in route handlers):**
   Abandons FastAPI's primary value proposition. Hides dependencies. Requires
   `cache_clear()` in every test. Violates FastAPI documented best practices.
   Why not chosen: when a DI framework is available, bypassing it is an antipattern.

3. **Centralized `dependencies.py` retained:**
   Grows with every new service. Forces consumers to import from a file that loads all
   infrastructure. Creates Service Locator symptom.
   Why not chosen: consumer-owned aliases eliminate speculative declarations.

4. **Pass all services to hookspecs as arguments:**
   Hookspec signatures become unwieldy (10+ arguments). Breaks pluggy's opt-in argument
   model. No mature pluggy project (pytest, tox, kedro) uses this pattern.
   Why not chosen: pluggy's design intentionally avoids universal injection.

## Consequences

**Positive:**

- Single table-driven standard eliminates ambiguity across all call contexts.
- HTTP route handlers gain explicit, testable dependency signatures.
- Test isolation improves: `dependency_overrides` for routes, `cache_clear()` for
  hookimpls/jobs — each context uses its natural mechanism.
- The asymmetry is named and rationalized as first-class architecture.
- New developers have one table to consult, not four ADRs to reconcile.

**Negative:**

- Two mental models coexist (Depends for HTTP, direct call for hookimpl/jobs).
  Mitigated by the structural explanation and the single-question test.
- Migration effort: existing route handlers must be refactored to use `Depends()`.
  Incremental as handlers are touched.
- Consumer-owned aliases mean the same declaration may appear in multiple files.
  Intentional — each file is self-describing.

**Neutral:**

- `@lru_cache` provider pattern unchanged. This ADR governs how providers are *called*,
  not how they are *defined*.
- Protocol types at the injection surface (ADR-0048 B7) apply regardless of mechanism.

## Compliance and Boundaries

**This ADR governs:**

- How feature packages and route handlers call infrastructure service providers.
- Which mechanism is canonical for each call context.
- Where DI type aliases are declared.
- The anti-pattern catalog.

**This ADR does not govern:**

- What `infrastructure.services` exports (ADR-0085).
- How provider functions are defined or composed (ADR-0056).
- Internal feature package structure (ADR-0087).
- Transport adapter patterns (ADR-0088).
- Protocol definitions or service contracts (ADR-0077).

**Enforcement:**

- Lint rules should flag direct `get_x()` calls inside HTTP route handler bodies.
- Lint rules should flag module-level `get_x()` calls in `app/packages/` and `app/api/`.
- Code review must verify the context resolution matrix compliance.

## Best-Practice Revalidation

| Source | Claim Validated | Alignment |
|--------|----------------|-----------|
| FastAPI "Dependencies" tutorial | `Depends()` is the framework's DI mechanism for route handlers | ✅ S2 mandates its use |
| FastAPI "Testing Dependencies" docs | `dependency_overrides` is the canonical test substitution | ✅ S2.3 adopts this |
| FastAPI "Share Annotated dependencies" | `Annotated` type alias pattern recommended for reuse | ✅ S6 permits module-level aliases |
| Pluggy documentation | Host controls what hookimpls receive; hookimpls may obtain other deps internally | ✅ S3 ratifies direct calls |
| pytest hookimpl patterns | Hookimpls access services internally, not via universal injection | ✅ S3 consistent with pytest |
| Mark Seemann (2011) | Service Locator = global query; Composition Root = single assembly | ✅ S6 eliminates the locator |
| Cosmic Python Ch. 13 | Bootstrap/composition patterns compose the graph once | ✅ `providers.py` remains Composition Root |

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: Draft record. Full rewrite from deprecated draft. Pending author review.
- Follow-up actions:
  - Author review of new scope.
  - Challenge review after author approval.

## Source References

| # | Source | URL | Key Insight |
|---|--------|-----|-------------|
| 1 | FastAPI, "Dependencies" | <https://fastapi.tiangolo.com/tutorial/dependencies/> | `Depends()` mechanism, per-request resolution, `use_cache` |
| 2 | FastAPI, "Testing Dependencies with Overrides" | <https://fastapi.tiangolo.com/advanced/testing-dependencies/> | `dependency_overrides` for per-test substitution |
| 3 | FastAPI, "Share Annotated dependencies" | <https://fastapi.tiangolo.com/tutorial/dependencies/#share-annotated-dependencies> | `Annotated` type alias pattern |
| 4 | Pluggy Documentation | <https://pluggy.readthedocs.io/en/stable/> | Hookimpl design: opt-in args, host controls injection scope |
| 5 | Mark Seemann, *Dependency Injection in .NET* (2011) | — (book, ISBN 978-1935182504) | Composition Root vs Service Locator distinction |
| 6 | Percival & Gregory, *Architecture Patterns with Python* Ch. 13 | <https://www.cosmicpython.com/book/chapter_13_dependency_injection.html> | Bootstrap pattern for Python DI composition |
| 7 | pytest source (hookimpl patterns) | <https://github.com/pytest-dev/pytest> | Mature pluggy usage: hookimpls obtain services internally |

## Implementation Guidance

1. **Immediate:** Apply the context resolution matrix to all new code. No grandfather
   clause for new files.
2. **Route handler migration:** Refactor existing handlers to use `Depends()` for
   infrastructure services as files are touched. Prioritize handlers under active
   development.
3. **Anti-pattern sweep:** Run a one-time audit for module-level provider calls
   (Standard 5 violations). These are the highest-risk violations.

## Change Log

- 2026-05-06: Full rewrite from deprecated draft. Scope refocused around a single
  context resolution matrix (Standard 1) that unifies the previously fragmented guidance.
  Added anti-pattern catalog (Standard 7) and module-level prohibition (Standard 5).
  Previous draft spread context-specific rules across separate standards without a
  unifying table; new version provides the single-question test identified as missing
  in the 0085-0088 conflict analysis.
