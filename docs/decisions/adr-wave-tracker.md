# ADR Program Wave Tracker

**Purpose:** Track current wave progress and pending actions. Update in-place each cycle.

**Last updated:** 2026-05-04

---

## Current Focus

**Active wave:** Wave 6  
**Parallel activity:** Managed services delegation review — **Complete** (all 7 criteria met)  
**Structural:** ADR-0080 (Application Portability Boundary) — **Accepted** (2026-05-01)  
**Infrastructure:** ADR-0081 (CI/CD Pipeline and Deployment Validation) — **Accepted** (2026-05-01)  
**Infrastructure:** ADR-0082 (Infrastructure Alerting Architecture) — **Accepted** (2026-05-01)
**Library:** ADR-0083 (Event Dispatcher Library Adoption) — **Accepted** (2026-05-04)
**Recent completion:** P1 — Event Dispatcher Library Adoption (ADR-0083) — **Accepted** (2026-05-04)

**Note:** ADR-0066 narrowed from "Access Runtime Naming and Operator Scope" to "Access Config Env-Source Naming". Lock lifecycle scope removed — governed by ADR-0058 Standard 9. ADR-0043 rejection stands independently.

---

## Wave Status Summary

| Wave | Scope | Status |
|------|-------|--------|
| 1 | Tier-1 Principles (0045–0050) | **Complete** |
| 2 | Taxonomy + Delivery (0051–0054) | **Complete** |
| 2.5 | Tier-5 Migrations (0068, 0069) | **Approved** — due 2026-05-12 |
| 3 | Settings + Providers + Infra (0055–0058, 0076, 0077) | **Complete** |
| 3.5 | Tier-5 Feature Settings (0070–0075) | **Complete** |
| 4 | API + Platform + Queueing (0059–0061, 0063, 0078, 0079) | **Complete** |
| 5 | Testing + Security + Type Models (0062, 0064, 0065) | **Complete** |
| 6 | Feature + Integration Decisions (0066, 0067) | **Complete** |
| 7 | Access Sub-Feature Decisions (P1 Tier-4) | Planning — blocked on Phase 1 |
| 8 | Legacy Module Migration Decisions (P3 Tier-4) | Planning — blocked on Phase 3 thaw |

---

## Wave 4 — Closed

| Item | ADR | Action | Status |
|------|-----|--------|--------|
| 1 | 0061 | Challenge review R1 | **R1 PASS** — Accepted |
| 2 | 0079 | Post-rework full challenge review | **PASS** — Accepted |
| 3 | Legacy | Mark 9 legacy ADRs Superseded + move to `superseded/` | **Complete** (0022, 0023, 0024, 0033, 0034, 0035, 0036, 0039, 0041) |
| 4 | — | Wave 4 gate close | **Closed 2026-04-30** |

### Wave 4 Legacy Supersession Summary

| Legacy ADR | Superseded By |
|-----------|---------------|
| 0022 (Response Format Abstraction) | ADR-0060 |
| 0023 (Identity Resolution) | ADR-0061 |
| 0024 (External Service Integration) | ADR-0061 |
| 0033 (Route Organization) | ADR-0063 |
| 0034 (Validation Patterns) | ADR-0063 |
| 0035 (HTTP Response Patterns) | ADR-0060 |
| 0036 (Dual-Interface Error Handling) | ADR-0060 |
| 0039 (Middleware & Request Pipeline) | ADR-0063 |
| 0041 (OpenAPI Documentation Standards) | ADR-0063 |

Note: ADR-0025 was superseded by ADR-0078 and moved to `superseded/` during Wave 3 (2026-04-29).

---

## Wave 2.5 — Pending Execution

| ADR | Title | Due | Status |
|-----|-------|-----|--------|
| 0068 | Runtime Bootstrap SSM-to-Release-Phase Migration | 2026-05-12 | Approved (code change required) |
| 0069 | Port Binding Settings-Driven Contract Migration | 2026-05-12 | Approved (atomic 4-file change) |

