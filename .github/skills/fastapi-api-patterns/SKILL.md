---
name: fastapi-api-patterns
description: Apply typed FastAPI route patterns with clean dependency boundaries, stable error mapping, and test coverage for success/failure paths.
---

Use when implementing or reviewing API endpoints.

## Handler Pattern (ADR-0063)

- Routes are thin adapters: parse input → invoke service → map response.
- Inject via `Annotated[Protocol, Depends(...)]`. Never import concrete Category A classes.
- Use `BaseModel` for request/response schemas at HTTP boundary only.

## Error Mapping (ADR-0060)

- RFC 9457 schema: `type`, `status`, `title`, `detail`, `error`, `errors`, `retry_after`, `request_id`.
- Map every `OperationResult` status to HTTP explicitly. No catch-alls.
- 5xx redacts internals (log separately). 4xx gives client-actionable context.
- Never return raw `OperationResult` from handlers.

## OpenAPI (ADR-0063)

- One tag per router. `summary`, `description`, `response_model`, `status_code` on every handler.
- Public fields include `Field(description=...)`.

## Forbidden

- Business logic in route handlers.
- Importing concrete Category A classes in routes.
- Broad exception catches collapsing distinct errors.

## Test Coverage (ADR-0062)

1. Success path with schema assertions.
2. Failure mapping (error status → HTTP status + RFC 9457 body).
3. Dependency variation (auth/permission where relevant).

Use `app.dependency_overrides`; always `finally` clear.