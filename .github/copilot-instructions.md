# Project AI Operating Contract

**Governance:** ADRs in `docs/decisions/adr/` are the source of truth. If this document and an ADR conflict, the ADR wins.

## Stack

Python 3.12+, FastAPI, API/backend only.

## Architecture (ADR-0045, ADR-0048)

- Unidirectional flow: Application → Service → Infrastructure. No reverse imports.
- Business logic in `app/packages/<domain>`. Shared platform capabilities in `app/infrastructure`.
- `app/modules` is legacy — no new code, not an architectural reference.
- Prefer managed cloud service > library > custom code (ADR-0045 P7).

## Type Boundaries (ADR-0065)

| Boundary | Type |
|----------|------|
| Service contracts | `typing.Protocol` |
| Internal domain data | `@dataclass(frozen=True)` |
| HTTP/webhook I/O | `pydantic.BaseModel` |
| Env configuration | `pydantic_settings.BaseSettings` |
| Dict-shaped adapters | `typing.TypedDict` |

Do not use Pydantic internally. Keep transport and domain models separate.

## Dependencies (ADR-0048, ADR-0056, ADR-0077)

- Consume infrastructure via `Annotated[Protocol, Depends(...)]` from `infrastructure.services.dependencies`.
- Constructor-only injection. No import-time side effects.
- Service classification (ADR-0077): A = Protocol-required, B = shared utility (concrete OK), C = implementation detail (never exposed to features).
- Composition in `providers.py` only. Intra-layer value-type imports OK (ADR-0076).

## Settings (ADR-0047, ADR-0055, ADR-0056)

- One `BaseSettings` + `@lru_cache` provider per domain. No key duplication.
- Three-way ownership: `infrastructure/configuration/infrastructure/`, `infrastructure/configuration/integrations/`, `packages/<feature>/settings.py`.
- Narrow-slice injection — never pass full Settings tree.
- Never nest `BaseSettings` in `BaseSettings` — use `BaseModel` for sections.

## Startup (ADR-0046, ADR-0049)

- 6-phase startup: Config → Infra → Discovery → Features → Transport → Background. Reverse shutdown.
- Fail-fast — phase failure terminates startup. Immutable registries after startup.
- Pluggy-based: `auto_discover_plugins`, hookspecs before plugins, `check_pending()`, keyword-only invocation.
- Package `__init__.py`: only `@hookimpl` functions. Zero-touch extension.

## API (ADR-0060, ADR-0063)

- Routes are thin adapters: parse → invoke service → map response. No business logic.
- RFC 9457 error schema. Exhaustive OperationResult-to-HTTP mapping. 5xx redacts internals.
- Middleware order: CORS → Rate Limiting → Request Context → Error Handling → Auth (dependency).
- OpenAPI: one tag per router; summary, description, response_model, status_code on every handler.

## OperationResult (ADR-0050)

External API calls return `OperationResult`; internal logic uses exceptions. Status: `SUCCESS`, `TRANSIENT_ERROR` (requires `retry_after`), `PERMANENT_ERROR`, `UNAUTHORIZED`, `NOT_FOUND`.

## Platform & Features (ADR-0059, ADR-0078)

- Feature interactions in `packages/<feature>/interactions/`. Multi-platform via hookspecs.
- Per-platform concrete services (no unified Protocol). Infrastructure-owned, settings-driven.

## Background Jobs (ADR-0058)

Colocated in-process. Pluggy `register_background_job` hookspec. Production-only (`PREFIX == ""`). Tier 1 (idempotent) vs Tier 2 (DynamoDB lock). `safe_run()` error isolation.

## Security (ADR-0064) & Identity (ADR-0061)

- JWT via `get_current_user` dependency. Defense-in-depth: WAF/ALB + SlowAPI. 429 with `Retry-After`.
- Identity resolution: JWT > Platform > Webhook > System. IdentityService is Category A.

## Logging (ADR-0054)

Structured `structlog.contextvars` middleware. No credentials/PII in logs. Unbuffered stdout/stderr.

## Testing (ADR-0062)

- `app/tests/` with `unit/` and `integration/`. Names: `test_<feature>_<entity>_<what>.py`.
- `app.dependency_overrides` with `finally` clear. Protocol-conformant stubs. Narrow-slice fixtures.
- Clear `@lru_cache` between tests. Cover success, failure mapping, and dependency variation paths.

## Working Modes

**Architecture** — when requirements are unclear or introducing patterns. Architect first, cite ADRs, define acceptance criteria before coding.

**Implementation** — when architecture is clear. TDD: failing tests → implement → green. Run quality gates every 3-5 edits.

## Quality Gates

Run regularly and before completion: `mypy`, `flake8`, `black --check .`, `pytest app/tests --ignore=app/tests/smoke`. Fix root causes before proceeding. No smoke tests unless explicitly requested.

## Generation Rules

Explicit imports, typed interfaces, structured logging, async I/O, centralized settings, ADR-0060 error mapping.

## Guardrails

- No git commands unless explicitly requested. User controls git.
- No file modifications unless explicitly asked, or the file is in `docs/decisions/`.
