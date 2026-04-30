# ADR Challenge and Content Review

## 1. Review Metadata

| Field | Value |
|-------|-------|
| **ADR Under Review** | ADR-0049: Plugin Registration and Startup Reliability Policy |
| **Reviewer Name & Title** | SRE Team, Architecture Reviewer |
| **Secondary Reviewers** | None |
| **Review Date** | 2026-04-28 |
| **Revalidation Due** | 2027-04-28 |
| **Gate Outcome** | **REVISE** |
| **Outcome Rationale** | Standard 6 (fail-fast warmup) needs explicit guidance on transient startup errors (e.g., a brief network blip during provider initialization). The current "any reason" failure-to-exit rule does not distinguish between configuration errors (permanent) and transient infrastructure errors (potentially retryable). Additionally, Standard 7 (zero-touch extension) should clarify the contract for what constitutes a discoverable package. |

## 2. Evidence Gathering & Convention Validation

### 2.A Language & Framework Standards

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| Pluggy Documentation | pluggy PluginManager registration check_pending hookspec | Pluggy supports hookspec-before-registration ordering, check_pending() validation, and keyword-only hook calls. | ✅ Aligned | None |
| FastAPI Lifespan | FastAPI lifespan startup failed | Unhandled exceptions before yield trigger startup.failed ASGI event. | ✅ Aligned | None |
| ASGI Lifespan Protocol v2.0 | ASGI startup.failed event | Protocol defines startup.failed signaling; server should log and exit. | ✅ Aligned | None |

### 2.B Infrastructure & Operational Standards

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| Twelve-Factor: Factor IX | disposability fast startup graceful shutdown | Fast startup and fail-fast are recommended for disposable processes. | ✅ Aligned | None |
| ECS Task Lifecycle | ECS task startup health check failure | ECS marks tasks as unhealthy and replaces them if startup fails. Supports fail-fast model. | ✅ Aligned | None |
| Pluggy Exception Handling | pluggy exception propagation hookimpl error | Pluggy propagates hookimpl exceptions to the call site; no special re-raise needed. | ✅ Aligned | None |

### 2.C Cross-Cutting Design Patterns

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| Plugin architecture patterns | plugin discovery registration patterns modular monolith | Startup-driven discovery is standard for plugin architectures; avoids import-time side effects. | ✅ Aligned | None |
| Fail-fast principle | fail fast principle software design startup | Fail-fast is widely recommended for startup validation; prevents silent degradation. | ✅ Aligned | None |

### 2.D Validation Summary

**Total Standards Checked:** 7
**Aligned with Best Practice:** 7
**Deliberate Deviations:** 0

**High-Level Finding:**
- 🟢 **Fully Grounded:** All standards checked; no unresolved deviations

## 3. Assumptions Challenged

### Assumption 3.1: All startup failures should terminate the process
- **Stated Norm:** Standard 6: "Enabled + warmup fails (any reason) → Exception propagates to lifespan; process terminates."
- **Underlying Assumption:** All startup failures are equally severe and warrant process termination.
- **Challenge:** A transient network error during startup_warmup (e.g., a brief DNS resolution failure when validating an external provider endpoint) would terminate the process even though the error might resolve on retry. ECS would restart the task, but multiple transient failures could cause the task to enter a crash loop.
- **Evidence Strength:** ⭐⭐ Moderate
- **Counter-Evidence Found:** Yes — legacy ADR-0017 notes: "Retry logic belongs in the config loader, not in startup_warmup. Loader retries should be bounded (≤ 3 attempts with backoff)."
- **Confidence (ADR survives challenge):** 🟡 Moderate
- **Reviewer Notes:** The fail-fast principle is correct, but the ADR should explicitly state that bounded retry with backoff is the responsibility of the caller within the warmup (e.g., retry an external health check 3 times before propagating the exception). The "any reason" language is too absolute.

