# Settings Singleton Pattern

**Reference**: `docs/decisions/tier-1-foundation/application-lifecycle/02-settings-singleton.md`

## Pattern

Settings loaded once at startup via `@lru_cache` singleton. Always access via provider function.

---

## Implementation

### Provider Function (Already Exists)

```python
# infrastructure/services/providers.py
from functools import lru_cache
from infrastructure.configuration import Settings

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()
```

**Do NOT modify this function.**

---

### Usage in Routes

```python
# modules/*/controllers.py
from fastapi import APIRouter
from infrastructure.services import SettingsDep

router = APIRouter()

@router.get("/config")
def get_config(settings: SettingsDep):
    """Settings injected as dependency."""
    return {
        "environment": settings.environment,
        "region": settings.aws.aws_region,
    }
```

**Pattern**: Use `SettingsDep` type annotation for FastAPI dependency injection.

---

### Usage in Services/Jobs

```python
# modules/*/service.py or jobs/*.py
from infrastructure.services import get_settings

class MyService:
    def __init__(self, settings: Settings):
        """Receive settings via dependency injection."""
        self.settings = settings
    
    def process(self):
        return self.settings.environment

# Instantiation
service = MyService(settings=get_settings())
```

**Pattern**: Services receive `Settings` in `__init__`, caller passes `get_settings()`.

---

### Usage in Standalone Functions

```python
# jobs/sync_groups.py
from infrastructure.services import get_settings

def sync_groups_job():
    """Job function calls get_settings directly."""
    settings = get_settings()
    
    if settings.environment == "development":
        return  # Skip in dev
    
    # Process...
```

**Pattern**: Call `get_settings()` once at function start, store in local variable.

---

## Forbidden Patterns

```python
# ❌ Direct instantiation
from infrastructure.configuration import Settings
settings = Settings()  # WRONG

# ❌ Import settings object
from infrastructure.configuration import settings  # WRONG - doesn't exist

# ❌ Call get_settings in service __init__
class Service:
    def __init__(self):
        self.settings = get_settings()  # WRONG - receive via parameter

# ❌ Call get_settings repeatedly
def process():
    region = get_settings().aws.aws_region
    env = get_settings().environment  # WRONG - call once, store
```

---

## Environment Variables

```bash
# .env file uses double underscore for nested config
AWS__AWS_REGION=us-east-1
AWS__AWS_ACCOUNT_ID=123456789012
GOOGLE__CREDENTIALS_BASE64=...
```

**Pattern**: `DOMAIN__SETTING_NAME` for nested configuration.

---

## Validation

Settings validate on first `get_settings()` call. Invalid config raises `ValidationError` and terminates process.

```python
# Pydantic validation happens automatically
settings = get_settings()  # ValidationError if AWS__AWS_REGION missing
```

**This is correct behavior - fail fast on invalid config.**
