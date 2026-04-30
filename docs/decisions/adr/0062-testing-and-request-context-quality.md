---
adr_id: ADR-0062
title: "Testing and Request Context Quality"
status: Draft
decision_type: Standard
tier: Tier-2
primary_domain: Testing and Quality
secondary_domains:
  - Observability and Logging
  - Dependency and Composition
owners:
  - SRE Team
date_created: 2026-04-30
last_updated: 2026-04-30  # R1 revision: S7 auto-mode caveat, S10 sync/async caveat
last_reviewed: 2026-04-30
next_review_due: 2026-08-28
constrained_by:
  - ADR-0044
  - ADR-0045
  - ADR-0048
  - ADR-0065
impacts:
  - ADR-0055
  - ADR-0056
  - ADR-0077
supersedes:
  - ADR-0030
  - ADR-0031
superseded_by: []
review_state: current
related_records:
  - ADR-0049
  - ADR-0076
  - ADR-0078
related_packages:
  - app/packages/access
  - app/tests
---

# Testing and Request Context Quality

## Context

The platform's testing patterns and request-context propagation approach have matured organically across multiple ADR waves. ADR-0030 established initial testing location and naming conventions at Tier-3. ADR-0031 established `structlog.contextvars` for request-ID propagation at Tier-3. Since then, Wave 3 and Wave 4 ADRs introduced architectural constraints that directly govern how tests must be structured:

- **ADR-0045 Principle 2** mandates that the dependency graph must be "overridable for testing."
- **ADR-0048 Boundaries 2 and 7** require Protocol-typed injection surfaces — which dictates how test doubles are constructed.
- **ADR-0055** requires narrow settings slices — which dictates how test fixtures construct configuration.
- **ADR-0056** requires provider composition in `providers.py` — which dictates where test overrides target.
- **ADR-0065** establishes type-model boundaries — which dictates the typing of test stubs and mock objects.
- **ADR-0077** classifies services into Categories A/B/C — which dictates which services require Protocol-typed test doubles.

ADR-0030 and ADR-0031 predate this constraint framework. Their patterns remain correct but incomplete: they do not address Protocol-based test doubles, narrow-slice fixture construction, provider cache isolation, or the relationship between service classification and test stub design. This ADR supersedes both, consolidating testing standards and request-context quality into a single Tier-2 record that aligns with the current architectural stack.

The codebase is also pre-ADR — existing test patterns are ground truth, not violations. The `app/packages/access` test suite serves as the reference implementation for new-pattern conformance. The `app/tests/TESTING_STRATEGY.md` documents the migration path from legacy flat structure to the new `unit/`/`integration/` hierarchy.

---

## Decision

### Standard 1: Test Location and Directory Structure

All application tests reside in `app/tests/` with a hierarchical structure mirroring the application's layer separation (ADR-0045 Principle 3).

```
app/tests/
├── unit/                        # Isolated tests, no external dependencies
│   ├── infrastructure/          # Infrastructure-layer unit tests
│   ├── packages/                # Package-layer unit tests
│   │   └── <package>/           # One directory per package domain
│   ├── api/                     # API route handler tests
│   ├── modules/                 # Legacy module unit tests
│   └── server/                  # Server configuration tests
├── integration/                 # Tests combining multiple components
│   ├── infrastructure/
│   ├── packages/
│   ├── modules/
│   ├── server/
│   ├── webhooks/
│   └── jobs/
├── performance/                 # Performance benchmarks
├── resilience/                  # Resilience and fault-injection tests
├── security/                    # Security-focused tests
├── smoke/                       # Smoke tests (excluded from CI by default)
├── factories/                   # Shared test data factories
├── fixtures/                    # Shared fake client implementations
├── testdata/                    # Static test data files
└── conftest.py                  # Root-level fixtures
```

**Rules:**

