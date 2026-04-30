# ADR-0055 Backend-Selection Settings Pattern Amendment — Challenge Review

**Scope:** Amended sections only (Standard 9 addition and supporting updates per authoring workflow amendment procedure).

---

## 1. Review Metadata

| Field | Value |
|-------|-------|
| **ADR Under Review** | ADR-0055: Settings Implementation and Dissolution Standard — Standard 9 Amendment |
| **Amendment Type** | Normative (new standard added) |
| **Reviewer** | Architecture Review (AI-assisted) |
| **Review Date** | 2026-04-30 |
| **Revalidation Due** | 2026-08-28 |
| **Gate Outcome** | ⚪ **PASS** |
| **Outcome Rationale** | Standard 9 codifies the `*_BACKEND` settings pattern already implemented in `RetrySettings`. It is a direct corollary of ADR-0047 P6 (backend-selection configuration) at the settings implementation level. Rules are minimal (5), grounded in pydantic-settings v2 `Literal` validation and existing codebase patterns. Dissolution accounting correctly identifies existing and future backend keys. |

---

## 2. Evidence Gathering (Amended Sections Only)

### 2.A Language & Framework Standards

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| Pydantic Settings V2 — Literal validation | `pydantic Literal type validation BaseSettings` | Pydantic validates `Literal` fields at instantiation — invalid values fail fast at startup with a clear validation error. | ✅ Aligned | K2 leverages built-in pydantic `Literal` validation |
| Pydantic V2 — Field alias | `pydantic Field alias environment variable` | `alias` parameter maps Python field names to environment variable names. | ✅ Aligned | K4 uses `alias` for env-var naming |

### 2.B Infrastructure & Operational Standards

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| ADR-0047 P6 (Backend-Selection Configuration) | `backend selection configuration key dev-safe defaults` | P6 mandates dedicated config keys for backend selection with dev-safe defaults and type-level constraints. | ✅ Aligned | Standard 9 is the settings-level implementation of P6 |
| Twelve-Factor Factor III: Config | `store config environment backing services` | Config varies between deploys. Backend selection is deployment-specific configuration. | ✅ Aligned | Backend keys are env-var-sourced, deployment-specific |

### 2.D Validation Summary

**Total Standards Checked:** 4
**Aligned with Best Practice:** 4
**Deliberate Deviations:** 0

**High-Level Finding:** 🟢 **Fully Grounded**

---

## 3. Assumptions Challenged

### Assumption 3.1: Backend keys should use `Literal` type, not `str` with runtime validation

- **Stated Norm:** "Key type must be `Literal[\"value1\", \"value2\", ...]`"
- **Underlying Assumption:** Type-level validation at startup is better than runtime validation in the factory.
- **Challenge:** The existing `RetrySettings.backend` uses `str`, not `Literal`. Changing to `Literal` is a breaking change for any deployment that uses an unexpected value. Is `Literal` over-constraining?
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** No — `Literal` fails at startup (ADR-0047 P3: fail-fast configuration validation), which is the desired behavior. An invalid backend value should never reach the factory's `ValueError` branch at runtime. The `Literal` type also provides IDE autocompletion and mypy enforcement. The migration from `str` to `Literal` for `RetrySettings` is a normal refinement (noted in §9.4 as a follow-up).
- **Confidence (ADR survives challenge):** 🟢 High

### Assumption 3.2: Backend keys must be infrastructure-owned (K5)

- **Stated Norm:** "Key must be owned by the infrastructure settings class for the service domain, not by a feature settings class."
- **Underlying Assumption:** Backend selection is an infrastructure concern, not a feature concern.
- **Challenge:** `RECONCILIATION_BACKEND` is in `infrastructure/configuration/features/groups.py` — a feature settings class. Does K5 conflict with existing ownership?
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** Partial — `RECONCILIATION_BACKEND` is in a *transitional* feature settings class that lives in infrastructure per Standard 4 (legacy module posture). K5 says backend keys belong in infrastructure settings; the transitional class is already in infrastructure. When `groups` migrates to `app/packages/`, the reconciliation backend key would either move to the feature's settings or be retired. §9.3 documents this transition explicitly.
- **Confidence (ADR survives challenge):** 🟢 High

### Assumption 3.3: Dissolution accounting is complete for existing backend keys

- **Stated Norm:** §9.3 documents `RETRY_BACKEND` and `RECONCILIATION_BACKEND` transition paths.
- **Underlying Assumption:** These are the only two `*_BACKEND` keys currently in the codebase.
- **Challenge:** Are there other backend-selection keys not using the `*_BACKEND` naming convention?
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** No — grep for `_BACKEND` in infrastructure configuration confirms only these two keys. No other backend-selection patterns exist under different naming conventions.
- **Confidence (ADR survives challenge):** 🟢 High

