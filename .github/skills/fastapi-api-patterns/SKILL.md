---
name: fastapi-api-patterns
description: Apply typed FastAPI route patterns with clean dependency boundaries, stable error mapping, and test coverage for success/failure paths.
---

# FastAPI API Patterns

Use this skill when implementing or reviewing API endpoints.

## Core Rules

1. Keep transport concerns in router layers only.
2. Keep business logic in package services.
3. Use typed schemas at I/O boundaries.
4. Map domain/application errors to stable HTTP responses.
5. Ensure async-safe I/O boundaries.
6. Add or adjust tests for success and failure paths.

## Handler Shape

- Prefer explicit request/response models.
- Keep handlers orchestration-thin.
- Inject dependencies through providers/dependencies rather than in-handler construction.

## Error Mapping

- Do not return raw internal result envelopes from routes.
- Normalize domain errors to consistent HTTP status codes and response detail shape.
- Log contextual, non-sensitive metadata for failures.

## Forbidden Patterns

- Business logic directly in route handlers.
- Returning raw `OperationResult` objects from HTTP handlers.
- Accessing `request.app.state` inside handlers when a dependency can be injected.
- Broad exception catches that collapse distinct error classes.
- Environment-derived CORS/security middleware configuration (e.g. toggling `allow_origins` on `ENVIRONMENT`/`PREFIX`) - use an explicit, settings-driven allow-list instead.
- `CORSMiddleware` with any of `allow_origins`, `allow_methods`, or `allow_headers` set to `["*"]` while `allow_credentials=True` - browsers and Starlette both reject/forbid this combination; all three must be explicit lists when credentials are enabled.

## Test Matrix (Minimum)

1. Success response path with expected schema.
2. Failure mapping path (at least one domain/application error).
3. Dependency-driven path (auth/rate limit/permission branch where relevant).

## OpenAPI Minimum Metadata

- Router includes exactly one tag.
- Route includes a clear summary and/or description.
- Route defines expected response mapping for non-2xx conditions.
- Public request/response fields include descriptions.