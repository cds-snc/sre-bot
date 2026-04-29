---
adr_id: ADR-0060
title: "API Response and Error Mapping Standard"
status: Accepted
decision_type: Standard
tier: Tier-2
primary_domain: Transport and API
secondary_domains:
 - Dependency and Composition
 - Observability and Operations
owners:
 - SRE Team
date_created: 2026-04-29
last_updated: 2026-04-29
last_reviewed: 2026-04-29
next_review_due: 2026-08-27
constrained_by:
 - ADR-0044
 - ADR-0045
 - ADR-0050
 - ADR-0054
 - ADR-0056
 - ADR-0063
 - ADR-0077
impacts:
 - ADR-0062  # planned — API versioning standard
supersedes:
 - ADR-0022
 - ADR-0035
 - ADR-0036
superseded_by: []
review_state: current
related_records:
 - ADR-0048
 - ADR-0055
 - ADR-0059
 - ADR-0063
 - ADR-0076
related_packages:
 - app/packages/access
 - app/infrastructure/http
---

# API Response and Error Mapping Standard

## Context

- Problem statement: Three legacy ADRs (ADR-0022, ADR-0035, ADR-0036) defined overlapping and inconsistent guidance for mapping internal `OperationResult` values to HTTP responses and platform-specific error formats. ADR-0022 defined a platform-agnostic response format abstraction (Card, ErrorMessage, SuccessMessage) at Tier-2. ADR-0035 defined HTTP response status code mapping at Tier-4. ADR-0036 defined dual-interface error handling (API errors as HTTP status codes vs. platform errors as user-friendly messages) at Tier-4. Together, these three records created fragmented authority over a single concern: how internal operation outcomes are translated to external API consumers and platform interfaces. The codebase currently exhibits ad-hoc error mapping — route handlers raise `HTTPException` directly with unstructured detail strings, losing the structured `error_code` and `retry_after` metadata that `OperationResult` carries (ADR-0050 Standard 3). There is no unified error response schema at the API boundary, meaning HTTP clients receive inconsistent error shapes depending on which route they hit.
- Business/operational drivers:
- Establish a single canonical standard for translating `OperationResult` outcomes to HTTP responses, consolidating the authority of ADR-0022, ADR-0035, and ADR-0036.
- Define a structured error response schema at the API boundary so HTTP clients receive machine-readable error information (error code, message, retry guidance) instead of bare detail strings.
- Align error response handling with ADR-0054 structured logging requirements — errors exposed to clients must not leak internal details, credentials, or stack traces.
- Ensure error and response mapping services follow ADR-0056 DI alias ceremony and ADR-0077 service classification.
- Support the dual-interface pattern: HTTP API consumers receive structured JSON error responses; platform consumers (Slack, Teams) receive user-friendly formatted messages via presenter layers (ADR-0059 Standard 2).
- Constraints:
- ADR-0050 defines the canonical `OperationResult` at the integration boundary; this standard governs only the downstream mapping from `OperationResult` → HTTP response (and separately, platform response via presenters).
- ADR-0045 Principle 5 (security-by-default boundaries) prohibits leaking sensitive data in error responses.
- ADR-0048 Boundary 2 requires infrastructure services to be consumed through the injection boundary, not imported directly.
- ADR-0056 Standard 4 (DI alias ceremony) applies to any shared error-mapping utility exposed as a FastAPI dependency.
- ADR-0077 classifies response/error mapping based on consumer scope: if feature-facing, the mapping utility must be classified (Category A, B, or C).
- ADR-0059 Standard 1 (HTTP-first bridge pattern) establishes HTTP routes as the primary testable surface; error mapping is part of that surface.
- Non-goals:
- This record does not define the `OperationResult` type or its status classification (governed by ADR-0050).
- This record does not define platform-specific presentation formatting (Slack Block Kit, Teams Adaptive Cards) — that is governed by ADR-0059 Standard 2 (feature-side interaction boundary with presenters).
- This record does not mandate a specific error response library or framework.

## Decision

