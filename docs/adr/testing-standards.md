---
title: "Testing Standards"
status: Accepted
type: Standard
tier: Tier-2
governance_domain: [application]
concerns: [testing, architecture]
constrained_by: [layered-architecture.md, dependency-injection.md, configuration-ownership.md, type-boundaries.md, feature-handler-standard.md, infrastructure-service-classification.md, package-management.md, code-quality-tooling.md, application-lifecycle.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Testing Standards

## Context and Problem Statement

The codebase produces typed Python code with strict architectural rules — three-position layers, Protocol-based contracts, per-domain settings, plugin-based features, an `OperationResult` envelope at integration boundaries, a stateless lifespan with fail-fast boot. Each of those rules has a corresponding test surface: a unit can be verified in isolation against its Protocol-typed collaborators; a feature service can be verified against substituted infrastructure Protocols; a route can be verified end-to-end against a `TestClient` with provider overrides; a startup sequence can be verified by exercising the lifespan.

Without a single shared standard for those tests, every feature reinvents test layering, fixture conventions, and substitution mechanics; reviewers spend cycles judging whether a given test is the right shape; coverage drifts; CI feedback grows long and unreliable.

The problem this record addresses: **what is the canonical structure, mechanics, and discipline for the application's test suite — test layering, directory layout, fixtures, dependency overrides, test doubles, coverage, CI gates, and per-test performance budgets?** The answer determines:

1. Whether a contributor adding a test reads one record and writes a test that fits, or judges shape per case.
2. Whether the test suite holds the architectural invariants (layered imports, Protocol contracts, OperationResult shape) accountable, or whether tests drift to ad-hoc verification.
3. Whether CI feedback is fast (minutes) and trustworthy (no flaky tests, no soft-fail) or slow and noisy.
4. Whether legacy tests (predating the corpus's accepted records) and new tests live alongside cleanly during migration.

**Constraints:**

- Test substitution mechanics are already partly specified by other accepted records: `dependency-injection.md` (Protocol-conformant doubles substituted via `app.dependency_overrides` for HTTP consumers; `cache_clear()` for direct-call providers), `configuration-ownership.md` (settings overrides through providers, never bypassing the provider). This record builds on those, not over them.
- The application is asynchronous (FastAPI on Uvicorn); the test runner must support `async`/`await` natively in tests and fixtures.
- Tests must be deterministic. Tests that depend on real-world time, network, or external services either substitute Protocol-conformant in-process implementations or are explicitly excluded from default CI runs.
- The CI pipeline is a single `uv run pre-commit run --all-files` step plus a separate test job (per `code-quality-tooling.md`); the test job is a required check on protected branches. The total CI feedback time is bounded by what fits in a developer's flow — minutes, not tens of minutes.
- Configuration in this codebase is `pyproject.toml`-centric per `package-management.md`; pytest configuration lives there or in a sidecar file, with the corpus preferring `pyproject.toml`.

**Non-goals:**

- This record does not pick a specific test-data factory library (e.g., `factory_boy`, `polyfactory`). It establishes the factory-as-fixture pattern; the library, if any, is a follow-on choice.
- This record does not define load testing, performance benchmarks, or visual regression. Those are separate concerns.
- This record does not redefine what counts as a unit (a function, a class, a module) — that is a per-test judgement; the layering this record establishes is about *test cost*, not about the unit-of-software taxonomy.
- This record does not define the security-testing posture (SAST is owned by `code-quality-tooling.md`; runtime security testing, fuzzing, dependency-vulnerability scanning are separate concerns).
- This record does not define the migration timeline for existing legacy tests; it pins the target structure and the discipline going forward.

## Considered Options

**Option 1 — Free-form tests; reviewers verify quality per case.** No prescribed layering, fixtures, or mechanics; each contributor writes tests in whichever style. Familiar in early-stage codebases; vulnerable to drift; reviewers spend cycles re-deriving the shape rule for every PR.

**Option 2 — Three-layer test pyramid with explicit substitution mechanics.** Unit / Integration / Smoke layers, each with explicit cost budgets and substitution rules. Layering is enforced through directory placement and pytest markers; substitution mechanics are inherited from `dependency-injection.md` and `configuration-ownership.md`. Fixtures use a hierarchical `conftest.py` plus factory-as-fixture pattern. Coverage is path-specific with a steady-state target. CI runs unit + integration as a required check; smoke runs separately.

**Option 3 — Single-layer integration-only suite.** Every test exercises the full FastAPI `TestClient` against routes; no unit-level isolation. Conceptually simple; produces slow CI feedback as the application grows; couples tests to transport-level shapes that change for non-business reasons.

**Option 4 — Property-based testing as the primary mode.** Use `hypothesis` to generate cases. Powerful for code that operates on data structures; high friction for HTTP routes and feature workflows; not the primary fit for an application of this shape.

## Decision Outcome

**Chosen: Option 2 — three-layer test pyramid with explicit substitution mechanics.**

The application's test suite is layered into three categories that differ in scope, cost, and what they substitute. Each test belongs to exactly one layer, and the layer is determined by what the test exercises — not by what the test author intends.

### Test runner: `pytest`

`pytest` is the project's test runner. The configuration lives under `[tool.pytest.ini_options]` in `pyproject.toml` (preferred) or in `pytest.ini` if a sidecar is operationally needed. Async support is provided by `pytest-asyncio` with `asyncio_mode = "auto"` so that `async def test_…` functions are run as coroutines without per-test decoration.

Test plugins beyond `pytest-asyncio`:

- `pytest-cov` for coverage measurement (delegating to `coverage.py`).
- `pytest-mock` for the `mocker` fixture wrapping `unittest.mock`.
- `httpx` (already a runtime dependency) for `httpx.AsyncClient` against FastAPI's `app` via `ASGITransport`.

Plugins beyond this set are added through normal review when a need surfaces.

### The three layers

| Layer | What it tests | Cost budget | What it substitutes |
| --- | --- | --- | --- |
| **Unit** | One unit (function, class, module) in isolation against its declared collaborators. | < 50 ms per test (steady state). | Protocol-conformant in-process fakes for collaborators; `MagicMock` for narrow internal collaborators that have no Protocol contract. |
| **Integration** | A stack of units composed in-process — typically a feature's service plus the infrastructure Protocols it consumes, exercised via FastAPI `TestClient` (HTTP) or via direct service calls (non-HTTP). | < 500 ms per test (steady state). | Protocol-conformant in-process fakes for **out-of-process** dependencies (databases, vendor SDKs, external HTTP). The application's own internal composition is **real**. |
| **Smoke** | The application against **real** external systems (a live Slack workspace, a real DynamoDB table, etc.). Asserts the integration is healthy in a target environment. | Bounded by the live system; not a per-test budget but a pre-merge guard that runs only on demand. | Nothing — this is the layer where substitution stops. |

The three layers form a pyramid: **most tests are unit; some are integration; very few are smoke**. The pyramid shape is enforced at review (a feature whose tests are mostly integration is a smell) and at CI cost (integration tests have a per-test budget that prevents accumulation).

**Default CI runs unit + integration.** Smoke is excluded from default runs (kept under `tests/smoke/` and gated by `--smoke` or a marker filter); smoke is run on demand against a target environment, before a release, or as a scheduled job.

### Directory layout

The `tests/` tree mirrors the `app/` tree, prefixed by the layer:

```text
tests/
  unit/
    clients/<vendor>/test_<module>.py
    infrastructure/<service>/test_<module>.py
    packages/<feature>/test_<module>.py
    server/test_<module>.py
  integration/
    infrastructure/<service>/test_<module>.py
    packages/<feature>/test_<module>.py
    server/test_<module>.py
  smoke/
    <feature>/test_<scenario>.py
  factories/
    <domain>.py
  conftest.py
```

Each test file under `tests/unit/<path>` corresponds to a source file under `app/<path>`. The mirror is the convention; reviewers verify it is honoured for new tests.

The legacy directories that predate this layout (`tests/modules/`, `tests/integrations/`, `tests/api/`, `tests/core/`) coexist during migration. Tests in those directories are marked `legacy` and migrate to `unit/` or `integration/` opportunistically (when touched) plus a planned cleanup pass; no hard deadline. New tests are not added to the legacy directories.

### Fixtures: hierarchical `conftest.py` plus factory-as-fixture

- A **root `tests/conftest.py`** holds fixtures used everywhere: clean-context fixtures (clear `contextvars`, clear all `@lru_cache` providers, suppress log output during tests), plus a small set of repeatedly-used helpers.
- **Per-feature or per-service `conftest.py`** files hold fixtures specific to that scope. Pytest's hierarchical `conftest` discovery means tests under `tests/unit/packages/access/` automatically see fixtures from `tests/unit/packages/access/conftest.py` plus `tests/conftest.py`.
- **Factory functions** live in `tests/factories/<domain>.py`. Each factory is a callable: `google_user(name="...", email="...")` returns a fresh fully-shaped Pydantic value. Factories accept overrides for the fields a particular test cares about; defaults are reasonable.
- **Factory-as-fixture pattern** wraps factories in fixtures when convenient: a `google_user_factory` fixture that returns the bare callable so tests can call it many times within a single test. This is preferred over fixtures that return pre-built values, because callers parameterize each call.

Autouse fixtures are reserved for true cross-cutting concerns (clearing `contextvars`, clearing caches, suppressing log output). Avoid autouse fixtures that influence test outcomes; tests should be honest about their setup.

### Dependency overrides and provider substitution

The substitution rules are inherited from `dependency-injection.md` and `configuration-ownership.md`; this record reaffirms them and pins the test-side discipline:

- **HTTP route consumers:** the test registers `app.dependency_overrides[provider] = lambda: <substitute>` before the `TestClient` request and clears it afterwards (a fixture's teardown). The `<substitute>` is a Protocol-conformant fake or a callable returning one.
- **Non-HTTP consumers** (background loops, hookimpls, startup code, direct service calls): the test calls `provider.cache_clear()` in setup, sets the relevant env vars (typically via `monkeypatch.setenv`), and calls the provider — which constructs the (substituted or real) instance against the test environment.
- **Tests do not bypass providers.** Constructing a `BaseSettings` subclass directly is reserved for tests that *exercise the parsing behavior of that class*; tests that exercise domain logic always go through the provider so the production injection path is what is tested.
- **A shared autouse fixture clears all registered providers in setup.** Forgetting to clear is a known footgun; the autouse fixture removes it.

### Test doubles

The application uses three kinds of test doubles, in this order of preference:

| Kind | When to use | Example |
| --- | --- | --- |
| **Protocol-conformant fake** | The collaborator is a Path A or Path B service with a Protocol contract per `infrastructure-service-classification.md`. The fake is an in-memory implementation of the Protocol with deterministic behavior. | A `FakeStorageService` that holds a dict of objects and returns them. |
| **Pre-built stub** | The collaborator is a narrow value provider (e.g., a settings instance, a stable read-only data source). The stub is a small object or callable returning canned values. | A factory that returns a stub `SlackUser` for `lookup_user_by_email`. |
| **`MagicMock`** | The collaborator has no Protocol contract and the test is asserting on call shape (a behavior verification per the test-doubles taxonomy). Used sparingly and only for internal collaborators. | A `MagicMock` settings object when a test asserts a setting was read. |

Tests **do not mock the SDK directly** (`slack_sdk.WebClient`, `boto3.client`). Substitution happens at the Protocol boundary (`SlackService`, `StorageService`); the SDK is reached only through the concrete adapter, which is unit-tested separately in adapter-specific tests using vendor-supplied test mocks (e.g., `moto` for AWS) or by mocking the SDK at that adapter's seam.

Tests **do not mock the code under test**. Mocks substitute *collaborators* of the code under test; mocking the system under test trivially passes the test and verifies nothing.

### Mocking external HTTP

For integration tests that exercise outbound HTTP through an adapter, the SDK call is allowed to reach an HTTP-mocking layer rather than the real network. The recommended primitives:

- `respx` or `pytest-httpx` for substituting `httpx` responses (the canonical async HTTP client used by the application's adapters).
- `moto` for AWS service substitution where the SDK in question is `boto3` and the operations require server-side semantics that pure stubs cannot reproduce.

These are integration-level tools; they are not used in unit tests, where Protocol-conformant fakes substitute at a higher level.

### FastAPI integration tests

Integration tests that exercise routes use `httpx.AsyncClient` against the FastAPI `app` via `httpx.ASGITransport(app=app)`. This pattern is async-native and works seamlessly with `pytest-asyncio`'s auto mode. The legacy `fastapi.testclient.TestClient` (sync) is acceptable but not preferred for new tests.

A typical route integration test:

1. Builds the `app` (a fixture) — exercising the lifespan briefly, with overrides applied for slow phases.
2. Registers `app.dependency_overrides` for any provider the test substitutes.
3. Makes a request through `httpx.AsyncClient(transport=ASGITransport(app=app))`.
4. Asserts the response status, body shape, and any side effects on substituted Protocol fakes.

### Lifespan and boot-time tests

The application lifespan (per `application-lifecycle.md`) is itself testable. A boot-failure test asserts that a misconfigured `BaseSettings` causes the lifespan to raise *before* `yield`. A registry-frozen test asserts that no `register_*` hook is callable after the lifespan has yielded. These are integration-layer tests; they live under `tests/integration/server/`.

### Coverage

Coverage is measured via `pytest-cov` over a path list, not over `app/` as a whole, so accidental coverage of generated or vendor-fenced code does not skew the number. The path list mirrors the project's source positions: `app/clients`, `app/infrastructure`, `app/packages`, `app/server`. A `[tool.coverage.run]` section in `pyproject.toml` declares the source paths and the omit patterns (e.g., `__init__.py` re-export shims, generated code).

Coverage targets:

- **Per-PR steady-state target: 80% line coverage** across the path list. Falling below the target on a PR is a soft signal that prompts review; the threshold tightens over time as the codebase reaches steady state.
- **New code expected at 90% line coverage.** A PR adding 200 lines of code with 50 lines of tests is reviewed against this expectation.
- **Branch coverage is reported** but not gated initially. Branch targets may be adopted as a follow-on.
- **Per-module thresholds** (a stricter rule for a specific subdirectory, e.g., `app/infrastructure/idempotency/` at 95%) are added through normal review when a module's correctness is high-stakes.
- **Coverage is not a substitute for test quality.** Tests that touch a line without asserting on its outcome do not count as covering it. Reviewers verify that covered lines have meaningful assertions.

### CI gates and performance SLAs

- **Default CI test job runs `pytest` over `tests/unit/` and `tests/integration/`.** It is a required check on protected branches.
- **Smoke is excluded from default runs** (gated by a marker filter or directory exclusion) and is run on demand in a separate workflow against staging credentials.
- **Total CI test time budget: 10 minutes** for unit + integration. Tests that violate the per-test budget (a unit test taking 200 ms; an integration test taking 5 s) are flagged at review and either reclassified to a higher layer or refactored.
- **Soft-fail is not used.** A failing test fails the CI job. The legacy `|| true` anti-pattern is rejected per `code-quality-tooling.md`; the same rule applies to test execution.
- **Flaky tests are bug reports, not noise.** A test that fails intermittently is fixed or quarantined explicitly (with a tracked deadline for fix); flaky tests are not retried-until-green in CI.

### Test isolation

- Each test is independent. No test depends on the order of execution or on side effects from other tests.
- The autouse fixtures in `tests/conftest.py` clear `contextvars`, clear the `@lru_cache` providers registered with the test framework, and reset any module-level state the application sets at boot.
- Tests do not write to the host filesystem outside `tmp_path` (pytest's per-test temp directory).
- Tests do not start subprocesses or open network sockets unless explicitly required (which is itself a test smell — substitute at the Protocol boundary instead).

### Test categorization markers

Pytest markers are used as a *secondary* layer of categorization for cross-cutting concerns; they are not a replacement for directory placement:

- `@pytest.mark.smoke` — smoke tests; excluded from default runs.
- `@pytest.mark.slow` — tests that exceed the layer's per-test budget for principled reasons; flagged at review.
- `@pytest.mark.legacy` — tests in legacy directories during migration.

The marker registry is declared in `pyproject.toml`; unknown markers fail strict marker checking.

## Consequences

**Positive:**

- Every contributor knows where a test goes (directory mirrored to source; layer chosen by what the test exercises) and how to substitute production wiring (provider overrides per `dependency-injection.md` and `configuration-ownership.md`).
- The CI feedback loop is bounded: unit tests are fast; integration tests are bounded; smoke is opt-in. A passing CI run is a strong signal.
- Test doubles follow a small, clear preference order. Protocol-conformant fakes are the steady state; `MagicMock` is reserved for narrow cases. Mocks of the SDK are not the test discipline.
- Coverage is path-specific and reviewable per PR. The target evolves as the codebase reaches steady state.
- Legacy tests have a path forward (migration when touched) without forcing a big-bang rewrite.

**Tradeoffs accepted:**

- Three test layers and a directory mirror are more structure than the smallest possible test suite. The cost is a once-per-feature setup; the benefit is durable discipline.
- The 80% coverage steady-state target is intentionally below the often-quoted 100%. Tests that touch every line do not necessarily prove correctness; the budget allows for code that is genuinely better verified at the type-system or contract level.
- Smoke tests against real external systems are not part of default CI. The cost is that a Slack-wide outage may not be caught by a PR; the benefit is that PRs do not depend on third-party uptime.
- Async-native testing via `httpx.AsyncClient` differs from the FastAPI tutorial's default `TestClient`. The cost is a small learning curve; the benefit is consistency with the application's async runtime.

**Risks:**

- A test is placed in the wrong layer (unit-marked but exercising five collaborators; integration-marked but only a function under test). Mitigation: code review against the layer table; misplaced tests are reclassified.
- Coverage rises mechanically (touching lines without assertions) to meet the target. Mitigation: review verifies meaningful assertions on covered lines.
- A flaky test is added and accepted as "intermittent". Mitigation: the rule is "fix or quarantine with a deadline"; a flaky test that is not quarantined is a CI bug.
- Migration of legacy tests stalls. Mitigation: opportunistic-when-touched plus a planned cleanup pass; legacy tests do not block new work but are not extended.

## Confirmation

Compliance is verified by:

- **Repository contents.** `tests/` has `unit/`, `integration/`, `smoke/`, `factories/`, and a root `conftest.py`. New tests are placed under the layer that matches what they exercise. Pytest configuration lives in `pyproject.toml` under `[tool.pytest.ini_options]`.
- **CI pipeline.** A required CI job runs `pytest tests/unit tests/integration` with coverage reporting. Smoke tests run in a separate, manually-triggered workflow.
- **Code review.** A PR adding a test is reviewed against (1) layer placement (does the test's scope match the layer's substitution rules?), (2) directory mirror (does the test live at the path that mirrors the source?), (3) double choice (Protocol-conformant fake first; `MagicMock` only for narrow cases), (4) coverage delta (new code at ~90% steady state). PRs that mock the SDK directly without an adapter-level seam are revised.
- **Coverage.** The CI run reports per-path coverage. Per-PR drops below the steady-state target trigger review; per-module thresholds are checked when set.
- **Tests of test infrastructure.** The autouse fixtures themselves are tested (a meta-test that confirms `contextvars` are cleared between tests, `lru_cache` providers are cleared, etc.).

## Source References

1. pytest — Official Documentation
   - URL: <https://docs.pytest.org/en/stable/>
   - Accessed: 2026-05-08
   - Relevance: Documents `pytest` as the canonical Python test runner: hierarchical `conftest.py` discovery, fixture scopes, parametrization, marker registry, and `[tool.pytest.ini_options]` configuration via `pyproject.toml`. Grounds the test runner choice and the configuration location.

2. pytest-asyncio — Documentation
   - URL: <https://pytest-asyncio.readthedocs.io/en/latest/>
   - Accessed: 2026-05-08
   - Relevance: Documents the plugin that enables `async def` test functions and async fixtures in pytest. Establishes `asyncio_mode = "auto"` as the simplest configuration for an application whose code is async-by-default. Grounds the async-test-runner choice.

3. The Practical Test Pyramid — Martin Fowler
   - URL: <https://martinfowler.com/articles/practical-test-pyramid.html>
   - Accessed: 2026-05-08
   - Relevance: Establishes the test-pyramid principle: "Write *lots* of small and fast *unit tests*. Write *some* more coarse-grained tests and *very few* high-level tests that test your application from end to end." Grounds the three-layer model and the per-layer cost budgets.

4. Mocks Aren't Stubs — Martin Fowler
   - URL: <https://martinfowler.com/articles/mocksArentStubs.html>
   - Accessed: 2026-05-08
   - Relevance: Establishes the Meszaros taxonomy of test doubles (dummy, fake, stub, spy, mock) and the distinction between state verification (preferred) and behavior verification (used sparingly). Grounds the test-doubles preference order: Protocol-conformant fakes first, pre-built stubs second, `MagicMock` reserved for narrow cases.

5. FastAPI — Testing
   - URL: <https://fastapi.tiangolo.com/tutorial/testing/>
   - Accessed: 2026-05-08
   - Relevance: Documents FastAPI's `TestClient`, the `app.dependency_overrides` mechanism for substitution, and the pattern of testing routes against an in-process `app`. Grounds the dependency-overrides discipline for HTTP route consumers and the preference for `httpx.AsyncClient`-via-`ASGITransport` for async-native testing.

6. coverage.py — Documentation
   - URL: <https://coverage.readthedocs.io/en/latest/>
   - Accessed: 2026-05-08
   - Relevance: Documents `coverage.py`'s line and branch coverage measurement, the `[tool.coverage.run]` configuration in `pyproject.toml`, and the source/omit selection mechanism. Grounds the path-specific coverage target and the configuration location.

## Change Log

- 2026-05-08: Created. Establishes a three-layer test pyramid (unit, integration, smoke) with explicit cost budgets (< 50 ms / < 500 ms / unbounded-but-opt-in) and per-layer substitution rules. Pins `pytest` as the test runner with `pytest-asyncio`'s `asyncio_mode = "auto"` for async-by-default tests. Pins the directory layout: `tests/{unit,integration,smoke}/` mirroring `app/<path>/`, with shared factories in `tests/factories/` and hierarchical `conftest.py`. Pins the test-doubles preference (Protocol-conformant fake → pre-built stub → `MagicMock`), the rule that mocks substitute *collaborators* not the system under test, and the rule that the SDK is mocked at the adapter seam, never directly by feature tests. Pins integration testing on `httpx.AsyncClient` against FastAPI via `ASGITransport`. Pins coverage at a path-specific 80% steady-state target with new code at ~90%; branch coverage reported but not gated initially. Pins CI gates (unit + integration as a required check; smoke separate; soft-fail rejected). Pins per-test SLAs and the rule that flaky tests are bug reports, not retried-until-green. Pins migration discipline for legacy tests: opportunistic-when-touched plus a planned cleanup pass; new tests are not added to legacy directories.
