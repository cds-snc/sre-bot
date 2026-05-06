# ADR Migration Map

**Purpose:** Single-source registry mapping legacy ADRs to canonical replacements. One row per target ADR.

---

## Target ADR Registry

| ID | Title | Tier | Wave | Supersedes | Status |
|----|-------|------|------|------------|--------|
| 0044 | ADR Governance and Operating Model | 0 | — | — | Accepted |
| 0045 | Core Architectural Principles | 1 | 1 | 0001 | Accepted |
| 0046 | Runtime Lifecycle and Lifespan Canonical Model | 1 | 1 | 0005, 0009, 0011 | Accepted |
| 0047 | Configuration and Settings Governance | 1 | 1 | 0002, 0007, 0010 | Accepted |
| 0048 | Dependency and Import Boundary Constitution | 1 | 1 | 0003, 0004 | Accepted |
| 0049 | Plugin Registration and Startup Reliability | 2 | 1 | 0013, 0017, 0026, 0027 | Accepted |
| 0050 | Operation Result Canonical Standard | 2 | 1 | 0006, 0020 | Accepted |
| 0051 | ADR Taxonomy and Classification Enforcement | 2 | 2 | 0019, 0032 | Accepted |
| 0052 | Build-Release-Run Delivery Standard | 2 | 2 | — | Accepted |
| 0053 | Port Binding and Runtime Exposure | 2 | 2 | — | Accepted |
| 0054 | Dev/Prod Parity and Operational Logs Ownership | 2 | 2 | 0029 | Accepted |
| 0055 | Settings Implementation and Dissolution | 2 | 3 | 0008 | Accepted |
| 0056 | Provider Discovery and Composition | 2 | 3 | 0012 | Accepted |
| 0057 | Runtime Disposability and Graceful Shutdown | 2 | 3 | 0016 | Accepted |
| 0058 | Background Execution and Worker Isolation | 2 | 3 | 0015 | Accepted |
| 0076 | Infrastructure Intra-Layer Import Standard | 2 | 3 | — | Accepted |
| 0077 | Infrastructure Service Contract Standard | 2 | 3 | — | Accepted |
| 0059 | Feature Interaction Boundaries and Platform Integration | 2 | 4 | 0028 | Accepted |
| 0060 | API Response and Error Mapping | 2 | 4 | 0022, 0035, 0036 | Accepted |
| 0061 | Identity and External Integration Contract | 3 | 4 | 0023, 0024 | Accepted |
| 0063 | API Composition and Validation | 2 | 4 | 0033, 0034, 0039, 0041 | Accepted |
| 0078 | Platform Services Architecture | 2 | 4 | 0025 | Accepted |
| 0079 | Queueing and Message-Broker Architecture | 2 | 4 | — | Accepted |
| 0062 | Testing and Request Context Quality | 2 | 5 | 0030, 0031 | Accepted |
| 0064 | Security and Rate-Limiting API Protection | 2 | 5 | 0037, 0038 | Accepted |
| 0065 | Type-Model Boundaries Canonical Principle | 1 | 5 | 0040 | Accepted |
| 0066 | Access Config Env-Source Naming | 4 | 6 | 0042 | Accepted |
| 0067 | Slack Transport Integration Decision | 4 | 6 | 0014 | Accepted |
| 0080 | Application Portability Boundary | 1 | P0 | — | Accepted |
| 0081 | CI/CD Pipeline and Deployment Validation | 2 | P3 | — | Accepted |
| 0082 | Infrastructure Alerting Architecture | 4 | P2 | — | Accepted |
| 0083 | Event Dispatcher Library Adoption | 5 | P1 | — | Accepted |
| 0085 | Infrastructure Import and Barrel Governance | 2 | 7 | — | Draft |
| 0086 | Service Resolution Context Standard | 2 | 7 | — | Draft |
| 0087 | Feature Package Vertical Isolation and Internal Composition | 2 | 7 | — | Draft |
| 0088 | Multi-Transport Dispatch and Platform Boundary Architecture | 2 | 7 | — | Draft |

## Tier-5 Records (Migration / Deprecation)

| ID | Title | Type | Wave | Status | Target Date |
|----|-------|------|------|--------|-------------|
| 0068 | Runtime Bootstrap SSM-to-Release-Phase Migration | Migration | 2.5 | Approved | 2026-05-12 |
| 0069 | Port Binding Settings-Driven Contract Migration | Migration | 2.5 | Approved | 2026-05-12 |
| 0070 | GroupsFeatureSettings Retirement | Deprecation | 3.5 | Executing (2/7 criteria met) | Phase 2 |
| 0071 | CommandsSettings Retirement | Deprecation | 3.5 | Executing (2/7 criteria met) | Phase 2 |
| 0072 | IncidentFeatureSettings Migration | Migration | 3.5 | Accepted | Phase C |
| 0073 | AWSFeatureSettings Migration | Migration | 3.5 | Accepted | Phase C |
| 0074 | AtipSettings Migration | Migration | 3.5 | Accepted | Phase C |
| 0075 | SreOpsSettings Migration | Migration | 3.5 | Accepted | Phase C |

## Superseded Legacy ADRs

All files in `adr/superseded/`. Each has `status: Superseded` and `superseded_by` set.

