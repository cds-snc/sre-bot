# ADR-0054 Dev/Test Fallback Standard Amendment — Challenge Review

**Scope:** Amended sections only (dev/test fallback standard addition per authoring workflow amendment procedure).

---

## 1. Review Metadata

| Field | Value |
|-------|-------|
| **ADR Under Review** | ADR-0054: Dev/Prod Parity and Operational Logs Ownership — Dev/Test Fallback Amendment |
| **Amendment Type** | Normative (new standard section added) |
| **Reviewer** | Architecture Review (AI-assisted) |
| **Review Date** | 2026-04-30 |
| **Revalidation Due** | 2026-08-28 |
| **Gate Outcome** | ⚪ **PASS** |
| **Outcome Rationale** | The dev/test fallback standard is a natural extension of Twelve-Factor dev/prod parity (Factor X) to the Protocol contract layer. It requires every Category A service to have an in-memory fallback, enabling local development and CI without cloud credentials. Grounded in ADR-0045 P7 (configurable backends require at least two implementations), validated against existing `InMemoryRetryStore` reference implementation. |

---

## 2. Evidence Gathering (Amended Sections Only)

### 2.B Infrastructure & Operational Standards

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| Twelve-Factor Factor X: Dev/Prod Parity | `dev prod parity keep development staging production similar` | "Keep development, staging, and production as similar as possible." The three gaps (time, personnel, tools) should all be minimized. | ✅ Aligned | Fallback standard extends tool parity to service implementations — same Protocol, same provider graph, different concrete backend |
| Twelve-Factor Factor IV: Backing Services | `backing services attached resources swap` | "Should be able to swap out a local MySQL database with one managed by a third party." Implies both directions — swap in-memory for prod, or prod for in-memory. | ✅ Aligned | In-memory fallback is the "local" backing service in Factor IV's model |
| ADR-0045 P7 (Managed Service Delegation Hierarchy) | `configurable backend dev/test fallback` | P7: "Every Protocol-backed service must support backend selection through configuration, enabling cloud portability and dev/test fallbacks without code changes." | ✅ Aligned | This amendment implements P7's "dev/test fallbacks" clause |

### 2.C Cross-Cutting Design Patterns

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| Cosmic Python — Repository Pattern (Ch. 2) | `in-memory repository testing fake` | "We can also use FakeRepository in our service layer tests." In-memory implementations are the standard testing approach for repository patterns. | ✅ Aligned | F1 and F5 directly implement this pattern for all Category A services |

### 2.D Validation Summary

**Total Standards Checked:** 4
**Aligned with Best Practice:** 4
**Deliberate Deviations:** 0

**High-Level Finding:** 🟢 **Fully Grounded**

---

## 3. Assumptions Challenged

### Assumption 3.1: Every Category A service can have a meaningful in-memory fallback

- **Stated Norm:** "Every Category A service must have an in-memory or local fallback implementation."
- **Underlying Assumption:** In-memory implementations are sufficient for dev/test purposes for all Category A services.
- **Challenge:** Some services may have complex semantics that an in-memory implementation cannot meaningfully replicate — e.g., `StorageService` with query/filter operations, `IdentityService` with external OAuth flows.
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** No — F3 explicitly states "functionally equivalent behavior for the Protocol's public interface — data persists for the process lifetime but is not required to survive restarts." This scopes the fallback to Protocol method contracts, not to backing-service-specific semantics (pagination, consistency guarantees, OAuth redirects). An in-memory dict satisfies `put`/`get`/`query`/`delete`. A stub identity resolver returns pre-configured test identities. The existing `InMemoryRetryStore` demonstrates this is feasible and practical.
- **Confidence (ADR survives challenge):** 🟢 High

### Assumption 3.2: The fallback must not import cloud SDKs (F4)

- **Stated Norm:** "The fallback must not import cloud SDKs, external service clients, or production-only dependencies."
- **Underlying Assumption:** CI environments should not require cloud SDK installation for testing.
- **Challenge:** Cloud SDKs (boto3, google-api-python-client) are already listed in `requirements.txt` and installed in all environments. F4 prevents importing them in fallback code, but they're still installed. Is F4 unnecessary?
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** Partial — Cloud SDKs are indeed installed everywhere, so F4 doesn't reduce install requirements. However, F4 serves a different purpose: it ensures the in-memory fallback has zero coupling to the production implementation. This prevents test failures caused by SDK version mismatches, credential configuration, or network-dependent initialization. F4 is a dependency isolation rule, not an installation optimization.
- **Confidence (ADR survives challenge):** 🟢 High

### Assumption 3.3: Fallback creation is correctly sequenced with Protocol migration

