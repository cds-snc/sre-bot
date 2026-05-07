# ADR Map: Current State

Date: 2026-05-07
Source scope: `docs/decisions/adr/*.md` and `docs/decisions/adr/superseded/*.md`

## Purpose

This document is a map of ADR metadata and interrelations in the repository.
It is intentionally not a migration plan and not a tracker.

## Corpus Snapshot

- Total ADR files: 87
- Active-directory ADR files (`docs/decisions/adr`): 44
- Superseded-directory ADR files (`docs/decisions/adr/superseded`): 43

### Status Distribution (all ADR files)

- Accepted: 36
- Draft: 8
- Rejected: 1
- Superseded: 42

### Status Distribution (active directory only)

- Accepted: 36
- Draft: 8
- Rejected: 0
- Superseded: 0

## Interrelation Map

### Supersedence Index (from superseded ADR metadata)

This table maps each superseding ADR ID to the ADR IDs it supersedes.
Note: a superseding ADR ID can itself now be superseded historically.

| Superseding ADR ID | Title | Superseded ADR IDs |
|---|---|---|
| ADR-0025 | - | ADR-0021 |
| ADR-0026 | - | ADR-0021 |
| ADR-0027 | - | ADR-0021 |
| ADR-0028 | - | ADR-0021 |
| ADR-0045 | Core Architectural Principles (Canonical Rewrite) | ADR-0001 |
| ADR-0046 | Runtime Lifecycle and Lifespan Canonical Model | ADR-0005<br>ADR-0009<br>ADR-0011 |
| ADR-0047 | Configuration and Settings Governance Canonical Model | ADR-0002<br>ADR-0007<br>ADR-0010 |
| ADR-0048 | Dependency and Import Boundary Constitution | ADR-0003<br>ADR-0004 |
| ADR-0049 | Plugin Registration and Startup Reliability Policy | ADR-0013<br>ADR-0017<br>ADR-0026<br>ADR-0027 |
| ADR-0050 | Operation Result Canonical Standard | ADR-0006<br>ADR-0020 |
| ADR-0051 | ADR Taxonomy and Classification Enforcement Standard | ADR-0019<br>ADR-0032 |
| ADR-0054 | Dev/Prod Parity and Operational Logs Ownership Standard | ADR-0029 |
| ADR-0055 | Settings Implementation and Dissolution Standard | ADR-0008 |
| ADR-0056 | Provider Discovery and Composition Standard | ADR-0012<br>ADR-0018 |
| ADR-0057 | Runtime Disposability and Graceful Shutdown Standard | ADR-0016 |
| ADR-0058 | Background Execution and Worker Isolation Standard | ADR-0015 |
| ADR-0059 | Feature Interaction Boundaries and Platform Integration Stan | ADR-0028 |
| ADR-0060 | API Response and Error Mapping Standard | ADR-0022<br>ADR-0035<br>ADR-0036 |
| ADR-0061 | Identity and External Integration Contract Standard | ADR-0023<br>ADR-0024 |
| ADR-0062 | Testing and Request Context Quality | ADR-0030<br>ADR-0031 |
| ADR-0063 | API Composition and Validation Standard | ADR-0033<br>ADR-0034<br>ADR-0039<br>ADR-0041 |
| ADR-0064 | Security and Rate-Limiting API Protection | ADR-0037<br>ADR-0038 |
| ADR-0065 | Type-Model Boundaries Canonical Principle | ADR-0040 |
| ADR-0066 | Access Config Env-Source Naming | ADR-0042 |
| ADR-0067 | Slack Transport Integration Decision | ADR-0014 |
| ADR-0077 | Infrastructure Service Contract Standard | ADR-0018 |
| ADR-0078 | Platform Services Architecture | ADR-0025 |

## Potential Scope Tension / Conflict Candidates

These are scope-overlap candidates to review, not confirmed contradictions.

- `ADR-0085` (Draft) explicitly supersedes `ADR-0056` while `ADR-0056` is still Accepted and active. This creates transitional dual authority in scope.
- `ADR-0089` (Draft) explicitly supersedes `ADR-0059` while `ADR-0059` is still Accepted and active. This creates transitional dual authority in scope.
- `ADR-0084`, `ADR-0089`, and `ADR-0090` (all Draft) overlap identity/transport handler boundaries already covered by Accepted `ADR-0061`, `ADR-0060`, and `ADR-0063`.
- `ADR-0091` (Draft, Data and Persistence) intersects handler reliability and idempotency concerns already constrained by runtime and transport standards (`ADR-0057`, `ADR-0058`, `ADR-0060`, `ADR-0063`).

## Metadata Quality Flags


## Active ADR Inventory (Complete)

