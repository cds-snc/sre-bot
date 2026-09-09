---
name: Packages Python Rules
description: Business-logic layer rules for app/packages — boundaries, plugin registration, settings ownership, and type model selection.
applyTo: app/packages/**/*.py
---

This is the **business logic** layer. Shared platform capabilities belong in
`app/infrastructure`; `app/modules` is legacy and is never a pattern to copy.

- **Never import a concrete infrastructure implementation.** Resolve services via
  the singleton providers in `app/infrastructure/services/providers.py`, and in
  routes via `Annotated[..., Depends(...)]` aliases from
  `app/infrastructure/services/dependencies.py`. Direct imports of
  `app/infrastructure/<service>/...` couple business logic to a swappable
  implementation and break test isolation.
- **Type boundaries** — `Protocol` for service/adapter contracts,
  `@dataclass(frozen=True)` for canonical internal entities, `BaseModel` **only**
  where untrusted input arrives (HTTP bodies, webhooks, external payloads).
  Pydantic on an internal boundary buys validation you already guaranteed and
  costs you free construction in tests.

  ```python
  class ItemAdapter(Protocol):
      async def get_item(self, item_id: str) -> OperationResult[Item]: ...

  @dataclass(frozen=True)
  class Item:
      id: str
      name: str
  ```
- **Settings** — new package domains define `app/packages/<feature>/settings.py`.
  Do not add package-owned fields to root aggregators, and pass services the
  narrowest slice they need rather than a root settings object.
- **Registration** — every package is plugin-registerable from day one via a
  `pyproject.toml` entry-point, loaded at startup by
  `pm.load_setuptools_entrypoints`. Never register at import time; no
  side-effecting code in `__init__.py` bodies.
- **Route handlers stay thin** — transport concerns only; delegate behavior to a
  package service and map its result to HTTP.