### Assumption 3.2: Zero-touch extension contract is sufficiently defined
- **Stated Norm:** Standard 7: "Adding a new package under app/packages/ must not require changes to the lifespan function."
- **Underlying Assumption:** Any directory under app/packages/ with @hookimpl functions is automatically discovered.
- **Challenge:** The contract for what makes a package "discoverable" is implied but not explicit. Does the package need an `__init__.py`? Does it need to export specific symbols? Does `auto_discover_plugins` scan recursively or only top-level directories?
- **Evidence Strength:** ⭐⭐ Moderate
- **Counter-Evidence Found:** No direct counter-evidence, but the discovery contract is implementation-specific and may vary.
- **Confidence (ADR survives challenge):** 🟡 Moderate
- **Reviewer Notes:** Standard 7 should clarify the minimum contract: a package directory under `app/packages/` with an `__init__.py` that contains at least one `@hookimpl`-decorated function.

### Assumption 3.3: check_pending() catches all registration errors
- **Stated Norm:** Standard 3: "pm.check_pending() must be called to validate that all hook implementations have matching specifications."
- **Underlying Assumption:** check_pending() is sufficient to catch all registration problems.
- **Challenge:** check_pending() validates that hookimpls have matching specs, but it does not validate that required hooks have at least one implementation. If a critical hookspec has zero implementations, check_pending() passes silently.
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** No — this is by design in pluggy. Missing implementations are not an error.
- **Confidence (ADR survives challenge):** 🟢 High
- **Reviewer Notes:** This is a pluggy design decision, not an ADR gap. If a hookspec requires at least one implementation, the application should validate that separately (e.g., assert len(pm.hook.startup_warmup.get_hookimpls()) > 0). This is a Tier-2 implementation detail and does not need to be in this standard.

### Assumption 3.4: Singleton plugin manager is always sufficient
- **Stated Norm:** Standard 4: "Each plugin manager instance must be created once per process via @lru_cache."
- **Underlying Assumption:** One plugin manager per hook domain is sufficient.
- **Challenge:** If multiple independent hook domains exist (e.g., interactions, i18n, lifecycle), each needs its own PluginManager. The standard says "each plugin manager instance," which correctly allows multiple singletons for different domains.
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** No — the wording correctly allows multiple domain-specific singletons.
- **Confidence (ADR survives challenge):** 🟢 High
- **Reviewer Notes:** Wording is correct.

## 4. Failure Modes Identified

### Failure Mode 4.1: Transient startup failure causes crash loop
- **If Assumption Fails:** A transient network error during warmup causes process termination. ECS restarts the task, which hits the same transient error, creating a crash loop.
- **Platform Impact:**
  - Incident management workflow: Impact: High (application unavailable)
  - Access synchronization workflow: Impact: High (sync unavailable)
  - Access request workflow: Impact: High (requests unavailable)
  - Multi-provider integrations: Impact: High (all providers unavailable)
- **Probability Estimate:** Low %
- **Mitigation or Acceptance:** Add bounded retry guidance to Standard 6. Transient failures during warmup should be retried with backoff (≤ 3 attempts) before the exception propagates.

### Failure Mode 4.2: Undiscoverable package created without feedback
- **If Assumption Fails:** A developer creates a package under app/packages/ that is not discovered because it lacks the right structure (missing __init__.py, no @hookimpl).
- **Platform Impact:**
  - Incident management workflow: Impact: Low (feature not activated, but no crash)
  - Access synchronization workflow: Impact: Low
  - Access request workflow: Impact: Low
  - Multi-provider integrations: Impact: Low
- **Probability Estimate:** Medium %
- **Mitigation or Acceptance:** Clarify discoverable package contract in Standard 7. Consider a startup log that lists discovered packages for visibility.

## 5. Contradiction Audit

### Cross-ADR Contradictions

| Conflict | ADRs Involved | Severity | Resolution Status |
|----------|---------------|----------|-------------------|
| None found | — | — | — |

### Supersession Ambiguities
- **ADRs this one supersedes:** ADR-0013, ADR-0017, ADR-0026, ADR-0027
- **Inheritance Status:** All plugin lifecycle standards from four source ADRs are captured. Fail-fast policy from ADR-0017 is preserved. Startup-driven discovery from ADR-0026 is preserved.
- **Gaps Identified:** Transient retry guidance from ADR-0017 (bounded retry in config loader) is not carried forward into Standard 6.

