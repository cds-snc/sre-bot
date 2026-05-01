# ADR Program Change Log

**Purpose:** Append-only audit trail of actions taken during the ADR program. Each entry records what changed, when, and why.

---

## 2026-04-28

### ADR-0044 — Governance Baseline

- Created `adr/0044-adr-governance-operating-model.md` (Tier-0). Accepted.

### Steps 1–4 — Program Setup

- Step 1: Established Tier-0 governance baseline (ADR-0044).
- Step 2: Finalized ADR metadata template (18 required fields) at `templates/adr-metadata-reference.md`.
- Step 3: Deployed review-state automation (`.github/scripts/update_adr_review_states.py`).
- Step 4: Built canonical migration map — 100% legacy ADR inventory dispositioned (43 records).

### Wave 1 — Tier-1 Principles + Tier-2 Standards

- Authored ADR-0045 through ADR-0050.
- Challenge reviewed all 6 ADRs (Round 1 + Round 2). All PASS.
- ADR-0045: Principle 2 revised (delegate mechanism to ADR-0048).
- ADR-0047: Principle 1 revised (migration exception clause).
- ADR-0049: Standard 6 revised (transient retry guidance); Standard 7 revised (discovery contract).

### Wave 2 — Taxonomy + Delivery Standards

- Authored ADR-0051 through ADR-0054.
- Challenge reviewed all 4 ADRs (Round 1 + Round 2). All PASS.
- ADR-0053: Round 1 REVISE → revised → Round 2 PASS.

---

## 2026-04-29

### Action 0 — Waves 1–2 Housekeeping

- Marked 15 legacy ADRs as `status: Superseded` with `superseded_by` links (ADR-0001 through ADR-0013, ADR-0017, ADR-0020, ADR-0026, ADR-0027).
- Moved 21 superseded ADRs to `adr/superseded/` (18 newly superseded + 3 previously superseded: ADR-0019, ADR-0029, ADR-0032).
- Replaced external planning document references in 5 ADRs (ADR-0044, ADR-0045, ADR-0048, ADR-0055, ADR-0077) with inline summaries.
- Updated 7 superseded file URL paths in ADR-0045 through ADR-0055.
- Updated ADR-0047 metadata: added `related_packages: [app/packages/access]`.
- Reclassified ADR-0008: tier Tier-1→Tier-3, decision_type Principle→Pattern.

### Action 1 — Wave 3 Mapping Reassessment

- ADR-0055 scope expanded from "Configuration Source Ordering" to "Settings Implementation and Dissolution Standard".
- ADR-0056 scope confirmed. ADR-0025 reassigned from ADR-0056 to ADR-0078 (Platform Services Architecture).
- ADR-0057, ADR-0058 confirmed independent of decentralization work.
- ADR-0065 sequencing confirmed as Wave 5 (not pulled forward).
- Migration map updated with Wave 3 expanded scope annotations.

### Wave 3 — Settings + Providers + Infrastructure

- Authored ADR-0055 (Settings Implementation and Dissolution Standard, 7 standards). R1 PASS.
- Authored ADR-0056 (Provider Discovery and Composition Standard, 7 standards). R1 PASS. Editorial: added MaxMindClient to violations table, fixed provider count (17, not 16).
- Authored ADR-0076 (Infrastructure Intra-Layer Import Standard). R1 PASS. Created during ADR-0056 review when ADR-0048 B5 found to have zero external evidence (61% violation rate). B5 refined into three-part standard.
- Authored ADR-0077 (Infrastructure Service Contract Standard). R1 PASS. Three-tier classification (A/B/C). Added PEP 544 caveat to Rule P1.
- Amended ADR-0045: added Principle 6 (Protocol-Driven Service Contracts). Amended Principle 3 (infrastructure as shared service platform).
- Amended ADR-0048: renamed B5 to "Infrastructure Composition Governance", added B7 (Protocol Contract Surface), extended B2 (Protocol type at injection surface).
- Amended ADR-0056: added ADR-0077 reference to Compliance and Boundaries section.
- Root cause analysis completed for ADR-0048 B5 misapplication — plugin isolation rule was incorrectly applied to infrastructure service layer.
- Round 2 skipped for all 4 Wave 3 ADRs (no normative revisions from R1).

### Wave 3 Downstream Assessment

- Systematic impact assessment of Wave 3 ADRs against 10 downstream targets.
- Migration map updated with Wave 3 constraint annotations for Waves 4–6.

### Wave 3.5 — Tier-5 Feature Settings

- Authored ADR-0070 (GroupsFeatureSettings Retirement — deprecation).
- Authored ADR-0071 (CommandsSettings Retirement — deprecation). Unblocked by Platform Services Assessment.
- Authored ADR-0072 through ADR-0075 (IncidentFeatureSettings, AWSFeatureSettings, AtipSettings, SreOpsSettings — migration).

