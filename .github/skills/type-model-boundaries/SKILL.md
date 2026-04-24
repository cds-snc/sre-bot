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
- When both shared service protocols and route-local protocols exist, keep their method signatures aligned for overlapping methods.

## Protocol Alignment Pattern

- Define one canonical contract for shared behavior (for example, service-level `Protocol` with concrete `OperationResult[T]` generics).
- Allow route-local protocols to be narrower, but never looser on return shapes for methods they share.
- Prefer explicit generic return types over bare containers (`OperationResult` vs `OperationResult[T]`) to prevent runtime unpacking mismatches.
- Add at least one type-focused test or static check path that would fail if shared and local contracts drift.

## Anti-patterns

- Returning HTTP schema models from core service internals by default.
- Dict-first internal contracts when stable structured types are available.
- Broad protocols exposing more methods than a consumer uses.
- Parallel protocols that describe the same method with different return shapes.

## Review Checklist

1. Is each model type selected for the boundary where it is used?
2. Are transport and domain concerns separated?
3. Are contracts typed and easy to test with fakes/mocks?
4. Are I/O boundaries validated with Pydantic where required?
5. If local and shared protocols both exist, do overlapping signatures (including generic return payloads) match exactly?
