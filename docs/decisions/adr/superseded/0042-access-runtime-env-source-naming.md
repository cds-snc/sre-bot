---
adr_id: ADR-0042
title: "Access Runtime Env-Source Variable Naming"
status: Superseded
decision_type: Feature
tier: Tier-4
date_created: 2026-04-27
last_updated: 2026-04-30
last_reviewed: unknown
next_review_due: 2026-04-28
owners:
  - SRE Team
supersedes: []
superseded_by:
  - ADR-0066
related_records:
  - ADR-0007
  - ADR-0008
related_packages: []
review_state: stale
---
# ADR-T4-11: Access Runtime Env-Source Variable Naming

## Context

Access package env-source configuration used `ACCESS_SYNC_*` prefixes, inherited from early designs when env-source was only used by sync. Now all three subfeatures (sync, requests, catalog) use the runtime config. The `ACCESS_SYNC_` prefix is semantically incorrect and misleading. No production deployments use these vars, so safe migration is possible.

## Decision

Rename env vars to use `ACCESS_CONFIG_` prefix (semantic match with ACCESS_CONFIG_SOURCE): `ACCESS_CONFIG_DIR_PREFIX`, `ACCESS_CONFIG_DIR_SEPARATOR`, `ACCESS_CONFIG_PLATFORMS_JSON`. Use direct rename (not deprecation aliases) because no deployed systems currently use these variables.

## Consequences

- ✅ Semantic clarity: env vars match the config selection mechanism
- ✅ Operators understand vars affect all subfeatures, not just sync
- ✅ Consistent naming within access feature configuration
- ✅ No breaking changes to deployed systems (greenfield assessment confirms zero production usage)

---

**Date**: 2026-04-27
**Status**: Accepted
**Applies to**: `app/packages/access/common/config/loaders.py` — `_EnvModel` in `EnvConfigLoader`
**Context Note**:

- Architecture review notes were in the transition folder (removed from repository history)

---

## Context

The access package supports `ACCESS_CONFIG_SOURCE=env` — a configuration source that reads
the access runtime config document directly from environment variables instead of a file,
SSM parameter, or DynamoDB record.

`EnvConfigLoader._EnvModel` (in `loaders.py`) uses three env vars to build the
`AccessRuntimeConfig` domain object:

| Current env var name         | Meaning                                                        |
|------------------------------|----------------------------------------------------------------|
| `ACCESS_SYNC_DIR_PREFIX`     | Prefix prepended to raw directory group names                  |
| `ACCESS_SYNC_DIR_SEPARATOR`  | Separator between prefix and group slug                        |
| `ACCESS_SYNC_PLATFORMS_JSON` | JSON-encoded dict of platform policies (the main config blob) |

These names carry the `ACCESS_SYNC_` prefix, inherited from the early design where
the env-source configuration was only used by the sync subfeature.

The runtime config document (`AccessRuntimeConfig`) now drives **all three subfeatures**:
sync, requests, and catalog. The `ACCESS_SYNC_` prefix is therefore semantically incorrect
and misleading:

- An operator reading `ACCESS_SYNC_PLATFORMS_JSON` would reasonably conclude it only
  affects sync behavior, not request access-mode overrides or catalog rendering.
- The env source is selected by `ACCESS_CONFIG_SOURCE`, which lives in `AccessConfigSettings`
  under the `ACCESS_CONFIG_` prefix — the sibling namespace `ACCESS_CONFIG_ENV_*` is
  more discoverable and semantically coherent.

### Greenfield assessment (2026-04-27)

A full codebase and infrastructure search confirmed:

- The three `ACCESS_SYNC_DIR_*` / `ACCESS_SYNC_PLATFORMS_JSON` vars appear **only** in:
  - `app/packages/access/common/config/loaders.py` (source code)
  - `app/packages/access/sync/README.md` (documentation — future setup instructions, not
    a record that the vars are currently set)
  - `app/tests/unit/packages/access/sync/conftest.py` and
    `app/tests/integration/packages/access/sync/conftest.py` (test env cleanup fixtures)
- Zero matches in: `terraform/`, `app/infrastructure/configuration/`, `app/core/`, any
  ECS task definition, any SSM parameter reference.
- `ACCESS_SYNC_ENABLED` is `false` (the default); the feature has never been enabled in
  production.

**The ADR-07 rolling-deployment constraint (use `AliasChoices` for gradual migration)
applies only to env vars that already exist in a deployed SSM parameter or ECS task
definition.** Because none of these vars have ever been deployed, that constraint does not
apply. A direct, clean rename is safe.

---

## Options

