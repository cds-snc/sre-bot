---
title: "API Design and Error Mapping"
status: Accepted
type: Standard
tier: Tier-2
governance_domain: [application]
concerns: [api, architecture]
constrained_by: [layered-architecture.md, type-boundaries.md, operation-result-pattern.md, feature-package-structure.md, application-lifecycle.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# API Design and Error Mapping

## Context and Problem Statement

The application exposes HTTP routes that are the boundary between external callers and internal feature services. A feature's service layer returns the application's domain envelope — a closed-status `OperationResult` — to its route handler. The route handler is the place where that internal envelope is translated into an HTTP response: a status code, a media type, a body shape, and (when applicable) headers like `Retry-After` and `Content-Type`. Without a single shared rule for that translation, every feature reinvents the body shape, picks its own status codes, and produces error responses that are inconsistent across the API surface.

The problem this record addresses: **what is the canonical HTTP response shape for the application's API — both success and error — and how is the internal `OperationResult` mapped onto an HTTP response with status code, headers, body schema, and OpenAPI documentation?** The answer determines:

1. What an external caller sees on every error: the body's shape, the media type, the fields that name the failure mode, and the headers that guide retry behaviour.
2. Where the mapping logic lives — duplicated across route handlers, or centralized in one helper at the framework boundary.
3. Whether OpenAPI documentation accurately reflects the responses callers actually receive (success and every error path), or only the success body.
4. How Pydantic's request-validation errors (the `422` path that FastAPI raises before any route function runs) are surfaced to callers in the same shape as application-emitted errors, rather than as FastAPI's default ad-hoc structure.

**Constraints:**

- The application's services return a closed five-status `OperationResult` envelope (`SUCCESS`, `NOT_FOUND`, `TRANSIENT_ERROR`, `PERMANENT_ERROR`, `UNAUTHORIZED`). Any HTTP mapping table must be exhaustive over those five statuses.
- HTTP semantics are governed by the HTTP/1.1 / HTTP semantics specification: status-code categories (1xx–5xx), `Retry-After` header semantics, content negotiation. The mapping must be a faithful application of those semantics, not a parallel scheme.
- The application is built on FastAPI; route handlers, dependency injection, and OpenAPI generation use FastAPI's primitives. The chosen shape must integrate with FastAPI's exception handlers, response models, and `responses=` route declarations rather than fight them.
- Body schemas at the HTTP boundary are Pydantic `BaseModel`s (trust-boundary types per the type-boundary decision); domain types (frozen dataclasses) do not appear directly on the wire.

**Non-goals:**

- This record does not define authentication, authorization, or rate-limiting policy at the HTTP boundary. Those concerns are owned by separate records.
- This record does not define cross-channel correlation-ID semantics or the request-context propagation mechanism. It specifies that a `request_id` extension member appears in error bodies, but the issuance and propagation rules belong elsewhere.
- This record does not pick the route's path layout for any specific feature, the URL versioning scheme, or per-feature path conventions beyond the rule that a feature's routes live where the feature-package-structure decision says they live.
- This record does not redefine the `OperationResult` envelope; it only maps it to HTTP. Adding or removing a status is outside scope.
- This record does not govern non-HTTP transports (Slack events, Teams payloads, queue messages); their response shapes are handled by their own decisions.

## Considered Options

**Option 1 — Bare `HTTPException` with ad-hoc detail strings.** Each route raises `HTTPException(status_code=…, detail="…")`. The default FastAPI body is `{"detail": "<string>"}`. Every route picks its own status codes and detail strings; the body shape is consistent only because FastAPI defaults are.

**Option 2 — Custom application-defined JSON envelope.** A project-specific shape, e.g., `{"status": "error", "code": "<feature>.<reason>", "message": "…"}`, returned with a `2xx`-only success body. Body fields are project-defined and consistent across the API but use no industry standard.

**Option 3 — RFC 9457 Problem Details for HTTP APIs.** Errors are returned as `application/problem+json` bodies with the standard base members (`type`, `status`, `title`, `detail`, `instance`) plus extension members for the application's needs (`error_code`, `retry_after`, `request_id`). The IETF specification governs the shape and the media type; clients can rely on a standardized error format.

**Option 4 — Status-in-body, always-`200`.** Every response is `200 OK` with a body that carries the actual status (`{"status": "NOT_FOUND", …}`). HTTP status loses signalling value. Violates HTTP semantics and breaks proxy/cache/observability tools that key on status codes.

## Decision Outcome

**Chosen: Option 3 — RFC 9457 Problem Details, with extension members carrying the application's `OperationResult` metadata.**

RFC 9457 is the IETF-published standard for HTTP API error bodies; its shape is wire-compatible with HTTP semantics (the `status` member echoes the actual HTTP status code), it accommodates application-specific data through documented extension members, and it integrates cleanly with FastAPI's exception-handler and `responses=` mechanisms. The closed-status `OperationResult` envelope maps onto problem-details with no information loss: `error_code` becomes an extension member, `retry_after` becomes both an extension member and the `Retry-After` HTTP header on transient failures, and `request_id` becomes an extension member tying the problem to logs and traces.

### Media types and base body shape

Two media types are used at the HTTP boundary:

| Response category | Media type | Body shape |
| --- | --- | --- |
| Success (`2xx`) | `application/json` | The route's declared `response_model` (a Pydantic `BaseModel`) |
| Error (`4xx`, `5xx`) | `application/problem+json` | RFC 9457 problem-details object |

Every error body is a JSON object containing at minimum the following base members from the standard:

- `type` — a URI reference identifying the problem category (e.g., `urn:problem:not-found`, `urn:problem:transient-error`). When omitted, defaults to `about:blank`. The application uses `urn:problem:<kebab-case-status>` as the canonical form so the URI is stable, opaque, and never resolvable by accident.
- `status` — the HTTP status code as a number. Echoes the response's actual status code.
- `title` — a short, human-readable summary of the problem category. Stable for a given `type`; does not vary per occurrence.
- `detail` — a human-readable explanation specific to this occurrence. Subject to the redaction policy below.
- `instance` — optional. When present, a URI reference identifying the specific occurrence (e.g., a request URL). Omitted when no stable URI exists.

### Extension members

The RFC permits problem-type definitions to include additional members. The application standardizes on three extensions, present where applicable:

- `error_code` — the application's machine-readable error code from `OperationResult.error_code`. Stable identifier callers can branch on (e.g., `notify.template_not_found`, `aws.access_denied`).
- `retry_after` — the retry guidance from `OperationResult.retry_after`, in seconds. Present only on `TRANSIENT_ERROR` responses (HTTP `503`). When present, the response also carries the `Retry-After` HTTP header with the same value.
- `request_id` — the request correlation ID. Always present in error bodies; logs and traces are queried by this value.

Other extension members are added only when a specific problem type warrants them (e.g., a `errors` array of field-level validation details on `422`); each is documented at the `type` URI's specification.

### `OperationResult` → HTTP mapping

Every value of `OperationStatus` maps to one HTTP outcome category. The mapping is closed; route handlers do not invent status codes outside this table.

| `OperationStatus` | HTTP status | Default `type` | When the route may pick another code |
| --- | --- | --- | --- |
| `SUCCESS` | `200` (read), `201` (create), `202` (accepted/async), `204` (no content) | n/a | The route picks the `2xx` that matches the operation's HTTP semantics. Body is `application/json` with the route's declared `response_model`. |
| `NOT_FOUND` | `404` | `urn:problem:not-found` | — |
| `UNAUTHORIZED` | `401` (no/invalid credentials) or `403` (authenticated but not authorized) | `urn:problem:unauthorized` / `urn:problem:forbidden` | The route disambiguates based on the underlying cause; both originate from `OperationStatus.UNAUTHORIZED`. |
| `PERMANENT_ERROR` | `400` (default), `409` (conflict), `422` (semantic validation) | `urn:problem:permanent-error` (or specific subtype) | The route picks the `4xx` that matches the failure shape. Application-side `PERMANENT_ERROR` always becomes a `4xx`, never a `5xx`. |
| `TRANSIENT_ERROR` | `503` | `urn:problem:transient-error` | The response always carries `Retry-After` (header) and `retry_after` (body extension), populated from `OperationResult.retry_after`. |

Three additional rules govern the mapping:

- **Unhandled exceptions** (anything that escapes a route handler) become `500` with `type = urn:problem:internal-error`. This category is distinct from `TRANSIENT_ERROR` (which is a *handled* outcome the service produced); a `500` indicates a bug or an unexpected runtime failure.
- **Request validation failures** (Pydantic `RequestValidationError` raised by FastAPI before the handler runs) become `422` with `type = urn:problem:request-invalid` and an `errors` array containing the per-field validation details.
- **Method-not-allowed** and **route-not-found** at the framework level become `405` and `404` respectively, with `type` URIs of `urn:problem:method-not-allowed` and `urn:problem:route-not-found`. These are framework-level outcomes, not `OperationResult` outcomes.

### `Retry-After` header on `503`

When `OperationStatus` is `TRANSIENT_ERROR` and `OperationResult.retry_after` is set, the response includes:

- HTTP header `Retry-After: <seconds>` (delta-seconds form). This is the form HTTP semantics define for the header; HTTP-date form is not used.
- Body extension member `retry_after: <seconds>`. Same value as the header.

If `retry_after` is absent on a `TRANSIENT_ERROR`, the header is omitted; callers fall back to their own backoff policy. The body extension member is also omitted in that case.

### Redaction policy

The body of an error response distinguishes by status category:

- **`5xx` (server-side outcomes).** `detail` is generic and does not include internal data: stack traces, vendor error messages, internal identifiers, or query fragments are not exposed. The redacted form names the category (e.g., "An internal error occurred") and references the `request_id` so operators can correlate to logs.
- **`4xx` (client-actionable outcomes).** `detail` may include client-actionable context: the offending field name, the constraint violated, the value range expected. Internal identifiers and credentials are still excluded.
- **`429` and `503`.** `detail` is short and operational ("Service temporarily unavailable"). The interesting information is the status code and `retry_after`.

`error_code` is included in both categories (callers may branch on it). `request_id` is always included.

### Validation errors (`422`)

FastAPI's default `RequestValidationError` body is `{"detail": [{"loc": …, "msg": …, "type": …}, …]}` — an ad-hoc shape that does not match RFC 9457. The application registers a single `RequestValidationError` exception handler at app construction that produces a problem-details body:

```text
{
  "type": "urn:problem:request-invalid",
  "status": 422,
  "title": "Request validation failed",
  "detail": "The request body or parameters did not match the operation's contract.",
  "errors": [
    {"location": "body", "field": "items.0.quantity", "message": "Input should be a valid integer", "code": "type_error.integer"}
  ],
  "request_id": "<uuid>"
}
```

The `errors` array is the validation extension. Each element names where the violation occurred (`location` ∈ `path` | `query` | `header` | `cookie` | `body`), the offending field path, the human-readable message, and the validator's `type` code. Stack traces and offending values are not echoed.

### Centralization: where the mapping lives

The translation from `OperationResult` to `JSONResponse` lives in **one** module at the framework level (under `app/server/` or equivalent infrastructure layer), exposed as a small, dependency-free utility:

```python
def operation_result_to_response(result: OperationResult, request_id: str) -> JSONResponse: ...
```

Route handlers do not construct problem-details bodies inline; they call the utility. The utility:

- Picks the HTTP status from the `OperationStatus → HTTP` table (with `2xx` provided by the route for `SUCCESS`, since the route knows whether the operation is a read, a create, etc.).
- Sets the `Content-Type` to `application/problem+json` for error responses and `application/json` for success.
- Populates the body's base members (`type`, `status`, `title`, `detail`) from a small lookup keyed on `OperationStatus` plus optional override.
- Populates extension members (`error_code`, `retry_after`, `request_id`) from the `OperationResult` and the request-bound `request_id`.
- Sets the `Retry-After` header on `TRANSIENT_ERROR` when `retry_after` is present.

A second module hosts the **exception handlers**: one for `RequestValidationError` (produces the `422` problem-details body), one for `StarletteHTTPException` (preserves explicit `HTTPException` raises but formats them as problem-details), and one for `Exception` (catches unhandled exceptions, logs with full context, returns a redacted `500`). The handlers are registered once during application construction, before transports bind.

### OpenAPI documentation

Every route declaration documents both the success and the error responses. Three rules:

1. **`response_model` documents the success body.** The Pydantic model returned on `2xx` is declared via `response_model=`; FastAPI emits its schema in OpenAPI.
2. **`responses=` documents every error status the route may produce.** A shared dictionary `ERROR_RESPONSES` (defined alongside the mapping helper) names the status codes that are universal across the application (`401`, `403`, `404`, `422`, `500`, `503`) and points each to the shared `ProblemDetails` schema. Each route may add status-code-specific examples or override the shared description.
3. **`operation_id` is set explicitly.** A stable `operation_id` per route makes the OpenAPI document version-stable; client generators rely on it. The convention is `<feature>_<verb>_<noun>` in snake_case.

A shared `tags=["<feature_name>"]` parameter groups a feature's routes in the generated documentation. The feature name is the package directory name.

### HTTP method and path conventions

The decision is intentionally light here — most routing decisions are per-feature — but three universal rules apply:

- **HTTP methods follow HTTP semantics.** `GET` is safe and idempotent. `PUT` and `DELETE` are idempotent. `POST` is not. `PATCH` is not idempotent unless the body declares it (rare). A route's method matches the action's semantics, not the route's path shape.
- **Status code is never `200` for a logical error.** A route that produces `OperationStatus.NOT_FOUND` returns `404`, not `200` with an error body.
- **Paths are kebab-case.** Path segments are lowercase, hyphen-separated. Query parameters and JSON body fields are snake_case. (This is the pragmatic Python-to-URL convention; mixed casing on the wire is avoided.)

## Consequences

**Positive:**

- Every error response across the API uses one shape, one media type, and one set of extension members. A caller writes one error parser; FastAPI clients generate one error type.
- The shape is an IETF standard (RFC 9457). New consumers do not need to learn a project-specific format; SDKs and observability tools that recognize problem-details work out of the box.
- The mapping helper centralizes what would otherwise be duplicated in every route. Adding a new error subtype (a more specific `type` URI for an existing `OperationStatus`) is one edit at one place.
- OpenAPI documentation reflects the actual response shape — including error responses — because every route declares `responses=` against the shared schema. Generated client code matches what the server actually sends.
- Validation errors and application errors share the same shape; consumer code does not branch on whether the failure happened before or inside a handler.

**Tradeoffs accepted:**

- The error body is verbose (five base members plus extensions). The cost is bytes on the wire; the benefit is unambiguous structured failure information. This trade is well-established at the API-design level.
- `application/problem+json` is a less-common media type than `application/json`. Some debugging tools default to the latter and may not auto-pretty-print the former. The cost is small; the rule is correct per the standard.
- A redaction policy on `5xx` means callers cannot self-diagnose internal failures. The mitigation is the `request_id` extension: callers report it; operators correlate to logs.

**Risks:**

- A route bypasses the mapping helper and constructs its own `JSONResponse`. The body shape diverges. Mitigation: code review; the helper is the only sanctioned constructor of `application/problem+json` bodies. A static lint check (or a contract test against the OpenAPI document) can flag any non-matching body shape.
- A new `OperationStatus` is added to the envelope without a corresponding row in the HTTP mapping table. Mitigation: the envelope's status set is closed and changing it is governance-grade; that change carries an explicit obligation to update this record's mapping table.
- The `type` URI scheme (`urn:problem:<kebab-case-status>`) implies a stable vocabulary over time. Renaming a `type` is a breaking change for callers that branch on it. Mitigation: `type` URIs are added through review and never renamed; deprecating one means adding a new one and deleting the old after a grace period.

## Confirmation

Compliance is verified by:

- **Repository contents.** A single `app/server/responses.py` (or equivalent path) contains `operation_result_to_response()` and exception-handler functions. A single `app/server/schemas.py` defines `ProblemDetails` and `ValidationErrorItem` Pydantic models. The application factory (in app construction code) registers the exception handlers exactly once.
- **OpenAPI document.** The generated `/openapi.json` includes the shared `ProblemDetails` schema in `components.schemas`. Every route's `responses` map references that schema for the error statuses it can produce. Every route has an `operation_id` and a `tags` array.
- **Code review.** A PR adding a route that does not use `operation_result_to_response()` for error paths is rejected. A PR that adds a new `type` URI without documenting it is rejected.
- **Tests.** A contract test asserts that, for each `OperationStatus`, the helper produces the correct HTTP status, the correct `type` URI, the correct media type, and the correct headers. A second test asserts that a `RequestValidationError` raised by an inbound payload produces an `application/problem+json` body of the expected shape.
- **Static analysis.** A check forbids `JSONResponse(..., media_type="application/problem+json", ...)` outside the `app/server/responses.py` module — the helper is the only legitimate construction site.

## Source References

1. RFC 9457 — Problem Details for HTTP APIs
   - URL: <https://www.rfc-editor.org/rfc/rfc9457.html>
   - Accessed: 2026-05-08
   - Relevance: Defines the canonical machine-readable error-response format for HTTP APIs: media type `application/problem+json`, base members (`type`, `status`, `title`, `detail`, `instance`), and the extension-member mechanism for application-specific data. Grounds the chosen body shape and the rule that extensions must be ignored by clients that do not recognize them.

2. RFC 9110 — HTTP Semantics (Status Codes and Headers)
   - URL: <https://www.rfc-editor.org/rfc/rfc9110.html>
   - Accessed: 2026-05-08
   - Relevance: Specifies HTTP status-code categories (1xx–5xx) and their meanings: `404 Not Found`, `401 Unauthorized`, `403 Forbidden`, `409 Conflict`, `422 Unprocessable Content`, `503 Service Unavailable`. Specifies the `Retry-After` header in delta-seconds and HTTP-date forms. Grounds the `OperationStatus → HTTP` mapping table and the `Retry-After` header rule.

3. FastAPI — Handling Errors
   - URL: <https://fastapi.tiangolo.com/tutorial/handling-errors/>
   - Accessed: 2026-05-08
   - Relevance: Documents `HTTPException`, custom exception handlers via `@app.exception_handler`, the default `RequestValidationError` body shape, and the pattern for overriding the validation handler with `JSONResponse`. Grounds the centralized exception-handler mechanism and the override of FastAPI's default `422` body.

4. FastAPI — Additional Responses in OpenAPI
   - URL: <https://fastapi.tiangolo.com/advanced/additional-responses/>
   - Accessed: 2026-05-08
   - Relevance: Documents the `responses=` parameter on path operations and how it adds entries to the OpenAPI document, including per-status `model` declarations. Grounds the rule that every route declares `responses=` against the shared `ProblemDetails` schema.

5. IANA — HTTP Status Code Registry
   - URL: <https://www.iana.org/assignments/http-status-codes/http-status-codes.xhtml>
   - Accessed: 2026-05-08
   - Relevance: The authoritative registry of HTTP status codes. Grounds the constraint that the application's status set is a subset of the registered codes, and that the canonical names used in `title` fields match the registered phrases.

6. OpenAPI Specification 3.1
   - URL: <https://spec.openapis.org/oas/v3.1.0>
   - Accessed: 2026-05-08
   - Relevance: Defines the `responses` object, `operationId`, `tags`, and reusable schema components in `components.schemas`. Grounds the OpenAPI documentation rules (shared `ProblemDetails` schema, stable `operation_id`, feature-named `tags`).

## Change Log

- 2026-05-08: Created. Establishes RFC 9457 Problem Details (`application/problem+json`) as the canonical error body across the API, with three application-defined extension members (`error_code`, `retry_after`, `request_id`). Pins an exhaustive `OperationStatus → HTTP` mapping table covering `SUCCESS`, `NOT_FOUND`, `UNAUTHORIZED`, `PERMANENT_ERROR`, and `TRANSIENT_ERROR`, plus framework-level outcomes (`500` for unhandled exceptions, `422` for request validation, `404`/`405` for routing failures). Centralizes the mapping in one helper module and the exception handlers (`RequestValidationError`, `StarletteHTTPException`, `Exception`) at one app-construction registration point. Establishes the redaction policy (`5xx` generic, `4xx` client-actionable). Requires every route to declare `responses=` against a shared `ProblemDetails` schema and to set `operation_id` and `tags` explicitly. Pins the `Retry-After` header to delta-seconds form, populated from `OperationResult.retry_after` on `TRANSIENT_ERROR`.
