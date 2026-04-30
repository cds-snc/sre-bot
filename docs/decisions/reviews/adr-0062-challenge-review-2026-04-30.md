# ADR Challenge and Content Review — ADR-0062

**Purpose:** Round 1 challenge review of ADR-0062 (Testing and Request Context Quality) per Step 9.5 gate.

---

## 1. Review Metadata

| Field | Value |
|-------|-------|
| **ADR Under Review** | ADR-0062: Testing and Request Context Quality |
| **Reviewer Name & Title** | AI Architecture Reviewer, SRE Team |
| **Secondary Reviewers** | — |
| **Review Date** | 2026-04-30 |
| **Revalidation Due** | 2027-04-30 |
| **Gate Outcome** | ✅ **ACCEPT** (revised from ⚪ REVISE) |
| **Outcome Rationale** | Original R1 identified two blockers. Both resolved in same-day revision: (1) Standard 7 now documents that `asyncio_mode = auto` is opt-in (default `strict`), references exact `pytest.ini` line, and notes pinned `pytest-asyncio==0.26.0`; (2) Standard 10 now includes the structlog-documented sync/async contextvars isolation caveat with three specific mitigations. |
| **Revision Applied** | 2026-04-30 — same-day R1 revision addressing both blockers |

---

## 2. Evidence Gathering & Convention Validation

### 2.A Language & Framework Standards

**Applicable Standards (checked):**

