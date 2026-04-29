---
adr_id: ADR-0073
title: "AWSFeatureSettings Migration to packages/aws_ops"
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
  - app/modules/aws
---

# AWSFeatureSettings Migration to packages/aws_ops

## Context

`AWSFeatureSettings` is defined in `app/infrastructure/configuration/features/aws_ops.py` and provides admin group and operations group configuration for AWS operations. Per ADR-0055 Standard 3 (reader-owns rule) and Standard 4 (transitional posture), this settings class must migrate to `app/packages/aws_ops/settings.py` when `app/modules/aws/` migrates to `app/packages/aws_ops/`.

## Decision

**Migrate `AWSFeatureSettings` to `app/packages/aws_ops/settings.py`** when `app/modules/aws/` migrates to `app/packages/aws_ops/`.

### Source Artifact

| Artifact | Path |
|----------|------|
| Settings class | `app/infrastructure/configuration/features/aws_ops.py` |
| Settings aggregator field | `Settings.aws_feature: AWSFeatureSettings` |
| Re-export | `app/infrastructure/configuration/features/__init__.py` |

### Target Artifact

| Artifact | Path |
|----------|------|
| Settings class | `app/packages/aws_ops/settings.py` |
| Singleton provider | `app/packages/aws_ops/settings.py :: get_aws_ops_settings()` |

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `AWS_ADMIN_GROUPS` | List of admin group emails for AWS operations |
| `AWS_OPS_GROUP_NAME` | Operations group name |

### Target Pattern

Follow the `AccessSettings` reference implementation (ADR-0055 Standard 1):

```python
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class AwsOpsSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", env_file=".env")

    admin_groups: list[str] = Field(
        default=["sre-ifs@cds-snc.ca"], alias="AWS_ADMIN_GROUPS"
    )
    ops_group_name: str = Field(default="", alias="AWS_OPS_GROUP_NAME")

@lru_cache(maxsize=1)
def get_aws_ops_settings() -> AwsOpsSettings:
    return AwsOpsSettings()
```

### Consumers

| File | Access Pattern |
|------|---------------|
| `app/modules/aws/groups.py` | `settings.aws_feature.AWS_ADMIN_GROUPS` (multiple call sites) |
| `app/modules/aws/groups.py` | `settings.aws_feature.AWS_OPS_GROUP_NAME` |

### Migration Steps

1. Create `app/packages/aws_ops/settings.py` with `AwsOpsSettings(BaseSettings)` and `get_aws_ops_settings()`.
2. Update all consumers in `app/packages/aws_ops/` to use `get_aws_ops_settings()` instead of `settings.aws_feature`.
3. Remove `AWSFeatureSettings` from `infrastructure/configuration/features/aws_ops.py`.
4. Remove re-export from `infrastructure/configuration/features/__init__.py`.
5. Remove `Settings.aws_feature` field from the aggregator.

### Blocking Prerequisite

Migration of `app/modules/aws/` to `app/packages/aws_ops/`.

### Retirement Criteria

All conditions must be true:

1. `app/infrastructure/configuration/features/aws_ops.py` is deleted.
2. `AWSFeatureSettings` is removed from `infrastructure/configuration/features/__init__.py`.
3. `Settings.aws_feature` field is removed from the Settings aggregator.
4. No imports of `AWSFeatureSettings` remain in the codebase.
5. Quality gates pass: `mypy`, `flake8`, `black --check .`, `pytest app/tests --ignore=app/tests/smoke`.

### Target Date

TBD — blocked on prerequisite module migration from `app/modules/aws/` to `app/packages/aws_ops/`.

## Consequences

- The aws_ops package becomes self-contained for settings, following the access package pattern.
- `AWS_ADMIN_GROUPS` default value (`["sre-ifs@cds-snc.ca"]`) is preserved in the migrated settings class; deployment configurations should be audited to ensure this default is explicitly overridden in all environments.
