---
adr_id: ADR-0063
title: "API Composition and Validation Standard"
status: Accepted
decision_type: Standard
tier: Tier-2
primary_domain: Transport and API
secondary_domains:
  - Package and Plugin Architecture
  - Dependency and Composition
owners:
  - SRE Team
date_created: 2026-04-29
last_updated: 2026-04-29
last_reviewed: 2026-04-29
next_review_due: 2026-08-27
constrained_by:
  - ADR-0044
  - ADR-0045
  - ADR-0048
  - ADR-0050
  - ADR-0053
  - ADR-0054
  - ADR-0055
  - ADR-0056
  - ADR-0059
  - ADR-0065
  - ADR-0076
  - ADR-0077
impacts:
  - ADR-0060
supersedes:
  - ADR-0033
  - ADR-0034
  - ADR-0039
  - ADR-0041
superseded_by: []
review_state: current
related_records:
  - ADR-0046
  - ADR-0049
  - ADR-0058
  - ADR-0078
related_packages:
  - app/api
  - app/infrastructure/http
  - app/packages/access/sync/interactions
  - app/packages/access/request/interactions
  - app/packages/access/catalog/interactions
  - app/packages/geolocate
  - app/server
---

# API Composition and Validation Standard

## Context

- **Problem statement:** Four legacy ADRs (ADR-0033, ADR-0034, ADR-0039, ADR-0041) defined overlapping and inconsistent guidance for API route organization, request validation, middleware ordering, and OpenAPI documentation at Tier-4 (Feature Decision). All four are marked `review_state: stale`. The codebase has no authoritative standard governing route composition patterns, validation conventions, middleware ordering, or the boundary between shared HTTP types and feature-owned types. Meanwhile, `app/api/` is a legacy wiring layer — a mix of static system routes (health, landing), legacy feature routes (webhooks, geolocate), a versioned sub-router (`app/api/v1/`), and an empty `dependencies/` directory. Feature packages already own their routes via `register_routes` hookimpl, making `app/api/` a shrinking transitional artifact rather than a growing architectural component.

- **Business/operational drivers:**
  - Establish a single Tier-2 standard governing route composition, validation, middleware ordering, and OpenAPI documentation — consolidating the scattered guidance from four stale Tier-4 records.
  - Classify `app/api/` as a legacy wiring layer — not a governed package — that will shrink as remaining legacy routes migrate to feature packages.
  - Place shared HTTP types (error responses, pagination envelopes) in `infrastructure/http/schemas.py`, consistent with the infrastructure service model (ADR-0048, ADR-0056). This unblocks ADR-0060's error schema placement without creating new package-level ownership in `app/api/`.
  - Codify the route-as-thin-adapter principle: route handlers orchestrate service invocations and format responses, but must not embed business logic, direct third-party SDK calls, or database operations.
  - Align middleware ordering with existing request-context binding (ADR-0054) and port exposure (ADR-0053) requirements.

- **Constraints:**
  - Route handlers consume infrastructure services through `Annotated[Protocol, Depends(provider)]` aliases from `dependencies.py`, never through direct imports (ADR-0048 B2, ADR-0056 Standard 4).
  - Feature routes register via `register_routes` hookimpl (ADR-0059 Standard 3); they are not placed in `app/api/`.
  - Request validation uses Pydantic `BaseModel` at the I/O boundary (ADR-0065 P4).
  - Shared HTTP schemas are value types — permitted for cross-boundary import (ADR-0076 Standard 1). They belong in `infrastructure/http/schemas.py`, not in a feature package or `app/api/`.
  - Middleware must account for request-context binding (ADR-0054) and port exposure (ADR-0053).
  - Settings follow the dissolution model (ADR-0055); no monolithic Settings object in route handlers.

- **Non-goals:**
  - This record does not define the `OperationResult` type or its HTTP mapping — that is governed by ADR-0050 and ADR-0060.
  - This record does not define platform-specific interaction patterns (Slack, Teams) — that is governed by ADR-0059.
  - This record does not define security/authentication middleware implementation — that belongs in ADR-0064 (planned).
  - This record does not prescribe specific rate-limiting libraries or algorithms — that belongs in ADR-0064.
  - This record does not define background execution patterns for async request processing — that is governed by ADR-0058.
  - This record does not govern the internal structure of `app/api/` as a package — `app/api/` is legacy wiring, not a first-class package. Its internal layout will shrink as legacy routes migrate to feature packages.