---

## Wave 5 — Pending Items

Opens now (Wave 4 gate closed 2026-04-30).

| Item | ADR | Action | Blocker | Status |
|------|-----|--------|---------|--------|
| 1 | 0062 | Author + challenge review | None | **R1 REVISE → Revised → Accepted** |
| 2 | 0064 | Author + challenge review | None | **R1 PASS — Accepted** |
| 3 | 0065 | Author + challenge review | None | **R1 PASS — Accepted** |
| 4 | Legacy | Supersession queue: ADR-0040 → superseded by ADR-0065 | Wave 5 gate | **Complete** (ADR-0040 moved to `superseded/`) |
| 5 | — | Wave 5 gate close | Items 1–2 | **Closed 2026-04-30** |
| 6 | Legacy | Supersession queue: ADR-0037, ADR-0038 → superseded by ADR-0064 | Wave 5 gate | **Complete** (ADR-0037, ADR-0038 moved to `superseded/`) |

| ADR | Title | Key Constraints |
|-----|-------|----------------|
| 0062 | Testing and Request Context Quality | Must codify test patterns from all Wave 3+4 ADRs |
| 0064 | Security and Rate-Limiting API Protection | Constrained by 0055, 0056, 0060, 0061, 0063, 0077, 0078 |
| 0065 | Type-Model Boundaries Canonical Principle | Reconcile Protocol/dataclass/BaseModel/TypedDict with Wave 3+4 patterns |

---

## Wave 6 — Planning Notes

Opens after Wave 5.

| ADR | Title | Blocker | Status |
|-----|-------|---------|--------|
| 0066 | Access Config Env-Source Naming | None (narrowed to naming only; lock scope governed by ADR-0058 S9) | **Accepted** |
| 0067 | Slack Transport Integration Decision | None | **R1 REVISE → Revised → R2 PASS — Accepted** |

### Wave 6 — Feature ADR Derivation Methodology

