# ADR-0061 Delegation Tier Declaration Amendment — Challenge Review

**Scope:** Amended sections only (delegation tier declaration added to Standard 3 and Standard 5, managed service delegation impact added to Compliance, per authoring workflow amendment procedure).

---

## 1. Review Metadata

| Field | Value |
|-------|-------|
| **ADR Under Review** | ADR-0061: Identity and External Integration Contract Standard — Delegation Tier Declaration Amendment |
| **Amendment Type** | Normative (delegation tier declaration added to Standard 3; Delegation Tier column added to Standard 5 classification table; managed service delegation impact added to Compliance section) |
| **Reviewer** | Architecture Review (AI-assisted) |
| **Review Date** | 2026-04-30 |
| **Revalidation Due** | 2026-08-28 |
| **Gate Outcome** | ⚪ **PASS** |
| **Outcome Rationale** | The delegation tier declaration cascades ADR-0045 P7 and ADR-0077 delegation tier requirements to the identity domain. The Tier 1 classification is grounded in codebase evidence: identity resolution backends (JWT/JWKS endpoints, Slack API, webhook payloads) delegate to managed external service APIs. The amendment adds an explicit domain boundary clarification distinguishing interaction identity resolution (this ADR) from IDP concerns (DirectoryProvider) and access sync concerns (access package). |

---

## 2. Evidence Gathering (Amended Sections Only)

### 2.B Infrastructure & Operational Standards

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| ADR-0045 P7 (Managed Service Delegation Hierarchy) | Upstream principle review | P7 mandates: "Infrastructure concerns must be served by the highest applicable delegation tier." IdentityService abstracts over managed identity provider APIs — Tier 1 is the correct classification. | ✅ Aligned | — |
| ADR-0077 Standard 1 (Category A Delegation Tier) | Category A table review | ADR-0077 already classifies IdentityService as "Tier 1 (managed service wrappers — Google Workspace, AWS IAM Identity Center)" with P1 migration priority. This amendment cascades that declaration into the domain-level ADR. | ✅ Aligned | — |
| Twelve-Factor Factor IV: Backing Services | Backing services documentation | Identity providers are backing services — the app treats them as attached resources accessed via configuration. Google Workspace, AWS IAM Identity Center, and JWKS endpoints are all config-driven external services. | ✅ Aligned | — |
| AWS Well-Architected — Operational Excellence | Managed services operational burden | AWS IAM Identity Center is an AWS-managed service; Google Workspace Directory API is a Google-managed service. Using managed identity services reduces undifferentiated operational burden. | ✅ Aligned | — |
| Hexagonal Architecture — Ports and Adapters | Port/adapter pattern for identity | IdentityService Protocol (port) is defined in Standard 3. The managed service clients (Google Workspace, AWS Identity Store) are the adapters. Documenting the delegation tier describes what the adapter wraps. | ✅ Aligned | — |

### 2.A Language & Framework Standards

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| PEP 544 — Protocols | Protocol structural subtyping | IdentityServiceProtocol mandate (Standard 3) is unchanged by this amendment. The delegation tier declaration is additive metadata about the backing implementation, not a Protocol contract change. | ✅ Aligned | — |

### 2.D Validation Summary

**Total Standards Checked:** 6
**Aligned with Best Practice:** 6
**Deliberate Deviations:** 0

**High-Level Finding:** 🟢 **Fully Grounded** — All standards checked; no unresolved deviations.

---

## 3. Assumptions Challenged

### Assumption 3.1: IdentityService is correctly classified as Tier 1 despite containing orchestration logic

