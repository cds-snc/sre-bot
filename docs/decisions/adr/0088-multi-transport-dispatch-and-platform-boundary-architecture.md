---
adr_id: ADR-0088
title: "Multi-Transport Dispatch and Platform Boundary Architecture"
status: Draft
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
last_updated: 2026-05-06
last_reviewed: 2026-05-06
next_review_due: 2026-09-03
constrained_by:
  - ADR-0044
  - ADR-0045
  - ADR-0048
  - ADR-0049
  - ADR-0059
  - ADR-0063
  - ADR-0065
  - ADR-0078
impacts:
  - ADR-0049
  - ADR-0059
  - ADR-0063
  - ADR-0078
supersedes: []
superseded_by: []
review_state: current
related_records:
  - ADR-0045
  - ADR-0048
  - ADR-0049
  - ADR-0059
  - ADR-0063
  - ADR-0067
  - ADR-0078
  - ADR-0085
  - ADR-0086
  - ADR-0087
related_packages:
  - app/packages/access
  - app/packages/geolocate
  - app/infrastructure/platforms
  - app/infrastructure/hookspecs
---

# Multi-Transport Dispatch and Platform Boundary Architecture

## Context

- Problem statement: The codebase supports two live interaction transports (FastAPI HTTP
  and Slack Bolt websocket) with stub support for Teams and Discord. As Teams moves to
  production, the absence of a governing model for multi-transport dispatch and platform
  boundary architecture creates two concrete problems:

  1. **Transport dispatch:** No rule defines how a feature package makes business logic
     available on multiple transports, how new transports are added without modifying
     existing feature code, or where the boundary between transport-specific adaptation
     and transport-agnostic business logic must be drawn.

  2. **Platform boundary architecture:** The previous draft (ADR-0088) addressed transport
     dispatch but did not distinguish between platform-specific orchestration (deciding
     *what* to do on a target platform) and pure protocol translation (executing API
     calls). The cross-ADR analysis found that this distinction is critical for features
     like Access Sync, where platform reconcilers contain legitimate decision logic
     (capability-aware planning, entity matching, execution sequencing) that is neither
     business logic nor thin translation.

  **The three-layer outbound model (discovered via Access Sync validation):**

  | Layer | Role | Example |
  |-------|------|---------|
  | **Intent** (Feature Service) | Computes desired state from business rules; platform-independent | Access Sync application service: policy evaluation, identity normalization |
  | **Realization** (Platform Reconciler) | Transforms desired state into target-specific action plan; capability-aware planning | `AwsIdentityStoreReconciler`: user+group+membership diffing and sequencing |
  | **Transport** (Client Adapter) | Executes API calls; handles protocol details | `AwsIdentityStoreClientAdapter`: boto3 calls, pagination, retry, error mapping |

  Without this distinction, platform integration classes accumulate mixed responsibilities
  (reconciliation + API translation) in a single class generically named "adapter,"
  causing architectural drift.

  **The current interaction file pattern:**

  | Package | Interaction files | Ingress layer? |
  |---------|------------------|----------------|
  | `access/sync` | `interactions/http.py`, `interactions/slack.py`, `interactions/ingress.py` | ✅ Yes |
  | `access/request` | `interactions/http.py` | HTTP only |
  | `geolocate` | `routes.py`, `platforms/slack.py`, `platforms/teams.py` (stub) | ❌ No (trivially thin) |

  `access/sync` introduced a transport-agnostic ingress layer that is the correct
  pattern but is not documented as canonical.

  **The hookspec registration model:**

  Platforms are registered via per-platform pluggy hookspecs:

  ```python
  @hookspec
  def register_slack_commands(provider: "SlackPlatformProvider") -> None: ...
  @hookspec
  def register_teams_commands(provider: "TeamsPlatformProvider") -> None: ...
  @hookspec
  def register_discord_commands(provider: "DiscordPlatformProvider") -> None: ...
  ```

  Features opt in by implementing the relevant hookimpls. This per-platform model was
  not validated for scale beyond 4 transports.

- Business/operational drivers:
  - Teams support is moving from stub to production; governing model must exist first.
  - The three-layer outbound model prevents mixed-responsibility platform classes.
  - Named role enforcement (Reconciler vs Adapter) catches drift at code review time.

- Constraints:
  - ADR-0049: transport registration must happen through pluggy hookspecs.
  - ADR-0059: `interactions/` is the governed home for interaction files.
  - ADR-0063: all transport handlers must be thin adapters (parse → invoke → map).
  - ADR-0078: platform providers are infrastructure services.
  - ADR-0065: `CommandPayload`/`CommandResponse` are `@dataclass` boundary types.

