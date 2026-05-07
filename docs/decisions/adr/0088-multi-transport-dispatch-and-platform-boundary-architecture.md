---
adr_id: ADR-0088
title: "Multi-Transport Dispatch and Platform Boundary Architecture"
status: Accepted
decision_type: Standard
tier: Tier-2
governance_domain: application
primary_domain: Transport and API
secondary_domains:
  - Package and Plugin Architecture
  - Dependency and Composition
owners:
  - SRE Team
date_created: 2026-05-06
last_updated: 2026-05-07
last_reviewed: 2026-05-07
next_review_due: 2026-09-03
constrained_by:
  - ADR-0044
  - ADR-0045
  - ADR-0048
  - ADR-0050
  - ADR-0056
  - ADR-0065
  - ADR-0078
  - ADR-0089
  - ADR-0090
  - ADR-0091
impacts:
  - ADR-0078
  - ADR-0089
supersedes: []
superseded_by: []
review_state: current
related_records:
  - ADR-0045
  - ADR-0048
  - ADR-0049
  - ADR-0063
  - ADR-0067
  - ADR-0078
  - ADR-0083
  - ADR-0085
  - ADR-0086
  - ADR-0087
  - ADR-0089
  - ADR-0090
  - ADR-0091
related_packages:
  - app/packages/access
---

# Multi-Transport Dispatch and Platform Boundary Architecture

## Context

- Problem statement: No ADR distinguished between platform-specific orchestration
  (deciding *what* to do on a target platform) and pure protocol translation (executing
  API calls). The cross-ADR analysis found that this distinction is critical for features
  like Access Sync, where platform reconcilers contain legitimate decision logic
  (capability-aware planning, entity matching, execution sequencing) that is neither
  business logic nor thin translation.

  Without this distinction, platform integration classes accumulate mixed responsibilities
  (reconciliation + API translation) in a single class generically named "adapter,"
  causing architectural drift.

  **The three-layer outbound model (discovered via Access Sync validation):**

  | Layer | Role | Example |
  |-------|------|---------|
  | **Intent** (Feature Service) | Computes desired state from business rules; platform-independent | Access Sync application service: policy evaluation, identity normalization |
  | **Realization** (Platform Reconciler) | Transforms desired state into target-specific action plan; capability-aware planning | `AwsIdentityCenterAdapter` (current) → `AwsIdentityStoreReconciler` (proposed): user+group+membership diffing and sequencing |
  | **Transport** (Client Adapter) | Executes API calls; handles protocol details | `AwsIdentityStoreClientAdapter`: boto3 calls, pagination, retry, error mapping |

- Business/operational drivers:
  - Teams support is moving from stub to production; governing model must exist first.
  - The three-layer outbound model prevents mixed-responsibility platform classes.
  - Named role enforcement (Reconciler vs Adapter) catches drift at code review time.

- Constraints:
  - ADR-0056: provider composition for reconcilers and client adapters happens in `providers.py`.
  - ADR-0065: domain models are `@dataclass(frozen=True)`; adapter boundary types use `TypedDict`.
  - ADR-0078: platform providers are infrastructure services.
  - ADR-0089: inbound handler architecture; `interactions/` directory contract; hookspec names.
  - ADR-0090: `correlation_id` cardinality and payload carrier per channel.
  - ADR-0091: idempotency key schema and atomic write contract that reconcilers must respect.

- Non-goals:
  - This record does not govern inbound multi-transport handler architecture (ADR-0089).
  - This record does not govern output/notification channels (proactive messages).
  - This record does not define platform provider implementation internals (ADR-0078).
  - This record does not govern HTTP authentication (ADR-0064).
  - This record does not govern barrel structure (ADR-0085) or package isolation (ADR-0087).

## Decision

Outbound platform interactions in feature packages follow a **three-layer model** separating
intent, realization, and transport. Inbound multi-transport handler architecture is governed
by ADR-0089.

### Standards 1–6: Governed by ADR-0089

Inbound multi-transport handler architecture — including the transport-agnostic ingress
layer, adapter independence, per-platform hookspec registration, `interactions/` directory
contract, normalised intent boundary type, and error mapping per transport — is governed
by **ADR-0089 (Platform Interaction Handler Standard)**.

The hookspec names in force are `register_slack_interactions`, `register_teams_interactions`,
`register_routes`, and `register_event_handlers` per ADR-0089 Standard 3. The earlier names
(`register_slack_commands`, `register_teams_commands`) used during ADR-0088's initial draft
are not the current canonical forms.

