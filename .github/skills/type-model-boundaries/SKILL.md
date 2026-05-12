---
name: type-model-boundaries
description: Choose correct Python type boundaries (Protocol, dataclass, BaseModel, TypedDict) for maintainable FastAPI architecture.
---

## Type Selection by Boundary

| Boundary | Type | Why |
|----------|------|-----|
| Service contracts (Protocols) | `typing.Protocol` | Structural typing, no inheritance ceremony. |
| Internal domain data | `@dataclass(frozen=True)` | Immutable, framework-independent, lightweight. |
| HTTP request/response bodies | `pydantic.BaseModel` | Validation, coercion, schema at trust boundary. |
| Environment configuration | `pydantic_settings.BaseSettings` | Env-var parsing, validation, defaults at startup. |
| SDK response internals in adapters | `typing.TypedDict` | Structural dict typing; never crosses adapter boundary. |
| Closed categorical values | `enum.Enum` | Identity, comparison, exhaustion (e.g., OperationResult status). |
| Constrained string/int values | `typing.Literal` | Type-level constraint without runtime class. |

## Rules

- **One representation per boundary.** A `User` is Pydantic at HTTP, frozen dataclass internally, TypedDict in adapter.
- **BaseModel only at trust boundaries.** Never in service, domain, or adapter return types.
- **Service contracts are Protocols.** No concrete implementations in type signatures above infrastructure.
- **OperationResult at integration boundaries only.** Not in domain logic, routes, or feature contracts.
- **No nested BaseSettings.** Root owns env-var sourcing; nested sections use BaseModel.
- **TypedDict stays inside adapters.** Never cross upward to service or domain.
- **Vendor types never cross infrastructure boundary.** Adapters translate SDK shapes to domain types.

## Anti-patterns

- Pydantic as default internal contract.
- Dict-first when structured types exist.
- Broad Protocols with unused methods.
- HTTP models returned from services.
- OperationResult in domain types.