- Chosen approach: Consolidate ADR-0022, ADR-0035, and ADR-0036 into a single Tier-2 standard that defines structured error response schemas, exhaustive status mapping, error detail redaction, and the dual-interface separation between API and platform error formatting.
- Why this approach: The three legacy ADRs addressed facets of the same problem — translating internal outcomes to external consumers. Consolidation eliminates ambiguity and ensures consistent treatment at both the HTTP and platform interfaces. Tier-2 is correct because this is an implementation standard, not a foundational principle.

### Standard 1: Structured Error Response Schema

All HTTP API error responses must use a Pydantic `BaseModel` schema at the I/O boundary (ADR-0040 type boundary rule). The schema adopts RFC 9457 (Problem Details for HTTP APIs) as the base structure with application-specific extension members, following the hybrid pattern established by Zalando's RESTful API Guidelines (Rule #176). This provides standards compliance from day one while preserving domain-specific fields.

The canonical error response shape is:

**RFC 9457 base fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | `str` | Yes | URI reference identifying the problem type (RFC 9457 §3.1.1). Use `about:blank` as default for generic HTTP errors. Use relative URI references (e.g., `/problems/rate-limited`, `/problems/sync-conflict`) for application-specific problem types. These URIs are identifiers, not resolvable endpoints. |
| `status` | `int` | Yes | HTTP status code for this occurrence (RFC 9457 §3.1.2). Must match the actual HTTP response status code. |
| `title` | `str` | Yes | Short, human-readable summary of the problem type (RFC 9457 §3.1.3). Should not change between occurrences of the same problem type. |
| `detail` | `str \| None` | No | Human-readable explanation specific to this occurrence (RFC 9457 §3.1.4). Must not contain internal service names, stack traces, credentials, or PII. |

**Extension members (RFC 9457 §3.2):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `error` | `str` | Yes | Machine-readable error code matching `OperationResult.error_code` (e.g., `RATE_LIMITED`, `UPSTREAM_TIMEOUT`, `VALIDATION_FAILED`). Application-specific extension member. |
| `errors` | `dict[str, Any] \| None` | No | Optional structured detail for client-actionable context (e.g., `{"field": "email", "reason": "invalid format"}`). Must not contain sensitive information. Application-specific extension member. |
| `retry_after` | `int \| None` | Conditional | Seconds until retry is appropriate. Mandatory when HTTP status is 503 (maps from `TRANSIENT_ERROR`). Omitted for non-retryable errors. Application-specific extension member. |
| `request_id` | `str \| None` | No | Correlation ID for the request, if available from request-context middleware (ADR-0054). Enables client-side incident reporting. Serves a similar role to RFC 9457's `instance` field. Application-specific extension member. |

**RFC 9457 adoption notes:**

- The response uses `application/json` content type initially. Full RFC 9457 compliance (`application/problem+json`) is deferred until API gateway or external consumer requirements mandate it — switching content types is a breaking change for existing consumers.
- The `instance` field (RFC 9457 §3.1.5) is not included as a separate field; `request_id` serves the same correlation purpose.
- Extension members (`error`, `errors`, `retry_after`, `request_id`) are permitted by RFC 9457 §3.2 and must be ignored by consumers that do not recognize them.
- Problem type URIs use relative paths (e.g., `/problems/rate-limited`) following Zalando's pragmatic approach — no resolvable problem type registry required.

This schema must be defined as a shared Pydantic model in `infrastructure/http/schemas.py` (ADR-0063 Standard 1 Rule S1) and used as the `response_model` for all error responses in OpenAPI documentation.

### Standard 2: Exhaustive OperationResult-to-HTTP Mapping

Route handlers that consume `OperationResult` must perform exhaustive pattern matching on all status variants. The canonical mapping is:

| `OperationStatus` | HTTP Status Code | Response Body | Notes |
|--------------------|-----------------|---------------|-------|
| `SUCCESS` | `200 OK` or `201 Created` or `202 Accepted` | Success response schema (feature-defined). | Route handler selects the appropriate 2xx code based on the operation semantics. |
| `NOT_FOUND` | `404 Not Found` | Error response schema with `type=/problems/not-found`, `error=OperationResult.error_code`. | |
| `UNAUTHORIZED` | `401 Unauthorized` or `403 Forbidden` | Error response schema. 401 for authentication failure; 403 for authorization failure. | Route handler disambiguates based on error context. |
| `PERMANENT_ERROR` | `400 Bad Request` or `409 Conflict` or `422 Unprocessable Entity` | Error response schema with appropriate problem `type`. | Default to 400; use 409 for state conflicts, 422 for validation. |
| `TRANSIENT_ERROR` | `503 Service Unavailable` | Error response schema with mandatory `retry_after`. | `Retry-After` HTTP header should also be set. |

Exhaustive matching means every status variant must be handled explicitly. A catch-all default must log an unrecognized status as a warning and return `500 Internal Server Error` with a generic error response (no internal details).

### Standard 3: Error Detail Redaction

Error responses for server-side errors (5xx) must not include internal details. The redaction rules are:

1. **5xx responses**: `title` must be a generic string (e.g., "An internal error occurred. Please try again later."). `detail` must be null or a generic message. Internal error details are logged via structured logging (ADR-0054) but never exposed in the HTTP response body.
2. **4xx responses**: `title` may include client-actionable context (e.g., "The requested resource was not found" or "Validation failed"). `detail` may provide occurrence-specific explanation. Internal service names, database table names, and provider-specific error codes must not appear in either field.
3. **`errors` field**: If populated, must contain only client-actionable structured information (e.g., `{"field": "email", "reason": "invalid format"}`). Must never contain stack traces, SQL queries, or credential fragments.
4. **Log correlation**: The `request_id` field (when available) enables clients to report errors using the correlation ID, which operators can use to locate the full internal error in structured logs.

This standard implements ADR-0045 Principle 5 (security-by-default boundaries) at the HTTP response layer.

### Standard 4: Dual-Interface Separation

The dual-interface pattern separates error formatting for two consumer types:

1. **HTTP API consumers**: Receive structured JSON error responses per Standard 1. Formatting is handled by route-level error mapping helpers. This is the primary testable surface (ADR-0059 Standard 1).
2. **Platform consumers (Slack, Teams)**: Receive user-friendly formatted messages via the presenter layer in each feature package (ADR-0059 Standard 2). Platform-specific formatting (emoji, Block Kit, Adaptive Cards) is the presenter's responsibility, not the error mapping standard's.

The service layer must remain channel-agnostic (ADR-0059 Standard 1). Neither HTTP error mapping nor platform presenters should be embedded in the service layer. The mapping boundary is:

```
Service Layer → returns OperationResult (channel-agnostic)
    ├── HTTP Route → maps to ErrorResponse schema (Standard 1-3)
    └── Platform Handler → maps via Presenter (ADR-0059 Standard 2)
```

### Standard 5: Error Mapping Utility Classification

Error mapping utilities shared across multiple route modules are classified per ADR-0077:

- **Category B (Shared Utility, Concrete OK)**: A shared helper function (e.g., `operation_result_to_http_response()`) that converts `OperationResult` to an HTTP response. This is a stateless utility with no backing service to abstract. No Protocol contract required.
- **If the utility requires injected dependencies** (e.g., request-context middleware for `request_id`): it must follow ADR-0056 Standard 4 (DI alias ceremony) — provider function in `providers.py`, `Annotated[..., Depends(...)]` alias in `dependencies.py`.
- **Feature-specific presenters** (Slack/Teams formatting): Category C (implementation detail) per ADR-0077. No shared Protocol; each feature owns its presenter.

### Standard 6: OpenAPI Error Documentation

All API routes must document error responses in their OpenAPI schema using FastAPI's `responses` parameter:

1. Every route handler must declare the error response model for each non-2xx status code it can return.
2. Error response descriptions must be concise and client-actionable.
3. The shared error response schema (Standard 1) must be used consistently across all routes — not ad-hoc `dict` or string descriptions.
4. This standard complements ADR-0063 (API Composition and Validation Standard) for route metadata requirements.