### Standard 7: Three-Layer Outbound Platform Model

When a feature interacts with an external platform to *realize* intent (not just dispatch
commands), the outbound interaction must follow a three-layer model separating concerns.

**Layer definitions:**

| Layer | Responsibility | Naming Convention | Example |
|-------|---------------|-------------------|---------|
| **Intent** (Feature Service) | Business rules, desired state computation, cross-platform invariants | `<Feature>Service`, `<Feature>Coordinator` | `AccessSyncCoordinator` |
| **Realization** (Platform Reconciler) | Capability-aware planning, entity matching, platform-specific diffing and sequencing, idempotent execution | `<Platform>Reconciler` | `AwsIdentityStoreReconciler` |
| **Transport** (Client Adapter) | Request/response translation, pagination, retry, auth, error mapping to OperationResult | `<Platform>ClientAdapter` or `<Platform>Client` | `AwsIdentityStoreClientAdapter` |

**Constraints:**

- S7.1: A class that mixes Realization and Transport responsibilities must be split.
  Classes must be named for their role — generic names like `Adapter` that hide mixed
  responsibilities are prohibited when reconciliation logic exists.
- S7.2: Only the Client Adapter layer may import platform SDK types (boto3, google-auth,
  Slack SDK). The Reconciler works with domain types and receives the client adapter
  as a dependency.
- S7.3: The Intent layer (feature service) must not reference platform-specific types
  or concepts. It produces a normalized desired state that any reconciler can consume.
- S7.4: The Reconciler may contain legitimate decision logic (capability-aware planning,
  entity matching, execution sequencing). This is not a violation of "adapters should be
  thin" — the Reconciler is a first-class architectural role, not a translator.
- S7.5: For features with only thin API translation and no reconciliation logic (e.g.,
  simple notification dispatch), the Reconciler layer may be omitted. The feature
  service calls the client adapter directly.

**When this applies vs when it does not:**

| Scenario | Three-Layer Required? | Why |
|----------|----------------------|-----|
| Access Sync (user/group lifecycle management) | ✅ Yes | Platform-specific reconciliation logic exists |
| Notification dispatch (send a message) | ❌ No — Intent → Transport is sufficient | No planning, matching, or sequencing needed |
| Provisioning (resource lifecycle) | ✅ Yes | Platform-specific capability planning exists |
| Simple API query (fetch data) | ❌ No — direct client call | No state transformation |

**Rationale:** The Hexagonal Architecture "Ports & Adapters" model describes thin
translation at the boundary. But when a feature computes intent and external systems
realize it with different object models, lifecycle rules, and capabilities, some
platform-specific decision logic is unavoidable and architecturally valid. The three-layer
model prevents this logic from being hidden in a generically-named "adapter" class
alongside protocol translation, which causes architectural drift as the class grows.

### Standard 8: Named Role Enforcement

Classes interacting with external platforms must be named for their architectural role.

| Role | Name Pattern | Anti-Pattern |
|------|-------------|--------------|
| Platform Reconciler | `<Platform>Reconciler` | Generic `<Platform>Adapter` when reconciliation logic exists |
| Client Adapter | `<Platform>ClientAdapter` or `<Platform>Client` | `<Platform>Adapter` mixing SDK calls with planning logic |
| Feature Service | `<Feature>Service` or `<Feature>Coordinator` | `<Feature>Manager` (ambiguous scope) |

**Constraints:**

- S8.1: A class named `*Adapter` that contains reconciliation logic (entity matching,
  diffing, sequencing) is a code review red flag and must be renamed or split.
- S8.2: If a legacy class named `*Adapter` is identified as a reconciler, it may retain
  a backward-compatible alias but the canonical name must reflect its actual role.
- S8.3: Protocol contracts for reconcilers and client adapters must use role-specific
  names (e.g., `PlatformReconcilerProtocol`, not `PlatformAdapterProtocol`).

## Alternatives Considered

1. **No three-layer outbound model (keep everything in "adapter"):**
   Platform integration classes accumulate mixed responsibilities. "Adapter" becomes a
   euphemism for "everything platform-related." Architectural drift is undetectable
   because the name hides multiple roles.
   Why not chosen: the three-layer model with named roles makes drift visible at review.

2. **Message bus dispatch (all transports put commands on a shared bus):**
   blinker (in-process, ADR-0083) and SQS (cross-process async, ADR-0079) are the
   governed event-driven mechanisms for the two distinct coordination scopes. A unified
   message bus adds complexity without covering any case not already served by blinker
   and SQS.
   Why not chosen: unnecessary duplication of covered ground at higher complexity.