### Wave 4 — API + Platform + Queueing

- Revised ADR-0059 (Feature Interaction Boundaries). Removed rejected Standards 1–3 (InteractionProvider Protocol), renumbered, added Standards 4–6. R1 REVISE → R2 APPROVE.
- Authored ADR-0078 (Platform Services Architecture, supersedes ADR-0025). R1 REVISE→PASS.
- Authored ADR-0060 (API Response and Error Mapping). R1 REVISE (4 blockers: supersession cascade, factual error, missing ADR-0063, ungoverned app/api/) → R2 PASS.
- Pull-forward: ADR-0063 moved from Wave 5 to Wave 4 to unblock ADR-0060. Authored. R1 REVISE → R2 PASS.
- Authored ADR-0061 (Identity and External Integration Contract). Status: Draft. R1 pending.
- Authored ADR-0079 (Queueing and Message-Broker Architecture). Status: Draft. R1 REVISE (phase numbering errors, shutdown ordering). R2 pending.
- Wave 4 downstream assessment completed. Migration map updated with Wave 4 constraint annotations.

### Supporting Analyses Completed

- Root cause analysis for ADR-0048 B5 misapplication — plugin isolation rule incorrectly applied to infrastructure service layer.
- Platform services assessment — rejected InteractionProvider Protocol; defined per-platform concrete service model.
- Interaction provider abstraction analysis — input for platform services decision.
- Legacy feature rearchitecting assessment — coupling analysis for Tier-5 ADR sequencing.

### ADR-0079 — Revision and R2

- Revised ADR-0079: corrected 5 lifecycle phase number references to match ADR-0046 Invariant 2 (Phase 4 for feature activation, Phase 5 for transport, shutdown step 2 for transport teardown).
- Fixed shutdown ordering: queue consumers stop in shutdown step 2 (reverse of Phase 5), not "shutdown phase 1 (first to stop)".
- Fixed factual error: background job scheduler thread is non-daemon (no `daemon=True` set on `ScheduleThread`).
- Fixed NotificationService classification wording: "ADR-0077 Category A P2" → "ADR-0077 P2 migration candidate".
- Added ADR-0079 to ADR-0058 `related_records` metadata.
- R2 challenge review: PASS. Saved to `reviews/adr-0079-review-2026-04-29-r2.md`.

---

## 2026-04-30

### Managed Services Delegation — Cross-Wave Review

- Trigger: ADR-0079 R2 review revealed a missing Tier-1 foundational principle governing managed service delegation.
- Managed services delegation framework analysis completed: three-tier delegation model (managed cloud service → industry library → custom implementation).
- Delegation review tracker established: 25 items across 4 phases (3 HIGH, 5 MEDIUM, 3 LOW, 12 NONE, 2 NEW).

### ADR-0045 — P7 Amendment (Managed Service Delegation Hierarchy)

- Amended ADR-0045: added Principle 7 (Managed Service Delegation Hierarchy). Three-tier model: managed cloud service → industry library → custom implementation. Completes P6 (Protocol contracts govern the port shape; P7 governs what sits behind the adapter).
- Updated metadata: `last_updated`, `last_reviewed`, `next_review_due`, `impacts` (added ADR-0054, ADR-0055, ADR-0056, ADR-0079).
- Updated Alternatives §2, Consequences (delegation evaluation tradeoff), Compliance (managed service delegation impact), Revalidation (3 new sources: AWS Well-Architected, GC Cloud Adoption Strategy, Twelve-Factor IV), Source References (3 new entries: §7–§9).
- Challenge review (amendment, normative): PASS. Saved to `reviews/adr-0045-review-2026-04-30.md`.
- Delegation tracker Item #1 marked PASS.

### ADR-0047 — P6 Amendment (Backend-Selection Configuration)

- Amended ADR-0047: added Principle 6 (Backend-Selection Configuration). When infrastructure services support multiple backing implementations (ADR-0045 P7), selection must be driven by a dedicated configuration key with dev-safe defaults.
- Updated metadata: `last_updated`, `last_reviewed`, `next_review_due`, `impacts` (added ADR-0079), `related_records` (added ADR-0077).
- Updated Consequences, Compliance (backend-selection impact), Revalidation (added Factor IV, GC Cloud Adoption Strategy), Source References (2 new entries: §4–§5).
- Challenge review (amendment, normative): PASS. Saved to `reviews/adr-0047-review-2026-04-30.md`.
- Delegation tracker Item #2 marked PASS.

### ADR-0044 — Tier-5 Library Trigger Amendment