## Alternatives Considered

1. Maintain three separate ADRs (ADR-0022, ADR-0035, ADR-0036):
   - Pros: Existing records cover the space.
   - Cons: Overlapping authority; inconsistent tier classifications (Tier-2 + two Tier-4); ADR-0022's response format abstraction is now subsumed by ADR-0059 Standard 2 (presenter pattern).
   - Why not chosen: Consolidation eliminates ambiguity and aligns with ADR-0051 taxonomy.
2. Use FastAPI exception handlers exclusively (no explicit mapping):
   - Pros: Framework-native; less boilerplate.
   - Cons: Exception handlers are global and lose per-route OperationResult context. The structured error_code and retry_after from OperationResult cannot be automatically propagated through FastAPI's exception handler mechanism without custom infrastructure.
   - Why not chosen: Route-level mapping preserves OperationResult metadata and enables exhaustive status matching.
3. Centralized error middleware:
   - Pros: DRY; all error formatting in one place.
   - Cons: Middleware cannot distinguish between different OperationResult sources without adding middleware state. Violates the HTTP-first bridge pattern (ADR-0059 Standard 1) which places mapping responsibility at the route level.
   - Why not chosen: Route-level mapping is more explicit and testable.
4. Promote to Tier-1 Principle:
   - Pros: Maximum authority.
   - Cons: This is an implementation convention, not a foundational invariant. Tier-2 is correct per ADR-0051.
   - Why not chosen: Tier classification must match content scope.

## Consequences

- Positive impacts:
- Single authoritative standard eliminates three-way authority fragmentation.
- Structured error response schema makes errors machine-readable for API clients.
- Exhaustive mapping prevents silent error swallowing and ensures all OperationResult statuses are handled.
- Error redaction rules implement security-by-default (ADR-0045 P5) at the HTTP layer.
- Dual-interface separation keeps the service layer channel-agnostic.
- Tradeoffs accepted:
- Route handlers have slightly more mapping boilerplate compared to global exception handlers. This is acceptable because it provides explicit, testable error handling per route.
- The shared error response schema is a new Pydantic model that must be adopted across all routes. Migration is incremental — new routes adopt immediately; legacy routes migrate during their next touch.
- The response uses `application/json` rather than `application/problem+json` initially, deferring the content type switch until external consumer or API gateway requirements mandate it (RFC 9457 §4.1 permits this).
- Risks introduced:
- Developers may add sensitive information to the `detail` field despite the redaction rules. Mitigation: code review enforcement; structured logging of the full OperationResult provides the internal detail that the response omits.
- Legacy routes using raw `HTTPException` will be inconsistent until migrated. Mitigation: ADR-0063 (API Composition) addresses route migration standards.
- Mitigations:
- ADR-0054 structured logging ensures internal error details are captured for debugging even when redacted from responses.
- Code review checks for sensitive data in error responses.
- OpenAPI schema validation (Standard 6) catches routes that return unstructured errors.

## Compliance and Boundaries

- Package/infrastructure boundary impact: The error response schema is defined in `infrastructure/http/schemas.py` as a shared value type (ADR-0076 Standard 1). This placement is consistent with the infrastructure service model — `ErrorResponse` is a cross-cutting HTTP type, not a feature-owned schema or API-layer artifact. `app/api/` is legacy wiring (ADR-0063 Standard 1) and must not contain a `schemas/` directory. Error mapping helpers are stateless utilities (Category B per ADR-0077) or feature-specific presenters (Category C). Infrastructure services return `OperationResult`; route handlers map it to HTTP responses. The `ErrorResponse` schema includes RFC 9457 base fields (`type`, `status`, `title`, `detail`) and application-specific extension members (`error`, `errors`, `retry_after`, `request_id`).
- Type boundary impact: Error responses use Pydantic `BaseModel` at the HTTP I/O boundary (correct per ADR-0040). `OperationResult` remains a `@dataclass(frozen=True)` at the internal service boundary (ADR-0050). The mapping from dataclass → Pydantic model happens at the route handler level.
- Startup/plugin registration impact: Not directly applicable. Error response schemas are module-level type definitions with no import-time side effects.
- Settings partitioning impact: Not directly applicable. Error mapping is stateless and does not require configuration. If a future enhancement adds configurable error verbosity levels, those settings must follow ADR-0055.
- DI alias ceremony impact: If error mapping utilities are exposed as FastAPI dependencies, they must follow ADR-0056 Standard 4. Currently, the mapping is a pure function (no DI needed), but the standard allows for future dependency injection.
- Service contract impact: Error/response mapping utilities that cross feature boundaries must be classified per ADR-0077. The shared error response schema is a value type (permitted for cross-boundary import per ADR-0076 Standard 1). Presenters are feature-owned (Category C).