- Non-goals:
  - This record does not govern output/notification channels (proactive messages).
  - This record does not define platform provider implementation internals (ADR-0078).
  - This record does not govern HTTP authentication (ADR-0064).
  - This record does not govern barrel structure (ADR-0085) or package isolation (ADR-0087).

## Decision

Feature packages serve multiple input transports through a **Ports & Adapters** model:
a transport-agnostic ingress layer contains business orchestration, thin per-transport
adapter modules handle parsing and response formatting, and outbound platform
interactions follow a three-layer model separating intent, realization, and transport.

### Standard 1: Transport-Agnostic Ingress Layer

Every feature operation reachable from more than one transport must have a single
transport-agnostic ingress function (or module). Transport adapters call this function;
they do not re-implement business logic.

```python
# interactions/ingress.py — transport-agnostic orchestration
def enqueue_user_sync(
    coordinator: SyncCoordinatorProtocol,
    idempotency: IdempotencyServiceProtocol,
    settings: AccessSyncSettings,
    user_email: str,
    trigger: str,
) -> SyncResult:
    """Pure business orchestration — no transport-specific types."""
    ...
```

```python
# interactions/http.py — HTTP adapter
@router.post("/sync")
async def trigger_sync(...) -> SyncJobResponse:
    result = enqueue_user_sync(coordinator, idempotency, settings, ...)
    return SyncJobResponse.from_domain(result)

# interactions/slack.py — Slack adapter
def handle_sync_command(ack, say, command):
    ack()
    result = enqueue_user_sync(coordinator, idempotency, settings, ...)
    say(format_slack_blocks(result))
```

**Constraints:**

- S1.1: The ingress function must accept only domain types (`@dataclass(frozen=True)`,
  primitives, Protocol-typed services) — never transport-specific types.
- S1.2: The ingress function must return a domain result type — never a transport-
  specific response.
- S1.3: Each transport adapter owns the conversion between its transport format and the
  domain types consumed/produced by the ingress function.
- S1.4: For trivially thin operations (single function call, no orchestration), the
  ingress layer may be the service function itself (e.g., `geolocate_ip()`). A separate
  `ingress.py` is not required when the shared function already has no transport
  dependencies.

### Standard 2: Adapter Independence

Transport adapters are independent modules that do not import from each other.

**Constraints:**

- S2.1: No adapter module may import from another adapter module within the same package.
- S2.2: Each adapter owns its own authentication, parsing, and response formatting.
  There is no shared "adapter base class."
- S2.3: Each adapter module must be independently importable — importing `http.py` must
  not trigger loading of Slack SDK dependencies, and vice versa.

### Standard 3: Per-Platform Hookspec Registration

The per-platform hookspec model (`register_slack_commands`, `register_teams_commands`,
`register_discord_commands`) is retained as the canonical registration mechanism.

**Rationale:**

- **Explicit opt-in:** Features declare platform support by implementing the hookspec.
- **Type safety:** Each hookspec provides the platform-specific provider type as argument.
- **Independent lifecycle:** Platforms can be added, stubbed, or removed without
  modifying a shared registry abstraction.
- **Manageable scale:** ≤6 transports is within the range where explicit hookspecs are
  clearer than a generic registry. Revisit if platform count exceeds 6.

**Constraints:**

- S3.1: Adding a new platform requires: (a) hookspec in `infrastructure/hookspecs/`,
  (b) platform provider in `infrastructure/platforms/`, (c) feature opt-in via hookimpl.
- S3.2: Platform support is always per-feature opt-in. No mechanism automatically
  exposes all features on all platforms.
- S3.3: HTTP route registration uses the FastAPI router model, not the
  `CommandPayload`/`CommandResponse` model. HTTP is a first-class transport with its
  own hookspec.

### Standard 4: The `interactions/` Directory Contract

```
packages/<feature>/interactions/
    __init__.py
    ingress.py       # Transport-agnostic business orchestration
    http.py          # FastAPI route adapter (APIRouter)
    slack.py         # Slack Bolt adapter (if applicable)
    teams.py         # Teams adapter (if applicable)
    discord.py       # Discord adapter (if applicable)
```

**Constraints:**

