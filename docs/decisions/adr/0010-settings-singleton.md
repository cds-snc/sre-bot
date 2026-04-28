---
adr_id: ADR-0010
title: "Settings Singleton Pattern"
status: Accepted
decision_type: Principle
tier: Tier-1
date_created: unknown
last_updated: 2026-04-28
last_reviewed: unknown
next_review_due: 2026-04-28
owners:
  - Platform Engineering
supersedes: []
superseded_by: []
related_records:
  - ADR-0002
  - ADR-0007
  - ADR-0008
related_packages: []
review_state: stale
---
# Settings Singleton Pattern

## Context

Configuration must be loaded and validated once, cached for the process lifetime, and accessed consistently by all services. Pydantic's validation runs on instantiation, so we need a safe, single point of construction.

## Decision

Create ONE Settings instance per ECS task via `@lru_cache(maxsize=1)` on a provider function. Pydantic validates on first call; subsequent calls return the cached instance from the same ECS task.

## Consequences

- ✅ Guaranteed single validation per task
- ✅ Invalid configuration raises `ValidationError` and terminates startup
- ✅ Thread-safe across sync and async handlers
- ⚠️ Cache must be seeded during startup (first `get_settings()` call during initialization)

---

## Implementation

```python
# infrastructure/services/providers.py
from functools import lru_cache
from infrastructure.configuration import Settings

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton Settings - created once per ECS task."""
    return Settings()  # Pydantic validates on instantiation
```

```python
# infrastructure/configuration/__init__.py
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class AWSConfig(BaseModel):  # ✅ BaseModel for nested sections, NOT BaseSettings
    aws_region: str
    aws_account_id: str


class Settings(BaseSettings):
    """Application configuration from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    environment: str = "development"
    log_level: str = "INFO"

    aws: AWSConfig
```

---

## Environment Variables

Nested config uses double underscore:

```bash
# .env
ENVIRONMENT=production
LOG_LEVEL=INFO
AWS__AWS_REGION=us-east-1
AWS__AWS_ACCOUNT_ID=123456789012
```

---

## Usage

**Routes** (dependency injection):
```python
from infrastructure.services import SettingsDep

@router.get("/")
def handler(settings: SettingsDep):
    return {"region": settings.aws.aws_region}
```

**Jobs/Services**:
```python
from infrastructure.services import get_settings

settings = get_settings()  # Returns cached singleton
return {"region": settings.aws.aws_region}
```

---

## Rules

- ✅ Use `@lru_cache(maxsize=1)`
- ✅ Use double underscore for nested settings
- ✅ Validate at instantiation time
- ❌ NEVER: `Settings()`
- ❌ NEVER: Direct import from `infrastructure.configuration`
- ❌ NEVER: Call `get_settings()` in service constructors (receive as parameter)