### Option A — Keep current names, add documentation only

- No code change. Inline comments and operator docs explain the naming artifact.
- **Pros**: zero effort.
- **Cons**: misleading names persist forever; every new operator must read documentation
  to understand why `ACCESS_SYNC_PLATFORMS_JSON` controls catalog behavior. Technical
  debt with no upside.

### Option B — Introduce canonical aliases with a deprecation window

- `AliasChoices(canonical, legacy)` in `_EnvModel`; emit deprecation warning when legacy
  var is detected; retire after one release window.
- **Pros**: safe for deployed vars.
- **Cons**: unnecessary complexity — the deprecation machinery exists to protect deployed
  keys. No deployed keys exist. This is pure overhead.

### Option C — Direct rename (recommended)

- Rename all three vars in-place: source code, README, test fixtures.
- No aliases, no deprecation window, no migration log.
- **Pros**: clean canonical names from day one; no temporary scaffolding; no operator
  confusion from day one of enabling the feature.
- **Cons**: none — verified no deployed occurrences.

---

## Decision

**Choose Option C — Direct rename.** The access feature is greenfield. These env vars
have never been set in any ECS task definition or SSM parameter. ADR-07's AliasChoices
migration pattern is explicitly scoped to *deployed* keys; it does not apply here.

### Canonical name mapping

| Old name (to remove)         | Canonical name                     |
|------------------------------|------------------------------------|
| `ACCESS_SYNC_DIR_PREFIX`     | `ACCESS_CONFIG_ENV_DIR_PREFIX`     |
| `ACCESS_SYNC_DIR_SEPARATOR`  | `ACCESS_CONFIG_ENV_DIR_SEPARATOR`  |
| `ACCESS_SYNC_PLATFORMS_JSON` | `ACCESS_CONFIG_ENV_PLATFORMS_JSON` |

### Naming rationale

`ACCESS_CONFIG_ENV_*` is the correct semantic namespace because:

- These vars are only read when `ACCESS_CONFIG_SOURCE=env`; they are env-source-specific
  runtime config, not sync operational settings.
- `ACCESS_CONFIG_` is already the prefix used by `AccessConfigSettings` (the sub-slice
  controlling which config source is active); `ACCESS_CONFIG_ENV_*` is a natural sub-namespace.
- An operator can infer the relationship: set `ACCESS_CONFIG_SOURCE=env` → populate
  `ACCESS_CONFIG_ENV_*` vars.

### Implementation pattern (`_EnvModel` in `loaders.py`)

```python
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class _EnvModel(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
    )

    dir_prefix: str = Field(default="", alias="ACCESS_CONFIG_ENV_DIR_PREFIX")
    dir_separator: str = Field(default="-", alias="ACCESS_CONFIG_ENV_DIR_SEPARATOR")
    platforms_json: str = Field(default="{}", alias="ACCESS_CONFIG_ENV_PLATFORMS_JSON")
```

`Field(alias=...)` is appropriate here — `_EnvModel` is a private parsing type used
exclusively for env-source config loading. It is never serialized via `.model_dump()` (the
ADR-07 caution about `alias` affecting serialization does not apply).

### Files to update

| File | Change |
|------|--------|
| `app/packages/access/common/config/loaders.py` | Rename `alias=` values and all references in docstrings/error messages |
| `app/packages/access/sync/README.md` | Rename vars in env-source setup examples |
| `app/tests/unit/packages/access/sync/conftest.py` | Rename vars in env cleanup fixtures |
| `app/tests/integration/packages/access/sync/conftest.py` | Rename vars in env cleanup fixtures |

### Rule for future env-source vars

Any new env var read only when `ACCESS_CONFIG_SOURCE=env` must use the
`ACCESS_CONFIG_ENV_*` prefix. Document this in the `_EnvModel` class docstring.

---

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| A deployed SSM parameter was missed in the search | Confirmed: no match in `terraform/` (Terraform manages all SSM params via `aws_ssm_parameter`), `app/infrastructure/configuration/`, or `app/core/`. Feature flag `ACCESS_SYNC_ENABLED=false` has never triggered loader construction in production. |
| Developer adds a future env-source var with `ACCESS_SYNC_` prefix | Rule above + `_EnvModel` docstring + this ADR define the correct prefix |

---

## Sources

- ADR-07 (2026-03-20) — AliasChoices for *deployed* key migration (constraint does not
  apply to greenfield vars)
- Architecture Review: Access Level 3 Settings (2026-04-27) — Section 13, Q3
- Codebase search (2026-04-27): zero Terraform / infrastructure / SSM references to the
  three legacy var names
