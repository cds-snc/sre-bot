---
name: type-model-boundaries
description: Choose correct Python type boundaries (Protocol, dataclass, BaseModel, TypedDict) for maintainable FastAPI architecture.
---

Use when introducing or refactoring interfaces, domain types, or transport models.

## Selection Matrix (ADR-0065)

| Boundary | Type |
|----------|------|
| Service contracts | `typing.Protocol` |
| Internal domain data | `@dataclass(frozen=True)` |
| HTTP/webhook I/O | `pydantic.BaseModel` |
| Env configuration | `pydantic_settings.BaseSettings` |
| Dict-shaped adapters | `typing.TypedDict` |

## Service Classification Impact (ADR-0077)

- Category A: Protocol required. Consume via `Annotated[Protocol, Depends(...)]`.
- Category B: concrete import OK.
- Category C: never exposed to features.

## Key Rules

- Keep protocols small and focused. One canonical contract; local variants may be narrower, never looser.
- Prefer `OperationResult[T]` over bare `OperationResult` for explicit generics (ADR-0050).
- Keep transport (`BaseModel`) and domain (`dataclass`) models separate. Explicit conversion at boundaries.
- Never nest `BaseSettings` in `BaseSettings` (ADR-0055).
- `OperationResult` at integration boundaries only; internal logic uses exceptions.

## Anti-patterns

- Pydantic as default internal contract.
- Dict-first when structured types exist.
- Broad protocols with unused methods.
- Returning HTTP models from service internals.

## Review Checklist

1. Type selected per ADR-0065 boundary?
2. Transport and domain separated?
3. Category A services behind Protocols?
4. Overlapping Protocol signatures aligned?
5. `OperationResult` only at integration boundaries?