## Decision

- **Chosen approach:** Consolidate ADR-0033, ADR-0034, ADR-0039, and ADR-0041 into a single Tier-2 standard defining six standards for API composition, route organization, validation patterns, middleware ordering, OpenAPI documentation, and shared HTTP type governance. Classify `app/api/` as a legacy wiring layer — not a governed package — and place shared HTTP types in `infrastructure/http/schemas.py`.

- **Why this approach:** The four legacy ADRs addressed facets of the same concern — how the API layer is structured and how HTTP requests flow through it. Consolidation eliminates authority fragmentation and promotes all guidance to the correct Tier-2 level. Treating `app/api/` as legacy wiring (rather than constituting it as a governed package) aligns with the established pattern where feature packages own their routes via hookimpl, keeps `app/api/` on a path to shrink, and avoids creating a second schema ownership location that competes with `infrastructure/`. This mirrors the approach validated by FastAPI's full-stack template (42.9k+ stars, by tiangolo), where `api/` is pure wiring with zero type ownership.

### Standard 1: Shared HTTP Types and Legacy Wiring Boundaries

Shared HTTP types (error response schemas, pagination envelopes, common request/response wrappers) used across multiple API consumers live in `infrastructure/http/schemas.py`. These are Pydantic `BaseModel` value types at the I/O boundary — they do not carry behavior and are permitted for cross-boundary import (ADR-0076 Standard 1).

`app/api/` is a **legacy wiring layer**, not a governed package. It assembles static/legacy routes into the root router. Its contents will shrink as remaining legacy routes migrate to feature packages via hookimpl.

**Canonical shared HTTP type location:**

```
app/infrastructure/http/
├── __init__.py
└── schemas.py           # ErrorResponse, PaginatedResponse, and other shared HTTP types
```

**Legacy wiring layer (shrinking — not a governed package):**

```
app/api/
├── __init__.py          # Package marker
├── router.py            # Root router assembly — system routes, legacy bridges
├── routes/              # Cross-cutting system routes only (health, landing)
│   ├── system.py
│   └── landing.py       # Legacy landing page (pre-Backstage)
└── v1/                  # Legacy versioned namespace — migration targets
    ├── router.py
    └── routes/
        ├── webhooks.py  # Legacy — migrate to feature package
        └── geolocate.py # Legacy — duplicate of hookimpl-registered route
```

Shared dependency factories (auth, request context) are governed by ADR-0056 Standard 4 and live in `infrastructure/services/dependencies.py` — not in `app/api/`.

**Rules:**

- S1: `infrastructure/http/schemas.py` is the canonical location for shared Pydantic models used across multiple API consumers. Error response schemas (ADR-0060), pagination models, and common request/response envelopes belong here. Feature-specific schemas remain in `packages/<feature>/schemas.py`.
- S2: Shared API-layer dependency factories (authentication, request-context extraction, rate-limiting) are defined in `infrastructure/services/dependencies.py` and exported through `infrastructure/services/__init__.py` per ADR-0056 Standard 4 (DI alias ceremony). Feature routes import these aliases — they do not import underlying implementations. Feature-specific dependencies remain in feature packages (e.g., `packages/<feature>/providers.py`).
- S3: `app/api/routes/` contains only cross-cutting system endpoints (health, version, readiness). No feature routes are placed here.
- S4: `app/api/v1/routes/` is a **legacy namespace**. Existing routes (`webhooks.py`, `geolocate.py`) remain here temporarily. New feature routes must register via `register_routes` hookimpl (ADR-0059 Standard 3), not by adding files to `app/api/v1/routes/`.
- S5: The root `app/api/router.py` assembles system and legacy sub-routers. Feature routers are included by the hookimpl mechanism during lifespan startup — they are not statically imported in `router.py`.
- S6: `app/api/` must not contain a `schemas/` directory. Shared HTTP types belong in `infrastructure/http/schemas.py`. This prevents `app/api/` from accreting ownership that anchors it as a permanent architectural component.
- S7: `app/api/dependencies/` is dead code and should be removed. All shared dependencies live in `infrastructure/services/dependencies.py` per ADR-0056.

### Standard 2: Route-as-Thin-Adapter Principle

Route handlers are thin adapters that translate HTTP requests into service invocations and format responses. They must not embed business logic.

