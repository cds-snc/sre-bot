---
adr_id: ADR-0089
title: "Platform Interaction Handler Standard"
status: Draft
decision_type: Standard
tier: Tier-2
governance_domain: application
primary_domain: Transport and API
secondary_domains:
  - Package and Plugin Architecture
  - Dependency and Composition
  - Runtime and Lifecycle
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
  - ADR-0050
  - ADR-0059
  - ADR-0065
  - ADR-0077
  - ADR-0079
  - ADR-0083
impacts:
  - ADR-0059
  - ADR-0067
  - ADR-0078
  - ADR-0083
  - ADR-0088
  - ADR-0090
  - ADR-0091
supersedes:
  - ADR-0059
superseded_by: []
review_state: current
related_records:
  - ADR-0045
  - ADR-0046
  - ADR-0048
  - ADR-0050
  - ADR-0054
  - ADR-0057
  - ADR-0058
  - ADR-0063
  - ADR-0079
  - ADR-0083
  - ADR-0085
  - ADR-0086
  - ADR-0087
  - ADR-0088
  - ADR-0090
  - ADR-0091
related_packages:
  - app/packages/access/interactions
  - app/packages/access/sync/interactions
  - app/infrastructure/events
  - app/infrastructure/idempotency
  - app/infrastructure/hookspecs
---

# Platform Interaction Handler Standard

## Context

- **Problem statement:** The application receives events from three interaction channels:
  FastAPI HTTP endpoints (called by Backstage and API clients), Slack Bolt (commands, views,
  block actions), and Microsoft Teams (task/fetch, task/submit invoke activities). Each channel
  fires independent, stateless payloads at handlers.

  ADR-0059 (Feature Interaction Boundaries and Platform Integration Standard) established the
  structural layer model — directory layout, hookspec registration, HTTP-first bridge, platform
  lifecycle — but did not define the **behavioral model** for handlers, particularly for
  multi-step interactions that span multiple events, multiple channels, or multiple ECS tasks.

  In the absence of a governing behavioral standard, prior architecture proposals introduced an
  `infrastructure/workflow/` coordinator with a `WorkflowStateProtocol` that owned state
  transition logic. This is architecturally incorrect because:

  1. An in-process state machine violates ADR-0045 Principle 6 (stateless processes — 12-Factor
     App Factor VI). The app process would own state that must survive across events and process
     restarts. Only backing services (DynamoDB) may own durable state.
  2. Slack Socket Mode and Teams Bot Framework deliver each platform event as an **independent,
     stateless payload** to a handler. There is no platform-managed session between events.
     The platform is an event source, not an interaction continuity owner.
  3. The correct coordination pattern is **choreography** (events + domain entity status in
     DynamoDB), not orchestration (coordinator owns state machine). This is consistent with the
     Saga pattern for distributed systems (Richardson, microservices.io).

  This ADR supersedes ADR-0059 and defines the complete Platform Interaction Handler Standard,
  incorporating ADR-0059's structural rules and extending them with the behavioral model.

- **Business/operational drivers:**
  - Multi-channel parity: the same domain logic must be reachable from HTTP, Slack, and Teams
    without duplicating business logic or behavioral rules.
  - Stateless ECS deployment: the application runs with `desired_count = 2` in ECS Fargate.
    No in-process state may be shared between ECS tasks or persisted across restarts.
  - Slack 3-second ack contract: interactive Slack events (view submissions, block actions)
    must be acknowledged within 3 seconds. Domain logic must be sequenced correctly relative
    to this window.
  - Teams synchronous invoke contract: Teams task/fetch and task/submit require a synchronous
    HTTP 200 response before any domain processing can occur.
  - Partial failure resilience: when a domain entity write succeeds but a downstream
    notification fails, the interaction must not be permanently stalled.
  - Testability: domain service logic must be independently testable without platform SDK
    dependencies. The HTTP endpoint is the primary test surface.