## Codebase Audit (2026-04-29)

### Current Violations

| Location | Violation | Standard |
|----------|-----------|----------|
| `app/api/v1/routes/webhooks.py` | Raises `HTTPException` with bare detail strings; no structured error schema; embeds business logic in route handler. | Standard 1, Standard 2 |
| `app/api/v1/routes/geolocate.py` | Raises `HTTPException(404)` with detail string; no error response model. | Standard 1 |
| `app/packages/access/sync/interactions/http.py` | `_http_error_from_enqueue()` maps error_code to status_code but returns `HTTPException` with bare detail string, not the canonical error schema. | Standard 1 |
| All existing routes | No OpenAPI error response documentation; `responses` parameter not used. | Standard 6 |

### Compliant Patterns (Reference)

| Location | Pattern | Notes |
|----------|---------|-------|
| `app/packages/access/sync/presenters.py` | `to_http_status_response()` maps OperationResult to HTTP-consumable dict; `to_slack_status_message()` maps to Slack blocks. | Implements dual-interface separation (Standard 4) directionally. Needs schema alignment with Standard 1. |
| `app/infrastructure/operations/result.py` | `OperationResult` with status, error_code, message, retry_after fields. | ADR-0050 compliant source; provides the metadata that Standard 1 schema exposes. |

### Migration Path

1. **Phase 1 (immediate)**: Define canonical `ErrorResponse` Pydantic model in `infrastructure/http/schemas.py` (ADR-0063 Standard 1 Rule S1) with RFC 9457 base fields (`type`, `status`, `title`, `detail`) and extension members (`error`, `errors`, `retry_after`, `request_id`). Add shared `operation_result_to_response()` helper that populates both RFC 9457 base fields and extension members from `OperationResult`.
2. **Phase 2 (incremental)**: New routes and touched routes adopt the canonical error schema. Add `responses` parameter to route decorators.
3. **Phase 3 (full migration)**: All routes use canonical error schema. Remove ad-hoc `HTTPException` raises with detail strings.

## Best-Practice Revalidation