- **Stated Norm:** "`IdentityService` is classified as Tier 1 (managed service wrappers) in the ADR-0077 Category A delegation tier table."
- **Underlying Assumption:** The delegation tier applies to the dominant backing service strategy, not every line of code. IdentityService's orchestration logic (multi-source resolution priority, conflict handling) is proportional glue, not a separate infrastructure concern.
- **Challenge:** Could the orchestration logic constitute a Tier 3 (custom) concern that should be declared separately?
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** No — Codebase verification confirms:
  - `app/infrastructure/identity/service.py` is a thin facade wrapping `IdentityResolver`
  - `app/infrastructure/identity/resolver.py` contains resolution logic that selects among managed service backends (JWT/JWKS, Slack API, webhooks)
  - The resolution logic is coordination/routing, not identity provider implementation. It does not implement user authentication, directory queries, or credential validation — those are delegated to managed services.
  - ADR-0077's delegation tier assessment already classified this as Tier 1, and the precedent set by `RetryProcessor` (Tier 3 — custom orchestration of feature-specific retry semantics) is distinguishable: `RetryProcessor` implements domain-specific retry coordination logic that no managed service covers, whereas IdentityService's resolution logic routes to managed identity APIs.
- **Confidence (ADR survives challenge):** 🟢 High
- **Reviewer Notes:** The distinction between "orchestration over managed services" (Tier 1) and "custom domain-specific logic" (Tier 3) is well-drawn. The ADR-0077 Category A table's existing classification provides upstream authority.

### Assumption 3.2: All current identity resolution backends are managed services

- **Stated Norm:** "The identity resolution backends all delegate to managed external service APIs."
- **Underlying Assumption:** JWT/JWKS endpoints, Slack API, and webhook payload sources are all managed external services.
- **Challenge:** Are there any identity resolution paths that use custom (non-managed) logic?
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** Partial — Codebase verification reveals:
  - **JWT/JWKS validation:** ✅ Managed service endpoints. `JWKSManager` creates `PyJWKClient` per issuer; keys fetched from managed JWKS URIs.
  - **Slack identity resolution:** ✅ Slack API is a managed external service. Platform-specific resolution mapping is Category C per ADR-0078.
  - **Webhook payload identity:** ✅ Extracts claims from payloads signed by managed external services.
  - **System identity (background jobs):** Synthetic user — no external service call. This is a degenerate case (no backing service), not a Tier 3 concern.
  - **Dev bypass token:** Local-only dev convenience. Not a production path.
  - **Note:** Google Workspace Directory API and AWS Identity Store are NOT part of IdentityService's resolution path. The DirectoryProvider (IDP — source of truth) is a separate Category A concern. AWS Identity Store is a sync target in the access domain, not an identity resolution backend.
- **Confidence (ADR survives challenge):** 🟢 High
- **Reviewer Notes:** Domain boundary is correctly drawn: IdentityService resolves *who is calling* from interaction context; DirectoryProvider governs *canonical user directory*; access sync governs *IDP → third-party mapping*.

### Assumption 3.3: Adding a Delegation Tier column to Standard 5 is meaningful for Category C services

- **Stated Norm:** Standard 5 table adds a Delegation Tier column with "N/A" for Category C services.
- **Underlying Assumption:** Delegation tiers apply only to Category A services; marking Category C as N/A is informative.
- **Challenge:** Is the N/A column adding noise without information value?
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** No — The column serves two purposes: (1) it highlights that `IdentityService` (the only Category A service in the table) has a declared tier, and (2) it preempts the question "what about Category C services?" by explicitly stating they are out of scope for delegation tier governance. This is consistent with ADR-0077's approach where only Category A services have delegation tiers.
- **Confidence (ADR survives challenge):** 🟢 High

---

## 4. Failure Modes Identified

No assumptions scored Moderate or Low confidence. No failure modes identified for the amended sections.

---

## 5. Contradiction Audit

### Cross-ADR Contradictions

| Conflict | ADRs Involved | Severity | Resolution Status |
|----------|---------------|----------|-------------------|
| None identified | — | — | — |

The amendment is a direct cascade of ADR-0045 P7 → ADR-0077 delegation tier → ADR-0061 identity domain. No conflicting claims exist in other ADRs.

### Supersession Ambiguities

- **ADRs this one supersedes:** ADR-0023, ADR-0024 (unchanged by this amendment)
- **Inheritance Status:** All inherited constraints acknowledged
- **Gaps Identified:** None

### Ownership Clarity

- **Primary Domain Owner:** SRE Team
- **Config Owner:** Identity settings (Standard 4 — unchanged by this amendment)
- **Audit Result:** ✅ Clear

---

## 6. Scenario Validation Matrix

### Scenario 6.2: Access Synchronization Workflow