- Tests must not exist outside `app/tests/`.
- The `unit/` and `integration/` directories are the canonical structure for new tests.
- Legacy test directories (`app/tests/modules/`, `app/tests/api/`, `app/tests/core/`, `app/tests/integrations/`) are maintained during migration but must not be used as the pattern for new tests.
- Shared fixtures, factories, and test data belong in their respective top-level directories (`factories/`, `fixtures/`, `testdata/`).
- Level-specific `conftest.py` files provide hierarchical fixture scoping.

### Standard 2: Test File Naming

Test files use feature-prefixed names that are self-documenting in isolation.

**Pattern:** `test_<feature>_<entity>_<what>.py`

**Examples:**

- `test_access_catalog_routes.py` — not `test_routes.py`
- `test_access_sync_service.py` — not `test_service.py`
- `test_identity_resolver.py` — not `test_resolver.py`
- `test_groups_orchestration.py` — not `test_orchestration.py`

**Rules:**

- Generic names (`test_routes.py`, `test_service.py`, `test_models.py`) are prohibited for new test files.
- The feature prefix must unambiguously identify the domain or package being tested.
- File naming enforcement is per-package — the access package enforces this via `test_access_test_file_naming.py`.

### Standard 3: Route Testing via Dependency Overrides

FastAPI route tests use `app.dependency_overrides` to replace provider functions at the injection surface (ADR-0048 Boundary 2).

**Canonical pattern:**

```python
from fastapi.testclient import TestClient
from server.main import app
from infrastructure.services import get_<service>, get_<service>_settings, get_current_user

def test_endpoint_returns_expected_result():
    stub_service = _StubService()
    stub_settings = _StubSettings(enabled=True)
    stub_user = _make_user(email="caller@example.com")

    app.dependency_overrides[get_<service>] = lambda: stub_service
    app.dependency_overrides[get_<service>_settings] = lambda: stub_settings
    app.dependency_overrides[get_current_user] = lambda: stub_user
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/endpoint")
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()
```

**Rules:**

- Override provider functions (from `infrastructure.services`), not concrete service classes.
- Always clear `dependency_overrides` in a `finally` block or autouse fixture.
- Route tests must cover both success and error-mapping paths.
- For routes that return structured responses, assert response body shape — not just status code.

### Standard 4: Protocol-Conformant Test Doubles

When a service has a Protocol contract (ADR-0077 Category A), test doubles must satisfy the Protocol's structural subtyping contract (ADR-0065 Principle 2).

**Rules:**

- Test stubs for Category A services (those with Protocol contracts) must implement all methods defined in the Protocol.
- Stubs may be minimal implementations (returning fixed values) but must satisfy the Protocol's type signature.
- `MagicMock()` is acceptable for Category B/C services (those without Protocol contracts) where duck typing suffices.
- Test doubles must not import or depend on the concrete implementation class.

### Standard 5: Narrow-Slice Fixture Construction

Test fixtures construct the narrowest settings slice needed by the code under test (ADR-0055, ADR-0056 Standard 1).

**Rules:**

- Tests needing AWS settings construct only `AwsSettings`, not the full `Settings` tree.
- Tests needing access settings construct only `AccessSyncSettings` or `AccessRequestSettings`, not the full settings object.
- Factory-as-fixture is the preferred pattern for configurable test data:

  ```python
  @pytest.fixture
  def make_sync_settings():
      def _make(**overrides):
          defaults = {"enabled": True, "job_ttl_seconds": 3600}
          defaults.update(overrides)
          return AccessSyncSettings(**defaults)
      return _make
  ```

- Sensible defaults with parameter overrides reduce test boilerplate without hiding test intent.

### Standard 6: Provider Cache Isolation

`@lru_cache` provider singletons (from `infrastructure/services/providers.py`) must be cleared between tests to prevent cross-test state leakage.

**Rules:**

- Package-level `conftest.py` files must include autouse fixtures that clear provider caches before and after each test.
- When `dependency_overrides` and `@lru_cache` providers are both in play, both must be cleared in the `finally` block.
- The access package's `conftest.py` is the reference implementation:
  - Strips all `ACCESS_*` environment variables.
  - Disables `.env` file reads for `AccessSettings`.
  - Clears access-specific provider caches between tests.