- S4.1: Each adapter file corresponds to exactly one transport.
- S4.2: `ingress.py` contains no transport-specific imports.
- S4.3: Features supporting only HTTP may use `routes.py` at package level. The
  `interactions/` directory becomes mandatory when a second transport is added.
- S4.4: Background jobs are not placed in `interactions/` — they are registered via
  `register_background_job` hookspec.

### Standard 5: Typed Command Handler Contract

Platform command handlers receive `CommandPayload` and return `CommandResponse` (both
`@dataclass` types defined in `infrastructure/platforms/models.py`).

**Constraints:**

- S5.1: `CommandPayload` and `CommandResponse` are the governed boundary types for all
  platform command handlers (Slack, Teams, Discord).
- S5.2: The command handler callable signature is:
  `Callable[[CommandPayload], CommandResponse]` (sync) or
  `Callable[[CommandPayload], Awaitable[CommandResponse]]` (async).
- S5.3: Platform providers convert native payloads into `CommandPayload` before
  invoking the handler, and convert `CommandResponse` back after.
- S5.4: Feature packages must not import platform-native types (slack_bolt.Say,
  teams.TurnContext) in their ingress layer. Platform-native types are permitted only
  in the adapter file for that specific platform.

### Standard 6: Error Mapping Per Transport

Each transport adapter maps domain results to its transport-specific error format.

| Transport | Error Mapping |
|-----------|---------------|
| HTTP | `OperationResult` → RFC 9457 error response with status code |
| Slack | `OperationResult` → Slack message blocks with error text |
| Teams | `OperationResult` → Adaptive Card with error message |
| Discord | `OperationResult` → Discord embed with error text |
| Background job | `OperationResult` → logged; retried if transient error |

**Constraints:**

- S6.1: The ingress layer must not perform error formatting — it returns domain results.
- S6.2: Each adapter owns a mapping function converting domain results to native format.
- S6.3: 5xx-equivalent errors must redact internal details in all transports.

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

1. **Unified transport registry (single hookspec for all platforms):**
   Loses type safety per platform. The registry becomes a string-keyed lookup (Service
   Locator for transports). At 4 platforms, the generic registry is more complex than
   4 explicit hookspecs.
   Why not chosen: explicit hookspecs are simpler and type-safe.

2. **No mandatory ingress layer (adapters call services directly):**
   Business logic duplicated across adapters when operations have shared orchestration.
   Why not chosen: ingress pattern prevents duplication (P1.4 exception covers thin ops).

3. **Abstract base class for adapters:**
   Adapters differ in parsing, auth, and response format — an ABC would be mostly empty.
   Python Protocols are preferred over inheritance for structural contracts.
   Why not chosen: forced inheritance adds coupling without shared behavior.

4. **No three-layer outbound model (keep everything in "adapter"):**
   Platform integration classes accumulate mixed responsibilities. "Adapter" becomes a
   euphemism for "everything platform-related." Architectural drift is undetectable
   because the name hides multiple roles.
   Why not chosen: the three-layer model with named roles makes drift visible at review.

5. **Message bus dispatch (all transports put commands on a shared bus):**
   Over-engineered for request-response transports. The codebase is primarily
   request-response, not event-driven.
   Why not chosen: premature abstraction.

## Consequences

**Positive:**

- Teams and Discord handlers follow the same established pattern as Slack handlers.
- Business logic written once in `ingress.py`, shared across all transports.
- The three-layer outbound model prevents mixed-responsibility platform classes.
- Named role enforcement catches architectural drift at code review.
- `CommandPayload`/`CommandResponse` provide stable typed contracts.

**Negative:**

- `interactions/` directory adds structural overhead for HTTP-only features (deferred
  until second transport per S4.3).
- Three-layer model adds files for features with complex platform interactions. This
  overhead is justified by the role clarity it provides.
- Per-platform hookspecs require one hookimpl per platform per feature (scales linearly).

**Neutral:**

- Slack Bolt websocket lifecycle remains platform-specific.
- HTTP routes continue to use FastAPI `APIRouter` conventions.
- Background jobs remain hookspec-based, not treated as "transports."

## Compliance and Boundaries

**This ADR governs:**

- Multi-transport `interactions/` directory structure.
- Transport-agnostic ingress layer requirement.
- Per-platform hookspec registration model.
- Adapter independence.
- `CommandPayload`/`CommandResponse` typed contract.
- Error mapping per transport.
- Three-layer outbound platform model (Intent → Realization → Transport).
- Named role enforcement for platform-facing classes.

**This ADR does not govern:**