- **Constraints:**
  - ADR-0045 Principle 6: stateless process design — 12-Factor VI. No state may be stored
    in the application process between events.
  - ADR-0045 Principle 7: managed cloud service > library > custom code. Domain state lives
    in DynamoDB (Tier 1 managed service), not in-process.
  - ADR-0048: no cross-package imports; dependency direction strictly downward.
  - ADR-0049: handler registration is startup-driven via pluggy hookspecs; no import-time
    side effects.
  - ADR-0050: fallible service operations return `OperationResult[T]`.
  - ADR-0065: normalised intent objects use `TypedDict` (dict-shaped adapter); domain entity
    models use `@dataclass(frozen=True)`; service contracts use `Protocol`.
  - ADR-0077: infrastructure services injected via `Annotated[Protocol, Depends(...)]` for
    Category A services. ingress.py receives infrastructure services by dependency injection.
  - ADR-0079: SQS for cross-process async continuation. In-process events (blinker, ADR-0083)
    for in-process coordination only.
  - ADR-0083: the `EventDispatcher` facade (blinker) provides error-isolated in-process event
    dispatch. Subscriber failures do not propagate to the publisher.
  - ADR-0085–0088 (Draft): barrel governance, service resolution context, vertical isolation,
    and multi-transport dispatch. These are related but not yet Accepted; they are referenced
    in `related_records` and their constraints are respected in this standard.

- **Non-goals:**
  - This ADR does not define `correlation_id` cardinality, minting authority, or payload
    carrier format per channel. Those are ADR-0090's scope.
  - This ADR does not define idempotency key schema, DynamoDB write ordering, SQS visibility
    timeout, or DLQ policy. Those are ADR-0091's scope.
  - This ADR does not define per-platform SDK integration constraints (Slack private_metadata
    schema, Teams Adaptive Card data field format). Those belong in ADR-0096 (Slack) and
    ADR-0097 (Teams).
  - This ADR does not govern cross-process event delivery. SQS is governed by ADR-0079.
  - This ADR does not govern identity resolution. That is ADR-0061's scope.
  - This ADR does not govern Discord. Discord support is a stub with no production
    implementation.

## Decision

The platform interaction handler model is a **stateless, event-driven, four-layer architecture**.
Every handler is a pure function: receive event → read domain state from backing service → apply
logic → write domain state → publish in-process events → return platform response. The process
owns no state between events.

Multi-step interactions are not managed by an in-process coordinator. The domain entity's
`status` field in DynamoDB is the authoritative record of "where we are" in a multi-step
interaction. The `correlation_id` is the shared key that links events across channels and
process instances.

This decision supersedes ADR-0059 in full. All standards from ADR-0059 are incorporated below,
amended where the behavioral model requires it.

---

### Standard 1: Handler Layer Architecture

The interaction handling model uses a strict four-layer architecture. All dependencies flow
downward. No layer may import from a layer above it.

```
Transport Adapter      interactions/slack.py, interactions/teams.py, interactions/http.py
        │              Parse platform payload → normalised intent → call ingress → format response
        ▼
   ingress.py          Intent resolver + idempotency gate (Standard 5)
        │              Platform-agnostic; no platform-specific parsing
        ▼
   service.py          Business logic; domain entity status transitions (Standard 8)
        │              Channel-agnostic; no platform SDK imports
        ▼
Infrastructure         DynamoDB, SQS, blinker (EventDispatcher), IdempotencyService
```

**Rules:**

- A1: `service.py` must never import from `interactions/`. Dependency direction is strictly
  downward.
- A2: Transport adapters parse platform payloads and produce a normalised intent (Standard 7).
  All platform-specific parsing is adapter-only. ingress.py receives only the normalised intent.
- A3: `ingress.py` resolves a normalised intent to exactly one domain service call and gates on
  idempotency (Standard 5). It is platform-agnostic — it knows nothing about Slack, Teams, or
  HTTP specifics.
- A4: Business logic belongs exclusively in `service.py`. Route handlers, `ingress.py`, and
  adapters contain no business logic.
- A5: Presenters map domain results to channel-specific response formats. They do not contain
  business logic.
- A6: The HTTP endpoint (`interactions/http.py`) is the canonical test surface. If a feature
  works via HTTP, the business logic is validated for all platforms (from ADR-0059 H1).