### Standard 7: Async Testing

Async route handlers and async services are tested with `pytest-asyncio` using `asyncio_mode = auto`.

> **Configuration dependency:** pytest-asyncio's default mode is `strict`, which requires an explicit `@pytest.mark.asyncio` on every async test. This project opts into `auto` mode via `app/pytest.ini` (`asyncio_mode = auto`, line 3). The `auto` setting auto-discovers coroutine test functions and applies the marker implicitly. If this configuration line is removed or if a future pytest-asyncio version changes `auto` mode semantics, async test functions will be collected but **not awaited** — the coroutine object evaluates as truthy, so tests appear to pass while executing nothing. The project pins `pytest-asyncio==0.26.0` in `requirements_dev.txt` to lock this behavior.

**Rules:**

- `asyncio_mode = auto` is configured in `app/pytest.ini` — explicit `@pytest.mark.asyncio` decorators are not required for coroutine test functions. This is an opt-in setting (default is `strict`); the exact configuration line is `asyncio_mode = auto` under the `[pytest]` section.
- Use `TestClient` for synchronous route handlers and simple integration tests.
- Use `httpx.AsyncClient` with `asgi-lifespan.LifespanManager` for async routes that exercise `contextvars` propagation, cancellation, or task groups.
- Background tasks spawned via `asyncio.create_task()` must be tested with the async client to verify correct `contextvars` isolation.

### Standard 8: Mocking Preferences

**Rules:**

- Prefer `monkeypatch` (pytest fixture) over `unittest.mock.patch` for new tests.
- `monkeypatch.setenv()` for environment variable overrides.
- `monkeypatch.setattr()` for attribute/function replacement.
- `@patch` decorators remain acceptable in legacy tests but should be migrated to `monkeypatch` when files are actively modified.
- No manual cleanup is needed with `monkeypatch` — it reverts automatically after each test.

### Standard 9: Test Markers

Tests use pytest markers for categorization and selective execution.

**Defined markers (in `app/pytest.ini`):**

- `@pytest.mark.unit` — Pure unit tests with no external dependencies.
- `@pytest.mark.integration` — Tests combining multiple components at system boundaries.
- `@pytest.mark.legacy` — Legacy test structure maintained during migration.
- `@pytest.mark.asyncio` — Async tests (auto-applied when `asyncio_mode = auto`).

**Rules:**

- New tests in `unit/` should use `@pytest.mark.unit`.
- New tests in `integration/` should use `@pytest.mark.integration`.
- Smoke tests in `smoke/` are excluded from default CI runs and require explicit invocation with configured environment variables.

### Standard 10: Request Context Propagation via structlog.contextvars

Request context (correlation ID, user identity, request metadata) propagates through `structlog.contextvars` — not through explicit function parameters (ADR-0031 replacement).

**Architecture:**

1. **Middleware binds context** at the ASGI boundary using `bind_request_context()` from `infrastructure.logging`.
2. **Service logic reads context** via `structlog.contextvars.get_contextvars()` when needed (e.g., for correlation headers to external APIs).
3. **Log processors merge context** via `structlog.contextvars.merge_contextvars` in the processor chain — all log events in the request scope automatically include bound context fields.
4. **Background tasks re-bind** explicitly — `contextvars` do not propagate across `asyncio.create_task()` boundaries.

**Context fields:**

- `correlation_id` — Generated `uuid4()` or forwarded from `X-Request-ID` / `X-Correlation-ID` header.
- `user_email` — Authenticated user identity (when available).
- `request_path` — HTTP request path.
- `request_method` — HTTP request method.

**Rules:**

