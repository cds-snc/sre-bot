---
adr_id: ADR-0090
title: "Cross-Channel Correlation and HTTP Coordination Standard"
status: Accepted
decision_type: Standard
tier: Tier-2
governance_domain: application
primary_domain: Transport and API
secondary_domains:
  - Data and Persistence
  - Runtime and Lifecycle
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
  - ADR-0063
  - ADR-0065
  - ADR-0077
  - ADR-0079
  - ADR-0089
impacts:
  - ADR-0063
  - ADR-0089
  - ADR-0091
  - ADR-0096
  - ADR-0097
supersedes: []
superseded_by: []
review_state: current
related_records:
  - ADR-0050
  - ADR-0054
  - ADR-0058
  - ADR-0061
  - ADR-0065
  - ADR-0079
  - ADR-0083
  - ADR-0085
  - ADR-0086
  - ADR-0087
  - ADR-0088
  - ADR-0089
  - ADR-0091
related_packages:
  - app/packages/access/interactions
  - app/infrastructure/idempotency
---

# Cross-Channel Correlation and HTTP Coordination Standard

## Context

- **Problem statement:** Multi-step interactions in this application span multiple platform
  channels — a request may be initiated via Backstage HTTP, require a Slack approval interaction,
  and ultimately be confirmed via Teams. Each channel delivers independent, stateless payloads
  to the application. There is no platform-managed session connecting these events.

  For the application to correctly associate events from different channels with the same
  underlying domain entity, it must establish and enforce a shared, durable identifier carried
  by every payload, on every channel, throughout the entity's lifecycle.

  The following questions were open prior to this ADR:
  1. How many unique identifiers does one domain entity have? Can a Slack payload use a different
     key than an HTTP payload for the same entity?
  2. Which application component mints a new correlation identifier? Can two platforms
     independently create identifiers for the same logical entity?
  3. How is the identifier physically transported by each platform's payload format?
  4. When is the identifier considered valid? What happens when it expires or becomes unknown?
  5. How do HTTP clients (e.g., Backstage) poll entity status without triggering state changes?

- **Business/operational drivers:**
  - Entity continuity: approval workflows span hours or days. The correlation mechanism
    must work across process restarts, ECS task replacements, and multiple channels.
  - Operator debuggability: a single identifier in the structured log (`correlation_id`)
    links every event in a workflow from creation to terminal status. ADR-0054 structured
    logging requirement.
  - Backstage integration: Backstage must be able to poll entity status via a stable HTTP
    endpoint identified by the same `correlation_id` used in Slack and Teams interactions.
  - Race-free creation: if HTTP and Slack both could mint identifiers independently for
    the same entity, the application would have two competing entities. Minting authority
    must be channel-constrained per feature.

- **Constraints:**
  - ADR-0045 Principle 6: stateless processes. No in-process identifier registry. The
    identifier and the entity it references must reside in a backing service (DynamoDB).
  - ADR-0048: no cross-package imports.
  - ADR-0050: all identifier resolution operations that fail return `OperationResult` with
    appropriate status. Unknown `correlation_id` returns `NOT_FOUND`.
  - ADR-0063: HTTP route shape (path parameters, response model, status code, OpenAPI metadata)
    governs the HTTP query API defined in Standard 5.
  - ADR-0065: identifier payloads that cross layer boundaries use the appropriate type model
    (TypedDict for dict-shaped adapters; dataclass for internal domain values).
  - ADR-0077: infrastructure services are injected via `Annotated[Protocol, Depends(...)]`.
  - ADR-0079: SQS continuation messages (ADR-0091 Standard 4) carry `correlation_id` as
    the routing key.
  - ADR-0089: `ingress.py` receives `correlation_id` from the normalised intent (Standard 7).
    This ADR governs how adapters extract it from platform payloads.

- **Non-goals:**
  - This ADR does not define idempotency key schema or DynamoDB write ordering. Those are
    ADR-0091's scope.
  - This ADR does not define the physical format of Slack `private_metadata` or Teams
    Adaptive Card data fields beyond `correlation_id`. Platform-specific constraints
    (size limits, signing, versioning) belong in ADR-0096 (Slack) and ADR-0097 (Teams).
  - This ADR does not govern identity resolution (`actor_id`). That is ADR-0061's scope.
  - This ADR does not govern SQS deduplication or visibility timeout. That is ADR-0091's scope.
  - This ADR does not govern how features discover which domain entities a user has permission
    to query. That is a feature-level access control concern.

## Decision

---

### Standard 1: Correlation ID Cardinality Model

One domain entity has **exactly one** `correlation_id` for its entire lifecycle. The identifier
does not change when the entity transitions status, crosses channels, or is re-queried.

**Shape:**

```
correlation_id: UUID v4, lower-case, hyphen-separated
Example: "550e8400-e29b-41d4-a716-446655440000"
```

**Rules:**

- C1: `correlation_id` is the **domain entity primary key** in DynamoDB. It maps one-to-one
  with the entity. There is no separate "request ID", "session ID", or "workflow ID" that
  may be used in place of, or alongside, `correlation_id` in platform payloads.