- Platform provider internals (ADR-0078).
- Output/notification channels.
- HTTP authentication (ADR-0064).
- Feature package structure beyond `interactions/` (ADR-0087).
- Infrastructure service consumption (ADR-0086).
- Barrel structure (ADR-0085).

**Enforcement:**

- Code review must verify multi-transport features have an ingress layer.
- Code review must verify platform classes are named for their role (Standard 8).
- Lint rules should flag platform-native type imports outside adapter files.

## Best-Practice Revalidation

| Source | Claim Validated | Alignment |
|--------|----------------|-----------|
| Cockburn, "Hexagonal Architecture" (2005) | Business logic independent of delivery mechanism; adapters translate | ✅ Standards 1–2 |
| Cosmic Python Ch. 12 | Separate entrypoints call same service layer | ✅ S1: ingress layer shared by adapters |
| Cosmic Python Appendix B | `entrypoints/` directory for multiple transports | ✅ S4: `interactions/` directory |
| FastAPI "Bigger Applications" | `APIRouter` per domain, composed via `include_router()` | ✅ HTTP adapter uses APIRouter |
| ADR-0060 (this project) | "Routes are thin adapters: parse → invoke → map" | ✅ S1 extends this to all transports |
| Pluggy documentation | Hookspecs define contract; hookimpls opt in | ✅ S3 uses per-platform hookspecs |
| Evans, *DDD* (2003) | Anti-corruption layer; separate domain model from external models | ✅ S7 separates reconciliation from translation |

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: Draft record. Full rewrite from deprecated draft. Pending author review.
- Follow-up actions:
  - Author review of new scope.
  - Challenge review after author approval.

## Source References

| # | Source | URL | Key Insight |
|---|--------|-----|-------------|
| 1 | Alistair Cockburn, "Hexagonal Architecture" (2005) | <https://alistair.cockburn.us/hexagonal-architecture/> | Business logic independent of delivery mechanism; ports & adapters |
| 2 | Percival & Gregory, *Architecture Patterns with Python* Ch. 12 | <https://www.cosmicpython.com/book/chapter_12_cqrs.html> | Separate entrypoints call same service/handler layer |
| 3 | Percival & Gregory, Appendix B (Project Structure) | <https://www.cosmicpython.com/book/appendix_project_structure.html> | `entrypoints/` directory pattern for multi-transport |
| 4 | FastAPI, "Bigger Applications — Multiple Files" | <https://fastapi.tiangolo.com/tutorial/bigger-applications/> | `APIRouter` per feature; `include_router()` |
| 5 | Pluggy Documentation | <https://pluggy.readthedocs.io/en/stable/> | Per-hookspec opt-in; hookimpls accept fewer args than spec |
| 6 | Slack Bolt for Python | <https://slack.dev/bolt-python/concepts> | Slack command handling; ack/say pattern; websocket mode |
| 7 | Microsoft Bot Framework SDK | <https://learn.microsoft.com/en-us/azure/bot-service/> | Teams TurnContext; Adaptive Cards response model |
| 8 | Eric Evans, *Domain-Driven Design* (2003) | — (book, ISBN 978-0321125217) | Anti-corruption layer; domain/external model separation |
| 9 | Vaughn Vernon, *Implementing Domain-Driven Design* (2013) | — (book, ISBN 978-0321834577) | Adapter role clarity; bounded context integration patterns |

## Implementation Guidance

1. **Immediate (new features):** Any new multi-transport feature must follow the
   `interactions/` contract (S4) and provide an ingress layer (S1).
2. **Teams activation:** First live Teams command handler establishes the pattern.
   Must implement `register_teams_commands(provider)` hookimpl and place adapter
   code in `interactions/teams.py`.
3. **Geolocate migration:** Current `platforms/` directory should be renamed to
   `interactions/` for consistency. `geolocate_ip()` is trivially thin (S1.4 exception).
4. **Access Sync platform classes:** Audit existing platform classes. Any class named
   `*Adapter` that contains reconciliation logic should be evaluated for rename to
   `*Reconciler` per Standard 8. If a class mixes reconciliation and SDK calls, split
   per Standard 7.

## Change Log

- 2026-05-06: Full rewrite from deprecated draft. Added three-layer outbound platform
  model (Standard 7), named role enforcement (Standard 8). Previous draft addressed
  only transport dispatch; new version addresses the platform boundary architecture gap
  identified in the 0085-0088 conflict analysis. The three-layer model was validated
  against the Access Sync platform reconciler pattern.
