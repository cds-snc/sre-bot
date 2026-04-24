---
name: settings-singleton
description: Apply partitioned settings and singleton provider patterns; use when adding or refactoring settings and provider wiring.
---

# Settings Singleton and Partitioning

Use this skill when introducing settings for new package domains, adjusting providers, or refactoring legacy settings usage.

## Core Rules

1. New package settings belong in `app/packages/<feature>/settings.py`.
2. Avoid growing root settings aggregators for package-owned concerns.
3. Validate settings at startup through lifecycle hooks.
4. Provider functions should expose cached singletons and inject narrow settings slices.
5. Services should receive only required settings sections.

## Provider Pattern

- Use `@lru_cache(maxsize=1)` for singleton providers.
- Keep providers in assembly/dependency layers, not service constructors.
- Do not call `get_settings()` from within service constructors.

## Migration Safety

When touching legacy settings:

1. Preserve existing runtime behavior first.
2. Introduce package-local settings for new functionality.
3. Migrate consumers incrementally to slice-based constructors.
4. Remove legacy wiring only after full migration and tests.

## Anti-patterns

- Adding new package settings directly to central aggregator by default.
- Passing a broad root settings object into every service.
- Instantiating settings repeatedly in route or service code.

## Minimum Tests

1. Startup validation passes with valid env.
2. Startup fails deterministically with invalid env.
3. Provider returns singleton instance behavior.
4. Service accepts narrow settings slice and works correctly.