- C2: `correlation_id` is a UUID v4 string, not an opaque token. Features must not embed
  additional semantic data (feature name, intent, timestamp) inside the `correlation_id` value.
  Semantic routing uses the idempotency key schema (ADR-0091 Standard 1), not the UUID itself.
- C3: The same `correlation_id` value appears verbatim in: DynamoDB entity PK, Slack
  `private_metadata`, Teams Adaptive Card data, HTTP URL path segment, SQS message body, and
  structured log fields. There is no per-channel translation.
- C4: The `GET /feature/entities/{correlation_id}` endpoint (Standard 5) returns the entity
  identified by `correlation_id`. It does not perform any alias resolution or ID translation.

---

### Standard 2: Minting Authority

A `correlation_id` is minted **exactly once**, at the moment a domain entity is created. The
channel and component that may create a new entity (and thus mint a new identifier) is a
feature-level decision, documented in the feature's Tier-4 ADR.

**Global rules (all features must comply):**

- M1: Exactly one channel may create a new domain entity per feature. If HTTP and Slack are
  both supported by a feature, only one of them is the designated creation channel for that
  feature. The other channel may only act on existing entities (it carries a `correlation_id`
  extracted from a prior payload — it never mints).
- M2: Entity creation is idempotent. If a creation request arrives for an entity that already
  exists (same business key, e.g., same user + same resource + same day), the response is
  `SUCCESS` with the existing entity's `correlation_id`. No new `correlation_id` is minted.
  This is enforced by a DynamoDB conditional write on the creation path (ADR-0091 Standard 2).
- M3: The minting component is `service.py` — specifically the "create entity" domain service
  method. Neither `ingress.py` nor transport adapters mint identifiers.
- M4: The minted `correlation_id` is returned in the creation response and embedded in the
  first platform payload (e.g., the initial Slack modal's `private_metadata`, the Teams card
  data) before any subsequent interaction step can occur.

> **Feature ADR forward reference:** The specific channel authorised to mint and the
> business key deduplication logic are documented in each feature's Tier-4 ADR (e.g.,
> ADR-0096 for Slack handler constraints; ADR-0097 for Teams interaction integration).
> ADR-0091 Standard 2 governs the DynamoDB conditional write that enforces creation
> idempotency at the infrastructure level.

---

### Standard 3: Payload Carrier Contract

Each platform transports `correlation_id` in the designated carrier field. Transport adapters
in `interactions/<platform>.py` are solely responsible for extracting it and constructing the
`NormalisedIntent` (ADR-0089 Standard 7). `ingress.py` never reads platform payloads directly.

| Platform | Carrier field | Shape |
|----------|--------------|-------|
| HTTP | URL path parameter | `/feature/entities/{correlation_id}/action` |
| Slack | `view.private_metadata` (JSON string) | `{"v": 1, "cid": "<uuid>"}` |
| Teams | `Action.Submit` data field | `{"correlation_id": "<uuid>", "intent": "..."}` |

**Rules:**

- P1: **HTTP:** `correlation_id` is a path parameter on all state-changing endpoints
  (`POST`, `PUT`, `PATCH`, `DELETE`). Query endpoints (`GET`) also use the path parameter
  (Standard 5). `correlation_id` is never a query string parameter or request body field
  on HTTP endpoints.
- P2: **Slack:** `private_metadata` is a JSON-serialized string in the view payload.
  The minimum required schema is `{"v": 1, "cid": "<uuid>"}`. The `v` field is a version
  sentinel for future schema evolution (ADR-0096 governs the full schema contract).
  The adapter extracts `private_metadata`, parses JSON, and reads `cid`. If `private_metadata`
  is absent or malformed, the adapter returns an error before calling `ingress.py`.
- P3: **Teams:** `correlation_id` is a field in the `Action.Submit` data object embedded in
  the Adaptive Card. The Teams adapter re-embeds `correlation_id` in every card rendered at
  each dialog step, so the identifier is always present in the subsequent `task/submit`
  payload (ADR-0097 governs the Teams card lifecycle contract).
- P4: Teams Adaptive Card `Action.Submit` data fields must NOT use Bot Framework
  `ConversationState` or `UserState` as the `correlation_id` carrier. Bot Framework SDK is
  archived (archived Dec 31, 2025; successor: Microsoft 365 Agents SDK for Python). The
  Adaptive Card data field is the correct carrier for correlation_id in Teams interactions.
- P5: Adapters must validate that `correlation_id` is a well-formed UUID v4 before calling
  `ingress.py`. A malformed identifier returns `OperationResult.permanent_error` with
  `NOT_FOUND` equivalent semantics (no entity lookup attempted).

---

### Standard 4: Lifecycle and TTL

`correlation_id` is valid for the full lifetime of the domain entity it identifies.

**States:**

```
CREATED → [feature-defined intermediate states] → TERMINAL_STATE
                                                    (e.g., APPROVED, REJECTED, CANCELLED, EXPIRED)
```

**Rules:**