- **Stated Norm:** "Fallback implementations are created during the ADR-0077 Protocol migration (Standard 5, step 6)."
- **Underlying Assumption:** Protocol migration is the right trigger for fallback creation — not before, not after.
- **Challenge:** Could fallbacks be created independently of Protocol migration? Some services already have test mocks that serve a similar purpose.
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** No — Existing test mocks are ad-hoc patches of concrete classes, not Protocol-satisfying implementations. Creating a proper fallback requires a Protocol to satisfy. The Protocol migration (ADR-0077 Standard 5) includes "Create test double" as step 6 — creating the fallback during migration ensures it satisfies the Protocol contract structurally (verified by `isinstance` if `@runtime_checkable`). Creating fallbacks before Protocols exist would be premature.
- **Confidence (ADR survives challenge):** 🟢 High

---

## 4. Failure Modes Identified

No Moderate or Low confidence assumptions. No failure modes to document.

---

## 5. Contradiction Audit

### Cross-ADR Contradictions

| Conflict | ADRs Involved | Severity | Resolution Status |
|----------|---------------|----------|-------------------|
| ADR-0054 originally focused on parity of "runtime behavior"; the fallback standard extends parity to "service implementation" | ADR-0054 original, amendment | 🟢 Low | ✅ Resolved — Service implementation parity is a natural extension of runtime behavior parity. Both are covered by Twelve-Factor Factor X. The amendment extends, does not contradict. |
| F1 requires fallback for all Category A services; `DirectoryProvider` (Category A, complete Protocol) currently has no in-memory fallback | ADR-0054 F1, ADR-0077 | 🟢 Low | ✅ Resolved — The fallback status table documents this gap. Fallback creation is tracked as part of incremental migration, not as an immediate mandate. |

### Ownership Clarity

- **Primary Domain Owner:** SRE Team
- **Audit Result:** ✅ Clear

---

## 6. Scenario Validation (Amended Sections Only)

### Scenario 6.1: New Developer Local Startup

| Aspect | Fallback Requirement | Expected Behavior | Gap? | Notes |
|--------|---------------------|-------------------|------|-------|
| App startup | All backend defaults to `"memory"` | App starts with in-memory implementations for all Category A services | ✅ No | F2 ensures dev-safe defaults |
| Route testing | In-memory services satisfy Protocol contracts | All routes function correctly against in-memory backends | ✅ No | F3 ensures functional equivalence |
| No credentials needed | Fallbacks don't import cloud SDKs | No AWS/Google credential errors at startup | ✅ No | F4 ensures isolation |

**Validation Summary:** ✅ Fully aligned

### Scenario 6.2: CI Test Suite

| Aspect | Fallback Requirement | Expected Behavior | Gap? | Notes |
|--------|---------------------|-------------------|------|-------|
| Test fixture setup | `dependency_overrides` with fallback | Test overrides provider with in-memory implementation | ✅ No | F5 ensures compatibility |
| Test isolation | In-memory state per test | Each test gets a fresh fallback instance | ✅ No | Standard test fixture pattern |

**Validation Summary:** ✅ Fully aligned

---

## 7. Tradeoffs Accepted

### Tradeoff 7.1: Mandatory Fallback vs Optional Fallback

- **Chosen:** Every Category A service must have a fallback (mandatory).
- **Rejected:** Fallbacks are recommended but optional.
- **Rationale:** ADR-0045 P7 says "must support backend selection through configuration, enabling... dev/test fallbacks." The word "must" makes this mandatory. Optional fallbacks would allow services to be Protocol-backed but still require cloud credentials for dev/test, defeating the portability goal.
- **Risk Accepted:** Maintenance overhead of N in-memory implementations (currently 10 Category A services, 5 already have fallbacks).
- **Contingency:** In-memory implementations are typically simple (dict-backed, ~50-100 LOC). The maintenance burden is proportional to the Protocol surface, which is intentionally narrow.

---

## 8. Follow-Up Actions

| Action | Blocker? | Owner | Due Date | Description |
|--------|----------|-------|----------|-------------|
| Create fallbacks during Protocol migrations | ❌ No | SRE Team | Per ADR-0077 S5 schedule | Each Protocol migration includes fallback creation |

**Blocking Actions:** None.

---

## 9. Binary Gate Outcome

**GATE DECISION:**

⚪ **PASS** → ADR-0054 dev/test fallback standard amendment is professionally sound and ready for acceptance.

**Rationale:**

- Amendment directly implements ADR-0045 P7's "dev/test fallbacks" clause
- Grounded in Twelve-Factor Factor X (dev/prod parity) and Factor IV (backing service swappability)
- All 3 assumptions survive challenge with High confidence
- No failure modes identified
- Existing `InMemoryRetryStore` validates the pattern in production codebase
- Fallback status table provides transparency on current gaps and migration sequencing
- Cross-reference chain is complete: P7 → F1 (mandate) → F2 → ADR-0055 S9 (settings) → ADR-0056 S8 (factory)

---

## 10. Reviewer Sign-Off

| Field | Signature/Value |
|-------|-----------------|
| **Reviewer** | Architecture Review (AI-assisted) |
| **Review Date** | 2026-04-30 |
| **Review Type** | Amendment review (normative change, scoped to amended sections per authoring workflow §Amendment Procedure) |
