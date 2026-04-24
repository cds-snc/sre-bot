---
name: type-model-boundaries
description: Choose correct Python type boundaries (Protocol, dataclass, BaseModel, TypedDict) for maintainable FastAPI architecture.
---

# Type Model Boundaries

Use this skill when introducing or refactoring interfaces, domain types, and transport models.

## Selection Matrix

1. `Protocol`: behavior contracts between services/adapters.
2. `@dataclass(frozen=True)`: canonical internal entities/value objects.
3. `BaseModel`: untrusted I/O boundaries and OpenAPI-facing models.
4. `TypedDict`: dictionary semantics that must remain dict-shaped.

## Rules

- Keep transport schemas separate from internal models.
- Avoid Pydantic as the default internal contract mechanism.
- Use explicit conversion between transport and internal models when crossing boundaries.
- Keep protocols small and focused on needed behavior.

## Anti-patterns

- Returning HTTP schema models from core service internals by default.
- Dict-first internal contracts when stable structured types are available.
- Broad protocols exposing more methods than a consumer uses.

## Review Checklist

1. Is each model type selected for the boundary where it is used?
2. Are transport and domain concerns separated?
3. Are contracts typed and easy to test with fakes/mocks?
4. Are I/O boundaries validated with Pydantic where required?