| ADR | Title | Status | Tier | Type | Primary Domain | Supersedes |
|---|---|---|---|---|---|---|
| ADR-0044 | ADR Governance and Operating Model | Accepted | Tier-0 | Governance Policy | Governance and Operating Model | - |
| ADR-0045 | Core Architectural Principles (Canonical Rewrite) | Accepted | Tier-1 | Principle | Dependency and Composition | - |
| ADR-0046 | Runtime Lifecycle and Lifespan Canonical Model | Accepted | Tier-1 | Principle | Runtime and Lifecycle | - |
| ADR-0047 | Configuration and Settings Governance Canonical Model | Accepted | Tier-1 | Principle | Configuration and Secrets | - |
| ADR-0048 | Dependency and Import Boundary Constitution | Accepted | Tier-1 | Principle | Dependency and Composition | - |
| ADR-0049 | Plugin Registration and Startup Reliability Policy | Accepted | Tier-2 | Standard | Package and Plugin Architecture | - |
| ADR-0050 | Operation Result Canonical Standard | Accepted | Tier-2 | Standard | Transport and API | - |
| ADR-0051 | ADR Taxonomy and Classification Enforcement Standard | Accepted | Tier-2 | Standard | Governance and Operating Model | - |
| ADR-0052 | Build-Release-Run Delivery Standard | Accepted | Tier-2 | Standard | Delivery and Environment Parity | - |
| ADR-0053 | Port Binding and Runtime Exposure Standard | Accepted | Tier-2 | Standard | Delivery and Environment Parity | - |
| ADR-0054 | Dev/Prod Parity and Operational Logs Ownership Standard | Accepted | Tier-2 | Standard | Observability and Operations | - |
| ADR-0055 | Settings Implementation and Dissolution Standard | Accepted | Tier-2 | Standard | Configuration and Secrets | - |
| ADR-0056 | Provider Discovery and Composition Standard | Accepted | Tier-2 | Pattern | Dependency and Composition | - |
| ADR-0057 | Runtime Disposability and Graceful Shutdown Standard | Accepted | Tier-2 | Standard | Runtime and Lifecycle | - |
| ADR-0058 | Background Execution and Worker Isolation Standard | Accepted | Tier-2 | Standard | Runtime and Lifecycle | - |
| ADR-0059 | Feature Interaction Boundaries and Platform Integration | Accepted | Tier-2 | Standard | Package and Plugin Architecture | - |
| ADR-0060 | API Response and Error Mapping Standard | Accepted | Tier-2 | Standard | Transport and API | - |
| ADR-0061 | Identity and External Integration Contract Standard | Accepted | Tier-3 | Domain Standard | Dependency and Composition | - |
| ADR-0062 | Testing and Request Context Quality | Accepted | Tier-2 | Standard | Testing and Quality | ADR-0030<br>ADR-0031 |
| ADR-0063 | API Composition and Validation Standard | Accepted | Tier-2 | Standard | Transport and API | ADR-0033<br>ADR-0034<br>ADR-0039<br>ADR-0041 |
| ADR-0064 | Security and Rate-Limiting API Protection | Accepted | Tier-2 | Standard | Security and Access Control | ADR-0037<br>ADR-0038 |
| ADR-0065 | Type-Model Boundaries Canonical Principle | Accepted | Tier-1 | Principle | Dependency and Composition | ADR-0040 |
| ADR-0066 | Access Config Env-Source Naming | Accepted | Tier-4 | Feature Decision | Configuration and Secrets | ADR-0042 |
| ADR-0067 | Slack Transport Integration Decision | Accepted | Tier-4 | Integration Decision | Transport and API | ADR-0014 |
| ADR-0070 | GroupsFeatureSettings Retirement | Accepted | Tier-5 | Deprecation Decision | Configuration and Secrets | - |
| ADR-0071 | CommandsSettings Retirement | Accepted | Tier-5 | Deprecation Decision | Configuration and Secrets | - |
| ADR-0072 | IncidentFeatureSettings Migration to packages/incident | Accepted | Tier-5 | Migration Decision | Configuration and Secrets | - |
| ADR-0073 | AWSFeatureSettings Migration to packages/aws_ops | Accepted | Tier-5 | Migration Decision | Configuration and Secrets | - |
| ADR-0074 | AtipSettings Migration to packages/atip | Accepted | Tier-5 | Migration Decision | Configuration and Secrets | - |
| ADR-0075 | SreOpsSettings Migration to packages/sre_ops | Accepted | Tier-5 | Migration Decision | Configuration and Secrets | - |
| ADR-0076 | Infrastructure Intra-Layer Import Standard | Accepted | Tier-2 | Standard | Dependency and Composition | - |
| ADR-0077 | Infrastructure Service Contract Standard | Accepted | Tier-2 | Standard | Dependency and Composition | - |
| ADR-0078 | Platform Services Architecture | Accepted | Tier-2 | Standard | Dependency and Composition | - |
| ADR-0079 | Queueing and Message-Broker Architecture Standard | Accepted | Tier-2 | Standard | Runtime and Lifecycle | - |
| ADR-0080 | Application Portability Boundary | Accepted | Tier-1 | Principle | Governance and Operating Model | - |
| ADR-0083 | Event Dispatcher Library Adoption | Accepted | Tier-5 | Library Adoption Decision | Runtime and Lifecycle | - |
| ADR-0084 | Platform Interaction Identity Resolution Standard | Draft | Tier-3 | Domain Standard | Security | - |
| ADR-0085 | Infrastructure Import and Barrel Governance | Draft | Tier-2 | Standard | Dependency and Composition | ADR-0056 |
| ADR-0086 | Service Resolution Context Standard | Draft | Tier-2 | Standard | Dependency and Composition | - |
| ADR-0087 | Feature Package Vertical Isolation and Internal Composi | Draft | Tier-2 | Standard | Package and Plugin Architecture | - |
| ADR-0088 | Multi-Transport Dispatch and Platform Boundary Architec | Draft | Tier-2 | Standard | Transport and API | - |
| ADR-0089 | Platform Interaction Handler Standard | Draft | Tier-2 | Standard | Transport and API | ADR-0059 |
| ADR-0090 | Cross-Channel Correlation and HTTP Coordination Standar | Draft | Tier-2 | Standard | Transport and API | - |
| ADR-0091 | Handler Reliability and Idempotency Standard | Draft | Tier-2 | Standard | Data and Persistence | - |
