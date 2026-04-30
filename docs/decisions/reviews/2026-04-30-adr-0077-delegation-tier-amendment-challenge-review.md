# ADR-0077 Delegation Tier Declaration Amendment — Challenge Review

**Scope:** Amended sections only (delegation tier declaration requirement added to Standard 1 Category A, per authoring workflow amendment procedure).

---

## 1. Review Metadata

| Field | Value |
|-------|-------|
| **ADR Under Review** | ADR-0077: Infrastructure Service Contract Standard — Delegation Tier Declaration Amendment |
| **Amendment Type** | Normative (new classification requirement added to Standard 1) |
| **Reviewer** | Architecture Review (AI-assisted) |
| **Review Date** | 2026-04-30 |
| **Revalidation Due** | 2026-08-28 |
| **Gate Outcome** | ⚪ **PASS** |
| **Outcome Rationale** | The delegation tier declaration is a direct implementation of ADR-0045 P7 at the service classification level. It adds traceability between Category A services and the delegation hierarchy without altering the existing A/B/C classification model. Tier assessments for all 10 current Category A services are grounded in actual backing service implementations. |

---

## 2. Evidence Gathering (Amended Sections Only)

### 2.B Infrastructure & Operational Standards

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| ADR-0045 P7 (Managed Service Delegation Hierarchy) | `delegation hierarchy managed service library custom` | P7 mandates: "Infrastructure concerns must be served by the highest applicable delegation tier." Category A services are the primary scope of P7 — they are the Protocol-backed services that abstract over backing services. | ✅ Aligned | — |
| Twelve-Factor Factor IV: Backing Services | `backing services attached resources config swap` | "A deploy of the twelve-factor app should be able to swap out a local MySQL database with one managed by a third party." Documenting the current delegation tier makes the swap path explicit. | ✅ Aligned | — |
| AWS Well-Architected — Operational Excellence | `managed services reduce operational burden` | "Use managed services. Reduce the operational burden by using AWS managed services where possible." Tier declaration surfaces services that could benefit from managed service adoption. | ✅ Aligned | — |
| Hexagonal Architecture — Adapter Documentation | `ports adapters hexagonal architecture adapter implementation` | Ports and Adapters pattern distinguishes between the port (Protocol) and the adapter (implementation). Documenting which tier the adapter belongs to is an extension of the adapter documentation practice. | ✅ Aligned | — |

### 2.D Validation Summary

**Total Standards Checked:** 4
**Aligned with Best Practice:** 4
**Deliberate Deviations:** 0

**High-Level Finding:** 🟢 **Fully Grounded** — All standards checked; no unresolved deviations.

---

## 3. Assumptions Challenged

### Assumption 3.1: Every Category A service can be meaningfully classified into a single delegation tier

- **Stated Norm:** "Each Category A service must document which delegation tier its current implementation uses."
- **Underlying Assumption:** Each service has a single, identifiable delegation tier for its primary backing implementation.
- **Challenge:** Some services may compose multiple tiers — e.g., `IdentityService` wraps managed services (Google Workspace, AWS IAM Identity Center) but also includes custom JWT parsing logic. Should this be Tier 1 or Tier 3?
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** No — The tier declaration applies to the *primary backing service abstraction*, not to every line of code in the implementation. `IdentityService` delegates identity resolution to managed services (Tier 1); JWT parsing is a Protocol contract concern, not the service's primary delegation target. The amendment says "which delegation tier its current implementation uses" — meaning the dominant delegation strategy, not a line-by-line analysis.
- **Confidence (ADR survives challenge):** 🟢 High
- **Reviewer Notes:** For services that compose tiers, the tier declaration should reflect the primary backing service. Secondary concerns (e.g., JWT parsing in IdentityService) are implementation details of the Protocol contract, not separate delegation decisions.

### Assumption 3.2: Tier 3 justification requirement is proportionate and not over-burdensome

- **Stated Norm:** "Tier 3 declarations must include a justification stating why no managed service or library applies."
- **Underlying Assumption:** The justification burden is proportionate to the maintenance cost of custom code.
- **Challenge:** For services where the custom nature is obvious (e.g., `RetryProcessor` which orchestrates domain-specific retry semantics), requiring justification adds bureaucratic overhead without informational value.
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** Partial — The justification for `RetryProcessor` Tier 3 is indeed brief and obvious ("orchestration logic specific to feature retry semantics; no managed service or library covers domain-specific retry coordination"). However, having the justification documented prevents future developers from assuming Tier 3 was chosen through inertia rather than deliberation. The cost of one sentence per Tier 3 service is negligible.
- **Confidence (ADR survives challenge):** 🟢 High
- **Reviewer Notes:** The justification can be a single clause — it does not require a detailed analysis. The existing table demonstrates this: `RetryProcessor` justification fits in one table cell.

