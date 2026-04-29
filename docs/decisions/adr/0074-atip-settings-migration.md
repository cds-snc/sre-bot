---
adr_id: ADR-0074
title: "AtipSettings Migration to packages/atip"
status: Accepted
decision_type: Migration Decision
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
  - ADR-0044
  - ADR-0055
impacts: []
supersedes: []
superseded_by: []
review_state: current
related_records:
  - ADR-0047
  - ADR-0056
related_packages:
  - app/modules/atip
---

# AtipSettings Migration to packages/atip

## Context

`AtipSettings` is defined in `app/infrastructure/configuration/features/atip.py` and provides a single environment variable for the ATIP (Access to Information and Privacy) feature. Per ADR-0055 Standard 3 (reader-owns rule) and Standard 4 (transitional posture), this settings class must migrate to `app/packages/atip/settings.py` when `app/modules/atip/` migrates to `app/packages/atip/`.

## Decision

**Migrate `AtipSettings` to `app/packages/atip/settings.py`** when `app/modules/atip/` migrates to `app/packages/atip/`.

### Source Artifact

| Artifact | Path |
|----------|------|
| Settings class | `app/infrastructure/configuration/features/atip.py` |
| Settings aggregator field | `Settings.atip: AtipSettings` |
| Re-export | `app/infrastructure/configuration/features/__init__.py` |

### Target Artifact

| Artifact | Path |
|----------|------|
| Settings class | `app/packages/atip/settings.py` |
| Singleton provider | `app/packages/atip/settings.py :: get_atip_settings()` |

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `ATIP_ANNOUNCE_CHANNEL` | Slack channel ID for ATIP announcements |

### Target Pattern

Follow the `AccessSettings` reference implementation (ADR-0055 Standard 1):

```python
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class AtipSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", env_file=".env")

    announce_channel: str | None = Field(
        default=None, alias="ATIP_ANNOUNCE_CHANNEL"
    )

@lru_cache(maxsize=1)
def get_atip_settings() -> AtipSettings:
    return AtipSettings()
```

### Migration Steps

1. Create `app/packages/atip/settings.py` with `AtipSettings(BaseSettings)` and `get_atip_settings()`.
2. Update all consumers in `app/packages/atip/` to use `get_atip_settings()` instead of `settings.atip`.
3. Remove `AtipSettings` from `infrastructure/configuration/features/atip.py`.
4. Remove re-export from `infrastructure/configuration/features/__init__.py`.
5. Remove `Settings.atip` field from the aggregator.

### Blocking Prerequisite

Migration of `app/modules/atip/` to `app/packages/atip/`.

### Retirement Criteria

All conditions must be true:

1. `app/infrastructure/configuration/features/atip.py` is deleted.
2. `AtipSettings` is removed from `infrastructure/configuration/features/__init__.py`.
3. `Settings.atip` field is removed from the Settings aggregator.
4. No imports of `AtipSettings` remain in the codebase.
5. Quality gates pass: `mypy`, `flake8`, `black --check .`, `pytest app/tests --ignore=app/tests/smoke`.

### Target Date

TBD — blocked on prerequisite module migration from `app/modules/atip/` to `app/packages/atip/`.

## Consequences

- The atip package becomes self-contained for settings, following the access package pattern.
- With only one field, this is the simplest migration in the Wave 3.5 set and can serve as a template for teams executing their first settings migration.