### Ownership Clarity
- **Primary Domain Owner:** SRE Team
- **Audit Result:** ✅ Clear

## 6. Scenario Validation Matrix

### Scenario 6.1: Incident Management Workflow
| Aspect | ADR Requirement | Workflow Reality | Gap? | Notes |
|--------|-----------------|------------------|------|-------|
| Plugin discovery | Auto-discovered at startup | Incident handlers registered via hookimpl | ✅ No | Correct |
| Fail-fast warmup | Process exits on warmup failure | Misconfigured incident settings terminate startup | ✅ No | Per Standard 6 |

**Validation Summary:** ✅ Fully aligned

### Scenario 6.2: Access Synchronization Workflow
| Aspect | ADR Requirement | Workflow Reality | Gap? | Notes |
|--------|-----------------|------------------|------|-------|
| Startup warmup | Settings validated, services primed | access.sync validates settings in startup_warmup | ✅ No | Correct |
| Silent continue prohibited | No try/except swallowing | Current code has try/except blocks (to be removed) | ⚠️ Yes | Implementation action required |

**Validation Summary:** ⚠️ Aligned with documented implementation action (remove try/except blocks)

### Scenario 6.3: Access Request Workflow
| Aspect | ADR Requirement | Workflow Reality | Gap? | Notes |
|--------|-----------------|------------------|------|-------|
| Zero-touch extension | New packages auto-discovered | New access subpackages would be auto-discovered | ✅ No | Correct |

**Validation Summary:** ✅ Fully aligned

### Scenario 6.4: Multi-Provider Integration
| Aspect | ADR Requirement | Integration Reality | Gap? | Notes |
|--------|-----------------|---------------------|------|-------|
| Keyword-only hooks | All hook calls use keyword args | Current codebase uses keyword args | ✅ No | Pluggy enforces this |
| Hookspec-first | Specs registered before plugins | Plugin managers follow add_hookspecs → register pattern | ✅ No | Correct |

**Validation Summary:** ✅ Fully aligned

## 7. Tradeoffs Accepted

### Tradeoff 7.1: Fail-Fast vs. Resilient Startup
- **Chosen:** Fail-fast (process exits on warmup failure).
- **Rejected:** Degrade mode (continue with feature unavailable).
- **Rationale:** In ECS deployment model, degrade mode creates zombie tasks that look healthy but serve errors. Fail-fast gives clear signals.
- **Risk Accepted:** Single bad config value takes down entire app.
- **Contingency:** ECS restarts tasks automatically; staging validation catches config errors before prod.

### Tradeoff 7.2: Pluggy Dependency vs. Custom Plugin System
- **Chosen:** Pluggy (battle-tested, pytest ecosystem).
- **Rejected:** Custom decorator-based registration.
- **Rationale:** Pluggy eliminates per-subsystem boilerplate and import-time side effects.
- **Risk Accepted:** Pluggy learning curve; runtime dependency.
- **Contingency:** Pluggy is stable (pytest ecosystem) and unlikely to be abandoned.

## 8. Follow-Up Actions

| Action | Blocker? | Owner | Due Date | Description |
|--------|----------|-------|----------|-------------|
| Add bounded retry guidance to Standard 6 | ✅ Yes | SRE Team | 2026-04-28 | Standard 6 should note that transient errors during warmup should be retried with bounded backoff before propagation. Carry forward ADR-0017 guidance. |
| Clarify discoverable package contract in Standard 7 | ✅ Yes | SRE Team | 2026-04-28 | Define the minimum contract: package directory with __init__.py containing @hookimpl function(s). |

## 9. Binary Gate Outcome

**GATE DECISION:** **REVISE**

**Primary Blockers:**
1. Standard 6 needs bounded retry guidance for transient startup errors.
2. Standard 7 needs explicit discoverable package contract definition.

**Revision Deadline:** 2026-04-28

## 10. Reviewer Sign-Off

| Field | Signature/Value |
|-------|-----------------|
| **Reviewer Name** | SRE Team |
| **Reviewer Title** | Architecture Reviewer |
| **Organization/Team** | SRE Team |
| **Sign-Off Date** | 2026-04-28 |