| Legacy ID | Original Title | Superseded By |
|-----------|----------------|---------------|
| 0001 | Core Architectural Principles | 0045 |
| 0002 | Configuration Management | 0047 |
| 0003 | Dependency Injection Pattern | 0048 |
| 0004 | Import Conventions | 0048 |
| 0005 | Application Initialization Lifecycle | 0046 |
| 0006 | Operation Result Pattern | 0050 |
| 0007 | Settings Partitioned Model | 0047 |
| 0008 | Settings JSON Blob Override | 0055 |
| 0009 | FastAPI Lifespan Pattern | 0046 |
| 0010 | Settings Singleton | 0047 |
| 0011 | Initialization Phases | 0046 |
| 0012 | Provider Discovery | 0056 |
| 0013 | Plugin Managers | 0049 |
| 0015 | Background Services | 0058 |
| 0016 | Graceful Shutdown | 0057 |
| 0017 | Feature Startup Failure Policy | 0049 |
| 0018 | Service Wrapper Pattern | 0056, 0077 |
| 0019 | Domain Isolation | 0051 |
| 0020 | Operation Result Pattern | 0050 |
| 0021 | Command Framework Platform Abstraction | 0059, 0078 |
| 0022 | Response Format Abstraction | 0060 |
| 0023 | Identity Resolution | 0061 |
| 0024 | External Service Integration | 0061 |
| 0025 | Platform Providers Concept | 0078 |
| 0026 | Explicit Registration Pattern | 0049 |
| 0027 | Pluggy Plugin System | 0049 |
| 0028 | Platform Feature Isolation | 0059 |
| 0029 | Logging Standards | 0054 |
| 0030 | Testing Standards | 0062 |
| 0031 | Request ID Propagation | 0062 |
| 0032 | Features Organization | 0051 |
| 0033 | Route Organization | 0063 |
| 0034 | Validation Patterns | 0063 |
| 0035 | HTTP Response Patterns | 0060 |
| 0036 | Dual-Interface Error Handling | 0060 |
| 0037 | Security & Authentication | 0064 |
| 0038 | Rate Limiting | 0064 |
| 0039 | Middleware & Request Pipeline | 0063 |
| 0040 | Type Model Boundaries | 0065 |
| 0041 | OpenAPI Documentation Standards | 0063 |
| 0042 | Access Runtime Env-Source Naming | 0066 |
| 0014 | Slack Socket Mode | 0067 |

## Pending Supersession

No legacy ADRs pending supersession. All legacy ADRs have been superseded.

### ADR-0043 — Rejected (Not Superseded)

ADR-0043 (Access Admin Stuck-Lock Scope) was rejected, not superseded. Lock lifecycle is governed by ADR-0058 Standard 4 and Standard 9. No Tier-4 replacement needed — the feature-scoped decision was invalid.

## Feature ADR Coverage Gaps

Tier-4 ADRs not yet allocated in the registry. IDs will be assigned when authoring begins. Wave assignments per the [wave tracker](adr-wave-tracker.md#wave-7--access-sub-feature-decisions-planning).

| Feature Domain | Package | Candidate Decisions | Priority | Wave | Blocked By |
|---------------|---------|---------------------|----------|------|-----------|
| Access / Sync | `packages/access/sync` | Reconciliation algorithm, platform adapter contract, lock consumption pattern | P1 | 7 | Phase 1 |
| Access / Request | `packages/access/request` | Request state machine, approval policies, auto-approval guards | P1 | 7 | Phase 1 |
| Access / Common | `packages/access/common` | Cross-sub-feature event contracts (evaluate if needed) | P1 | 7 | Phase 1 |
| Access / Catalog | `packages/access/catalog` | Enumeration and annotation strategy (evaluate if trivial) | P1 | 7 | Phase 1 |
| Incident | `modules/incident` → `packages/incident` | Incident lifecycle, Slack interaction patterns, stale-channel notification | P3 | 8 | Phase 3 thaw |
| Webhooks | `modules/webhooks` → `packages/webhooks` | Payload dispatch pattern, webhook registry, delivery adapter (platform-agnostic — Slack is one output channel, not the only one) | P3 | 8 | Phase 3 thaw |
| AWS Ops | `modules/aws` → `packages/aws_ops` | Multi-service integration, async revocation, health monitoring | P3 | 8 | Phase 3 thaw |
| SRE Ops | `modules/sre` → `packages/sre_ops` | Notification patterns (may not warrant ADR) | P4 | 8 | Phase 3 thaw |

## Cross-Cutting ADR Gaps (Non-Feature)

ADRs identified by the Horizontal-Vertical review as needed but not yet allocated. IDs will be assigned when authoring begins.

| Candidate Title | Tier | HV Finding | Priority | Trigger | Blocked By |
|----------------|------|------------|----------|---------|------------|
| Access Domain Contract Standard | 3 | V-017 | HIGH | Access domain has ~8 domain-specific contracts (adapter Protocol, reconciliation lifecycle, request state machine, entitlement parsing, IDP naming, platform locks, multi-source config, service classification) with no Tier-3 governance | Phase 1 complete |
| API Versioning Strategy | 2 | H-009 | DEFERRED | No standard governs v2 endpoint introduction, deprecation lifecycle, or client migration. Not needed until first v2 endpoint is planned | First v2 endpoint planned |