### Assumption 3.3: The tier assessments for existing services are accurate

- **Stated Norm:** The Category A table assigns specific tiers to all 10 services.
- **Underlying Assumption:** Each tier assignment accurately reflects the service's current primary delegation strategy.
- **Challenge:** Are any tier assignments incorrect or debatable?
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** No — Verification against codebase:
  - `DirectoryProvider` → wraps Google Workspace SDK → Tier 1 ✅
  - `RetryStore` → wraps DynamoDB conditional writes → Tier 1 ✅
  - `RetryProcessor` → custom orchestration logic → Tier 3 ✅ (with justification)
  - `ResponseChannel` → wraps platform APIs (Slack, Teams) → Tier 1 ✅
  - `BackgroundJobRegistry` → wraps `schedule` library → Tier 2 ✅
  - `StorageService` → wraps DynamoDB → Tier 1 ✅
  - `IdentityService` → wraps Google Workspace + AWS IAM Identity Center → Tier 1 ✅
  - `AuditTrailService` → delegates to DynamoDB via StorageService → Tier 1 ✅
  - `NotificationService` → wraps GC Notify API → Tier 1 ✅
  - `IdempotencyService` → wraps DynamoDB → Tier 1 ✅
- **Confidence (ADR survives challenge):** 🟢 High
- **Reviewer Notes:** All assessments are consistent with the actual backing services documented in the existing "Backing Service" column. The only Tier 3 service (`RetryProcessor`) has a documented justification.

### Assumption 3.4: Delegation tier belongs in ADR-0077 (Tier-2 classification), not elsewhere

- **Stated Norm:** The delegation tier declaration is added to Standard 1 Category A classification.
- **Underlying Assumption:** Service classification is the right place to anchor delegation tier documentation.
- **Challenge:** Should delegation tier be documented elsewhere — e.g., in ADR-0056 (provider composition), in ADR-0055 (settings), or in each service's own code?
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** No — ADR-0077 Standard 1 already classifies services by their relationship to backing services. The delegation tier is a *property of the service classification* — it describes what kind of backing service sits behind the Protocol. This is a natural extension of Standard 1, not a separate concern. Code-level documentation (docstrings, comments) can reference the ADR table, but the authoritative classification belongs in the ADR.
- **Confidence (ADR survives challenge):** 🟢 High
- **Reviewer Notes:** P7 (ADR-0045) defines the hierarchy; ADR-0077 Standard 1 classifies which services are subject to the hierarchy (Category A); the delegation tier declaration bridges the two by recording the current tier for each Category A service.

---

## 4. Failure Modes Identified

No Moderate or Low confidence assumptions. No failure modes to document.

---

## 5. Contradiction Audit

### Cross-ADR Contradictions

| Conflict | ADRs Involved | Severity | Resolution Status |
|----------|---------------|----------|-------------------|
| ADR-0045 P7 defines delegation hierarchy at Tier 1; ADR-0077 implements it at Tier 2 classification level | ADR-0045 P7, ADR-0077 S1 | 🟢 Low | ✅ Resolved — P7 establishes the foundational principle; ADR-0077 implements the classification-level requirement. This is the intended Tier-1 → Tier-2 delegation. |
| `ResilienceService` (Category B, no Protocol) uses custom circuit breaker code (Tier 3), but P7 flags custom code for delegation | ADR-0045 P7, ADR-0077 S1 | 🟢 Low | ✅ Resolved — P7's delegation hierarchy applies to Category A services (Protocol-backed). `ResilienceService` is Category B (shared utility, no Protocol). The `pybreaker` library adoption (delegation tracker Item #24) addresses the custom code concern independently of the ADR-0077 classification. |
| ADR-0054 (dev/test fallback) may require every Category A service to have an in-memory implementation, which is related to but distinct from delegation tier | ADR-0077, ADR-0054 | 🟢 Low | ✅ Resolved — Delegation tier documents *what the production implementation delegates to*. Dev/test fallback (ADR-0054) documents *what the test/dev implementation uses*. They are complementary, not conflicting. The compliance section cross-references ADR-0054. |

### Supersession Ambiguities

- **ADRs this one supersedes:** None changed by this amendment.
- **Inheritance Status:** N/A.
- **Gaps Identified:** None.