- A7: Features implement platform handlers only for platforms they support. No mandate exists
  that all features support all platforms.

---

### Standard 2: Feature-Side Directory Structure

Feature packages organise inbound interaction handling in a dedicated `interactions/` directory.
This supersedes the directory standard from ADR-0059 Standard 2.

```
packages/<feature>/
├── __init__.py          # @hookimpl functions only (ADR-0049)
├── domain.py            # Frozen dataclass models (ADR-0065)
├── service.py           # Business logic (channel-agnostic)
├── providers.py         # @lru_cache DI factory functions (ADR-0056)
├── settings.py          # BaseSettings singleton per domain (ADR-0055)
├── schemas.py           # Pydantic I/O boundary models (ADR-0065)
├── presenters.py        # Channel-specific response formatting
├── adapters/            # Outbound: Protocol-defined external integrations
│   ├── __init__.py
│   └── <provider>.py
└── interactions/        # Inbound: channel-specific request handlers
    ├── ingress.py       # Intent resolver + idempotency gate (Standard 5)
    ├── http.py          # FastAPI route handlers (primary testable surface)
    ├── slack.py         # Slack event/view/action handlers
    └── teams.py         # Teams invoke/card handlers
```

For complex features with multiple subdomains, the same structure applies per subdomain:

```
packages/<feature>/
├── __init__.py          # Umbrella @hookimpl functions only
└── <subdomain>/
    ├── __init__.py
    ├── domain.py
    ├── service.py
    ├── providers.py
    └── interactions/
        ├── ingress.py
        ├── http.py
        ├── slack.py
        └── teams.py
```

**Rules:**

- B1: `service.py` must never import from `interactions/`. Dependency flows inward only.
- B2: `interactions/http.py` is the canonical test surface. Slack/Teams handlers are thin
  adapters.
- B3: Presenters map domain results to channel-specific formats. No business logic in
  presenters.
- B4: Features implement platform handlers only for platforms they support.
- B5: Cross-package imports are forbidden at all levels (ADR-0048, ADR-0087).
- B6: `__init__.py` contains only `@hookimpl` functions (ADR-0049, ADR-0087). No service
  composition, no module-level provider calls (ADR-0086).

---

### Standard 3: Hookspec Registration Contract

Feature packages register interaction capabilities via pluggy hookspecs defined in
`app/infrastructure/hookspecs/features.py`. Registration uses per-platform hooks with concrete
platform service types to preserve platform-native type signatures (from ADR-0059 Standard 3).

Amended to add blinker event handler registration.

**Per-platform hookspecs:**

```python
# app/infrastructure/hookspecs/features.py

@hookspec
def register_slack_interactions(provider: "SlackPlatformProvider") -> None:
  """Register Slack interactions (commands, views, block actions, shortcuts) with the provider."""

@hookspec
def register_teams_interactions(provider: "TeamsPlatformProvider") -> None:
  """Register Teams interactions (invoke activities, card handlers) with the provider."""

@hookspec
def register_routes(app: "FastAPI") -> None:
    """Register HTTP routes with the FastAPI application."""

@hookspec
def register_event_handlers(dispatcher: "EventDispatcher") -> None:
    """Register in-process blinker event handlers (ADR-0083 Standard 3)."""
```

**Feature-side hookimpl example:**

```python
# packages/access/__init__.py

@hookimpl
def register_slack_interactions(provider: "SlackPlatformProvider") -> None:
    from .interactions.slack import register
    register(provider)

@hookimpl
def register_routes(app: "FastAPI") -> None:
    from .interactions.http import router
    app.include_router(router)

@hookimpl
def register_event_handlers(dispatcher: "EventDispatcher") -> None:
    from .interactions.events import register
    register(dispatcher)
```

**Rules:**

- K1: Hookspec parameter types are concrete (e.g., `SlackPlatformProvider`), not abstract
  Protocols. Platform APIs are asymmetric — no shared Protocol is appropriate (ADR-0078).