**Permitted in route handlers:**

- Parse and validate request parameters (via Pydantic models and FastAPI parameter binding).
- Invoke service-layer functions or methods via injected dependencies.
- Map `OperationResult` to HTTP responses per ADR-0060 Standard 2.
- Return structured response models (Pydantic `BaseModel` for success, `ErrorResponse` for errors).
- Set response headers (e.g., `Retry-After` for 503 responses).

**Prohibited in route handlers:**

- Direct third-party SDK calls (Slack SDK, AWS SDK, Google API, etc.).
- Direct database or storage operations (DynamoDB, S3, etc.).
- Business logic branching based on domain state (e.g., incident triage, email-to-user mapping).
- Constructing platform-specific response formats (Block Kit, Adaptive Cards) — use presenters (ADR-0059 Standard 2).

**Current violations (2026-04-29):**

| Location | Violation | Severity |
|----------|-----------|----------|
| `app/api/v1/routes/webhooks.py` | Embeds webhook validation, DynamoDB calls via `modules.slack.webhooks`, email-to-Slack user mapping, incident button attachment construction. Route handler is ~165 lines with deep business logic. | Critical |
| `app/api/v1/routes/geolocate.py` | Minimal violation — calls `geolocate_ip` service function directly. Structurally acceptable but uses bare `HTTPException`. | Low |

### Standard 3: Request Validation Patterns

Request validation uses Pydantic V2 at the I/O boundary (ADR-0045 Principle 4).

**Rules:**

- V1: Use `BaseModel` subclasses for request body schemas. All fields must include `description` in `Field()` for OpenAPI documentation.
- V2: Use `@field_validator(mode='after')` for single-field validation that requires custom logic beyond type constraints. Use `Field(gt=0, max_length=255, ...)` for declarative constraints that Pydantic handles natively.
- V3: Use `@model_validator(mode='after')` for multi-field validation (cross-field dependencies). The validator must return `self`. Raise `ValueError` with a user-facing message on failure.
- V4: Use discriminated unions with `Annotated[Union[TypeA, TypeB], Field(discriminator="field_name")]` for polymorphic request bodies. Branch on resolved type using `isinstance` in the route handler — do not pass the union into the service layer.
- V5: Path and query parameter validation uses FastAPI's `Path()` and `Query()` with the same constraint parameters as `Field()`. Include `description` for all parameters.
- V6: Response models use `BaseModel` subclasses with `response_model` parameter or return type annotation. Internal canonical entities (`@dataclass(frozen=True)`) must not be returned directly from route handlers — convert to Pydantic response models at the handler level.

### Standard 4: Middleware Ordering and Registration

Middleware forms a request/response stack. The canonical ordering from outermost (first to process request, last to process response) to innermost is:

| Order | Middleware | Purpose | Registration |
|-------|-----------|---------|--------------|
| 1 (outermost) | CORS | Cross-origin request handling | `app.add_middleware(CORSMiddleware, ...)` |
| 2 | Rate Limiting | Request throttling | Framework-specific (e.g., `SlowAPI`) |
| 3 | Request Context | Bind `request_id`, correlation ID, structured logging context | `@app.middleware("http")` or ASGI |
| 4 | Error Handling | Catch unhandled exceptions, format 500 responses | `@app.exception_handler(Exception)` |
| 5 (innermost) | Authentication | Validate JWT/tokens, resolve `current_user` | FastAPI `Depends()` (not middleware) |

**Current-state note (2026-04-29):** Rows 3 (request context) and 4 (error handling) describe the target architecture. The current codebase relies on FastAPI's built-in exception handler for unhandled 500 responses and does not yet have dedicated request-context binding middleware. Structured error response formatting (row 4) is a Phase 2 migration step per ADR-0060.

**Rules:**