- Do not pass `request_id` or `correlation_id` as a function argument through service layers — use `structlog.contextvars`.
- Do not bind context at module scope — context is per-request.
- Call `clear_contextvars()` at the start of each request (middleware responsibility).
- Re-bind context explicitly in background tasks and scheduled jobs.
- Honour incoming `X-Request-ID` or `X-Correlation-ID` headers for end-to-end traceability.

> **Sync/async isolation caveat:** structlog documents that in Starlette/FastAPI applications, context variables set in a synchronous execution context are **not visible** in an asynchronous context and vice versa. This is a Python `contextvars` behavior in the Starlette threading model — when a `def` (sync) route handler runs in a thread pool, it receives a *copy* of the context, and mutations do not propagate back to the async context (or to other sync handlers). **Mitigations:**
>
> 1. **Prefer `async def` route handlers** so that middleware and handler share the same async context.
> 2. If sync handlers are required, ensure the middleware binds context **before** Starlette dispatches to the thread pool — context variables *inherited* at thread-pool dispatch time are visible in the sync handler, but variables *bound inside* the sync handler are not visible to async code after the handler returns.
> 3. When testing sync/async boundary behavior, use `httpx.AsyncClient` (not `TestClient`) to exercise the real ASGI dispatch path and verify context propagation end-to-end.

### Standard 11: Log Suppression in Tests

Test execution suppresses structured log output to keep test output clean and focused on assertions.

**Rules:**

- The root `conftest.py` provides an autouse `suppress_structlog_output` fixture.
- Test environment detection via `"pytest" in sys.modules` disables production log output.
- Tests that need to assert log content should use `structlog.testing.capture_logs()` or equivalent capture mechanisms.

### Standard 12: Integration Test Boundary Mocking

Integration tests mock at system boundaries — not at internal service boundaries.

**Rules:**

- Autouse fixtures in `integration/conftest.py` mock external system boundaries (DynamoDB, Sentinel, external APIs).
- Internal service composition remains real — integration tests verify that components work together correctly.
- System boundary mocks are provided via the `fixtures/` directory (e.g., `aws_clients.py`, `google_clients.py`).

---

## Alternatives Considered

### Alternative 1: Tests Outside `app/`

Place tests in a top-level `tests/` directory alongside `app/`.

**Rejected because:** Would require `PYTHONPATH` or `--import-mode` configuration changes. Current infrastructure (`pytest.ini`, `conftest.py`, CI) assumes `app/tests/`. Migration risk exceeds benefit.

### Alternative 2: No Feature-Prefix Naming Requirement

Allow generic test file names like `test_routes.py` within feature directories.

**Rejected because:** Generic names are ambiguous in pytest output, editor search results, and tracebacks. Feature-prefixed names are self-documenting when viewed in isolation. The codebase already adopted this convention in the access package.

### Alternative 3: Explicit request_id Parameter Threading

Pass `request_id` through every service function signature.

**Rejected because:** This approach is verbose, breaks down in background tasks, and couples every service signature to an operational concern. `structlog.contextvars` provides the same traceability with zero signature pollution. ADR-0031 already established this conclusion.

### Alternative 4: unittest.mock.patch as Primary Mocking

Standardize on `@patch` decorators for all mocking.

**Rejected because:** `monkeypatch` provides automatic cleanup without `finally` blocks, integrates with pytest's fixture lifecycle, and avoids decorator-stacking complexity. New tests should prefer `monkeypatch`; legacy `@patch` usage is accepted during migration.

---

## Consequences

### Positive

- Test structure mirrors application layer separation, making test location predictable.
- Feature-prefixed names eliminate ambiguity in large codebases.
- Protocol-conformant test doubles catch interface drift at test time.
- Narrow-slice fixtures prevent tests from depending on unrelated configuration.
- Provider cache isolation prevents cross-test contamination.
- `structlog.contextvars` for request context eliminates parameter-threading boilerplate while maintaining full traceability.
- Log suppression keeps test output focused on failures.

### Tradeoffs Accepted

