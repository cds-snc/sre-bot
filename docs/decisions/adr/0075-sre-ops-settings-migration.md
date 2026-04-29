---
adr_id: ADR-0075
title: "SreOpsSettings Migration to packages/sre_ops"
status: Accepted
decision_type: Migration
tier: Tier-5
primary_domain: Configuration and Secrets
secondary_domains:
  - Package and Plugin Architecture
owners:
  - SRE Team
date_created: 2026-04-29
last_updated: 2026-04-29
last_reviewed: 2026-04-29
next_review_due: 2026-08-27
constrained_by:
  - ADR-0055
impacts: []
supersedes: []
superseded_by: []
review_state: current
related_records:
  - ADR-0047
  - ADR-0056
related_packages:
  - app/modules/sre
---

# SreOpsSettings Migration to packages/sre_ops

## Context

`SreOpsSettings` is defined in `app/infrastructure/configuration/features/sre_ops.py` and provides a single environment variable for SRE operations notifications. Per ADR-0055 Standard 3 (reader-owns rule) and Standard 4 (transitional posture), this settings class must migrate to `app/packages/sre_ops/settings.py` when `app/modules/sre/` migrates to `app/packages/sre_ops/`.

**Note:** The current consumer (`app/modules/ops/notifications.py`) reads `settings.sre_ops.SRE_OPS_CHANNEL_ID` at module-level import time, assigning it to a module constant `OPS_CHANNEL_ID`. This violates ADR-0046 (no side effects at import time) and must be fixed as part of the migration.

## Decision

**Migrate `SreOpsSettings` to `app/packages/sre_ops/settings.py`** when `app/modules/sre/` migrates to `app/packages/sre_ops/`.

### Source Artifact

| Artifact | Path |
|----------|------|
| Settings class | `app/infrastructure/configuration/features/sre_ops.py` |
| Settings aggregator field | `Settings.sre_ops: SreOpsSettings` |
| Re-export | `app/infrastructure/configuration/features/__init__.py` |

### Target Artifact

| Artifact | Path |
|----------|------|
| Settings class | `app/packages/sre_ops/settings.py` |
| Singleton provider | `app/packages/sre_ops/settings.py :: get_sre_ops_settings()` |

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `SRE_OPS_CHANNEL_ID` | Slack channel ID for SRE operations notifications |

### Target Pattern

Follow the `AccessSettings` reference implementation (ADR-0055 Standard 1):

```python
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class SreOpsSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", env_file=".env")

    ops_channel_id: str = Field(default="", alias="SRE_OPS_CHANNEL_ID")

@lru_cache(maxsize=1)
def get_sre_ops_settings() -> SreOpsSettings:
    return SreOpsSettings()
```

### Consumers

| File | Access Pattern | Issue |
|------|---------------|-------|
| `app/modules/ops/notifications.py` | `OPS_CHANNEL_ID = settings.sre_ops.SRE_OPS_CHANNEL_ID` (module-level) | Import-time side effect — violates ADR-0046 |

### Migration Steps

1. Create `app/packages/sre_ops/settings.py` with `SreOpsSettings(BaseSettings)` and `get_sre_ops_settings()`.
2. Fix the import-time side effect in the consumer: replace module-level constant with a function call or lazy accessor.
3. Update all consumers in `app/packages/sre_ops/` to use `get_sre_ops_settings()` instead of `settings.sre_ops`.
4. Remove `SreOpsSettings` from `infrastructure/configuration/features/sre_ops.py`.
5. Remove re-export from `infrastructure/configuration/features/__init__.py`.
6. Remove `Settings.sre_ops` field from the aggregator.

### Blocking Prerequisite

Migration of `app/modules/sre/` to `app/packages/sre_ops/`.

### Retirement Criteria

All conditions must be true:

1. `app/infrastructure/configuration/features/sre_ops.py` is deleted.
2. `SreOpsSettings` is removed from `infrastructure/configuration/features/__init__.py`.
3. `Settings.sre_ops` field is removed from the Settings aggregator.
4. No imports of `SreOpsSettings` remain in the codebase.
5. The import-time side effect in `app/modules/ops/notifications.py` (or its successor) is eliminated.
6. Quality gates pass: `mypy`, `flake8`, `black --check .`, `pytest app/tests --ignore=app/tests/smoke`.

### Target Date

TBD — blocked on prerequisite module migration from `app/modules/sre/` to `app/packages/sre_ops/`.

## Consequences

- The sre_ops package becomes self-contained for settings, following the access package pattern.
- The import-time side effect fix is a prerequisite for correct startup behavior under the lifespan model (ADR-0046).