| Aspect | ADR Requirement | Workflow Reality | Gap? | Notes |
|--------|-----------------|------------------|------|-------|
| Identity provider delegation tier | Standard 3: Tier 1 managed service wrappers | Access sync resolves identities via Google Workspace Directory API and AWS Identity Store API — both managed services | ✅ No | Tier 1 classification matches operational reality |
| Future provider addition | Standard 3: Tier 3 requires justification | If a new identity provider with no managed API is needed, the ADR requires explicit justification | ✅ No | Governance path is clear |

**Validation Summary:** ✅ Fully aligned

### Scenario 6.4: Multi-Provider Integration (Slack/Teams/AWS/GWS/GitHub)

| Aspect | ADR Requirement | Integration Reality | Gap? | Notes |
|--------|-----------------|---------------------|------|-------|
| Multi-source resolution with managed backends | Standard 3: orchestration over Tier 1 backends | IdentityService resolves from JWT, Slack, webhook sources — all backed by managed APIs or managed JWKS endpoints | ✅ No | Platform-specific resolution (Slack) is Category C per ADR-0078 |
| Delegation tier in classification table | Standard 5: Tier column for Category A, N/A for Category C | Table correctly classifies IdentityService as Tier 1; platform clients as Category C / N/A | ✅ No | Consistent with ADR-0077 classification |

**Validation Summary:** ✅ Fully aligned

---

## 7. Tradeoffs Accepted

### Tradeoff 7.1: Single Tier Classification vs. Composite Tier Declaration

- **Chosen:** Single Tier 1 classification for IdentityService based on dominant backing service strategy
- **Rejected:** Composite declaration (e.g., "Tier 1 backends + Tier 2 orchestration")
- **Rationale:** ADR-0077 delegates tier to the *primary backing service abstraction*. The orchestration logic is proportional coordination, not a separate infrastructure concern. Composite declarations would add complexity without actionable governance value.
- **Risk Accepted:** If orchestration logic grows significantly, the single-tier classification may understate the custom code burden.
- **Contingency:** If orchestration complexity exceeds proportionality, re-evaluate as Tier 3 with justification per ADR-0045 P7.

---

## 8. Follow-Up Actions

| Action | Blocker? | Owner | Due Date | Description |
|--------|----------|-------|----------|-------------|
| Update change log | ❌ No | SRE Team | 2026-04-30 | Record the delegation tier amendment in the ADR change log |
| Update tracker Item #22 | ❌ No | SRE Team | 2026-04-30 | Mark Item #22 as PASS in the managed services delegation review tracker |

---

## 9. Binary Gate Outcome

**GATE DECISION:**

⚪ **PASS** → ADR-0061 delegation tier declaration amendment is sound and ready for acceptance.

**Rationale:** The amendment is a targeted cascade of ADR-0045 P7 and ADR-0077 Category A delegation tier requirements to the identity domain. All identity resolution backends are confirmed as Tier 1 (managed cloud services) through codebase verification. The orchestration logic is proportional and does not constitute a separate Tier 3 concern. No contradictions, no failure modes, no scenario misalignments.

---

## 10. Reviewer Sign-Off

| Field | Signature/Value |
|-------|-----------------|
| **Reviewer** | Architecture Review (AI-assisted) |
| **Review Date** | 2026-04-30 |
| **Scope** | Amended sections only (Standard 3 delegation tier, Standard 5 table, Compliance delegation impact) |

---

## 11. Review Artifacts Reference

- **ADR amended:** [ADR-0061](../adr/0061-identity-and-external-integration-contract-standard.md)
- **Upstream authority:** [ADR-0045 P7](../adr/0045-core-architectural-principles.md), [ADR-0077 Standard 1](../adr/0077-infrastructure-service-contract-standard.md)
- **Tracker item:** managed-services-delegation-adr-review-tracker-2026-04-30.md Item #22
- **Codebase evidence:** `app/infrastructure/identity/service.py`, `app/infrastructure/identity/resolver.py`, `app/infrastructure/security/jwks.py`
- **Domain boundary clarification:** IdentityService = interaction identity resolution; DirectoryProvider = IDP; access sync = IDP → third-party targets (separate domain)
