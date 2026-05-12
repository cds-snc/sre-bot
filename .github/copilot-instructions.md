# Copilot Agent Instructions

## Architecture Principles

**Layered architecture with unidirectional dependencies:**
- Application layer (features in `app/packages/`) → Infrastructure layer (Protocols, services) → Vendor clients (`app/clients/`) → External services
- Reverse imports prohibited
- No feature imports from other features

**Type boundaries by purpose, not shape:**
- Service contracts: `typing.Protocol`
- Internal domain types: `@dataclass(frozen=True)`
- HTTP I/O: `pydantic.BaseModel`
- Configuration: `pydantic_settings.BaseSettings`
- Adapter internals: `typing.TypedDict`
- Status enums: `enum.Enum`

**Integration boundaries use OperationResult:**
- Five-status closed enum: SUCCESS, NOT_FOUND, TRANSIENT_ERROR, PERMANENT_ERROR, UNAUTHORIZED
- Appears: adapter Protocol methods → feature services → handlers
- Not: inside domain logic, routes, feature contracts

## Feature Package Structure

Required:
- `__init__.py` (public surface, hookimpls)
- `service.py` (business logic)

Optional by concern:
- `models.py` (Pydantic request/response)
- `domain.py` (frozen dataclasses, enums)
- `routes.py` (FastAPI handlers)
- `adapters/` (feature-owned outbound adapters)
- `providers.py` (per-feature DI/composition)
- `settings.py` (feature BaseSettings)
- `slack/`, `teams/` (transport handlers by platform)

One feature = one Pluggy plugin; plugins registered via entry-points in pyproject.toml.

## HTTP API Pattern

- Routes: thin adapters (parse → service → map response)
- Inject via `Annotated[Protocol, Depends(...)]`
- Map `OperationResult` to RFC 9457 Problem Details + HTTP status:
  - SUCCESS → 200/201/202/204 (application/json)
  - NOT_FOUND → 404
  - UNAUTHORIZED → 401/403
  - PERMANENT_ERROR → 400/409/422
  - TRANSIENT_ERROR → 503 + Retry-After header/extension
- Error bodies include: type, status, title, detail, error_code, request_id, retry_after

## Testing

Three layers:
- **Unit** (<50ms): isolated units with Protocol fakes
- **Integration** (<500ms): feature + infrastructure Protocols with real internal composition; stub external deps
- **Smoke**: live system validation

Layout: `tests/unit/`, `tests/integration/`, `tests/smoke/` mirror `app/` structure.

Use `app.dependency_overrides` for Protocol substitution; clear in finally block.

## Startup & Plugin Lifecycle

Phases (fail-fast):
1. Configuration (env vars)
2. Infrastructure (composed services)
3. Discovery/Registration (entry-points plugin load)
4. Feature Activation (hookimpls)
5. Transport (route/handler binding)
6. Background (task registration)

- Pluggy `PluginManager` singleton via `@lru_cache`
- No import-time side effects
- Hookspecs centralized; plugins own hookimpls
- `startup_warmup` hook allows warmup; failures propagate

## Static Analysis & Quality

- No Pydantic in domain modules (only at trust boundaries)
- No vendor types above infrastructure layer
- Feature packages don't import each other
- `OperationResult` only at integration boundaries
- No nested `BaseSettings`
- Feature imports follow entry-points declaration