- M1: Middleware is registered in `app/server/server.py` during app construction. The ordering above is normative — CORS must be outermost to handle preflight requests before any other processing.
- M2: Prefer pure ASGI middleware over `BaseHTTPMiddleware` for high-throughput paths. `BaseHTTPMiddleware` buffers the full response body — avoid for streaming endpoints or large payloads.
- M3: Authentication is implemented as a FastAPI dependency (`Depends()`), not as middleware. This enables per-route opt-in/opt-out and provides correct OpenAPI security scheme documentation.
- M4: Request-context middleware must bind `request_id` and structured logging context before route execution (ADR-0054). This middleware is order-critical — it must execute before error handling so that error responses include the `request_id`.
- M5: Custom exception handlers (`@app.exception_handler(ExceptionType)`) should be registered in `app/server/server.py` when implemented. They will catch exceptions that escape route handlers and format them using the canonical error response schema (ADR-0060 Standard 1). These complement — not replace — route-level `OperationResult` mapping. Until implemented, FastAPI's built-in handler provides baseline 500 responses.

### Standard 5: OpenAPI Documentation Requirements

All API routes must provide complete OpenAPI metadata for generated clients and interactive documentation.

**Rules:**

- O1: Every `APIRouter` instance must declare exactly one `tags` entry. The tag name must be title-cased and match the feature or concern name (e.g., `tags=["Access Sync"]`, `tags=["System"]`).
- O2: Every route handler must declare `summary` (imperative verb phrase, ≤8 words) and `description` (1-2 sentences describing behavior and response semantics).
- O3: Every route handler must declare `response_model` (success response) and `status_code` (success status code). For endpoints returning no body, use `status_code=204` with no `response_model`.
- O4: Every route handler must declare `responses` parameter documenting all non-2xx status codes it can return, using the canonical error response schema (ADR-0060 Standard 1) as the model. Error response descriptions must be concise and client-actionable.
- O5: Internal infrastructure endpoints (health probes, readiness checks, webhook receivers) should use `include_in_schema=False` to exclude from public OpenAPI documentation.
- O6: Mark deprecated endpoints with `deprecated=True` in the route decorator. Deprecated endpoints must include a deprecation notice in `description` indicating the replacement endpoint or migration path.
- O7: Function names serve as `operationId` in OpenAPI — keep them descriptive, unique across the application, and stable (renaming is a breaking change for generated clients).
- O8: All Pydantic schema fields used in request/response models must include `description` in `Field()` for OpenAPI documentation.

### Standard 6: Feature Route Registration and Composition

Feature packages register their HTTP routes via the `register_routes` hookimpl (ADR-0059 Standard 3). This standard governs how those routes compose into the application.

**Rules:**

- R1: Feature routes register via `register_routes(app: FastAPI)` hookimpl. The hookimpl calls `app.include_router(router)` with the feature's `APIRouter`. The feature owns the router's `prefix`, `tags`, and `dependencies`.
- R2: Feature routers must include a versioned prefix (e.g., `prefix="/api/v1"`). The prefix may be applied at inclusion time via `app.include_router(router, prefix="/api/v1")` or set on the feature's `APIRouter`. The current codebase convention is inclusion-time prefix — 3 of 4 feature packages use `app.include_router(router, prefix="/api/v1")`. Feature-specific path segments (e.g., `/access`) are set on the feature's `APIRouter` itself.
- R3: Feature route handlers consume infrastructure services through `Annotated[Protocol, Depends(provider)]` aliases. Feature-specific dependencies are defined in the feature package (e.g., `packages/<feature>/providers.py`), not in `app/api/dependencies/`.
- R4: Feature routes must not import from `app/api/v1/routes/` or other feature route modules. Route modules are leaf nodes — they consume services and produce responses.
- R5: Cross-cutting dependencies shared across features (authentication, request context) are imported from `infrastructure/services/dependencies.py` (ADR-0056 Standard 4). Feature routes import these aliases, not the underlying implementations.

## Alternatives Considered

1. **Maintain four separate ADRs at Tier-4:**
   - Pros: Existing records already cover the space.
   - Cons: All four are stale; Tier-4 is too low for a standard governing route composition patterns that all features must follow. Overlapping authority between ADR-0033 (route organization) and ADR-0041 (OpenAPI) on per-route metadata.
   - Why not chosen: Consolidation eliminates ambiguity and promotes to correct Tier-2 authority level.

2. **Promote individual ADRs to Tier-2 without consolidation:**
   - Pros: Preserves granular records.
   - Cons: Four separate records for tightly coupled concerns (route structure affects validation affects middleware affects documentation) creates navigation burden and cross-reference overhead.
   - Why not chosen: These concerns are facets of one system — the API composition layer.

