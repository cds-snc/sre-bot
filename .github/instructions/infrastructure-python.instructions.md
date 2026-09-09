---
name: Infrastructure Python Rules
description: Shared-platform layer rules for app/infrastructure — service boundaries, provider assembly, and startup wiring.
applyTo: app/infrastructure/**/*.py
---

This is the **shared platform** layer: capabilities more than one feature depends
on. Anything specific to one business domain belongs in `app/packages/<domain>`.

- **No business logic here.** If a change only one feature needs is landing in
  `app/infrastructure`, it is in the wrong layer — say so rather than adding it.
- **Object assembly lives in provider/dependency layers**, not inside services.
  Providers expose cached singletons (`@lru_cache(maxsize=1)`) and inject narrow
  settings slices. A service that calls `get_settings()` in its own constructor
  cannot be tested with a fake configuration.
- **Constructor injection over service lookup** — a service takes its
  collaborators as typed `Protocol` parameters; it does not reach into a registry
  to find them.
- **Startup wiring stays in the bootstrap/lifespan flow.** No import-time side
  effects: importing a module must never register a hook, open a connection, or
  mutate a module-level registry. Fail fast at startup instead of
  catch-and-continue, so a broken dependency cannot serve degraded traffic silently.
- Log structured, contextual, non-sensitive metadata on failure paths.