### Ownership Clarity

- **Primary Domain Owner:** SRE Team
- **Audit Result:** ✅ Clear

---

## 6. Scenario Validation (Amended Sections Only)

### Scenario 6.1: New Category A Service Registration

| Aspect | Amendment Requirement | Expected Workflow | Gap? | Notes |
|--------|----------------------|-------------------|------|-------|
| Service creation | New Category A service must declare delegation tier | Developer adds row to Category A table with Delegation Tier column populated | ✅ No | Natural extension of existing service registration workflow |
| Tier 1 declaration | Document managed service wrapper | Developer writes "Tier 1 (managed service — SQS)" | ✅ No | Minimal overhead |
| Tier 3 declaration | Must include justification | Developer writes "Tier 3 (custom — [reason])". Triggers review discussion. | ✅ No | Justification serves as a discussion prompt during code review |

**Validation Summary:** ✅ Fully aligned

### Scenario 6.2: Existing Service Delegation Review

| Aspect | Amendment Requirement | Expected Workflow | Gap? | Notes |
|--------|----------------------|-------------------|------|-------|
| `RetryProcessor` (Tier 3) | Justification documented; flagged for future delegation | Table shows justification. If a managed service or library later covers retry coordination, the service is a candidate for tier promotion. | ✅ No | Only Tier 3 service currently; justification is clear. |
| `BackgroundJobRegistry` (Tier 2) | Tier 2 documented | Table shows Tier 2 (library — `schedule`). No action needed — Tier 2 is an acceptable delegation tier. | ✅ No | Correctly classified. |

**Validation Summary:** ✅ Fully aligned

---

## 7. Tradeoffs Accepted

### Tradeoff 7.1: Classification Complexity — Four-Column Table vs Three-Column

- **Chosen:** Add `Delegation Tier` column to existing Category A table.
- **Rejected:** Create a separate delegation tier table or subsection.
- **Rationale:** The delegation tier is a property of each Category A service. Embedding it in the existing classification table keeps all service metadata in one place and avoids duplication.
- **Risk Accepted:** Wider table may be harder to read in narrow viewports.
- **Contingency:** If the table becomes unwieldy, the delegation tier column can be moved to a companion table with a cross-reference.

### Tradeoff 7.2: Inline Justification vs Separate Document

- **Chosen:** Tier 3 justification inline in the table cell.
- **Rejected:** Separate justification document or ADR for each Tier 3 choice.
- **Rationale:** Only one service (`RetryProcessor`) is currently Tier 3. A separate document for a single-sentence justification would be over-engineered. If Tier 3 services proliferate, a separate document can be introduced.
- **Risk Accepted:** Inline justifications must remain brief to fit in table cells.
- **Contingency:** For complex Tier 3 justifications, the table cell can reference a separate analysis document.

---

## 8. Follow-Up Actions

| Action | Blocker? | Owner | Due Date | Description |
|--------|----------|-------|----------|-------------|
| Cascade delegation tier to ADR-0061 (identity) | ❌ No | SRE Team | Per tracker Item #22 | Add delegation tier declaration for identity providers |
| Cascade to ADR-0054 (dev/test fallback) | ❌ No | SRE Team | Per tracker Item #9 | Add fallback requirement cross-referencing delegation tier |
| Cascade to ADR-0056 (provider backend selection) | ❌ No | SRE Team | Per tracker Item #7 | Formalize backend-selection logic using delegation tier |

**Blocking Actions:** None.

---

## 9. Binary Gate Outcome

**GATE DECISION:**

⚪ **PASS** → ADR-0077 delegation tier declaration amendment is professionally sound and ready for acceptance.

**Rationale:**

- Amendment directly implements ADR-0045 P7 at the Tier-2 service classification level
- All 4 assumptions survive challenge with High confidence
- No failure modes identified (all assumptions High confidence)
- No contradictions with existing canonical ADRs
- Tier assessments for all 10 Category A services verified against actual backing services
- Only one Tier 3 service (`RetryProcessor`) — justification is documented and proportionate
- Amendment is additive (new column, new subsection) — does not alter existing A/B/C classification model
- Compliance section correctly cross-references downstream ADRs (0047, 0054, 0055, 0056)

---

## 10. Reviewer Sign-Off

| Field | Signature/Value |
|-------|-----------------|
| **Reviewer** | Architecture Review (AI-assisted) |
| **Review Date** | 2026-04-30 |
| **Review Type** | Amendment review (normative change, scoped to amended sections per authoring workflow §Amendment Procedure) |
