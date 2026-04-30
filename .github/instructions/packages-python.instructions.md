---
name: Packages Python Rules
description: Use for package-layer Python work under app/packages; enforces boundaries, registration, and type model selection.
applyTo: app/packages/**/*.py
---

- Business logic in services; route handlers are thin adapters (ADR-0063).
- Consume infrastructure via `Annotated[Protocol, Depends(...)]` — never import concrete classes (ADR-0048, ADR-0077).
- `@dataclass(frozen=True)` for domain data; `BaseModel` only at I/O boundaries (ADR-0065).
- Package settings in `packages/<feature>/settings.py` with `@lru_cache`. Narrow-slice injection (ADR-0055, ADR-0056).
- `__init__.py`: only `@hookimpl` functions. No import-time side effects (ADR-0049).
- Feature interactions in `packages/<feature>/interactions/` with hookspec contracts (ADR-0059).
- External API calls return `OperationResult`; internal logic uses exceptions (ADR-0050).
