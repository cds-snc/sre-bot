# Type Model Boundaries Pattern

**Reference**: `docs/decisions/tier-4-application/09-type-model-boundaries.md`

## Purpose

Choose the right type mechanism for the right boundary:

- `Protocol` for behavior contracts
- `@dataclass` for internal canonical data models
- `BaseModel` for untrusted I/O boundaries
- `TypedDict` only when dict semantics are required

This skill complements `type-hints-pattern.md`. That skill answers "should this be typed?". This skill answers "what kind of typed model should this be?"

---

## Decision Matrix

| Need | Use | Why | Avoid |
|------|-----|-----|-------|
| Define a provider or service capability | `Protocol` | Structural contract for interchangeable implementations | Using `BaseModel` or `TypedDict` as an interface |
| Share canonical internal data across infrastructure or packages | `@dataclass(frozen=True)` | Lightweight, explicit, tool-friendly, not tied to validation framework | Passing `BaseModel` through core services |
| Validate HTTP, webhook, command, or settings input/output | `pydantic.BaseModel` | Validation, coercion, JSON schema, FastAPI integration | Using dataclasses alone at untrusted boundaries |
| Represent raw JSON-like dict payloads where keys matter | `TypedDict` | Precise typing for dict-shaped data without a runtime model | Using `TypedDict` as the main domain model |

---

## Internal Core Services

Examples: directory, platforms, identity, resilience, notifications.

### Use `Protocol` for Service Contracts

```python
from typing import Protocol

from infrastructure.operations import OperationResult


class DirectoryProvider(Protocol):
    def get_user(self, email: str) -> OperationResult[DirectoryUser]:
        ...
```

Rules:
- `Protocol` defines methods and return types only.
- `Protocol` methods should return concrete internal types such as dataclasses, lists, primitives, or `OperationResult[T]`.
- Do not use `BaseModel` as the main provider contract type for internal services.

### Use Frozen Dataclasses for Canonical Internal Models

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class DirectoryUser:
    email: str
    provider_user_id: str
    display_name: str | None = None
```

Rules:
- Prefer `@dataclass(frozen=True)` for canonical entities, value objects, and result payloads.
- Use dataclasses for data crossing package boundaries inside the application.
- If a result needs multiple named fields, define a dedicated result dataclass instead of wrapping dataclasses in a one-key dict.

### Use `TypedDict` Only for Dict-Shaped Adapter Data

```python
from typing import TypedDict


class GoogleUserPayload(TypedDict, total=False):
    primaryEmail: str
    id: str
    suspended: bool
```

Rules:
- `TypedDict` is acceptable for raw provider payloads, metadata bags, or partial dicts.
- Keep `TypedDict` local to adapters when possible.
- Avoid new shared contracts that expose single-key envelopes such as `{"user": user}` unless compatibility requires it.

### Result Payload Rule

Prefer these shapes for new shared contracts:

```python
OperationResult[DirectoryUser]
OperationResult[list[DirectoryUser]]
OperationResult[MembershipCheckResult]
OperationResult[None]
```

If several fields belong together, prefer:

```python
@dataclass(frozen=True)
class GroupMembersResult:
    group: DirectoryGroup
    members: list[DirectoryMember]
```

Over:

```python
class GroupMembersData(TypedDict):
    group: DirectoryGroup
    members: list[DirectoryMember]
```

Transitional rule:
- Existing stable contracts using `TypedDict` envelopes may remain until an explicit migration is planned.
- New contracts should prefer direct dataclass payloads.

---

## Feature Packages

Examples: `packages/geolocate`, future packages under `packages/`.

### FastAPI Endpoints

Use `BaseModel` for request and response schemas.

```python
from pydantic import BaseModel


class GeolocateRequest(BaseModel):
    ip_address: str


class GeolocateResponse(BaseModel):
    ip_address: str
    country: str | None = None
```

```python
@router.post("/geolocate", response_model=GeolocateResponse)
def geolocate(request: GeolocateRequest, settings: SettingsDep) -> GeolocateResponse:
    query = GeolocateQuery(ip_address=request.ip_address)
    result = geolocate_ip(query)
    ...
```

Rules:
- Use Pydantic for HTTP request and response schemas.
- Keep Pydantic models at the adapter boundary: routes, webhooks, commands, settings.
- Convert request models to internal dataclasses or primitive arguments early.
- Convert internal results back to response models at the route boundary.

### Business Logic Modules

Use dataclasses, primitives, and protocols.

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
- Business logic should not depend on FastAPI or Pydantic request models.
- Express business rules in plain Python functions, methods, and dataclasses.
- If a feature needs interchangeable collaborators, define a `Protocol` for the collaborator behavior.
- Return `OperationResult[T]` where `T` is a dataclass, list of dataclasses, primitive, or `None`.

### Other Adapter Boundaries

For Slack commands, Teams payloads, Discord payloads, webhooks, and similar untrusted inputs:
- Use Pydantic if validation and coercion are needed.
- Convert to dataclasses or primitives before calling business logic.

---

## Forbidden Patterns

```python
# ❌ Pydantic as a core provider contract
class DirectoryProvider(Protocol):
    def get_user(self, email: str) -> UserSchema:
        ...

# ❌ Single-key envelope as the default new shared contract
class DirectoryUserData(TypedDict):
    user: DirectoryUser

# ❌ Passing FastAPI request models deep into service code
def geolocate_ip(request: GeolocateRequest) -> OperationResult:
    ...

# ❌ Using Protocol for data-only shapes
class DirectoryUser(Protocol):
    email: str
```

---

## Pre-Implementation Checklist

Before introducing or changing a model type:

1. ☐ Is this a behavior contract? Use `Protocol`.
2. ☐ Is this an internal canonical data shape? Use `@dataclass(frozen=True)`.
3. ☐ Is this an untrusted I/O boundary? Use `BaseModel`.
4. ☐ Does this truly need dict semantics? Use `TypedDict`.
5. ☐ For new shared contracts, avoid single-key `TypedDict` envelopes.
6. ☐ Keep Pydantic models out of core service protocols and business logic where possible.
7. ☐ Return `OperationResult[T]` with concrete typed payloads.