# ADR-0056 Backend-Selection Logic Amendment — Challenge Review

**Scope:** Amended sections only (Standard 8 addition and supporting updates per authoring workflow amendment procedure).

---

## 1. Review Metadata

| Field | Value |
|-------|-------|
| **ADR Under Review** | ADR-0056: Provider Discovery and Composition Standard — Standard 8 Amendment |
| **Amendment Type** | Normative (new standard added) |
| **Reviewer** | Architecture Review (AI-assisted) |
| **Review Date** | 2026-04-30 |
| **Revalidation Due** | 2026-08-28 |
| **Gate Outcome** | ⚪ **PASS** |
| **Outcome Rationale** | Standard 8 codifies the settings-driven factory pattern already proven in `retry/factory.py`. It is a direct implementation of ADR-0045 P7 (delegation hierarchy) and ADR-0047 P6 (backend-selection configuration) at the provider composition level. Rules are minimal and grounded in Twelve-Factor IV. |

---

## 2. Evidence Gathering (Amended Sections Only)

### 2.B Infrastructure & Operational Standards

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| Twelve-Factor Factor IV: Backing Services | `backing services swap config` | "Should be able to swap out a local MySQL database with one managed by a third party without any changes to the app's code. Only the resource handle in the config needs to change." | ✅ Aligned | Standard 8 implements this — backend selection via settings key, provider constructs appropriate implementation |
| ADR-0045 P7 (Managed Service Delegation Hierarchy) | `delegation hierarchy managed service library custom` | P7 mandates configurable backends for Category A services. "Every Protocol-backed service must support backend selection through configuration." | ✅ Aligned | Standard 8 is the provider-level implementation of P7's configurable backend mandate |
| ADR-0047 P6 (Backend-Selection Configuration) | `backend selection configuration key dev-safe` | P6 mandates dedicated `*_BACKEND` settings keys with dev-safe defaults. | ✅ Aligned | Standard 8 rules B1-B3 directly implement P6 requirements |

### 2.C Cross-Cutting Design Patterns

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| Abstract Factory Pattern (GoF) | `abstract factory runtime implementation selection` | Factory method selects concrete implementation based on runtime parameter. Client code receives the abstract type. | ✅ Aligned | The factory pattern (branch on settings key → return Protocol type) is a straightforward Abstract Factory application |

### 2.D Validation Summary

**Total Standards Checked:** 4
**Aligned with Best Practice:** 4
**Deliberate Deviations:** 0

**High-Level Finding:** 🟢 **Fully Grounded**

---

## 3. Assumptions Challenged

### Assumption 3.1: Backend selection belongs in the provider layer, not elsewhere

- **Stated Norm:** "The provider must implement settings-driven backend selection using a factory pattern."
- **Underlying Assumption:** Provider functions are the right location for backend branching logic.
- **Challenge:** Could backend selection be handled at a different layer — e.g., in a standalone factory module, in the settings class itself, or in a dedicated DI container?
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** No — Provider functions are already the sole constructors for infrastructure services (ADR-0048 B3). Backend selection is construction-time logic. Placing it in providers keeps construction logic centralized. Rule B7 permits extracting to a factory function for complex cases, providing the flexibility escape hatch. The existing `retry/factory.py` demonstrates this — it's a factory called by the provider.
- **Confidence (ADR survives challenge):** 🟢 High

### Assumption 3.2: Inline branching is sufficient; a plugin/registry pattern is not needed

- **Stated Norm:** Backend selection uses if/elif/else branching on a settings key, not a plugin registry.
- **Underlying Assumption:** The number of backends per service is small (typically 2-3) and known at design time.
- **Challenge:** If a service needs many backends (e.g., 5+ storage adapters), inline branching becomes unwieldy. Should Standard 8 prescribe a registry pattern?
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** No — Current services have 2-3 backends maximum (`memory`, `dynamodb`, `sqs`). A registry pattern would be over-engineering at this scale. If a service exceeds 3 backends, the factory can be extracted to a module-level function (rule B7) or a registry pattern can be adopted as a service-specific decision. Standard 8 does not prohibit registries — it simply doesn't mandate them.
- **Confidence (ADR survives challenge):** 🟢 High

### Assumption 3.3: Conditional dependency construction (rule B6) is implementable with `@lru_cache`

- **Stated Norm:** "Each backend branch must construct only the dependencies it needs. `\"memory\"` branch must not call `get_aws_clients()`."
- **Underlying Assumption:** `@lru_cache` and conditional branching compose correctly — only the selected branch's dependencies are constructed.
- **Challenge:** With `@lru_cache(maxsize=1)`, the provider is called exactly once. The conditional dependency call happens once and only for the selected backend. Could there be edge cases?
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** No — `@lru_cache(maxsize=1)` ensures the function runs once, branches once, and constructs only the selected backend's dependencies. This is deterministic and safe. The existing `retry/factory.py` demonstrates this pattern working correctly.
- **Confidence (ADR survives challenge):** 🟢 High