- K2: Features that do not support a platform simply omit the hookimpl. If a hookspec fires,
  the platform is available; if it does not fire for a feature, that feature runs on HTTP and
  background jobs only.
- K3: Registration is startup-driven via pluggy. No import-time side effects (ADR-0049).
- K4: Hookimpls use lazy imports (deferred to function body) to avoid circular import issues
  and to minimise startup cost for disabled features.
- K5: Blinker event handler registration (`register_event_handlers`) happens in Phase 4
  (feature activation), not at import time. This is the required hook for all in-process
  blinker subscriptions (ADR-0083 Standard 3).

---

### Standard 4: Platform Transport Lifecycle

The startup and shutdown sequence for platform connections follows a deterministic ordering.
This standard carries forward ADR-0059 Standard 5 with an amendment for HTTP Mode support.

**Lifecycle sequence:**

1. **Settings check** — skip platform if disabled in configuration.
2. **Service construction** — inject narrowest settings slice; construct the platform service
   instance.
3. **Handler registration** — fire per-platform hookspecs (`register_slack_interactions`,
   `register_teams_interactions`, `register_routes`, `register_event_handlers`).
4. **Transport connection** — start Slack transport / Teams HTTP handler / FastAPI binding.
   For Slack: either Bolt HTTP mode (ALB endpoint, recommended for production) or Socket Mode
   (WebSocket daemon thread, appropriate for development/firewall-restricted environments).
   Mode is settings-driven (`SLACK_SOCKET_MODE: bool`, default `False` in production).
5. **Graceful shutdown** — drain in-flight handlers, close connections, join threads with
   timeout. Follows ADR-0057 shutdown obligations.

**Transport mode guidance (Slack):** Slack's official documentation recommends HTTP for
production applications: *"To have the highest possible reliability for application connectivity,
we recommend using HTTP for production applications."* (docs.slack.dev, Comparing HTTP and
Socket Mode). Socket Mode is appropriate for local development and firewall-restricted
deployments. The transport mode does not affect handler code — Bolt abstracts the protocol.

**Rules:**

- L1: Steps 1–4 execute during the FastAPI lifespan startup phase (ADR-0046).
- L2: Transport connection (Step 4) must not block other startup phases. Slack Socket Mode
  runs in a daemon thread. HTTP mode binds within the ASGI lifecycle.
- L3: Graceful shutdown (Step 5) drains in-flight handlers before closing the transport
  connection. SQS consumer workers drain before transport closes (ADR-0057).
- L4: Settings (`SLACK_SOCKET_MODE`) control the transport mode. Changing mode requires no
  handler code changes — Bolt abstracts the protocol at the infrastructure layer.

---

### Standard 5: ingress.py Contract

`ingress.py` is the platform-agnostic intent resolver and idempotency gate. It is not a state
machine coordinator, workflow owner, or multi-step sequencer.

**What `ingress.py` IS:**

| ingress.py IS | ingress.py is NOT |
|---------------|-------------------|
| Intent resolver — maps normalised intent to one domain call | State machine coordinator |
| Idempotency gate — checks/claims key before domain execution | Workflow progression owner |
| Platform-agnostic entry point | Orchestrator that sequences multi-step logic |
| Delegation boundary — calls one service method per intent | Transport adapter (parsing belongs to callers) |

**Rules:**

- I1: `ingress.py` receives a normalised intent object (Standard 7). It never parses
  platform-specific payloads directly.
- I2: `ingress.py` checks the idempotency key before executing domain logic. If a duplicate
  is detected, it returns a semantically equivalent response without re-executing the domain
  call (ADR-0091 Standard 3).
- I3: `ingress.py` calls exactly one domain service method per intent. It does not sequence
  multiple service calls for a single event.
- I4: `ingress.py` returns `OperationResult[T]` (ADR-0050). The transport adapter maps this
  to the platform-specific response format.
- I5: `ingress.py` receives infrastructure services by dependency injection
  (`Annotated[Protocol, Depends(...)]` — ADR-0077). It does not call provider functions
  directly.

---

### Standard 6: Ack-First Contract