3. **Constitute `app/api/` as a governed package with `app/api/schemas/` for shared types:**
   - Pros: Gives shared HTTP types a visible, intuitive location adjacent to route code. Simple migration path.
   - Cons: Anchors `app/api/` as a permanent architectural component by giving it schema ownership. Creates a second type-ownership location that competes with `infrastructure/`. Contradicts the direction where feature packages own their routes and `app/api/` shrinks over time. No authoritative FastAPI reference uses `api/schemas/` — the full-stack template (tiangolo, 42.9k+ stars) places all shared models at the application root, and Cosmic Python / Clean Architecture / Hexagonal Architecture all place shared types in infrastructure or domain layers, never in the transport/wiring layer.
   - Why not chosen: Growing `app/api/` with new directories reverses the architectural direction established by hookimpl-based feature route ownership.

4. **Let `app/api/` remain ungoverned:**
   - Pros: No new ADR needed.
   - Cons: Blocks ADR-0060 (error schema placement has no governed home). Allows continued ad-hoc additions to `app/api/` without structural review. Webhooks anti-pattern persists without a standard to cite.
   - Why not chosen: Route composition patterns need explicit governance regardless of `app/api/`'s package status.

5. **Merge API composition into ADR-0059:**
   - Pros: Reduces ADR count.
   - Cons: ADR-0059 governs feature-side interaction boundaries and multi-platform registration — a different concern from API-layer composition, middleware, and OpenAPI documentation. Merging would create an oversized record with mixed scopes.
   - Why not chosen: Separation of concerns between feature interaction patterns (ADR-0059) and API-layer composition (this record) aligns with ADR-0051 single-decision-per-record rule.

## Consequences

- **Positive impacts:**
  - `app/api/` is explicitly classified as legacy wiring — no new schemas, dependencies, or structural additions permitted. This prevents accretion that would anchor it as a permanent component.
  - `infrastructure/http/schemas.py` provides a governed, infrastructure-aligned location for shared HTTP types, unblocking ADR-0060's error schema placement without creating competing ownership.
  - Feature packages retain full ownership of their routes, schemas, and dependencies via hookimpl — reinforcing the established architectural direction.
  - The route-as-thin-adapter principle provides a concrete standard to cite when identifying and migrating anti-pattern routes (webhooks.py).
  - Middleware ordering is codified, preventing accidental misordering that breaks request-context propagation or CORS handling.
  - OpenAPI documentation requirements ensure API consumers receive complete, consistent documentation.

- **Tradeoffs accepted:**
  - Legacy routes in `app/api/v1/routes/` remain temporarily. Migration to feature packages is a separate effort governed by individual feature migration decisions.
  - The `landing.py` route (bilingual HTML landing page) remains in `app/api/routes/` as a cross-cutting system concern. This is a legacy artifact that will be retired when Backstage fully replaces the landing page.
  - Middleware ordering is prescriptive rather than flexible. This is intentional — incorrect ordering causes subtle bugs (missing request_id in error responses, CORS failures on preflight requests).
  - Placing shared HTTP types in `infrastructure/http/schemas.py` rather than adjacent to route code introduces a small navigation cost. This is acceptable because shared types are imported infrequently and the location aligns with the infrastructure service model.

- **Risks introduced:**
  - New features might be unclear on whether a schema belongs in `infrastructure/http/schemas.py` (shared across consumers) vs. `packages/<feature>/schemas.py` (feature-specific). Mitigation: Standard 1 Rule S1 provides clear criteria — only types used by multiple API consumers belong in `infrastructure/http/schemas.py`.
  - The route-as-thin-adapter principle requires refactoring `webhooks.py` (~165 lines of embedded business logic). Mitigation: Migration is incremental and tracked by the webhooks feature rearchitecting assessment.
  - `infrastructure/http/` is a new infrastructure sub-package. Mitigation: It follows the established `infrastructure/<concern>/` pattern (e.g., `infrastructure/audit/`, `infrastructure/clients/`) and contains only value types, not services.

- **Mitigations:**
  - Feature route registration via hookimpl (ADR-0059) is already implemented in 4 packages (`access/sync`, `access/request`, `access/catalog`, `geolocate`), providing validated reference implementations.
  - The middleware ordering matches the current `app/server/server.py` implementation (CORS → rate limiting → router), minimizing migration effort.

## Compliance and Boundaries