---

## 4. Failure Modes Identified

No Moderate or Low confidence assumptions. No failure modes to document.

---

## 5. Contradiction Audit

### Cross-ADR Contradictions

| Conflict | ADRs Involved | Severity | Resolution Status |
|----------|---------------|----------|-------------------|
| Standard 8 prescribes factory logic in providers; Standard 3 says providers are centralized in `providers.py` | ADR-0056 S3, S8 | 🟢 Low | ✅ Resolved — Backend-selection logic runs inside the provider function. Rule B7 permits extracted factory functions called by the provider. The provider remains in `providers.py`; the factory function may live in the service's module. |
| Standard 8 B2 prescribes `Literal` type constraint; ADR-0055 has not yet formalized `*_BACKEND` settings | ADR-0056 S8, ADR-0055 | 🟡 Medium | ⚪ Unresolved — ADR-0055 amendment is Item #8 in the delegation review tracker. Forward-reference to intended state. Acceptable: cascade will resolve. |

### Ownership Clarity

- **Primary Domain Owner:** SRE Team
- **Audit Result:** ✅ Clear

---

## 6. Scenario Validation (Amended Sections Only)

### Scenario 6.1: Adding Backend Selection to StorageService

| Aspect | Standard 8 Requirement | Expected Workflow | Gap? | Notes |
|--------|----------------------|-------------------|------|-------|
| Settings key | `STORAGE_BACKEND: Literal["memory", "dynamodb"]` in `StorageSettings` | Developer adds key with `"memory"` default | ✅ No | Per B1-B3 |
| Provider factory | Branch on `storage_settings.backend` | Provider returns `InMemoryStorageService` or `DynamoDBStorageService` based on key | ✅ No | Per §8.1 pattern |
| Conditional deps | `"memory"` branch skips `get_aws_clients()` | Only `"dynamodb"` branch calls `get_aws_clients()` | ✅ No | Per B6 |
| Return type | Protocol type `StorageService` | Provider annotated as `-> StorageService` | ✅ No | Per B5 |
| Error handling | Unknown backend raises `ValueError` | `else: raise ValueError(...)` | ✅ No | Per B4 |

**Validation Summary:** ✅ Fully aligned

---

## 7. Tradeoffs Accepted

### Tradeoff 7.1: Standard Count — Eight vs Seven

- **Chosen:** Add Standard 8 as a distinct standard.
- **Rejected:** Embed backend-selection guidance in Standard 1 (narrow-slice injection) or Standard 6 (graph shape).
- **Rationale:** Backend selection is a distinct concern from narrow-slice injection and graph shape. It has its own set of rules (B1-B7) that don't naturally fit in other standards. Standard 1 governs what goes into constructors; Standard 8 governs how providers choose which constructor to call.
- **Risk Accepted:** Larger standard count in ADR-0056.
- **Contingency:** If provider-level standards grow beyond 10, consider splitting ADR-0056 into composition and construction concerns.

---

## 8. Follow-Up Actions

| Action | Blocker? | Owner | Due Date | Description |
|--------|----------|-------|----------|-------------|
| Cascade `*_BACKEND` pattern to ADR-0055 | ❌ No | SRE Team | Per tracker Item #8 | Add `*_BACKEND` as recognized settings pattern with `Literal` typing |
| Apply Standard 8 to StorageService provider | ❌ No | SRE Team | Per P0 migration | First concrete application of Standard 8 |

**Blocking Actions:** None.

---

## 9. Binary Gate Outcome

**GATE DECISION:**

⚪ **PASS** → ADR-0056 Standard 8 amendment is professionally sound and ready for acceptance.

**Rationale:**

- Standard 8 codifies a pattern already proven in production (`retry/factory.py`)
- Directly implements ADR-0045 P7 and ADR-0047 P6 at the provider composition level
- All 3 assumptions survive challenge with High confidence
- No failure modes identified
- Rules are minimal (7) and grounded in Twelve-Factor IV and Abstract Factory pattern
- One Medium-severity unresolved item (ADR-0055 forward-reference) is acceptable — cascade will resolve

---

## 10. Reviewer Sign-Off

| Field | Signature/Value |
|-------|-----------------|
| **Reviewer** | Architecture Review (AI-assisted) |
| **Review Date** | 2026-04-30 |
| **Review Type** | Amendment review (normative change, scoped to amended sections per authoring workflow §Amendment Procedure) |
