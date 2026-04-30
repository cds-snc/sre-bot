---
name: settings-singleton
description: Apply partitioned settings and singleton provider patterns; use when adding or refactoring settings and provider wiring.
---

Use when introducing package settings, adjusting providers, or refactoring legacy settings.

## Settings Ownership (ADR-0055)

| Owner | Location |
|-------|----------|
| Infrastructure | `infrastructure/configuration/infrastructure/` |
| Integration | `infrastructure/configuration/integrations/` |
| Feature | `packages/<feature>/settings.py` |

## Provider Pattern (ADR-0055, ADR-0056)

- One `BaseSettings` + `@lru_cache(maxsize=1)` provider per domain.
- Infrastructure providers in `providers.py`. Feature packages may have local providers.
- Services receive narrow settings slices only — never full Settings tree.

## Rules

- No key duplication across domains (ADR-0047).
- Never nest `BaseSettings` in `BaseSettings` — use `BaseModel` for sections (ADR-0055).
- `BaseSettings` for env vars; `@dataclass(frozen=True)` for runtime config documents.
- Fail-fast: invalid config terminates startup (ADR-0045 P4).
- Don't call `get_settings()` in service constructors — inject the slice.

## Anti-patterns

- Adding package settings to central aggregator.
- Passing broad settings objects to services.
- Instantiating settings repeatedly in routes/services.

## Tests (ADR-0062)

1. Valid env → startup passes.
2. Invalid env → startup fails deterministically.
3. Provider returns singleton (same identity).
4. `@lru_cache` cleared between tests.