- **Package/infrastructure boundary impact:** `app/api/` is classified as a legacy wiring layer — not infrastructure, not a feature package, not a governed package. It will shrink as legacy routes migrate to feature packages. Shared HTTP types live in `infrastructure/http/schemas.py` as value types (ADR-0076 Standard 1: shared value types permitted for cross-boundary import). Feature routes register via hookimpl from their own packages; they import shared HTTP types from `infrastructure/http/schemas.py` but do not import route implementations from `app/api/`.
- **Type boundary impact:** Request/response models use Pydantic `BaseModel` at the HTTP boundary (ADR-0045 P4). Internal entities remain `@dataclass(frozen=True)`. Conversion happens at the route handler level — the service layer never sees Pydantic models, and route handlers never return raw dataclasses.
- **Startup/plugin registration impact:** Feature routes register during the `register_routes` hookspec phase of lifespan startup (ADR-0059 Standard 3, Standard 5). Cross-cutting routes in `app/api/routes/` are statically included in `router.py` — no hookspec required for system endpoints.
- **Settings partitioning impact:** Route handlers receive settings through narrow-slice dependency injection (ADR-0055, ADR-0056). No route handler should access the root `Settings` object. Middleware configuration (CORS origins, rate-limit thresholds) follows the same settings dissolution model.
- **DI alias ceremony impact:** Route handlers consume infrastructure through `Annotated[Protocol, Depends(provider)]` aliases from `infrastructure/services/dependencies.py` (ADR-0056 Standard 4). Feature-specific providers remain in feature packages. Shared dependencies (e.g., `get_current_user`) are exported through `infrastructure/services/__init__.py`.
- **Service contract impact:** Route handlers consume Category A services via Protocol-typed dependencies (ADR-0077). The route layer is a consumer, not a provider — it does not define new service contracts.

## Codebase Audit (2026-04-29)

### Current Violations

| Location | Violation | Standard | Severity |
|----------|-----------|----------|----------|
| `app/api/v1/routes/webhooks.py` | Embeds business logic (webhook validation, DynamoDB calls, email-to-Slack mapping, incident button construction). 165+ lines violating route-as-thin-adapter. | Standard 2 | Critical |
| `app/api/v1/routes/webhooks.py` | No `summary`, `description`, `response_model`, or `responses` parameter. No OpenAPI documentation. | Standard 5 (O2-O4) | High |
| `app/api/v1/routes/geolocate.py` | Uses bare `HTTPException(404)` with detail string; no error response model. | Standard 5 (O4), ADR-0060 | Medium |
| `app/api/v1/routes/geolocate.py` | Legacy route in `app/api/v1/routes/` — `geolocate` package exists and has hookimpl registration but route still lives in legacy location. | Standard 1 (S4) | Low |
| `app/api/dependencies/` | Empty directory — contains only `__pycache__`. Dead code per Standard 1 Rule S7 — shared dependencies live in `infrastructure/services/dependencies.py` per ADR-0056. Should be removed. | Standard 1 (S7) | Low |
| `app/api/router.py` | Includes `webhooks_router` without tags or metadata. `log_legacy_calls` dependency is correctly applied to legacy router but has no centralized request-context binding. | Standard 5 (O1) | Low |
| `app/server/server.py` | `settings = get_settings()` called at module level for CORS configuration — should use narrower settings slice. | Standard 4 (M1), ADR-0055 | Low |

### Compliant Patterns (Reference)

| Location | Pattern | Notes |
|----------|---------|-------|
| `app/packages/access/sync/interactions/http.py` | Feature route registered via hookimpl with `APIRouter(prefix="/api/v1/access/sync", tags=["Access Sync"])`. Route handler delegates to service layer. | Standard 2 and Standard 6 compliant. |
| `app/packages/access/sync/__init__.py` | `register_routes` hookimpl calls `app.include_router(router)`. | Standard 6 (R1) compliant. |
| `app/packages/access/request/__init__.py` | `register_routes` hookimpl for access request feature. | Standard 6 (R1) compliant. |
| `app/packages/access/catalog/__init__.py` | `register_routes` hookimpl for access catalog feature. | Standard 6 (R1) compliant. |
| `app/packages/geolocate/__init__.py` | `register_routes` hookimpl for geolocate feature. | Standard 6 (R1) compliant (but legacy route still exists in `app/api/v1/`). |
| `app/api/routes/system.py` | Health and version endpoints — cross-cutting system routes in correct location. | Standard 1 (S3) compliant. |