- ✅ Pytest Documentation (<https://docs.pytest.org/en/stable/\>\) — test layout, fixtures, conftest, monkeypatch, markers, factory-as-fixture
- ✅ pytest-asyncio Documentation (<https://pytest-asyncio.readthedocs.io/en/latest/\>\) — async test modes, discovery
- ✅ FastAPI Testing Documentation (<https://fastapi.tiangolo.com/tutorial/testing/\>\) — TestClient
- ✅ FastAPI Testing Dependencies (<https://fastapi.tiangolo.com/advanced/testing-dependencies/\>\) — dependency_overrides
- ✅ Structlog Testing Documentation (<https://www.structlog.org/en/stable/testing.html\>\) — capture_logs, LogCapture fixture
- ✅ Structlog Context Variables (<https://www.structlog.org/en/stable/contextvars.html\>\) — merge_contextvars, clear_contextvars, sync/async caveat
- ✅ PEP 544 — Protocol structural subtyping
- ✅ Python Typing Module — structural subtyping for test doubles
- ✅ Mypy Documentation (<https://mypy.readthedocs.io/en/stable/\>\) — static type checking of test doubles
- ⚪ Black Documentation — not directly relevant to ADR content
- ⚪ Flake8 Documentation — not directly relevant to ADR content

**Search & Findings:**

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| pytest: Good Practices — test layout | "Choosing a test layout" | pytest supports tests-outside-app and tests-inside-app layouts. Both require `pythonpath` or editable install. `importlib` import mode recommended for new projects. | ✅ Aligned | ADR uses tests-inside-app (`app/tests/`) with `pythonpath = app` in root `pytest.ini`. Matches pytest guidance. |
| pytest: Fixtures — conftest.py scoping | "conftest.py fixture sharing, hierarchical scoping" | conftest.py files at each directory level provide fixture scoping. Autouse fixtures execute for all tests in scope. | ✅ Aligned | Standards 6, 11, 12 correctly use hierarchical conftest with autouse fixtures for cache clearing and log suppression. |
| pytest: Factory as fixture | "Factories as fixtures" | pytest docs explicitly recommend factory-as-fixture: fixture returns a callable that generates data with parameters. | ✅ Aligned | Standard 5 codifies factory-as-fixture with `make_sync_settings` example. Direct match to pytest guidance. |
| pytest: Monkeypatch | "monkeypatch setattr setenv" | `monkeypatch` provides `setattr`, `setenv`, `delenv` with automatic cleanup. No manual teardown needed. Can be shared via fixtures. | ✅ Aligned | Standard 8 preference for `monkeypatch` over `@patch` matches pytest best practice. |
| pytest-asyncio: Discovery modes | "asyncio_mode strict auto" | Default mode is **strict** (requires explicit `@pytest.mark.asyncio`). Auto mode auto-detects coroutine test functions. Must be explicitly configured. | ⚠️ Deviation | Standard 7 states "`asyncio_mode = auto` is configured in `app/pytest.ini`" — correct given the config, but the ADR should note auto is opt-in (not default) and reference the exact config line. See Assumption 3.3. |
| FastAPI: TestClient | "TestClient, httpx, testing" | TestClient wraps httpx for sync testing. For async testing, use `httpx.AsyncClient`. | ✅ Aligned | Standard 3 uses TestClient correctly. Standard 7 correctly distinguishes TestClient (sync) vs AsyncClient (async). |
| FastAPI: dependency_overrides | "app.dependency_overrides, override dependencies" | `app.dependency_overrides[original] = override` replaces dependencies. Reset with `.clear()`. | ✅ Aligned | Standard 3 uses `dependency_overrides` exactly as documented. `finally` block cleanup matches FastAPI guidance. |
| structlog: capture_logs | "capture_logs, LogCapture, testing" | `capture_logs()` context manager captures log output. All processors disabled inside. `LogCapture` usable as pytest fixture. Caveat: `cache_logger_on_first_use` cached loggers not affected. | ✅ Aligned | Standard 11 uses autouse fixture for log suppression. Matches structlog testing guidance. |
| structlog: contextvars sync/async caveat | "contextvars set in synchronous context don't appear in async context" | structlog docs explicitly warn: "context variables set in a synchronous context don't appear in logs from an async context and vice versa" for Starlette/FastAPI apps. | ⚠️ Deviation | Standard 10 does not mention this caveat. Since FastAPI is Starlette-based (sync def + async def), this is directly relevant. See Assumption 3.4. |
| PEP 544: Protocol structural subtyping | "Protocol, structural subtyping" | Protocol classes define structural interfaces. mypy verifies conformance statically. | ✅ Aligned | Standard 4 correctly requires Protocol-conformant test doubles for Category A services. |

---

### 2.B Infrastructure & Operational Standards

**Applicable Standards (checked):**

- ✅ Twelve-Factor App, Factor X (Dev/prod parity)

**Search & Findings:**

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| Twelve-Factor Factor X | "Dev/prod parity" | Keep dev, staging, production similar. Backing services same type. Test environments should not diverge from production behavior. | ✅ Aligned | Standard 12 (mock at system boundaries, not internal) preserves production-like composition. Standard 6 (cache isolation) prevents test-only state leakage. |

---

### 2.C Cross-Cutting Design Patterns

**Applicable Standards (checked):**

- ✅ Dependency Injection Best Practices — test double design
- ✅ Observability & Logging Patterns — request context propagation

**Search & Findings:**

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| DI best practices for testing | "dependency injection, test overrides" | Override at injection surface, not concrete class level. Test doubles should satisfy same contract as production. | ✅ Aligned | Standards 3 and 4 override at provider functions with Protocol-conformant stubs. |
| Observability: correlation ID propagation | "correlation ID, request context, structured logging" | Correlation IDs generated at request boundary, propagated without explicit parameter threading. | ✅ Aligned | Standard 10 uses `structlog.contextvars` for zero-parameter-threading propagation. |

---

### 2.D Validation Summary

**Total Standards Checked:** 12
**Aligned with Best Practice:** 10
**Deliberate Deviations:** 2

**High-Level Finding:**

- 🟡 **Mostly Grounded:** Most standards checked; two deviations require clarification.

**Deviation Summary:**

1. **pytest-asyncio auto mode (Standard 7):** The ADR correctly uses `asyncio_mode = auto` but does not note this is opt-in, not the default. Should state the required `pytest.ini` configuration and note the default is `strict`.
2. **structlog sync/async contextvars isolation (Standard 10):** structlog warns that contextvars set in sync context are invisible in async context within Starlette/FastAPI. Standard 10 does not mention this caveat. Could lead to silent context loss in hybrid sync/async handler chains.

---

## 3. Assumptions Challenged

### Assumption 3.1: Protocol-conformant test doubles catch interface drift (Standard 4)

- **Stated Norm:** "Test stubs for Category A services must implement all methods defined in the Protocol."
- **Underlying Assumption:** Protocol-conformant stubs catch interface drift at test time without importing concrete implementations.
- **Challenge:** If Protocol definitions evolve (new methods added), all test stubs must be updated simultaneously, creating maintenance overhead.
- **Evidence Strength:** ⭐ Strong — PEP 544 and mypy verify Protocol conformance statically.
- **Counter-Evidence Found:** No — MagicMock alternative silently passes when interfaces change, which is worse.
- **Confidence (ADR survives challenge):** 🟢 High
- **Reviewer Notes:** Sound. mypy catches Protocol drift in CI. Category A scope keeps the blast radius manageable.

### Assumption 3.2: Factory-as-fixture is preferred for configurable test data (Standard 5)

- **Stated Norm:** "Factory-as-fixture is the preferred pattern for configurable test data."
- **Underlying Assumption:** Factory functions with default parameters reduce boilerplate while keeping test intent visible.
- **Challenge:** Factory fixtures can hide important details if defaults are too "magic."
- **Evidence Strength:** ⭐ Strong — pytest documentation explicitly recommends this pattern.
- **Counter-Evidence Found:** No.
- **Confidence (ADR survives challenge):** 🟢 High
- **Reviewer Notes:** The `make_sync_settings` example is a clean implementation of the pytest-recommended pattern.

### Assumption 3.3: `asyncio_mode = auto` eliminates need for explicit markers (Standard 7)

- **Stated Norm:** "`asyncio_mode = auto` is configured in `app/pytest.ini` — explicit `@pytest.mark.asyncio` decorators are not required."
- **Underlying Assumption:** The project's `pytest.ini` configuration is authoritative and all environments use it.
- **Challenge:** pytest-asyncio's default is `strict` mode. The ADR's statement is true for this project but could mislead. Behavior has changed between pytest-asyncio versions — project pins `pytest-asyncio==0.26.0`.
- **Evidence Strength:** ⭐⭐ Moderate — depends on configuration being present and version being compatible.
- **Counter-Evidence Found:** Yes — pytest-asyncio docs confirm `strict` is the default. If `pytest.ini` is missing, async tests silently become no-ops.
- **Confidence (ADR survives challenge):** 🟡 Moderate
- **Reviewer Notes:** ADR should add explicit note that `auto` is opt-in, reference the exact `pytest.ini` entry, and note the pinned version dependency.

### Assumption 3.4: `structlog.contextvars` propagates context correctly in FastAPI (Standard 10)

- **Stated Norm:** "Middleware binds context at the ASGI boundary. Service logic reads context via `structlog.contextvars.get_contextvars()`."
- **Underlying Assumption:** Context variables bound in middleware propagate to all handler code.
- **Challenge:** structlog docs explicitly warn: in Starlette/FastAPI, "context variables set in a synchronous context don't appear in logs from an async context and vice versa." If middleware binds context in async ASGI but a sync `def` route reads it, context may be invisible.
- **Evidence Strength:** ⭐⭐⭐ Weak — the ADR does not address this known caveat at all.
- **Counter-Evidence Found:** Yes — structlog's own documentation warns about this exact scenario.
- **Confidence (ADR survives challenge):** 🟡 Moderate
- **Reviewer Notes:** Standard 10 must add a caveat about sync/async context isolation in Starlette-based apps. Mitigation: ensure consistent concurrency model or re-bind at boundaries.

### Assumption 3.5: `monkeypatch` preferred over `@patch` (Standard 8)

- **Stated Norm:** "Prefer `monkeypatch` over `unittest.mock.patch` for new tests."
- **Underlying Assumption:** `monkeypatch` provides cleaner lifecycle management via pytest fixtures.
- **Challenge:** `monkeypatch` cannot do spec-based mocking. `@patch(autospec=True)` catches incorrect attribute access.
- **Evidence Strength:** ⭐ Strong — pytest docs recommend `monkeypatch` for env vars and simple attribute replacement.
- **Counter-Evidence Found:** Partial — `autospec` safety not available, but Protocol stubs (S4) provide equivalent safety for Category A services.
- **Confidence (ADR survives challenge):** 🟢 High
- **Reviewer Notes:** Well-scoped preference. `@patch` remains acceptable in legacy code.

### Assumption 3.6: Forward compliance only (Migration)

- **Stated Norm:** "Non-conforming existing tests are not retroactively non-compliant."
- **Underlying Assumption:** Test suite is too large for big-bang migration; forward compliance is pragmatic.
- **Challenge:** Without forcing function, legacy tests may never migrate. Developers may copy legacy patterns.
- **Evidence Strength:** ⭐ Strong — `@pytest.mark.legacy` and `TESTING_STRATEGY.md` provide tracking and migration path.
- **Counter-Evidence Found:** No.
- **Confidence (ADR survives challenge):** 🟢 High
- **Reviewer Notes:** Standard approach for pre-ADR codebases.

---

## 4. Failure Modes Identified

### Failure Mode 4.1: Assumption 3.3 — async tests silently become no-ops

- **If Assumption Fails:** `pytest.ini` missing `asyncio_mode = auto`, or pytest-asyncio version change alters behavior. Async test functions collected but not awaited — coroutine object is truthy, tests appear to pass.
- **Platform Impact:**
  - Incident management workflow: Low
  - Access synchronization workflow: Medium — batch processing tests use async patterns
  - Access request workflow: Low
  - Multi-provider integrations: Medium — webhook and API integration tests may use async
- **Probability Estimate:** Low % — config is version-controlled; would require deliberate or accidental change.
- **Mitigation or Acceptance:** Add explicit note in Standard 7 referencing required `pytest.ini` line and pinned version.

### Failure Mode 4.2: Assumption 3.4 — context loss at sync/async boundary

- **If Assumption Fails:** Middleware binds correlation_id in async ASGI context; sync `def` route calls `get_contextvars()` and gets empty context. Logs from that handler lack correlation IDs.
- **Platform Impact:**
  - Incident management workflow: High — incident correlation depends on end-to-end request IDs
  - Access synchronization workflow: Medium — sync jobs need correlation IDs for audit trails
  - Access request workflow: Medium — approval flow needs traceable logs
  - Multi-provider integrations: High — multi-hop requests need forwarded correlation IDs
- **Probability Estimate:** Medium % — app has both sync and async handlers; middleware is ASGI (async). This is the exact scenario structlog warns about.
- **Mitigation or Acceptance:** Revise Standard 10 to add sync/async caveat. Document mitigation: use `async def` handlers consistently, or re-bind at sync/async boundary.

---

## 5. Contradiction Audit

### Cross-ADR Contradictions

| Conflict | ADRs Involved | Severity | Resolution Status |
|----------|---------------|----------|-------------------|
| S4 requires Protocol stubs for Category A; ADR-0065 P2 (Protocol for Behavioral Contracts) confirms this classification. | ADR-0062, ADR-0065 | 🟢 Low | ✅ Resolved — ADR-0065 Accepted 2026-04-30. P2 directly validates S4's Protocol stub requirement for Category A services. |
| S3 says override "provider functions (from `infrastructure.services`)" — ADR-0056 S1 says providers in `providers.py`. `infrastructure.services` is a re-export. No actual conflict. | ADR-0062, ADR-0056 | 🟢 Low | ✅ Resolved — re-export convenience; both correct. |

### Supersession Ambiguities

- **ADRs this one supersedes:** ADR-0030, ADR-0031
- **Inheritance Status:** All inherited patterns from ADR-0030 and ADR-0031 explicitly acknowledged in Supersession table.
- **Gaps Identified:** None.

### Ownership Clarity

- **Primary Domain Owner:** SRE Team
- **Secondary Domain Owners:** —
- **Plugin/Startup Registration:** N/A
- **Config Owner:** `app/pytest.ini`, `app/tests/conftest.py`
- **Audit Result:** ✅ Clear

---

## 6. Scenario Validation Matrix

> **Important — Target-State Validation, Not Current-State Compliance**
>
> This matrix tests whether the ADR's rules *would produce correct behavior* if fully applied. It does **not** assess whether current code complies. No package is fully ADR-compliant yet.

### Scenario 6.1: Incident Management Workflow

**Context:** Emergency response requires rapid logging, context propagation, and operational decision-making under time pressure.

| Aspect | ADR Requirement | Workflow Reality | Gap? | Notes |
|--------|-----------------|------------------|------|-------|
| Test isolation | S6: Clear provider caches between tests | Incident tests need isolated state | ✅ No | Cache clearing prevents cross-test contamination. |
| Context propagation | S10: structlog.contextvars for correlation IDs | End-to-end traceability required | ⚠️ Yes | Sync/async caveat could cause context loss in hybrid handlers. |
| Route test coverage | S3: dependency_overrides + success/error paths | Notification routes need both paths covered | ✅ No | Pattern is sound. |

**Validation Summary:**
- ⚠️ Aligned with documented exception handling

**Mitigation:** Standard 10 sync/async caveat needs documentation.

---

### Scenario 6.2: Access Synchronization Workflow

**Context:** Automated sync from identity providers to application; must handle failure, retry, and eventual consistency.

| Aspect | ADR Requirement | Workflow Reality | Gap? | Notes |
|--------|-----------------|------------------|------|-------|
| Narrow-slice fixtures | S5: Narrowest settings slice | Sync tests need `AccessSyncSettings` only | ✅ No | Factory-as-fixture proven in access package. |
| Protocol doubles | S4: Category A stubs satisfy Protocol | `AccessRequestServicePort` stubs validate interface | ✅ No | Access package demonstrates the pattern. |
| Integration boundaries | S12: Mock at system boundaries | DynamoDB, Google API, AWS IAM mocked externally | ✅ No | Matches Twelve-Factor dev/prod parity. |
| Async batch testing | S7: pytest-asyncio auto mode | Batch executor tests use async patterns | ✅ No | Auto mode eliminates marker boilerplate. |

**Validation Summary:**
- ✅ Fully aligned

---

### Scenario 6.3: Access Request Workflow

**Context:** User requests access; admin approves; system provisions and audits across platforms.

| Aspect | ADR Requirement | Workflow Reality | Gap? | Notes |
|--------|-----------------|------------------|------|-------|
| Feature-prefix naming | S2: `test_access_*` pattern | Request workflow spans catalog, approval, provisioning | ✅ No | Feature prefix disambiguates multi-step workflow. |
| Override cleanup | S3: `finally` block or autouse fixture | Multiple providers overridden per test | ✅ No | No leakage to subsequent tests. |
| Log suppression | S11: Autouse `suppress_structlog_output` | Verbose logging during test execution | ✅ No | Output focused on assertions. |

**Validation Summary:**
- ✅ Fully aligned

---

### Scenario 6.4: Multi-Provider Integration (Slack/Teams/AWS/GWS/GitHub)

**Context:** Single operation may span multiple external APIs.

| Aspect | ADR Requirement | Integration Reality | Gap? | Notes |
|--------|-----------------|---------------------|------|-------|
| Integration boundaries | S12: Mock at system boundaries | Each external API mocked independently | ✅ No | System boundary mocks in `fixtures/` enable realistic tests. |
| Correlation forwarding | S10: Honour `X-Request-ID` headers | Multi-hop requests need forwarded IDs | ✅ No | Standard 10 requires header forwarding. |
| Async multi-provider | S7: AsyncClient for contextvars | Multi-provider ops may use async HTTP | ✅ No | Standard 7 recommends AsyncClient for async routes. |

**Validation Summary:**
- ✅ Fully aligned

---

## 7. Tradeoffs Accepted

### Tradeoff 7.1: Protocol stubs vs. MagicMock simplicity

- **Chosen:** Protocol-conformant stubs for Category A services (Standard 4).
- **Rejected:** Universal MagicMock for all service doubles.
- **Rationale:** Protocol stubs catch interface drift. MagicMock silently accepts any attribute.
- **Risk Accepted:** More maintenance when Protocol interfaces evolve.
- **Contingency:** mypy catches drift in CI. Review Category A count if burden grows.

### Tradeoff 7.2: Forward compliance vs. full migration

- **Chosen:** Forward compliance only.
- **Rejected:** Big-bang migration of all existing tests.
- **Rationale:** Test suite is large and predates ADR standards. Big-bang risks regressions.
- **Risk Accepted:** Inconsistent patterns coexist during migration.
- **Contingency:** `@pytest.mark.legacy` tracks progress. Code review enforces new patterns.

### Tradeoff 7.3: monkeypatch preference vs. @patch safety

- **Chosen:** Prefer `monkeypatch` for new tests.
- **Rejected:** Mandate `@patch(autospec=True)` everywhere.
- **Rationale:** `monkeypatch` has cleaner lifecycle. `@patch` stacking is complex.
- **Risk Accepted:** No `autospec` equivalent in `monkeypatch`.
- **Contingency:** Protocol stubs (S4) provide interface safety for Category A services.

---

## 8. Follow-Up Actions

| Action | Blocker? | Owner | Due Date | Description |
|--------|----------|-------|----------|-------------|
| Add structlog sync/async caveat to S10 | ✅ Yes | ADR Author | 2026-05-05 | ✅ **Resolved 2026-04-30.** Standard 10 now includes sync/async isolation caveat blockquote with three mitigations: prefer `async def` handlers, bind context before thread-pool dispatch, use AsyncClient for boundary testing. |
| Clarify pytest-asyncio auto mode in S7 | ✅ Yes | ADR Author | 2026-05-05 | ✅ **Resolved 2026-04-30.** Standard 7 now includes configuration-dependency callout noting `auto` is opt-in (default `strict`), references `app/pytest.ini` line 3, and notes pinned `pytest-asyncio==0.26.0`. |
| ADR-0065 dependency verification | ❌ No | Wave 5 | Wave 5 gate | ✅ **Resolved 2026-04-30.** ADR-0065 Accepted. P2 (Protocol for Behavioral Contracts) confirms S4's Category A classification is correct. No changes needed. |

**All blocking actions resolved. ADR-0062 may proceed to Step 10.**

---

## 9. Binary Gate Outcome

**GATE DECISION:**

✅ **ACCEPT** (revised from ⚪ REVISE)

**Original Blockers (both resolved 2026-04-30):**

1. ~~**Standard 10 missing structlog sync/async caveat**~~ → Resolved. Standard 10 now includes a dedicated caveat blockquote documenting the sync/async contextvars isolation behavior with three actionable mitigations.
2. ~~**Standard 7 pytest-asyncio auto mode underspecified**~~ → Resolved. Standard 7 now includes a configuration-dependency callout noting `auto` is opt-in, referencing the exact `pytest.ini` entry, and noting the pinned version.

**Remaining Non-Blocking:** ADR-0065 dependency verification (Wave 5 gate).

---

## 10. Reviewer Sign-Off

| Field | Signature/Value |
|-------|-----------------|
| **Reviewer Name** | AI Architecture Reviewer |
| **Reviewer Title** | ADR Challenge Review Agent |
| **Organization/Team** | SRE Team |
| **Sign-Off Date** | 2026-04-30 |
| **Email** | — |

---

## 11. Review Artifacts Reference

**This Review Record Should Be Attached To:**
- Wave 5 tracker (ADR-0062 item)
- ADR-0062 revision PR

**This Review Template Was Completed Per:**
- ADR-0044 (Governance and Operating Model) § Step 9.5
- Revalidation Cycle: One-time gate review → annual review_state cycle