- Hybrid directory structure (legacy + new) persists during migration. New code must use the new structure; legacy code is migrated opportunistically.
- Feature-prefix naming adds verbosity to file names. This is accepted for the disambiguation benefit.
- Provider cache clearing requires maintenance of `conftest.py` autouse fixtures as new providers are added.

### Risks and Mitigations

- **Risk:** New providers added without corresponding cache-clearing fixtures, causing intermittent test failures.
  - **Mitigation:** The access package `conftest.py` serves as the reference; code review should verify cache isolation for new packages.
- **Risk:** Legacy tests not migrated to new patterns, creating inconsistent patterns.
  - **Mitigation:** Forward compliance only. `@pytest.mark.legacy` tracks migration progress. Legacy patterns are not retroactively non-compliant.

---

## Compliance

### Constraining ADR Alignment

| Constraining ADR | Relevant Constraint | This ADR's Response |
|-----------------|---------------------|---------------------|
| ADR-0044 | Governance metadata contract | Full metadata, 120-day review cycle |
| ADR-0045 P2 | DI must be overridable for testing | Standard 3: `dependency_overrides` as canonical pattern |
| ADR-0045 P3 | Strict layer separation | Standard 1: Test directory mirrors application layers |
| ADR-0048 B2 | Single injection surface | Standard 3: Override provider functions, not concrete classes |
| ADR-0048 B7 | Protocol contract surface | Standard 4: Test doubles satisfy Protocol contracts |
| ADR-0055 | Narrow settings slices | Standard 5: Narrow-slice fixture construction |
| ADR-0056 S1 | Provider composition in providers.py | Standard 6: Provider cache isolation |
| ADR-0065 P2 | Protocol for behavioral contracts | Standard 4: Protocol-conformant test doubles |
| ADR-0065 P3 | Frozen dataclass for internal data | Test stubs for internal data use frozen dataclass |
| ADR-0065 P4 | Pydantic at trust boundaries only | Route test request/response bodies use Pydantic schemas |
| ADR-0077 | Service classification A/B/C | Standard 4: Category A requires Protocol stubs |

### Supersession

| Superseded ADR | What is Inherited | What Changes |
|---------------|-------------------|--------------|
| ADR-0030 (Testing Standards) | Test location in `app/tests/`, feature-prefix naming, `dependency_overrides` pattern, factory fixtures, `monkeypatch` preference, `lru_cache` teardown, async testing | Elevated to Tier-2. Added Protocol-conformant doubles (S4), narrow-slice fixtures (S5), provider cache isolation (S6), test marker conventions (S9), integration boundary mocking (S12). Structured as standards rather than code-example recipes. |
| ADR-0031 (Request ID Propagation) | `structlog.contextvars` for context binding, middleware binding pattern, background task re-binding | Elevated to Tier-2. Integrated as Standard 10 within the unified testing-and-quality ADR. Added `correlation_id` naming (replacing `request_id`), context field enumeration, and explicit rules for header forwarding. |

**Supersession Actions:**

- ADR-0030: Set `status: Superseded`, `superseded_by: [ADR-0062]`. Move to `adr/superseded/`.
- ADR-0031: Set `status: Superseded`, `superseded_by: [ADR-0062]`. Move to `adr/superseded/`.

---

## Current State Assessment

The codebase is pre-ADR — existing patterns are ground truth, not violations. This ADR codifies conventions that emerged organically, particularly in the access package.

