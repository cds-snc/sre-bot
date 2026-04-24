---
name: Infrastructure Python Rules
description: Use for app/infrastructure Python files; enforces shared-service boundaries and dependency injection patterns.
applyTo: app/infrastructure/**/*.py
---

- Keep infrastructure code focused on shared platform capabilities.
- Do not introduce package business logic in infrastructure modules.
- Use provider/dependency layers for object assembly and caching.
- Prefer constructor injection and typed contracts over service lookups inside services.
- Keep startup wiring in bootstrap/lifespan flow and avoid import-time side effects.