For all interactive platform events that require an explicit acknowledgment, `ack()` MUST be
called before any domain logic executes.

**Rules:**

- F1: **Slack interactive events** (view submissions, block actions, slash commands): call
  `ack()` first, unconditionally. The 3-second window begins at event delivery by Slack, not
  at `ack()`. Domain logic, DynamoDB writes, and SQS enqueues execute after `ack()`.

  ```python
  async def handle_request_submitted(ack, body, ingress: AccessIngress):
      await ack()                # Always first — Slack 3-second contract
      correlation_id = json.loads(body["view"]["private_metadata"])["cid"]
      await ingress.handle(intent="submit_request", correlation_id=correlation_id, payload=body)
  ```

- F2: **Teams task/fetch and task/submit**: respond with HTTP 200 synchronously before
  delegating to domain logic. Long-running work that exceeds the synchronous window must be
  deferred via SQS after the HTTP 200 (ADR-0091 Standard 4).
- F3: **HTTP/REST endpoints**: no explicit `ack()` is required. The HTTP response IS the
  synchronous return. Long-running work is deferred via SQS after writing the domain entity.
- F4: If `ack()` fails (network error, timeout), the adapter must NOT proceed to domain logic.
  Log the failure with `correlation_id` and return without executing the domain call.

---

### Standard 7: Normalised Intent Contract

Transport adapters produce a normalised intent object that `ingress.py` consumes.
`ingress.py` reads ONLY from this object. No platform-specific payload fields may be accessed
by `ingress.py` or below.

**Mandatory fields:**

```python
from typing import Literal
from typing import TypedDict  # ADR-0065: dict-shaped adapter


class NormalisedIntent(TypedDict):
    correlation_id: str          # Domain entity primary key (UUID) — ADR-0090
    intent: str                  # Domain command name, e.g. "submit_request"
    actor_id: str                # User performing the action — resolved per ADR-0061
    platform: Literal["http", "slack", "teams"]  # Source channel (logging/tracing only)
    raw_payload: dict            # Platform-specific data; opaque to ingress.py
```

**Rules:**

- N1: Transport adapters are solely responsible for constructing the `NormalisedIntent`. They
  extract `correlation_id` from platform payloads (Slack `private_metadata`, Teams card data,
  HTTP URL path) as governed by ADR-0090.
- N2: `ingress.py` must not access `raw_payload` for routing decisions. Routing is based solely
  on `intent`. `raw_payload` is passed to the domain service only if the service requires
  platform-specific context it cannot fetch from DynamoDB.
- N3: `actor_id` is resolved by the transport adapter per ADR-0061 identity resolution priority
  (JWT > Platform > Webhook > System). `ingress.py` does not perform identity resolution.
- N4: `platform` is metadata for structured logging (ADR-0054) and is never used for
  conditional domain logic. Platform-specific behaviour belongs in the transport adapter.

---

### Standard 8: Stateless Handler Invariant

Every handler is a pure function from a platform event to a response. The process owns no state
between events.

**Handler invariant (mandatory sequence):**

```
1. ack() — platform acknowledgment (Standard 6; before domain logic)
2. read — fetch domain entity by correlation_id from DynamoDB
3. validate — check status transition is legal; reject illegal transitions
4. write — write updated entity to DynamoDB (atomic with idempotency key — ADR-0091)
5. publish — emit blinker events and/or enqueue SQS messages (Standard 9)
6. return — platform response (OperationResult mapped to platform format)
```

**Rules:**

- S1: Handlers read domain state from DynamoDB at the start of each event. In-process memory
  must never carry state across event boundaries (ADR-0045 Principle 6; 12-Factor VI).
- S2: The domain entity write (Step 4) always precedes side-effect publication (Step 5). Side
  effects are conditional on a successful entity write.
- S3: The domain entity's `status` field IS the multi-step continuation model. There is no
  separate `WorkflowState` entity, coordinator class, or in-process state machine.
- S4: Domain status transitions are pure functions in `service.py`. A legal transition table
  (e.g., `DRAFT → PENDING_APPROVAL`) is defined per entity type. Illegal transitions raise a
  domain exception; `ingress.py` maps this to `OperationResult.permanent_error`.
