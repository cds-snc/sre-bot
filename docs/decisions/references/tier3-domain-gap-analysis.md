# Tier-3 Domain Contract Gap Analysis

**Date:** 2026-04-30  
**Trigger:** HV Review — only 1 Tier-3 ADR (ADR-0061, Identity) exists  
**Related:** Wave 7 planning in [wave tracker](../adr-wave-tracker.md)

---

## Summary

The ADR corpus has 1 Tier-3 Domain Standard (ADR-0061). Codebase analysis identifies 2 additional candidates. The strongest (Access) has more domain-specific contracts than the existing Tier-3 ADR.

---

## 1. Access Domain — HIGH PRIORITY

**Location:** `app/packages/access/` (sync, request, catalog)  
**Current coverage:** ADR-0066 (Tier-4, naming only), ADR-0070 (Tier-5, settings retirement)  
**Gap:** No Tier-3 ADR governs access domain contracts.

### Domain-Specific Contracts Not Covered by Tier-2

| Contract | Evidence | Why Tier-2 Is Insufficient |
|----------|----------|---------------------------|
| **Adapter Protocol** (`AccessSyncAdapter`) | 9-method Protocol in `sync/adapters/__init__.py` | Defines domain-specific reconciliation semantics (assess → plan → execute), idempotency, dry-run, capability declarations |
| **Desired vs. Actual Reconciliation** | `DesiredUserState`, `DesiredPlatformState`, `AdapterAssessment` frozen dataclasses | Domain-specific: adapters assess current state, coordinators derive desired state from IDP, deltas planned and executed |
| **Application Service Orchestration** | `AccessSyncApplicationService` with `AccessSyncApplicationServicePort` Protocol | Orchestration flow (resolve adapter → derive desired state → reconcile → audit → emit) is domain-specific |
| **Request Lifecycle** | `AccessRequest` with 8-state machine: submitted → pending_approval → approved/rejected/cancelled/expired → completed/failed | State machine semantics (frozen approvers, delegated vs. self-service actors, minimum thresholds) are domain-specific |
| **Entitlement Parsing** | `ParsedEntitlementToken` with platform-specific decomposition (AWS: `Product-Env-Role-Service-Resource`) | Token grammar and disambiguation rules are access-domain-specific |
| **IDP Group Naming** | `AccessGroupNaming` enforces `prefix-platform-token` pattern | Cross-platform naming convention is domain-specific |
| **Platform Lock & Sync Persistence** | `SyncRunRecord`, lock acquisition/TTL/stale detection | ADR-0058 S9 governs locks generically; access adds domain-specific semantics |
| **Runtime Config Loading** | Multi-source config (DynamoDB, env, file) with `AccessRuntimeConfig` | ADR-0055 governs settings patterns; access adds domain-specific config sources |

### Tier-1/2 Norms Requiring Domain Specialization

| Parent Norm | Specialization Needed |
|------------|----------------------|
| ADR-0050 (OperationResult) | Domain-specific status semantics: `OperationResult[SyncOutcome]`, `OperationResult[AccessRequest]`, domain error codes |
| ADR-0077 S1 (Service Classification) | 9-method adapter Protocol, `AccessSyncApplicationServicePort` — classification table needed |
| ADR-0058 S3-S4 (Job/Concurrency) | Singleton job with platform-scoped locks, TTL, operator intervention |
| ADR-0045 P7 (Delegation) | Per-adapter delegation tier (AWS Identity Store, GitHub API) |
| ADR-0059 S2-S3 (Interaction) | Slack commands for sync trigger and request approval |

### Estimated Scope

A Tier-3 Access Domain Contract Standard would define ~7–9 standards:

1. Adapter Protocol contract and reconciliation lifecycle
2. Desired-state resolution and IDP membership mapping
3. Request lifecycle state machine and approval rules
4. Entitlement catalog parsing contract
5. IDP group naming convention
6. Platform lock and sync run audit persistence
7. Runtime config loading and multi-source strategy
8. Service classification table
9. Delegation tier declarations per platform adapter

---

## 2. Groups Domain — MEDIUM PRIORITY (Deferred)

**Location:** `app/modules/groups/` (legacy)  
**Gap:** No Tier-3 ADR. Has `NormalizedGroup`/`NormalizedMember` types, provider normalization pattern, reconciliation workflows.  
**Assessment:** Lower complexity than Access. Fully deprecated — replaced by access package (ADR-0070). Author Tier-3 ADR only after migrating to `app/packages/`, clarifying boundary with access (directory read model vs. provisioning write model).

---

## 3. Incident Domain — LOW PRIORITY (Deferred)

**Location:** `app/modules/incident/` (legacy, 16 files)  
**Gap:** No Tier-3 ADR. Has incident lifecycle state machine, artifact generation, on-call escalation.  
**Assessment:** Heavily legacy, tightly coupled to Slack SDK (9 files) and Google APIs (7 files). No Protocol contracts. Defer until incident is refactored into `app/packages/incident`.

---

## Non-Candidates

| Domain | Location | Why Not Tier-3 |
|--------|----------|----------------|
| Geolocate | `app/packages/geolocate/` | Thin MaxMind wrapper, Category C, no domain contracts |
| Provisioning | `app/modules/provisioning/` | Generic batch framework, no domain specificity |
| Permissions | `app/modules/permissions/` | Single handler file, too minimal |

---

## Recommendation

Author a Tier-3 Access Domain Contract Standard before Wave 7 Tier-4 ADRs can be scoped — the Tier-4 records will derive constraints from it. See Wave 7 prerequisites in the [wave tracker](../adr-wave-tracker.md#wave-7--access-sub-feature-decisions-planning).