---

## 4. Failure Modes Identified

No Moderate or Low confidence assumptions. No failure modes to document.

---

## 5. Contradiction Audit

### Cross-ADR Contradictions

| Conflict | ADRs Involved | Severity | Resolution Status |
|----------|---------------|----------|-------------------|
| Standard 9 K2 prescribes `Literal` type; existing `RetrySettings.backend` is `str` | ADR-0055 S9, current code | 🟢 Low | ✅ Resolved — S9 is a design target. §9.4 notes the existing `str` field as a future refinement. New backend keys must use `Literal` from day one; existing keys migrate incrementally. |
| Standard 9 K5 says infrastructure-owned; ADR-0047 P2 says ownership follows code | ADR-0055 S9, ADR-0047 P2 | 🟢 Low | ✅ Resolved — Backend selection is an infrastructure concern (the service's Protocol and backing implementation are infrastructure-owned). P2 applies: the code that reads the backend key is infrastructure provider code, so infrastructure owns the key. |

### Ownership Clarity

- **Primary Domain Owner:** SRE Team
- **Audit Result:** ✅ Clear

---

## 6. Scenario Validation (Amended Sections Only)

### Scenario 6.1: Adding `STORAGE_BACKEND` During StorageService Protocol Migration

| Aspect | Standard 9 Requirement | Expected Workflow | Gap? | Notes |
|--------|----------------------|-------------------|------|-------|
| Key creation | `STORAGE_BACKEND: Literal["memory", "dynamodb"]` in `StorageSettings` | Developer adds field per §9.1 pattern | ✅ No | K1-K4 govern |
| Default value | `"memory"` | Dev startup works without DynamoDB credentials | ✅ No | K3 governs |
| Dissolution | Key in infrastructure-owned settings | No ownership change during dissolution | ✅ No | K5, §9.3 govern |
| Consumer | ADR-0056 Standard 8 factory reads key | Provider branches on `storage_settings.backend` | ✅ No | Cross-ADR chain complete |

**Validation Summary:** ✅ Fully aligned

---

## 7. Tradeoffs Accepted

### Tradeoff 7.1: Standard Count — Nine vs Eight

- **Chosen:** Add Standard 9 as a distinct settings pattern.
- **Rejected:** Embed backend-selection guidance in Standard 1 (singleton) or Standard 5 (bootstrap vs runtime).
- **Rationale:** Backend-selection keys are a distinct pattern with their own naming convention, type constraints, and dissolution considerations. They are not simply another bootstrap setting — they govern which implementation class the provider constructs. A separate standard provides clear searchability and cross-reference from ADR-0056 Standard 8.
- **Risk Accepted:** Larger standard count.
- **Contingency:** Standards 8 (config requirements) and 9 (backend keys) could be merged if the distinction proves confusing.

---

## 8. Follow-Up Actions

| Action | Blocker? | Owner | Due Date | Description |
|--------|----------|-------|----------|-------------|
| Update `RetrySettings.backend` to `Literal` type | ❌ No | SRE Team | Per implementation plan | Migrate from `str` to `Literal["memory", "dynamodb"]` per §9.4 |
| Apply Standard 9 to future `STORAGE_BACKEND`, `QUEUE_BACKEND` keys | ❌ No | SRE Team | Per migration schedule | New keys created per S9 from day one |

**Blocking Actions:** None.

---

## 9. Binary Gate Outcome

**GATE DECISION:**

⚪ **PASS** → ADR-0055 Standard 9 amendment is professionally sound and ready for acceptance.

**Rationale:**

- Standard 9 codifies an existing pattern (`RetrySettings.backend`) and formalizes it for future keys
- Directly implements ADR-0047 P6 at the settings implementation level
- All 3 assumptions survive challenge with High confidence
- No failure modes identified
- Dissolution accounting (§9.3) correctly tracks existing backend keys through the aggregator dissolution lifecycle
- `Literal` type constraint leverages pydantic's built-in validation — no custom enforcement needed

---

## 10. Reviewer Sign-Off

| Field | Signature/Value |
|-------|-----------------|
| **Reviewer** | Architecture Review (AI-assisted) |
| **Review Date** | 2026-04-30 |
| **Review Type** | Amendment review (normative change, scoped to amended sections per authoring workflow §Amendment Procedure) |