- S5: The `correlation_id` is the shared key across all channels and all ECS tasks. It is
  minted once at interaction creation and carried by every subsequent event (ADR-0090).

---

### Standard 9: Side-Effect Compensation Framework

When the domain entity write (Standard 8 Step 4) succeeds but a downstream side effect fails,
the compensation strategy depends on the side-effect class. This framework resolves the
dual-write problem for this stack.

| Side-effect class | Compensation strategy | Rules |
|------------------|-----------------------|-------|
| Slack modal open (`views.open`) — requires `trigger_id` | Execute within ack window. If it fails, `ack()` with error response. No retry possible. | `trigger_id` expires in 3 seconds; single-use. Cannot be deferred to SQS. |
| Platform notification (message to approver, confirmation to requester) | Enqueue to SQS notification queue after entity write. SQS provides at-least-once delivery with DLQ. | Decoupled from ack window; delayed delivery acceptable for notifications. |
| In-process domain event (blinker) with no external I/O | Fire-and-forget with error isolation (ADR-0083 Standard 4). Log failure with `correlation_id`. | Internal coordination only; no external durability required. |
| Critical gate — if not delivered, interaction stalls permanently (e.g., approver notification is the only trigger for approval) | Transactional outbox: write outbox record atomically with domain entity in one `TransactWriteItems` call; Phase 6 background worker (ADR-0058) delivers and deletes the record. | Guaranteed at-least-once; no data loss on process crash. DynamoDB Streams or polling relay both acceptable. |

**Rules:**

- E1: Blinker subscribers that trigger platform I/O (Slack or Teams API calls) must NOT be
  fire-and-forget. They must either enqueue to SQS within the ack window, or use the
  transactional outbox for critical gates.
- E2: SQS enqueues (any class) must happen ONLY after the domain entity write succeeds. Never
  enqueue before writing the entity.
- E3: For critical gate side effects, the outbox record is written atomically with the domain
  entity in the same `TransactWriteItems` call (ADR-0091 Standard 2).
- E4: SQS notification messages carry only `correlation_id` + notification target + payload.
  The worker re-fetches domain state from DynamoDB on dequeue — it does not trust message
  content as authoritative domain state (ADR-0045 Principle 6; 12-Factor VI).
- E5: The classification of a side effect as "critical gate" is a feature-level decision,
  documented in the feature's Tier-4 ADR.

---

## Compliance

An interaction handler is compliant with this standard if and only if:

1. It uses the four-layer architecture (Standard 1) with imports flowing strictly downward.
2. Its `interactions/` directory follows the prescribed structure (Standard 2).
3. Hookimpl registration is startup-driven via pluggy hookspecs (Standard 3).
4. `ack()` or equivalent acknowledgment precedes all domain logic (Standard 6).
5. `ingress.py` is limited to intent resolution and idempotency gating (Standard 5).
6. `NormalisedIntent` carries the required fields; no platform-specific fields reach
   `ingress.py` (Standard 7).
7. The handler follows the mandatory sequence: ack → read → validate → write → publish →
   return (Standard 8).
8. Side effects are compensated according to the framework in Standard 9.

---

## Migration

ADR-0059 is fully superseded by this ADR. All ADR-0059 standards are incorporated above.

The amendment to `ingress.py`'s role (from "shared admission logic: enabled-check,
lock-check" in ADR-0059 Standard 2 B3 to "intent resolver + idempotency gate" in Standard 5
above) is the primary behavioral change. Lock checks are a domain service concern that
executes inside `service.py`, not inside `ingress.py`.

Existing handler code that currently calls `ingress.py` as a lock-gating admission step
must be migrated to the domain service before this ADR is marked Accepted. The
`interactions/http.py` primary test surface requirement (Standard 1 A6) is already
implemented in `packages/access/sync/interactions/`.

ADR-0059 file must be moved to `adr/superseded/` and updated with `superseded_by: ADR-0089`
after this ADR is Accepted.