- Revalidation date: 2026-04-29
- Sources rechecked:
- RFC 9457 Problem Details for HTTP APIs (<https://www.rfc-editor.org/rfc/rfc9457>) — IETF Internet Standard; base fields and extension members adopted.
- Zalando RESTful API Guidelines — Rule #176 (<https://opensource.zalando.com/restful-api-guidelines/#176>) — MUST support problem JSON; validates hybrid approach with relative URI problem types.
- OWASP Improper Error Handling (<https://owasp.org/www-community/Improper_Error_Handling>) — error detail redaction guidance.
- FastAPI Error Handling documentation (<https://fastapi.tiangolo.com/tutorial/handling-errors/>).
- Google API Design Guide - Errors (<https://cloud.google.com/apis/design/errors>) — structured error response patterns.
- Microsoft REST API Guidelines - Error Responses (<https://github.com/microsoft/api-guidelines/blob/vNext/azure/Guidelines.md>) — counterexample using custom error schema; validates hybrid as middle ground.
- Alignment summary:
- Standard 1 adopts RFC 9457 (Problem Details) hybrid approach — the error response schema includes RFC 9457 base fields (`type`, `status`, `title`, `detail`) alongside application-specific extension members (`error`, `errors`, `retry_after`, `request_id`) per RFC 9457 §3.2. This follows the pattern established by Zalando RESTful API Guidelines (Rule #176) for RFC 9457 with extensions.
- Standard 3 (error redaction) aligns with OWASP improper error handling guidance.
- Standard 2 (exhaustive mapping) aligns with Google API Design Guide's status code mapping table.
- Intentional deviations:
- The response uses `application/json` content type rather than `application/problem+json`. This is a pragmatic deferral — switching content types is a breaking change for existing consumers, and RFC 9457 §4.1 permits application-specific formats. The `application/problem+json` media type can be adopted when (a) API gains external consumers, (b) API gateway requires standard problem details, or (c) >3 consuming services integrate against the error schema.
- Problem type URIs use relative paths (e.g., `/problems/rate-limited`) rather than absolute URIs. This follows Zalando's guidance — these are identifiers, not resolvable endpoints.

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: Consolidates ADR-0022, ADR-0035, and ADR-0036 into one Tier-2 standard with RFC 9457-compliant structured error schema (hybrid approach: base fields + extension members), exhaustive mapping, redaction rules, dual-interface separation, and OpenAPI documentation requirements.
- Follow-up actions:
- Mark ADR-0022, ADR-0035, ADR-0036 as superseded with `superseded_by: [ADR-0060]`.
- Ensure ADR-0063 references this record in `constrained_by` for route composition error documentation.
- Define `ErrorResponse` Pydantic model in `infrastructure/http/schemas.py` (ADR-0063 Standard 1 Rule S1) with RFC 9457 base fields and extension members.
- Adopt `application/problem+json` content type when: (a) API gains external consumers, (b) API gateway requires standard problem details, or (c) >3 consuming services integrate against the error schema.

## Source References

1. Source title: RFC 9457 - Problem Details for HTTP APIs
   - URL: <https://www.rfc-editor.org/rfc/rfc9457>
   - Publisher/maintainer: IETF
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Industry standard for structured HTTP error responses; Standard 1 adopts RFC 9457 base fields (`type`, `status`, `title`, `detail`) with application-specific extension members per §3.2.
2. Source title: OWASP Improper Error Handling
   - URL: <https://owasp.org/www-community/Improper_Error_Handling>
   - Publisher/maintainer: OWASP Foundation
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Error detail redaction guidance; informs Standard 3.
3. Source title: Google API Design Guide - Errors
   - URL: <https://cloud.google.com/apis/design/errors>
   - Publisher/maintainer: Google Cloud
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Structured error response patterns and status code mapping; informs Standard 2.
4. Source title: FastAPI Error Handling
   - URL: <https://fastapi.tiangolo.com/tutorial/handling-errors/>
   - Publisher/maintainer: Sebastián Ramírez
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Framework-native error handling patterns; validates route-level mapping approach.
5. Source title: ADR-0050 - Operation Result Canonical Standard
   - URL: docs/decisions/adr/0050-operation-result-canonical-standard.md
   - Publisher/maintainer: SRE Team
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Upstream standard defining OperationResult; this standard governs downstream mapping.
6. Source title: Zalando RESTful API Guidelines — Rule #176: MUST support problem JSON
   - URL: <https://opensource.zalando.com/restful-api-guidelines/#176>
   - Publisher/maintainer: Zalando SE
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Industry reference for RFC 9457 adoption with extension members and relative URI problem types. Validates the hybrid approach (RFC 9457 base + custom extensions) chosen for Standard 1.
7. Source title: Microsoft Azure REST API Guidelines — Error Responses
   - URL: <https://github.com/microsoft/api-guidelines/blob/vNext/azure/Guidelines.md>
   - Publisher/maintainer: Microsoft
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Major counterexample — Azure uses a fully custom error schema without RFC 9457. Validates that custom extensions alongside standard fields is a defensible middle ground.
8. Source title: ADR-0022, ADR-0035, ADR-0036 (Legacy)
   - URL: docs/decisions/adr/
   - Publisher/maintainer: SRE Team
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Superseded legacy records whose content is consolidated here.