| Standard | Current Conformance | Reference Implementation |
|----------|-------------------|-------------------------|
| S1: Test Location | ✅ All tests in `app/tests/`. Hybrid legacy/new structure. | `app/tests/unit/packages/access/` |
| S2: Feature-Prefix Naming | ✅ Enforced in access package. Partially adopted elsewhere. | `test_access_catalog_routes.py` |
| S3: Route Testing | ✅ `dependency_overrides` used throughout. | `test_access_catalog_routes.py` |
| S4: Protocol Doubles | ✅ Access package uses Protocol-typed stubs. Legacy uses `MagicMock`. | `AccessRequestServicePort` stubs |
| S5: Narrow-Slice Fixtures | ✅ Access package constructs narrow settings. Legacy uses full `Settings`. | `make_sync_settings` fixture |
| S6: Cache Isolation | ✅ Access package clears caches. Groups module resets provider registries. | `conftest.py` autouse fixtures |
| S7: Async Testing | ✅ `pytest-asyncio` with `asyncio_mode = auto`. | Rate-limit and webhook tests |
| S8: Mocking Preferences | ⚠️ Mixed `monkeypatch` and `@patch`. New tests prefer `monkeypatch`. | Access package tests |
| S9: Test Markers | ⚠️ Markers defined but not consistently applied. | `pytest.ini` marker definitions |
| S10: Request Context | ✅ `structlog.contextvars` infrastructure ready. Middleware not yet integrated. | `infrastructure/logging/context.py` |
| S11: Log Suppression | ✅ Autouse fixture in root `conftest.py`. | `suppress_structlog_output` |
| S12: Integration Boundaries | ✅ System boundary mocks in `integration/conftest.py`. | Integration conftest autouse fixtures |

---

## Best-Practice Revalidation

| Source | Claim or Guidance | Alignment |
|--------|-------------------|-----------|
| pytest 9.x documentation | Tests inside application package with simple imports | ✅ `app/tests/` with `pythonpath = app` in root `pytest.ini` |
| pytest fixture best practices | Factory-as-fixture pattern for configurable test data | ✅ Standard 5 codifies factory-as-fixture |
| FastAPI testing documentation | `TestClient` with `dependency_overrides` for route testing | ✅ Standard 3 codifies this pattern |
| structlog documentation | `contextvars` for per-request structured logging context; sync/async isolation caveat | ✅ Standard 10 codifies `structlog.contextvars` binding with sync/async caveat |
| PEP 544 | Protocol for structural subtyping | ✅ Standard 4 requires Protocol-conformant test doubles |
| Python typing best practices | Test doubles should satisfy the same interface contract | ✅ Standard 4 aligns test doubles with ADR-0077 categories |
| Twelve-Factor App (Factor X: Dev/prod parity) | Keep development, staging, production as similar as possible | ✅ Standards 6, 12 ensure test isolation without diverging from production behavior |

---

## Source References

1. **pytest documentation** — Test layout, fixtures, markers, monkeypatch: <https://docs.pytest.org/en/stable/>
2. **FastAPI testing** — TestClient, dependency overrides: <https://fastapi.tiangolo.com/tutorial/testing/>
3. **structlog documentation** — contextvars, testing, processor chain: <https://www.structlog.org/en/stable/>
4. **PEP 544** — Protocol structural subtyping: <https://peps.python.org/pep-0544/>
5. **pytest-asyncio** — Async test patterns, asyncio_mode: <https://pytest-asyncio.readthedocs.io/>
6. **Twelve-Factor App** — Dev/prod parity (Factor X): <https://12factor.net/dev-prod-parity>

---

## Migration

### Forward Compliance

Non-conforming existing tests are not retroactively non-compliant. These standards apply to:

- All new test files.
- Existing test files when actively modified (opportunistic alignment).

### Migration Path

The migration from legacy flat structure to `unit/`/`integration/` hierarchy is documented in `app/tests/TESTING_STRATEGY.md`:

1. Mark legacy tests with `@pytest.mark.legacy`.
2. Copy to new location, update imports and markers.
3. Verify identical behavior.
4. Remove legacy file after CI passes.

### Supersession Queue

| Legacy ADR | Action | When |
|-----------|--------|------|
| ADR-0030 | `status: Superseded`, `superseded_by: [ADR-0062]`, move to `adr/superseded/` | Wave 5 gate close |
| ADR-0031 | `status: Superseded`, `superseded_by: [ADR-0062]`, move to `adr/superseded/` | Wave 5 gate close |