All Wave 6+ Tier-4 ADRs must follow the derivation methodology documented in the [authoring workflow](references/adr-authoring-workflow.md#tier-4-feature-adr-derivation). Mandatory checks: Derivation Test (4-point), Constraint Derivation Table, Feature-Specific Decisions table, and complex-feature scoping rules.

### Wave 6 — ADR-0043 Rejection Summary

ADR-0043 (Proposed → Rejected) proposed feature-scoped lock release under `access/admin`. Rejected because:

- Contradicts ADR-0058 Standard 4 (singleton lock as infrastructure utility)
- Contradicts ADR-0058 Standard 9 (lock lifecycle is infrastructure-owned, added 2026-04-30)
- Operator intervention is a platform concern, not feature-scoped

### Wave 6 — ADR-0058 Amendment

- Added Standard 9: Singleton Lock Lifecycle and Operator Intervention (6 rules)
- Challenge review: PASS (2026-04-30)
- Establishes infrastructure ownership of lock release and operator intervention utility

### Wave 6 — Legacy Supersession and Gate Close

| Item | ADR | Action | Status |
|------|-----|--------|--------|
| 1 | 0066 | Challenge review | **R1 PASS — Accepted** |
| 2 | 0067 | Challenge review | **R1 REVISE → Revised → R2 PASS — Accepted** |
| 3 | Legacy | Supersession: ADR-0014 → superseded by ADR-0067, moved to `superseded/` | **Complete** |
| 4 | — | Wave 6 gate close | **Closed 2026-04-30** |

**Note:** ADR-0014 was the last legacy ADR pending supersession. All 43 legacy ADRs (0001–0042, plus 0014) are now superseded.

---

## Wave 7 — Access Sub-Feature Decisions (Planning)

**Prerequisite:** Phase 1 infrastructure foundation complete (standalone actions below).  
**Scope:** P1 Tier-4 ADRs for access sub-features — domain-specific decisions not governed by higher tiers.

### Wave 7 Pre-Requisite — Access Domain Contract (Tier-3)

The HV review (finding V-017, Major) identified that the access domain has ~8 domain-specific contracts with no Tier-3 governance. A Tier-3 Access Domain Contract Standard must be authored and accepted before Wave 7 Tier-4 ADRs can be scoped, since the Tier-4 records will derive constraints from it.

| Item | Description | Blocker | Status |
|------|-------------|---------|--------|
| TBD | Access Domain Contract Standard (Tier-3) — adapter Protocol, reconciliation lifecycle, request state machine, entitlement parsing, IDP naming, platform locks, multi-source config, service classification | Phase 1 complete | Not started |

The access domain has ~8 domain-specific contracts (adapter Protocol, reconciliation lifecycle, request state machine, entitlement parsing, IDP naming, platform locks, multi-source config, service classification) with no Tier-3 governance. See also the Cross-Cutting ADR Gaps section in the [migration map](adr-migration-map.md#cross-cutting-adr-gaps-non-feature).

### Wave 7 — Tier-4 ADRs

| ADR | Title | Sub-Feature | Candidate Decisions | Blocker | Status |
|-----|-------|-------------|---------------------|---------|--------|
| TBD | Access Sync Reconciliation and Adapter Contract | Sync | Desired-state reconciliation algorithm, platform adapter Protocol shape, lock consumption pattern | Phase 1 complete | Not started |
| TBD | Access Request State Machine and Approval Policies | Request | Request lifecycle transitions (submit → pending → approved/rejected/cancelled/expired), approval policy engine, auto-approval guards, approver resolution | Phase 1 complete | Not started |
| TBD | Access Cross-Sub-Feature Event Contracts | Common | Which events exist, what triggers what, event payload shapes — feature-internal coordination | Phase 1 complete | Not started — evaluate if needed |
| TBD | Access Catalog Enumeration Strategy | Catalog | Platform enumeration, user membership annotation, response shaping | Phase 1 complete | Not started — evaluate if trivial enough to skip |

**Gate:** All P1 ADRs challenge-reviewed before Phase 2 code work begins. IDs assigned when authoring starts.

---

## Wave 8 — Legacy Module Migration Decisions (Planning)

**Prerequisite:** Phase 2 complete (access finalized, Wave 2.5 executed).  
**Scope:** P3 Tier-4 ADRs authored before each legacy module thaws for migration.

| ADR | Title | Module | Candidate Decisions | Blocker | Status |
|-----|-------|--------|---------------------|---------|--------|
| TBD | Incident Lifecycle and Interaction Patterns | `modules/incident` → `packages/incident` | Incident state machine, Slack interaction patterns, scheduled stale-channel notification, Google Workspace integration shape | Phase 2 complete + Rule F4 (thaw requires Tier-4 ADR) | Not started |
| TBD | Webhooks Architecture | `modules/webhooks` → `packages/webhooks` | Payload dispatch pattern, webhook registry, delivery adapter | Phase 2 complete + Rule F4 | Not started |
| TBD | AWS Ops Multi-Service Integration | `modules/aws` → `packages/aws_ops` | Multi-service integration, async access revocation, health monitoring | Phase 2 complete + Rule F4 | Not started |

**Notes:**

- SRE Ops and ATIP may not warrant Tier-4 ADRs (P4 — simple features). Evaluate during Phase 3.
- Each module thaws one at a time (Rule F5). Migration order: Incident → Webhooks → AWS Ops → SRE Ops/ATIP.
- Each thaw requires: Tier-4 ADR authored and challenge-reviewed, settings migration (Tier-5 ADRs 0070–0075), infrastructure service abstraction (replace raw DynamoDB/integration calls), plugin registration (hookimpl for routes, commands, jobs), tests for new package structure.

---

## Phase 1 — Infrastructure Foundation (Code Implementation)

**Prerequisite:** Wave 5 gate closed (complete). Wave 6 in progress (non-blocking).  
**Purpose:** Execute the infrastructure code changes mandated by settled Tier-1/2/3 ADRs. Frozen zones untouched.

| Item | Description | Governing ADR(s) | Dependencies | Status |
|------|-------------|-------------------|-------------|--------|
| 1 | Settings dissolution — extract AppSettings into independent singletons with narrow-slice providers | ADR-0055, ADR-0056 | None (unblocked — Wave 4+5 gates closed) | **Not started** |
| 2 | Provider restructuring — composition inside root providers only, fix infrastructure import boundary violations | ADR-0056 S3, ADR-0076 | Item 1 (settings dissolution) | **Not started** |
| 3 | Infrastructure service contracts — Protocol-based contracts for Category A services | ADR-0077 | Item 2 (provider restructuring) | **Not started** |
| 4 | Event dispatcher fix — remove import-time side effects from `infrastructure/events/dispatcher.py` | ADR-0048 B4, ADR-0049 S7 | None (independent) | **Not started** |
| 5 | Backward-compatible settings shim — `core.config.settings` shim for frozen zone consumers during Phase 1 | ADR-0055 (dissolution), Freeze Rule F3 | Item 1 (settings dissolution) | **Not started** |

**Completion gate:** All 5 items complete, frozen zones compile without behavioral changes, access package validated against new infrastructure surface.

---

## Standalone Actions (Wave-Independent)

| Action | Description | Status |
|--------|-------------|--------|
| Event dispatcher fix | `infrastructure/events/dispatcher.py` import-time side effects (ADR-0048 B4 / ADR-0049 S7 violation) | **Not started** — tracked as Phase 1 Item 4 |
| Settings dissolution (code) | Extract AppSettings, independent singletons, narrow-slice providers (ADR-0055/0056 implementation) | **Not started** — unblocked (Wave 5 gate closed); tracked as Phase 1 Item 1 |
| Provider restructuring (code) | ADR-0056/0076 Standard 3 violations (composition outside root) | **Not started** — blocked on settings dissolution; tracked as Phase 1 Item 2 |
| Delegation review | Cross-wave ADR amendments for managed service delegation hierarchy (ADR-0045 P7) | **Complete** — Phases 1–3 done (8 PASS, 3 Verified, 12 NONE verified). Phase 4 library ADRs deferred (custom interim accepted, flagged for Tier 1 delegation). |
| HV review — redundancy consolidation | Prose consolidation of 5 redundancy/ambiguity findings across 7 ADR files | **Complete** — H-001, H-002, H-005, H-007, H-008 all applied. |
| API Versioning Strategy ADR (HV finding H-009) | Tier-2 standard for v2 endpoint introduction, deprecation lifecycle, and client migration. Not needed until first v2 endpoint is planned. | **DEFERRED** — trigger: first v2 endpoint planned |
| ADR-0080 follow-up: ADR-0067 scope clarification | Update ADR-0067 to reference ADR-0080 and clarify "any feature or subsystem" is scoped to in-process code within ASGI lifespan. | **Complete** — editorial amendment applied 2026-05-01 |
| ADR-0080 follow-up: ADR-0052 decomposition assessment | Assess infra-specific guidance in ADR-0052 for reclassification or migration to future infra ADR. | **Complete** — ECS-specific guidance relabeled as infrastructure fulfillment context 2026-05-01 |
| ADR-0080 follow-up: ADR-0044 tier assessment | Assess ADR-0044 tier definitions for infra-domain fit when first infrastructure ADR is authored. | **Complete** — blast radius descriptions updated in metadata reference 2026-05-01 |

---

## Feature ADR Gap Assessment

Tracks Tier-4 coverage gaps across feature domains.

### Prioritized Feature ADR Backlog

| Priority | Feature Domain | Package | Candidate Tier-4 ADR(s) | Wave | Status |
|----------|---------------|---------|-------------------------|------|--------|
| **P1** | Access / Sync | `packages/access/sync` | Reconciliation algorithm, platform adapter contract, lock consumption pattern | 7 | Not started — blocked on Phase 1 |
| **P1** | Access / Request | `packages/access/request` | Request state machine, approval policies, auto-approval guards | 7 | Not started — blocked on Phase 1 |
| **P1** | Access / Common | `packages/access/common` | Cross-sub-feature event contracts (evaluate if needed) | 7 | Not started — blocked on Phase 1 |
| **P1** | Access / Catalog | `packages/access/catalog` | Enumeration and annotation strategy (evaluate if trivial) | 7 | Not started — blocked on Phase 1 |
| **P2** | Slack Transport | `modules/slack` + integration | ADR-0067 (blocks ADR-0014 supersession) | 6 | Not started |
| **P3** | Incident | `modules/incident` → `packages/incident` | Incident lifecycle, Slack interaction patterns, stale-channel notification | 8 | Not started — blocked on Phase 3 thaw |
| **P3** | AWS Ops | `modules/aws` → `packages/aws_ops` | Multi-service integration, async revocation, health monitoring | 8 | Not started — blocked on Phase 3 thaw |
| **P4** | SRE Ops | `modules/sre` → `packages/sre_ops` | Notification patterns | 8 | Not started — may not warrant ADR |
| **P4** | ATIP | `modules/atip` → `packages/atip` | — | — | No gap — too simple for Tier-4 |
| **P4** | Geolocate | `packages/geolocate` | — | — | No gap — too simple for Tier-4 |

### Legacy Feature ADRs Supersession Status

| Legacy ADR | Title | Mixed Concerns | Canonical Replacements | Status |
|-----------|-------|----------------|------------------------|--------|
| 0014 | Slack Socket Mode | Startup + daemon threads + Slack integration | Tier-1/2: ADR-0046, 0057, 0058 (done). Tier-4: ADR-0067 (pending) | **Pending** — awaiting ADR-0067 |
| 0042 | Access Runtime Env-Source Naming | Settings namespace + feature naming | Tier-4: ADR-0066 (Accepted) | **Complete** — moved to `superseded/` |
| 0043 | Access Admin Stuck-Lock Scope | Infrastructure lock lifecycle + feature admin | Tier-2: ADR-0058 S4/S9 (done). Feature scope: **Rejected** | **Complete** — rejected, no supersession needed |

### Migration Execution Phases

| Phase | Scope | Prerequisite | Wave | Status |
|-------|-------|-------------|------|--------|
| 1 | Infrastructure Foundation (settings dissolution, provider restructuring, service contracts, event dispatcher, backward-compatible shim) | Wave 5 gate closed (done) | — | **Not started** — unblocked |
| 2 | Access Feature Finalization (sub-feature Tier-4 ADRs, code completion, Wave 2.5 execution) | Phase 1 complete | 7 | **Not started** |
| 3 | Legacy Module Migration (one at a time: Incident → Webhooks → AWS Ops → SRE Ops/ATIP) | Phase 2 complete | 8 | **Not started** |
| 4 | Legacy Cleanup (remove `app/modules/`, `app/core/`, `app/models/`, `app/locales/`, `app/utils/`) | Phase 3 complete | — | **Not started** |

### Frozen Zones (Phase 1–2)

| Zone | Path | Files | Thaw Phase |
|------|------|-------|-----------|
| /sre Command Dispatch | `app/modules/sre/` | 3 | Phase 3 (last) |
| Incident Module | `app/modules/incident/` | 17 | Phase 3a |
| Webhooks System | `app/modules/slack/` + `app/modules/webhooks/` + `app/api/v1/routes/webhooks.py` | 7 | Phase 3b |
| Frozen Support Packages | `app/core/`, `app/integrations/`, `app/models/`, `app/locales/`, `app/utils/` | — | Phase 3–4 (progressive) |