### Migration Path

1. **Phase 1 (immediate):** Create `infrastructure/http/__init__.py` and `infrastructure/http/schemas.py` with canonical `ErrorResponse` model (ADR-0060 Standard 1) and any other shared HTTP types.
2. **Phase 2 (incremental):** Add OpenAPI metadata (`summary`, `description`, `response_model`, `responses`) to all existing routes. New routes adopt all standards from day one.
3. **Phase 3 (legacy migration):** Extract `webhooks.py` business logic into a webhooks service module. Refactor route handler to thin adapter. Move `geolocate.py` route to feature package (remove legacy copy from `app/api/v1/routes/`).
4. **Phase 4 (cleanup):** Remove `app/api/dependencies/` (empty dead directory). As legacy routes migrate, `app/api/v1/routes/` empties and can eventually be removed.

## Best-Practice Revalidation

- **Revalidation date:** 2026-04-29
- **Sources rechecked:**
  - FastAPI Official Documentation — Bigger Applications (<https://fastapi.tiangolo.com/tutorial/bigger-applications/>) — APIRouter composition, prefix/tags/dependencies patterns.
  - FastAPI Official Documentation — Dependencies (<https://fastapi.tiangolo.com/tutorial/dependencies/>) — `Annotated[..., Depends()]` alias pattern, hierarchical resolution.
  - FastAPI Official Documentation — Additional Responses (<https://fastapi.tiangolo.com/advanced/additional-responses/>) — `responses` parameter for OpenAPI error documentation.
  - FastAPI Official Documentation — Middleware (<https://fastapi.tiangolo.com/tutorial/middleware/>) — middleware stack ordering, execution model.
  - FastAPI Full-Stack Template (<https://github.com/fastapi/full-stack-fastapi-template>) — 42.9k+ stars, by tiangolo. `api/` is pure wiring (router assembly only); all shared models live at `app/models.py`, not in `api/`. Validates Option C: transport wiring layer owns no types.
  - Cosmic Python — Architecture Patterns with Python (Percival & Gregory) — shared types belong in the domain or infrastructure layer, not the transport/entrypoint layer.
  - Clean Architecture (Robert C. Martin) — the interface adapter layer (controllers/routes) is a thin translation layer that imports from inner layers; it does not own shared types.
  - Hexagonal Architecture (Alistair Cockburn) — adapters are thin translators between the application and external actors; shared port types live in the application or infrastructure layer.
  - Pydantic V2 Documentation — Validators (<https://docs.pydantic.dev/latest/concepts/validators/>) — `@field_validator`, `@model_validator` patterns.
  - Starlette Middleware Documentation (<https://www.starlette.io/middleware/>) — ASGI vs `BaseHTTPMiddleware` tradeoffs.
  - FastAPI Official Documentation — Metadata and Docs URLs (<https://fastapi.tiangolo.com/tutorial/metadata/>) — tag metadata, OpenAPI configuration.
- **Alignment summary:**
  - Standard 1 aligns with FastAPI full-stack template pattern (wiring layer owns no types) and with Cosmic Python / Clean Architecture / Hexagonal Architecture (shared types in infrastructure/domain, not transport).
  - Standard 3 aligns with Pydantic V2 validator patterns (`@field_validator`, `@model_validator`, discriminated unions).
  - Standard 4 aligns with Starlette's middleware execution model (stack ordering, outermost-first for requests). Authentication as dependency (not middleware) aligns with FastAPI's security documentation.
  - Standard 5 aligns with FastAPI's OpenAPI documentation features (`tags`, `summary`, `description`, `responses`, `deprecated`).
  - Standard 6 aligns with FastAPI's `include_router` composition model with prefix/tags/dependencies.
- **Intentional deviations:** None. All standards align with framework best practices.

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: Consolidates ADR-0033, ADR-0034, ADR-0039, and ADR-0041 into one Tier-2 standard. Classifies `app/api/` as legacy wiring (not a governed package), places shared HTTP types in `infrastructure/http/schemas.py`, and codifies route composition patterns, validation conventions, middleware ordering, and OpenAPI documentation requirements.
- Follow-up actions:
  - Mark ADR-0033, ADR-0034, ADR-0039, ADR-0041 as superseded with `superseded_by: [ADR-0063]`.
  - Move superseded ADRs to `docs/decisions/adr/superseded/`.
  - Create `infrastructure/http/` sub-package with `__init__.py` and `schemas.py` (Phase 1 of migration path).
  - Unblock ADR-0060 error schema placement (now has governed location per Standard 1 Rule S1).
  - Migrate webhooks route to thin adapter pattern (Phase 3).
  - Remove empty `app/api/dependencies/` directory (dead code per Standard 1 Rule S7).

## Source References

1. Source title: FastAPI Official Documentation — Bigger Applications
   - URL: <https://fastapi.tiangolo.com/tutorial/bigger-applications/>
   - Publisher/maintainer: Sebastián Ramírez
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Canonical FastAPI project structure and APIRouter composition patterns; informs Standard 1 and Standard 6.
2. Source title: FastAPI Official Documentation — Dependencies
   - URL: <https://fastapi.tiangolo.com/tutorial/dependencies/>
   - Publisher/maintainer: Sebastián Ramírez
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Dependency injection patterns, `Annotated[..., Depends()]` alias convention, hierarchical dependency resolution; informs Standard 6 Rule R3.
3. Source title: FastAPI Official Documentation — Additional Responses in OpenAPI
   - URL: <https://fastapi.tiangolo.com/advanced/additional-responses/>
   - Publisher/maintainer: Sebastián Ramírez
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: `responses` parameter for documenting non-2xx status codes with Pydantic models; informs Standard 5 Rule O4.
4. Source title: FastAPI Official Documentation — Middleware
   - URL: <https://fastapi.tiangolo.com/tutorial/middleware/>
   - Publisher/maintainer: Sebastián Ramírez
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Middleware stack execution model and ordering semantics; informs Standard 4.
5. Source title: Pydantic V2 Documentation — Validators
   - URL: <https://docs.pydantic.dev/latest/concepts/validators/>
   - Publisher/maintainer: Pydantic Team
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Current `@field_validator` and `@model_validator` patterns; informs Standard 3.
6. Source title: Starlette Middleware Documentation
   - URL: <https://www.starlette.io/middleware/>
   - Publisher/maintainer: Encode
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: ASGI vs BaseHTTPMiddleware tradeoffs; informs Standard 4 Rule M2.
7. Source title: FastAPI Official Documentation — Metadata and Docs URLs
   - URL: <https://fastapi.tiangolo.com/tutorial/metadata/>
   - Publisher/maintainer: Sebastián Ramírez
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Tag metadata configuration and OpenAPI schema customization; informs Standard 5 Rule O1.
8. Source title: FastAPI Full-Stack Template
   - URL: <https://github.com/fastapi/full-stack-fastapi-template>
   - Publisher/maintainer: Sebastián Ramírez (tiangolo)
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Reference architecture (42.9k+ stars) where `api/` is pure router assembly with zero type ownership; all shared models at `app/models.py`. Validates Option C: transport wiring layer owns no types.
9. Source title: Architecture Patterns with Python (Cosmic Python)
   - URL: <https://www.cosmicpython.com/>
   - Publisher/maintainer: Harry Percival and Bob Gregory
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Shared types belong in the domain or infrastructure layer, not the transport/entrypoint layer. Informs Standard 1 placement decision.
10. Source title: Clean Architecture
    - URL: N/A (book)
    - Publisher/maintainer: Robert C. Martin
    - Accessed date (YYYY-MM-DD): 2026-04-29
    - Relevance summary: Interface adapter layer (controllers/routes) is a thin translation layer importing from inner layers; does not own shared types. Validates route-as-thin-adapter (Standard 2) and type placement (Standard 1).
11. Source title: Hexagonal Architecture (Ports and Adapters)
    - URL: <https://alistair.cockburn.us/hexagonal-architecture/>
    - Publisher/maintainer: Alistair Cockburn
    - Accessed date (YYYY-MM-DD): 2026-04-29
    - Relevance summary: Adapters are thin translators; shared port types live in the application or infrastructure layer. Validates infrastructure placement of shared HTTP types.
12. Source title: ADR-0033, ADR-0034, ADR-0039, ADR-0041 (Legacy)
    - URL: docs/decisions/adr/
    - Publisher/maintainer: SRE Team
    - Accessed date (YYYY-MM-DD): 2026-04-29
    - Relevance summary: Superseded legacy records whose content is consolidated and promoted here.