## Consequences

**Positive:**

- The three-layer outbound model prevents mixed-responsibility platform classes.
- Named role enforcement catches architectural drift at code review.
- Reconciler and ClientAdapter naming makes the split visible at file/class-name level.

**Negative:**

- Three-layer model adds files for features with complex platform interactions. This
  overhead is justified by the role clarity it provides (S7.5 exempts thin cases).

**Neutral:**

- Inbound handler architecture consequences are governed by ADR-0089.

## Compliance and Boundaries

**This ADR governs:**

- Three-layer outbound platform model (Intent → Realization → Transport).
- Named role enforcement for platform-facing classes in `adapters/`.

**This ADR does not govern:**

- Inbound multi-transport handler architecture (ADR-0089).
- Platform provider internals (ADR-0078).
- Output/notification channels.
- HTTP authentication (ADR-0064).
- Feature package structure (ADR-0087).
- Infrastructure service consumption (ADR-0086).
- Barrel structure (ADR-0085).

**Enforcement:**

- Code review must verify platform classes in `adapters/` are named for their role (Standard 8).
- Classes named `*Adapter` containing reconciliation logic are a code review red flag (S8.1).

## Best-Practice Revalidation

| Source | Claim Validated | Alignment |
|--------|----------------|-----------|
| Cockburn, "Hexagonal Architecture" (2005) | Business logic independent of delivery mechanism; adapters translate | ✅ S7–S8: outbound model implements ports & adapters |
| Evans, *DDD* (2003) | Anti-corruption layer; separate domain model from external models | ✅ S7 separates reconciliation from translation |
| Vernon, *IDDD* (2013) | Adapter role clarity; bounded context integration patterns | ✅ S8 named role enforcement |

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
  - Validation summary: Accepted record. Round 3 challenge review passed 2026-05-07.
- Follow-up actions:
  - Track `AwsIdentityCenterAdapter` split per Standards 7–8 as a separate migration item.

## Source References

| # | Source | URL | Key Insight |
|---|--------|-----|-------------|
| 1 | Alistair Cockburn, "Hexagonal Architecture" (2005) | <https://alistair.cockburn.us/hexagonal-architecture/> | Business logic independent of delivery mechanism; ports & adapters |
| 2 | Eric Evans, *Domain-Driven Design* (2003) | — (book, ISBN 978-0321125217) | Anti-corruption layer; domain/external model separation |
| 3 | Vaughn Vernon, *Implementing Domain-Driven Design* (2013) | — (book, ISBN 978-0321834577) | Adapter role clarity; bounded context integration patterns |

## Implementation Guidance

1. **Inbound handler implementation:** Follow ADR-0089 for all `interactions/` directory
   structure, hookspec registration, and ingress layer contracts.
2. **Teams activation:** First live Teams command handler must follow ADR-0089 Standard 3
   (`register_teams_interactions` hookimpl) and ADR-0088 Standard 7 for any outbound
   Teams API calls that involve reconciliation logic.
3. **Access Sync platform classes:** Audit existing platform classes. `AwsIdentityCenterAdapter`
   mixes `capabilities()` and entity resolution (Realization role) with direct API calls
   (Transport role). Rename/split per Standards 7–8: introduce `AwsIdentityStoreReconciler`
   for the Realization layer and `AwsIdentityStoreClientAdapter` for Transport.
4. **New outbound integrations:** Any new feature `adapters/` class that contains
   reconciliation logic (capability planning, entity matching, execution sequencing)
   must use the three-layer model and the `*Reconciler` / `*ClientAdapter` naming.

## Change Log

- 2026-05-07: Scope narrowed to Standards 7–8 (outbound platform model and named role
  enforcement) following Round 2 challenge review. Standards 1–6 (inbound multi-transport
  handler architecture) delegated to ADR-0089. Metadata updated: ADR-0049/0063 removed
  (inbound concerns); ADR-0056/0090/0091 added to `constrained_by`. Context, Alternatives,
  and Source References pruned to outbound scope. Round 3 challenge review passed;
  status set to Accepted.
- 2026-05-06: Created. Includes transport-agnostic ingress layer (Standard 1),
  per-platform hookspec model (Standard 3), three-layer outbound platform model
  (Standard 7), and named role enforcement (Standard 8). Addresses cross-ADR
  governance gaps identified in the 0085-0088 conflict analysis. The three-layer
  model was validated against the Access Sync platform reconciler pattern.
