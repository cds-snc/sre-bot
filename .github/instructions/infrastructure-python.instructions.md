---
name: Infrastructure Python Rules
description: Use for app/infrastructure Python files; enforces shared-service boundaries and dependency injection patterns.
applyTo: app/infrastructure/**/*.py
---

- No package business logic here — infrastructure is shared platform capabilities only (ADR-0048).
- Category A services: Protocol + concrete + `@lru_cache` provider + DI alias (ADR-0077).
- Category B (shared utility): concrete import OK. Category C (impl detail): never exposed to features.
- Providers in `providers.py`, DI aliases in `dependencies.py` (ADR-0056).
- Sibling value-type imports OK; configuration via injection; composition in `providers.py` only (ADR-0076).
- Constructor-only injection. No import-time side effects (ADR-0048).
- Category A services must provide in-memory dev/test fallback (ADR-0054).
