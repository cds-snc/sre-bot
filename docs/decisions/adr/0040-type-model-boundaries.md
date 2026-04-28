---
adr_id: ADR-0040
title: "Type Model Boundaries"
status: Accepted
decision_type: Feature
tier: Tier-4
date_created: unknown
last_updated: 2026-04-28
last_reviewed: unknown
next_review_due: 2026-04-28
owners:
  - SRE Team
supersedes: []
superseded_by: []
related_records:
  - ADR-0032
  - ADR-0034
  - ADR-0043
related_packages: []
review_state: stale
---
# Type Model Boundaries

## Decision

Use different type mechanisms for different boundaries:

- Use `Protocol` for behavior contracts.
- Use `@dataclass(frozen=True)` for canonical internal data models.
- Use `pydantic.BaseModel` for untrusted I/O boundaries.
- Use `TypedDict` only when dict semantics are required.

This decision clarifies the missing boundary between:
- FastAPI-facing request and response schemas, which should remain Pydantic models.
- Internal cross-package and infrastructure contracts, which should not default to Pydantic models.

---

## Why

We want all of the following at the same time:

- Strong type safety.
- Stable contracts for centralized core services used by feature packages.
- A lightweight internal model layer that is not coupled to FastAPI or JSON schema generation.
- Explicit validation at external boundaries.

Pydantic is excellent at validation, coercion, and schema generation, but those strengths are mainly needed at adapter boundaries. Internal business logic and provider contracts benefit more from lightweight, explicit, framework-independent types.

---

## Model Selection Matrix

| Scenario | Preferred Type | Notes |
|----------|----------------|-------|
| Provider or service interface | `Protocol` | Define behavior only |
| Internal shared entity or value object | `@dataclass(frozen=True)` | Preferred for cross-package internal data |
| Internal service result with multiple fields | dedicated dataclass | Prefer over `TypedDict` envelopes |
| HTTP request or response schema | `BaseModel` | Required for validation and OpenAPI |
| Webhook, command, or other untrusted input | `BaseModel` | Parse and validate before business logic |
| Raw SDK payload or dict-shaped metadata | `TypedDict` | Keep local when possible |
| Settings | Pydantic settings models | Existing pattern remains unchanged |

---

## Internal Core Services

Examples: directory, platforms, identity, notifications, resilience.

### Contracts

Internal core service contracts should be defined with `Protocol`.

```python
from typing import Protocol

from infrastructure.operations import OperationResult


class DirectoryProvider(Protocol):
    def get_user(self, email: str) -> OperationResult[DirectoryUser]:
        ...

    def list_users(self, query: str = "", limit: int = 100) -> OperationResult[list[DirectoryUser]]:
        ...
```

Rules:
- A protocol describes callable behavior, not serialized schema.
- Protocol signatures should use internal concrete types, not FastAPI or Pydantic HTTP models.
- Shared protocols should avoid dict-first shapes when a concrete internal model exists.

### Canonical Data

Internal data shared across packages should use dataclasses.

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class DirectoryUser:
    email: str
    provider_user_id: str
    display_name: str | None = None
```

Rules:
- Prefer `@dataclass(frozen=True)` for entities, value objects, policy objects, and result payloads.
- Use dataclasses for values that cross internal package boundaries.
- Use plain methods on dataclasses only when the behavior is intrinsic to the value object.

### Result Shapes

For new contracts, prefer typed payloads directly in `OperationResult[T]`.

Preferred:

```python
OperationResult[DirectoryUser]
OperationResult[list[DirectoryUser]]
OperationResult[MembershipCheckResult]
OperationResult[None]
```

If a result needs several named fields, define a result dataclass:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class GroupMembersResult:
    group: DirectoryGroup
    members: list[DirectoryMember]
```

Avoid `TypedDict` envelopes for shared contracts:

```python
class GroupMembersData(TypedDict):
    group: DirectoryGroup
    members: list[DirectoryMember]
```

### TypedDict Usage

`TypedDict` still has a place, but it is narrower:

- raw provider payloads returned by SDKs or HTTP clients
- partial metadata maps
- dict-shaped structures where key presence matters and dict behavior is intentional

`TypedDict` should usually stay close to the adapter that consumes or produces the dict.

---

## Feature Packages

Examples: `packages/geolocate` and future packages under `packages/`.

### FastAPI Endpoints

FastAPI-facing schemas should use Pydantic.

```python
from pydantic import BaseModel, Field


class GeolocateRequest(BaseModel):
    ip_address: str = Field(..., description="IPv4 or IPv6 address")


class GeolocateResponse(BaseModel):
    ip_address: str
    country: str | None = None
```

Rules:
- Request models use `BaseModel`.
- Response models use `BaseModel`.
- Routes should declare `response_model` or return a Pydantic response type directly.
- Validation and OpenAPI generation stay at the HTTP boundary.

### Business Logic Modules

Feature business logic uses dataclasses, primitives, and protocols.

```python
from dataclasses import dataclass

from infrastructure.operations import OperationResult


@dataclass(frozen=True)
class GeolocateQuery:
    ip_address: str


@dataclass(frozen=True)
class GeolocateResult:
    ip_address: str
    country: str | None = None


def geolocate_ip(query: GeolocateQuery) -> OperationResult[GeolocateResult]:
    ...
```

Rules:
- Business logic should not depend on FastAPI or on route request models.
- Convert from Pydantic request models to dataclasses near the route.
- Convert from dataclass results back to Pydantic response models near the route.
- Express business rules in explicit code, not in Pydantic validators buried deep in service modules.

### Other Adapters

The same edge rule applies outside HTTP:

- Slack command schemas
- Teams payloads
- Discord payloads
- webhooks
- scheduled job payloads loaded from external JSON

If the input is untrusted or serialized, validate with Pydantic first, then convert to internal dataclasses or primitives.

---

## Guidance by Scenario

### Scenario 1: Internal Core Service

Use:
- `Protocol` for the service interface
- frozen dataclasses for canonical models and results
- `TypedDict` only for local adapter payloads

Do not use:
- Pydantic models as the main shared provider contract
- one-key `TypedDict` envelopes for new contracts

### Scenario 2: Feature FastAPI Endpoint

Use:
- Pydantic request model
- Pydantic response model
- explicit mapping to internal dataclass input and output

Do not use:
- raw dict responses from routes
- dataclasses as the primary FastAPI schema layer unless there is a deliberate FastAPI dataclass use case

### Scenario 3: Feature Business Logic Module

Use:
- dataclasses for internal inputs and outputs
- protocols for collaborators when multiple implementations exist
- `OperationResult[T]` for operation outcomes

Do not use:
- route request models as service-layer arguments
- Pydantic validators as the main expression of business rules