- Amended ADR-0044: added infrastructure library adoption as an explicit Tier-5 ADR trigger category alongside existing migration/deprecation trigger. Complements ADR-0045 P7 (Managed Service Delegation Hierarchy) by ensuring Tier-2 library selections are formally governed.
- Updated metadata: `last_updated`, `last_reviewed`, `next_review_due`.
- Challenge review (amendment, normative): PASS. Saved to `reviews/adr-0044-review-2026-04-30.md`.
- Delegation tracker Item #3 marked PASS.

### ADR-0046 — Delegation Review (Verify Only)

- Reviewed ADR-0046 Invariant 2, Phase 2 ("Infrastructure — Initialize core platform services and capabilities") for managed service delegation alignment.
- Assessment: no amendment needed. Wording is already sufficiently abstract to accommodate managed service SDK clients, library-wrapped services, and custom implementations. Phase ordering (config first → infra second) ensures `*_BACKEND` settings are available before backend client instantiation. Reverse shutdown (Invariant 4) correctly handles managed service client cleanup.
- Delegation tracker Item #4 marked Verified.

### ADR-0048 — Delegation Review (Verify Only)

- Reviewed ADR-0048 Boundary 7 (Protocol Contract Surface) for managed service delegation alignment.
- Assessment: no amendment needed. B7 governs the port shape (Protocol contract surface) while P7 governs what sits behind the adapter — they are complementary, not overlapping. B7 already defers service classification and Protocol migration priorities to ADR-0077, which is where the delegation tier declaration will be added (Item #6). The reference chain B7 → ADR-0077 → P7 is already intact; adding a direct P7 forward-reference would be redundant.
- Delegation tracker Item #5 marked Verified.

### ADR-0077 — Delegation Tier Declaration Amendment

- Amended ADR-0077: added delegation tier declaration requirement to Standard 1 Category A classification per ADR-0045 P7. Each Category A service now documents its delegation tier (Tier 1: managed service, Tier 2: industry library, Tier 3: custom code). Tier 3 declarations require justification. Added Delegation Tier column to Category A table with current assessments for all 10 services.
- Updated metadata: `last_updated`, `last_reviewed`, `next_review_due`, `related_records` (added ADR-0079).
- Updated Compliance section: added managed service delegation impact cross-referencing ADR-0045 P7, ADR-0047 P6, ADR-0054, ADR-0055, ADR-0056.
- Updated Freshness Review: validation summary references P7 amendment.
- Challenge review (amendment, normative): PASS. Saved to `reviews/adr-0077-review-2026-04-30.md`.
- Delegation tracker Item #6 marked PASS.

### ADR-0056 — Backend-Selection Logic Amendment

- Amended ADR-0056: added Standard 8 (Backend-Selection Logic in Providers) formalizing the settings-driven factory pattern for Category A services with configurable backends. Codifies the if/elif/else branching on `*_BACKEND` settings keys with 7 rules (B1-B7) covering settings key sourcing, Literal typing, dev-safe defaults, error handling, Protocol return types, conditional dependencies, and extraction guidance.
- Updated metadata: `last_updated`, `last_reviewed`, `next_review_due`, `related_records` (added ADR-0055).
- Updated Compliance section: added backend-selection impact cross-referencing ADR-0045 P7, ADR-0047 P6, ADR-0055.
- Updated Best-Practice Revalidation alignment summary: added Abstract Factory pattern reference.
- Reference implementation: `app/infrastructure/resilience/retry/factory.py`.
- Challenge review (amendment, normative): PASS. Saved to `reviews/adr-0056-review-2026-04-30.md`.
- Delegation tracker Item #7 marked PASS.

### ADR-0055 — Backend-Selection Settings Pattern Amendment

- Amended ADR-0055: added Standard 9 (Backend-Selection Settings Pattern) formalizing `*_BACKEND` as a recognized settings pattern with `Literal` typing, dev-safe defaults (K3), infrastructure ownership (K5), and dissolution accounting (§9.3) for existing keys (`RETRY_BACKEND`, `RECONCILIATION_BACKEND`).
- Updated metadata: `last_updated`, `last_reviewed`, `next_review_due`, `related_records` (added ADR-0045, ADR-0077).
- Updated Compliance section: added backend-selection settings impact cross-referencing ADR-0045 P7, ADR-0047 P6, ADR-0056 S8.
- Reference implementation: `app/infrastructure/configuration/infrastructure/retry.py`.
- Challenge review (amendment, normative): PASS. Saved to `reviews/adr-0055-review-2026-04-30.md`.
- Delegation tracker Item #8 marked PASS.

### ADR-0054 — Dev/Test Fallback Standard Amendment

- Amended ADR-0054: added dev/test fallback standard requiring every Category A service (ADR-0077) to provide an in-memory or local fallback implementation. Defines 5 rules (F1-F5) covering Protocol satisfaction, settings-driven selection, functional equivalence, SDK isolation, and test override compatibility. Includes current fallback status table for all 10 Category A services (5 have fallbacks, 5 need them).
- Updated metadata: `last_updated`, `last_reviewed`, `next_review_due`, `constrained_by` (added ADR-0045), `related_records` (added ADR-0055, ADR-0056, ADR-0077).
- Updated Compliance section: added dev/test fallback impact cross-referencing ADR-0045 P7, ADR-0055 S9, ADR-0056 S8, ADR-0077.
- Challenge review (amendment, normative): PASS. Saved to `reviews/adr-0054-review-2026-04-30.md`.
- Delegation tracker Item #9 marked PASS.

### ADR-0051 — Library Adoption Decision Type Amendment

- Amended ADR-0051: added `Library Adoption Decision` as a valid Tier-5 decision_type alongside `Migration Decision` and `Deprecation Decision`. Infrastructure library selections per ADR-0045 P7 delegation hierarchy require formal evaluation via Tier-5 ADR.
- Updated metadata reference template (`templates/adr-metadata-reference.md`): added `Library Adoption Decision` to decision_type catalog and Tier-5 compatibility row.
- Updated metadata: `last_updated`, `last_reviewed`, `next_review_due`, `related_records` (added ADR-0077).
- Challenge review (amendment, normative): PASS. Saved to `reviews/adr-0051-review-2026-04-30.md`.
- Delegation tracker Item #10 marked PASS.

### ADR-0079 — Managed Service Delegation Rework

- Reworked ADR-0079: narrowed Standards 1/3/4/5/6 and reframed Standard 7 to align with ADR-0045 P7 delegation hierarchy. Standard 1 narrowed from pre-defined `MessageProducer`/`MessageConsumer`/`MessageEnvelope` Protocols to queue integration standard that lets Protocol shape emerge from wrapping the managed service SDK. Standards 3/4 narrowed from prescriptive app-level standards to posture statements (delivery semantics and DLQ are the managed service's responsibility). Standard 5 simplified to essential lifecycle integration points (start/stop/pluggy registration). Standard 6 narrowed from 5 settings keys to 2 backend-selection keys (`QUEUE_BACKEND`, `QUEUE_ENDPOINT_URL`). Standard 7 evolution phases reframed around managed service adoption. Standard 2 (event dispatcher remediation) unchanged.
- Updated metadata: `last_updated`, `last_reviewed`, `next_review_due`, `related_records` (added ADR-0045).
- Updated Compliance section: added managed service delegation impact.
- Updated Codebase Audit: deferred actions table aligned with narrowed standards.
- Updated Best-Practice Revalidation: alignment summary updated for all revised standards.
- Challenge review (rework, normative): PASS. Saved to `reviews/adr-0079-review-2026-04-30.md`.
- Delegation tracker Item #11 marked PASS.

### Phase 3 — Downstream Records (Tier-3 / Tier-5)

### ADR-0061 — Delegation Tier Declaration Amendment

- Amended ADR-0061: added delegation tier declaration to Standard 3 (IdentityService Protocol Contract) per ADR-0045 P7. IdentityService classified as Tier 1 (managed service wrappers) — identity resolution delegates to managed APIs (JWT/JWKS endpoints, Slack API, webhook payloads). Added explicit domain boundary clarification: IdentityService governs interaction identity resolution only; IDP (source of truth) is governed by DirectoryProvider Protocol; access sync (IDP → third-party targets like AWS Identity Store) is governed by the access package.
- Corrected ADR-0077 Category A table: IdentityService delegation tier description updated from "Google Workspace, AWS IAM Identity Center" to "JWT/JWKS endpoints, Slack API" — AWS Identity Store is a sync target, not an identity resolution backend.
- Added Delegation Tier column to Standard 5 (External Integration Client Classification) table. Category A service (`IdentityService`) has Tier 1 declaration; Category C services marked N/A.
- Added managed service delegation impact to Compliance and Boundaries section.
- Updated metadata: `last_updated`, `last_reviewed` to 2026-04-30. Updated freshness review record age.
- Added Amendment Record section at end of ADR.
- Challenge review (amendment, normative): PASS. Saved to `reviews/adr-0061-review-2026-04-30-r2.md`.
- Delegation tracker Item #22 marked PASS.

### ADR-0070–0075 — Tier-5 Settings Migrations (Verified)

- Items #23 in delegation tracker: no delegation impact. Feature settings migrations are domain-specific and do not involve infrastructure service backing. Already verified during Phase 2.

### ADR-0044 — License Compatibility Amendment

- Amended ADR-0044: strengthened library evaluation criterion. Library licenses must be compatible with the project’s own license (currently MIT); incompatible licenses are grounds for rejection regardless of technical merit. Editorial change — clarifies existing "licensing" criterion, no normative review needed.

### Delegation Tracker Phase 4 — Library ADRs Deferred

- Items #24 (`pybreaker`) and #25 (`tenacity`) deferred. Custom implementations (~300 LOC circuit breaker, ~400 LOC in-process retry) are accepted as proportional Tier 3 interim. Justification: both are flagged for future delegation to managed services (Tier 1) rather than intermediate library adoption (Tier 2). Adding library dependencies for concerns that will ultimately be delegated to SQS, EventBridge, or equivalent managed services introduces transitional overhead without long-term benefit.
- Delegation tracker completion criteria updated: 6/7 checked; migration map check pending.
- Delegation tracker completion criteria: 7/7 checked — no new supersession relationships from delegation amendments.

### ADR-0061 — Challenge Review R1 and Acceptance

- Challenge review R1: PASS. Saved to `reviews/adr-0061-review-2026-04-30.md`.
- 6 standards grounded in 12 authoritative sources. 6 assumptions challenged, all High confidence. Zero cross-ADR contradictions. 4 workflow scenarios validated.
- Status changed: Draft → Accepted.

### ADR-0079 — Post-Rework Full Challenge Review and Acceptance

- Prior R2 PASS (2026-04-29) was issued before the managed service delegation rework (2026-04-30) which substantially revised 5 of 7 standards. Fresh full challenge review required.
- Post-rework challenge review: PASS. Saved to `reviews/adr-0079-review-2026-04-30-r2.md`.
- 7 standards grounded in 13 authoritative sources. 6 assumptions challenged, all High confidence. Zero cross-ADR contradictions. 3 scenarios validated.
- Status changed: Draft → Accepted.

### Wave 4 Legacy Supersession

- Marked 9 legacy ADRs as Superseded and moved to `adr/superseded/`:
  - ADR-0022 (Response Format Abstraction) → superseded by ADR-0060
  - ADR-0023 (Identity Resolution) → superseded by ADR-0061
  - ADR-0024 (External Service Integration) → superseded by ADR-0061
  - ADR-0033 (Route Organization) → superseded by ADR-0063
  - ADR-0034 (Validation Patterns) → superseded by ADR-0063
  - ADR-0035 (HTTP Response Patterns) → superseded by ADR-0060
  - ADR-0036 (Dual-Interface Error Handling) → superseded by ADR-0060
  - ADR-0039 (Middleware & Request Pipeline) → superseded by ADR-0063
  - ADR-0041 (OpenAPI Documentation Standards) → superseded by ADR-0063
- Note: ADR-0025 was superseded by ADR-0078 during Wave 3 (2026-04-29).

### Wave 4 Gate Close

- All Wave 4 items complete: ADR-0059 (R2 PASS), ADR-0060 (R2 PASS), ADR-0061 (R1 PASS), ADR-0063 (R2 PASS), ADR-0078 (R1 PASS), ADR-0079 (post-rework PASS).
- 9 legacy ADRs superseded and moved.
- Wave 4 gate closed. Wave 5 opened.

### Wave 5 — ADR-0065 Accepted

- Authored ADR-0065 (Type-Model Boundaries Canonical Principle, Tier-1, 5 principles). R1 PASS. Accepted.
- Supersedes ADR-0040 (Type Model Boundaries, Tier-4 Feature). ADR-0040 metadata updated (`status: Superseded`, `superseded_by: [ADR-0065]`), moved to `adr/superseded/`.
- Cross-reference updates: ADR-0040 → ADR-0065 references updated in ADR-0043 (constrained_by, related_records), ADR-0055 (related_records, 3 inline refs), ADR-0056 (1 inline ref), ADR-0060 (2 inline refs), ADR-0061 (2 inline refs), ADR-0063 (1 inline ref), ADR-0079 (1 inline ref).
- Migration map updated: ADR-0065 status → Accepted; ADR-0040 added to Superseded Legacy table.
- Wave tracker updated: Item 3 (ADR-0065) marked PASS; Item 4 (legacy supersession) marked Complete.

### Wave 5 — ADR-0062 R1 Review + Revision

- Authored ADR-0062 (Testing and Request Context Quality, Tier-2, 12 standards). Status: Draft.
- Challenge review R1: REVISE. Two blockers: (1) Standard 7 pytest-asyncio `auto` mode underspecified (default is `strict`); (2) Standard 10 missing structlog sync/async contextvars isolation caveat.
- Revision applied same-day: Standard 7 added configuration-dependency callout (opt-in `auto`, `pytest.ini` reference, pinned version). Standard 10 added sync/async isolation caveat blockquote with three mitigations.
- R1 review updated to ACCEPT. Review artifact: `reviews/adr-0062-review-2026-04-30.md`.
- ADR-0065 dependency verification (non-blocking follow-up): Resolved. ADR-0065 P2 confirms ADR-0062 S4's Category A Protocol stub requirement.
- ADR-0062 awaiting user acceptance decision (Step 5).

### Wave 5 — ADR-0062 Accepted

- ADR-0062 accepted by user (Step 5 → Step 6). Status set to `Accepted`.
- Superseded ADR-0030 (Testing Standards): metadata updated (`status: Superseded`, `superseded_by: [ADR-0062]`), moved to `adr/superseded/`.
- Superseded ADR-0031 (Request ID Propagation): metadata updated (`status: Superseded`, `superseded_by: [ADR-0062]`), moved to `adr/superseded/`.
- Cross-reference updates: ADR-0031 → ADR-0062 in ADR-0037 (related_records), ADR-0054 (related_records).
- Migration map updated: ADR-0062 status → Accepted; ADR-0030 and ADR-0031 added to Superseded Legacy table.
- Wave tracker updated: Item 1 (ADR-0062) marked Accepted.

### Wave 5 — ADR-0064 Accepted

- Authored ADR-0064 (Security and Rate-Limiting API Protection, Tier-2, 10 standards). Status: Draft.
- Challenge review R1: PASS. 12/12 external standards aligned (OWASP, FastAPI, PyJWT, SlowAPI, RFC 9457, RFC 7519). 5 assumptions challenged (4 high, 1 moderate confidence). 1 deliberate deviation from ADR-0045 P4 (degraded-start) documented with rationale. Review artifact: `reviews/adr-0064-review-2026-04-30.md`.
- ADR-0064 accepted by user (Step 5 → Step 6). Status set to `Accepted`.
- Superseded ADR-0037 (Security & Authentication): metadata updated (`status: Superseded`, `superseded_by: [ADR-0064]`), moved to `adr/superseded/`.
- Superseded ADR-0038 (Rate Limiting): metadata updated (`status: Superseded`, `superseded_by: [ADR-0064]`), moved to `adr/superseded/`.
- Cross-reference impact: No live ADRs reference ADR-0037 or ADR-0038 (only superseded ADR-0023 and ADR-0039). No updates needed.
- Migration map updated: ADR-0064 status → Accepted; ADR-0037 and ADR-0038 added to Superseded Legacy table.
- Wave tracker updated: Item 2 (ADR-0064) marked Accepted; Item 6 (legacy supersession) marked Complete.

### Wave 5 — Gate Closed

- All three Wave 5 ADRs accepted: ADR-0062, ADR-0064, ADR-0065.
- All Wave 5 legacy supersessions complete: ADR-0037, ADR-0038, ADR-0040 moved to `adr/superseded/`.
- Wave 5 gate closed. Wave 6 opened.

### Wave 6 — ADR-0043 Rejection and ADR-0058 Amendment

- **Pre-author gate analysis:** Identified ADR-0043 (Proposed) contradicts ADR-0058 Standard 4 (infrastructure utility mandate for singleton locks). Feature-scoped lock release in `access/admin` violates established platform boundaries.
- **ADR-0058 Standard 9 amendment:** Added Standard 9 (Singleton Lock Lifecycle and Operator Intervention). 6 rules: R1 (infrastructure ownership), R2 (TTL as primary recovery), R3 (structured lock observability events), R4 (operator release utility), R5 (feature admission vs infrastructure release boundary), R6 (no feature admin packages for lock management). Updated Compliance, Consequences, Source References (§11-§12), metadata.
- **ADR-0058 Standard 9 challenge review:** PASS. One factual error corrected during review (R5 incorrectly cited ADR-0059 Standard 2 for background job admission; removed incorrect cross-reference). Review artifact: `reviews/adr-0058-review-2026-04-30.md`.
- **ADR-0043 rejected:** Status changed from Proposed to Rejected. Rejection rationale: contradicts ADR-0058 Standard 4 and Standard 9. Change log entry added to ADR-0043.
- **ADR-0066 authored (Draft):** Supersedes ADR-0042 (env-source naming) with canonical Tier-4 structure. Single decision: `ACCESS_CONFIG_ENV_*` naming rule.
- **ADR-0066 narrowed:** Removed Decision 2 (operator lock intervention scope). Lock lifecycle boundaries are fully governed by ADR-0058 Standard 9 — restating them in a Tier-4 record was inverted authority. ADR-0043 rejection stands independently via its own `status: Rejected` + ADR-0058 Standard 9. Title changed from "Access Runtime Naming and Operator Scope" to "Access Config Env-Source Naming".
- **ADR-0066 challenge review R1:** PASS. 4 standards checked, all aligned. 3 assumptions challenged (all High confidence). Zero cross-ADR contradictions. Review artifact: `reviews/adr-0066-review-2026-04-30.md`.
- **ADR-0066 awaiting user acceptance decision (Step 5).**
- Migration map updated: ADR-0066 status Deferred → Draft; title updated; legacy ref narrowed to 0042 only.
- Wave tracker updated: ADR-0066 title and scope updated.

### Feature-Level ADR Structure Migration Analysis

- Completed feature-level ADR structure migration analysis.
- Identified legacy mixed-concern anti-pattern: ADR-0014, ADR-0042, ADR-0043 each conflate multiple tiers into single records.
- Established Tier-4 derivation methodology: 4-point Derivation Test (tier-bleed, constraint chain, single-concern, domain-specificity).
- Established complex-feature scoping rules: one ADR per sub-feature concern, shared concerns separate, ADR-per-decision not ADR-per-package.
- Feature ADR gap assessment completed: P1 (Access/Sync, Access/Request), P2 (Slack Transport/ADR-0067), P3 (Incident, AWS Ops), P4 (SRE Ops, ATIP, Geolocate).
- Defined 4-phase migration execution order with freeze zone discipline (7 rules, F1–F7).
- **Template updated:** Added mandatory "Derivation from Higher-Tier ADRs" section to `templates/decision-record-template.md` for Tier-4 ADRs (Constraint Derivation Table, Feature-Specific Decisions table, Derivation Test Checklist, Scoping Rules).
- **Workflow updated:** Added Tier-4 Feature ADR Derivation section to `references/adr-authoring-workflow.md` (Derivation Test, Scoping Rules, Mixed-Concern Anti-Pattern, Freeze Zone Discipline, Migration Execution Order). Pre-Author Gate and Draft steps updated with Tier-4 callouts.
- **Wave tracker updated:** Added Feature ADR Derivation Methodology note to Wave 6, Feature ADR Gap Assessment section (prioritized backlog, legacy supersession table, migration execution phases, frozen zones inventory).
- **Migration map updated:** Replaced stale "Pending Supersession (Wave 4)" with "Pending Supersession (Wave 6)" (ADR-0042→0066, ADR-0014→0067). Added ADR-0043 rejection note. Added Feature ADR Coverage Gaps table. Completed Superseded Legacy ADRs table (added Wave 4 supersessions: 0022–0025, 0033–0036, 0039, 0041).

### Review Artifact Naming Normalization

- Renamed 57 review files from date-first (`2026-MM-DD-adr-NNNN-*.md`) to ADR-first generic pattern (`adr-NNNN-review-YYYY-MM-DD.md`). `round-2` suffixes normalized to `-r2`. Same-date collisions (main + amendment) resolved with `-r2` suffix.
- Updated authoring workflow: steps 3, 4, and Review Artifact Naming section updated to `adr-NNNN-review-YYYY-MM-DD.md` pattern.
- Updated 17 change log inline references to match new filenames.

### Wave 6 — ADR-0066 Accepted

- ADR-0066 accepted by user (Step 5 → Step 6). Status set to `Accepted`.
- Superseded ADR-0042 (Access Runtime Env-Source Naming): metadata updated (`status: Superseded`, `superseded_by: [ADR-0066]`), moved to `adr/superseded/`.
- No cross-reference updates needed — no other live ADRs reference ADR-0042.
- Migration map updated: ADR-0066 status Draft → Accepted; ADR-0042 added to Superseded Legacy table; removed from Pending Supersession.
- Wave tracker updated: ADR-0066 marked Accepted; next gate updated.

### Comprehensive Feature ADR Migration Integration

Thorough integration of the feature-level ADR structure migration analysis into tracking documents. Gaps identified by audit against analysis (§3.3, §5.1, §6):

**Data integrity fixes (migration map):**

- ADR-0061 status: Draft → Accepted (was accepted during Wave 4; tracking lagged).
- ADR-0079 status: Draft → Accepted (was accepted during Wave 4; tracking lagged).

**Wave tracker — new sections added:**

- **Wave 7 (Planning):** Access sub-feature Tier-4 decisions — Sync reconciliation/adapter, Request state machine/approval, Common event contracts (evaluate), Catalog enumeration (evaluate). Blocked on Phase 1 infrastructure foundation.
- **Wave 8 (Planning):** Legacy module migration Tier-4 decisions — Incident lifecycle, Webhooks architecture, AWS Ops integration. Blocked on Phase 3 thaw. Notes on SRE Ops/ATIP evaluation and one-at-a-time thaw order.
- **Phase 1 — Infrastructure Foundation:** Replaced ad-hoc standalone actions with sequenced 5-item implementation plan (settings dissolution → provider restructuring → service contracts → event dispatcher fix → backward-compatible shim). Dependencies explicit. Stale "blocked on Wave 4 gate" note removed — Wave 4+5 gates closed.
- Wave Status Summary: Added Wave 7 and Wave 8 rows.

**Wave tracker — existing sections updated:**

- Prioritized Feature ADR Backlog: Added Wave column. Added Access/Common event contracts (P1) and Access/Catalog enumeration strategy (P1). Expanded candidate decisions (lock consumption pattern, auto-approval guards, stale-channel notification, health monitoring). All P1 items correctly blocked on Phase 1 (not "None").
- Legacy Feature ADRs table: Renamed from "Pending Supersession" to "Supersession Status". Added Status column. ADR-0042 marked Complete (superseded). ADR-0043 marked Complete (rejected).
- Migration Execution Phases: Added Wave column. Phase 1 prerequisite updated to "Wave 5 gate closed (done)" to reflect current state. Phase 1 scope expanded to include service contracts and backward-compatible shim. Phase 1 marked unblocked.
- Standalone Actions: Added "tracked as Phase 1 Item N" cross-references. Removed stale "blocked on Wave 4 gate" blocker.

**Migration map — updated:**

- Feature ADR Coverage Gaps: Added Wave column. Added Access/Common event contracts, Access/Catalog enumeration, and Webhooks architecture. Expanded candidate decisions to match analysis. P1 items blocked on Phase 1 (not "None"). Cross-reference to wave tracker added.

### HV Review — Redundancy Consolidation

Prose-level redundancy consolidation applied across 7 ADR files based on HV review findings.

**Protocol norm consolidation (H-001, H-002):**

- ADR-0045: Principle 6 (Protocol-Driven Service Contracts) slimmed to brief statement referencing ADR-0065 P2 as canonical.
- ADR-0048: Boundary 7 (Protocol Contract Surface) slimmed to retain unique import-boundary content; references ADR-0065 P2.
- ADR-0065: Principle 2 unchanged (already the most complete).

**OpenAPI consolidation (H-005):**

- ADR-0060: Standard 6 body replaced with reference to ADR-0063 S5 O4.
- ADR-0063: Standard 5 Rule O4 enriched with "concise and client-actionable" detail absorbed from 0060 S6.

**Composition root cross-references (H-007):**

- ADR-0056: Added "see also ADR-0076 Standard 3" after S3 (Infrastructure Provider Centralization).
- ADR-0076: Added "see also ADR-0056 Standard 3" after S3 (Service Composition Must Happen in the Composition Root).

**Degraded-start amendment (H-008):**

- ADR-0046: Invariant 3 (Fail-Fast Startup) amended with Known Exceptions section acknowledging ADR-0064 S5 R5 (security service degraded-start).

**Tracking document updates:**

- HV review finding index, amendment summary, and gate assessment updated. Gate upgraded from CONDITIONAL PASS to PASS.
- Migration map: Added "Cross-Cutting ADR Gaps" section with V-017 (Access Domain Contract, Tier-3, HIGH) and H-009 (API Versioning, Tier-2, DEFERRED).
- Wave tracker: Added Wave 7 Pre-Requisite section for V-017 (Access Domain Contract). Added H-009 and HV redundancy consolidation to Standalone Actions.

---

## 2026-05-01

### ADR-0080 — Application Portability Boundary (Accepted)

- Authored ADR-0080 (Application Portability Boundary, Tier-1, 4 principles). Addresses the structural gap identified when investigating CI/CD pipeline governance questions — no prior ADR defined the boundary between application architecture and hosting infrastructure.
- Principles: (1) Two Governance Domains — application architecture vs. hosting infrastructure; (2) Contract-Based Interface — app ADRs state contracts, infra ADRs define fulfillment; (3) ADR Scope Constraint — application ADRs govern code within the ASGI lifespan only; (4) Portability Invariant — application ADR corpus must survive a full platform change.
- Challenge review R1: PASS. 10 standards checked (all aligned), 4 assumptions challenged (3 high confidence, 1 moderate — infra ADR tier fit deferred as follow-up). Zero unresolved contradictions. 4 scenarios validated. Review artifact: `reviews/adr-0080-review-2026-05-01.md`.
- Status set to Accepted. No legacy supersession — this is a new structural ADR.
- Migration map updated: ADR-0080 status Draft → Accepted.
- Follow-up actions (non-blocking): ADR-0067 scope clarification to reference ADR-0080; ADR-0052 decomposition assessment for infra-specific guidance; ADR-0044 tier assessment when first infra ADR is authored.