- T1: `correlation_id` is valid as long as the domain entity exists in DynamoDB with a
  non-terminal status. Features define their own terminal status set in their Tier-4 ADR.
- T2: An unknown `correlation_id` (no entity found in DynamoDB) returns
  `OperationResult.not_found` from `ingress.py`. Transport adapters map this to:
  HTTP 404, Slack ephemeral error message, Teams card error task module.
- T3: A `correlation_id` for an entity in a terminal status returns
  `OperationResult.permanent_error` with a user-visible message indicating the entity is
  closed. Features must specify the human-readable message in their Tier-4 ADR.
- T4: Entities may carry a DynamoDB item-level TTL (UNIX epoch seconds) for automatic
  expiry. TTL is set at entity creation; the value is a feature-level decision. Expired items
  are automatically deleted by DynamoDB — no application-level cleanup is required.
- T5: The idempotency record (ADR-0091 Standard 1) has an independent 24-hour TTL from its
  write time. The entity TTL and idempotency record TTL are separate DynamoDB TTL attributes.

> **ADR boundary note:** This standard governs the 24-hour TTL *value* for idempotency
> records and the entity TTL policy. The DynamoDB write mechanics (TransactWriteItems,
> conditional expressions, ClientRequestToken) are specified in ADR-0091 Standard 2.
- T6: Features that require a hard "active window" for user interaction (e.g., access request
  must be approved within 48 hours) must set the entity TTL accordingly and define a
  background job (Phase 6 lifespan, ADR-0058) that transitions `PENDING_APPROVAL` entities
  to `EXPIRED` before DynamoDB auto-deletes them. Auto-deletion without status transition
  leaves no audit record.

---

### Standard 5: HTTP Query API Pattern

HTTP API clients (e.g., Backstage) must be able to query entity status by `correlation_id`
without triggering any state changes. This is an observe-only endpoint.

**Route shape:**

```
GET /feature/entities/{correlation_id}
```

**Response model:**

```python
# packages/<feature>/schemas.py (Pydantic BaseModel — ADR-0065)

class EntityStatusResponse(BaseModel):
    correlation_id: str
    status: str                    # Feature-defined status enum value (as string)
    created_at: datetime
    updated_at: datetime
    # Feature-defined additional read fields (no mutable fields exposed)
```

**HTTP status mapping:**

| Entity state | HTTP status | Notes |
|--------------|-------------|-------|
| Found, any non-terminal status | 200 OK | Entity returned |
| Found, terminal status | 200 OK | Entity returned (status indicates terminal) |
| Unknown `correlation_id` | 404 Not Found | RFC 9457 problem detail |
| Malformed `correlation_id` | 400 Bad Request | RFC 9457 problem detail |
| DynamoDB unavailable | 503 Service Unavailable | RFC 9457, `Retry-After` header |

**Rules:**

- Q1: The `GET /feature/entities/{correlation_id}` endpoint performs a direct DynamoDB fetch
  by `correlation_id`. No secondary index is used for this query.
- Q2: The endpoint is observe-only. It must not write to DynamoDB, enqueue SQS messages,
  emit blinker events, or trigger any side effects.
- Q3: Identity is required for the query endpoint. The caller must present a valid JWT
  (ADR-0061). The endpoint must enforce that the caller has permission to observe the entity.
  Permission model is feature-defined and documented in the feature's Tier-4 ADR.
- Q4: The response model is a Pydantic `BaseModel` (ADR-0065 HTTP/webhook I/O boundary).
  It must NOT expose internal domain fields not intended for external consumption.
- Q5: The route follows ADR-0063 conventions: one OpenAPI tag per router, `summary`,
  `description`, `response_model`, and `status_code` on every handler. The route is
  registered via `register_routes` hookimpl (ADR-0089 Standard 3).
- Q6: Backstage polling MUST use exponential backoff with jitter.

> **Endpoint naming guidance:** The `/feature/entities/{correlation_id}` path pattern uses
> generic placeholders. Feature ADRs (Tier-4) specify the concrete noun (e.g.,
> `/access/requests/{correlation_id}`). All features must use `{correlation_id}` as the
> path parameter name — no aliases (`id`, `request_id`, `entity_id`) are permitted. The recommended interval
  starts at 5 seconds and caps at 60 seconds. This is an operational convention, not
  enforced at the API layer.

---

## Compliance

An implementation is compliant with this standard if and only if:

1. `correlation_id` is a UUID v4 domain entity primary key used verbatim across all channels
   (Standard 1).
2. `correlation_id` is minted exactly once, at entity creation, by the domain service
   (Standard 2).
3. Each platform adapter extracts `correlation_id` from the designated carrier field and
   does not pass raw platform payloads beyond the adapter (Standard 3).
4. Unknown or malformed `correlation_id` values return `NOT_FOUND` / `permanent_error`
   without attempting a domain operation (Standards 3 and 4).
5. An observe-only `GET /feature/entities/{correlation_id}` endpoint exists, returns a
   Pydantic response model, and enforces JWT identity (Standard 5).
6. Entity TTL and idempotency record TTL are independent DynamoDB attributes (Standard 4).
